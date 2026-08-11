# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Final approved and immutable
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r5`
- Supersedes: drafts R1–R4, which remain unchanged draft history.
- Baseline: all fixed authority, prerequisites, traceability, test cases, expected results, and
  evidence requirements in `m2-issue-20-r4` remain part of this guide unless replaced below.
- Baseline provenance: R4 SHA-256
  `8ca29b8013144aec5cd67faa10aacd8d2fb7179870fe111513314d299e4c5e23`, captured in this worktree
  at Git revision `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7` before this lock.
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-10T03:56:04Z
- Manual-acceptance state: Locked for implementation; execution remains pending implementation.

## Unchanged R4 coverage

R5 retains without weakening the R4 oracles for superseded citation/trace/evaluation retention,
asynchronous terminal cleanup in `succeeded`/`superseded`/`failed`, cleanup-path stale ownership
revalidation, W2 reconciliation read canary, W2 ObjectStore denial, canonical Compose MinIO,
bounded streaming and capability-boundary audit, cleanup per-attempt counters, replay controls,
alert sustain-window negatives, and DB/ObjectStore gap plus crash-after-delete evidence.

## Revised acceptance traceability matrix

| Issue #20 criterion | Falsifiable test coverage |
| --- | --- |
| Original retention; approved hard deletion; failed-upload diagnostic retention | R4 TC-01, R4 TC-02, R4 TC-05 |
| Async/idempotent cleanup of staging, temporary, and partial artifacts | R5 TC-04, R4 TC-03, R4 TC-10 |
| Independent cleanup failure/retry without outcome reversal | R4 TC-03, R5 TC-04, R4 TC-08 |
| Safe orphan reconciliation and Workspace isolation | R4 TC-06; R5 TC-08 |
| SHA-256 metadata and Workspace-scoped ObjectStore behavior | R4 TC-07 |
| Queue and lifecycle metric semantics | R5 TC-08 |
| Configured alert boundary and recovery behavior | R5 TC-09 |
| MinIO and approved S3-compatible subset | R4 TC-07 |
| Contract tests on Compose MinIO and configured provider | R4 TC-07 |
| DB/ObjectStore gaps, duplicate delivery, crash, supersession, failed uploads, retained originals | R4 TC-01–TC-07, R4 TC-10; R5 TC-04, TC-08 |

## Replaced test cases

### TC-04: Prove asynchronous ordering and duplicate delivery for superseded and failed cleanup

- Setup: retain R4's canonical `superseded` and `failed` state × applicable temporary/partial
  artifact matrix, deterministic cleanup barrier, and retained Original Source Object sentinel.
  Do not invent a failure subtype for an inapplicable artifact cell.
- Steps for each applicable state/class cell:
  1. Hold destructive cleanup at the deterministic barrier.
  2. Complete the terminal transition and prove the Job/Attempt terminal state is durable while the
     artifact remains present; prove terminalization did not wait for destructive cleanup.
  3. Release cleanup. Execute the first successful delivery and capture the authoritative converged
     lifecycle/object state.
  4. Deliver the same logical cleanup intent again. Read authoritative lifecycle/object state and
     destructive-operation trace after the duplicate.
- Expected results:
  - Terminalization is durable before cleanup; synchronous-only failed/superseded cleanup cannot
    pass. Each applicable artifact is cleaned/absent after first delivery.
  - Duplicate delivery converges idempotently: it creates no inconsistent second lifecycle effect
    and does not delete any retained Original Source Object.
- Evidence: state/class matrix with authoritative `not applicable` rationale; barrier/commit/order
  trace; first-delivery result; duplicate-delivery result; before/after authoritative object and
  lifecycle state; destructive-operation trace; retained-original trace.

### TC-08: Calculate Operational Metrics V1 with positive reconciliation counter oracle

- Setup: retain R4's recorded metric-counter baseline and all queue, retry, lease-expiry, claim
  histogram, cleanup, replay, empty-population, and excluded-disposition fixtures. Additionally
  seed authoritative completed corrective dispositions: one completed repair of an inconsistent
  database/object record and one completed deletion of an eligible unreferenced orphan. Seed first
  orphan discovery and then a re-observation of that same unresolved orphan.
- Cleanup fixture: retain R4's durable attempt A that fails, independently scheduled distinct
  attempt B that succeeds, and all A/B/failure replay controls.
- Steps:
  1. Independently calculate all gauges, histogram effects, rate, and monotonic counter deltas from
     the captured baseline, without calling metrics implementation.
  2. Collect the contract-visible Operational Metrics V1 representation at the same observation.
  3. Replay/read back an already completed corrective disposition if the Operational Metrics V1
     implementation exposes that replay case; otherwise record it as not applicable under the
     existing authority.
- Expected results:
  - All R4 queue, claim, retry, lease-expiry, cleanup-attempt/failure, label, and excluded-population
    assertions continue to pass unchanged.
  - `orphan_discovery_total` delta is exactly 1 for first discovery; re-observation adds 0.
  - `orphan_reconciliation_total` delta is exactly 2 for the completed repair and completed eligible
    deletion. Report-only, too-young, retained, cross-Workspace, and delete-suppressed dispositions
    each add 0. A supported replay/read-back adds 0.
- Evidence: captured baseline; independent ledger/calculator; completed repair/deletion records;
  discovery/re-observation records; metric delta snapshot; excluded-disposition records; and replay
  result where applicable.

### TC-09: Prove required alert-definition completeness, then boundaries

- Setup: load the versioned configured alert definitions and enumerate their required classes:
  queue age/contention, repeated lease-expiry recovery, cleanup backlog, and unreconciled orphan
  growth.
- Steps:
  1. Prove one versioned configured definition exists for each required class. Fail the case if any
     class is missing.
  2. For each configured definition, separately hold the metric below predicate/threshold for the
     complete sustain duration.
  3. For that same definition, separately sustain a qualifying breach for less than its configured
     sustain window.
  4. Sustain a qualifying breach for the configured window, then clear the configured condition.
- Expected results:
  - A missing required alert definition fails acceptance before boundary testing.
  - Steps 2 and 3 independently produce no alert. Step 4 produces the matching alert and then its
    configured recovery behavior.
  - No numeric default is invented, and alerting does not mutate ingestion or start cleanup.
- Evidence: definition inventory/version/class mapping; four metric-window traces per definition;
  alert/recovery events; and unchanged ingestion/cleanup projections.

## Final adversarial audit before approval

- [ ] An always-zero `orphan_reconciliation_total` fails the completed repair/deletion oracle.
- [ ] Omitting any required alert class fails before its boundary test.
- [ ] A second cleanup delivery that fails after a first success cannot pass.
- [ ] R4's superseded-retention, asynchronous-ordering, cleanup-race, Compose-MinIO, metric-replay,
  and gap/crash controls remain intact.

This revision is immutable. Any semantic change discovered during implementation requires a new
guide revision; do not edit this locked guide. Execution observations belong in a separate
Evaluation JSONL record.
