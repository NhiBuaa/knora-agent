# Milestone 3 remediation design v2

Status: approved design checkpoint, 2026-08-18

This design responds to the external review recorded in
`.agents/review/m3-remediation-external-review-aggregation-v1.json`. Historical
approval, acceptance, and review artifacts remain immutable; this document defines the
next append-only remediation slices.

## Scope and invariants

The remediation preserves the M3 production seam and the already-accepted retrieval,
trace, citation, refusal, and evaluation contracts. It adds no evaluation-only retrieval
path and does not change the meaning of `retrieval_latency_ms` or
`end_to_end_latency_ms`. Raw traces and credentials remain in authorized persistence.

The production improvement boundary must fail closed unless all of the following are
bound and verifiable:

- an independent review artifact covers the exact authority source commit, policy
  projection, and complete claim-rule scope; reviewer identity is concrete and differs
  from the source-commit author and approver;
- the approved policy JSON projection is the sole normative value source, with a
  content-addressed Git blob and strict schema/type validation;
- the immutable M3 dataset and corpus manifests resolve to the exact `m3-dataset-v1`
  population and matching corpus/Chunk Set provenance;
- vector-only and hybrid reports are a complete paired population with only retrieval
  configuration differences;
- the selected record retains vector and hybrid latency observations, explicit
  pair-level deltas, guardrails, metric deltas, and every remaining regression.

## Bounded slices

### R1 — authority chain and sole-source policy projection

Seam: `canonical_authority_validation` and `ClaimRuleAuthority` in
`evals/runners/m3_claim_authority.py`.

The slice adds a versioned external-review artifact and a new sealed authority revision.
The validator binds its reviewer identity, source commit, policy projection digest, review
scope, seal, and closure. It rejects missing, malformed, mutated, self-authored, or
self-approved chains before a policy outcome. It parses and validates the approved JSON
projection at the bound Git blob; production no longer contains a duplicated full policy
value map. Explicit focused-test fixtures remain available only through
`production=False`.

Acceptance must prove both the current self-attested chain rejection and a separately
sealed independent-review chain that passes, plus projection mutation/unknown-field,
caller-authority, and caller-policy override failures.

### R2 — immutable population binding and paired latency retention

Seam: `select_production_improvement` in
`evals/runners/milestone_3_comparison.py`, with the existing dataset/corpus loaders as
the manifest-verification boundary.

The production selector resolves a repository-bound verified M3 population capability.
It does not accept caller-supplied expected case IDs or a caller-supplied dataset digest.
The capability binds dataset version/digest, the exact sorted 50-case IDs, corpus
manifest version/digest, and Chunk Set provenance. Reduced or synthetic populations stay
available only through the explicit non-production comparison fixture seam.

Reports must also carry a versioned pair-level latency projection. For each case it keeps
vector and hybrid `retrieval_latency_ms`, vector and hybrid
`end_to_end_latency_ms`, the explicit `hybrid_minus_vector` deltas, and clock-boundary
metadata. No latency hard threshold or inferred metric is introduced. The selected
artifact retains both sides of this projection, guardrails, metric deltas, and
`remaining_regressions`.

Acceptance must prove full-manifest success and fail-closed subset, extra-case, and
same-shaped-wrong-digest mutations at the canonical production seam; the non-production
fixture seam remains usable.

### R3 — guide v7 and final integrated acceptance

R3 is directly blocked by R1 and R2 through GitHub native dependency edges. It revises
the Issue #63 guide without rewriting v6. The new guide adds authority identity/source
coverage, exact manifest population and wrong-digest negatives, selected vector/hybrid
latency and regression retention, and the applicability rule that semantic citation is
required for `ANSWER` but inapplicable (not missing) for `REFUSAL`.

After R1 and R2 integrate, R3 locks the guide, executes acceptance, runs the final
fixed-point review, and reruns the cadence evidence gate.

## Dependency graph

```text
R1 authority + sole-source policy  ─┐
                                    ├── R3 guide v7 + final acceptance
R2 population + latency retention ──┘
```

R1 and R2 may proceed independently from the pinned M3 remediation integration head.
R3 cannot start until both parent slices are merged and their acceptance evidence is
append-only and approved.

## Completion gate

M3 closes only at a new fixed point with code review `APPROVE` and zero Critical/Major
findings, cadence status `ready`, zero observation failures, valid immutable provenance,
and a selected/improvement decision that discloses metric deltas, guardrails, pair-level
latency trade-offs, and remaining regressions. Issue #48 remains open until that gate
passes and the integration/default-branch/worktree invariants are clean.
