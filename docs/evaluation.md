# Evaluation datasets and Milestone 1 runner

## Milestone 3 dataset contract

Issue #50 completed the versioned M3 evaluation dataset. It is a data contract, not an evaluation
runner or report format.

- Dataset: `evals/datasets/milestone_3.jsonl` with 50 corpus-grounded cases.
- Dataset manifest: `evals/datasets/milestone_3.manifest.json` (`m3-dataset-v1`).
- Corpus/Chunk Set manifest: `evals/corpora/milestone_3/manifest.json` (`m3-corpus-v1`).
- Workspace: `evaluation-m3-v1`.

Each case explicitly stores retrieval-relevance applicability and acceptable relevant Chunks,
answer expectations, evidence expectations, and where applicable an
`INSUFFICIENT_EVIDENCE` refusal expectation. Answerable cases must have non-empty required facts.
Several acceptable relevant Chunks are valid. A refusal case has non-applicable retrieval relevance;
a later metrics consumer must not infer a retrieval miss or a zero Recall/MRR value from it. For
M3 metrics, a gold `source_key#ordinal` reference resolves only through this manifest's pinned
Chunk Set provenance identity; the evaluator compares the resulting
`(chunk_set_provenance_id, source_key, ordinal)` identity with the projection of the exactly
correlated trace, never with a database `chunk_id`.

The contract validates dataset and corpus digests, unique manifest Chunk references, Workspace and
source compatibility, and gold references before execution. It does not add an M3 runner, metric
calculation, or report generation. Those capabilities remain separate work.

## Milestone 3 production retrieval calibration

Issue #56 independently accepted the provider and retrieval configuration needed before the M3
runner can execute. The immutable provider contract is `embedding-gemini-m1-v1`: native Gemini API
`v1beta` `models.embedContent`, `gemini-embedding-2`, 1536 dimensions, cosine, NFKC normalization,
and asymmetric input policy `gemini-m3-qa-asymmetric-v1`. Runtime uses
`KNORA_PROVIDER_MODE=google-gemini-api` and `KNORA_GEMINI_API_KEY`; the credential must never enter
artifacts, logs, traces, or provenance.

Calibration `m3-retrieval-calibration-v1` passed its frozen-corpus independence and usefulness
gates and selected literal vector similarity threshold `0.657410732025`. Production M3 retrieval
uses the existing `m3-corpus-v1` Chunk Sets re-embedded under the Gemini configuration, without
rechunking. Paired configurations are `retrieval-m3-vector-v2` and `retrieval-m3-rrf-v2`; both pin
`vector_candidate_k = 8`, while hybrid additionally pins `fts_candidate_k = 8`,
`fts-m3-or-v2`, and `rrf-v2`. This completion makes Issue #51 eligible to resume its remaining
acceptance cases; it does not itself execute the M3 evaluation runner.

## Issue #51 production evaluation acceptance

Issue #51 is accepted against locked guide `issue-51-v12` by run
`m3-issue-51-20260814-acceptance-05`. The run used a sealed, isolated production topology and
the normal `POST /v1/questions` seam. It passed closure and Binding V3 preflight, exact
`(workspace_id, trace_id)` correlation, one non-empty manifest-bound candidate observation,
public citation alias validation, public-only semantic scoring, post-run drift verification and
independent latency capture. TC-02 recorded Recall@8 `1.0` and reciprocal rank `1.0` for the one
applicable observed case; this is acceptance evidence, not an aggregate M3 quality claim.

The append-only Evaluation record is
`.agents/manual-tests/milestone-3/51-production-evaluation-correlation.evaluations.jsonl`.
TC-01 and TC-05 evidence from prior accepted observations remain unchanged. The semantic scorer
used version `m3-semantic-citation-v1` and method
`public-answer-public-citation-only-v1`; its input contained only the public answer and public
citation excerpt/source locator. Raw Gemini and scorer credentials are runtime-only and are not
part of the record.

## Milestone 1 runner

The Milestone 1 runner measures deterministic structural invariants, retrieval quality and system
observations through the versioned `POST /v1/questions` HTTP seam. Deterministic-local mode does
not claim semantic answer quality. Model-backed mode adds the first semantic baseline through an
explicit, versioned scorer without applying an arbitrary quality threshold.

## Pinned inputs

- Dataset manifest: `evals/datasets/milestone_1.manifest.json` (`m1-dataset-v1`).
- Dataset: `evals/datasets/milestone_1.jsonl`, containing 20 curated cases.
- Corpus manifest: `evals/corpora/milestone_1/manifest.json` (`m1-corpus-v1`).
- Runtime configurations: `chunking-m1-v1`, `embedding-local-m1-v2` and the retrieval
  configuration observed in each persisted Question Trace.
- Workspace: the dedicated local `evaluation-m1-r2` Workspace.

The runner checksum-binds the dataset version, validates every corpus document checksum, verifies
that every relevance judgment resolves to a pinned Chunk, and requires the Workspace's complete
active corpus/configuration state to match the manifest before sending questions.

## Prepare the factual corpus

With PostgreSQL healthy and migrations at head, create the dedicated Workspace once:

```powershell
@'
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import WorkspaceTable
with SessionFactory.begin() as session:
    if session.get(WorkspaceTable, "evaluation-m1-r2") is None:
        session.add(WorkspaceTable(id="evaluation-m1-r2", name="Milestone 1 Evaluation R2"))
'@ | .\.venv\Scripts\python -
```

Ingest every pinned factual Document through the application-backed CLI seam:

```powershell
$manifest = Get-Content -Raw evals\corpora\milestone_1\manifest.json | ConvertFrom-Json
foreach ($document in $manifest.documents) {
    $path = Join-Path evals\corpora\milestone_1 $document.path
    .\.venv\Scripts\knora-ingest.exe $path `
        --workspace $manifest.workspace_id `
        --source-key $document.source_key
}
```

The runner rejects missing, extra or differently derived active Documents. Use a clean dedicated
Workspace rather than mixing unrelated retrieval state into it.

## Run through HTTP

Start Knora in deterministic-local mode with a credential for `evaluation-m1-r2`. Keep the raw
key only in runtime environment state and expose it to the runner through a named variable:

```powershell
$env:KNORA_EVALUATION_API_KEY = "<runtime-only-key>"
```

Always choose a new report path. Publication uses an atomic no-clobber operation, so concurrent or
repeated writers cannot replace completed evidence.

```powershell
.\.venv\Scripts\python -m evals.runners.run_http_eval `
    --dataset evals\datasets\milestone_1.jsonl `
    --dataset-manifest evals\datasets\milestone_1.manifest.json `
    --corpus-manifest evals\corpora\milestone_1\manifest.json `
    --endpoint http://127.0.0.1:8000/v1/questions `
    --report evals\reports\milestone_1-http-r1.json
```

The report separates:

- structural hard gates derived from HTTP responses and trace-scoped PostgreSQL projections,
  including decision/citation contracts, Evidence Set membership, independently resolved
  candidate Workspace ownership and persisted traces;
- per-case and aggregate Recall@8, MRR, hit rate and observed retrieval latency;
- end-to-end latency, usage, cost and provider errors;
- expected-behavior observations, which are not confused with structural validity;
- semantic status, which is explicitly `not_run` in deterministic-local mode. Model-backed mode
  reports citation entailment, faithfulness, answer relevance and refusal correctness under a
  dedicated `semantic` section.

The trace projection requires both the opaque `trace_id` returned by HTTP and the dataset
Workspace. It does not expose a public trace endpoint or permit trace enumeration.

## Repeatability

Run into a second new path, then compare normalized reports. Only retrieval and end-to-end
wall-clock observations are excluded:

```powershell
.\.venv\Scripts\python -m evals.runners.compare_reports `
    evals\reports\milestone_1-http-r1.json `
    evals\reports\milestone_1-http-r2.json
```

Case ordering, provenance, structural outcomes and retrieval metrics must remain identical.

## Model-backed semantic baseline

Run the application in `openai-compatible` mode with an active corpus derived under the same
immutable OpenAI-compatible Embedding Configuration used by the runtime. The repository includes
`evals/corpora/milestone_1/manifest.openai-compatible.json` for this derivation; it keeps the
factual content checksums while pinning `embedding-openai-m1-v1`. Keep the provider key
and scorer key in runtime environment state only. The application provider and the semantic judge
may use the same compatible endpoint, but they remain separate runtime roles.

The runner requires all of the following for model-backed mode:

- `--scorer-version`, a versioned scorer identity;
- `--scorer-method`, the explicit measurement method;
- `KNORA_SEMANTIC_SCORER_BASE_URL`;
- `KNORA_SEMANTIC_SCORER_API_KEY`;
- `KNORA_SEMANTIC_SCORER_MODEL`.

Optional scorer pricing variables are `KNORA_SEMANTIC_SCORER_PRICING_VERSION`,
`KNORA_SEMANTIC_SCORER_INPUT_COST_PER_MILLION_TOKENS` and
`KNORA_SEMANTIC_SCORER_OUTPUT_COST_PER_MILLION_TOKENS`. Missing pricing is reported as
`unavailable`; it is never guessed.

Use a fresh report path for every run:

```powershell
.\.venv\Scripts\python -m evals.runners.run_http_eval `
    --dataset evals\datasets\milestone_1.jsonl `
    --dataset-manifest evals\datasets\milestone_1.manifest.json `
    --corpus-manifest evals\corpora\milestone_1\manifest.openai-compatible.json `
    --endpoint http://127.0.0.1:8000/v1/questions `
    --report evals\reports\milestone_1-semantic-baseline-r1.json `
    --mode model-backed `
    --scorer-version semantic-scorer-v1 `
    --scorer-method llm-judge-v1
```

The semantic report keeps deterministic structural validity separate from model-judged citation
entailment/support. System observations remain separate under `system`, including application and
scorer latency, token usage, cost and provider errors. The first 20-case run is a baseline
observation, not a portfolio claim: CV claims require at least 50 cases and an explicit dataset
size and measurement method.

### Historical Milestone 1 Gemini OpenAI-compatible runtime

The completed Milestone 1 baseline used Gemini through its OpenAI-compatible base URL for both
application generation and embeddings. Its historical evidence records `gemini-embedding-001`.
Final Issue #56 authority supersedes reuse of `embedding-gemini-m1-v1` for that runtime path; the
canonical current meaning of that identity is native Gemini API `gemini-embedding-2`. To reproduce
the closed historical observation, keep its embedding space at 1536 dimensions and use the
provider-specific manifest
`evals/corpora/milestone_1/manifest.gemini.json`, which pins that configuration. Re-embed and
activate the corpus under this configuration; do not switch only an environment variable or mix
its vectors with another configuration. The Gemini OpenAI-compatible embedding response may omit `data[*].index`;
the adapter preserves wire order when that field is absent and rejects a response whose vector
length is not 1536.

Historical runtime values below reproduce that closed Milestone 1 baseline only and must not be
used for Production Retrieval V2 (keep API keys only in process environment or an untracked
`.env`):

```text
KNORA_PROVIDER_MODE=openai-compatible
KNORA_OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
KNORA_OPENAI_EMBEDDING_MODEL=gemini-embedding-001
KNORA_OPENAI_EMBEDDING_CONFIGURATION_ID=embedding-gemini-m1-v1
KNORA_OPENAI_GENERATION_MODEL=gemini-3.1-flash-lite
KNORA_SEMANTIC_SCORER_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
KNORA_SEMANTIC_SCORER_MODEL=gemini-3.1-flash-lite
```

Verify exact model IDs with `GET /models` and probe `POST /embeddings` with `dimensions=1536`
before ingesting. Free-tier rate limits are project/model scoped; pace scorer requests for a full
20-case run so transient throttling is not confused with semantic quality.

## Issue 158: optional evaluation tools

These integrations extend Knora Evaluation. Knora remains the sole authority for datasets, gold,
manifests, runs, reports and release gates; installing or passing mocked tool contracts is not
quality acceptance. [ADR 0017](adr/0017-knora-evaluation-tool-authority.md) records the approved
boundary. Existing citation, refusal and security checks retain their authority.

| Component | Responsibility | Activation boundary |
| --- | --- | --- |
| DeepEval | Correctness, answer relevancy, faithfulness on captured observations | Explicit data permission and judge preflight; no default live calls |
| Ragas | Vietnamese/English multi-hop drafts for owner review; conditional NoiseSensitivity experiment | At most 12 drafts; live generation has a separate call inventory and approval |
| Langfuse | Metadata observations from persisted traces to investigate failures | Local preview first; Cloud export needs separate approval |
| Guardrails AI (#188) | Security detection and false-positive review | Separate shadow work; enforcement remains off |

### Inputs and acceptance

Score the captured application answer once across tools. Correlate every supplement with the
original run, case, attempt, trace and immutable dataset/corpus/configuration provenance. Do not
match by question text, latest trace or timestamps. Exact generation evidence is the selected
Evidence Set, including selected evidence the answer did not cite. Retrieval candidates and
bounded citation excerpts cannot substitute for that input. Missing exact evidence makes the
faithfulness measurement unavailable; provider failures have no quality score.

Ragas review packets retain question, reference answer, source anchors and proposed necessary
evidence steps locally. The owner must verify that at least two steps are actually necessary and
approve each draft before gold insertion. Generation success, a multi-hop label or two context
segments do not prove that a question is genuinely multi-hop. The approved 16-PDF/60-case scope
does not grow automatically. Judge correctness still needs comparison against human assessments;
no new numeric release threshold is established by these integrations.

### Cloudflare data and zero-paid-cost preflight

Cloudflare Workers AI `@cf/openai/gpt-oss-20b` is the preferred judge. Raw question, reference,
answer and exact evidence may be sent only when the inputs are approved public/synthetic data.
Private inputs without external-use permission stay local. A public URL alone is not permission.
No Ollama infrastructure, automatic model downloads, paid-provider fallback or plan upgrades are
part of this integration.

The authorized first DeepEval trial has **paid budget USD 0**, at most **24 HTTP attempts** and
at most **60 minutes**. Every nested judge call and timeout counts before dispatch; resuming does
not reset the attempt count. Unused attempts do not authorize Ragas generation or application
baseline calls. Unknown Workers plan/quota blocks inference. The historical USD 2 proposal is
superseded.

Before a live trial, select the exact inference account in the dashboard and positively verify
**Workers Free** under Manage Account → Billing → Subscriptions, then observe today's Workers AI
Neuron usage in the same account. The account-wide free allocation is 10,000 Neurons/day and
resets at 00:00 UTC. Workers Free stops at that limit; Workers Paid bills overage. Shared usage can
consume quota after the snapshot. A domain's Free plan, an empty subscriptions API response or a
403 response does not prove Workers Free. Keep inference directly on Workers AI, outside AI
Gateway prepaid/Unified billing.
[Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/),
[billing dashboard](https://developers.cloudflare.com/billing/understand/how-billing-works/).

The implementation session's read-only subscriptions request returned 403/code 10000. Its live
trial is **not run**, with zero inference attempts, because the zero-cost condition is unverified.
This observation describes this session, rather than a permanent account-plan assertion.

### Langfuse access, payload and retention

The approved pilot destination is Langfuse Cloud Hobby, Tokyo, initially owner-only. Cloud export
remains off until separately approved. Preview contains only project-scoped opaque identifiers,
approved metadata and finite numeric diagnostics. Questions, references, answers, evidence,
filenames, source keys, user/Workspace identifiers, rationales, raw exceptions and credentials
must never appear in the Cloud payload. Keep the identifier mapping in Knora locally. Imported
phase durations are diagnostic metadata; monotonic ticks are not UTC execution timestamps.
Tokyo's base URL is `https://jp.cloud.langfuse.com`; OTLP ingestion uses
`/api/public/otel/v1/traces`, with the current ingestion version header. Region/key matching must
be verified before activation. [Langfuse OTLP setup](https://langfuse.com/integrations/native/opentelemetry).

Before activation, inspect the final serialized payload, verify owner-only project access and
demonstrate deletion/readback with safe synthetic metadata. Use the current OTLP ingestion path;
the legacy batch ingestion endpoint is being retired on Cloud. Do not enable automatic runtime
decorators or unrelated OpenTelemetry exporters.

The target Cloud metadata retention is **at most seven days**. Hobby's read window is not a
deletion policy. For the small pilot, retain the exact exported opaque trace IDs locally and
delete them through the UI or `DELETE /api/public/traces` with `{"traceIds": [...]}` before the
target expires. Trace deletion is asynchronous; submitting deletion is not proof. Query the same
IDs/observations again and confirm disappearance, including associated observations and scores.
If deletion or access cannot be verified, keep export off. No cleanup service or scheduler is
introduced. [Langfuse deletion documentation](https://langfuse.com/docs/administration/data-deletion).

### Optional tool commands

Install the tools only when using the evaluation integration (Python 3.12):

```powershell
python -m pip install -e "./backend[dev,evaluation-deepeval,evaluation-ragas,evaluation-langfuse]"
```

Create an offline DeepEval supplement from a modern M3 report bound to its dataset manifest:

```powershell
python -m evals.runners.run_deepeval_capture `
  --report <captured-m3-report.json> `
  --dataset evals/datasets/milestone_3.jsonl `
  --dataset-manifest evals/datasets/milestone_3.manifest.json `
  --case-id <selected-case-id> --output evals/reports/<new-supplement.json>
```

The command defaults to `not_run`, opens no HTTP client, and refuses to overwrite a report. An
old report lacking the dataset digest fails closed. The stable run identity is the SHA-256 of the
source report bytes; each score is bound to run/case/attempt/trace and the exact scoring inputs.
This supports the existing M3 pipeline immediately; #153's PDF projection needs the same validated
captured-input contract before scoring. Do not fabricate missing evidence or rerun answering.
The #153/#189 capture seam already has canonical `run_id`, `case_id`, `attempt_id`, `attempt`,
`trace_id`, response digest and selected attempts. A follow-up connection must preserve these
identities, rather than substituting the legacy M3 file hash or replaying pending dispatches.

Live mode additionally requires a reviewed local `--preflight` record and
`KNORA_CF_EVALUATION_TOKEN`. The record binds the exact account, report-derived run ID and selected
capture digest to Workers Free, a same-day quota observation, public/synthetic permission and the
original trial start. Read the implementation's `validate_free_preflight` contract when recording
that evidence. Do not populate an approval record from the 403 response. The CLI permits at most
two answer cases; nested judge calls are bounded by the durable 24-attempt/60-minute ledger under
ignored `evals/reports/.deepeval-ledgers`. Scores and rationales remain local and cannot establish
a release gate. No live judge result exists from this implementation session.

The Ragas packet command is local: it validates existing candidate drafts against selected Knora
corpus chunks and writes a new review artifact. It never invokes a model:

```powershell
python -m evals.runners.ragas_review `
  --manifest evals/corpora/milestone_1/manifest.json `
  --source-key <approved-source-key-1> --source-key <approved-source-key-2> `
  --candidates <local-candidate-drafts.json> --model <recorded-generator-model> `
  --prompt-version <recorded-prompt-version> --output evals/reports/<new-review-packet.json>
```

Each candidate has `language` (`vi` or `en`), `question`, `reference_answer`, and `hops` containing
`chunk_ref`, an exact `quote`, and a proposed `necessary_claim`. Unsupported source mappings or
quotes fail; two distinct evidence steps remain a claim for the owner to verify. The initial
source loader reuses the M1 manifest and chunking processor; it cannot treat an unreviewed #153
PDF baseline as approved gold. Packets remain `pending_owner_review` and never enter a gate.
Imported candidates carry caller-declared model/prompt provenance; they are not labeled as
generated by Ragas. Only the actual Ragas generation path records that tool as the generator.

The explicit `generate_review_packet` API uses an installed Ragas PydanticPrompt and a supplied
Knora schema-aware provider. It has no provider factory, downloads or default live path. A future
generation approval must bind the permitted source inputs and model. For selected chunks, the
planned inventory is one QA generation call per packet, zero embeddings, zero graph transforms,
zero persona/translation calls and zero JSON repair retries. The provider's own attempts still
need a separately reviewed cap; the DeepEval allowance does not apply. This implementation tested
generation with a mock provider only. NoiseSensitivity has readiness diagnostics and no score;
current M3 capture lacks the full retrieved contexts needed for that experiment.

Langfuse's local preview uses a project-specific opaque-ID key kept locally. Reuse that key for
stable joins and preserve the original Knora source report. The preview is an imported metadata
event, not a reconstruction of UTC execution spans. CLI preview does not load Cloud keys or
activate export. The export seam requires a separate approval after serialized-payload review;
the SDK transport was exercised with mocks only. No Langfuse UI, server retention, access or
deletion claim is established by a mock export.

```powershell
python -m evals.runners.langfuse_bridge --report <captured-m3-report.json> `
  --project-key-file <local-opaque-id-key-file> --output evals/reports/<new-metadata-preview.json>
```

The opaque-ID key is distinct from Langfuse Cloud credentials. Keep it out of version control;
changing it changes the projected IDs. Preview is a local review artifact, not an export approval.

See [implementation evidence](development/issue-158-evaluation-verification.md) for compatibility,
test isolation, mocked versus live results, and remaining owner acceptance.
