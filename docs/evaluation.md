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

## Provider and scorer configuration

Daily development uses the AI/storage/session and email OTP/SMTP groups in the
[root template](../.env.example); complete [daily auth setup](runbooks/local-development.md#daily-auth-setup-one-time)
once for registration, sign-in, sign-out and Forgot Password.
The variables below remain supported for direct backend invocation, compatibility
and evaluation; they are not required for daily Cloudflare use. Provider settings
that affect the embedding space must match the corpus/profile. Do not change
identities or re-index historical data merely to try another provider.

### Application provider

The backend reads `.env` through `Settings`; the process environment takes
precedence over the file. Set `KNORA_EMBEDDING_PROVIDER` and
`KNORA_GENERATION_PROVIDER` together. When both are unset, `KNORA_PROVIDER_MODE`
defaults to `deterministic-local`; legacy modes also support `openai-compatible`
(both roles) or `google-gemini-api` (Gemini embedding, OpenAI-compatible generation).
The daily launcher selects only Cloudflare/Ollama/deterministic; use direct
invocation for these compatibility modes.

| Variable | Default / requirement |
| --- | --- |
| `KNORA_OPENAI_BASE_URL`, `KNORA_OPENAI_API_KEY` | Unset; required for OpenAI-compatible. OpenAI's example URL is `https://api.openai.com/v1`; other compatible endpoints need the corresponding contract. Keep the key only in gitignored `.env` or process secrets. |
| `KNORA_OPENAI_EMBEDDING_MODEL`, `KNORA_OPENAI_EMBEDDING_CONFIGURATION_ID` | `text-embedding-3-small`, `embedding-openai-m1-v1`; dimension 1536. Deterministic validation also uses this default model label. |
| `KNORA_OPENAI_GENERATION_MODEL` | Unset; select a model for OpenAI-compatible generation. |
| `KNORA_OPENAI_PRICING_VERSION` | Unset; required for the OpenAI-compatible application provider. |
| `KNORA_OPENAI_EMBEDDING_INPUT_COST_PER_MILLION_TOKENS` | Unset; a nonnegative number is required for OpenAI-compatible embedding. |
| `KNORA_OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS`, `KNORA_OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS` | Unset; nonnegative numbers are required for OpenAI-compatible generation. Do not enter 0 when pricing is unknown. |
| `KNORA_OPENAI_TIMEOUT_SECONDS` | 60 seconds; overrides must be positive numbers. |
| `KNORA_GEMINI_API_KEY`, `KNORA_GEMINI_TIMEOUT_SECONDS` | Key unset; timeout 60 seconds. Selecting `google-gemini-api` embedding requires a key; native V2 pins `gemini-embedding-2`, `embedding-gemini-m1-v1`, 1536 dimensions and the approved input policy. Calibration/re-embedding CLIs read the key directly from the process environment. |

Example application OpenAI-compatible configuration in a separate environment
with a corpus under the matching profile (replace model/prices with verified
values; do not run this against a shared runtime):

```dotenv
KNORA_PROVIDER_MODE=openai-compatible
KNORA_OPENAI_BASE_URL=https://api.openai.com/v1
KNORA_OPENAI_API_KEY=<runtime-secret>
KNORA_OPENAI_GENERATION_MODEL=<compatible-model>
KNORA_OPENAI_PRICING_VERSION=<reviewed-pricing-version>
KNORA_OPENAI_EMBEDDING_INPUT_COST_PER_MILLION_TOKENS=<verified-nonnegative-number>
KNORA_OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS=<verified-nonnegative-number>
KNORA_OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS=<verified-nonnegative-number>
```

For native Gemini embedding, select the pair
`KNORA_EMBEDDING_PROVIDER=google-gemini-api` and
`KNORA_GENERATION_PROVIDER=openai-compatible`, add `KNORA_GEMINI_API_KEY`, and keep
dimension 1536 with the corresponding generation/pricing configuration. Legacy
`KNORA_PROVIDER_MODE=google-gemini-api` still works when both selectors are unset.
The historical Gemini OpenAI-compatible values below have different semantics
from native V2; do not substitute them for the native contract.

### Semantic scorer: separate process environment

The scorer uses `SemanticScorerConfiguration.from_environment` and **reads only the
process environment**. Adding `KNORA_SEMANTIC_SCORER_*` to `.env` does not supply
them automatically to the runner. Backend Settings does not own or validate
scorer configuration; the evaluator retains its separate reader/validation.
Supply variables through the evaluation process's secrets or an authorized secret
manager; do not add automatic `.env` loading or substitute the application token
for the judge key.

| Variable | Default / requirement |
| --- | --- |
| `KNORA_SEMANTIC_SCORER_BASE_URL`, `KNORA_SEMANTIC_SCORER_API_KEY`, `KNORA_SEMANTIC_SCORER_MODEL` | Unset; required for semantic scoring. The judge model/endpoint/key are independent of the application provider. |
| `KNORA_SEMANTIC_SCORER_TIMEOUT_SECONDS` | 60 seconds; overrides must be positive numbers. |
| `KNORA_SEMANTIC_SCORER_PRICING_VERSION`, `KNORA_SEMANTIC_SCORER_INPUT_COST_PER_MILLION_TOKENS`, `KNORA_SEMANTIC_SCORER_OUTPUT_COST_PER_MILLION_TOKENS` | Unset; optional, with nonnegative costs. Missing pricing is recorded as `unavailable`. |

Example variables supplied only to an authorized evaluation process, without
printing secrets:

```powershell
$env:KNORA_SEMANTIC_SCORER_BASE_URL = '<reviewed-compatible-endpoint>'
$env:KNORA_SEMANTIC_SCORER_API_KEY = '<runtime-judge-secret>'
$env:KNORA_SEMANTIC_SCORER_MODEL = '<reviewed-judge-model>'
```

The M1 runner's `--mode model-backed` currently requires `openai-compatible`
provenance for both embedding and generation; sharing the generation protocol
does not automatically enable Cloudflare support. Retain legacy M1/M3/Vietnamese
datasets/manifests/reports and V1/V2 profiles for regression. The judge and
DeepEval/Langfuse integration in #158 require separate approval; this configuration
reference does not select a provider/hosting or change the #153/#158 evaluator contract.

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

## Retrieval V3 S1 PDF baseline

S1 A prepares a **review candidate**, not accepted gold. See
[corpus and five review batches](../evals/corpora/pdf_retrieval_v3_v1/README.md) and
[approved S1 scope](superpowers/specs/2026-10-14-retrieval-v3-s1.md).
The same Knora authority owns source manifests, cases, bindings, observations and
reports. #158 tools consume captured observations; this adapter installs no judge.

**Paid budget: 0 USD.** B waits for owner approval of the corpus and all 60 gold
cases, verified Workers **Free** plan and remaining daily quota, and runtime
coordination. Never upgrade or use a paid account with overage. If Free is
unavailable, stop and report for a later owner decision. Quota exhaustion retains
the source data, configuration, persisted chunks and counters until reset. The
approved baseline is pypdf layout-v2 / Qwen3 0.6B 1024d / GPT-OSS20B
max_tokens=1024 / retrieval-evidence-containment-v1 threshold 0.65; it is
exploratory, not a calibrated threshold or V3 acceptance.

### A: inspect the candidate without inference

From the isolated worktree root:

```powershell
.\.venv\Scripts\python -m evals.runners.pdf_retrieval_v3 validate --output .verification/issue153/candidate.json
.\.venv\Scripts\python -m pytest evals/test/test_pdf_retrieval_v3_dataset.py evals/test/test_pdf_source_binding.py evals/test/test_pdf_retrieval_v3.py evals/test/test_pdf_baseline_runtime.py
```

Review the real/synthetic composition, licenses, source hashes, PDF physical
pages/visible regions and evidence groups. Outer groups are AND; alternatives
inside one group are OR. Six multi-hop cases require two necessary source steps.
Follow-up parents occur earlier in the same conversation. Scan anchors come from
visible source content, independently of parser output. Extraction/mapping misses
remain failures; they never become empty positive gold or retrieval score zero.

After owner approval, save a local `gold-approval.json` with `status: approved`,
`owner: NhiBuaa`, and exact `corpus_sha256`/`dataset_sha256` from candidate validation.
Retain the owner decision URL alongside the local approval. Never manufacture this
record from a passing test or agent review.

### B: owned Free-only runtime, after approval

Coordinate first. Default S1 topology is Compose project `knora153s1`, only
Postgres on loopback **55453**, fresh database `knora153s1_baseline`, filesystem
objects under the S1 worktree, API **8153** and production PDF/Turn workers.
Do not borrow daily database 5432, another session's volume, object root, PID or
port. Run migrations on the fresh owned database. No GPU/Ollama, frontend, MinIO
or Keycloak server is needed; the loopback eval credential uses existing owner
and capability authorization services. This is not deployed authentication/UI evidence.

Before launching, inspect the **actual account** plan and Workers AI usage in
Cloudflare dashboard. Save a local `free-preflight.json` containing:

```json
{
  "account_id": "actual-account-id",
  "plan": "Workers Free",
  "checked_at": "actual-UTC-ISO-timestamp",
  "neurons_used": 0,
  "daily_limit": 10000,
  "models_free_eligible": true,
  "no_paid_gateway": true,
  "evidence": "local-reviewed-dashboard-evidence-reference"
}
```

Values above illustrate the schema, **not verified account facts**. Check the
same account that credentials target; no paid AI Gateway. Startup requires a
snapshot checked within 15 minutes; crossing UTC midnight requires a new
preflight. Workers Free rejects usage beyond 10,000 neurons/day; Workers Paid
can bill overage. Quota resets at **00:00 UTC / 07:00 Vietnam**.
[Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).
HTTP429 is conservatively paused until reset, including temporary capacity errors;
HTTP402/403 stops for an access/Free eligibility review. No automatic paid fallback.
[Cloudflare error taxonomy](https://developers.cloudflare.com/workers-ai/platform/errors/).

Set `KNORA_DATABASE_URL` to the owned `knora153s1_baseline` database and keep
`KNORA_CLOUDFLARE_ACCOUNT_ID`, `KNORA_CLOUDFLARE_API_TOKEN` and a strong generated
`KNORA_S1_BEARER_TOKEN` in process environment. Never commit or print tokens.

```powershell
.\.venv\Scripts\python -m evals.runners.pdf_baseline_runtime --approval .verification/issue153/gold-approval.json --free-preflight .verification/issue153/free-preflight.json --counters .verification/issue153/run/counts.json --objects .verification/issue153/objects --run-id s1-baseline-01
```

Create the workspace through `POST /v1/workspaces` with the eval Bearer token,
owner-selected name and stable Idempotency-Key. Preserve its returned ID. The
runner commands below use that same workspace and run ID; append the required
`--approval`, `--run-id`, `--workspace-id`, `--output` and `--counters` arguments.
The collector defaults to loopback8153. Execute sequentially:

1. `python -m evals.runners.pdf_retrieval_v3 upload` submits all16 PDFs and polls
   only their admitted job IDs. Terminal extraction failures are retained.
2. `python -m evals.runners.pdf_retrieval_v3 propose` writes immutable
   `binding-proposals.json` from current persisted PDF derivations.
3. Owner reviews each anchor match. Save `binding-review.json` with
   `status: approved`, `reviewer: NhiBuaa`, `decision_url`, exact
   `proposal_sha256`, and `choices` mapping **every** anchor ID to one occurrence
   index, or `[]` for missing extraction. Ambiguous occurrences need an explicit
   selection; overlapping chunks of the same occurrence remain alternatives.
4. `python -m evals.runners.pdf_retrieval_v3 collect --binding-review ...`
   captures each question once through production Q&A/Conversation HTTP, its
   exact workspace/trace/public response and PDF citation provenance. Immutable
   run/case/attempt/trace records are the #158 tool input seam. A pending dispatch
   without a captured response is an uncertain outcome: inspect it before retry;
   automatic replay is blocked. Already captured cases are skipped on resume.
5. After daily quota reset, refresh Free preflight and restart the **same run**
   with unchanged data/config/counters. Use `collect --resume-quota` only for
   explicitly recorded quota-paused or expired-preflight attempts; previous attempt artifacts remain.
   Request cap stops require review, not a new run ID to reset counters.
6. `python -m evals.runners.pdf_retrieval_v3 report --binding-review ...`
   scores reviewed source groups. Optional `--response-reviews` supplies owner
   semantic judgments tied to the exact response digest. Missing review is
   pending; #158 tools unavailable is not_run. Reports never imply final acceptance.

All report/observation publication uses existing atomic no-clobber Knora helper.
Counters persist **70 generation HTTP attempts / 2,500 individual embedding
strings**, including failed/time-out requests and repeated PDF-job batches.
These limits prevent waste; they are not a paid reserve or account quota meter.
Only one owned eval runtime may use its counter file. Stop on insufficient Free
quota/caps; never truncate PDFs, skip cases, change models or lower threshold.
Report total/attempted/observed/evaluable/missing-extraction/not-run/error
denominators separately. Observed invoice cost remains unavailable, not assumed zero.

### Offline sizing of this candidate

The unchanged production pypdf layout-v2 extractor was run locally on all 16
candidate PDFs without embedding or generation. It produced 47 chunks and
16,307 chunk tokens measured with its existing cl100k tokenizer, from 2,083,688
PDF bytes. This is a sizing observation, not provider token accounting or a
successful source binding. Scan-01/scan-03 failed with PDF_TEXT_INSUFFICIENT;
scan-02 extracted only 127 characters, and ViT5 only 243 characters over 7 pages.
Retain their source gold and expose the missing extraction in B.

One initial pass therefore sizes to 47 document embedding strings plus 60 query
strings (107 total), before retries or setup probes. At most 60 initial
generation requests and 61,440 configured output tokens are possible; actual
generation can be lower when retrieval refuses. The retry-inclusive caps remain
70 requests / 2,500 embedding strings. These figures do not prove that the
remaining Free quota fits in one day: model tokenizers, input prompts, retries
and other sessions affect consumption. Paid allowance is **0 USD**; split across
quota resets if necessary, with the same data/configuration and no duplicate calls.


## Issue 158: optional evaluation tools

These integrations extend Knora Evaluation. Knora remains the sole authority for datasets, gold,
manifests, runs, reports and release gates; installing or passing mocked tool contracts is not
quality acceptance. [ADR 0018](adr/0018-knora-evaluation-tool-authority.md) records the approved
boundary. Existing citation, refusal and security checks retain their authority.

Issue #153 owns the 16-PDF/60-question Gold Dataset and Retrieval V3 baseline. Issue #158
integrates the tools with Knora's existing datasets, provenance, runners and reports. Ragas is
available to propose new questions, particularly multi-hop, only for a later needed expansion;
it does not regenerate those 60 cases. Every proposed gold addition requires owner review.
CI and code review may establish merge readiness for this integration without live quality
evaluation. Issue #158 stays In Progress until the owner accepts actual quality.

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

An explicitly approved DeepEval trial has **paid budget USD 0**, at most **24 HTTP attempts** and
at most **60 minutes**. Every nested judge call and timeout counts before dispatch; resuming does
not reset the attempt count. Unused attempts do not authorize Ragas generation or application
baseline calls. Unknown Workers plan/quota blocks inference. The historical USD 2 proposal is
superseded.

The current task authorizes code/CI fixes only. Obtain approval for the particular live run before
calling a model, even after Free/quota verification. Dashboard evidence can establish Free/quota
when the billing API returns 403; that response alone cannot.

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
