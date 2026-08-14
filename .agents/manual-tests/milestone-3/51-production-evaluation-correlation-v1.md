# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Design decisions: https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261026759
- Guide revision: issue-51-v1
- Approval status: pending explicit human approval
- Approved by: —
- Approved at: —

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
  4. Inspect the runner surface for timestamp, question-text, or latest-trace lookup fallbacks.
- Expected results:
  - The evaluator has one production HTTP request/response path and uses its returned `trace_id`.
  - A missing trace, Workspace mismatch, or incomplete required provenance is an explicit
    evaluation execution/observation failure; it is never converted to zero Recall@k, MRR, or a
    retrieval miss.
  - No evaluation-only retrieval call or timestamp/question/latest-trace fallback exists.
- Evidence to capture:
  - Focused contract and integration test output.
  - Redacted response/trace correlation identifiers and the observation-failure record.

### TC-02: Retrieval metrics use ordered fused candidates only when applicable

- Purpose: Prove Recall@k and MRR use the correlated trace's ordered fused candidate sequence and
  that refusal cases remain outside the retrieval-relevance denominator.
- Steps:
  1. Evaluate answerable fixtures with known fused candidate order and multiple acceptable gold
     Chunk references.
  2. Evaluate an insufficient-evidence/refusal fixture whose dataset contract says retrieval
     relevance is not applicable.
  3. Compare calculated Recall@k, MRR, hit rate, denominator, and refusal correctness output.
- Expected results:
  - Metrics use only ordered fused trace candidates, never Evidence Set order or an independently
    retrieved list.
  - Metrics include only cases whose gold relevance semantics permit them.
  - Refusal correctness is reported separately and is not a zero-valued retrieval-quality result.
- Evidence to capture:
  - Focused metric tests and a worked expected-result example.
  - Report fragments showing the separate retrieval and refusal sections.

### TC-03: Deterministic public-citation checks preserve the correlated public contract

- Purpose: Prove deterministic citation evaluation checks the exact public answer, public
  citations, marker order, and Evidence Alias mapping from the correlated request.
- Steps:
  1. Run an answerable case with multiple public citations and markers.
  2. Verify citation aliases map to the correlated trace candidates and marker order equals public
     citation order.
  3. Exercise missing/duplicate/out-of-order markers, unknown aliases, and a citation to a
     non-evidence candidate.
- Expected results:
  - Deterministic checks accept only the public contract correlated to the Q&A response.
  - Structural errors are explicit failures and do not substitute hidden retrieval payloads for
    public citations.
- Evidence to capture:
  - Focused contract test output.
  - Redacted public answer/citation projection and structural finding examples.

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

### TC-05: Server retrieval and client end-to-end latency remain independent

- Purpose: Prove reports preserve server candidate-retrieval/evidence-selection latency separately
  from the executor's full HTTP request/response interval.
- Steps:
  1. Execute cases with distinguishable server retrieval and client-observed timings.
  2. Inspect raw observations, aggregate report metrics, and normalized-report comparison.
  3. Exercise a trace missing server latency and an HTTP/trace observation failure.
- Expected results:
  - `retrieval_latency_ms` comes only from the correlated server trace.
  - `end_to_end_latency_ms` is measured by the executor around the Q&A request/response.
  - Neither value is inferred from the other; missing required server timing becomes an explicit
    observation failure.
- Evidence to capture:
  - Focused timing/report tests and report excerpts.
  - Normalized comparison demonstrating that only declared wall-clock observations are excluded.

This draft is not approved or locked. Explicit human approval is required before implementation or
manual execution. After approval, this exact revision becomes immutable; semantic changes require
a new revision and run observations belong in a separate append-only JSONL Evaluation history.
