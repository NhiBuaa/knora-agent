# Milestone 3 remediation design v3

Status: pending independent external review
Revision: `m3-remediation-design-v3`
Supersedes: `m3-remediation-v2`

This revision incorporates the external review findings from
`codex-agent:/root/m3_remediation_external_review`. It remains append-only: the v2 design,
old ticket bodies, v6 guide, and all historical Evaluation/review artifacts are unchanged.

## Immutable design subject and review binding

The design subject is this document and the ticket/guide package at source commit
`bf23b677eb717dfa0ca51faa60ff61623433a10c`. A later approval artifact must bind that exact
commit, its Git blob for this document, the complete package scope, and a concrete reviewer
identity. The reviewer identity contract is:

- `reviewer_id` is a stable execution-task identity such as
  `codex-agent:/root/m3_remediation_external_review_v2`, never a generic placeholder;
- the artifact records `identity_kind`, `source_record`, `identity_digest`, reviewed subject
  commit/blob and complete-scope digest;
- the reviewer identity is checked against the source-commit author and approver, and the
  artifact must explicitly state `reviewer_was_author: false` and
  `reviewer_was_approver: false`;
- the sealed review response and closure are content-addressed and are required before any
  implementation or policy result can become effective.

## R1 — authority chain and sole-source policy projection

The production seam remains `canonical_authority_validation` → `ClaimRuleAuthority`.
The new authority revision binds the external-review artifact above, the exact source commit,
the exact approved policy JSON Git blob/digest, review scope, seal, and closure. Production
derives the source-commit author from Git and rejects missing, malformed, generic,
self-authored, self-approved, or assertion-only reviewer evidence.

The approved policy JSON projection is the sole normative value source. Production parses and
strictly validates its schema/types and exact bound Git blob; it does not maintain a second
value-level policy copy in Python. Focused fixtures may construct a typed projection only with
`production=False`; production caller authority and policy overrides remain forbidden.

Required external-review fields are `reviewer_id`, `identity_kind`, `source_record`,
`identity_digest`, `reviewed_subject_commit`, `reviewed_subject_blob`, `scope_digest`,
`reviewer_was_author`, `reviewer_was_approver`, `verdict`, `reviewed_complete_scope`,
`response_sha256`, and the sealed closure identities. A missing or mismatched field is an
`AUTHORITY_VALIDATION_FAILURE` before policy evaluation.

## R2 — immutable population binding and paired latency

The canonical production selector resolves and validates the following immutable manifest
capability from the repository root; callers cannot supply replacements:

| Binding | Exact value |
| --- | --- |
| dataset manifest path | `evals/datasets/milestone_3.manifest.json` |
| dataset manifest Git blob at the design base | `08061b4a26b1d10b9720769828bb179264d99fec` |
| dataset manifest SHA-256 | `f42bb8aa0fe064ab172bac7aa1c8603e9d23b9d3e41ccadbf38d4fbc06c0b41b` |
| dataset content SHA-256 | `1830dd47863eae06927a4a6c2eb927b13899784ff94c83f522931ca6ec3ccc50` |
| dataset version/case count | `m3-dataset-v1` / `50` |
| sorted case-ID digest | `ff69bb0f8ebffb9a5b82ca64244b92f8e7f07eb2163da959b4ea3480d2838ce0` |
| corpus manifest path | `evals/corpora/milestone_3/manifest.json` |
| corpus manifest Git blob at the design base | `5b8ff82769239f253d31424606205a9e74828d71` |
| corpus manifest SHA-256 | `6b0daffe9acb7e541bb1621efb6880cd013d6af6e851f91867b36899d3eca326` |
| corpus/chunk-set provenance | `m3-corpus-v1` / `chunk-set-m3-v1` |

The capability also binds the immutable source commit/blob used to resolve those paths. The
production selector rejects subsets, extras, replacements, wrong digests, corpus/Chunk Set
mismatches, and caller-provided expected IDs. `compare_paired_reports(... expected_case_ids=...)`
is retained only as an explicit non-production fixture seam.

Paired reports must match every field in the existing equal-provenance contract:
`dataset_version`, `dataset_digest`, `corpus_id`, `corpus_digest`, `chunk_set_id`,
`chunk_set_digest`, `workspace`, `chunking_configuration`, `embedding_configuration`,
`generation_configuration`, `scorer_configuration`, `scorer_model`, `scorer_prompt`,
`scorer_policy`, `scorer_stochasticity`, `metric_contract`, `source_commit`,
`evaluation_commit`, and `report_artifact_schema_version`. Only the retrieval-configuration
fields may differ: `retrieval_configuration_id`, `strategy`, `fusion_policy_id`,
`fusion_policy_version`, `lexical_policy_id`, and `fts_candidate_k`.

The versioned pair-level latency projection `m3-paired-latency-v1` stores, for every case,
vector and hybrid `retrieval_latency_ms`, vector and hybrid `end_to_end_latency_ms`, explicit
`hybrid_minus_vector` deltas for each metric, and clock-boundary metadata. The selector stores
both sides of that projection, guardrails, metric deltas, and `remaining_regressions`. No
latency hard cutoff or inference from one latency metric to the other is introduced; streaming
would require a separate contract.

The manual evidence must prove the executor uses the public Q&A endpoint and exact
`(workspace_id, trace_id)` correlation, and must include structural/request evidence that no
evaluation-only retrieval path is invoked.

## R3 — guide v7 and final integrated acceptance

R3 remains directly blocked by R1 and R2 through native GitHub dependency edges. The new
append-only guide v7 adds authority identity provenance, exact manifest path/blob/digest and
case-ID binding, field-level paired generation/scorer invariants, pair-level latency and
regression retention, refusal semantic applicability, and no-evaluation-only-path evidence.
It runs only after R1 and R2 are integrated and their external review/acceptance records are
bound. Final fixed-point review and cadence evidence gate remain mandatory before Issue #48 can
close.

## Completion gate

M3 closes only at a new fixed point with code review `APPROVE` and zero Critical/Major findings,
cadence `ready`, zero observation failures, valid immutable provenance, and a selected record
that retains metric deltas, guardrails, pair-level latency trade-offs, and all remaining
regressions. Default branch and all relevant worktrees must be clean.
