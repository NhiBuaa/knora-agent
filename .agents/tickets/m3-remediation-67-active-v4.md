## Objective

Publish and execute the final M3 paired-claim acceptance guide after #68 and #69 integrate.

Authoritative design: `docs/design/m3-remediation-v4.md`.
Locked guide: `.agents/manual-tests/milestone-3/63-remediation-issue-63-v8.md`.

## Acceptance

- #68 and #69 are closed with accepted evidence before this ticket starts.
- Guide v8 is independently reviewed/approved without rewriting v6/v7 histories.
- Public `answer`, citation marker/order/alias mapping and exact request correlation are checked;
  semantic citation receives only public answer/citation excerpts/source locators; missing trace,
  Workspace mismatch or incomplete provenance is observation failure, not score zero.
- Exact manifests, field-level paired invariants, pair latency/regression retention and no
  evaluation-only-path evidence pass.
- Final fixed-point review is APPROVE with zero Critical/Major, cadence is ready, isolation passes,
  and only then is #48 updated/closed with clean default branch/worktrees.

## Dependency

Child of #48. Directly blocked by #68 and #69 through GitHub native edges; no manual blocked label.
