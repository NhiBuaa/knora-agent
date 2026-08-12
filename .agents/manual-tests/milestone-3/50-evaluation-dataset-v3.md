# Manual Test Guide: M3.3 — Versioned evaluation dataset and gold judgments

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #50 — Versioned evaluation dataset and gold judgments
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/50
- Design decisions: https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261026759
- Guide revision: issue-50-v3
- Approval status: approved and locked
- Approved by: NhiBuaa
- Approved at: 2026-08-12 (Codex task approval)

## Prerequisites

- Environment: the dedicated Issue #50 worktree on branch `nhibuaa/issue-50-evaluation-dataset`.
- Data and state: a version-controlled evaluation corpus and its immutable corpus/Chunk Set
  manifest, plus the version-controlled dataset and its immutable digest manifest.
- Credentials and permissions: no production credentials or production data.  The evaluation
  Workspaces are fixture-only and must use scoped test credentials when an HTTP seam is exercised.

## Locked Test Cases

### TC-01: Versioned dataset has complete M3 case semantics and separated gold judgments

- Purpose: Prove the dataset contains 50–100 uniquely identified cases and all approved quality
  categories: lexical/exact-match, semantic/paraphrase, multi-source, and
  insufficient-evidence/refusal. Prove that retrieval gold relevance semantics are distinct from
  answer/evidence expectations.
- Steps:
  1. Load the released dataset through its public evaluation-dataset seam.
  2. Inspect every case's expected behavior, Workspace, source-document expectations, acceptable
     relevant Chunk set, and (for answerable cases) required facts.
  3. Inspect insufficient-evidence cases for an explicit refusal expectation and inspect the
     dataset's retrieval-gold fields separately from answer/reference and citation/evidence fields.
  4. Verify a case may name multiple acceptable relevant Chunks, while each gold reference still
     resolves deterministically to a pinned corpus/Chunk Set artifact.
- Expected results:
  - The dataset validates only with 50–100 unique cases and at least one case in every approved
    quality category; no security or Cross-Workspace category is present.
  - Every case has an expected behavior and Workspace. Answerable cases have source-document
    expectations, a non-empty set of acceptable relevant Chunks for retrieval relevance, and
    non-empty required facts. The validator rejects every answerable case with missing or empty
    required facts. Insufficient-evidence cases have an explicit refusal expectation and do not
    require required facts.
  - The dataset explicitly marks retrieval-relevance applicability and its gold relevance set,
    separately from answer/reference and citation/evidence expectations, so downstream consumers
    do not need to infer whether retrieval relevance applies. These are not collapsed into one
    gold-reference contract; this test does not execute or score retrieval metrics.
  - Multiple acceptable relevant Chunks are valid. “Ambiguous” applies only when a reference does
    not resolve uniquely to a pinned artifact, not when a case has more than one acceptable Chunk.
  - Refusal cases are represented with refusal semantics that a consumer cannot silently treat as a
    retrieval miss or as zero Recall/MRR.
- Evidence to capture:
  - Focused test command and result.
  - Dataset manifest version and SHA-256.
  - Category/count and per-field semantic assertion output.

### TC-02: Dataset and gold-reference validation rejects invalid contracts before a run

- Purpose: Prove malformed, duplicate, ambiguous, incompatible, or unknown relevance/evidence
  references fail before evaluation execution.
- Steps:
  1. Exercise the validator with missing required fields, duplicate case identifiers, unknown
     categories/behavior, and invalid case counts.
  2. Exercise it with missing or empty required facts on answerable cases, empty or ambiguous
     answerable evidence judgments, and Chunk references absent from the pinned corpus/Chunk Set
     manifest.
- Expected results:
  - Every invalid fixture fails with a stable, actionable validation error before a run/report is
    started.
  - “Ambiguous” is rejected only when a gold reference cannot resolve uniquely to a pinned artifact;
    a case with multiple acceptable relevant Chunks remains valid.
  - No invalid relevance or evidence reference is silently accepted or scored as a retrieval miss.
- Evidence to capture:
  - Focused test command and result.
  - Assertions showing each rejection reason.

### TC-03: Immutable dataset and corpus/Chunk Set manifests bind compatible released inputs

- Purpose: Prove the dataset and corpus/Chunk Set manifests accept only compatible released inputs
  with immutable digest provenance.
- Steps:
  1. Load the valid dataset manifest and corpus/Chunk Set manifest, then validate gold references
     against the manifest.
  2. Mutate dataset bytes, corpus source/checksum, manifest identity, or Chunk Set provenance in
     isolated fixtures.
- Expected results:
  - The valid released artifacts load with their pinned versions and digests.
  - Every mutation is rejected and reports the incompatible artifact.
  - A successful validation exposes sufficient immutable provenance to reproduce the dataset/corpus
    pairing.
- Evidence to capture:
  - Focused test command and result.
  - Released manifest contents and computed digests.
  - Rejection assertions for each incompatible fixture.

### TC-04: Cross-Workspace isolation remains a separate security contract

- Purpose: Prove security isolation is pass/fail behavior and is not part of the dataset quality
  taxonomy.
- Steps:
  1. Submit an evaluation retrieval/answer request under a valid principal for one fixture
     Workspace while referring to data in another Workspace.
  2. Inspect the dataset quality taxonomy independently of any evaluation execution/reporting
     schema.
- Expected results:
  - The foreign-Workspace request is denied without revealing protected resources.
  - The dataset quality taxonomy contains no security or Cross-Workspace category.
  - Cross-Workspace isolation remains protected by its own authorization/security contract and is
    not converted into a dataset quality score or retrieval metric.
- Evidence to capture:
  - Focused authorization/integration test command and result.
  - HTTP/application response evidence and dataset taxonomy assertion.

This approved guide is locked. Any semantic change requires a new guide revision; run observations
belong in a separate append-only Evaluation record.
