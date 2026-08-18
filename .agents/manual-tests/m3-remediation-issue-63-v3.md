# Manual Test Guide: M3 remediation — paired report and fail-closed improvement gate

## Metadata

- Feature: Milestone 3 evaluation and improvement selection
- Slice: Issue #63 — paired report and fail-closed improvement gate
- Authoritative specification: GitHub Issue #63; `docs/design/m3-evaluation-sealed-environment-v2.md`; `docs/design/m3-evaluation-environment-binding-v3.md`; `docs/design/m3-retrieval-rrf-v2-authority-proposal-r9.md`; `docs/standards/architecture.md`; `docs/evaluation.md`; accepted Issue #52 guide `.agents/manual-tests/milestone-3/52-paired-hybrid-evaluation-v3.md`; existing schema-v1 report artifacts under `evals/reports/milestone_3/m3-issue-52-20260814-132055/`; `.agents/review/m3-fixed-point-review-v1.json`
- Supersedes: unapproved `m3-remediation-issue-63-v2`; v2 and v1 remain unchanged and must not be executed
- Guide revision: `m3-remediation-issue-63-v3`
- Approval status: pending authority clarification, external review and explicit human approval
- Approved by: pending
- Approved at: pending

## Scope and immutable contracts

- This guide covers only Issue #63 report construction, paired provenance validation,
  denominator/applicability accounting, taxonomy validation and fail-closed improvement
  selection. It does not add or re-test ownership/seal implementation; the existing sealed
  environment is a prerequisite owned by the other remediation slice.
- Report schema version `1` is the existing immutable schema. Its closed required guardrail key
  set is exactly `{structural_validity, citation_correctness, refusal_correctness}`, and every
  value for those keys is a JSON boolean. `observation_failure_count` and
  `observed_guardrail_values` are audit counters in the existing report artifacts, not guardrail
  keys. Unknown guardrail keys are invalid under this closed contract; the implementation may not
  invent or infer the required set.
- The paired-difference contract permits only the exact configuration-specific fields
  `{retrieval_configuration_id, strategy, fusion_policy_id, fusion_policy_version,
  lexical_policy_id, fts_candidate_k}` to differ. Dataset version/digest, corpus and Chunk Set
  identity/digest, Workspace, chunking, embedding, generation, scorer, metric contract,
  `source_commit`, `evaluation_commit`, stochasticity/prompt/policy provenance and artifact
  schema version must match exactly. `source_commit` and `evaluation_commit` are the locked Git
  provenance names; a generic `recorded_git_commit` is not accepted.
- The semantic scorer input is exactly the public-only projection produced by the existing
  `semantic_citation_input` seam: the final public answer and each public citation's excerpt and
  source locator; the accompanying `evidence_id` is only an opaque public correlation alias, not
  evidence content. Hidden trace candidates/chunks, excluded candidates, database IDs and dataset
  gold metadata are never scorer input. The pinned method is
  `public-answer-public-citation-only-v1`.
- The closed taxonomy is `m3-failure-taxonomy-v1` with the exact fixture mapping below. It has one
  primary enum and optional contributing enums from the same closed allowlist. The exact
  `INSUFFICIENT_EVIDENCE_CORRECT` outcome is non-failure. Branch, fusion and Evidence Selection
  stage preconditions are checked before a finding is emitted.

### Claim-rule authority clarification — blocking

- No immutable/pre-declared authority currently defines the complete `m3-improvement-claim-v1`
  policy. The checked statements at `CONTEXT.md:451-454`,
  `docs/standards/architecture.md:898-901`, Issue #48's Milestone 3 decisions, Issue #52's
  acceptance criteria, Issue #63's acceptance criteria, `docs/evaluation.md`, and the accepted
  Issue #52 guide require a pre-declared claim rule but do not pin its full policy parameters.
- Existing `improvement.json` artifacts retain `claim_rule_version` but do not retain the policy
  values needed to establish an independent oracle. `evals/runners/milestone_3_comparison.py`
  currently contains a default mapping and accepts a caller-supplied `claim_rule`; that is
  implementation behavior, not immutable authority, and must not be promoted to authority by this
  guide.
- Therefore this v3 does not assert values for primary metrics, minimum-delta comparison or
  boundary semantics, all-vs-any metric qualification, guardrail requirement, or the
  zero-observation-failure precondition. TC-04 is blocked at authority clarification until an
  approved immutable artifact pins all of them and its digest/approval is recorded.
- The eventual authority must explicitly state the exact claim-rule version and all policy
  parameters, and must require every selected/no-claim artifact to retain `claim_rule_version`.
  It must also prohibit policy weakening through caller overrides; an override, version mutation,
  missing field or authority digest mismatch must be rejected/fail closed by canonical M3
  production selection.

### Closed taxonomy fixture mapping

| Deterministic fixture ID | Required primary enum |
| --- | --- |
| `fixture-lexical-branch-miss` | `LEXICAL_MISS` |
| `fixture-semantic-branch-miss` | `SEMANTIC_MISS` |
| `fixture-fusion-union-ranked-low` | `FUSION_RANKING_ERROR` |
| `fixture-evidence-selection-excluded` | `EVIDENCE_SELECTION_ERROR` |
| `fixture-answer-refused` | `FALSE_REFUSAL` |
| `fixture-citation-structure-invalid` | `CITATION_STRUCTURAL_ERROR` |
| `fixture-citation-semantic-unsupported` | `CITATION_SEMANTIC_UNSUPPORTED` |
| `fixture-corpus-or-config-mismatch` | `CORPUS_OR_CONFIGURATION_MISMATCH` |
| `fixture-observation-invalid` | `EVALUATION_OBSERVATION_FAILURE` |
| `fixture-provider-failure` | `PROVIDER_ERROR` |
| `fixture-infrastructure-failure` | `INFRASTRUCTURE_ERROR` |
| `fixture-insufficient-evidence-correct` | `INSUFFICIENT_EVIDENCE_CORRECT` (non-failure) |

## Prerequisites

- Environment: isolated Issue #63 worktree at `D:/Developer/Projects/knora-agent-worktree/issue-63-m3-remediation-report`, checked out at the implementation fixed point under test; Python virtual environment and repository test dependencies available.
- Data and state: use a fresh temporary report/evaluation directory for each run; use only immutable, validated M3 dataset/corpus, Chunk Set, retrieval, embedding, generation, scorer, Git, and artifact-schema inputs. The PostgreSQL-backed production evaluation environment may be used only as an already-sealed prerequisite; this guide does not implement or change seal ownership.
- Credentials and permissions: evaluator may read the sealed production observations and write report artifacts; no raw provider secrets may be written to logs or provenance. Human reviewer must be able to inspect generated JSON artifacts and focused-test output.
- Execution gate: this v3 guide is blocked on claim-rule authority clarification and pending approval. Do not implement or execute any case, and do not create an Evaluation record, before an approved authority artifact, explicit human approval and guide lock.

## Proposed Test Cases (not locked; pending approval)

### TC-01: Complete paired report records public outcomes, metric denominators and semantic boundaries

- Purpose: Verify the report includes public answer/citation/refusal outcomes, deterministic and semantic citation correctness, refusal correctness, aggregate/category metrics, independent latencies, and auditable denominator semantics.
- Steps:
  1. Run the canonical paired production evaluation for the approved vector and hybrid configurations against a valid sealed environment containing applicable answerable, lexical, semantic, multi-source, and refusal cases.
  2. Open the generated vector report, hybrid report, pair report, and publication manifest.
  3. Correlate each observation with its public response and persisted trace.
  4. Separately construct derived, disposable observation-failure and hidden-evidence mutation fixtures; do not mix those mutations into either authoritative measured production run.
  5. Inspect aggregate and every category/metric section, using the derived observation-failure fixture only for audit/denominator assertions, and reconcile `applicable_count`, `inapplicable_count`, `observation_failure_count`, `numerator`, `denominator` and `value`.
  6. Capture the exact semantic-scorer request input for one valid answer and use the derived hidden-evidence fixture to prove that hidden trace evidence cannot substitute for the public citation.
- Expected results:
  - Every successful observation records the public decision/answer, citations, refusal reason when applicable, deterministic citation result, semantic citation result, refusal correctness, retrieval latency, and end-to-end latency.
  - The authoritative measured production reports contain only their actual production observations; derived failure/hidden-evidence mutations are labelled fixtures and never alter the measured dataset, corpus, traces or quality claim.
  - For aggregate and each category/metric, `applicable_count + inapplicable_count` equals the category membership count; `observation_failure_count` is a separately reported subset of applicable cases; `denominator` equals applicable cases minus observation failures; `numerator` is the sum of valid per-case contributions; and `value` is `numerator / denominator`, or explicit null when the denominator is zero.
  - The derived observation-failure fixture is retained in its fixture/report audit, is not converted to zero quality, is not counted as inapplicable, and contributes neither numerator nor denominator.
  - Aggregate and category sections cover lexical, semantic, multi-source, and refusal categories; refusal cases do not receive retrieval scores when retrieval is inapplicable.
  - Retrieval latency includes candidate retrieval plus Evidence Selection and excludes generation and seal-control-plane work.
  - The semantic scorer receives only the final public answer plus public citation excerpt and source locator (with `evidence_id` retained only as an opaque public alias). Injecting hidden evidence, excluded candidates or gold metadata cannot make semantic citation correctness pass when the public citation is unsupported.
- Evidence to capture:
  - Generated `vector-report.json`, `hybrid-report.json`, `pair.json`, and publication manifest paths and SHA-256 digests.
  - Aggregate and every category reconciliation table, including the derived failure fixture and its audit record.
  - The exact semantic-scorer input payload and the derived hidden-evidence fixture result.

### TC-02: Complete typed provenance and allowed-difference contract are required for a paired comparison

- Purpose: Verify immutable reproducibility fields are captured and compared before any improvement claim, with only declared retrieval-configuration semantics allowed to differ.
- Steps:
  1. Produce a valid vector/hybrid report pair with dataset version/digest, corpus and Chunk Set identity/digest, Workspace, chunking, embedding, generation/scorer versions, scorer model/prompt/policy/stochasticity, metric contract, `source_commit`, `evaluation_commit`, both retrieval configuration IDs, and artifact schema version.
  2. Compare the pair using the canonical comparison entry point and record the exact allowed-difference projection.
  3. Repeat after removing or changing one required shared field at a time, including Workspace, corpus/Chunk Set digest, embedding, scorer prompt/policy/stochasticity, artifact schema, `source_commit` and `evaluation_commit`.
  4. Repeat with a change to a field outside the allowed-difference set, such as `workspace_id`, `scorer_model` or `metric_contract`, while leaving retrieval configuration differences valid.
- Expected results:
  - The complete pair has `provenance_match=true` only when all required fields are present, correctly typed, and equal after removing exactly the six pinned configuration-specific fields.
  - Retrieval Configuration and its declared strategy/fusion/lexical semantics may differ only through the pinned allowed set; no other field is silently ignored.
  - Missing, malformed, mismatched or out-of-set provenance produces explicit `PROVENANCE_MISMATCH`/no-claim behavior and prevents publication of a selected improvement.
- Evidence to capture:
  - Pair comparison JSON for the valid pair and every tampered variant, including the exact no-claim or provenance failure reason and the `source_commit`/`evaluation_commit` readback.

### TC-03: Closed guardrails fail closed for every malformed or incomplete shape

- Purpose: Verify the immutable report-schema guardrail contract is closed and cannot be weakened by implementation-defined required keys.
- Steps:
  1. Start with a valid paired report whose `guardrails` object contains exactly the required keys `structural_validity`, `citation_correctness` and `refusal_correctness`, each with a JSON boolean value.
  2. Evaluate variants with the guardrails object absent, null, empty, missing each required key one at a time, containing an extra/unknown key, containing a non-boolean value for each required key, and containing each required key set to false.
  3. Run the improvement-selection entry point for each variant, retaining the existing audit counters separately from the guardrail mapping.
- Expected results:
  - Only the exact closed key set with all three values `true` can satisfy the guardrail precondition; `observation_failure_count` and `observed_guardrail_values` do not substitute for a required key.
  - Every absent, null, empty, incomplete, extra/unknown, non-boolean, or false guardrail variant fails closed with explicit `GUARDRAIL_FAILURE`/`NO_CLAIM`, with no selected improvement.
  - The required key set is read from the pinned schema/authority above, not inferred from the supplied mapping or implementation defaults.
- Evidence to capture:
  - Selection result for each mutation, the exact schema key-set assertion, and the explicit failure reason.

### TC-04: Claim-rule authority clarification and fail-closed improvement selection

- Purpose: Establish an independent oracle for `m3-improvement-claim-v1`; ensure canonical production selection never derives authority from implementation defaults or caller overrides.
- Authority precondition:
  - Current status is **BLOCKED**: no immutable/pre-declared authority currently pins the exact claim-rule version and policy values. Do not infer them from `milestone_3_comparison.py`, existing `improvement.json` files, or any caller-supplied mapping.
- Steps:
  1. Before selection, load the future approved claim-rule authority artifact and verify its immutable identity/digest, approval evidence and exact `m3-improvement-claim-v1` version.
  2. Verify that the authority explicitly pins all policy parameters: primary metrics; minimum-delta value and strict/inclusive comparison semantics; all-vs-any metric qualification; exact guardrail requirement; zero-observation-failure precondition; and whether policy overrides are forbidden.
  3. If the authority artifact is absent, malformed, unapproved, stale, or digest-mismatched, stop at authority clarification. Do not run canonical selection and do not manufacture a selected or no-claim result from an unresolved policy.
  4. Once the authority exists, run canonical M3 production selection with no caller override on a qualifying pair and on a valid pair without a qualifying delta. Verify both selected and no-claim artifacts retain the exact `claim_rule_version` and all required policy/provenance references.
  5. Create disposable negative fixtures that mutate each authoritative policy field and version independently, and a caller-supplied override for each field. Submit each to canonical production selection.
- Expected results:
  - Until the authority clarification is approved, TC-04 remains blocked and no policy value is treated as authoritative.
  - After approval, the canonical selector uses exactly the authority values; a field/version mutation, missing authority field, digest mismatch or caller override is rejected/fails closed and cannot weaken the rule.
  - The qualifying artifact and every no-claim artifact retain the exact authoritative `claim_rule_version`; no artifact may silently fall back to an implementation default.
  - A valid pair with no qualifying delta returns `NO_CLAIM` with `selected_improvement=null`; an observation failure returns `NO_CLAIM` with `selected_improvement=null`; neither result is converted into a claim.
- Evidence to capture:
  - Authority artifact, approval/readback and digest; exact policy projection; selected and no-claim artifacts with `claim_rule_version`; and rejection output for each policy-field/version mutation and caller override.

### TC-05: Closed taxonomy preserves every authoritative enum and enforces stage semantics

- Purpose: Verify the exact versioned taxonomy and fixture mapping remain closed, preserve the non-failure refusal outcome, and reject stage-invalid or category-invalid findings before emission.
- Steps:
  1. Load every fixture in the pinned `m3-failure-taxonomy-v1` mapping above and generate one finding per fixture.
  2. Assert the exact `taxonomy_version`, primary enum and fixture mapping; attempt rename/drop/synonym variants for every enum.
  3. Include `fixture-insufficient-evidence-correct` and verify `INSUFFICIENT_EVIDENCE_CORRECT` is non-failure.
  4. Submit valid branch-miss evidence, fusion evidence proving gold presence in the eligible branch union and incorrect post-fusion rank, and Evidence Selection evidence proving post-fusion exclusion by the locked selection policy.
  5. Submit variants with missing branch-union evidence, fusion evidence before both branches ran, Evidence Selection evidence before fused ordering, an invalid optional contributing category, a duplicate/unknown enum, and a refusal incorrectly marked as a failure.
- Expected results:
  - All twelve fixtures map one-to-one to the exact closed enum table; no enum is renamed, dropped or replaced by a synonym.
  - `INSUFFICIENT_EVIDENCE_CORRECT` remains explicitly non-failure and is not emitted as a failure finding.
  - Optional contributing categories are accepted only from the same closed enum allowlist and only with valid stage evidence.
  - Stage-invalid, category-invalid, renamed/dropped/unknown-enum, and refusal-as-failure variants are rejected before any finding enters the report.
- Evidence to capture:
  - Taxonomy version, complete enum allowlist, fixture-to-enum mapping output and preservation assertions.
  - Branch/fusion/Evidence Selection precondition evidence and rejection output for every invalid variant.

### TC-06: Category applicability, denominator audit and public citation boundaries are enforced

- Purpose: Verify category metrics reconcile their own membership/applicability sets and public citations cannot use hidden or excluded evidence.
- Steps:
  1. Run answerable lexical, semantic and multi-source cases plus a refusal/no-hit case, and include one applicable observation-failure fixture in a category.
  2. For aggregate and each category/metric, record `applicable_count`, `inapplicable_count`, `observation_failure_count`, `numerator`, `denominator` and `value`; verify the membership/applicability/failure equations from TC-01.
  3. Include a response that cites a retrieved-but-excluded candidate, a response with duplicate aliases for one chunk, and a negative semantic scorer fixture where hidden trace evidence supports an otherwise unsupported public citation.
  4. Build the report and category breakdown, then inspect the public-only semantic-scorer payload and guardrail result.
- Expected results:
  - Retrieval metrics are omitted or marked inapplicable for refusal cases, while refusal correctness is still scored.
  - The observation-failure fixture remains an auditable failure, is not a zero metric contribution, is not inapplicable and is not silently omitted from aggregate/category reports.
  - Citations to excluded candidates, duplicate chunk mappings or hidden-only evidence fail deterministic/semantic citation validation and cannot contribute a passing guardrail.
  - Category aggregates include only applicable observations in their denominator, reconcile numerator/value exactly and identify the category in each breakdown.
- Evidence to capture:
  - Observation records, aggregate/category reconciliation, citation-validation results, exact semantic input payload, hidden-evidence negative result and final guardrail status.

### TC-07: Focused regression tests cover every no-claim and qualifying path

- Purpose: Verify executable focused coverage for malformed reports, closed guardrails/provenance, applicability, observation failure, stage-invalid findings, claim-rule authority gating, no-claim and qualifying-claim paths while keeping the full-suite limitation explicit.
- Steps:
  1. Run the repository's focused M3 remediation test selection for report construction, paired comparison, taxonomy validation, semantic citation projection and improvement selection.
  2. Confirm tests include absent/empty/incomplete/extra/non-boolean/false guardrails; malformed/mismatched provenance; category applicability and denominator reconciliation; hidden-evidence semantic negative; every taxonomy fixture and stage-invalid finding; unresolved/malformed claim-rule authority; policy-field/version mutations; caller-override rejection; `OBSERVATION_FAILURE -> NO_CLAIM`; valid pair with no qualifying delta -> `NO_CLAIM`; and a qualifying selected claim retaining `claim_rule_version`.
  3. Record the focused command and complete output without running production Q&A or locked manual cases.
- Expected results:
  - All focused tests pass and demonstrate both accepted and rejected fixtures, including both explicit no-claim regressions and the qualifying path.
  - Focused-test success is reported separately and is not represented as a full-suite pass; the known PostgreSQL/psycopg migration baseline limitation remains explicitly tracked.
- Evidence to capture:
  - Focused test command, output, test count, commit SHA under test and the full-pytest limitation reference.

This v3 guide is not locked. It becomes immutable only after claim-rule authority clarification, external review and explicit human approval. Any later semantic change requires `m3-remediation-issue-63-v4`; v2 and v1 remain unchanged and must not be executed. Store future run observations separately as JSONL Evaluation records.
