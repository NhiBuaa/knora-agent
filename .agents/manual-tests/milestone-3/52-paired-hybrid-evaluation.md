# Manual Test Guide: M3.4 — Paired hybrid evaluation report and improvement record

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #52 — Paired hybrid evaluation report and improvement record
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/52
- Parent specification and testing decisions: https://github.com/NhiBuaa/knora-agent/issues/48
- Binding prerequisites: Issue #50 accepted dataset/corpus manifests; Issue #51 accepted
  production correlation seam; Issue #56 accepted Production Retrieval V2 authority
- Guide revision: issue-52-v1
- Approval status: pending human approval
- Approved by: pending
- Approved at: pending

## Prerequisites

- Environment: the dedicated Issue #52 worktree on branch
  `nhibuaa/issue-52-paired-hybrid-evaluation`, based on the recorded Milestone 3 integration
  head. PostgreSQL migrations are at head and the isolated production evaluation topology from
  Issue #51 is available.
- Data and state: the immutable `m3-dataset-v1` dataset manifest and `m3-corpus-v1` corpus/Chunk
  Set manifest; one sealed evaluation Workspace containing exactly the manifest-bound active
  corpus; the same pinned chunking, embedding, generation and scorer configuration for both runs.
  The paired runs differ only in Retrieval Configuration: vector-only versus hybrid.
- Runtime configurations: the accepted Production Retrieval V2 configurations
  `retrieval-m3-vector-v2` and `retrieval-m3-rrf-v2`; the accepted embedding configuration and
  scorer policy; the current implementation Git commit; report schema version; and the declared
  claim rule for selecting an improvement.
- Credentials and permissions: runtime-only evaluation/API/scorer credentials. Raw credentials,
  provider payloads, database identifiers and raw traces must not be written to committed
  artifacts, logs or reports.
- Boundary coverage: data/provenance, state/seal, ordering/metric bounds, failure taxonomy,
  latency separation and artifact hygiene are included. UI, concurrency races and cross-tenant
  authorization are omitted because Issue #52 has no UI or new authorization behavior and those
  contracts are already owned by Issues #48–#51.

## Locked Test Cases

### TC-01: Paired runs preserve identical inputs and reproducible provenance

- Purpose: Prove that vector-only and hybrid reports are paired over identical dataset, immutable
  corpus/Chunk Set, Workspace, chunking, embedding, generation and scorer inputs, with only the
  Retrieval Configuration differing.
- Steps:
  1. Acquire the exclusive evaluation seal and run the accepted corpus-closure/preflight checks.
  2. Execute the complete versioned dataset once with `retrieval-m3-vector-v2` and once with
     `retrieval-m3-rrf-v2` through the production Q&A endpoint and correlated trace reader.
  3. Generate the normalized vector-only report, normalized hybrid report and paired comparison
     from fresh, non-overwriting artifact paths.
  4. Inspect each report's immutable metadata and compare every paired input identity.
- Expected results:
  - Both reports identify the same dataset version and digest, corpus/Chunk Set version and
    digest, Workspace, chunking configuration, embedding configuration, generation/scorer
    versions, Git commit and report schema version.
  - The only intentional paired-input difference is the Retrieval Configuration identity and its
    declared strategy/fusion policy; no report mixes corpus, embedding or scorer provenance.
  - The report discloses semantic scorer prompt/policy/model and stochasticity, or explicitly marks
    the scorer as deterministic/not run according to the selected mode.
  - A missing, mismatched, or invalid paired provenance prevents comparison and prevents any
    selected-improvement claim.
- Evidence to capture:
  - Seal/closure and binding snapshot references for both runs.
  - Redacted report metadata and normalized comparison output.
  - Dataset/corpus manifest versions and SHA-256 digests; Git commit; retrieval configuration
    identities; report schema version.

### TC-02: Reports expose quality breakdowns, citation/refusal guardrails and separate latency

- Purpose: Prove that the comparison reports aggregate and break down quality without conflating
  retrieval quality, public-answer guardrails, observation failures or latency domains.
- Steps:
  1. Inspect aggregate and per-case results for lexical/exact-match, semantic/paraphrase,
     multi-source and insufficient-evidence/refusal categories.
  2. Verify Recall@8/MRR (and any declared applicable hit/coverage metrics), citation correctness,
     refusal correctness and structural/observation guardrail outcomes for both configurations.
  3. Inspect per-observation retrieval latency and end-to-end latency fields and their labels;
     compare no aggregate latency statistic that merges the two domains.
  4. Confirm that valid insufficient-evidence refusals are represented as correct refusals and are
     not converted into retrieval failures or zero-quality claims.
- Expected results:
  - Aggregate and category breakdowns report the applicable retrieval metrics, citation/refusal
    guardrails and observation-failure counts for both paired configurations.
  - Retrieval latency excludes query embedding and generation; end-to-end latency is the complete
    request/response duration. They remain separately labelled in reports and comparisons.
  - A valid refusal is not a failure finding merely because it has no retrieved evidence.
  - Observation failures are visible and excluded from quality denominators according to the
    declared metric contract; they cannot silently become misses.
- Evidence to capture:
  - Redacted normalized report sections for aggregate and every required category.
  - Per-case metric/guardrail projections and refusal observations.
  - Independent latency field samples and report schema assertions.

### TC-03: Findings use stage-correct primary and contributing failure categories

- Purpose: Prove that findings distinguish retrieval, answer/evidence, configuration, provider,
  infrastructure and observation causes instead of inferring a cause from a metric delta.
- Steps:
  1. Exercise or load deterministic fixtures representing a branch miss, fusion-ranking error,
     evidence-selection error, citation/refusal error, configuration/provenance error, provider
     error, infrastructure error and observation failure.
  2. Generate findings for the paired reports and inspect each finding's primary category,
     optional contributing categories, case identity and evidence references.
  3. Include a correct insufficient-evidence refusal and verify its classification independently.
  4. Attempt to create a finding from an invalid pair or an observation-failure-only run.
- Expected results:
  - Each finding has one stage-correct primary category and only applicable contributing
    categories from the versioned taxonomy; branch misses are not labelled fusion errors and
    citation/refusal failures are not labelled retrieval misses.
  - Correct insufficient-evidence refusal is explicitly non-failure.
  - Invalid paired provenance or observation failures produce no quality finding/claim and remain
    explicit configuration or observation failures.
  - Findings retain enough case/report evidence to audit the classification without exposing SQL,
    provider secrets or raw traces.
- Evidence to capture:
  - Versioned taxonomy/schema and finding records for every category.
  - Fixture-to-finding mapping and refusal non-failure assertion.
  - Rejection output for invalid pair and observation-failure inputs.

### TC-04: Selected-improvement record follows the pre-declared claim rule

- Purpose: Prove that one selected improvement is evidence-backed, preserves trade-offs and
  remaining regressions, and makes no claim when paired evidence is invalid.
- Steps:
  1. Apply the pre-declared claim rule to the paired vector-only and hybrid reports.
  2. Select the improvement supported by the observed delta and record the baseline/hybrid
     metrics, citation/refusal guardrails, retrieval and end-to-end latency trade-offs, and all
     remaining regressions.
  3. Re-run report normalization/comparison with the same pinned inputs and verify the selected
     record remains reproducible apart from explicitly excluded wall-clock observations.
  4. Repeat selection with an injected observation failure or mismatched provenance.
- Expected results:
  - The selected record names the exact paired reports/configurations, claim rule, measured delta,
    guardrail impact, latency trade-offs and remaining regressions.
  - Repeated normalized reports preserve all claim inputs and findings; only declared wall-clock
    observations may differ.
  - Observation failures or invalid paired provenance block the claim and are recorded as such;
    the record never upgrades an unobserved result into an improvement.
- Evidence to capture:
  - Selected-improvement record and claim-rule version.
  - Normalized report comparison and repeatability output.
  - Blocked-claim record for invalid provenance/observation fixtures.

### TC-05: Committed artifacts are reproducible and secret-safe

- Purpose: Prove that the release artifacts contain the manifests, normalized reports, findings and
  selected-improvement record required by Issue #52, while excluding raw traces and secrets.
- Steps:
  1. Inspect the changed-file set and artifact manifest produced by the Issue #52 workflow.
  2. Verify each committed report/finding/improvement artifact references immutable manifests and
     schema versions and can be validated from a clean checkout at the recorded Git commit.
  3. Search committed artifacts and generated logs for raw API keys, scorer credentials, provider
     payloads, raw traces and database-private identifiers.
  4. Re-run the artifact validators and report normalization from the clean checkout.
- Expected results:
  - Dataset/corpus manifests, normalized vector-only and hybrid reports, versioned findings and
    the selected-improvement record are committed and validate successfully.
  - Raw traces, provider payloads, secrets and database-private identifiers are absent from the
    committed artifact set.
  - Artifact validation is deterministic at the recorded commit and report writers do not replace
    an existing evidence file.
- Evidence to capture:
  - Final changed-file list and artifact manifest/digests.
  - Clean-checkout validation output and report schema checks.
  - Secret/payload scan summary with zero credential matches.

This guide remains pending human approval. Once approved, it becomes immutable; any semantic
change requires a new guide revision. Record all execution observations in the separate append-only
Evaluation history at `.agents/manual-tests/milestone-3/52-paired-hybrid-evaluation.evaluations.jsonl`.
