# Manual Test Guide: M3 remediation — paired report and fail-closed improvement gate

## Metadata

- Feature: Milestone 3 evaluation and improvement selection
- Slice: Issue #63 — paired report and fail-closed improvement gate
- Authoritative specification: GitHub Issue #63; `docs/design/m3-evaluation-sealed-environment-v2.md`; `docs/design/m3-evaluation-environment-binding-v3.md`; `docs/design/m3-retrieval-rrf-v2-authority-proposal-r9.md`; `.agents/review/m3-fixed-point-review-v1.json`
- Guide revision: `m3-remediation-issue-63-v1`
- Approved by: pending explicit human approval
- Approved at: pending

## Prerequisites

- Environment: isolated Issue #63 worktree at `D:/Developer/Projects/knora-agent-worktree/issue-63-m3-remediation-report`, checked out at the implementation fixed point under test; Python virtual environment and repository test dependencies available.
- Data and state: use a fresh temporary report/evaluation directory for each run; use only immutable, validated M3 dataset/corpus, Chunk Set, retrieval, embedding, generation, scorer, Git, and artifact-schema inputs. Keep the PostgreSQL-backed production evaluation environment sealed for the measured run and perform post-run drift verification before releasing it.
- Credentials and permissions: evaluator may read the sealed production observations and write report artifacts; no raw provider secrets may be written to logs or provenance. Human reviewer must be able to inspect generated JSON artifacts and focused-test output.

## Locked Test Cases

### TC-01: Complete paired report records public outcomes and required metrics

- Purpose: Verify the report includes public answer/citation/refusal outcomes, deterministic and semantic citation correctness, refusal correctness, aggregate and category metrics, and independent retrieval and end-to-end latency observations.
- Steps:
  1. Run the canonical paired production evaluation for the approved vector and hybrid configurations against a valid sealed environment containing applicable answerable, lexical, semantic, multi-source, and refusal cases.
  2. Open the generated vector report, hybrid report, pair report, and publication manifest.
  3. Correlate each observation with its public response and persisted trace.
- Expected results:
  - Every observation records the public decision/answer, citations, refusal reason when applicable, deterministic citation result, semantic citation result, refusal correctness, retrieval latency, and end-to-end latency.
  - Aggregate and category sections cover lexical, semantic, multi-source, and refusal categories; refusal cases do not receive retrieval scores when retrieval is inapplicable.
  - Retrieval latency includes candidate retrieval plus Evidence Selection and excludes generation and seal-control-plane work.
- Evidence to capture:
  - Generated `vector-report.json`, `hybrid-report.json`, `pair.json`, and publication manifest paths and SHA-256 digests.
  - A representative answerable observation, refusal observation, category breakdown, and latency fields.

### TC-02: Complete typed provenance is required for a paired comparison

- Purpose: Verify immutable reproducibility fields are captured and compared before any improvement claim.
- Steps:
  1. Produce a valid vector/hybrid report pair with dataset version/digest, corpus and Chunk Set digests, both retrieval configuration IDs, embedding/generation/scorer versions, scorer model/prompt/policy, Git commit, and artifact schema version.
  2. Compare the pair using the canonical comparison entry point.
  3. Repeat after removing or changing one required provenance field in either report.
- Expected results:
  - The complete pair has `provenance_match=true` only when all required fields are present, correctly typed, and equal under the declared pairing rules.
  - Missing, malformed, or mismatched provenance produces an explicit no-claim outcome and prevents publication of a selected improvement.
- Evidence to capture:
  - Pair comparison JSON for the valid pair and each tampered variant, including the exact no-claim reason.

### TC-03: Missing or malformed guardrails fail closed

- Purpose: Verify an empty, missing, non-boolean, or incomplete guardrail mapping can never pass the improvement gate.
- Steps:
  1. Start with a valid paired report whose required guardrails are all explicit booleans.
  2. Evaluate variants with the guardrails mapping absent, empty, missing one required key, containing a non-boolean value, and containing a false refusal/citation/structural guardrail.
  3. Run the improvement-selection entry point for each variant.
- Expected results:
  - Only the complete all-true guardrail set can satisfy the guardrail precondition.
  - Every absent, empty, incomplete, malformed, or false guardrail variant returns an explicit no-claim / `GUARDRAIL_FAILURE` outcome with no selected improvement.
- Evidence to capture:
  - Selection result for each mutation, including required-key validation and failure reason.

### TC-04: Qualifying selected improvement retains deltas, trade-offs, and regressions

- Purpose: Verify a genuinely qualifying pair produces the complete selected-improvement artifact.
- Steps:
  1. Use a valid baseline/hybrid pair with complete provenance and guardrails, with the hybrid satisfying the locked improvement policy.
  2. Run paired comparison and improvement selection.
  3. Inspect the selected-improvement record.
- Expected results:
  - The record is selected only after all metric and guardrail policy checks pass.
  - It retains deterministic metric deltas, guardrail values, latency trade-offs, and a deterministic `remaining_regressions` section, including an empty section when none remain.
- Evidence to capture:
  - `improvement.json` and the paired reports, with the selected configuration IDs and all retained sections.

### TC-05: Failure taxonomy enforces pipeline-stage semantics

- Purpose: Verify branch, fusion, Evidence Selection, contributing-category, and non-failure refusal semantics are validated before findings are emitted.
- Steps:
  1. Submit valid structured findings for semantic/lexical branch misses, fusion ranking errors, Evidence Selection errors, and refusal outcomes with their required stage evidence.
  2. Submit variants with missing branch-union evidence, fusion evidence before both branches ran, Evidence Selection evidence before fused ordering, invalid contributing categories, and a refusal incorrectly marked as a failure.
  3. Run the taxonomy classifier and inspect the resulting findings artifact.
- Expected results:
  - Valid findings retain their canonical primary and optional contributing categories.
  - Stage-invalid, category-invalid, and refusal-as-failure variants are rejected with explicit validation errors; no invalid finding enters the report.
- Evidence to capture:
  - Classifier output for valid cases and rejection records for every invalid variant.

### TC-06: Category applicability and public citation boundaries are enforced

- Purpose: Verify category metrics respect applicability and public citations can reference only selected Evidence Set members.
- Steps:
  1. Run answerable lexical, semantic, and multi-source cases plus a refusal/no-hit case.
  2. Include a response that cites a retrieved-but-excluded candidate and another response with duplicate aliases for one chunk.
  3. Build the report and category breakdown.
- Expected results:
  - Retrieval metrics are omitted or marked inapplicable for refusal cases, while refusal correctness is still scored.
  - Citations to excluded candidates or duplicate chunk mappings fail deterministic citation validation and cannot contribute a passing guardrail.
  - Category aggregates include only applicable observations and identify the category in each breakdown.
- Evidence to capture:
  - Observation records, category breakdown, citation-validation results, and final guardrail status.

### TC-07: Focused regression tests cover no-claim and qualifying paths

- Purpose: Verify the implementation includes executable focused coverage for malformed reports, missing guardrails/provenance, applicability, stage-invalid findings, no-claim, and qualifying-claim paths.
- Steps:
  1. Run the repository's focused M3 remediation test selection for report construction, paired comparison, taxonomy validation, and improvement selection.
  2. Confirm tests exercise both accepted and rejected fixtures rather than only happy paths.
  3. Record the focused command and complete output.
- Expected results:
  - All focused tests pass.
  - Test names or reports demonstrate coverage of malformed reports, missing/invalid guardrails and provenance, category applicability, stage-invalid findings, no-claim, and qualifying-claim paths.
  - This focused pass is not reported as a full-suite pass; the known PostgreSQL/psycopg migration baseline limitation remains explicitly tracked until separately resolved.
- Evidence to capture:
  - Focused test command, output, test count, and commit SHA under test.

This guide becomes immutable after human approval. Create `m3-remediation-issue-63-v2` for any semantic change to the requirements or expected behavior. Store run observations separately as JSONL Evaluation records.
