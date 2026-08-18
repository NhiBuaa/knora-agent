# M3 Improvement Claim Rule V1 — Revision Draft 3

## Candidate status and authority bundle

- Claim-rule authority identifier: `m3-improvement-claim-v1`
- Revision draft: `m3-improvement-claim-rule-v3`
- Human-readable authority path: `docs/design/m3-improvement-claim-rule-v3.md`
- Sole canonical machine-readable policy projection:
  `docs/design/m3-improvement-claim-rule-v1.policy.json`
- Current lifecycle state: **REVIEW-FROZEN DRAFT — not source-commit frozen and not effective**
- Approval payload path after explicit human approval:
  `.agents/review/m3-improvement-claim-v1-approval.json`
- Immutable approval seal archive after approval:
  `.agents/review/m3-improvement-claim-v1-approval-sealed-v1.tar`
- Approval closure result after approval:
  `.agents/review/m3-improvement-claim-v1-approval-closure-v1.json`
- `claim_rule_digest` is normative. It is the SHA-256 digest of the exact canonical Git blob bytes
  of the sole machine-readable policy projection at the attested source commit/blob.

The current candidate is frozen for review in the working tree only. It is not the lifecycle state
`FROZEN_CANDIDATE` because neither candidate path is present in a pinned source commit yet. The
candidate blob IDs and SHA-256 values are review-integrity evidence only; they do not establish
source-commit freeze, approval or effectiveness.

The Markdown document explains the policy and protocol. It is not a machine-readable input and
must not be parsed by production selection. The JSON projection is the only canonical semantic
projection. The current defaults in `evals/runners/milestone_3_comparison.py` are implementation
behavior, not authority.

## Existing repository contract reused

The repository has no standalone generic approval-ledger abstraction. This revision reuses the
existing Git-backed and sealed-evidence contract already used for Issue #56:

- `evals/calibration/validate_m3_retrieval_v1.py:_semantic_review` requires a strict review record
  with no extra keys, an independent reviewer, complete-population coverage, `PASS` verdict,
  empty derivation findings, a bound artifact digest, a bound review-bundle digest and a valid
  timestamp.
- `evals/test/test_m3_retrieval_calibration.py::test_independent_attestation_opens_first_execution_gate`
  opens the execution gate only after that exact attestation is read and its bound digests pass.
- `evals/calibration/close_issue_56_evidence.py:r9_proof` resolves an authority from an exact Git
  blob and checks its blob-byte SHA-256. Its `seal` flow creates a read-only archive with a
  `SEALED-MANIFEST.json`, revalidates every member hash, makes archive members read-only, and
  records a separate closure result with the sealed archive and manifest digests.
- The Issue #56 final closure record requires `status: PASS`, `aggregate_match_count: 0`, sealed
  manifest/archive digests and a candidate commit identity. The sealed archive includes the
  independent attestation, so a mutable working-tree JSON cannot open the gate.

The M3 claim-rule attestation below follows this existing pattern. It does not treat a mutable
working-tree JSON with `APPROVED_EFFECTIVE` as sufficient evidence.

## Deterministic Git-backed freeze, attestation and closure protocol

### Source-commit freeze

1. Create a candidate source commit containing both exact paths:
   `docs/design/m3-improvement-claim-rule-v3.md` and
   `docs/design/m3-improvement-claim-rule-v1.policy.json`.
2. Resolve each exact Git blob from that commit/path. The source blobs are Git objects returned by
   commit/path lookup; checkout file hashes are not accepted.
3. Read the blobs from Git's object store and compute SHA-256 over their exact blob bytes. Canonical
   bytes are repository Git blob bytes, with no platform checkout conversion, BOM insertion,
   newline rewrite or display formatting.
4. Record the source commit, document blob/hash and projection blob/hash in the approval payload.
   Only after these bindings are recorded does the external workflow move the candidate to
   `FROZEN_CANDIDATE`.

### Approval payload commit

The review approval payload is committed at the exact attestation path in a separate attestation
commit. The payload follows the existing strict independent-review schema and adds the authority
bundle bindings:

```json
{
  "schema_version": 1,
  "attestation_type": "m3-improvement-claim-authority-approval-v1",
  "authority_identifier": "m3-improvement-claim-v1",
  "claim_rule_version": "m3-improvement-claim-v1",
  "authority_document_path": "docs/design/m3-improvement-claim-rule-v3.md",
  "authority_document_blob": "<Git blob object ID>",
  "authority_document_sha256": "<SHA-256 of exact document blob bytes>",
  "policy_projection_path": "docs/design/m3-improvement-claim-rule-v1.policy.json",
  "policy_projection_blob": "<Git blob object ID>",
  "claim_rule_digest": "sha256:<SHA-256 of exact projection blob bytes>",
  "source_commit": "<full source commit object ID>",
  "reviewer_id": "<human identity>",
  "reviewer_was_author": false,
  "reviewed_complete_policy": true,
  "verdict": "PASS",
  "policy_mutation_findings": [],
  "reviewed_at": "<UTC RFC 3339 timestamp>",
  "attestation_status": "APPROVED_EFFECTIVE",
  "approved_by": "<human identity>",
  "approved_at": "<UTC RFC 3339 timestamp>"
}
```

`attestation_status: APPROVED_EFFECTIVE` is a field in the committed/reviewed payload, but it is not
authoritative by itself. The payload does not self-bind its own attestation commit, blob or digest;
those identity fields belong to the external seal and closure record. Therefore a mutable working-
tree JSON cannot self-authorize, even if it is edited to contain `APPROVED_EFFECTIVE`.

### Attestation commit/blob seal

After the payload commit is frozen, resolve:

```text
attestation_commit = the exact commit containing the approval payload path
attestation_blob = git ls-tree attestation_commit -- <approval payload path>
attestation_sha256 = SHA-256(git cat-file blob attestation_blob)
```

The attestation commit must be a descendant of the candidate source commit, contain the exact
approval payload path, and be resolved from Git objects. The payload's Git blob bytes are the only
attestation bytes. Checkout text, a working-tree path or a recomputed JSON serialization is not an
attestation identity.

Create the external approval seal using the exact Issue #56 sealed-evidence pattern. The
read-only archive at
`.agents/review/m3-improvement-claim-v1-approval-sealed-v1.tar` contains the authority source
archive, the approval payload, a canonical `authority-binding.json` member and
`SEALED-MANIFEST.json`. The manifest uses the existing Issue #56 fields exactly
(`schema_version`, `seal_id`, `candidate_sha`, `sealed_at` and sorted `items` containing
`reference`, `byte_count` and `sha256`), with sorted keys, compact separators and a final LF. The
`authority-binding.json` member carries the Git object identities that the manifest hashes:

```json
{
  "schema_version": 1,
  "authority_identifier": "m3-improvement-claim-v1",
  "claim_rule_version": "m3-improvement-claim-v1",
  "authority_source_commit": "<source commit>",
  "authority_document_path": "docs/design/m3-improvement-claim-rule-v3.md",
  "authority_document_blob": "<document blob>",
  "authority_document_sha256": "<document blob SHA-256>",
  "policy_projection_path": "docs/design/m3-improvement-claim-rule-v1.policy.json",
  "policy_projection_blob": "<projection blob>",
  "claim_rule_digest": "sha256:<projection blob SHA-256>",
  "attestation_path": ".agents/review/m3-improvement-claim-v1-approval.json",
  "attestation_commit": "<attestation commit>",
  "attestation_blob": "<attestation blob>",
  "attestation_sha256": "<attestation blob SHA-256>"
}
```

The manifest's `items` must include the authority source archive, approval payload and this
`authority-binding.json` member. Its member hashes are the only archive inventory; the binding
member is where the authority/document/projection/attestation Git IDs are bound.

The archive is written with read-only members and re-opened to revalidate the manifest and every
member hash. The separate closure result at
`.agents/review/m3-improvement-claim-v1-approval-closure-v1.json` is the sole non-recursively-
scanned result, matching the existing Issue #56 contract. It must contain:

```json
{
  "schema_version": 1,
  "seal_id": "m3-improvement-claim-v1-approval-seal-v1",
  "status": "PASS",
  "authority_source_commit": "<source commit>",
  "authority_document_path": "docs/design/m3-improvement-claim-rule-v3.md",
  "authority_document_blob": "<document blob>",
  "policy_projection_path": "docs/design/m3-improvement-claim-rule-v1.policy.json",
  "policy_projection_blob": "<projection blob>",
  "claim_rule_digest": "sha256:<projection blob SHA-256>",
  "attestation_path": ".agents/review/m3-improvement-claim-v1-approval.json",
  "attestation_commit": "<attestation commit>",
  "attestation_blob": "<attestation blob>",
  "attestation_sha256": "<attestation blob SHA-256>",
  "sealed_manifest_sha256": "<SEALED-MANIFEST.json SHA-256>",
  "sealed_archive_sha256": "<read-only archive SHA-256>",
  "closure_artifact_role": "sole-non-recursively-scanned-result"
}
```

The closure result is accepted only when its status, seal ID, candidate identities, manifest digest
and archive digest match the revalidated read-only archive. A working-tree change, a rewritten
approval JSON, a changed attestation commit/blob, a changed member, or a changed projection digest
makes the seal invalid.

The payload, `SEALED-MANIFEST.json` and closure result each use strict no-extra-key schemas; the
fields shown above are complete for this authority contract. The closure result is not a mutable
status switch: changing it without regenerating the exact sealed archive and its identity makes
canonical authority validation fail.

### Canonical authority validation

Before production selection accepts `APPROVED_EFFECTIVE`, it must verify all of the following from
Git objects and the external seal/closure record:

1. the source commit contains the exact document and projection paths;
2. the document and projection blobs match the recorded blob IDs and SHA-256 values;
3. `claim_rule_digest` equals the exact projection blob SHA-256;
4. the attestation commit contains the exact approval payload path;
5. `attestation_blob` and `attestation_sha256` match that Git object;
6. the payload has the strict schema, an explicit human approver, independent reviewer,
   complete-policy review, `PASS` verdict, `APPROVED_EFFECTIVE` status, empty mutation findings and
   valid timestamps;
7. the read-only seal archive revalidates `SEALED-MANIFEST.json` and every member hash;
8. the separate closure result binds all identities and has `status: PASS`; and
9. the canonical policy projection parses as strict JSON with the exact V1 shape below.

Missing, malformed, stale, unapproved or mismatched evidence returns
`AUTHORITY_VALIDATION_FAILURE`. A mutable working-tree copy is never consulted as an authority.

### Lifecycle states

The external workflow record uses:

```text
DRAFT -> REVIEW_FROZEN_DRAFT -> FROZEN_CANDIDATE -> APPROVED_EFFECTIVE -> SUPERSEDED
                                      \-> REJECTED
```

- `DRAFT`: candidate bytes may change; no source-commit freeze and no production selection.
- `REVIEW_FROZEN_DRAFT`: local review bytes are fixed for review, but the paths are not yet bound
  to a source commit/blob; production selection is forbidden.
- `FROZEN_CANDIDATE`: exact source commit/blob and hashes are recorded; bytes are frozen, but
  production selection remains forbidden until the sealed approval attestation passes.
- `APPROVED_EFFECTIVE`: the Git-backed payload, attestation seal and closure result all match; the
  exact authority bundle is immutable and canonical production selection may bind it.
- `SUPERSEDED`: a later approved authority replaces this one; all prior bytes and records remain
  immutable for historical reports.
- `REJECTED`: the candidate is not effective; its bytes remain unchanged for audit.

The current candidate is `REVIEW_FROZEN_DRAFT`, not `FROZEN_CANDIDATE`. Approval never edits the
authority document or projection to insert status or digest. Only the matching external seal and
closure record can make the authority effective.

## Canonical machine-readable policy projection

`docs/design/m3-improvement-claim-rule-v1.policy.json` is the sole canonical semantic projection.
It is strict JSON with `schema_version: 1`, no unknown top-level or nested-object fields, required
`null` values where the policy deliberately has no threshold, ordered arrays where order is
normative, and the exact V1 values. The Markdown document is explanatory only. Production must
bind `claim_rule_digest` to this projection's approved Git blob and enforce the parsed projection;
it must not parse arbitrary Markdown or infer missing values from implementation defaults. Missing,
malformed, extra or mutated projection fields fail authority validation.

The projection contains the exact metric, qualification, observation, guardrail, latency,
provenance, regression and override policy. The low-level focused-test seam uses the following
typed `ClaimRuleAuthority` shape after strict parsing of that projection. This is a type contract,
not a second policy block; the JSON file remains the sole canonical semantic projection:

```text
ClaimRuleAuthority(
  schema_version: 1,
  authority_identifier: "m3-improvement-claim-v1",
  claim_rule_version: "m3-improvement-claim-v1",
  metric_contract: "m3-retrieval-metrics-v1",
  recall_k: 8,
  primary_metric_set: {closed: true, ordered: ("recall_at_8", "mrr")},
  qualification: {
    delta_definition: "hybrid_minus_vector",
    all_non_regressing: {operator: ">=", threshold: "0"},
    any_strictly_improving: {operator: ">", threshold: "0"},
    epsilon: null,
    minimum_positive_delta: null
  },
  numeric_decision_representation: {
    kind: "reduced_rational",
    source: "metric_contract_numerators_and_denominators",
    serialization: "p/q",
    denominator: "positive_integer",
    comparison: "cross_multiply_signed_difference",
    binary_float: "forbidden",
    display_rounding: "non_authoritative"
  },
  observation_failure_requirement: {
    field: "observation_failure_count",
    required_zero: true,
    failure_is_inapplicable: false,
    failure_is_zero_quality: false,
    policy_outcome: "NO_CLAIM"
  },
  guardrail_requirement: {
    closed: true,
    required_keys: ("structural_validity", "citation_correctness", "refusal_correctness"),
    value_type: "boolean",
    all_values_must_be: true,
    unknown_keys: "reject",
    missing_keys: "reject",
    malformed_values: "reject"
  },
  latency_policy: {
    mode: "retain_and_disclose",
    required_observations: ("retrieval", "end_to_end"),
    hard_threshold: null
  },
  remaining_regressions: {required: true, empty_allowed: true},
  provenance: {
    required: true,
    equal_fields: (
      "dataset_version", "dataset_digest", "corpus_id", "corpus_digest",
      "chunk_set_id", "chunk_set_digest", "workspace", "chunking_configuration",
      "embedding_configuration", "generation_configuration", "scorer_configuration",
      "scorer_model", "scorer_prompt", "scorer_policy", "scorer_stochasticity",
      "metric_contract", "source_commit", "evaluation_commit",
      "report_artifact_schema_version"
    ),
    allowed_differences: (
      "retrieval_configuration_id", "strategy", "fusion_policy_id",
      "fusion_policy_version", "lexical_policy_id", "fts_candidate_k"
    ),
    all_other_differences: "reject",
    missing_or_malformed: "reject"
  },
  override_policy: {
    production: "forbidden",
    caller_override: "reject",
    runtime_override: "reject",
    projection_source: "approved_git_blob_only",
    focused_tests: "explicit_authority_fixture_only"
  },
  claim_scope: "retrieval_quality_improvement_only"
)
```

`provenance.equal_fields` is the exact immutable set in the projection:
`dataset_version`, `dataset_digest`, `corpus_id`, `corpus_digest`, `chunk_set_id`,
`chunk_set_digest`, `workspace`, `chunking_configuration`, `embedding_configuration`,
`generation_configuration`, `scorer_configuration`, `scorer_model`, `scorer_prompt`,
`scorer_policy`, `scorer_stochasticity`, `metric_contract`, `source_commit`, `evaluation_commit`,
and `report_artifact_schema_version`. The six configuration-specific fields listed above are the
only allowed pair differences. The exact machine-readable bytes are in the companion projection
file. No second normative policy block may be introduced in another artifact without a new
authority revision.

## Purpose and claim scope

The rule decides whether one valid vector-only versus hybrid M3 report pair supports a retrieval-
quality improvement claim. It is evaluated only after the pair passes comparable-provenance,
observation, report-schema, guardrail and metric-validity gates.

`SELECTED` means **retrieval-quality improvement under `m3-improvement-claim-v1`**. It does not
mean overall-system improvement, production readiness, safety approval or a deployment
recommendation. Latency is disclosed and retained, but V1 defines no hard latency gate. A separate
authority is required for any overall-system or deployment claim.

## Policy V1 semantics

The policy values remain unchanged from prior authority drafts:

- `metric_contract = m3-retrieval-metrics-v1` and `recall_k = 8`;
- ordered closed primary metrics are `recall_at_8`, `mrr`;
- zero observation failures are required;
- the closed guardrail set is exactly `structural_validity`, `citation_correctness`,
  `refusal_correctness`, and all three must be explicit `true`;
- qualification is `all primary deltas >= 0 && any primary delta > 0`;
- no epsilon, rounding tolerance or arbitrary minimum positive delta exists;
- latency trade-offs are retained and disclosed without a hard threshold; and
- `remaining_regressions` is mandatory, including an explicit empty collection when applicable.

### Exact numeric decision representation

The metric contract defines Recall@8 as `|G ∩ top_8| / |G|` for each applicable successful case,
and MRR as `1 / r` for the first gold rank `r`, or `0` for a valid no-hit case. Aggregate values
are arithmetic macro-means over successful applicable cases. Refusal/inapplicable cases and
observation failures do not enter quality denominators.

The selector uses exact reduced rationals from those case contributions:

- Recall@8 contribution: `hit_count / gold_count`;
- MRR contribution: `1 / rank`, or `0 / 1`;
- aggregate: exact arithmetic mean serialized as reduced `p/q`;
- delta sign: exact cross-product `p_h*q_v - p_v*q_h`.

Report display fields `recall_at_8`, `mrr` and `metric_deltas` are not decision oracles. Policy
artifacts retain exact `metric_decision_values` and `metric_decision_deltas`. If exact metric
representation is unavailable, metric validation fails closed after authority validation.

## Decision outcomes and failure separation

### Authority-validation failure

The canonical selector returns a separate control-plane `AUTHORITY_VALIDATION_FAILURE` and does not
emit policy-based `SELECTED` or `NO_CLAIM` when:

- authority source commit/blob or projection is missing;
- the Git-backed approval payload, attestation commit/blob/hash, read-only seal archive or sealed
  closure is missing;
- the attestation is not independently reviewed, complete, `PASS`, explicitly approved or validly
  timestamped;
- source commit, source blob, path, projection blob or `claim_rule_digest` mismatches;
- the projection is missing, malformed, mutated or has unknown fields;
- a required policy field is missing or malformed; or
- a caller/runtime policy mutation or override is supplied.

This is not a quality result. It is not zero, inapplicable, an observation failure or policy
`NO_CLAIM`. No selected or policy no-claim artifact is published from this path.

### Selected improvement

After authority validation succeeds, the selector emits `SELECTED` only when all policy gates pass
and the exact qualification rule holds. The artifact retains `claim_rule_version`,
`claim_rule_digest`, comparable provenance, reporting and exact decision deltas, all guardrails,
latency trade-offs and `remaining_regressions`.

### Policy no claim

After authority validation succeeds, the selector emits `NO_CLAIM` with
`selected_improvement: null` when provenance, observation, guardrail or metric validation fails, or
when qualification does not hold. The artifact retains `claim_rule_version`, `claim_rule_digest`,
exact decision values/deltas where available, the policy reason and relevant audit evidence.

## Production binding and focused-test seam

### Canonical production binding

The canonical M3 production entry point binds the approved projection by exact identifier, source
commit/blob and `claim_rule_digest`, then verifies the Git-backed attestation seal and closure
result, including the immutable `attestation_commit`, `attestation_blob` and attestation SHA-256.
It does not parse Markdown and exposes no arbitrary runtime or caller `claim_rule` override. Any
mismatch, mutation, missing field, invalid seal/closure, or override returns
`AUTHORITY_VALIDATION_FAILURE`.

### Focused-test seam

A low-level pure selector may accept an explicit `ClaimRuleAuthority` fixture matching the canonical
projection shape. Focused tests may use this fixture to exercise exact rational boundaries,
authority failures, policy mutations and policy no-claim paths. The fixture is test input, not
production authority. Production cannot receive this override capability.

## Required external-review evidence

Before this revision can become `FROZEN_CANDIDATE` or receive approval, external review must verify:

1. the exact Issue #56 Git-backed/sealed-attestation contract is reused: the approval payload is
   committed after explicit human approval, its `attestation_commit`/`attestation_blob`/SHA-256 are
   sealed, and no mutable working-tree JSON can self-authorize;
2. source-commit freeze resolves both exact candidate blobs and canonical blob-byte SHA-256 values;
3. the read-only approval archive and separate `status: PASS` closure result revalidate the manifest,
   every member hash and the attestation identity before `APPROVED_EFFECTIVE` is accepted;
4. the companion JSON is the sole canonical policy projection and has strict no-unknown-field
   validation at every object level;
5. `ClaimRuleAuthority` matches the projection exactly, including the six allowed provenance
   differences and the closed projection shape;
6. `recall_at_8`, `mrr`, exact rational comparison, zero failures, closed all-true guardrails,
   `all deltas >= 0 && any delta > 0`, latency disclosure and claim scope are unchanged;
7. authority-validation failure is separate from policy `NO_CLAIM`;
8. `claim_rule_version`, normative `claim_rule_digest`, exact decision deltas and remaining regressions are
   retained; and
9. production binding rejects Markdown parsing and arbitrary policy overrides while focused tests
   can use an explicit authority fixture.

Until external review and explicit human approval are complete, this revision and its projection
are review-frozen drafts. They do not authorize implementation, production selection, manual
execution or Evaluation recording.
