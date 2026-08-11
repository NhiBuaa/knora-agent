# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; ADR 0014; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r6`
- Supersedes: R1–R5, which remain unchanged immutable/draft history.
- Baseline: every acceptance semantic, falsifiable oracle, expected result, and evidence requirement
  in locked `m2-issue-20-r5` remains part of this guide unless refined below by approved authority.
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## Production-seam traceability

| Approved seam | R5 coverage refined by R6 | Required observable evidence |
| --- | --- | --- |
| `ObjectLifecycleMaintenance` and lifecycle store | R5 TC-02–TC-06, TC-10 | Typed work/attempt claim and completion result; immutable attempt history; Workspace scope; lease/fencing and operation-ID replay result; no ORM/session evidence. |
| `prepare_delete` delete-generation capability | R5 TC-01, TC-05, TC-06 | Authoritative pre-delete decision, capability generation/fenced-or-suppressed result, and idempotent ObjectStore delete/completion reconciliation. |
| PostgreSQL polling and lifecycle retry | R5 TC-02–TC-04, TC-08 | Atomic terminal Job/Attempt plus deduplicated work read-back; eligible claim; `queued -> processing -> retry_scheduled | succeeded | failed`; independent attempt/retry records; replay result. |
| `OperationalObservability` | R5 TC-08, TC-09 | Typed `OperationalSnapshot` and `OperationalAlert`; independent fixture calculator; no identifier-bearing labels/annotations. |
| `OperationalMetricsStore` / `OperationalTelemetry` | R5 TC-08, TC-09 | Purpose-specific authoritative snapshot evidence and typed low-cardinality emitted values; no ORM/session or raw annotation map assertion. |
| `AlertPolicyV1` / `OperationalAlertConfigurationV1` | R5 TC-09 | Loaded configuration version and complete required-definition inventory; configured predicate/window/recovery evidence, without numeric default. |
| `S3ObjectStore` / `ObjectStoreSettings` bootstrap selection | R5 TC-07 | Typed selected backend and canonical Compose MinIO target or configured S3-compatible target; no credential evidence. |
| `S3CapabilityClient` / capability audit | R5 TC-07 | Provider-boundary allowlist audit for streaming put/get, head, delete only; fail on unapproved capability; no SDK-internal assertion. |

## R6 evidence refinements

### Lifecycle terminalization and dispatch

For every R5 terminalization case, evidence must show one PostgreSQL authoritative read-back in
which the terminal Ingestion Job/Attempt and its deduplicated `object_lifecycle_work` are both
durable. The cleanup worker may claim only after that commit. The test observes typed lifecycle
claim/completion results and independent lifecycle attempts, never store internals.

For retry/replay cases, capture the lifecycle work state, attempt number, lease/fencing result,
operation-ID result and next-eligibility state. A duplicate operation must return its durable result
without another attempt or external delete. Cleanup failure may change only lifecycle work, typed
observability output and alert output; it cannot change the already-durable Ingestion Job outcome.

### Delete-time authorization and crash reconciliation

R5 stale-reference and stale-ownership races exercise `prepare_delete` through
`ObjectLifecycleMaintenance`. Evidence identifies only the typed outcome: prepared generation,
fenced, suppressed, or reconciled. It proves that a newly attached/retained object is suppressed
before ObjectStore delete. After a delete acknowledgement but before lifecycle completion, a resumed
worker reconciles durable work state with `ObjectStore.head` and reaches one typed final result.
It does not re-run an unverified destructive effect.

### Operational observability and alerts

R5 TC-08 obtains a typed `OperationalSnapshot` through `OperationalObservability.collect()` backed
by `OperationalMetricsStore`. Its independent fixture ledger remains the expected-value oracle.
R5 TC-09 obtains versioned definitions through `OperationalAlertConfigurationV1`, evaluates them
through `AlertPolicyV1`, and observes typed alerts through `OperationalTelemetry`. Tests assert only
the approved metric values, configuration version, enum labels and alert state; they do not inspect
SQL, ORM, config storage, or telemetry-provider implementation.

### S3-compatible storage

R5 TC-07 proves bootstrap chooses the typed `ObjectStoreSettings` backend. Its MinIO run uses the
canonical Compose service; its production-provider run uses the configured isolated target. The
capability audit wraps `S3CapabilityClient`, so an unapproved provider capability is an observable
contract failure even when application method logging would otherwise look valid. Tests never assert
SDK internals, credentials, caller-selected keys, or a capability outside the approved allowlist.

## Revised traceability matrix

| Issue #20 criterion | Falsifiable coverage and production seam |
| --- | --- |
| Original retention and failed-upload diagnostic lifecycle | R5 TC-01/TC-02 via `ObjectLifecycleMaintenance` and `prepare_delete` |
| Async/idempotent cleanup and independent failure | R5 TC-02–TC-04 via lifecycle work claim/attempt/replay |
| Orphan reconciliation and Workspace isolation | R5 TC-05/TC-06 via lifecycle work and `prepare_delete` |
| SHA-256 ObjectStore behavior | R5 TC-07 via `S3ObjectStore` and capability audit |
| Queue/lifecycle metrics | R5 TC-08 via `OperationalObservability.collect()` |
| Required alerts | R5 TC-09 via versioned alert configuration/policy/telemetry |
| MinIO and configured S3-compatible provider | R5 TC-07 via bootstrap-selected typed settings |
| Transaction gaps/crash recovery | R5 TC-10 via lifecycle completion reconciliation with `head` |

## Adversarial self-audit

- [ ] Every Issue #20 criterion retains a falsifiable oracle and named evidence.
- [ ] Terminal work insertion, lifecycle claim, lease/fencing, retry and replay cannot false-pass.
- [ ] Delete-generation fencing/revalidation and delete-ack crash reconciliation cannot false-pass.
- [ ] Metrics/alerts test only approved typed seams and cannot leak high-cardinality identifiers.
- [ ] S3 capability audit observes the provider boundary, not only application logs or SDK internals.
- [ ] No matrix row overclaims an inapplicable terminal/artifact cell or lacks required evidence.
- [ ] No new queue, broker, attachment API, retry policy, metric formula, alert threshold, or S3
  capability is introduced by this guide.

This guide becomes immutable only after explicit human approval. Any semantic change requires a new
revision. Execution observations belong in a separate Evaluation JSONL record.
