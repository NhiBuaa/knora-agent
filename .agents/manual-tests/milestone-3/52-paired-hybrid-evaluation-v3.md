# Manual Test Guide: M3.4 — Paired hybrid evaluation report and improvement record

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #52 — Paired hybrid evaluation report and improvement record
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/52
- Parent specification and testing decisions: https://github.com/NhiBuaa/knora-agent/issues/48
- Binding prerequisites: Issue #50 accepted dataset/corpus manifests; Issue #51 accepted
  production correlation seam; Issue #56 binding authority
- Taxonomy authority: `docs/standards/architecture.md:902-910`
- Supersedes: unapproved `issue-52-v1` and `issue-52-v2`; both remain unchanged and must not be
  executed
- Guide revision: issue-52-v3
- Approval status: approved and locked
- Approved by: repository owner (explicit user approval)
- Approved at: 2026-08-14T10:46:01.6448532+07:00

## Independent guide lifecycle and execution gate

This guide has two independent state machines:

1. **Approval/immutability.** While pending, the guide may be revised. The explicit human approval
   transition records the approver, approval time and guide digest and makes this exact revision
   immutable immediately. This transition does not wait for Issue #56 and is allowed while Issue
   #52 remains execution-blocked. After approval, any semantic change requires a new guide
   revision; the approved revision is never rewritten.
2. **Implementation/execution eligibility.** Issue #52 remains **BLOCKED** until both conditions
   below are read from the authoritative Issue #56 binding artifact and validated against its
   recorded digest:

   - `binding_prerequisite.issue_56.accepted` is exactly boolean `true`.
   - `binding_prerequisite.first_execution_allowed` is exactly boolean `true`.

The Issue #56 gate controls only permission to invoke `implement` and to execute a locked Test
Case/production Q&A run. It does not control when a human-approved guide becomes immutable.
Missing, false, stale, ambiguous, or inferred gate values fail closed. A closed GitHub issue, a
merged commit, a passing local test, or a report from another environment does not imply either
flag. While either flag is not true:

- do not invoke `implement`;
- do not execute any locked Test Case or production Q&A/evaluation run;
- do not create an Evaluation record claiming `PASSED`; and
- an already-approved guide remains immutable but execution-blocked.

The gate may be cleared only by an authoritative Issue #56 binding readback that records both
flags, its artifact digest, the binding environment revision, and the exact transition that made
the first execution eligible.

## Verified Issue #50 category contract

The accepted `m3-dataset-v1` contract was checked before this revision was authored:

- `Milestone3Case.category` is one scalar string, not a list or multi-label set.
- `QUALITY_CATEGORIES` is exactly `{lexical_exact_match, semantic_paraphrase, multi_source,
  insufficient_evidence_refusal}`; unknown values are rejected.
- Duplicate case IDs are rejected, and the released dataset has exactly 50 case IDs.
- Current membership sets are disjoint and partition the dataset: lexical exact-match 13,
  semantic paraphrase 13, multi-source 12 and insufficient-evidence/refusal 12.

Therefore TC-02 requires the current manifest's aggregate case count to equal the sum of these
four disjoint membership counts. It still does **not** infer metric denominators from category
counts: every metric/category section must reconcile only with its own membership set and that
metric's applicability/observation-failure subset. If a future immutable dataset manifest changes
to multi-label categories, the aggregate-sum oracle is disabled and each category reconciles only
with its declared membership set.

## Closed failure taxonomy contract

TC-03 uses only the following exact primary enum values from the versioned closed taxonomy. Fixture
descriptions are test labels and evidence, never taxonomy values, and no new synonym is accepted:

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

`FUSION_RANKING_ERROR` is valid only when gold evidence is present in the eligible branch union
but ranked incorrectly after fusion. `EVIDENCE_SELECTION_ERROR` is valid only after fusion when
relevant evidence is excluded by overlap, token budget or chunk-count selection. Provider,
observation and configuration failures must not be forced into retrieval enums.

## Prerequisites

- Environment: the dedicated Issue #52 worktree on branch
  `nhibuaa/issue-52-paired-hybrid-evaluation`, based on the recorded Milestone 3 integration
  head. PostgreSQL migrations are at head and the isolated production evaluation topology from
  Issue #51 is available only after the execution gate clears.
- Data and state: immutable `m3-dataset-v1` and `m3-corpus-v1` manifests; one sealed evaluation
  Workspace containing exactly the manifest-bound active corpus; and identical pinned chunking,
  embedding, generation and scorer settings for both runs. Only Retrieval Configuration differs.
- Runtime configurations: accepted Production Retrieval V2 configurations
  `retrieval-m3-vector-v2` and `retrieval-m3-rrf-v2`; accepted embedding/scorer policies; the
  source/evaluation commits; report schema version; and pre-declared improvement claim rule.
- Credentials and permissions: runtime-only evaluation/API/scorer credentials. Raw credentials,
  provider payloads, database identifiers and raw traces must not be written to committed
  artifacts, logs or reports.
- Boundary coverage: approval lifecycle, binding gate, exact case pairing, category membership,
  metric applicability, closed taxonomy, latency separation, claim conservatism, publication
  identity and artifact hygiene are included. UI, concurrency races and cross-tenant
  authorization are omitted because Issue #52 adds none of those behaviors.

## Locked Test Cases

### TC-01: Exact paired case identity, cardinality and provenance

- Purpose: Prove that vector-only and hybrid reports are paired over exactly the same cases and
  immutable inputs, with only Retrieval Configuration allowed to differ.
- Steps:
  1. Read the dataset manifest and derive `expected_case_ids` as the sorted set of declared case
     IDs. Record its exact cardinality `N`.
  2. After the Issue #56 execution gate clears, acquire the exclusive evaluation seal and run the
     accepted corpus-closure/preflight checks.
  3. Execute the complete dataset once with `retrieval-m3-vector-v2` and once with
     `retrieval-m3-rrf-v2` through the production Q&A endpoint and correlated trace reader.
  4. Generate one normalized report per configuration and a paired comparison from fresh,
     non-overwriting artifact paths.
  5. Inspect the pair key and every immutable provenance field in both reports.
- Expected results:
  - Each report contains exactly `N` case records; its sorted `case_ids` equals
    `expected_case_ids` after canonical serialization: no duplicate, missing, unexpected, or
    position-only pairing is accepted.
  - The pair contains exactly one vector record and one hybrid record for every `case_id`; the
    composite key `(case_id, retrieval_configuration_id)` is unique and has cardinality `2N`.
  - Both reports identify the same dataset/corpus/Chunk Set digests, Workspace, chunking,
    embedding, generation/scorer versions and report schema. Only Retrieval Configuration and its
    declared strategy/fusion policy may differ.
  - Semantic scorer prompt/policy/model and stochasticity are disclosed, or the scorer is
    explicitly marked deterministic/not run according to the selected mode.
  - Any case-set mismatch, duplicate, missing observation, invalid binding or mismatched pair
    rejects comparison and prevents a selected-improvement claim.
- Evidence to capture:
  - `expected_case_ids`, `N`, both sorted lists, duplicate/missing/extra checks and `2N` assertion.
  - Seal/closure and binding snapshots, redacted report metadata and normalized comparison.
  - Dataset/corpus/configuration digests and report schema version.

### TC-02: Category membership, metric numerator/denominator/applicability counts and guardrails

- Purpose: Prove that reports use the verified #50 category membership contract and expose
  auditable counts without conflating retrieval quality, answer guardrails, observation failures
  or latency domains.
- Steps:
  1. Derive each membership set `M_c = {case_id | dataset.case.category == c}` from the immutable
     manifest and record its exact sorted IDs and cardinality.
  2. Inspect aggregate and per-category results for the four exact categories and verify each
     category's `case_ids` equals its own `M_c` exactly.
  3. For every metric and category, record `applicable_count`, `inapplicable_count`,
     `observation_failure_count`, `numerator`, `denominator` and derived value.
  4. Verify Recall@8/MRR (and declared applicable hit/coverage metrics), citation correctness,
     refusal correctness and structural/observation guardrails for both configurations.
  5. Inspect retrieval versus end-to-end latency and verify valid insufficient-evidence refusals.
- Expected results:
  - For current `m3-dataset-v1`, the four membership sets are disjoint, partition all `N` cases,
    and their case counts sum to the aggregate case count. A future multi-label manifest must use
    only per-membership reconciliation and must not be forced through this sum.
  - Every category section reconciles only with its own `M_c`; metric denominators equal the
    applicable, provenance-valid, non-failed subset of that membership set. Inapplicable and
    observation-failure counts remain separate.
  - Each metric `numerator` equals the canonical sum of its per-case contributions, and its value
    is `numerator / denominator`, or explicit null at denominator zero. Aggregate metric counts
    reconcile independently; they are not obtained by blindly summing category denominators when
    applicability differs.
  - Retrieval latency excludes query embedding/generation; end-to-end latency is full
    request/response duration. Valid refusal is not a failure or retrieval miss.
- Evidence to capture:
  - Manifest-derived membership sets and exact counts.
  - Category/aggregate report sections with numerator/denominator arithmetic and applicability
    exclusions.
  - Per-case guardrails, refusal observations, latency samples and schema assertions.

### TC-03: Findings map deterministic fixtures to the closed taxonomy enums

- Purpose: Prove that findings use the versioned closed taxonomy exactly and never create ambiguous
  categories from prose descriptions.
- Steps:
  1. Load the twelve deterministic fixture IDs in the Closed failure taxonomy contract above.
  2. For each fixture, generate one finding and assert its `taxonomy_version`, exact `primary_enum`,
     optional contributing enums and evidence reference.
  3. Verify the branch/fusion/evidence-selection preconditions for the three retrieval-stage
     fixtures, especially eligible-union presence for fusion and post-fusion exclusion for
     evidence selection.
  4. Include `fixture-insufficient-evidence-correct` and attempt invalid-pair and
     observation-failure-only findings.
- Expected results:
  - Each fixture maps to exactly the required enum in the table; prose labels such as “branch
    miss” or “evidence-selection error” never appear as taxonomy values and cannot add a new enum.
  - `INSUFFICIENT_EVIDENCE_CORRECT` is explicitly non-failure.
  - Invalid pair/provenance uses `CORPUS_OR_CONFIGURATION_MISMATCH`; invalid observation uses
    `EVALUATION_OBSERVATION_FAILURE`; provider/infrastructure failures stay in their exact enums.
  - Each finding has one primary enum plus only valid contributing enums and enough evidence to
    audit classification without SQL, secrets or raw traces.
- Evidence to capture:
  - Closed taxonomy version, enum allowlist and fixture-to-enum mapping output.
  - Preconditions/evidence for each retrieval-stage fixture.
  - Non-failure refusal assertion and rejection output for invalid inputs.

### TC-04: Selected-improvement record follows the claim rule, including no-claim outcome

- Purpose: Prove that an improvement is selected only when the pre-declared claim rule and all
  guardrails are satisfied; valid paired evidence alone does not force a claim.
- Steps:
  1. Apply the pre-declared claim rule to a pair with a qualifying quality delta and passing
     citation/refusal guardrails.
  2. Record the selected improvement with exact pair identities, metric numerators/denominators,
     measured delta, guardrail impact, latency trade-offs and remaining regressions.
  3. Re-run normalization/comparison with identical pinned inputs and verify reproducibility apart
     from explicitly excluded wall-clock observations.
  4. Run the negative case: use fully valid paired evidence/provenance, but provide no delta that
     satisfies the claim rule or a required guardrail/trade-off bound.
  5. Repeat with an observation failure or mismatched provenance.
- Expected results:
  - A qualifying pair produces a selected record naming the claim rule, exact evidence, delta,
    guardrails, latency trade-offs and remaining regressions.
  - The valid-evidence/no-qualifying-delta case records explicit `NO_CLAIM`/not-claimed status,
    the failed rule or guardrail reason, and null/absent `selected_improvement`; it must not force
    a claim.
  - Repeated normalized reports preserve claim inputs; invalid provenance/observation blocks a
    claim and never upgrades an unobserved result.
- Evidence to capture:
  - Qualifying selected-improvement record and claim-rule version.
  - Negative no-claim record and absence assertion for `selected_improvement`.
  - Repeatability output and blocked-claim records.

### TC-05: Git provenance and artifact publication are non-self-referential and secret-safe

- Purpose: Prove that reports identify the code that produced/evaluated them without embedding a
  commit hash that can only be known after the report itself is committed.
- Steps:
  1. Before report generation, capture `source_commit` for the production endpoint and
     `evaluation_commit` for runner/scorer code. Each is a full immutable Git object ID from a
     clean checkout and neither is the future artifact publication commit.
  2. Generate reports/findings/improvement records and a canonical publication manifest. Define
     `artifact_publication_id` as SHA-256 of sorted artifact paths, content hashes and schema
     versions; exclude its own hash, publication commit and mutable timestamps.
  3. Commit the artifact set. Record `artifact_publication_commit` only in the external feature
     ledger/publication record, never by rewriting the committed report.
  4. Validate from the publication commit by recomputing every listed artifact hash and canonical
     publication-manifest digest; verify source/evaluation commits exist and are ancestors or
     explicitly declared immutable inputs.
  5. Scan committed artifacts/logs for keys, scorer credentials, provider payloads, raw traces and
     database-private identifiers.
- Expected results:
  - Reports use `source_commit` and `evaluation_commit`; no ambiguous `recorded_git_commit` field.
  - No report/finding/improvement contains `artifact_publication_commit` or self-references the
    commit containing that artifact.
  - `artifact_publication_id` depends only on canonical artifact bytes/paths/schema. The external
    publication record may bind it to a later commit without changing the ID.
  - Clean-checkout validation proves exact declared artifact membership and no self-referential
    hash/manifest entry; secret/payload scan is empty.
- Evidence to capture:
  - Pre-generation source/evaluation commit and clean-tree readback.
  - Publication manifest, publication ID, external publication record and post-commit validation.
  - Changed-file list, artifact digests and zero-match secret/payload scan.

This revision is approved and locked at the approval transition, even though the Issue #56 gate
remains false. Thereafter any semantic change requires `issue-52-v4` or later. The Issue #56 gate
still blocks implementation and execution. Record execution observations only in the separate
append-only Evaluation history at
`.agents/manual-tests/milestone-3/52-paired-hybrid-evaluation.evaluations.jsonl`.
