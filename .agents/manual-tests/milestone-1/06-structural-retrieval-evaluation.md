# Manual Test Guide: Structural and Retrieval Evaluation Reports

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #6 — Produce repeatable structural and retrieval evaluation reports
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-structural-retrieval-evaluation-r1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-01T10:56:07+07:00

## Prerequisites

- Environment: local checkout with Docker PostgreSQL/pgvector healthy, migrations at head and the
  FastAPI application available in deterministic-local provider mode. The runner executes through
  its documented CLI seam and the public ingestion/question contracts.
- Data and state: a versioned Milestone 1 corpus plus a 20–25 case JSONL dataset. Evaluation cases
  cover answerable, unanswerable, ambiguous and adversarial/near-miss behavior and use dedicated
  acceptance Workspaces that can be reset without rewriting prior reports.
- Credentials and permissions: enabled test credentials only for the acceptance Workspaces. Raw
  credentials remain in environment/test-client state and never enter dataset or report artifacts.
- Version inputs: explicit identifiers for dataset, corpus, chunking, embedding, retrieval,
  generation and scorer configurations. Local structural/retrieval runs record generation and
  scorer state as deterministic-local or not-run rather than inventing semantic results.
- Output isolation: a fresh report directory for each run. Repeated executions use distinct output
  paths so prior evidence remains unchanged.

## Locked Test Cases

### TC-01: Validate the curated Evaluation Case contract and category coverage

- Purpose: prove the dataset is large enough and sufficiently explicit to support repeatable
  structural and retrieval measurement without assuming one uniquely correct Chunk.
- Steps:
  1. Load the versioned Milestone 1 JSONL dataset through the runner's validation path.
  2. Count cases and category membership for answerable, unanswerable, ambiguous and
     adversarial/near-miss behavior.
  3. Inspect every case for stable identity, expected behavior, expected source Documents,
     acceptable relevant Chunks and required facts/reference answer when applicable.
  4. Run controlled invalid variants with a duplicate ID, missing required field, unknown category,
     empty acceptable set for an answerable case and a dataset outside the 20–25 case bound.
- Expected results:
  - The authoritative dataset contains 20–25 unique cases and every required category is nonempty.
  - Each case has the fields required by its expected behavior; multiple acceptable relevant Chunks
    are allowed and preserved.
  - Every invalid variant fails before HTTP/provider work with a precise dataset-validation error.
  - No invalid or partial dataset produces a success report.
- Evidence to capture:
  - Dataset summary by category, validation output and the invalid-variant error matrix.

### TC-02: Produce complete versioned provenance from a pinned corpus

- Purpose: make every report reproducible and prevent configuration changes from being mistaken
  for quality changes.
- Steps:
  1. Reset the acceptance Workspace and ingest the versioned corpus through the public ingestion
     seam.
  2. Run the local evaluation CLI with explicit dataset, corpus and configuration versions.
  3. Inspect report metadata and compare it with the exact inputs used by ingestion and questions.
  4. Change one version input without changing its identifier and run the validation path again.
- Expected results:
  - The report records dataset and corpus identity/checksum plus chunking, embedding, retrieval,
    generation and scorer versions.
  - Reported provenance matches the actual corpus and runtime configurations; raw credentials and
    environment-only secrets are absent.
  - An identifier/content collision or missing provenance field fails explicitly rather than
    emitting a misleading report.
- Evidence to capture:
  - Corpus ingest manifest, report provenance object and collision/missing-field failures.

### TC-03: Hard-gate structural pipeline invariants at 100 percent

- Purpose: ensure a numerically useful retrieval report cannot hide a broken cited-answer pipeline.
- Steps:
  1. Run all cases against the deterministic-local application and capture Question responses plus
     persisted traces.
  2. Verify decision/refusal contracts, citation marker-to-projection consistency, Evidence Set
     membership, Workspace ownership and trace persistence for every case.
  3. Inject controlled fixtures for a cross-Workspace candidate, citation outside the Evidence Set,
     missing trace and malformed decision/citation contract.
- Expected results:
  - The valid run reports every structural check and an aggregate structural pass rate of 100%.
  - Structural gates include no cross-Workspace retrieval, no citation outside the Evidence Set and
    a persisted Question Trace for every completed request.
  - Each controlled violation identifies the affected case/check and makes the overall run fail,
    even when retrieval metrics would otherwise be high.
- Evidence to capture:
  - Per-case structural results, aggregate gate result, trace references and violation reports.

### TC-04: Compute retrieval metrics independently of Generation Provider

- Purpose: measure retrieval quality through pinned relevance judgments without conflating it with
  generated answer quality.
- Steps:
  1. Run retrieval for the full dataset with `candidate_k = 8` and capture ordered candidate IDs,
     scores and retrieval latency before generation.
  2. Compute Recall@8, MRR and hit rate from each case's acceptable relevant Chunks/Documents.
  3. Recompute a small worked example independently and compare it with the report.
  4. Replace the Generation Provider with a failing/no-call provider and rerun retrieval scoring.
- Expected results:
  - The report contains per-case relevance outcomes and aggregate Recall@8, MRR, hit rate and
    retrieval latency with documented denominators.
  - Any acceptable relevant Chunk satisfies the judgment; the scorer does not require one arbitrary
    unique Chunk.
  - The independent worked example matches the runner's metrics.
  - Retrieval metrics remain available and identical when generation is disabled or fails.
- Evidence to capture:
  - Ordered retrieval results, worked metric calculation and generation-independent report diff.

### TC-05: Separate system observations from structural and retrieval metrics

- Purpose: prevent latency, usage, cost or provider reliability from being presented as semantic
  answer quality.
- Steps:
  1. Execute a deterministic-local run and inspect the structural, retrieval and system sections.
  2. Execute controlled requests with token/cost metadata, missing usage metadata and one provider
     error.
  3. Compare aggregation and case-level error accounting across the runs.
- Expected results:
  - System reporting contains end-to-end latency, retrieval latency, token usage, cost and provider
    errors in a section separate from structural and retrieval results.
  - Missing usage/cost is represented explicitly as unavailable or zero-by-contract, never guessed.
  - Provider errors are counted without changing retrieval relevance judgments.
  - No local deterministic run emits citation entailment, faithfulness or answer-relevance scores.
- Evidence to capture:
  - Report-section schema, system metric aggregates and provider-error accounting.

### TC-06: Distinguish local structural/retrieval mode from model-backed semantic mode

- Purpose: keep Issue #6 within scope while leaving the first semantic baseline to Issue #7.
- Steps:
  1. Run the CLI in deterministic-local structural/retrieval mode.
  2. Request model-backed semantic mode without a configured scorer/provider.
  3. Inspect mode, provider and scorer provenance in both outputs/errors.
- Expected results:
  - Local mode completes structural, retrieval and system reporting and marks semantic evaluation
    explicitly `not_run` with no semantic threshold or quality claim.
  - Model-backed mode requires explicit provider/scorer configuration and fails fast when absent;
    it never silently falls back to deterministic semantic scoring.
  - Report metadata makes the two modes impossible to confuse.
- Evidence to capture:
  - Local report mode/provenance and missing-model-backed-configuration error.

### TC-07: Produce repeatable, order-stable and append-safe reports

- Purpose: ensure the runner can detect regressions rather than producing order- or state-dependent
  results.
- Steps:
  1. Run the same pinned dataset/corpus/configuration twice into different output paths.
  2. Run the same cases in reversed input order.
  3. Compare normalized reports while excluding explicitly documented wall-clock observations.
  4. Interrupt one run after a controlled case and inspect both the partial output path and prior
     completed reports.
- Expected results:
  - Dataset/corpus/configuration identity, case outcomes, structural gates and retrieval metrics are
    identical across repeated and reordered runs; report case ordering is deterministic.
  - Timing values may vary but retain the same units and aggregation contract.
  - An interrupted run cannot overwrite or masquerade as a completed report, and prior reports
    remain byte-for-byte unchanged.
  - The final report is valid JSON and the documented CLI prints a stable completion summary.
- Evidence to capture:
  - Normalized report comparison, deterministic ordering evidence, interruption result and hashes
    of prior completed reports.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL
Evaluation records.
