# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; ADR 0014; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r8`
- Supersedes: R1–R7, which remain unchanged draft history.
- Baseline: all R5 semantics and R6/R7 seam oracles remain part of this draft unless refined below.
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## R8 replacements

### TC-11: Bidirectional atomic terminalization/work invariant

- Apply deterministic pre-commit faults that expose either terminal-first or work-first broken
  two-transaction ordering, then read both projections authoritatively.
- Expected results:
  - Failure before atomic outcome commit leaves neither terminal Job/Attempt nor lifecycle-work
    item durably visible.
  - No terminal-without-work and no work-without-terminal state may exist.
  - Success makes terminal Job/Attempt and exactly one deduplicated work item durable together.
  - Replay creates no second work item.
- Evidence: paired before/after projections for each fault and success/replay; no SQL statement order.

### TC-12B: Fence pre-issued delete capability after lifecycle lease handoff

- A validly claims work and obtains prepared delete generation G_A. Pause before ObjectStore delete,
  expire/fence A through approved lease semantics, establish B as valid owner, then resume A/G_A.
- Expected results: A/G_A is fenced before delete; stale A delete count is zero and cannot complete
  work; B obtains current authorization and converges it; immutable history shows ownership
  succession with no simultaneous valid owners.
- Evidence: claims/generations, lease handoff, A fence results, delete trace, B authorization and
  completion, immutable attempt history.

### TC-14: Exact deterministic full-jitter samples

- Supply known valid controlled samples X1, X2 and X3 for the 5-second, 30-second and 2-minute
  windows. Repeat the same policy input/sequence, then use a different valid sample Y.
- Expected results:
  - Retry attempts 1/2/3 persist chosen delays exactly X1/X2/X3, each inside its authoritative
    inclusive window; same controlled input replays deterministically.
  - Different valid Y persists Y, proving the source result is not ignored or always zero.
  - Attempt 4 failure makes lifecycle work `failed`; exactly four immutable attempts exist and no
    fifth exists. Cleanup failure/retry never changes the durable Ingestion Job outcome.
- Evidence: controlled inputs, exact persisted delay values/windows, distinct attempt history,
  terminal/no-fifth projection, unchanged Job result. Jitter-version metadata is not required.

## Final adversarial self-audit

- [ ] Terminal-only and work-only partial commit cannot pass.
- [ ] A stale pre-issued delete capability after lease handoff cannot delete or complete work.
- [ ] Ignored RandomSource/always-zero jitter cannot pass.
- [ ] Fifth attempt cannot pass; no guide-invented jitter metadata is required.
- [ ] R5–R7 oracles remain intact and every requirement has falsifiable evidence.

This guide becomes immutable only after explicit human approval. Any semantic change requires a new
revision. Execution observations belong in a separate Evaluation JSONL record.
