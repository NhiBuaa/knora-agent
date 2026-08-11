
# Milestone 2 Module Seams

Status: Approved; delivered through Issue #19 (2026-08-10)
Source: [Milestone 2 specification and design ledger](https://github.com/NhiBuaa/knora-agent/issues/14)

Milestone 2 extends the existing capability-first layout. It does not add a top-level
`milestone-2` package. Existing Milestone 1 interfaces remain stable while PDF submission,
processing, storage, and worker behavior enter through explicit modules and adapters.

Issues #15–#19 have delivered the durable PDF submission, deterministic extraction, worker
coordination, PDF derivation/activation, and public polling/reprocess slices described below. The
seams remain the ownership contract for the next Milestone 2 tickets; this document does not make
the standalone worker scheduler or an S3 adapter part of the current HTTP application.

## Application modules

### Ingest Document

`IngestDocument` remains the synchronous Markdown and plain-text module:

```text
IngestDocument.execute(command, principal) -> IngestionResult
```

Its implementation remains in `knora/ingestion/module.py`. PDF submission must not add format
switching, background work, or ObjectStore behavior to this module.

### Ingestion Jobs

`IngestionJobs` owns durable submission, status lookup, and reprocessing:

```text
IngestionJobs.submit_pdf(command, principal) -> PdfSubmissionResult
IngestionJobs.get_job_status(ingestion_job_id, principal) -> JobStatusProjection
IngestionJobs.reprocess_document_version(command, principal) -> ReprocessResult
```

Issues #15 and #19 deliver the submission, status and reprocess entry points in this module. It
hides request idempotency, content/configuration deduplication, source version creation,
current-version updates, job generation, audit binding and compensation for an unreferenced
uploaded object. The public status projection and reprocess result are serialized by the HTTP
adapter; callers do not read the PostgreSQL projection directly.

The interface and implementation stay in `knora/ingestion/jobs.py`. HTTP handlers translate
transport input and delegate to this module. They do not query PostgreSQL tables or construct
object keys.

### Process Ingestion Job

`ProcessIngestionJob` owns worker orchestration delivered by Issues #17 and #18 and consumed by
Issue #19. It coordinates claims, fenced leases, ObjectStore reads, extraction, chunking,
embedding, persistence, activation, retries and cleanup outcomes.

The Issue #17 orchestration contract remains strongly typed without knowing the Issue #18 success
schema: one immutable data-only type parameter flows through `WorkHandler[SuccessT]`,
`ProcessIngestionJob[SuccessT]`, `WorkSucceeded[SuccessT]` and
`IngestionJobCoordinationStore[SuccessT]`. `Any`, untyped mappings, callbacks and persistence
handles are not valid success payloads. Issue #18 supplies the concrete value object and its
fenced atomic derivation/activation persistence.

Its implementation is `knora/ingestion/job_processing.py`. The application composes the worker and
the durable-work PDF handler in `knora.main`; a deployment-specific daemon loop remains outside
this seam.

## PDF extraction seam

Issue #16 places the `PdfTextExtractor` interface and PDF result/configuration types in
`knora/ingestion/pdf.py`. The pinned `pypdf` implementation is the adapter in
`knora/adapters/pdf/pypdf.py`.

The adapter hides child-process execution, parser options, resource enforcement, and parser error
translation. Deterministic normalization and page-bounded chunking remain behind the PDF interface.
`knora/ingestion/processing.py` remains the Milestone 1 text/Markdown processor and must not become
a format switchboard.

## Persistence and storage seams

### Synchronous derivation persistence

`knora/ingestion/store.py` remains the persistence interface for synchronous Milestone 1
derivations. Its PostgreSQL adapter remains
`knora/adapters/postgres/ingestion_store.py`.

### Ingestion Job persistence

The PostgreSQL adapter for durable Ingestion Jobs is
`knora/adapters/postgres/ingestion_job_store.py`. It owns submission, claim, lease, retry, public
status, reprocess, idempotency and audit transactions delivered by Issues #15, #17 and #19.

Worker coordination depends on a consumer-owned `IngestionJobCoordinationStore` application port,
initially beside `ProcessIngestionJob` in `knora/ingestion/job_processing.py`. The existing
PostgreSQL adapter implements this port as well as `PdfSubmissionStore`; a separate concrete store
is not required. Each typed operation owns one complete transaction. Atomic claim returns an
immutable Claimed Attempt/fencing capability, while heartbeat and outcome operations return typed
transition results. The port exposes no ORM row, session, connection, transaction, generic status
update or commit operation. Moving the port later to avoid a demonstrated dependency cycle does
not change this seam.

Issue #17 adds durable `ingestion_job_attempts` history beside the mutable `ingestion_jobs`
scheduling/current-owner projection. Attempt number equals the job counter after atomic increment,
a partial unique constraint permits one open attempt per job, and a closed attempt is immutable.
Lease-expiry recovery is a coordinator-policy transition: the port may observe an expired attempt,
then conditionally apply the coordinator's retry/exhaustion decision against the unchanged job,
lease generation and open attempt. This optimistic two-step recovery is not a split claim; actual
claim remains one atomic operation and occurs only after a scheduled retry becomes due.

The immutable expiry observation is not a capability. Conditional apply revalidates job and open
attempt identity, worker, lease version, counters and exact observed lease expiry using fresh
database time after locks. It returns disjoint typed stale, not-expired and applied outcomes;
policy/capacity mismatch is an invariant error. Multiple coordinators may evaluate different
jitter samples, but exactly one decision can be persisted. Normal claim never direct-reclaims an
expired processing row, including for zero-delay recovery.

Current-attempt fields on `ingestion_jobs` are explicitly named and exist only while processing;
they exactly match the open history row and clear on closure. Attempt history stores immutable
`initial_lease_expires_at`, not heartbeat-renewed expiry. Stable partial indexes accelerate queued,
due-retry and expired-processing candidate scans without embedding clock expressions. Deferrable
commit-time validation (or equivalent) enforces cross-table correspondence while allowing valid
multi-statement transactions.

The migration asserts all pre-existing jobs are queued with zero attempts, the only state the
pre-#17 production application can create, and fails rather than synthesizing unknown history.
Issue #17 adds no generic success JSON or production-only success transition; Issue #18 specializes
the typed success port and adds concrete activation persistence before wiring its handler. Issue #19
adds the public lifecycle, serving, retry-hint and successful terminal-result projections without
exposing internal coordination identifiers.

Job projection and attempt history enter and leave processing atomically. PostgreSQL must enforce
the cross-table correspondence—processing if and only if exactly one current-numbered attempt is
open—through transaction design plus constraint triggers or an equivalent mechanism; application
assertions and a partial unique index alone are insufficient. Fenced operations check current
ownership before transition legality so stale calls return `FENCED`.

The port preserves separate time domains. PostgreSQL supplies fresh authoritative wall time for
durable timestamps, eligibility and fencing; coordinator APIs do not pass authoritative wall-clock
`now`. `AttemptSupervisor` uses an injected monotonic clock only for elapsed scheduling. Retry
policy supplies a relative typed delay which persistence anchors to fresh database time.

`ProcessIngestionJob.run_once` uses recovery-first precedence: one successful recovery returns, a
stale/not-expired recovery may fall through once, and normal claim starts at most one handler
attempt. Its tagged result has six variants—no eligible job, succeeded, superseded, retry
scheduled, terminal failure and lease lost. Persistence exceptions with an ambiguous commit are
reconciled authoritatively or remain explicit indeterminate infrastructure failures; they are not
invented lifecycle outcomes.

Every mutating port call accepts one logical operation ID whose immutable request binding and
durable result are retained with attempt history for claim/outcome/recovery reconciliation. Claim
replay revalidates current unexpired ownership before exposing a capability. Heartbeat keeps only
the latest ID/result under a single-heartbeat-in-flight invariant. No generic operations ledger is
introduced for no-op claim replay or historical heartbeat replay.

Worker failure facts converge on one closed `FailureCauseV1` coordinator taxonomy before retry
policy. A pure versioned mapping converts handler-specific failure kinds; supervisor timeout and
lease-expiry recovery produce canonical causes directly. Coordination-port failures never enter
that taxonomy. Attempt history persists canonical cause and version alongside the later policy
decision.

`AttemptRunner` is a narrow execution port used by `AttemptSupervisor`. It captures a
single-assignment completion at the handler-return boundary with the injected monotonic clock and
supports idempotent cancellation plus logical detach. The Issue #17 thread adapter uses fixed
bounded capacity reserved before claim; a detached handler retains its slot until physical exit.
The port carries no coordination persistence or policy. Issue #18 may replace the bounded thread
adapter with stronger process isolation without changing supervisor semantics.

`knora/adapters/postgres/tables.py` remains the shared SQLAlchemy table registry. Split it only
when a later ticket demonstrates that one file obscures ownership or migration safety.

### Object Lifecycle Maintenance

`ObjectLifecycleMaintenance` lives in `knora/ingestion/object_lifecycle.py`. It owns
cleanup and orphan reconciliation application behavior, not Ingestion Job terminal state. Its
consumer-owned lifecycle store port returns typed work claims, delete-preparation capabilities and
typed completion/reconciliation results; it exposes no ORM rows, sessions, transactions, generic
status updates or ObjectStore implementation details.

The PostgreSQL ingestion-job-store adapter implements the port. It owns the
transaction that atomically records terminal Job/Attempt state with deduplicated Object Lifecycle
Work and later owns lifecycle attempts, lease/fencing, operation-ID replay and authoritative
delete-time revalidation. `ObjectStore.delete` remains an external idempotent action. A cleanup
worker reconciles the external-delete/record-completion gap through `head`, never by changing the
already-durable Ingestion Job outcome.

### Operational observability

`knora/ingestion/operational_observability.py` owns typed metric collection and
pure alert-policy evaluation. Its `OperationalMetricsStore` and `OperationalTelemetry` ports stay
beside the module; the Postgres adapter supplies purpose-specific read-only snapshots and telemetry
adapters receive only typed low-cardinality values. `config.py` owns bootstrap loading of immutable,
versioned `OperationalAlertConfigurationV1`.

### ObjectStore

The `ObjectStore` interface lives in `knora/ingestion/object_store.py`. Callers receive opaque
keys and cannot construct storage paths.

Adapters live under `knora/adapters/object_store/`:

- `filesystem.py` supports local development and deterministic tests.
- `s3.py` provides the S3-compatible adapter.

`S3ObjectStore` is selected by typed `ObjectStoreSettings` in `config.py` and composed in
`main.py`. Its injected private provider-capability client exposes only streaming put/get, head and
delete; a capability-audit wrapper observes that boundary for contract tests without leaking SDK
internals into the application interface.

## HTTP adapters

HTTP routes and schemas remain under `knora/adapters/http/`. The document upload route selects the
synchronous text module or the durable PDF module from transport metadata, then delegates. It owns
HTTP status selection and serialization, not application rules or persistence. The same adapter now
exposes Workspace-scoped PDF job polling and current Document Version reprocess routes with
no-store polling responses, retry hints, safe terminal metadata and explicit configuration-source
selection.

## Target directory ownership

```text
backend/
├── migrations/
│   └── versions/
├── src/knora/
│   ├── ingestion/
│   │   ├── interface.py
│   │   ├── module.py
│   │   ├── processing.py
│   │   ├── store.py
│   │   ├── jobs.py
│   │   ├── job_processing.py        # create when Issues #17/#18 need it
│   │   ├── object_lifecycle.py
│   │   ├── operational_observability.py
│   │   ├── object_store.py
│   │   └── pdf.py
│   └── adapters/
│       ├── http/
│       │   ├── routes.py
│       │   └── schemas.py
│       ├── postgres/
│       │   ├── tables.py
│       │   ├── ingestion_store.py
│       │   └── ingestion_job_store.py
│       ├── object_store/
│       │   ├── filesystem.py
│       │   └── s3.py
│       └── pdf/
│           └── pypdf.py
└── test/
    ├── ingestion/
    └── adapters/
        ├── http/
        ├── postgres/
        ├── object_store/
        └── pdf/
```

Tests mirror the module that owns the behavior. Application behavior is tested through the
application interface. Adapter-specific contract tests stay under the matching adapter directory.
PostgreSQL atomicity and concurrency tests may use focused persistence projections where the
approved acceptance seam requires them.

## Dependency direction

- `domain` imports no FastAPI, SQLAlchemy, storage SDK, parser library, or model SDK.
- `ingestion` owns application interfaces and may depend on domain and provider interfaces.
- `adapters` depend on application interfaces. Application modules do not import adapters.
- `main.py` and `bootstrap.py` compose adapters with application modules.

Avoid generic `services`, `repositories`, `utils`, `helpers`, and `common` directories. Add a new
directory only when an approved ticket gives it one clear owner.
