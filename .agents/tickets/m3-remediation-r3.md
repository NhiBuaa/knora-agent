## Objective

Revise the Issue #63 manual acceptance guide to v7 and execute the final integrated M3
acceptance after R1 and R2 are merged.

Design: `docs/design/m3-remediation-v2.md` (R3), approved artifact
`.agents/design/m3-remediation-v2.json`.

## Scope

- Create an append-only guide revision; do not rewrite v6 or its Evaluation history.
- Add authority external-review identity, source-commit coverage and reviewer/author/approver
  separation cases.
- Add exact 50-case dataset/corpus/Chunk Set manifest binding, favorable-subset and
  same-shaped-wrong-digest negatives.
- Require selected-artifact inspection of vector and hybrid latency projections, explicit
  pair-level deltas, guardrails, metric deltas and `remaining_regressions`.
- Clarify semantic citation applicability: required for `ANSWER`; `REFUSAL` is inapplicable,
  not a missing semantic result.
- Execute the guide, record append-only Evaluation evidence, run final fixed-point review and
  cadence gate, then update/close Issue #48 only if every gate is ready.

## Acceptance

1. Native blockers R1 and R2 are closed and their accepted evidence is bound before this ticket
   starts.
2. Guide v7 is externally reviewed/approved and all required cases pass.
3. Final fixed-point code review is `APPROVE` with zero Critical/Major findings.
4. Cadence evidence gate is `ready`; observation failures are zero and all provenance is valid.
5. Issue #48 is updated and closed only after integration/default-branch/worktree checks pass.

## Dependencies and invariants

- Child of Milestone 3 parent Issue #48.
- Directly blocked by R1 and R2 using GitHub native blocking edges; no manual `blocked` label.
- The production `HttpEvaluationExecutor` and exact `(workspace_id, trace_id)` seam remain the
  only evaluation path.
