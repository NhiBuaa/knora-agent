# Issue #17 Worker Coordination Design

Status: Approved (2026-08-09)  
Source: [GitHub Issue #17](https://github.com/NhiBuaa/knora-agent/issues/17)  
Parent: [Milestone 2](https://github.com/NhiBuaa/knora-agent/issues/14)

## Decision summary

`ProcessIngestionJob` is the deep module. Its external interface is one operation:

```python
result = processor.run_once(worker_id)
```

The module hides expired-attempt recovery, bounded execution admission, atomic claim, heartbeat,
deadline precedence, failure mapping, retry policy, fenced outcome persistence and ambiguous-commit
reconciliation. Issue #18 supplies the concrete PDF/embedding Work Handler, concrete typed success
value and production worker loop; it does not duplicate coordination.

This design is constrained by the canonical meanings in `CONTEXT.md`, the Architecture Standard,
ADRs 0001 and 0005, and the approved Issue #17 design ledger. If an implementation detail cannot
satisfy one of those invariants, the design decision must be reopened rather than weakened in code.

## Alternatives considered

### Alternative A: closed command executor

Expose `observe_expired_attempt()` plus one overloaded `execute(command)` persistence method over a
closed command algebra.

This minimizes method count and keeps transaction commands immutable. It does not materially
shrink the persistence interface: every command, reply and invariant remains knowledge required by
the adapter, while generic dispatch weakens method-local typing and navigation. Rejected as false
depth at the persistence seam.

### Alternative B: flexible policy kernel

Inject store, handler, runner, supervisor factory, mapping, policy, random source, operation-ID
factory, clock and profile independently.

This maximizes replaceability, but exposes correctness-sensitive assembly and creates hypothetical
seams for V1 mapping and policy that have only one implementation. Rejected because flexibility
makes construction shallow and permits mismatched clocks/runtime dependencies.

### Alternative C: default-caller facade

Keep one external `run_once` operation and use explicit typed persistence methods for the distinct
transaction shapes.

This gives the Issue #18 loop the smallest useful interface while retaining local, searchable
persistence operations. Selected, combined with Alternative A's strong tagged values and distinct
operation-ID types. V1 cause mapping and retry policy remain concrete internal modules rather than
hypothetical ports.

## File and module ownership

```text
backend/src/knora/
├── ingestion/
│   └── job_processing.py
│       ProcessIngestionJob, consumer-owned ports, immutable commands/results,
│       FailureCauseV1, CauseMappingV1, RetryPolicyV1, AttemptSupervisor
└── adapters/
    ├── postgres/
    │   ├── ingestion_job_store.py
    │   │   Existing PostgresIngestionJobStore gains coordination operations
    │   └── tables.py
    │       IngestionJobTable plus IngestionJobAttemptTable
    └── execution/
        └── thread_attempt_runner.py
            Fixed-capacity thread-backed AttemptRunner
```

The exact execution-adapter directory may remain `adapters/` without a new subdirectory if one file
does not yet justify it. No generic `services`, `repositories`, `ports` or `common` package is
introduced. The consumer-owned persistence interface initially remains beside its module in
`job_processing.py`; moving it later to break a demonstrated import cycle does not change the seam.

## External interface

```python
SuccessT = TypeVar("SuccessT")


class ProcessIngestionJob(Generic[SuccessT]):
    def __init__(
        self,
        *,
        store: IngestionJobCoordinationStore[SuccessT],
        handler: WorkHandler[SuccessT],
        runtime: AttemptRuntime[SuccessT],
        random_source: RandomSource,
        operation_ids: OperationIdFactory,
        telemetry: CoordinationTelemetry,
    ) -> None: ...

    def run_once(self, worker_id: WorkerId) -> RunOnceResult: ...
```

`AttemptRuntime` is a construction parameter object containing one shared monotonic clock,
scheduler and bounded Attempt Runner. It prevents incompatible clock domains without creating a
new behavioral port. `CauseMappingV1` and `RetryPolicyV1` are concrete internal modules built by
`ProcessIngestionJob`; only their true varying inputs are injected.

The future worker loop receives an already-composed module:

```python
while not stop.is_set():
    result = processor.run_once(worker_id)
    if isinstance(result, NoEligibleJob):
        stop.wait(idle_poll_interval)
```

Polling, daemon lifetime and process-level operational backoff remain Issue #18 concerns.

### Six lifecycle results

Use frozen tagged value objects, not a bare enum or nullable-field record:

```python
RunOnceResult = (
    NoEligibleJob
    | Succeeded
    | Superseded
    | RetryScheduled
    | FailedTerminal
    | LeaseLost
)
```

Attempt-bearing results include an immutable `AttemptRef(job_id, attempt_number)`. Retry result
includes the authoritative `next_attempt_at`; terminal failure includes canonical failure reason
and allowlisted safe code. Superseded may include validated replacement identifiers.

`RunnerCapacityUnavailable`, definite coordination persistence failure,
`CoordinationOutcomeIndeterminate` and `CoordinationInvariantError` are operational/programming
exceptions, never extra lifecycle results.

## Work interface and immutable capability

```python
@dataclass(frozen=True, slots=True)
class FencingToken:
    job_id: IngestionJobId
    attempt_number: int
    worker_id: WorkerId
    lease_version: int


@dataclass(frozen=True, slots=True)
class ClaimedAttempt:
    token: FencingToken
    work: IngestionWork
    attempt_count: int
    max_attempts: int
    attempt_started_at: datetime
    initial_lease_expires_at: datetime
    deadline_at: datetime


class WorkHandler(Protocol[SuccessT]):
    def execute(
        self,
        work: IngestionWork,
        cancellation: CancellationToken,
    ) -> WorkOutcome[SuccessT]: ...


WorkOutcome = WorkSucceeded[SuccessT] | WorkSuperseded | WorkFailed
```

`IngestionWork` contains data-only Workspace, Document/Version, Original Source Object and immutable
configuration references needed by the future handler. It contains no ORM object, store, callback,
session or transaction. The handler cannot persist lifecycle or activation state.

`WorkSucceeded[SuccessT]` carries only an immutable data-only value. The type parameter flows
through handler, processor, outcome and store. `Any`, untyped mapping/JSON and persistence
capabilities are forbidden. Issue #17 tests with a frozen fake success value; Issue #18 supplies the
concrete value and same-transaction activation implementation.

`WorkSuperseded` is an expected non-failure typed domain condition. Arbitrary zero-row updates do
not prove supersession. `WorkFailed` uses a closed handler-specific failure kind and allowlisted safe
code; raw exception/provider/SQL text goes only to internal telemetry.

## Failure mapping and retry policy

`CauseMappingV1` is a total, pure exhaustive mapping from handler failure kinds to the unified
`FailureCauseV1`. Supervisor timeout and expired-attempt recovery originate `ATTEMPT_TIMEOUT` and
`LEASE_EXPIRED` directly. Coordination-store errors never become `DATABASE_TRANSIENT`.

`RetryPolicyV1` is the sole owner of retryability:

```text
decide(cause, attempt_count, max_attempts)
  -> ScheduleRetry | FailTerminal | RetryExhausted
```

It samples exact integer-duration full jitter once only for `ScheduleRetry`:

```text
after attempt 1: [0, 5 seconds]
after attempt 2: [0, 30 seconds]
after attempt 3: [0, 120 seconds]
attempt 4 retryable failure: exhausted, no sample
non-retryable failure: terminal, no sample
```

The 5-minute cap clamps a future nominal window before sampling; it does not add a V1 retry. Store
receives typed relative delay/audit and anchors it to fresh database time.

## Consumer-owned persistence interface

Explicit methods mirror complete transaction-shaped use cases:

```python
class IngestionJobCoordinationStore(Protocol[SuccessT]):
    def observe_expired_attempt(self) -> ExpiredAttemptObservation | None: ...

    def apply_expired_recovery(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> RecoveryResult: ...

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: WorkerId,
        timing: AttemptTimingV1,
    ) -> ClaimResult: ...

    def heartbeat(
        self,
        *,
        operation_id: HeartbeatOperationId,
        token: FencingToken,
        lease_duration: ExactDuration,
    ) -> HeartbeatResult: ...

    def finalize_success(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        success: SuccessT,
    ) -> FinalizationResult: ...

    def finalize_superseded(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        outcome: WorkSuperseded,
    ) -> FinalizationResult: ...

    def schedule_retry(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> FinalizationResult: ...

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: FailTerminal | RetryExhausted,
    ) -> FinalizationResult: ...
```

The eight methods are intentionally explicit. In particular, the four durable exits from
processing are represented by `schedule_retry`, `finalize_success`, `finalize_superseded` and
`finalize_terminal_failure`. They expose different legal transaction shapes;
collapsing them into generic `execute`, `transition` or `update_status` would not reduce the command
knowledge an adapter needs and would weaken locality.

Result variants are closed and disjoint:

- claim: `NoEligibleClaim | ClaimedAttempt | HistoricalClaimLost`;
- heartbeat: `HeartbeatApplied | Fenced`;
- recovery: `RecoveryRetryScheduled | RecoveryFailedExhausted | StaleObservation | NotExpired`;
- finalization: `FinalizationApplied | Fenced | InvalidTransition`.

Expected races are values. Invalid decision/capacity pairing, incompatible operation-ID binding or
impossible durable data raises `CoordinationInvariantError`.

## Attempt Runner and supervisor

```python
class AttemptRunner(Protocol[SuccessT]):
    def try_reserve(self) -> ExecutionPermit[SuccessT] | None: ...


class ExecutionPermit(Protocol[SuccessT]):
    def start(
        self,
        handler: WorkHandler[SuccessT],
        work: IngestionWork,
        cancellation: CancellationToken,
    ) -> RunningAttempt[SuccessT]: ...

    def release(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AttemptCompletion(Generic[SuccessT]):
    completed_at: MonotonicInstant
    result: WorkOutcome[SuccessT] | HandlerRaised
```

Reservation occurs after recovery fallback and before claim. No capacity raises
`RunnerCapacityUnavailable` without a database mutation. Claim-none/error releases the permit.
Successful start transfers the fixed-capacity slot to execution; detach keeps it until physical
handler exit. The permit guarantees normal start acceptance after claim.

`AttemptSupervisor` is a concrete internal module, not a replaceable protocol. It owns scheduling,
heartbeat, deadline precedence, cancellation, detach, the single-heartbeat-in-flight barrier and
quiescing. It returns `HandlerCompleted | AttemptTimedOut | SupervisorLeaseLost` only after future
heartbeat scheduling is closed and any in-flight heartbeat is authoritatively resolved.

Runner captures immutable completion time from the shared monotonic clock at the handler return/
raise boundary. Completion wins only for `completed_at < local_deadline`; equality is timeout.
Definite heartbeat fencing vetoes completion/timeout. Indeterminate heartbeat cancels, detaches,
prevents finalization and raises. Timeout/lease loss never waits for handler termination. Late
completion is consumed into internal telemetry only.

## `run_once` implementation hidden behind the seam

1. Observe at most one expired attempt.
2. Evaluate `LEASE_EXPIRED` through Retry Policy V1 and conditionally recover with one logical
   transition ID.
3. Return immediately on applied recovery, including zero delay. Fall through once on absent,
   stale or not-expired observation.
4. Reserve bounded execution capacity.
5. Capture the local monotonic attempt-start point, generate one claim ID and atomically claim one
   queued or due retry-scheduled job.
6. Release the permit on no claim, historical claim loss or claim error.
7. Supervise exactly one handler invocation.
8. Convert accepted handler/supervisor fact into success, superseded or canonical failure.
9. Quiesce heartbeat, generate one transition ID and perform exactly one typed fenced exit:
   schedule retry, finalize success, finalize superseded or finalize terminal failure.
10. Translate only authoritative durable results to the six lifecycle outcomes.

A successful recovery and a newly claimed handler attempt never occur in the same invocation.
Stale/not-expired recovery may fall through and claim a retry another coordinator just scheduled.
Business work, policy, random sampling and delay anchoring are never repeated for reconciliation.

## Operation IDs and ambiguous commits

Use distinct `ClaimOperationId`, `HeartbeatOperationId` and `TransitionOperationId` value types. One
logical mutation receives one ID reused across transport attempts/read-back. Retained records bind
operation kind, immutable request identity, decision/disposition and deterministic fingerprint.

Claim replay proves historical commit and then revalidates current, processing, unexpired ownership
with fresh database time before returning an executable capability. Outcome/recovery replay returns
the exact persisted disposition, policy audit and anchored timestamps. Heartbeat permits exactly one
logical operation in flight and retains latest ID, request fingerprint and resulting expiry on the
job projection.

An unresolved ambiguous outcome raises `CoordinationOutcomeIndeterminate` with non-secret operation
and attempt context. Handler does not run before claim reconciliation; ambiguous finalization does
not rerun work; indeterminate heartbeat stops scheduling and prevents outcome commit. No generic
operation ledger is introduced.

## PostgreSQL transaction design

All Issue #17 mutating paths that lock multiple rows use lock order:

```text
ingestion_jobs row -> current ingestion_job_attempts row -> Issue #18 activation rows
```

Heartbeat locks only the job row. The activation-row suffix is an extension contract for Issue #18,
not an Issue #17 dependency: Issue #17 imports or locks no activation table. Issue #18 must extend
the established job/attempt prefix and must not acquire activation locks before returning to either
coordination row. No transaction remains open while handler work runs.

### Atomic claim

1. Reconcile retained `claim_operation_id` first.
2. Otherwise select one eligible queued/due-retry job using `FOR UPDATE SKIP LOCKED LIMIT 1`.
3. Order by effective eligibility time, then `created_at`, then job ID.
4. Sample fresh database time after row-lock acquisition and revalidate status, due time and
   capacity.
5. Increment `attempt_count` and `lease_version` once; set current worker/timing/lease projection;
   insert the exactly matching open attempt; commit.

Normal claim never selects processing rows. Lease validity is `fresh_db_time < lease_expires_at`;
equality is expired.

### Heartbeat

Lock job, sample fresh time after lock, then predicate on processing, job/worker/lease generation
and unexpired current lease. Extend to sample plus two minutes, retain operation binding/result and
never bump lease version.

### Recovery and finalization

Recovery observation is unlocked and uses database time. Conditional recovery/finalization lock job
then attempt, take one fresh time sample after locks and reuse it for predicates/timestamps. Recovery
revalidates exact observed expiry and all identity/policy inputs. Fenced operations check ownership
before transition legality so stale callers receive `FENCED`.

## Migration and schema

### `ingestion_jobs` additions

```text
worker_id
lease_version NOT NULL DEFAULT 0
lease_expires_at
current_attempt_number
current_attempt_started_at
current_attempt_deadline_at
next_attempt_at
terminal_at
failure_reason
safe_failure_code
terminal_outcome_code
replacement_document_version_id
replacement_ingestion_job_id
last_heartbeat_operation_id
last_heartbeat_request_fingerprint
last_heartbeat_resulting_lease_expires_at
```

Current-attempt and active-lease fields exist only while processing. Lease version remains after
exit as fencing history. Heartbeat binding fields reset on a new lease generation.

### `ingestion_job_attempts`

```text
ingestion_job_id, attempt_number                 composite primary key
worker_id, lease_version
attempt_started_at, deadline_at, initial_lease_expires_at
claim_operation_id, claim_request_fingerprint
closed_at, disposition, closure_cause
failure_cause, failure_cause_version, cause_mapping_version
safe_failure_code, failure_reason, terminal_outcome_code
retry_policy_version, policy_result, jitter_version
retry_window_upper_bound_microseconds, retry_delay_microseconds
resulting_next_attempt_at
transition_operation_id, transition_request_fingerprint
replacement_document_version_id, replacement_ingestion_job_id
```

There is no success JSON/blob and no operations ledger.

### Constraints

- state-specific job counters/nullable fields and `attempt_count <= max_attempts`;
- unique claim operation ID and unique non-null transition operation ID within their kinds;
- unique partial open attempt per job;
- one allowed open-to-closed mutation, then no normal-role update/delete;
- deferrable commit-time processing iff exactly-one-current-open-attempt validation;
- retry projection matches latest attempt schedule;
- terminal projection matches latest attempt disposition.

Stable partial indexes accelerate queued claim, retry-scheduled claim and processing-expiry scans.
They contain no dynamic time predicate. Correctness never depends on planner/index use.

### Migration order

1. Add nullable projection columns and attempt table.
2. Assert every legacy row is queued with zero attempts; abort otherwise.
3. Backfill only known queued-state values and lease version zero.
4. Add stable indexes and initially tolerant checks.
5. Validate checks and tighten nullability/defaults.
6. Install deferrable correspondence and closed-history protection triggers.

No unknown worker/lease/attempt history is synthesized.

## Issue #17 versus Issue #18 production completeness

Issue #17 implements and tests the full generic orchestration interface, Retry Policy V1,
supervisor, bounded thread runner, migration, atomic claim, heartbeat, recovery, failure and
superseded persistence. The fake typed store proves success orchestration.

The PostgreSQL adapter is not a complete production `IngestionJobCoordinationStore[SuccessT]` until
Issue #18 supplies the concrete success value/schema and fenced transaction that atomically commits
derivation/activation with `status=succeeded`. Production handler wiring before that point is
forbidden; `status=succeeded` is never committed as a placeholder.

## Implementation-planning gates

The tracer-bullet plan must preserve these checks:

1. Every slice that adds an exit from processing uses its explicit typed persistence operation.
   Retry and superseded paths may not be hidden inside a generic status/terminal mutation.
2. Execution capacity is reserved only after expired-recovery fallback and before claim. No-claim
   and authoritative claim failure release it; successful execution owns it through physical
   handler exit; detach does not release it. A post-claim start failure takes an explicit safe
   fenced retry/terminal path and cannot silently leave processing state.
3. Issue #17 lock acquisition ends at job then open attempt. Issue #18 may append activation locks
   only after that prefix and cannot introduce a reverse order or an Issue #17 activation import.
4. Before meaningful implementation, establish a bounded reproducible test baseline or identify
   the current full-suite hang. The existing timeout is not attributed to this docs-only design,
   but implementation cannot finish with an unbounded/hanging suite as its only regression signal.

## Test surfaces

### Application interface

`backend/test/ingestion/test_job_processing.py` crosses `run_once` with deterministic fake store,
runner, monotonic runtime, random source, operation IDs, telemetry and immutable success value.

It covers recovery-first flow, six results, capacity-before-claim, policy/RNG invariants, exact
deadline, delayed completion observation, cancellation/detach, late completion, heartbeat races,
indeterminate outcomes and no work/policy replay.

### Runner and supervisor

Focused tests use synchronization primitives or deterministic scheduler actions, never sleeps, for
bounded permits, single-assignment completion, exact completion/detach resolution, heartbeat
barrier and late exception telemetry.

### PostgreSQL adapter

`backend/test/adapters/postgres/test_ingestion_job_coordination.py` uses real PostgreSQL for
simultaneous claims, deterministic ordering, fresh-time lock waits, fencing, operation replay,
recovery races, atomic projection/history, deferred constraints and immutable history. Correctness
tests must pass without relying on index plans.

### Migration

Upgrade tests preserve valid queued legacy rows and fail loudly on fabricated non-queued/nonzero
legacy state.

## Depth and locality

The worker loop learns one operation and six results. Deleting `ProcessIngestionJob` would spread
recovery, claim, supervision, policy, fencing and reconciliation across callers, so the module earns
its interface.

Lifecycle knowledge remains local to `job_processing.py`; SQL and authoritative reconciliation stay
in the PostgreSQL adapter; execution races stay in Attempt Runner/Supervisor. The persistence port is
wider than the external interface because its methods represent genuinely different atomic
transactions. That width is deliberate and preferable to a generic shallow transition interface.

## Published tracer-bullet graph

Approved and published on 2026-08-09:

1. [#25 — Establish bounded worker-coordination verification baseline](https://github.com/NhiBuaa/knora-agent/issues/25) — no blockers.
2. [#26 — Process one queued attempt to deterministic terminal failure](https://github.com/NhiBuaa/knora-agent/issues/26) — blocked by #25.
3. [#27 — Schedule, reclaim, and exhaust a retryable attempt](https://github.com/NhiBuaa/knora-agent/issues/27) — blocked by #26.
4. [#28 — Recover an expired attempt through scheduled retry](https://github.com/NhiBuaa/knora-agent/issues/28) — blocked by #27.
5. [#29 — Supervise a bounded attempt with heartbeat and timeout](https://github.com/NhiBuaa/knora-agent/issues/29) — blocked by #27.
6. [#30 — Reconcile attempt-backed ambiguous mutations](https://github.com/NhiBuaa/knora-agent/issues/30) — blocked by #28.
7. [#31 — Reconcile ambiguous heartbeats](https://github.com/NhiBuaa/knora-agent/issues/31) — blocked by #29.
8. [#32 — Complete the six-result worker coordination contract](https://github.com/NhiBuaa/knora-agent/issues/32) — blocked by #30 and #31.

Native GitHub blocking edges are authoritative. The initial frontier is #25 only.
