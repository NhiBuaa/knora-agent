# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Design decisions: https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261026759
- Metric authority: `m3-retrieval-metrics-v1` and M3 Evaluation Chunk Identity in `CONTEXT.md`
  and `docs/standards/architecture.md`
- Guide revision: issue-51-v5
- Supersedes: locked `issue-51-v4`, which remains unchanged
- Approval status: approved and locked
- Approved by: NhiBuaa
- Approved at: 2026-08-12 (Codex task approval)

## Prerequisites

- Environment: the dedicated Issue #51 worktree on branch
  `nhibuaa/issue-51-production-evaluation`, with PostgreSQL and the production Q&A endpoint
  available for integration acceptance.
- Data and state: the immutable `m3-dataset-v1` dataset and `m3-corpus-v1` manifest, loaded in
  their dedicated evaluation Workspace with the active corpus exactly matching its manifest.
- Credentials and permissions: a scoped, runtime-only API key for the evaluation Workspace. No
  production data, provider key, raw trace, or secret may be committed to evidence.

## Proposed Test Cases

### TC-01: The evaluator observes and projects the exact production Q&A trace

- Purpose: Prove every evaluation observation originates from one production `POST /v1/questions`
  response and the trace identified by that response's exact `(workspace_id, trace_id)` pair.
  Prove the run, corpus manifest, and correlated trace agree on one `chunk_set_id`.
- Steps:
  1. Run a representative answerable evaluation case through the production Q&A endpoint.
  2. Record the response Workspace and opaque `trace_id`, then have the evaluator read that exact
     trace using both values.
  3. Resolve each dataset gold `source_key#ordinal` only with the corpus manifest's pinned
     `chunk_set_id`, yielding `(chunk_set_id, source_key, ordinal)`.
  4. Project every ordered fused trace candidate directly to the same tuple from the correlated
     production trace's Chunk Set, Document source key, and ordinal.
  5. Verify the run provenance, corpus manifest, and trace have the same `chunk_set_id`; verify
     that within it each `(source_key, ordinal)` identifies exactly one logical Chunk.
  6. Exercise missing trace, foreign-Workspace trace, missing/incomplete provenance, missing or
     mismatched `chunk_set_id`, duplicate or ambiguous `(source_key, ordinal)`, and candidate
     ordering/rank-provenance failures.
  7. Exercise present-but-mismatched Retrieval Configuration and response-to-trace identity
     fixtures. Inspect the runner for timestamp, question-text, latest-trace, and evaluation-only
     retrieval fallbacks.
- Expected results:
  - The evaluator has one production HTTP request/response path and uses its returned `trace_id`.
  - The canonical M3 evaluation Chunk reference is the complete tuple
    `(chunk_set_id, source_key, ordinal)`. An unscoped `source_key#ordinal` is not globally
    canonical; it becomes a gold reference only after corpus-manifest scoping.
  - Deriving `(source_key, ordinal)` from the exactly correlated production trace is an identity
    projection, not an evaluation-only retrieval path.
  - Missing trace, Workspace mismatch, incomplete provenance, missing/mismatched `chunk_set_id`,
    duplicate/ambiguous Chunk identity, Retrieval Configuration mismatch, response-to-trace
    identity mismatch, and malformed/inconsistent candidate ordering/rank provenance are explicit
    execution/observation or provenance/data-integrity failures.
  - No such failure creates a Recall@8, MRR, or other retrieval-quality score. There is no fallback
    resolution or silent deduplication.
- Evidence to capture:
  - Focused contract and integration test output for every failure mode.
  - Redacted response/trace/corpus correlation identifiers, projected canonical references, and
    observation-failure records.

### TC-02: M3 Retrieval Metrics V1 calculates Recall@8 and uncut MRR from canonical evaluation references

- Purpose: Prove `m3-retrieval-metrics-v1` evaluates only successful, retrieval-applicable
  observations by equality of canonical M3 evaluation Chunk references from the corpus-scoped gold
  set and the ordered fused candidates of the correlated trace.
- Steps:
  1. Verify report provenance records `m3-retrieval-metrics-v1`, the pinned Recall cutoff `k = 8`,
     and the corpus `chunk_set_id`; comparable runs use the same values.
  2. For each successful `retrieval_relevance.applicable == true` case, resolve its non-empty gold
     set from manifest-scoped `source_key#ordinal` references to canonical tuples. Project trace
     candidates to canonical tuples directly and compare the tuples for equality. Do not resolve
     either side through database `chunk_id`.
  3. Calculate per-case `Recall@8` as `|gold ∩ top_8 ordered fused candidates| / |gold|`.
  4. Calculate per-case reciprocal rank as `1 / rank` of the first canonical gold reference in the
     entire ordered fused candidate sequence, or `0` when a valid observation has no relevant
     candidate. `MRR` is the arithmetic macro-mean of that uncut RR.
  5. Verify aggregate Recall@8 is the arithmetic macro-mean of included per-case Recall@8 values.
  6. Exercise the acceptance-oracle examples below, including candidate lists shorter than eight,
     a relevant candidate beyond rank 8, inapplicable refusal, and observation failure.
- Acceptance oracle:

  | Case | Gold canonical references | Ordered fused canonical references | Recall@8 | RR | Included |
  | --- | --- | --- | ---: | ---: | --- |
  | Multiple gold / partial recall | `{(S, a, 0), (S, b, 0), (S, c, 0)}` | `[(S, x, 0), (S, a, 0), (S, y, 0), (S, c, 0), (S, z, 0)]` | `2/3` | `1/2` | yes |
  | First relevant rank > 1 | `{(S, b, 0)}` | `[(S, x, 0), (S, y, 0), (S, b, 0), (S, z, 0)]` | `1` | `1/3` | yes |
  | Relevant only at rank 9 | `{(S, a, 0)}` | `[(S, x1, 0), (S, x2, 0), (S, x3, 0), (S, x4, 0), (S, x5, 0), (S, x6, 0), (S, x7, 0), (S, x8, 0), (S, a, 0)]` | `0` | `1/9` | yes |
  | Valid no-hit retrieval miss | `{(S, a, 0), (S, b, 0)}` | `[(S, x, 0), (S, y, 0), (S, z, 0)]` | `0` | `0` | yes |
  | Fewer-than-k candidates | `{(S, a, 0), (S, b, 0), (S, c, 0)}` | `[(S, x, 0), (S, a, 0), (S, y, 0)]` | `1/3` | `1/2` | yes; use all 3 for Recall@8; retain `|gold| = 3` |
  | Inapplicable refusal | not applicable | `[]` | no score | no score | no; report refusal correctness separately |
  | Observation failure | `{(S, a, 0)}` | unavailable because correlation/provenance failed | no score | no score | no; record failure |

- Expected results:
  - Gold matching uses only equality of full `(chunk_set_id, source_key, ordinal)` tuples. A
    database `chunk_id` is operational/persistence identity and never participates in portable gold
    matching.
  - `top_8` is the first eight ordered fused candidates; when fewer exist, it is the full available
    sequence while the Recall denominator remains the complete gold set. The `k=8` cutoff applies
    only to Recall@8, not RR/MRR.
  - Valid retrieval misses have zero Recall@8 and RR and remain in the retrieval-quality
    denominator. Only `retrieval_relevance.applicable == false` cases and execution/observation
    failures are excluded; neither is encoded as a zero retrieval score.
  - Reports expose per-case scores and inclusion/exclusion reason, aggregate macro-mean Recall@8,
    uncut aggregate MRR, the retrieval-quality denominator, metric contract, Recall `k`, and
    corpus `chunk_set_id`. Refusal correctness remains separate.
  - No hit-rate requirement is introduced by this slice.
- Evidence to capture:
  - Focused identity-projection, formula, ordered-rank, denominator, applicability, and
    observation-failure tests.
  - A report fragment with metric-contract provenance, Recall `k`, corpus `chunk_set_id`, per-case
    scores, denominator, and exclusion reasons.
  - Worked-result assertions matching every row of the acceptance oracle.

### TC-03: Deterministic citation correctness uses only public response data after TC-01 succeeds

- Purpose: Prove the public answer, public citations, and their Evidence Alias mapping are the
  source of truth for citation correctness, without weakening the trace-correlation gate.
- Steps:
  1. Run an answerable case whose response and trace pass TC-01, with multiple public citations
     and markers.
  2. Verify public citation aliases map in public-citation order and marker order matches that
     public order.
  3. Exercise missing, duplicate, and out-of-order markers; unknown aliases; and a public
     citation whose alias cannot map to evidence for the correlated request.
  4. Exercise missing or conflicting trace/provenance alongside otherwise plausible public
     citation data.
- Expected results:
  - TC-01 is a precedence gate: missing or conflicting trace/provenance makes the overall
    observation an execution/observation failure. It cannot become a successful evaluation result.
  - Once TC-01 succeeds, deterministic citation checks use only the exact public answer, public
    citation projections, marker order, and public Evidence Alias mapping returned for the request.
  - The correlated retrieval trace supports only correlation and provenance. It must not repair,
    infer, or substitute public citation data.
  - Invalid public citation data is an explicit structural failure, even when trace data could
    appear to supply a plausible replacement.
- Evidence to capture:
  - Focused correlation-precedence and citation-contract test output.
  - Redacted public answer/citation projection, alias mapping, and structural finding examples.

### TC-04: Semantic citation scoring receives no hidden retrieved content

- Purpose: Prove the semantic scorer receives only the public answer plus public citation excerpts
  and source locators, while trace data remains limited to correlation and provenance.
- Steps:
  1. Run a model-backed fixture with a recording scorer fake.
  2. Inspect its scorer request inputs and provenance output.
  3. Exercise a case with extra retrieved candidates that are not publicly cited.
- Expected results:
  - The scorer receives public answer, citation excerpts, and source locators only.
  - Hidden retrieved Chunk content, SQL/trace internals, and un-cited candidates never reach the
    scorer.
  - Scorer model and prompt/policy version are recorded as semantic provenance.
- Evidence to capture:
  - Recording-scorer contract test output.
  - Sanitized scorer request projection and report provenance.

### TC-05: Server retrieval and executor end-to-end latency remain independent per-observation durations

- Purpose: Prove each successful observation preserves server candidate-retrieval/evidence-
  selection duration separately from the executor's full Q&A HTTP request/response duration.
- Steps:
  1. Execute cases with distinguishable server retrieval and executor-observed end-to-end durations.
  2. Inspect each successful observation's two duration values and their source/provenance.
  3. Exercise a trace with missing or invalid server retrieval duration and an HTTP/trace
     observation failure.
  4. Inspect report metadata separately from duration metrics, including wall-clock timestamps
     used to identify a run or record an event.
- Expected results:
  - `retrieval_latency_ms` is the correlated server candidate-retrieval/evidence-selection
    duration. `end_to_end_latency_ms` is measured by the executor around the Q&A request/response.
  - Both duration values remain in each successful observation and report projection; neither is
    inferred from, replaced by, or discarded because of the other.
  - Missing or invalid required server duration is an explicit observation failure and creates no
    retrieval-quality score.
  - Wall-clock metadata/timestamps are distinct from duration metrics. Any reproducibility process
    may handle wall-clock metadata separately, but it must not use normalization to remove these
    duration observations.
  - M3.2 defines no aggregate latency statistic. Aggregation is outside this guide until a
    separately approved metric contract supplies its formula.
- Evidence to capture:
  - Focused per-observation timing/provenance tests with distinguishable expected durations.
  - Report projections showing both durations and separately identified wall-clock metadata.
  - Observation-failure result for missing or invalid retrieval duration.

This approved guide is locked. Any semantic change requires a new guide revision; run observations
belong in a separate append-only JSONL Evaluation history.
