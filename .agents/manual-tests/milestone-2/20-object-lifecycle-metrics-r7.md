# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; ADR 0014; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r7`
- Supersedes: R1–R6, which remain unchanged draft history.
- Baseline: all R5 acceptance semantics and R6 production-seam traceability/oracles remain locked
  into this draft unless refined below by approved authority.
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## R7 seam-specific acceptance additions

### TC-11: Atomic terminalization and lifecycle-work insertion

- Inject a deterministic fault/barrier around terminalization and lifecycle-work insertion. On
  failure, read both projections authoritatively.
- Expected results:
  - No committed terminal Job/Attempt exists without its required deduplicated
    `object_lifecycle_work` item.
  - On success, terminal Job/Attempt and exactly one lifecycle-work item become durable together.
  - Replaying the same terminalization returns its durable result and creates no second work item.
- Evidence: before/after terminal Job/Attempt and work projections, work identity/deduplication result,
  fault/barrier ordering, and replay result. No SQL statement shape is asserted.

### TC-12: Single-owner claim and stale-worker fencing

- Seed one eligible lifecycle work item. Workers A and B contend at a deterministic claim barrier.
  Establish B as valid owner after A becomes stale under approved lease/fencing semantics.
- Expected results:
  - Exactly one active lifecycle attempt owns the item at any time; immutable history never shows two
    simultaneous valid owners.
  - Stale A is fenced by `prepare_delete` and lifecycle completion.
  - B can claim and converge the work with its valid capability.
- Evidence: typed claim outcomes/tokens, attempt ownership projection, lease generations, A fence
  results, B completion, and immutable history. `FOR UPDATE SKIP LOCKED` text is not inspected.

### TC-13: Fence a prepared delete generation

- Through `ObjectLifecycleMaintenance`, bring eligible work to `prepare_delete` and capture prepared
  generation G1. Pause before ObjectStore delete.
- Steps:
  1. Through the existing authoritative lifecycle fixture/gateway, attach or retain the object or
     add a blocking reference. Commit and prove the new state visible.
  2. Resume the worker with stale G1.
  3. Run a positive control with an unchanged valid prepared generation.
- Expected results:
  - Stale G1 is fenced/suppressed before destructive effect; ObjectStore delete count is zero and
    retained object remains present.
  - The unchanged valid generation completes cleanup successfully.
- Evidence: G1 preparation, attachment/reference commit read-back, fenced/suppressed result, zero
  delete trace, retained object state, and positive-control completion. No second production
  attachment API is invented.

### TC-14: Exercise Object Lifecycle Retry Policy V1 deterministically

- Inject one controlled random source at the policy/application boundary. Run the same policy input
  twice with the same controlled sequence and record durable lifecycle attempt history.
- Expected results:
  - Four attempts are the total budget; attempts are distinct immutable lifecycle attempts.
  - After attempt 1 failure, chosen delay is within inclusive `[0, 5s]`; after attempt 2, `[0, 30s]`;
    after attempt 3, `[0, 2m]`. Exact chosen delay and policy/jitter versions are persisted.
  - Equal policy input plus equal controlled sequence produces equal chosen delays. Policy logic does
    not read global/process randomness directly.
  - Attempt 4 failure transitions lifecycle work to terminal `failed`; no fifth attempt exists.
  - Cleanup retry/failure never changes the already-durable Ingestion Job outcome.
- Evidence: controlled sequence, policy inputs, exact chosen delays/windows, immutable attempt rows,
  terminal lifecycle projection, no-fifth-attempt read-back, and unchanged Ingestion Job result.

## Updated traceability and adversarial self-audit

R5/R6 matrix coverage remains unchanged. TC-11 covers atomicity; TC-12 covers single-owner/fencing;
TC-13 covers delete-generation fencing and positive completion; TC-14 covers complete retry
budget/window/exhaustion. Audit before approval:

- [ ] A broken two-transaction terminalization cannot pass.
- [ ] Double claim and stale-worker completion cannot pass.
- [ ] Attachment after prepared generation cannot cause destructive delete.
- [ ] Unlimited, wrong-window, or fifth-attempt retry cannot pass.
- [ ] R5/R6 oracles and evidence remain intact; no matrix overclaim or requirement lacks evidence.

This guide becomes immutable only after explicit human approval. Any semantic change requires a new
revision. Execution observations belong in a separate Evaluation JSONL record.
