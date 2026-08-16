# Manual Test Guide: M3 remediation — production trace and public observation contract

- Slice: GitHub Issue #61, child remediation of Issue #48
- Guide revision: `m3-remediation-61-v1`
- Source authority: Issue #48, Issue #61, fixed-point review findings `.agents/review/m3-fixed-point-review-v1.json`
- Worktree: `D:/Developer/Projects/knora-agent-worktree/issue-61-m3-remediation-trace`
- Source base: `511023428202e77e2e981dc8f25ab191cb3c86ab`
- Evaluation history: `.agents/manual-tests/milestone-3/61-remediation-production-observation.evaluations.jsonl`

## Preconditions

- PostgreSQL/pgvector and the production-shaped Q&A endpoint are running from the issue-61
  worktree.
- The M3 Workspace has active vector and hybrid configurations and a corpus containing a lexical
  match, a semantic match, an excluded candidate, an empty-lexeme query and a refusal case.
- No raw provider secret or SQL implementation detail is included in trace/report evidence.

## Test cases

### TC-61-01 — Branch observations remain separate from fused candidates

1. Run a query with a vector candidate below `min_similarity`, an FTS-eligible candidate for the
   same canonical Chunk, and a candidate eligible in both branches.
2. Read the correlated trace.

Expected:

- Vector and FTS branch observations contain their closed eligibility statuses and nullable
  contributions.
- The vector-below-threshold/FTS-eligible Chunk has only an FTS contribution.
- Only eligible contributions receive fused rank and fusion score; pre-fusion losses never receive
  `final_rank` or `fusion_score`.

Evidence: trace JSON, branch statuses, fused ordering and canonical Chunk identity assertions.

### TC-61-02 — Required trace provenance fails closed

1. Read a valid trace with retrieval configuration, fusion-policy, embedding-set, chunk-set and
   lexical provenance.
2. Repeat with each required field removed or malformed.

Expected: the valid trace is accepted; each malformed trace is an explicit observation failure and
never receives a quality score or fabricated latency.

Evidence: reader result/error taxonomy and provenance field projection.

### TC-61-03 — Public citations map only to selected Evidence Set members

1. Produce one answer citing a selected candidate.
2. Produce a response whose alias maps to a fused candidate excluded by chunk count, token budget
   or overlap.
3. Produce valid and malformed refusal responses.

Expected: selected citation passes; excluded-candidate citation fails closed; ANSWER validates
markers/order/citations; REFUSAL validates answer/refusal reason/citation emptiness.

Evidence: public response, correlated trace, deterministic validation result and no hidden chunks
sent to semantic scoring.

### TC-61-04 — Retrieval latency clock boundary

1. Instrument candidate retrieval and Evidence Selection with distinct delays.
2. Execute the production Q&A request and capture trace retrieval latency plus client end-to-end
   duration.

Expected: retrieval latency includes retrieval and Evidence Selection but excludes generation;
end-to-end includes the complete client request/response interval; neither metric is derived from
the other.

Evidence: injected timing markers, trace latency, executor duration and arithmetic boundary check.

### TC-61-05 — Lexical policy provenance and empty-lexeme behavior

1. Run a query producing normalized and omitted lexemes.
2. Run a query whose normalization produces no eligible lexemes.

Expected: trace records versioned lexical policy, normalized/omitted lexemes and FTS ineligibility;
the empty-lexeme path does not silently become a missing telemetry case.

Evidence: lexical branch observation and policy/version fields.

### TC-61-06 — Closed decision-reason taxonomy

1. Trigger selected, overlap, token-budget and chunk-count outcomes.
2. Read the serialized fused candidate decisions.

Expected: final decisions are the approved closed enum and `decision_reason` uses exactly
`TOKEN_BUDGET` or `CHUNK_COUNT_LIMIT` where applicable.

Evidence: serialized candidate decision list and exact enum assertions.

## Verdict rule

Any missing required observation, citation outside the selected Evidence Set, malformed refusal
accepted, missing provenance, incorrect latency boundary or taxonomy mismatch is `FAILED`. An
unavailable production-shaped environment is `BLOCKED`. `PASSED` requires every case pass and
explicit repository-owner approval.
