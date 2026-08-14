# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Design decisions: https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261026759
- Metric authority: `m3-retrieval-metrics-v1` in `CONTEXT.md` and
  `docs/standards/architecture.md`
- Guide revision: issue-51-v4
- Supersedes: unapproved draft `issue-51-v3`, which remains unchanged
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

### TC-01: The evaluator observes the exact production Q&A trace only

- Purpose: Prove every evaluation observation originates from one production `POST /v1/questions`
  response and the trace identified by that response's exact `(workspace_id, trace_id)` pair.
- Steps:
  1. Run a representative answerable evaluation case through the production Q&A endpoint.
  2. Record the response Workspace and opaque `trace_id`, then have the evaluator read that exact
     trace using both values.
  3. Exercise missing trace, foreign-Workspace trace, and trace/provenance-incomplete fixtures.
  4. Exercise present-but-mismatched fixtures: a Retrieval Configuration that conflicts with the
     run's required provenance; a trace whose identity does not match the response correlation;
     and candidates with malformed or inconsistent ordered fused rank provenance.
  5. Inspect the runner surface for timestamp, question-text, latest-trace, and evaluation-only
     retrieval fallbacks.
- Expected results:
  - The evaluator has one production HTTP request/response path and uses its returned `trace_id`.
  - Missing trace, Workspace mismatch, incomplete required provenance, Retrieval Configuration
    mismatch, response-to-trace identity mismatch, and malformed or inconsistent candidate
    ordering/rank provenance are explicit evaluation execution/observation failures.
  - No such failure creates a Recall@8, MRR, or other retrieval-quality score.
  - No evaluation-only retrieval call or timestamp/question/latest-trace fallback exists.
- Evidence to capture:
  - Focused contract and integration test output for every failure mode.
  - Redacted response/trace correlation identifiers and the observation-failure records.

### TC-02: M3 Retrieval Metrics V1 calculates Recall@8 and uncut MRR from ordered fused candidates

- Purpose: Prove `m3-retrieval-metrics-v1` evaluates only successful, retrieval-applicable
  observations against canonical stable Chunk identities in the correlated trace's ordered fused
  candidates.
- Steps:
  1. Verify report provenance records metric-contract identity `m3-retrieval-metrics-v1` and its
     pinned Recall cutoff `k = 8`, and comparable runs use the same values.
  2. For each successful `retrieval_relevance.applicable == true` case, verify its gold-relevant
     canonical Chunk identity set is non-empty and calculate per-case `Recall@8` as
     `|gold ∩ top_8 ordered fused candidates| / |gold|`.
  3. Calculate per-case reciprocal rank as `1 / rank` of the first gold-relevant canonical Chunk
     in the entire ordered fused candidate sequence, or `0` when a valid observation has no
     relevant candidate. `MRR` is the arithmetic macro-mean of that uncut RR.
  4. Verify aggregate Recall@8 is the arithmetic macro-mean of included per-case Recall@8 values.
  5. Exercise the acceptance-oracle examples below, including candidate lists shorter than eight,
     a relevant candidate beyond rank 8, inapplicable refusal, and observation failure.
- Acceptance oracle:

  | Case | Gold canonical Chunk identities | Ordered fused candidates | Per-case Recall@8 | RR | Included in quality denominator |
  | --- | --- | --- | ---: | ---: | --- |
  | Multiple gold / partial recall | `{A, B, C}` | `[X, A, Y, C, Z]` | `2/3` | `1/2` | yes |
  | First relevant rank > 1 | `{B}` | `[X, Y, B, Z]` | `1` | `1/3` | yes |
  | Relevant only at rank 9 | `{A}` | `[X1, X2, X3, X4, X5, X6, X7, X8, A]` | `0` | `1/9` | yes |
  | Valid no-hit retrieval miss | `{A, B}` | `[X, Y, Z]` | `0` | `0` | yes |
  | Fewer-than-k candidates | `{A, B, C}` | `[X, A, Y]` | `1/3` | `1/2` | yes; use all 3 for Recall@8, retain `|gold| = 3` |
  | Inapplicable refusal | not applicable | `[]` | no score | no score | no; report refusal correctness separately |
  | Observation failure | `{A}` | unavailable because correlation/provenance failed | no score | no score | no; record execution/observation failure |

- Expected results:
  - Matching uses canonical stable Chunk identity, not Evidence Set position, source key/ordinal
    shorthand, alias, or a mutable database row identity.
  - `top_8` is the first eight ordered fused candidates; when fewer exist, it is the full available
    sequence while the Recall denominator remains the complete gold set. The `k=8` cutoff applies
    only to Recall@8, not RR/MRR.
  - Valid retrieval misses have zero Recall@8 and RR and remain in the retrieval-quality
    denominator. Only `retrieval_relevance.applicable == false` cases and execution/observation
    failures are excluded; neither is encoded as a zero retrieval score.
  - Reports expose per-case scores and inclusion/exclusion reason, aggregate macro-mean Recall@8,
    uncut aggregate MRR, and the retrieval-quality denominator. Refusal correctness remains
    separate.
  - No hit-rate requirement is introduced by this slice.
- Evidence to capture:
  - Focused formula, ordered-rank, denominator, applicability, and observation-failure tests.
  - A report fragment with metric-contract provenance, Recall `k`, per-case scores, denominator,
    and exclusion reasons.
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
  1. Execute cases with distinguishable server retrieval and executor-observed end-to-end
     durations.
  2. Inspect each successful observation's two duration values and their source/provenance.
  3. Exercise a trace with missing or invalid server retrieval duration and an HTTP/trace
     observation failure.
  4. Inspect report metadata separately from duration metrics, including any wall-clock timestamps
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
