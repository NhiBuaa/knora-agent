# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Guide revision: issue-51-v12
- Binding authority: `docs/design/m3-evaluation-environment-binding-v3.md`
- Lifecycle authority: `docs/design/m3-evaluation-bootstrap-lifecycle-v1.md` and
  `docs/design/m3-evaluation-sealed-environment-v2.md`
- Supersedes: unapproved `issue-51-v11`, unchanged
- Approval status: approved and locked

## Canonical lifecycle

```text
bootstrap/provision corpus → acquire exclusive seal
→ corpus-closure PASS + capture V3/config provenance snapshot
→ inject startup auth → start production API → measured Q&A
→ post-run verification while seal is still held → stop API
→ release seal/process/ephemeral credential
```

1. Bootstrap provisions/reuses the isolated Workspace and may materialize `m3-corpus-v1` through
   normal application/ingestion seams before seal; this work is not yet authority for measurement.
2. `EvaluationEnvironmentSeal.acquire` establishes exclusive evaluation-run ownership. If it cannot
   acquire it, setup fails and no Q&A occurs.
3. While holding seal, bootstrap runs the authoritative corpus-closure check and captures the
   Binding V3 plus resolved Retrieval Configuration snapshot. This is the only preflight authority
   for measured Q&A.
4. Launcher injects hash-only normal startup auth configuration, starts normal `create_app()` and
   normal `ApiKeyAuthenticator`; raw key remains ephemeral runtime input only.
5. During seal, no corpus/retrieval-provenance mutation may occur. The guarantee may use isolated
   evaluation topology, exclusive run ownership, restricted actors/credentials, or existing
   centralized mutation guard. Q&A and trace persistence are permitted. #51 does not require
   adding evaluation-specific checks to every production mutation path.
6. After Q&A, while still sealed, control plane compares active corpus closure, Binding V3 and
   resolved Retrieval Configuration against the sealed snapshot. It then stops API and releases the
   seal, process and ephemeral credential.

Seal, closure/preflight, post-run verification and teardown are outside the Q&A request/response
interval and never contribute to `end_to_end_latency_ms`.

## TC-01: Sealed authoritative closure and exact production correlation

1. Capture redacted evidence of corpus provisioning followed by successful exclusive seal acquire.
   Capture authoritative closure PASS and Binding V3/configuration snapshot only after seal.
2. Demonstrate each supported mutation path and actor present in the isolated evaluation topology
   cannot mutate the sealed corpus/retrieval provenance. Do not require hypothetical unsupported
   paths to implement evaluation-specific checks.
3. Inject startup auth, start normal production API, and call `POST /v1/questions`. Use only the
   returned `(workspace_id, trace_id)` to read correlated trace.
4. Verify response↔trace identity, Workspace, resolved configuration, fused rank/order, and each
   candidate's exact `(source_key, document_version_id, chunk_set_id)` against V3 before canonical
   projection. Q&A/trace persistence must remain permitted under seal.
5. While seal is still held, re-verify corpus closure, V3 bindings and resolved configuration equal
   the sealed snapshot, before quality report generation; stop API then release lifecycle state.
6. Exercise: seal acquisition failure; mutation by every supported topology actor/path; post-seal
   closure/binding/configuration drift; missing/wrong version or Chunk Set UUID; response/trace
   mismatch; unknown source; malformed rank/order; and post-run verification failure.

Expected results:

- No exclusive seal means no measured Q&A. The no-mutation contract is satisfied by the selected
  evaluation topology/ownership boundary, not a mandatory retrofit of every production mutation
  path.
- Any post-run drift invalidates the entire run as environment/observation failure: it is not
  quality-valid and publishes no quality scores.
- No seal, closure, verification or teardown time enters `end_to_end_latency_ms`.

## TC-02: M3 Retrieval Metrics V1

Only after TC-01 preflight and post-run PASS, score canonical
`(chunk_set_provenance_id, source_key, ordinal)` with locked Recall@8, uncut MRR, macro averaging,
valid misses in denominator and inapplicable/failure exclusions.

## TC-03: Citation correctness

TC-01 gates result validity. Public answer/citation/marker data is source of truth; trace validates
only exact-request alias evidence membership and never repairs or substitutes public data.

## TC-04: Semantic citation scoring

After TC-01, scorer receives only public answer and public citation excerpts/source locators;
hidden candidates, database IDs and trace internals remain excluded.

## TC-05: Independent durations

After TC-01, retain server `retrieval_latency_ms` and Q&A-only executor `end_to_end_latency_ms`
separately. Missing/invalid duration is observation failure; no aggregate latency statistic exists.

This guide is approved and locked. Any semantic change requires a new revision. Do not execute
manual acceptance until implementation verification completes; do not alter Evaluation history.
