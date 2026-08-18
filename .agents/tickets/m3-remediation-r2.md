## Objective

Make the canonical production improvement selector bind the immutable M3 population and
retain an auditable vector-versus-hybrid latency trade-off.

Design: `docs/design/m3-remediation-v2.md` (R2), approved artifact
`.agents/design/m3-remediation-v2.json`.

## Scope

- Resolve a repository-bound verified capability for `m3-dataset-v1`, its exact sorted
  50-case IDs, dataset digest, corpus manifest version/digest and Chunk Set provenance.
- Make `select_production_improvement` reject caller-supplied expected IDs, favorable subsets,
  extra cases, and same-shaped wrong digests. Keep reduced populations only on the explicit
  non-production comparison fixture seam.
- Add a versioned pair-level latency projection containing vector and hybrid
  `retrieval_latency_ms`, `end_to_end_latency_ms`, explicit `hybrid_minus_vector` deltas,
  and clock-boundary metadata. Do not add a hard latency threshold or infer one metric from
  the other.
- Retain both sides of the projection, metric deltas, guardrails, and `remaining_regressions`
  in the selected-improvement record.

## Acceptance

1. The full immutable 50-case manifest and matching corpus/Chunk Set provenance pass at the
   canonical production seam.
2. Subset, extra-case, same-shaped wrong-digest, and manifest/corpus mismatch mutations fail
   closed before selection.
3. The reduced non-production fixture seam remains usable for focused tests.
4. A selected artifact retains vector and hybrid latency values, explicit pair deltas,
   guardrails, metric deltas and all remaining regressions.
5. Focused comparison tests and repository verification are green; raw traces/secrets remain
   out of committed artifacts.

## Dependencies and invariants

- Child of Milestone 3 parent Issue #48.
- Uses the existing paired public-Q&A evaluation contract; only retrieval configuration may
  differ between vector baseline and hybrid reports.
- R3 guide/final acceptance is blocked by this ticket through a native GitHub dependency edge.
