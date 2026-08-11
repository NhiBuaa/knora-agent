# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Final approved and immutable
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; ADR 0014; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r9`
- Supersedes: R1–R8. R5 is the previously approved immutable historical baseline; R6–R8 are
  unchanged draft history.
- Layered baseline provenance: worktree base commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`;
  R5 SHA-256 `d2fc737f8cced4ef778c5b1014a25f8150ab217f3ef177a13c206df98bb31e29`; R6 SHA-256
  `66a639259ea7abe4a560cc50d9cec8ae0f674209c9fb8af48bca3158146d8637`; R7 SHA-256
  `ee5720322b23e57fa68c723e1272da32f54b0de5edaa68ef40595e6ef15088e5`; R8 SHA-256
  `7eebc7a8fa70d91df24ea52db3037d831b3fe72768a337a4420e7de588d02e64`.
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-10T04:45:29Z
- Manual-acceptance state: Locked for implementation; execution remains pending implementation.

## Replacement TC-14: Exact deterministic full-jitter boundary contract

- Inject a controlled RandomSource at the approved policy/application boundary. The source records
  every requested upper bound and returns a configured valid sample. It does not expose or require
  RNG SDK/library internals.
- For each retry scheduling decision, record the boundary call count, requested upper bound, returned
  sample, and persisted lifecycle-attempt result.

### Steps

1. Fail attempt 1. Require exactly one RandomSource request with upper bound `5s`; return known valid
   sample X1 and read the persisted chosen delay.
2. Fail attempt 2. Require exactly one request with upper bound `30s`; return X2 and read the exact
   persisted chosen delay.
3. Fail attempt 3. Require exactly one request with upper bound `2m`; return X3 and read the exact
   persisted chosen delay.
4. Repeat the same policy input and controlled sequence and compare every request and persisted
   delay. Repeat one scheduling decision with a different valid returned sample Y.
5. Fail attempt 4 and read the lifecycle work and immutable attempt history.

### Expected results

- The requested bounds are exactly `5s`, `30s`, and `2m`, in order, with exactly one source call per
  scheduling decision. A larger or smaller bound fails even if its returned sample is numerically
  inside the expected final window.
- Persisted `chosen_delay` equals X1, X2, X3, and Y exactly. The policy does not ignore, transform,
  reroll, or otherwise replace a valid returned sample.
- Equal policy input and controlled sequence produce the same requests and persisted delays.
- Attempt 4 is terminal lifecycle `failed`; exactly four distinct immutable attempts exist and no
  fifth attempt exists. Cleanup retry/failure leaves the already-durable Ingestion Job outcome
  unchanged.

### Evidence

Capture the controlled RandomSource boundary trace (requested upper bound, call count, returned
sample), exact persisted chosen delays and policy inputs, immutable attempt history, terminal/no-fifth
projection, and unchanged Ingestion Job result. Do not capture or assert SDK internals.

## Final adversarial audit

- [ ] Wrong upper bound with an accidentally valid delay fails.
- [ ] Multiple RandomSource draws for one scheduling decision fail.
- [ ] Ignored or transformed returned sample fails.
- [ ] Fifth-attempt creation fails.
- [ ] R5–R8 TC-11 bidirectional atomicity, TC-12B stale pre-issued capability fencing, and all other
  locked baseline oracles remain unchanged and traceable.

This revision is immutable. Any semantic change discovered during implementation requires a new
guide revision; do not edit this locked guide. Execution observations belong in a separate
Evaluation JSONL record.
