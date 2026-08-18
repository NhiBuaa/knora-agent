## Objective

Remediate the M3 improvement-claim authority so production accepts only a verifiable,
independent authority chain and reads policy values from the approved JSON projection as
the sole normative source.

Design: `docs/design/m3-remediation-v2.md` (R1), approved artifact
`.agents/design/m3-remediation-v2.json`.

## Scope

- Add a versioned external-review artifact bound to the exact authority source commit,
  policy projection blob/digest, complete claim-rule scope, reviewer identity, seal and
  closure.
- Reject missing, malformed, mutated, self-authored, self-approved, or unprovable
  reviewer/author/approver chains before any policy decision.
- Parse and strictly validate the approved JSON policy projection at its content-addressed
  Git blob. Remove the duplicated full value-level policy map from the production validator.
- Keep explicit focused-test fixtures behind `production=False`; caller authority and policy
  overrides remain rejected.
- Preserve old authority/approval/seal artifacts as immutable history and append new
  revision artifacts only.

## Acceptance

1. The current self-attested `NhiBuaa` reviewer/approver chain is rejected.
2. A separately sealed independent-review chain with a concrete reviewer identity passes.
3. Source-commit, policy-blob, scope, seal, closure and reviewer identity mutations fail closed.
4. Unknown/malformed policy projection fields and caller authority/policy overrides fail closed.
5. Focused authority tests and repository verification are green; no raw secrets or traces are
   committed.

## Dependencies and invariants

- Child of Milestone 3 parent Issue #48.
- Uses the existing improvement-claim seam; no retrieval or evaluation-only path is introduced.
- R3 guide/final acceptance is blocked by this ticket through a native GitHub dependency edge.
