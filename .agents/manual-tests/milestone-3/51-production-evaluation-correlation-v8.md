# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Authority: `m3-retrieval-metrics-v1`, M3 Evaluation Chunk Identity,
  `EvaluationEnvironmentBootstrap`, and `RetrievalConfigurationResolver` in `CONTEXT.md` and
  `docs/standards/architecture.md`
- Binding schema: `docs/design/m3-evaluation-environment-binding-v2.md`
- Guide revision: issue-51-v8
- Supersedes: locked `issue-51-v7`, which remains unchanged
- Approval status: pending human approval

## Prerequisites

- A prepared control-plane `EvaluationEnvironmentBootstrap` result for the isolated M3 Workspace,
  production Q&A endpoint, and runtime-only scoped credential. Bootstrap is outside measurement.
- Immutable V2 binding for `m3-dataset-v1`, `m3-corpus-v1`, `chunk-set-m3-v1`,
  `evaluation-m3-v1`, and `retrieval-m3-rrf-v1`, with exactly one source binding for each source
  in the immutable corpus manifest. Each binding entry records `source_key`, persisted production
  Document Version UUID, and persisted production Chunk Set UUID; raw credentials are redacted.

## TC-01: Per-source binding and exact correlated production trace

1. Bootstrap the Workspace, credential and manifest corpus through supported application/ingestion
   seams; inspect its V2 binding.
2. Verify coverage equals the manifest source-key set exactly, and bootstrap verified each source's
   active manifest-matching Document Version and corresponding persisted Chunk Set UUID.
3. Call production `POST /v1/questions`; use only its returned `(workspace_id, trace_id)` to read
   the correlated trace.
4. Verify trace Workspace and resolved configuration ID, ordered fused rank provenance, then for
   every candidate select the binding entry by candidate `source_key` and require exact Chunk Set
   UUID equality (and Document Version UUID equality when trace projection supplies it).
5. Project only a verified candidate to `(chunk-set-m3-v1, source_key, ordinal)`.
6. Exercise missing trace; Workspace/response-trace and configuration mismatch; missing/extra/
   duplicate binding source; unknown candidate source; wrong Chunk Set or Document Version UUID;
   malformed rank/order; duplicate/ambiguous canonical source+ordinal; incomplete binding and
   manifest-provenance mismatch.

Expected: every listed defect is setup/execution/observation or provenance/data-integrity failure
with no quality score. No current/latest/name fallback, unordered UUID-set membership, silent
dedupe, timestamp/question/latest-trace lookup or evaluation-only retrieval is permitted.

## TC-02: M3 Retrieval Metrics V1 uses provenance-scoped canonical references

1. Scope each gold `source_key#ordinal` from `m3-corpus-v1` with `chunk-set-m3-v1`.
2. Only after TC-01's per-source UUID/version gate, project candidates to the same tuple; never
   use database `chunk_id`, persisted Document Version UUID or persisted Chunk Set UUID as gold
   identity.
3. Verify report provenance records metric contract, `k=8`, corpus/dataset/provenance identities,
   complete V2 source bindings and resolved retrieval configuration.

| Case | Expected Recall@8 | Expected RR | Included |
| --- | ---: | ---: | --- |
| 3 gold; hits at ranks 2 and 4 | 2/3 | 1/2 | yes |
| relevant only at rank 9 | 0 | 1/9 | yes |
| valid no-hit retrieval | 0 | 0 | yes |
| fewer than 8 candidates; one hit rank 2 of 3 gold | 1/3 | 1/2 | yes |
| inapplicable refusal | no score | no score | no |
| any TC-01/observation failure | no score | no score | no |

Expected: Recall@8 uses at most eight candidates; RR searches the full ordered fused sequence;
aggregate Recall@8 and MRR are macro-means. Valid misses are zero-valued denominator members;
inapplicable and failures are excluded. No hit-rate requirement is introduced.

## TC-03: Citation correctness uses public data after TC-01

1. For a TC-01-successful answer, capture exact public answer, citations, markers and aliases.
2. Validate public marker/citation order and aliases; use correlated trace/evidence only to verify
   each public alias maps to evidence of that exact request.
3. Exercise missing, duplicate, out-of-order and unknown aliases, plus syntactically valid aliases
   mapping to nonexistent evidence or another request's evidence.
4. Exercise invalid trace/binding/correlation with otherwise plausible public citations.

Expected: public data remains source of truth; trace never repairs, infers, reorders, adds,
removes or substitutes it. Alias defects are `CITATION_STRUCTURAL_ERROR`; TC-01 failure has
precedence and cannot become successful citation evaluation.

## TC-04: Semantic citation scoring excludes hidden retrieval content

Run a recording scorer after TC-01 success with uncited correlated candidates. Expected: scorer
receives only public answer and public citation excerpts/source locators; no hidden candidate,
database ID or trace internal. Report scorer model and policy/prompt provenance.

## TC-05: Per-observation durations retain V2 provenance

Inspect successful observations with distinguishable server retrieval and executor end-to-end
durations, binding provenance and wall-clock metadata. Exercise missing/invalid retrieval duration
and binding/trace failure. Expected: both duration metrics remain separate, are never normalized
away, and missing/invalid duration is observation failure with no quality score. M3.2 defines no
aggregate latency statistic.

This draft is not approved or locked. Observations, if later authorized, append only to the existing
Evaluation history JSONL; no existing record may be edited.
