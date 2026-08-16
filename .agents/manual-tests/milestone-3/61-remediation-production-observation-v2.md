# Manual Test Guide: M3 remediation — production trace and public observation contract

- Slice: GitHub Issue #61, child remediation of Issue #48
- Guide revision: `m3-remediation-61-v2`
- Supersedes: `m3-remediation-61-v1` (v1 is immutable; this revision is draft and unlocked)
- Source authority: Issue #48, Issue #61, `.agents/review/m3-fixed-point-review-v1.json`,
  `.agents/review/m3-standards-axis-v1.json`, `.agents/review/m3-spec-axis-v1.json`
- Worktree: `D:/Developer/Projects/knora-agent-worktree/issue-61-m3-remediation-trace`
- Source base: `511023428202e77e2e981dc8f25ab191cb3c86ab`
- Evaluation history: `.agents/manual-tests/milestone-3/61-remediation-production-observation.evaluations.jsonl`
- Lock status: `DRAFT` — do not implement or execute from this guide until it is approved and locked.

## Preconditions

- PostgreSQL/pgvector and the production-shaped Q&A endpoint are running from the issue-61
  worktree.
- The M3 Workspace has active vector and hybrid configurations and a corpus containing a lexical
  match, a semantic match, an excluded candidate, an empty-lexeme query and a refusal case.
- The evaluator can read the exact `(workspace_id, trace_id)` pair returned by the production Q&A
  response and the resulting evaluation observation through the evaluation seam.
- No raw provider secret or SQL implementation detail is included in trace/report evidence.

## Test cases

### TC-61-01 — Branch observations remain separate from fused candidates

1. Run a query that exercises these branch outcomes across canonical Chunks:
   - vector `ELIGIBLE` and FTS `ELIGIBLE`;
   - vector `BELOW_THRESHOLD` and FTS `ELIGIBLE` for the same Chunk;
   - vector `ELIGIBLE` with no FTS contribution; and
   - FTS `INELIGIBLE` with no vector contribution.
2. Read the correlated trace.

Expected:

- Vector and FTS branch observations contain their closed statuses and nullable contributions.
- `ELIGIBLE` contributions receive fused rank and fusion score.
- A vector `BELOW_THRESHOLD` / FTS `ELIGIBLE` Chunk is retained as an FTS-only fused candidate;
  it has no vector contribution.
- `INELIGIBLE` or no-contribution branch observations are retained as observations but are not
  fabricated as fused candidates. Pre-fusion losses never receive `final_rank` or `fusion_score`.
- This case owns candidate-level branch status and fusion coverage. The lexical empty-lexeme
  no-contribution path is covered by TC-61-05.

Evidence: trace JSON, one observation for each exercised branch status, nullable contribution
assertions, fused ordering and canonical Chunk identity assertions.

### TC-61-02 — Required trace provenance and correlation fail closed

1. Read a valid trace correlated by the exact `(workspace_id, trace_id)` pair returned by the Q&A
   response. Include retrieval configuration, fusion-policy, embedding-set, chunk-set and lexical
   provenance.
2. Repeat with each required provenance field removed or malformed.
3. Repeat when the trace is missing for the response's `trace_id`.
4. Repeat with a response-to-trace identity mismatch, including a different `trace_id` or a trace
   returned for a different response.
5. Repeat with a Workspace mismatch or a trace that the requesting principal is not authorized to
   read.

Expected:

- The valid trace is accepted.
- Every malformed, missing, mismatched or unauthorized observation is an explicit evaluation
  observation failure.
- The reader uses no fallback by timestamp, question text, recency or latest trace.
- Failed observations receive no retrieval-quality score and no fabricated latency value.

Evidence: reader result/error taxonomy, exact response/trace identity pair, Workspace and
authorization checks, provenance field projection, and proof that no score or latency was emitted
for each failed observation.

### TC-61-03 — Public ANSWER/REFUSAL validation and selected citations

1. Produce a valid `ANSWER` citing a candidate selected into the Evidence Set.
2. Produce a response whose alias maps to a fused candidate excluded by overlap, chunk count or
   token budget.
3. Produce negative `ANSWER` responses with one defect at a time: missing or empty `answer`,
   missing/unknown/duplicate/out-of-order markers, marker-to-citation mismatch, a decision other
   than `ANSWER` (including an unknown value), or a non-null/invalid `refusal_reason`.
4. Produce a valid `REFUSAL` response with `answer: null`, no markers, empty citations,
   `decision: REFUSAL`, and `refusal_reason: INSUFFICIENT_EVIDENCE`.
5. Produce negative `REFUSAL` responses with one defect at a time: non-null `answer`, any marker
   or citation, `decision: ANSWER` or an unknown decision, or a missing/incorrect refusal reason.
6. Send the valid refusal and an invalid refusal through the production evaluation seam. Inspect
   the resulting evaluation observation/report input for retained `decision`, `refusal_reason`
   and refusal-correctness data.

Expected:

- `ANSWER` validation requires a non-empty answer, unique Evidence Alias markers in first-
  appearance order, citations that exactly match those markers, `decision: ANSWER`, and a null or
  absent `refusal_reason`.
- Every cited alias maps one-to-one to a candidate selected into the Evidence Set. A citation to
  an excluded fused candidate fails closed.
- `REFUSAL` validation requires `answer: null`, no markers, empty citations,
  `decision: REFUSAL`, and `refusal_reason: INSUFFICIENT_EVIDENCE`.
- Every malformed or contradictory public response fails closed as an observation/contract
  failure. It is not repaired or converted into a valid Refusal.
- The evaluation seam retains refusal `decision`, `refusal_reason` and refusal-correctness data;
  invalid observations do not receive a quality score.

Evidence: public response JSON, correlated trace, selected Evidence Set membership, deterministic
validation result, negative-case error taxonomy, and evaluation observation/report projection
showing retained refusal-correctness data.

### TC-61-04 — Retrieval latency clock boundary

1. Instrument four separate phases with distinct timing markers: query embedding, candidate
   retrieval, Evidence Selection, and generation.
2. Execute the production Q&A request and capture the trace `retrieval_latency_ms` plus the client
   end-to-end request/response duration.

Expected:

- `retrieval_latency_ms` starts with candidate retrieval and ends after Evidence Selection. It
  includes candidate retrieval and Evidence Selection, and excludes both query embedding and
  generation.
- `end_to_end_latency_ms` covers the complete client-observed Q&A interval, including query
  embedding, candidate retrieval, Evidence Selection and generation.
- The two metrics are independent; neither is calculated from the other.
- Instrumented phase timestamps and arithmetic boundary checks demonstrate the stated inclusion
  and exclusion, within the timer's documented precision.

Evidence: phase timing markers, trace latency, executor duration, phase-total arithmetic and the
documented clock-boundary assertion.

### TC-61-05 — Lexical policy provenance and empty-lexeme behavior

1. Run a query whose lexical normalization produces both retained and omitted lexemes.
2. Run a query whose normalization produces no eligible lexemes.
3. Read the lexical branch observation in each correlated trace.

Expected:

- Each trace records the versioned lexical policy, normalized lexemes, omitted lexemes and the
  FTS eligibility result.
- The empty-lexeme path records an explicit FTS no-contribution/ineligibility observation; it does
  not silently disappear from telemetry or become a missing-trace case.
- This case owns lexical-policy and empty-lexeme no-contribution coverage. TC-61-01 owns the
  candidate-level vector/FTS `ELIGIBLE`, `BELOW_THRESHOLD`, `INELIGIBLE` and no-contribution
  coverage used for fusion decisions.

Evidence: lexical branch observation, policy/version fields, normalized/omitted lexeme lists,
explicit empty-lexeme status and FTS contribution state.

### TC-61-06 — Closed decision/reason taxonomy and precedence

1. Trigger selected, overlap, token-budget and chunk-count outcomes, including candidates for
   which more than one exclusion condition is true.
2. Read the serialized fused candidate decisions.
3. Repeat with an unknown `final_decision` or unknown/incompatible `decision_reason` value.

Expected:

- `final_decision` is exactly one of `SELECTED`, `REDUNDANT_OVERLAP`, `BUDGET_EXCEEDED` or
  `ELIGIBLE_NOT_SELECTED`.
- `decision_reason` is null for `SELECTED`, `REDUNDANT_OVERLAP` and `ELIGIBLE_NOT_SELECTED`.
- `BUDGET_EXCEEDED` requires exactly one reason: `TOKEN_BUDGET` for token-budget exclusion or
  `CHUNK_COUNT_LIMIT` for chunk-count exclusion.
- Competing exclusions use deterministic precedence: `REDUNDANT_OVERLAP` wins over either budget
  condition; when both budget conditions apply, `CHUNK_COUNT_LIMIT` wins over `TOKEN_BUDGET`.
- An unknown value or an incompatible decision/reason pair fails closed and cannot be serialized as
  an accepted candidate decision.

Evidence: serialized candidate decision list, exact enum/reason assertions, competing-condition
fixtures with stable precedence, and closed-failure results for unknown values.

## Verdict rule

Any missing required observation, trace correlation/provenance failure accepted, unauthorized or
cross-Workspace trace accepted, citation outside the selected Evidence Set, malformed
ANSWER/REFUSAL accepted, refusal-correctness data dropped, incorrect latency boundary, lexical
no-contribution omission, unknown taxonomy value accepted or precedence mismatch is `FAILED`. An
unavailable production-shaped environment is `BLOCKED`. `PASSED` requires every case pass and
explicit repository-owner approval.
