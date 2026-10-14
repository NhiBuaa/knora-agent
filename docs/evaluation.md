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
