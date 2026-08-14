# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Design decisions: https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261026759
- Metric and environment authority: `m3-retrieval-metrics-v1`, M3 Evaluation Chunk Identity,
  `EvaluationEnvironmentBootstrap`, and `RetrievalConfigurationResolver` in `CONTEXT.md` and
  `docs/standards/architecture.md`
- Binding schema: `docs/design/m3-evaluation-environment-binding-v1.md`
- Guide revision: issue-51-v7
- Supersedes: unapproved draft `issue-51-v6`, which remains unchanged
- Approval status: approved and locked
- Approved by: NhiBuaa
- Approved at: 2026-08-12 (Codex task approval)

## Prerequisites

- Environment: a prepared `EvaluationEnvironmentBootstrap` result for the dedicated M3
  evaluation Workspace and production Q&A endpoint. Bootstrap is control-plane only and is outside
  the measured Q&A path.
- Binding artifact: a verified immutable binding that records `m3-dataset-v1`, `m3-corpus-v1`,
  `chunk-set-m3-v1`, the exact production Chunk Set UUID, Workspace ID, and
  `retrieval-m3-rrf-v1`.
- Data and state: the active corpus and chunking provenance match `m3-corpus-v1`; the binding was
  verified through supported application/ingestion behavior, not inferred from current/latest/name
  lookups. `m3-corpus-v1` remains unchanged.
- Credentials and permissions: a runtime-only scoped API credential produced by bootstrap under
  production credential invariants. Do not commit, log, or include its raw value in evidence.

## Proposed Test Cases

### TC-01: Bootstrap binding and exact production Q&A trace are verified

- Purpose: Prove a canonical control-plane setup binds the immutable M3 corpus provenance to one
  isolated production Workspace before a production Q&A response is correlated to its trace.
- Steps:
  1. Invoke `EvaluationEnvironmentBootstrap` to provision/reuse the Workspace, scoped runtime
     credential, and manifest-bound corpus; retain its verified binding artifact.
  2. Inspect the binding for dataset/corpus manifest identities, `chunk-set-m3-v1`, Workspace ID,
     exact persisted production Chunk Set UUID, and `retrieval-m3-rrf-v1`.
  3. Call production `POST /v1/questions` with the scoped credential. Read only the returned
     `(workspace_id, trace_id)` pair.
  4. Verify the trace Workspace, resolved Retrieval Configuration ID, and every correlated
     candidate's persisted Chunk Set UUID against the binding. Verify ordered fused rank provenance
     and unique `(source_key, ordinal)` inside the bound persisted Chunk Set.
  5. Project a verified candidate to `(chunk_set_provenance_id, source_key, ordinal)`. This is an
     identity projection from the correlated production trace, not an evaluation-only retrieval.
  6. Exercise missing trace, Workspace/response-trace mismatch, missing or mismatched bound UUID,
     duplicate/ambiguous `(source_key, ordinal)`, malformed rank/order, Retrieval Configuration
     mismatch, and incomplete binding/provenance fixtures.
- Expected results:
  - The evaluator uses only the Q&A response trace ID; no timestamp/question/latest-trace or
    evaluation-only retrieval fallback exists.
  - A manifest `chunk_set_provenance_id` and a production Chunk Set UUID are distinct identities.
    The binding is explicit and verified; the UUID never needs to equal `chunk-set-m3-v1`.
  - Every listed mismatch is an execution/observation or provenance/data-integrity failure with no
    retrieval-quality score and no silent fallback/deduplication.
- Evidence to capture:
  - Redacted binding artifact and bootstrap result.
  - Production response/trace correlation and UUID-binding verification.
  - Focused negative-contract output for every failure mode.

### TC-02: M3 Retrieval Metrics V1 uses provenance-scoped canonical references

- Purpose: Prove `m3-retrieval-metrics-v1` matches manifest gold and correlated trace candidates
  only as `(chunk_set_provenance_id, source_key, ordinal)` after TC-01 verifies the persisted UUID
  binding.
- Steps:
  1. Resolve each gold `source_key#ordinal` from `m3-corpus-v1` by adding the manifest's
     `chunk-set-m3-v1`; do not treat the unscoped shorthand as globally canonical.
  2. After UUID binding verification, project ordered fused candidates to the same provenance-
     scoped tuple. Do not use database `chunk_id` for matching.
  3. Verify report provenance records `m3-retrieval-metrics-v1`, Recall `k = 8`, corpus manifest
     identity, chunk-set provenance identity, production Chunk Set UUID binding, and resolved
     Retrieval Configuration ID.
  4. Apply the unchanged v5 Recall@8, uncut RR/MRR, macro-average and denominator contract.
  5. Exercise the oracle below.
- Acceptance oracle:

  | Case | Gold / ordered candidate references | Recall@8 | RR | Included |
  | --- | --- | ---: | ---: | --- |
  | Multiple gold / partial recall | `{(P,a,0),(P,b,0),(P,c,0)}` / `[(P,x,0),(P,a,0),(P,y,0),(P,c,0)]` | `2/3` | `1/2` | yes |
  | Relevant only at rank 9 | `{(P,a,0)}` / first `a` at rank 9 | `0` | `1/9` | yes |
  | Valid no-hit retrieval miss | `{(P,a,0),(P,b,0)}` / no gold candidate | `0` | `0` | yes |
  | Fewer-than-k candidates | three gold; three candidates with one hit at rank 2 | `1/3` | `1/2` | yes |
  | Inapplicable refusal | not applicable | no score | no score | no; refusal correctness separate |
  | Observation failure | binding/correlation unavailable | no score | no score | no; record failure |

- Expected results:
  - `P` is the bound `chunk_set_provenance_id`, never a production UUID. Database `chunk_id` is
    operational identity and cannot participate in portable gold matching.
  - `top_8` limits Recall@8 only. RR searches the entire ordered fused candidate sequence; MRR and
    aggregate Recall@8 remain macro-means of included cases.
  - Valid misses remain zero-valued denominator members. Inapplicable cases and every observation
    failure are excluded, never encoded as zero scores.
  - No hit-rate requirement is introduced.
- Evidence to capture:
  - Binding-aware metric test output and worked oracle assertions.
  - Report fragment with the required binding and metric provenance fields.

### TC-03: Citation correctness uses public data and validates alias evidence after TC-01 succeeds

- Purpose: Prove the public answer, public citation projections, and markers are the source of
  truth for citation correctness, while correlated trace/evidence provenance is used only to
  validate that each public Evidence Alias identifies evidence from that exact correlated request.
- Steps:
  1. Run an answerable case whose binding and trace pass TC-01. Capture its exact public answer,
     public citations, markers, Evidence Alias mapping, and correlated evidence provenance.
  2. Verify public marker order equals public citation order, each public citation has one valid
     alias, and every alias maps to evidence belonging to the exact correlated request.
  3. Exercise missing, duplicate, out-of-order, and unknown public aliases.
  4. Exercise a syntactically valid public alias that maps to no correlated evidence, to evidence
     that does not exist, and to evidence belonging to a different request.
  5. Exercise missing or conflicting trace/binding/correlation provenance alongside otherwise
     plausible public citation data.
- Expected results:
  - TC-01 is a precedence gate: invalid trace, binding, or correlation makes the overall result an
    execution/observation failure. Citation evaluation cannot become successful.
  - After TC-01 succeeds, public answer, public citation projections, and markers remain the
    source of truth. The trace may validate alias-to-correlated-evidence membership only; it must
    not repair, infer, reorder, add, remove, or substitute public citation data.
  - An alias that is syntactically valid but lacks correlated evidence, names nonexistent evidence,
    or resolves to another request's evidence is a `CITATION_STRUCTURAL_ERROR`.
- Evidence to capture:
  - Redacted public response/citation/marker projection and correlated alias-evidence membership
    result.
  - Focused tests for each alias failure and TC-01 precedence case.
  - Structural finding artifacts for rejected alias cases.

### TC-04: Semantic citation scoring receives no hidden retrieved content

- Purpose: Prove semantic scoring receives only public answer and public citation excerpts/source
  locators after TC-01 succeeds.
- Steps:
  1. Run a model-backed configured environment with a recording scorer fake.
  2. Inspect scorer input and provenance with extra correlated candidates that are not cited.
- Expected results:
  - Hidden candidates, database IDs, trace internals, and un-cited content never reach the scorer.
  - Scorer model and prompt/policy version are reported as semantic provenance.
- Evidence to capture:
  - Recording-scorer input projection and semantic provenance output.

### TC-05: Independent per-observation duration values retain binding provenance

- Purpose: Prove each successful observation keeps server retrieval duration and executor
  end-to-end duration separately, alongside verified binding provenance.
- Steps:
  1. Execute distinguishable production retrieval and executor durations after TC-01 passes.
  2. Inspect each observation's two duration values, binding provenance, and wall-clock metadata.
  3. Exercise missing/invalid server retrieval duration and binding/trace failure.
- Expected results:
  - `retrieval_latency_ms` is correlated server candidate-retrieval/evidence-selection duration;
    `end_to_end_latency_ms` is the executor's Q&A interval. Neither is derived from the other.
  - Missing/invalid duration or binding/trace failure is an observation failure with no quality
    score. Duration values are not removed by normalization.
  - M3.2 defines no aggregate latency statistic.
- Evidence to capture:
  - Per-observation duration/binding report projection and negative-case output.

This approved guide is locked. Any semantic change requires a new guide revision; run observations
belong in a separate append-only JSONL Evaluation history.
