# Manual Test Guide: M3 remediation — paired report and fail-closed improvement gate

## Metadata

- Feature: Milestone 3 evaluation and improvement selection
- Slice: Issue #63 — paired report and fail-closed improvement gate
- Authoritative specification: GitHub Issue #63; `docs/design/m3-evaluation-sealed-environment-v2.md`; `docs/design/m3-evaluation-environment-binding-v3.md`; `docs/design/m3-retrieval-rrf-v2-authority-proposal-r9.md`; `docs/standards/architecture.md`; `docs/evaluation.md`; accepted Issue #52 guide `.agents/manual-tests/milestone-3/52-paired-hybrid-evaluation-v3.md`; existing schema-v1 report artifacts under `evals/reports/milestone_3/m3-issue-52-20260814-132055/`; `.agents/review/m3-fixed-point-review-v1.json`
- Supersedes: unapproved `m3-remediation-issue-63-v4`; v4, v3, v2 and v1 remain unchanged and must not be executed
- Guide revision: `m3-remediation-issue-63-v5`
- Approval status: claim-rule authority `m3-improvement-claim-v1` is `APPROVED_EFFECTIVE`; this guide remains pending external review and explicit human approval/lock
- Approved authority source commit: `82f8f5193b658310e73e9f2fb4abf13ebb954076`
- Guide approved by: pending
- Guide approved at: pending

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

### Approved claim-rule authority binding — exact and effective

The immutable authority for TC-04 is now approved and effective. The guide binds the authority by
Git object identity and digest; a working-tree copy, implementation default or caller-supplied rule
is not authority.
The listed authority/review paths are resolved from the approved Git objects and commits; a local
checkout copy in this Issue #63 worktree is not a substitute for those identities.

- Authority identifier and claim-rule version: `m3-improvement-claim-v1`
- Authority lifecycle: `APPROVED_EFFECTIVE`
- Source commit: `82f8f5193b658310e73e9f2fb4abf13ebb954076`
- Authority document:
  `docs/design/m3-improvement-claim-rule-v3.md`
  - Git blob: `cb9c917eaf3d73a31ec4e3d1007bb2463168dcc9`
  - SHA-256: `a8e43cd2468302df35c94648327f9c688f01ea0ba20a199f5a3dc78752ce4773`
- Canonical policy projection:
  `docs/design/m3-improvement-claim-rule-v1.policy.json`
  - Git blob: `6a79bfe367dc1af95a0f50613dcbaa6d3dc868b9`
  - `claim_rule_digest`:
    `sha256:5f44d27602a6a9819d857a15f8cee201deea0f21385b01789777b4ef7bf83c7e`
- Approval payload:
  `.agents/review/m3-improvement-claim-v1-approval.json`
  - Human reviewer identity: `NhiBuaa`
  - Human approver identity: `NhiBuaa`
  - `reviewed_at`: `2026-08-17T03:34:43Z`
  - `approved_at`: `2026-08-17T03:34:43Z`
  - Payload SHA-256: `8dbd257dffec5969b756a165f48e527ac6f79e2b1414786df594a7ca1346b4b1`
  - Attestation commit: `ed575ef837cd422bce131d79fc31959791996bcb`
  - Attestation blob: `0422385455af91420efab5affb87aabdb0c0f14c`
  - Attestation SHA-256: `8dbd257dffec5969b756a165f48e527ac6f79e2b1414786df594a7ca1346b4b1`
- Sealed archive:
  `.agents/review/m3-improvement-claim-v1-approval-sealed-v2.tar`
  - Seal ID: `m3-improvement-claim-v1-approval-seal-v2`
  - SHA-256: `7f24cedc0a9f0f97f06d97483e43b1c9231c6fb93a2996b8cde2bab234a4f38b`
- Sealed manifest SHA-256:
  `f7180796e6259cdcd8f5928311c260d77ab71b07a287c9417d8ab849cf2f6dff`
- Closure result:
  `.agents/review/m3-improvement-claim-v1-approval-closure-v2.json`
  - SHA-256: `5cec43e9a1cd4f502d8308b38bd2b27d30bfbec6922006c01b4fb1c13257e627`
  - Required status: `PASS`
- Canonical authority validation: `APPROVED_EFFECTIVE` with `integrity_valid=true` and no policy
  `NO_CLAIM` downgrade.

The approved projection pins these exact policy values: metric contract
`m3-retrieval-metrics-v1`, `recall_k=8`, ordered closed primary metrics
`recall_at_8` and `mrr`, zero observation failures, the closed all-true guardrails
`structural_validity`, `citation_correctness`, `refusal_correctness`, and qualification
`all primary deltas >= 0 && any primary delta > 0` using exact reduced-rational/cross-multiplied
comparison. No epsilon, rounding tolerance or arbitrary minimum positive delta is permitted.
Latency is retained and disclosed without a hard threshold,
`remaining_regressions` is mandatory, and production/caller/runtime policy overrides are
forbidden or rejected.

Canonical production selection must first validate this exact source/projection/attestation/seal/
closure chain. A missing, stale, malformed, mutated or digest-mismatched authority returns
`AUTHORITY_VALIDATION_FAILURE`; it must not emit policy-based `SELECTED` or `NO_CLAIM`.
After authority validation succeeds, policy failures map to `NO_CLAIM` and only the qualifying
pair maps to `SELECTED`. Selected and no-claim artifacts must retain both
`claim_rule_version` and `claim_rule_digest`.

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
- Execution gate: the claim-rule authority is approved/effective, but this v5 guide is pending external review and explicit human approval/lock. Do not implement or execute any case, and do not create an Evaluation record, before this guide is locked.

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

### TC-04: Approved claim-rule authority binding and fail-closed improvement selection

- Purpose: Verify canonical M3 selection uses only the approved immutable authority above and
  separates authority-validation failure from policy `NO_CLAIM`.
- Authority precondition:
  - Resolve the source document and canonical projection directly from source commit
    `82f8f5193b658310e73e9f2fb4abf13ebb954076`.
  - Verify both Git blob IDs and SHA-256 values, `claim_rule_digest`, the strict approval payload,
    descendant attestation identity, sealed manifest/archive hashes and closure `status: PASS`.
  - Do not parse arbitrary Markdown, use `milestone_3_comparison.py` defaults, or accept a caller/
    runtime policy override as authority.
- Steps:
  1. Load the exact approved authority chain and assert `claim_rule_version` and
     `claim_rule_digest` match every selected/no-claim artifact.
  2. Verify the projection pins `recall_at_8`, `mrr`, zero observation failures, closed all-true
     guardrails and exact qualification `all deltas >= 0 && any delta > 0`; verify exact rational
     decision representation, latency disclosure without a hard threshold and mandatory
     `remaining_regressions`.
  3. Run canonical production selection without a caller override on a valid qualifying pair and on
     a valid pair with no qualifying delta.
  4. Create disposable negative fixtures that mutate each authority identity, projection policy
     field/version, approval assertion, attestation identity, seal/closure digest or caller/runtime
     override. Include `reviewer_id`/`approved_by` values `YOUR_IDENTITY`,
     `YOUR_REAL_IDENTITY`, `<human identity>`, empty/whitespace, `TODO`, `TBD` and `UNKNOWN`.
     Submit each fixture to canonical production selection.
  5. Separately exercise an observation-failure pair and retain the derived fixture as test evidence;
     it must not be mixed into an authoritative measured production run.
- Expected results:
  - A complete exact chain validates before any policy decision. Any missing, malformed, stale,
    mutated or mismatched authority returns `AUTHORITY_VALIDATION_FAILURE` and emits neither
    policy-based `SELECTED` nor policy-based `NO_CLAIM`.
  - An integrity-valid chain whose reviewer or approver identity is a placeholder returns
    `AUTHORITY_VALIDATION_FAILURE` / `HUMAN_IDENTITY_PLACEHOLDER`; it does not become policy
    `NO_CLAIM`. The approved `NhiBuaa` identity chain passes this gate.
  - After authority validation succeeds, a valid pair with no qualifying delta returns
    `NO_CLAIM` with `selected_improvement=null`; an observation failure likewise returns
    `NO_CLAIM`; neither result is converted into a claim.
  - A qualifying pair returns `SELECTED` only under the exact approved rule, and selected/no-claim
    artifacts retain `claim_rule_version`, `claim_rule_digest`, exact decision deltas and the
    required authority/provenance references.
  - Every policy-field/version mutation, approval/attestation/seal/closure mutation and caller
    override is rejected or fails closed before a finding/claim is emitted.
- Evidence to capture:
  - Git object readback for every authority/attestation identity, projection, payload, manifest,
    archive and closure digest; selected/no-claim artifacts retaining version and digest; and
    rejection output for every mutation/override fixture.

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
  2. Confirm tests include absent/empty/incomplete/extra/non-boolean/false guardrails; malformed/mismatched provenance; category applicability and denominator reconciliation; hidden-evidence semantic negative; every taxonomy fixture and stage-invalid finding; missing/stale/malformed/digest-mismatched/non-effective claim-rule authority; placeholder human identities including `YOUR_IDENTITY` and `YOUR_REAL_IDENTITY`; valid `NhiBuaa` identity; policy-field/version mutations; caller-override rejection; `OBSERVATION_FAILURE -> NO_CLAIM`; valid pair with no qualifying delta -> `NO_CLAIM`; and a qualifying selected claim retaining `claim_rule_version` and `claim_rule_digest`.
  3. Record the focused command and complete output without running production Q&A or locked manual cases.
- Expected results:
  - All focused tests pass and demonstrate both accepted and rejected fixtures, including placeholder human identity -> `AUTHORITY_VALIDATION_FAILURE`, both explicit no-claim regressions and the qualifying path.
  - Focused-test success is reported separately and is not represented as a full-suite pass; the known PostgreSQL/psycopg migration baseline limitation remains explicitly tracked.
- Evidence to capture:
  - Focused test command, output, test count, commit SHA under test and the full-pytest limitation reference.

This v5 guide is not locked. The pinned claim-rule authority is already `APPROVED_EFFECTIVE`, but this guide becomes immutable only after external review, explicit human approval and lock. Any later semantic change requires `m3-remediation-issue-63-v6`; v4, v3, v2 and v1 remain unchanged and must not be executed. Store future run observations separately as JSONL Evaluation records.

