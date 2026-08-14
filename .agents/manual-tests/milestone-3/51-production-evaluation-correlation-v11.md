# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Guide revision: issue-51-v11
- Binding authority: `docs/design/m3-evaluation-environment-binding-v3.md`
- Lifecycle authority: `docs/design/m3-evaluation-bootstrap-lifecycle-v1.md` and
  `docs/design/m3-evaluation-sealed-environment-v1.md`
- Supersedes: unapproved `issue-51-v10`, unchanged
- Approval status: pending human approval

## Canonical lifecycle

```text
bootstrap → corpus-closure PASS → seal environment → inject startup auth
→ start production API → measured Q&A → post-run closure/provenance verification → teardown
```

1. Bootstrap provisions/reuses the isolated Workspace, materializes `m3-corpus-v1`, verifies
   Binding V3/corpus closure, and creates an ephemeral normal Workspace-scoped credential.
2. `EvaluationEnvironmentSeal.acquire` establishes exclusive run ownership after closure PASS. If
   it cannot seal, setup fails and Q&A never runs.
3. Launcher injects only hash-only startup auth configuration, starts normal `create_app()` and
   normal `ApiKeyAuthenticator`; the raw key remains ephemeral runtime input only.
4. During seal, corpus/retrieval-provenance mutation is prohibited: ingestion, reprocess, delete,
   activation, Document Version/Chunk Set rebinding, Binding replacement and resolved Retrieval
   Configuration change. Q&A and Question Trace persistence are allowed.
5. After Q&A, control plane verifies closure, V3 bindings and resolved configuration equal the
   preflight snapshot. Drift invalidates the whole run as quality evidence; then teardown releases
   seal, process and ephemeral credential.

Seal acquisition, post-run verification and teardown are outside per-request Q&A measurement and
must not contribute to `end_to_end_latency_ms`.

## TC-01: Sealed corpus closure and exact production correlation

1. Capture redacted bootstrap/closure PASS evidence and acquire an exclusive sealed-environment
   capability before startup-auth injection and production API start.
2. Verify seal rejects corpus/retrieval-provenance mutation while it permits Q&A/trace persistence.
3. Call production `POST /v1/questions`; read only its `(workspace_id, trace_id)` correlated trace.
   Verify response/trace identity, Workspace, resolved configuration, rank/order and each exact
   `(source_key, document_version_id, chunk_set_id)` against V3 before canonical projection.
4. Run every measured request inside the seal.
5. After the last request, verify active corpus closure, V3 bindings and resolved Retrieval
   Configuration exactly equal preflight, before publishing any quality report.
6. Exercise seal acquisition failure; each forbidden mutation; missing/extra/duplicate active
   source/version; V3/configuration drift; trace/binding/correlation mismatch; and malformed rank.

Expected results:

- Lack of exclusive seal blocks measured Q&A. Seal/post-run drift is an environment/observation
  failure; the entire run is not quality-valid and no quality scores publish.
- Valid Q&A/trace persistence remains possible under seal.
- No seal/preflight/post-run duration appears in `end_to_end_latency_ms`.

## TC-02: M3 Retrieval Metrics V1

Only after successful TC-01 preflight and post-run verification, use canonical
`(chunk_set_provenance_id, source_key, ordinal)`, Recall@8, uncut MRR, macro averaging, valid-miss
denominator membership and inapplicable/failure exclusions as locked in V10.

## TC-03: Citation correctness

TC-01 gates success. Public answer/citation/marker data remains source of truth; trace only validates
exact-request alias evidence membership and never repairs or substitutes public data.

## TC-04: Semantic citation scoring

After TC-01, scorer receives only public answer and public citation excerpts/source locators; it
never receives hidden retrieval content or trace internals.

## TC-05: Independent durations

After TC-01, report server `retrieval_latency_ms` and Q&A-only executor `end_to_end_latency_ms`
separately. Missing/invalid duration is observation failure; no aggregate latency metric exists.

This draft is unapproved. Do not execute manual acceptance or alter Evaluation history.
