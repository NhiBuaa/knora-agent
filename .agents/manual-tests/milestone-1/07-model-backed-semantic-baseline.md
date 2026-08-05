# Manual Test Guide: First Model-Backed Semantic Baseline

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #7 — Produce the first model-backed semantic baseline
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-semantic-baseline-r1`
- Approved by: Nhi (explicit approval in Codex task)
- Approved at: 2026-08-02T07:47:15+07:00

## Scope and test-craft coverage

This guide verifies the first model-backed semantic baseline through the approved Evaluation CLI
seam and the public `POST /v1/questions` seam. It covers the Issue #7 requirements for citation
entailment, faithfulness, answer relevance, refusal correctness, provenance, baseline reporting
and separation from system metrics.

Included boundary axes:

- Data shape and contract: complete semantic score output, missing/invalid score output, and
  category-specific cases.
- State and lifecycle: explicit model-backed configuration, scorer/version provenance, baseline
  publication and no-clobber output.
- Security and trust boundaries: runtime-only provider credentials, no secret leakage, and
  server/trace-owned structural citation evidence.

Omitted axes:

- UI transitions: the slice exposes a CLI/report artifact and has no UI seam.
- Application concurrency: provider concurrency is outside this slice; report publication and
  repeatability are covered only where they affect evidence integrity.

## Prerequisites

- Environment: local checkout with Docker PostgreSQL/pgvector healthy, migrations at head, and the
  FastAPI application available through the documented HTTP seam.
- Data and state: the pinned `m1-dataset-v1` 20-case dataset and `m1-corpus-v1` corpus in the
  dedicated `evaluation-m1-r2` Workspace. The active corpus must match its checksum, source keys,
  Chunk references, Chunking Configuration and Embedding Configuration manifests.
- Provider configuration: the application and evaluation runner are explicitly in
  `openai-compatible`/model-backed mode. A runtime-only OpenAI-compatible API key, base URL,
  generation model, embedding model and pricing configuration are supplied through environment
  state. No raw key may enter source, dataset, report or logs.
- Scorer configuration: the run supplies an explicitly approved versioned scorer and its explicit
  measurement method. This guide does not silently select a vendor, model, scorer or quality
  threshold; the chosen values must be recorded in the report.
- Output isolation: use a fresh report path and a fresh append-only Evaluation record. Never
  overwrite a prior report or rewrite a prior Evaluation.

## Locked Test Cases

### TC-01: Require explicit model-backed provider and scorer configuration

- Purpose: prove the semantic baseline cannot run in deterministic-local mode, silently fall back,
  or omit the scorer identity.
- Steps:
  1. Run the evaluation CLI in deterministic-local mode with model-backed semantic scoring
     requested.
  2. Run the CLI in model-backed mode with the provider mode, scorer version, or scorer method
     missing one at a time.
  3. Run the CLI with the explicit OpenAI-compatible provider, an explicit versioned scorer and an
     explicit measurement method.
  4. Inspect the application Question Traces and the final report mode/provenance.
- Expected results:
  - Missing or mismatched model/scorer configuration fails before publishing a semantic report
    with a precise configuration error.
  - The successful run uses the OpenAI-compatible Generation Provider and Embedding Provider;
    it does not fall back to deterministic-local behavior.
  - The report identifies model-backed mode and the configured scorer rather than reporting
    `not_run` or a local semantic result.
- Evidence to capture:
  - CLI exit codes and sanitized configuration errors for each invalid variant.
  - Successful report mode, provider/model provenance and trace-scoped provider metadata.

### TC-02: Score all four required semantic dimensions

- Purpose: prove the first baseline measures citation entailment, faithfulness, answer relevance
  and refusal correctness across the curated behavior categories.
- Steps:
  1. Run the full pinned dataset with the approved model-backed scorer and measurement method.
  2. Inspect per-case and aggregate semantic results for answerable, unanswerable, ambiguous and
     adversarial/near-miss cases.
  3. Confirm that each required dimension has an observable value, denominator/case coverage and
     the scorer's documented interpretation.
- Expected results:
  - The semantic report contains separate results for citation entailment, faithfulness, answer
    relevance and refusal correctness.
  - Per-case results identify the case and the applicable semantic judgments; aggregate results
    state their denominator and do not silently drop a behavior category.
  - The scorer evaluates the generated answer, its cited evidence and refusal behavior from the
    persisted Question Trace/response evidence; it does not receive database Chunk IDs as a
    provider-facing alias.
- Evidence to capture:
  - Full semantic section of the report, per-case score records and category/denominator summary.
  - The approved scorer method/version and sanitized request/response metadata.

### TC-03: Keep deterministic citation validity separate from semantic citation support

- Purpose: prevent structural pipeline validity from being confused with model-judged citation
  support or entailment.
- Steps:
  1. Inspect the same report's structural hard-gate section and semantic citation-entailment
     section.
  2. Use a controlled fixture or approved test case where aliases, marker ordering and Evidence
     Set membership are structurally valid but the answer is not supported by the cited Chunk.
  3. Use a controlled invalid fixture where an alias is outside the Evidence Set or the marker
     contract is malformed.
- Expected results:
  - Structural validity remains a deterministic hard gate with explicit checks and is reported
    independently from semantic citation entailment/support.
  - A structurally valid but semantically unsupported citation can lower the semantic score
    without being relabeled as a structural failure.
  - A malformed or out-of-Evidence-Set citation fails the structural gate and is not rescued by a
    favorable semantic score.
  - The report does not collapse the two signals into one unqualified citation-quality number.
- Evidence to capture:
  - Per-case structural checks, hard-gate result and semantic citation-entailment result for both
    controlled fixtures.

### TC-04: Record complete scorer and runtime provenance without secrets

- Purpose: make the baseline reproducible and distinguish scorer/configuration changes from quality
  changes.
- Steps:
  1. Run the baseline with explicit dataset, corpus, Chunking, Embedding, Retrieval, Generation
     and scorer version identifiers plus the measurement method.
  2. Inspect the report provenance and the model-backed Question Trace projections.
  3. Search the report, trace projection and captured logs for raw provider credentials and secret
     response bodies.
  4. Change a pinned input's content without changing its identifier and rerun the validation
     path.
- Expected results:
  - The report records dataset version/checksum, corpus version/checksum, Chunking Configuration,
    Embedding Configuration, Retrieval Configuration, Generation configuration, scorer version,
    scorer method and the model/provider identities used for scoring.
  - Provider request IDs, finish reasons, usage and cost metadata are retained when supplied, but
    raw API keys and sensitive payloads are not persisted or logged.
  - A content/checksum collision or missing provenance field fails explicitly before publishing a
    misleading baseline.
- Evidence to capture:
  - Sanitized provenance object, trace metadata projection, redaction check and invalid-input
    failure output.

### TC-05: Publish a baseline without an arbitrary semantic pass threshold

- Purpose: preserve the first run as a measured baseline rather than an unsupported quality claim.
- Steps:
  1. Run the approved model-backed scorer against all pinned cases.
  2. Inspect semantic aggregate values, status and any pass/fail or threshold fields.
  3. Confirm the report and documentation state the dataset size and measurement method.
- Expected results:
  - The report publishes observed semantic values and their measurement metadata without applying
    an arbitrary semantic pass threshold before this baseline exists.
  - No semantic metric is presented as a portfolio/CV claim from this 20-case run; documentation
    states that such claims require at least 50 cases and an explicit dataset size and measurement
    method.
  - Structural hard-gate status remains independently enforceable; it is not replaced by a
    semantic threshold.
- Evidence to capture:
  - Semantic aggregate section, absence of an arbitrary threshold/gate, and the updated
    documentation excerpt with its commit/file reference.

### TC-06: Separate semantic metrics from latency, usage, cost and provider errors

- Purpose: ensure operational observations cannot be misread as semantic quality.
- Steps:
  1. Run a successful model-backed baseline with provider usage and pricing metadata enabled.
  2. Run a controlled provider-error or incomplete-usage case using the approved test endpoint or
     fixture.
  3. Inspect report aggregation and per-case records.
- Expected results:
  - Semantic results are under a dedicated semantic section, while end-to-end/retrieval latency,
    token usage, cost and provider errors remain under a separate system section.
  - Missing usage/cost is represented as unavailable or otherwise explicit; it is never guessed
    or converted into a semantic score.
  - A provider error is counted and attributable to the affected case/run without being treated as
    evidence of faithfulness, relevance or refusal correctness.
- Evidence to capture:
  - Semantic and system report sections, aggregate usage/cost/error values and the controlled error
    case result.

### TC-07: Preserve append-safe baseline evidence and explicit measurement method

- Purpose: prevent a later scorer/configuration change from rewriting the first semantic baseline.
- Steps:
  1. Publish one successful baseline report and append its Evaluation record.
  2. Repeat the run with the same pinned inputs and output to a new report path.
  3. Attempt to publish to the original report path or mutate the original Evaluation record.
  4. Compare stable report fields and provenance while allowing documented wall-clock/model variance.
- Expected results:
  - The first report and Evaluation record remain byte-for-byte/record-for-record unchanged.
  - A repeated run uses a distinct output path and preserves the scorer version and measurement
    method in its own provenance.
  - No-clobber publication rejects the reused report path; Evaluation history remains append-only.
  - Differences caused by model variance or wall-clock timing are observable and documented, not
    hidden by rewriting prior evidence.
- Evidence to capture:
  - Report/Evaluation hashes before and after the attempted overwrite, append result, normalized
    comparison and final provenance objects.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL
Evaluation records.
