# Manual Test Guide: M3.4 — Paired hybrid evaluation report and improvement record

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #52 — Paired hybrid evaluation report and improvement record
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/52
- Parent specification and testing decisions: https://github.com/NhiBuaa/knora-agent/issues/48
- Binding prerequisites: Issue #50 accepted dataset/corpus manifests; Issue #51 accepted
  production correlation seam; Issue #56 binding authority
- Supersedes: unapproved `issue-52-v1`; v1 remains unchanged and must not be executed
- Guide revision: issue-52-v2
- Approval status: pending human approval
- Approved by: pending
- Approved at: pending

## Mandatory implementation and execution gate

Issue #52 is **BLOCKED** until both conditions below are read from the authoritative Issue #56
binding artifact and validated against its recorded digest:

1. `binding_prerequisite.issue_56.accepted` is exactly boolean `true`.
2. `binding_prerequisite.first_execution_allowed` is exactly boolean `true`.

Missing, false, stale, ambiguous, or inferred values fail closed. A closed GitHub issue, a merged
commit, a passing local test, or a report generated from another environment does not imply either
flag. While either flag is not true:

- do not invoke `implement`;
- do not execute any locked Test Case or production Q&A/evaluation run;
- do not create an Evaluation record claiming `PASSED`; and
- retain this guide as pending approval/blocked.

The gate may be cleared only by an authoritative Issue #56 binding readback that records both
flags, its artifact digest, the binding environment revision, and the exact transition that made
the first execution eligible.

## Prerequisites

- Environment: the dedicated Issue #52 worktree on branch
  `nhibuaa/issue-52-paired-hybrid-evaluation`, based on the recorded Milestone 3 integration
  head. PostgreSQL migrations are at head and the isolated production evaluation topology from
  Issue #51 is available only after the mandatory gate clears.
- Data and state: the immutable `m3-dataset-v1` dataset manifest and `m3-corpus-v1` corpus/Chunk
  Set manifest; one sealed evaluation Workspace containing exactly the manifest-bound active
  corpus; the same pinned chunking, embedding, generation and scorer configuration for both runs.
  The paired runs differ only in Retrieval Configuration.
- Runtime configurations: the accepted Production Retrieval V2 configurations
  `retrieval-m3-vector-v2` and `retrieval-m3-rrf-v2`; the accepted embedding configuration and
  scorer policy; the current implementation Git commit; report schema version; and the declared
  claim rule for selecting an improvement.
- Credentials and permissions: runtime-only evaluation/API/scorer credentials. Raw credentials,
  provider payloads, database identifiers and raw traces must not be written to committed
  artifacts, logs or reports.
- Boundary coverage: data/provenance, state/seal, exact case pairing, ordering/metric bounds,
  failure taxonomy, latency separation, claim conservatism, publication identity and artifact
  hygiene are included. UI, concurrency races and cross-tenant authorization are omitted because
  Issue #52 has no UI or new authorization behavior and those contracts are owned by Issues
  #48–#51.

## Locked Test Cases

### TC-01: Exact paired case identity, cardinality and provenance

- Purpose: Prove that vector-only and hybrid reports are paired over exactly the same cases and
  immutable inputs, with only Retrieval Configuration allowed to differ.
- Steps:
  1. Read the dataset manifest and derive `expected_case_ids` as the sorted set of declared case
     IDs. Record its exact cardinality `N`.
  2. After the mandatory Issue #56 gate clears, acquire the exclusive evaluation seal and run the
     accepted corpus-closure/preflight checks.
  3. Execute the complete dataset once with `retrieval-m3-vector-v2` and once with
     `retrieval-m3-rrf-v2` through the production Q&A endpoint and correlated trace reader.
  4. Generate one normalized report per configuration and a paired comparison from fresh,
     non-overwriting artifact paths.
  5. Inspect the pair key and every immutable provenance field in both reports.
- Expected results:
  - Each report contains exactly `N` case records; its sorted `case_ids` equals
    `expected_case_ids` byte-for-byte after canonical serialization: no duplicate, missing,
    unexpected, or position-only pairing is accepted.
  - The pair contains exactly one vector record and one hybrid record for every `case_id`; the
    composite key `(case_id, retrieval_configuration_id)` is unique and has cardinality `2N`.
  - Both reports identify the same dataset version/digest, corpus/Chunk Set version/digest,
    Workspace, chunking configuration, embedding configuration, generation/scorer versions and
    report schema version. Only the Retrieval Configuration and its declared strategy/fusion
    policy may differ.
  - The report discloses semantic scorer prompt/policy/model and stochasticity, or explicitly
    marks the scorer as deterministic/not run according to the selected mode.
  - Any case-set mismatch, duplicate, missing observation, invalid binding, or mismatched paired
    provenance rejects the comparison and prevents any selected-improvement claim.
- Evidence to capture:
  - `expected_case_ids`, `N`, both sorted case-id lists, duplicate/missing/extra checks and pair
    cardinality assertion.
  - Seal/closure and binding snapshot references for both runs.
  - Redacted report metadata, normalized comparison output and all manifest/configuration digests.

### TC-02: Metric numerator/denominator/applicability counts and guardrails

- Purpose: Prove that reports expose auditable counts and do not conflate retrieval quality,
  public-answer guardrails, observation failures or latency domains.
- Steps:
  1. Inspect aggregate and per-category results for lexical/exact-match, semantic/paraphrase,
     multi-source and insufficient-evidence/refusal cases.
  2. For every metric and category, record `applicable_count`, `inapplicable_count`,
     `observation_failure_count`, `numerator`, `denominator` and the derived metric value.
  3. Verify Recall@8/MRR (and any declared applicable hit/coverage metrics), citation correctness,
     refusal correctness and structural/observation guardrail outcomes for both configurations.
  4. Inspect per-observation retrieval latency and end-to-end latency fields and their labels.
  5. Confirm that valid insufficient-evidence refusals are represented as correct refusals and are
     not converted into retrieval failures or zero-quality claims.
- Expected results:
  - For each metric, `denominator` equals the count of applicable, provenance-valid, non-failed
    observations; `inapplicable_count` and `observation_failure_count` are reported separately
    and never silently enter that denominator.
  - `numerator` equals the canonical sum of per-case metric contributions (including fractional
    Recall@8/MRR contributions); the reported value is `numerator / denominator`, or explicit
    null when the denominator is zero. Category counts reconcile exactly to aggregate counts.
  - Aggregate and category breakdowns include citation/refusal guardrails and observation-failure
    counts for both paired configurations.
  - Retrieval latency excludes query embedding and generation; end-to-end latency is the complete
    request/response duration. The two remain separately labelled and are never merged into one
    quality or latency claim.
  - A valid refusal is not a failure finding merely because it has no retrieved evidence.
- Evidence to capture:
  - Redacted normalized report sections with exact case/category counts and numerator/denominator
    arithmetic.
  - Per-case metric, guardrail and refusal projections.
  - Independent latency field samples and report schema assertions.

### TC-03: Findings use stage-correct primary and contributing categories

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

### TC-04: Selected-improvement record follows the claim rule, including no-claim outcome

- Purpose: Prove that an improvement is selected only when the pre-declared claim rule and all
  guardrails are satisfied; valid paired evidence alone does not force a claim.
- Steps:
  1. Apply the pre-declared claim rule to a paired vector-only/hybrid result with a qualifying
     quality delta and passing citation/refusal guardrails.
  2. Record the selected improvement with exact paired report/configuration identities, metric
     numerators/denominators, measured delta, guardrail impact, retrieval/end-to-end latency
     trade-offs and remaining regressions.
  3. Re-run normalization/comparison with the same pinned inputs and verify the selected record
     remains reproducible apart from explicitly excluded wall-clock observations.
  4. Run the negative case: use fully valid paired evidence and provenance, but construct a pair
     where no delta satisfies the pre-declared claim rule or a required guardrail/trade-off bound.
  5. Repeat with an observation failure or mismatched provenance.
- Expected results:
  - A qualifying pair produces a selected record that names the claim rule, exact evidence,
    measured delta, guardrail impact, latency trade-offs and remaining regressions.
  - In the negative case, the workflow records an explicit `NO_CLAIM`/not-claimed outcome with
    the failed rule or guardrail reason and `selected_improvement` is null/absent. It must not
    manufacture, weaken or choose a claim merely because the paired evidence is valid.
  - Repeated normalized reports preserve all claim inputs and findings; only declared wall-clock
    observations may differ.
  - Observation failures or invalid paired provenance block the claim and remain explicit; they
    never upgrade an unobserved result into an improvement.
- Evidence to capture:
  - Selected-improvement record and claim-rule version for the qualifying pair.
  - Negative no-claim record, rule/guardrail evaluation and absence assertion for
    `selected_improvement`.
  - Normalized repeatability output and blocked-claim records for invalid inputs.

### TC-05: Git provenance and artifact publication are non-self-referential and secret-safe

- Purpose: Prove that reports identify the code that produced/evaluated them without embedding a
  commit hash that can only be known after the report itself is committed.
- Steps:
  1. Before generating reports, capture two explicit provenance values: `source_commit` for the
     production application/evaluation endpoint and `evaluation_commit` for the runner/scorer
     code. Each is a full immutable Git object ID from a clean checkout and neither is the future
     artifact publication commit.
  2. Generate reports/findings/improvement records and a canonical publication manifest. Define
     `artifact_publication_id` as the SHA-256 of the canonical manifest payload containing sorted
     artifact paths, content hashes and schema versions; the manifest excludes its own hash,
     publication commit and mutable timestamps.
  3. Commit the artifact set. Record the resulting `artifact_publication_commit` only in the
     external feature ledger/publication record, never by rewriting the already-committed report.
  4. Validate the publication by checking out the recorded publication commit, recomputing every
     listed artifact hash and the canonical publication-manifest digest, and checking that the
     report's source/evaluation commits exist and are ancestors or explicitly declared immutable
     inputs for that publication.
  5. Inspect the committed artifact set and generated logs for raw API keys, scorer credentials,
     provider payloads, raw traces and database-private identifiers.
- Expected results:
  - Reports use unambiguous `source_commit` and `evaluation_commit` fields; a generic
    `recorded_git_commit` field is not used for publication identity.
  - No report, finding or improvement record contains `artifact_publication_commit` or otherwise
    self-references the commit that contains that same artifact.
  - `artifact_publication_id` validates from canonical artifact paths/content hashes/schema
    versions alone. The external publication record may bind it to `artifact_publication_commit`
    after commit; changing commit metadata without changing listed artifact bytes does not change
    the publication ID.
  - Clean-checkout validation proves the publication commit contains exactly the declared
    artifacts, the recorded source/evaluation commits are reproducible, and no artifact hash or
    manifest entry is self-referential.
  - Raw traces, provider payloads, secrets and database-private identifiers are absent from the
    committed artifact set.
- Evidence to capture:
  - Pre-generation source/evaluation commit readback and clean-tree evidence.
  - Canonical publication manifest, `artifact_publication_id`, external publication record and
    post-commit validation output.
  - Final changed-file list, artifact digests and secret/payload scan summary with zero matches.

This guide revision remains pending human approval and the Issue #56 gate remains closed. Once
approved and once both mandatory binding flags are true, this revision becomes immutable; any
semantic change requires a new guide revision. Record all execution observations in the separate
append-only Evaluation history at
`.agents/manual-tests/milestone-3/52-paired-hybrid-evaluation.evaluations.jsonl`.
