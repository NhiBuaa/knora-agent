# Milestone 3 remediation design v4

Status: pending independent external review
Revision: `m3-remediation-design-v4`
Supersedes: `m3-remediation-design-v3`

This append-only revision closes the remaining review ambiguities. The package is frozen first at
an immutable subject commit `P`; the post-package scope projection and review closure are the
only sources of the exact subject identity. Historical designs, guides, issue Evaluations and
review artifacts are not rewritten.

## Canonical serialization and identity proof

All digest values in this contract use SHA-256 over immutable UTF-8 bytes and are written with
the `sha256:` prefix. The identity, scope, case-population and review-response projection files
listed below are the authoritative bytes; a verifier hashes those files directly. This removes
serialization ambiguity from the active gate. For any derived fixture, `canonical_json(value)` is:

```text
UTF-8(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
```

The M3 case-ID projection is `.agents/review/m3-dataset-v1-case-ids.json`; its raw-byte digest
is `sha256:d2295109d810984767b1f8157e323a2993c6773c2ccfd27e5dc61c35e5362253` for the exact 50
IDs in `m3-dataset-v1`. Manifest file and dataset-content digests remain SHA-256 over their raw
committed bytes; no newline normalization is applied to those file digests.

Reviewer identity is independently addressable through the committed record
`.agents/review/identities/codex-agent-m3-final-package-review-v4.json` and projection
`.agents/review/identities/codex-agent-m3-final-package-review-v4-projection.json`; the projection
digest is `sha256:b6af13241badf537647b9c0301043fa721ea6fb42a1ab6a344ff28065076bfda` and the record
raw digest is `sha256:1fa4a4ef8e640c5c32f3ad88ebe38dd662381a89f8e347170fefa119f8d654e3`.
The scope and response projections are post-package artifacts. Their Git blobs and raw SHA-256
values are recorded in the review closure; the production validator resolves that closure and
rejects any generic, missing, assertion-only, self-authored, self-approved, stale or
caller-substituted identity. Response revisions remain preserved as historical evidence.

### Exact package-subject binding (revision v4.2)

The review package is frozen first at package commit `P`; it cannot contain its own commit hash.
The post-package scope projection `S` then records `P`, the exact design blob and sorted subject
paths. A fresh independent response `R` must record both `subject_commit=P` and
`reviewed_commit=P`, plus the Git blob/raw digest of `S`. Finally, the review closure `C` pins the
Git blob/raw digest of `S` and `R`, the identity record, policy projection, reviewer/author/
approver separation, and the approval outcome. `C` is the only active authority input; callers
cannot substitute a path, latest artifact, or assertion-only response. Guides execute closure
validation and recompute every listed raw digest, while stable identity/case-population digests
remain literal inputs. Any later guide or design change creates a new append-only package `P` and
requires a new `S → R → C` chain; prior responses remain historical evidence and are never
rewritten.

The complete review subject scope is immutable and is represented by the following sorted
paths: `.agents/design/m3-remediation-v4.json`,
`.agents/manual-tests/milestone-3/63-remediation-issue-63-v9.md`,
`.agents/manual-tests/milestone-3/68-remediation-authority-v3.md`,
`.agents/manual-tests/milestone-3/69-remediation-population-latency-v4.md`,
`.agents/review/m3-remediation-cadence-input-v3.json`,
`.agents/review/m3-remediation-cadence-v3.json`,
`.agents/review/identities/codex-agent-m3-final-package-review-v4.json`,
`.agents/tickets/m3-remediation-67-active-v4.md`,
`.agents/tickets/m3-remediation-68-active-v4.md`,
`.agents/tickets/m3-remediation-69-active-v4.md`,
`.agents/tickets/m3-remediation-r1-v3.md`,
`.agents/tickets/m3-remediation-r2-v4.md`,
`.agents/tickets/m3-remediation-r3-v4.md`, `docs/design/m3-remediation-v4.md`, and
`docs/standards/architecture.md`, plus the production authority/comparison/seam implementations
and focused remediation tests (`backend/src/knora/adapters/postgres/evaluation_reader.py`,
`backend/src/knora/answering/evidence.py`, `backend/src/knora/answering/module.py`,
`backend/test/adapters/postgres/test_issue_61_reader_contract.py`,
`backend/test/answering/test_issue_61_trace_contract.py`,
`evals/runners/m3_claim_authority.py`, `evals/runners/milestone_3_comparison.py`,
`evals/runners/run_http_eval.py`, `evals/test/test_http_eval.py`,
`evals/test/test_issue_63_remediation.py`, `evals/test/test_issue_68_remediation.py`, and
`evals/test/test_issue_69_remediation.py`).
The sorted requirement IDs are `authority_independent_review`, `exact_manifest_population`,
`native_dependency_graph`, `no_evaluation_only_retrieval`, `pair_latency_boundary`,
`paired_generation_scorer_invariants`, `public_citation_and_trace_failure`, and
`sole_source_policy_projection`, and `two_layer_taxonomy`. The closure's scope record is the
authoritative subject identity and stores the exact package commit, design blob, sorted path set,
and recomputable scope projection digest. No historical subject hash or projection digest in an
older revision is active.

The immutable dataset and corpus manifests are additionally bound to source commit
`2a6061ad38b3b3c4f06811c7ceb8bc26af39892`; production verifies the expected manifest blobs at that
commit and at the measured checkout. A current `HEAD` alone, or a caller-supplied same-shaped
manifest, cannot authorize the M3 population.

## R1 — authority chain and sole-source policy projection

The `canonical_authority_validation` → `ClaimRuleAuthority` seam binds the exact source
commit/blob, approved policy projection blob/digest, identity record, review response,
complete-scope digest, reviewer/author/approver separation, seal and closure. Every field is
required; a mismatch returns `AUTHORITY_VALIDATION_FAILURE` before policy evaluation.

The approved JSON projection is the sole normative value source. Production parses and
strictly validates its schema/types and bound Git blob; it does not contain a duplicated
value-level policy map. Focused fixtures remain explicit `production=False` only.

An effective independent-review response uses schema version 3. In addition to the exact
subject/scope bindings and zero finding counts, it contains typed `requirement_coverage` entries
with `requirement`, `result: PASS` and non-empty `evidence_paths`, and a sorted `reviewed_paths`
list that covers every path in the bound scope projection. Evidence paths must belong to that
reviewed-path set, and every scope requirement must occur exactly once. A free-form review-basis
assertion without this complete typed coverage is invalid.

The same projection binding applies to the closed guardrail key set: production passes the
bound `guardrail_requirement.required_keys` into guardrail and observation validators. A
projection mutation is either reflected by those validators or rejected as an invalid policy;
the compatibility fixture export is not a production policy source.

## R2 — immutable population, paired fields and latency

Production resolves the immutable M3 capability from exact committed paths and identities:

- `evals/datasets/milestone_3.manifest.json`, Git blob
  `08061b4a26b1d10b9720769828bb179264d99fec`, raw SHA-256
  `sha256:f42bb8aa0fe064ab172bac7aa1c8603e9d23b9d3e41ccadbf38d4fbc06c0b41b`;
- dataset content SHA-256
  `sha256:1830dd47863eae06927a4a6c2eb927b13899784ff94c83f522931ca6ec3ccc50`;
- version `m3-dataset-v1`, 50 exact sorted IDs, case-ID digest
  `sha256:d2295109d810984767b1f8157e323a2993c6773c2ccfd27e5dc61c35e5362253`;
- `evals/corpora/milestone_3/manifest.json`, Git blob
  `5b8ff82769239f253d31424606205a9e74828d71`, raw SHA-256
  `sha256:6b0daffe9acb7e541bb1621efb6880cd013d6af6e851f91867b36899d3eca326`;
- corpus `m3-corpus-v1`, Workspace `evaluation-m3-v1`, Chunk Set provenance `chunk-set-m3-v1`.

The capability also binds the exact source commit containing these paths. Every production report
must carry `2a6061ad38b3b3c4f06811c7ceb8bc26af39892` as `provenance.source_commit`; matching
dataset/corpus values with a different source commit are invalid. Subsets, extras, replacements,
wrong path/blob/digest, corpus/Chunk Set drift and caller-provided expected IDs fail closed.
Reduced populations remain only in the explicit non-production comparison seam.

Paired reports must be equal for every field in the equal-provenance contract: dataset version/
digest, corpus ID/digest, Chunk Set ID/digest, Workspace, chunking, embedding, generation,
scorer configuration/model/prompt/policy/stochasticity, metric contract, source commit,
evaluation commit and report artifact schema. Only `retrieval_configuration_id`, `strategy`,
`fusion_policy_id`, `fusion_policy_version`, `lexical_policy_id`, and `fts_candidate_k` may differ.

`m3-paired-latency-v1` is explicit and non-streaming. For each case, `retrieval_latency_ms`
starts immediately after authenticated request validation and immediately before
`AnsweringStore.retrieve_candidates`; it ends immediately after Evidence Selection and before
generation. `end_to_end_latency_ms` starts at the executor's `perf_counter` immediately before
the HTTP request is sent and ends after the complete non-streaming response body is received.
The projection stores both vector and hybrid values, `hybrid_minus_vector` deltas, and
`clock_boundary_version: m3-latency-boundary-v1`, `streaming: false`. No metric is inferred
from the other and no hard latency threshold is applied. Streaming requires a new contract and
must not reuse this metric silently.

The selected record retains both latency sides, metric deltas, guardrails and
`remaining_regressions`.

Branch observations and fused outcomes are separate acceptance data: vector
`ELIGIBLE`/`BELOW_THRESHOLD`/no-contribution and FTS `ELIGIBLE`/`INELIGIBLE`/no-contribution are
pre-fusion statuses; only fused candidates may use `SELECTED`, `REDUNDANT_OVERLAP`,
`BUDGET_EXCEEDED` or `ELIGIBLE_NOT_SELECTED` with `final_rank`/`fusion_score`. Pre-fusion losses
never receive a fused rank or RRF score. A fused `BUDGET_EXCEEDED` decision must carry a closed
`decision_reason` of either `TOKEN_BUDGET` or `CHUNK_COUNT_LIMIT`; the two reasons are not
interchangeable. It also carries typed `budget_evidence` with the configured maximum chunk/token
budgets, selected chunk/token counts, candidate token count and total token count. The reader
binds the candidate token count to the persisted chunk and verifies that `TOKEN_BUDGET` means
the token total exceeds its budget before the chunk-count limit, while `CHUNK_COUNT_LIMIT` means
the selected chunk count has reached its limit. Swapping either reason fails closed.

### Canonical executor seam

The canonical M3 executor symbol is `evals.runners.milestone_3.HttpEvaluationExecutor`, which
calls the production Q&A HTTP endpoint and reads the exact trace returned by that response.
`ProductionM3Executor` remains only a compatibility alias to that class; it is not a second
evaluation path. The compatibility `evals.runners.run_http_eval.HttpEvaluationExecutor` must
enforce the same contract when used by the generic runner: after the response body is received it
captures the completion clock, validates the public payload, and then requires
`trace.trace_id == response.trace_id` and `trace.workspace_id == request.workspace_id` before
any trace-derived observation. `end_to_end_latency_ms` uses the captured response-completion
clock and excludes trace loading, citation validation and scoring. Fault probes for both exact
correlation mismatches and the response-completion timestamp are mandatory acceptance evidence.
Both the canonical and generic compatibility executors expose an injectable monotonic clock for
deterministic tests that prove the tick order: request start, complete response body, then trace
loading. The measured interval ends at the second tick.

## R3 — guide v9 and final integrated acceptance

R3 remains directly blocked by #68 and #69 through native GitHub dependency edges. Guide v9
explicitly tests the final public `answer`, citation marker/order, alias mapping and same-request
binding for deterministic citation correctness. Semantic citation tests supply only public answer
and public citation excerpts/source locators; hidden retrieved chunks from the trace are forbidden.
Missing trace, Workspace mismatch or incomplete provenance is an observation/execution failure,
never a zero quality score. `ANSWER` requires a semantic citation result; `REFUSAL` records that
metric as inapplicable, while `INSUFFICIENT_EVIDENCE_CORRECT` remains a non-failure refusal outcome.

The guide also requires executor route/request evidence and a structural assertion proving no
evaluation-only retrieval path is invoked. Final fixed-point review and cadence `ready` remain
mandatory before Issue #48 closes.
