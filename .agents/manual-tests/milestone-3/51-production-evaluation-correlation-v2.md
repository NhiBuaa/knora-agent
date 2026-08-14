# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Design decisions: https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261026759
- Guide revision: issue-51-v2
- Supersedes: unapproved draft `issue-51-v1`, which remains unchanged
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
  - No such failure creates a Recall@k, MRR, or other retrieval-quality score.
  - No evaluation-only retrieval call or timestamp/question/latest-trace fallback exists.
- Evidence to capture:
  - Focused contract and integration test output for every failure mode.
  - Redacted response/trace correlation identifiers and the observation-failure records.

### TC-02: Metric-contract authority is resolved before Recall@k and MRR implementation

- Purpose: Lock the full metric contract before implementing or accepting Recall@k and MRR from
  the ordered fused trace candidates.
- Steps:
  1. Trace each proposed metric rule to Issue #51, the Issue #48 decision record, `CONTEXT.md`,
     and the Architecture Standard: the reported `k`; the multiple-relevant-chunk Recall@k
     formula; the MRR first-relevant-rank formula; per-case report fields; aggregate formula; and
     quality denominator.
  2. Verify that every eligible case has `retrieval_relevance.applicable == true`, and that a
     refusal case with `retrieval_relevance.applicable == false` is excluded from retrieval metric
     calculation and reported separately as refusal correctness.
  3. Verify the resolved contract explicitly excludes every evaluation execution/observation
     failure from every retrieval-quality denominator and produces no quality score for it.
  4. If any rule in steps 1–3 lacks an authoritative definition, stop at authority resolution;
     record the unresolved decision and do not implement or invent metric semantics.
- Expected results:
  - The accepted contract names the reported `k`, defines Recall@k for multiple acceptable
    relevant Chunks, defines MRR from the first relevant rank within the ordered fused candidates,
    and specifies the per-case and aggregate report fields and denominator.
  - Only `retrieval_relevance.applicable == true` cases with successful observations contribute to
    retrieval-quality metrics. Inapplicable refusal cases and observation/execution failures are
    excluded, never represented as zero scores.
  - Refusal correctness remains a separate result.
  - No hit-rate requirement is introduced by this slice unless a later approved authority adds it.
  - If authority is incomplete, the outcome is a documented design/authority-resolution blocker,
    not an implementation choice.
- Evidence to capture:
  - Requirement-to-authority matrix for each metric rule.
  - The approved metric-contract decision, or the explicit unresolved-decision record.
  - After authority approval only: focused formula, denominator, applicability, and
    observation-failure tests with worked expected results.

### TC-03: Deterministic citation correctness uses only public response data

- Purpose: Prove the public answer, public citations, and their Evidence Alias mapping are the
  source of truth for citation correctness.
- Steps:
  1. Run an answerable case with multiple public citations and markers.
  2. Verify public citation aliases map in public-citation order and marker order matches that
     public order.
  3. Exercise missing, duplicate, and out-of-order markers; unknown aliases; and a public
     citation whose alias cannot map to evidence for the correlated request.
  4. Exercise a correlated trace containing extra, missing, or conflicting candidate data.
- Expected results:
  - Deterministic citation checks use only the exact public answer, public citation projections,
    marker order, and public Evidence Alias mapping returned for the request.
  - The correlated retrieval trace supports only correlation and provenance. It must not repair,
    infer, or substitute public citation data.
  - Invalid public citation data is an explicit structural failure, even when trace data could
    appear to supply a plausible replacement.
- Evidence to capture:
  - Focused contract test output.
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

### TC-05: Server retrieval and executor end-to-end latency remain independent duration metrics

- Purpose: Prove reports preserve server candidate-retrieval/evidence-selection duration separately
  from the executor's full Q&A HTTP request/response duration.
- Steps:
  1. Execute cases with distinguishable server retrieval and executor-observed end-to-end
     durations.
  2. Inspect the raw observations and aggregate report metrics for both durations.
  3. Exercise a trace with missing or invalid server retrieval duration and an HTTP/trace
     observation failure.
  4. Inspect report metadata separately from duration metrics, including any wall-clock timestamps
     used to identify a run or record an event.
- Expected results:
  - `retrieval_latency_ms` is the correlated server candidate-retrieval/evidence-selection
    duration. `end_to_end_latency_ms` is measured by the executor around the Q&A request/response.
  - Both duration metrics remain in observations and reports; neither is inferred from, replaced
    by, or discarded because of the other.
  - Missing or invalid required server duration is an explicit observation failure and creates no
    retrieval-quality score.
  - Wall-clock metadata/timestamps are distinct from duration metrics. Any reproducibility process
    may handle wall-clock metadata separately, but it must not use normalization to remove these
    duration observations.
- Evidence to capture:
  - Focused timing and report tests with distinguishable expected durations.
  - Report excerpts showing both duration metrics and separately identified wall-clock metadata.
  - Observation-failure result for missing or invalid retrieval duration.

This draft is not approved or locked. Explicit human approval is required before implementation or
manual execution. After approval, this exact revision becomes immutable; semantic changes require
a new revision and run observations belong in a separate append-only JSONL Evaluation history.
