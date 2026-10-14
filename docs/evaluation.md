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

Daily development chỉ cần năm input trong [mẫu root](../.env.example).
Các biến dưới đây vẫn được hỗ trợ cho backend trực tiếp, compatibility và evaluation;
không cần điền khi chỉ chạy Cloudflare daily. Cấu hình provider ảnh hưởng embedding
space phải khớp corpus/profile, không đổi identity hoặc re-index dữ liệu lịch sử chỉ
để thử một provider khác.

### Application provider

Backend đọc `.env` qua `Settings`; process env ưu tiên hơn file. Nếu đặt
`KNORA_EMBEDDING_PROVIDER` và `KNORA_GENERATION_PROVIDER`, phải đặt cả cặp. Nếu cả
cặp chưa đặt, `KNORA_PROVIDER_MODE` mặc định `deterministic-local`; legacy mode còn
hỗ trợ `openai-compatible` (cả hai vai trò) hoặc `google-gemini-api` (Gemini embedding,
OpenAI-compatible generation). Daily launcher chỉ chọn Cloudflare/Ollama/deterministic;
không dùng launcher đó để chạy các mode compatibility này.

| Biến | Default / điều kiện |
| --- | --- |
| `KNORA_OPENAI_BASE_URL`, `KNORA_OPENAI_API_KEY` | Chưa đặt; bắt buộc khi chọn OpenAI-compatible. Ví dụ URL của OpenAI là `https://api.openai.com/v1`; endpoint compatible khác cần contract tương ứng. Key chỉ ở `.env` bỏ qua bởi Git hoặc process secrets. |
| `KNORA_OPENAI_EMBEDDING_MODEL`, `KNORA_OPENAI_EMBEDDING_CONFIGURATION_ID` | `text-embedding-3-small`, `embedding-openai-m1-v1`; dimension 1536. Default model label này cũng được deterministic validation sử dụng. |
| `KNORA_OPENAI_GENERATION_MODEL` | Chưa đặt; cần chọn model khi dùng OpenAI-compatible generation. |
| `KNORA_OPENAI_PRICING_VERSION` | Chưa đặt; bắt buộc với OpenAI-compatible application provider. |
| `KNORA_OPENAI_EMBEDDING_INPUT_COST_PER_MILLION_TOKENS` | Chưa đặt; cần số không âm khi chọn OpenAI-compatible embedding. |
| `KNORA_OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS`, `KNORA_OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS` | Chưa đặt; cần số không âm khi chọn OpenAI-compatible generation. Không tự điền 0 nếu chưa biết giá. |
| `KNORA_OPENAI_TIMEOUT_SECONDS` | 60 giây; override bằng số dương. |
| `KNORA_GEMINI_API_KEY`, `KNORA_GEMINI_TIMEOUT_SECONDS` | Key chưa đặt, timeout 60 giây. Chọn embedding `google-gemini-api` cần key; native V2 pin `gemini-embedding-2`, `embedding-gemini-m1-v1`, 1536 chiều và input policy đã duyệt. Các calibration/re-embedding CLI đọc key từ process env trực tiếp. |

Ví dụ cấu hình application OpenAI-compatible trong môi trường riêng đã có corpus
đúng profile (thay model/giá bằng giá trị đã xác minh, không chạy trên runtime chung):

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

Để dùng native Gemini embedding, chọn cặp
`KNORA_EMBEDDING_PROVIDER=google-gemini-api` và
`KNORA_GENERATION_PROVIDER=openai-compatible`, thêm `KNORA_GEMINI_API_KEY`, giữ
dimension 1536 và các cấu hình generation/giá tương ứng. Legacy
`KNORA_PROVIDER_MODE=google-gemini-api` vẫn hoạt động khi không đặt cặp selectors.
Các giá trị Gemini OpenAI-compatible lịch sử ở phần bên dưới có ý nghĩa khác với
native V2; không dùng chúng thay cho native contract.

### Semantic scorer: process environment riêng

Scorer dùng `SemanticScorerConfiguration.from_environment`, **chỉ đọc process env**.
Điền `KNORA_SEMANTIC_SCORER_*` vào `.env` không tự cấp chúng cho runner. Backend
Settings không sở hữu hoặc validate cấu hình scorer; evaluator giữ reader/validation
riêng. Cấp biến qua process secrets của phiên evaluation hoặc công cụ quản lý secrets
được phép; không thêm cơ chế tự nạp `.env` hoặc dùng application token thay judge key.

| Biến | Default / điều kiện |
| --- | --- |
| `KNORA_SEMANTIC_SCORER_BASE_URL`, `KNORA_SEMANTIC_SCORER_API_KEY`, `KNORA_SEMANTIC_SCORER_MODEL` | Chưa đặt; bắt buộc cho semantic scoring. Judge model/endpoint/key độc lập với application provider. |
| `KNORA_SEMANTIC_SCORER_TIMEOUT_SECONDS` | 60 giây; override bằng số dương. |
| `KNORA_SEMANTIC_SCORER_PRICING_VERSION`, `KNORA_SEMANTIC_SCORER_INPUT_COST_PER_MILLION_TOKENS`, `KNORA_SEMANTIC_SCORER_OUTPUT_COST_PER_MILLION_TOKENS` | Chưa đặt; tùy chọn, cost phải không âm. Thiếu giá được ghi `unavailable`. |

Ví dụ chỉ cấp trong process evaluation được phép, không in secret ra output:

```powershell
$env:KNORA_SEMANTIC_SCORER_BASE_URL = '<reviewed-compatible-endpoint>'
$env:KNORA_SEMANTIC_SCORER_API_KEY = '<runtime-judge-secret>'
$env:KNORA_SEMANTIC_SCORER_MODEL = '<reviewed-judge-model>'
```

Runner M1 `--mode model-backed` hiện yêu cầu cả embedding và generation provenance
`openai-compatible`; không tự hỗ trợ Cloudflare chỉ vì cùng giao thức generation.
Giữ legacy M1/M3/Vietnamese datasets/manifests/reports và V1/V2 profiles để regression.
Judge và tích hợp DeepEval/Langfuse của #158 sẽ được duyệt riêng; phần cấu hình này
không chọn provider/hosting hoặc thay evaluator contract của #153/#158.

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
