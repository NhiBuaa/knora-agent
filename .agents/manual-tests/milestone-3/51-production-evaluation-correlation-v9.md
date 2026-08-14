# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Metric authority: `m3-retrieval-metrics-v1`
- Binding authority: `docs/design/m3-evaluation-environment-binding-v3.md`
- Guide revision: issue-51-v9
- Supersedes: unapproved `issue-51-v8`, which remains unchanged
- Approval status: approved and locked

## Prerequisites

- A control-plane `EvaluationEnvironmentBootstrap` result for the dedicated M3 evaluation
  Workspace, production Q&A endpoint and runtime-only scoped credential. Bootstrap is not part of
  measured Q&A and never exposes a public acceptance-only administrative endpoint.
- An immutable V3 binding for `m3-dataset-v1`, `m3-corpus-v1`, `chunk-set-m3-v1`,
  `evaluation-m3-v1`, and `retrieval-m3-rrf-v1`. Its `source_bindings` contains exactly one entry
  per corpus-manifest `source_key`; each entry contains `source_key`, persisted
  `production_document_version_id` and persisted `production_chunk_set_id`.
- A PASS corpus-closure preflight, completed before Q&A execution through supported production/
  application seams. It proves the complete retrieval-eligible active corpus source-key set equals
  `m3-corpus-v1` exactly; every manifest source has exactly one active manifest-matching Document
  Version and exactly one corresponding persisted Chunk Set; no extra active source/document,
  missing source, duplicate source binding or multiple-active source/version exists.
- The trace/evaluation reader projects candidate `source_key`, `document_version_id`,
  `chunk_set_id`, ordinal and ordered rank provenance. If the raw trace does not expose version,
  the reader must already have established an equivalent mandatory verified
  source → Document Version → Chunk Set relation; version checking may not be skipped.
- `m3-corpus-v1` is immutable. Credentials remain runtime-only and redacted from artifacts.

## TC-01: Corpus closure, per-source binding, and exact correlated trace

1. Invoke `EvaluationEnvironmentBootstrap` via supported control-plane/application seams. Retain
   its redacted V3 binding and corpus-closure preflight evidence before calling Q&A.
2. Verify binding coverage is exactly the manifest source-key set. Verify closure enumerated the
   complete retrieval-eligible active corpus, found no extra active source/document, and proved
   exactly one active manifest-matching Document Version plus its persisted Chunk Set for each
   manifest source.
3. Call production `POST /v1/questions` with the scoped credential. Use only returned
   `(workspace_id, trace_id)` to read the exactly correlated trace.
4. Verify response↔trace identity, Workspace, resolved Retrieval Configuration ID and fused
   candidate ordering/rank provenance. For each candidate, select its binding entry by
   `source_key`, then require exact equality of the mandatory triple `(source_key,
   document_version_id, chunk_set_id)` and the binding entry.
5. Only after the triple gate passes, project each candidate to
   `(chunk-set-m3-v1, source_key, ordinal)`; this is trace identity projection, not retrieval.
6. Exercise: corpus closure missing/extra active source/document; duplicate/multiple active source
   or active version; missing/extra/duplicate binding source; missing trace; Workspace or
   response↔trace mismatch; Retrieval Configuration mismatch; unknown candidate source; absent,
   wrong or mismatched Document Version UUID; wrong Chunk Set UUID; incomplete provenance relation;
   malformed rank/order; duplicate/ambiguous canonical reference; and manifest mismatch.

Expected results:

- Corpus-closure defects stop execution before measured Q&A. Trace/binding/correlation defects are
  setup/execution/observation or provenance/data-integrity failures with no quality score.
- No current/latest/name inference, unordered UUID-set membership, silent dedupe,
  timestamp/question/latest-trace lookup, evaluation-only retrieval path or version-check bypass is
  permitted.
- Persisted Document Version and Chunk Set UUIDs are mandatory environment-provenance gates only;
  portable gold matching uses neither.

## TC-02: M3 Retrieval Metrics V1 uses canonical references

After TC-01, scope gold `source_key#ordinal` with `chunk-set-m3-v1` and compare only that canonical
tuple to candidates. Confirm report provenance includes V3 binding plus `m3-retrieval-metrics-v1`
and Recall `k=8`. Validate: 3 gold/hits ranks 2 and 4 gives Recall@8 `2/3`, RR `1/2`; rank-9-only
hit gives `0`, `1/9`; valid miss gives `0`, `0`; fewer-than-8 candidates with one rank-2 hit of
three gold gives `1/3`, `1/2`; inapplicable and observation failure have no score and are excluded.
Recall and MRR aggregate as macro-means; valid misses remain in the denominator.

## TC-03: Citation correctness uses public data after TC-01

Public answer/citations/markers remain source of truth. After TC-01, correlated trace may only
verify public alias membership in evidence from the exact request, never repair/infer/substitute
public data. Invalid aliases are `CITATION_STRUCTURAL_ERROR`; TC-01 failure prevents success.

## TC-04: Semantic citation scoring excludes hidden retrieval content

After TC-01, recording scorer input contains only public answer and public citation excerpts/source
locators, never hidden candidates, database IDs or trace internals. Record scorer provenance.

## TC-05: Per-observation durations retain V3 provenance

After TC-01, retain independent `retrieval_latency_ms` and executor `end_to_end_latency_ms` plus V3
binding and wall-clock metadata. Missing/invalid retrieval duration is observation failure with no
quality score. No aggregate latency statistic is defined.

This guide is approved and locked. Any semantic change requires a new revision. Do not alter the
append-only Evaluation history; execute manual acceptance only after implementation verification.
