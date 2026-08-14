# Knora Agent

Knora là AI support và knowledge agent trả lời dựa trên tài liệu có citation.
[Milestone 1](docs/specs/done/milestone-1-cited-rag.md) và
[Milestone 2](docs/specs/done/milestone-2-production-ingestion.md) đã hoàn tất. Milestone 2 cung
cấp PDF ingestion production-shaped: upload tạo durable job, worker xử lý và activate derivation,
HTTP có polling/retry/serving projection, và Document Version hiện tại có thể được reprocess với
idempotency, audit và supersession semantics đã được phê duyệt.

Đọc [bức tranh tổng quan](docs/PROJECT_OVERVIEW.md) trước để hiểu product boundary và roadmap.

## Mục lục

- [Chạy local](#chạy-local)
  - [Cài đặt lần đầu](#cài-đặt-lần-đầu)
  - [Cấu hình `.env`](#cấu-hình-env)
  - [Bootstrap mỗi phiên PowerShell](#bootstrap-mỗi-phiên-powershell)
  - [Chuẩn bị database và Workspace](#chuẩn-bị-database-và-workspace)
  - [Khởi động API](#khởi-động-api)
  - [Kiểm tra API](#kiểm-tra-api)
  - [PDF jobs và reprocess](#pdf-jobs-và-reprocess)
  - [OpenAI-compatible provider](#openai-compatible-provider)
- [Kiểm tra](#kiểm-tra)
- [Chạy evaluation](#chạy-evaluation)
- [Tài liệu liên quan](#tài-liệu-liên-quan)
- [Trạng thái phát triển](#trạng-thái-phát-triển)

## Chạy local

Yêu cầu: Python 3.12–3.14, Docker Desktop và PowerShell.

### Quickstart: clone đến cited answer

Quickstart này dùng `deterministic-local`, PostgreSQL và filesystem ObjectStore. Nó không cần API
key từ provider bên ngoài.

```powershell
git clone https://github.com/NhiBuaa/knora-agent.git
Set-Location knora-agent
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\backend[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d postgres
docker compose ps postgres
Push-Location .\backend
..\.venv\Scripts\alembic upgrade head
Pop-Location
```

Tiếp theo, chạy block **Bootstrap mỗi phiên PowerShell** bên dưới trong cùng terminal. Block đó tạo
credential runtime an toàn cho Workspace evaluation. Sau đó mở terminal thứ hai tại repository root,
chạy lại block bootstrap và khởi động API:

```powershell
Push-Location .\backend
..\.venv\Scripts\python -m uvicorn knora.main:app --host 127.0.0.1 --port 8000 --reload
```

Trong terminal bootstrap, xác nhận API và chạy full regression suite:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python -m pytest
```

`pytest` là đường nhanh nhất để chạy các HTTP, worker, polling, citation và PostgreSQL seams một
cách lặp lại được. Phần **Chạy evaluation** bên dưới hướng dẫn ingest corpus mẫu và gửi câu hỏi qua
API với credential runtime.

Sau khi ingest corpus theo phần **Chạy evaluation**, gửi một câu hỏi từ terminal bootstrap:

```powershell
$headers = @{ "X-API-Key" = $env:KNORA_EVALUATION_API_KEY }
$body = @{ workspace_id = "evaluation-m1-r2"; question = "What is the refund policy?" } |
  ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/questions `
  -Headers $headers -ContentType "application/json" -Body $body
```

Response thành công chứa answer và citations. Nếu mở terminal khác, chạy lại block bootstrap trước
khi gửi request để tạo lại biến `KNORA_EVALUATION_API_KEY` trong process đó.

### Cài đặt lần đầu

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\backend[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d postgres
```

`Copy-Item` chỉ chạy khi `.env` chưa tồn tại. Không ghi đè `.env` đang chứa secret.

### Cấu hình `.env`

Mở `.env` và điền các biến theo chế độ bạn muốn chạy:

| Biến | Khi nào cần | Giá trị |
|---|---|---|
| `KNORA_PROVIDER_MODE` | Luôn cần | `deterministic-local`, `openai-compatible` hoặc `google-gemini-api` |
| `KNORA_API_CREDENTIALS_JSON` | Giữ mặc định | `[]`; bootstrap mỗi phiên sẽ ghi đè trong process |
| `KNORA_OBJECT_STORE_ROOT` | PDF ingestion local | Thư mục lưu source object; mặc định `.knora-objects` |
| `KNORA_OPENAI_API_KEY` | `openai-compatible` | OpenAI API key, chỉ giữ trong runtime/local `.env` |
| `KNORA_OPENAI_GENERATION_MODEL` | `openai-compatible` | Model chat tương thích, ví dụ `gpt-4o-mini` |
| `KNORA_OPENAI_PRICING_VERSION` và các biến cost | `openai-compatible` | Giá USD trên 1 triệu token của bảng giá đã chọn |
| `KNORA_GEMINI_API_KEY` | `google-gemini-api` | Gemini API key, chỉ giữ trong runtime/local `.env` |
| `KNORA_GEMINI_TIMEOUT_SECONDS` | `google-gemini-api` | Timeout dương; mặc định 60 giây |
| `KNORA_SEMANTIC_SCORER_*` | `--mode model-backed` | Cấu hình riêng của semantic scorer |

Embedding storage cố định ở 1536 dimensions và cosine distance. Provider-backed embedding spaces
được version hóa riêng: `embedding-openai-m1-v1` cho `text-embedding-3-small` và
`embedding-gemini-m1-v1` cho native Gemini API `v1beta` / `gemini-embedding-2`. Gemini space phải
được re-embed/activate riêng và không được trộn với space khác.
Không commit `.env`, raw API key hoặc raw evaluation key.

### Bootstrap mỗi phiên PowerShell

Các biến `$env:...` mất khi đóng PowerShell hoặc khởi động lại máy. Chạy block sau từ repository
root ở đầu mỗi phiên. Block này nạp `.env` vào process hiện tại, tạo một credential runtime mới
cho Workspace evaluation và không in raw key ra màn hình.

```powershell
$repoRoot = git rev-parse --show-toplevel
Set-Location $repoRoot
$ErrorActionPreference = "Stop"
if (-not (Test-Path .\.env)) {
    throw ".env chưa tồn tại; chạy phần Cài đặt lần đầu trước"
}

foreach ($line in Get-Content -LiteralPath .\.env) {
    if ($line -match '^\s*([^#=\s][^=]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable(
            $matches[1].Trim(),
            $matches[2],
            [EnvironmentVariableTarget]::Process
        )
    }
}

$rawKey = [Convert]::ToBase64String(
    [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
)
$env:KNORA_EVALUATION_API_KEY = $rawKey
$env:KNORA_RAW_KEY = $rawKey

$keyHash = .\.venv\Scripts\python -c `
    "import os; from knora.access.api_keys import hash_api_key; print(hash_api_key(os.environ['KNORA_RAW_KEY']))"

Remove-Item Env:KNORA_RAW_KEY

$credentials = @(
    @{
        key_id       = "evaluation-m1"
        key_hash     = $keyHash
        workspace_id = "evaluation-m1-r2"
        enabled      = $true
    }
)

# Dùng -InputObject để giữ JSON dạng array, kể cả khi chỉ có một credential.
$env:KNORA_API_CREDENTIALS_JSON = ConvertTo-Json `
    -InputObject $credentials `
    -Compress

$credential = $env:KNORA_API_CREDENTIALS_JSON | ConvertFrom-Json
if (-not $env:KNORA_API_CREDENTIALS_JSON.StartsWith("[")) {
    throw "KNORA_API_CREDENTIALS_JSON phải là JSON array"
}
"provider_mode=$env:KNORA_PROVIDER_MODE"
"credential_count=$($credential.Count)"
"workspace_id=$($credential[0].workspace_id)"
```

Sau block này, các process con phải được khởi chạy từ cùng PowerShell để nhận cùng
`KNORA_EVALUATION_API_KEY` và `KNORA_API_CREDENTIALS_JSON`. Không chạy `echo $rawKey` và không ghi
raw key vào file.

### Chuẩn bị database và Workspace

Chạy migration ở lần cài đặt đầu tiên hoặc sau khi repository có migration mới:

```powershell
Push-Location .\backend
..\.venv\Scripts\alembic upgrade head
Pop-Location
```

Workspace evaluation chỉ cần tạo một lần. Lệnh này an toàn khi chạy lại:

```powershell
Push-Location .\backend
@'
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import WorkspaceTable

with SessionFactory.begin() as session:
    if session.get(WorkspaceTable, "evaluation-m1-r2") is None:
        session.add(WorkspaceTable(id="evaluation-m1-r2", name="Milestone 1 Evaluation R2"))
'@ | ..\.venv\Scripts\python -
Pop-Location
```

Để chạy evaluation với corpus mẫu, ingest corpus một lần sau khi Workspace đã tồn tại. Chọn manifest
theo provider mode để embedding configuration trong database khớp với runtime:

```powershell
$manifestPath = if ($env:KNORA_PROVIDER_MODE -eq "openai-compatible") {
    ".\evals\corpora\milestone_1\manifest.openai-compatible.json"
} else {
    ".\evals\corpora\milestone_1\manifest.json"
}
$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
Push-Location .\backend
foreach ($document in $manifest.documents) {
    $path = Join-Path ..\evals\corpora\milestone_1 $document.path
    ..\.venv\Scripts\knora-ingest.exe $path `
        --workspace $manifest.workspace_id `
        --source-key $document.source_key
}
Pop-Location
```

Nếu `KNORA_PROVIDER_MODE=openai-compatible`, bước ingest dùng embedding provider đã cấu hình và
có thể phát sinh chi phí API. Không cần chạy lại nếu corpus không thay đổi.

### Khởi động API

Khởi động API từ `backend` sau khi chạy bootstrap. Cách này dùng các biến đã nạp vào process hiện
tại và không phụ thuộc vào việc process tự tìm `.env` theo current working directory:

```powershell
Push-Location .\backend
..\.venv\Scripts\alembic current
..\.venv\Scripts\python -m uvicorn knora.main:app --host 127.0.0.1 --port 8000 --reload
```

Giữ terminal này mở. `Ctrl+C` để dừng API.

### Kiểm tra API

`/health` là public nên không cần API key:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Mở API docs tại `http://localhost:8000/docs`.

Các Workspace endpoint yêu cầu header `X-API-Key`. Runtime chỉ nhận hash của key; Knora không nhận
hoặc lưu raw key. Evaluation runner dùng `KNORA_EVALUATION_API_KEY` làm raw key và gửi nó qua
header này.

Ingestion HTTP dùng `multipart/form-data` tại `POST /v1/workspaces/{workspace_id}/documents` với
fields `source_key` và `file`.

- Markdown và plain text vẫn chạy đồng bộ theo Milestone 1.
- PDF yêu cầu header `Idempotency-Key`. Một submission mới trả `202` với
  `ingestion_job_id`, `submission_outcome` và `status=queued` sau khi source object và job đã bền
  vững.
- `PdfTextExtractor` dùng `pypdf==6.14.2` trong child process cô lập, chuẩn hóa text theo physical
  page và tạo page-bounded chunks. Baseline giới hạn 25 MiB raw, 500 pages, 4 MiB stream mỗi page,
  64 MiB tổng stream, 30 giây extraction và 256 MiB RSS.
- Upload route vẫn chỉ ghi nhận durable work; extractor, embedding persistence và activation chạy
  qua `ProcessIngestionJob` và các adapter đã được composition trong `knora.main`.

### PDF jobs và reprocess

- Poll một job qua `GET /v1/workspaces/{workspace_id}/ingestion-jobs/{ingestion_job_id}`. Response
  có sáu public states, attempt/retry metadata, serving pointers, lifecycle timestamps, safe
  terminal metadata và `Cache-Control: no-store` cùng polling hint.
- Reprocess Document Version hiện tại qua
  `POST /v1/workspaces/{workspace_id}/document-versions/{document_version_id}/reprocess` với
  header `Idempotency-Key`. Body dùng `config_mode=current` hoặc `same_as_job`; mode thứ hai phải
  cung cấp `config_source_job_id` rõ ràng.
- Upload, poll và reprocess đều kiểm tra Workspace trước resource lookup. Job generation, audit và
  request-idempotency binding được lưu trong PostgreSQL; worker đọc Original Source Object và chỉ
  activation thành công sau fenced compare-and-swap.
- Repository hiện composition worker qua `application.state.ingestion_worker`; daemon/queue
  scheduling loop là deployment concern riêng, không phải một HTTP progress surface.

Repository không có worker daemon/CLI. Để local demo một queued PDF Job, chạy đúng composition đã
được app tạo ra một lần từ `backend`:

```powershell
@'
from knora.main import create_app

app = create_app()
print(app.state.ingestion_worker.run_once("readme-manual-worker"))
'@ | ..\.venv\Scripts\python -
```

Lệnh này xử lý nhiều nhất một Job eligible. Production phải chạy scheduling loop do vận hành cung
cấp, không dùng loop demo này.

### OpenAI-compatible provider

Mặc định Knora dùng `deterministic-local` để test lặp lại được. Để chạy ingestion và cited answers
qua một endpoint OpenAI-compatible, điền các biến sau trong `.env` hoặc export chúng trước khi
khởi động API/`knora-ingest`:

```powershell
$env:KNORA_PROVIDER_MODE = "openai-compatible"
$env:KNORA_OPENAI_BASE_URL = "https://provider.example/v1"
$env:KNORA_OPENAI_API_KEY = "<runtime-only-key>"
$env:KNORA_OPENAI_GENERATION_MODEL = "<compatible-chat-model>"
$env:KNORA_OPENAI_PRICING_VERSION = "<provider-pricing-version>"
$env:KNORA_OPENAI_EMBEDDING_INPUT_COST_PER_MILLION_TOKENS = "<usd-rate>"
$env:KNORA_OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS = "<usd-rate>"
$env:KNORA_OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS = "<usd-rate>"
```

Embedding Configuration của Milestone 1 vẫn khóa ở 1536 dimensions và cosine distance; model
embedding là giá trị runtime phải được endpoint công bố và phải trả đúng 1536 phần tử. Khi dùng
OpenAI-compatible mode, không dùng identity `embedding-gemini-m1-v1`; identity đó được dành cho
native Gemini contract của Production Retrieval V2. Prompt content và version
`m1-cited-answer-v1` được khóa cùng nhau trong code để Question
Trace luôn có provenance chính xác. Có thể pin thêm
`KNORA_OPENAI_EMBEDDING_CONFIGURATION_ID` và `KNORA_OPENAI_TIMEOUT_SECONDS`; xem
[`.env.example`](.env.example) để biết toàn bộ tên biến. OpenAI-compatible mode fail khi startup
nếu cấu hình thiếu hoặc embedding space không đúng; Knora không tự động fallback sang local
provider. API key chỉ được đọc từ runtime configuration và được redacted trong representation của
settings.

## Kiểm tra

Từ repository root:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
docker compose config --quiet
```

## Chạy evaluation

Sau khi API đang chạy:

```powershell
.\.venv\Scripts\python evals\runners\run_http_eval.py `
  --dataset evals\datasets\milestone_1.jsonl `
  --dataset-manifest evals\datasets\milestone_1.manifest.json `
  --corpus-manifest evals\corpora\milestone_1\manifest.json `
  --endpoint http://127.0.0.1:8000/v1/questions `
  --report evals\reports\milestone_1.json
```

Deterministic-local mode reports structural and retrieval metrics only. Model-backed semantic
baseline mode requires an explicit scorer version, measurement method and runtime-only scorer
configuration:

```powershell
$env:KNORA_SEMANTIC_SCORER_BASE_URL = "https://provider.example/v1"
$env:KNORA_SEMANTIC_SCORER_API_KEY = "<runtime-only-key>"
$env:KNORA_SEMANTIC_SCORER_MODEL = "<compatible-judge-model>"
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

Semantic metrics are baseline observations; CV claims require at least 50 cases and an explicit
dataset size and measurement method. See [evaluation guidance](docs/evaluation.md) for provenance,
repeatability and report boundaries.

Milestone 3 now includes the 50-case `m3-dataset-v1` data contract, pinned to `m3-corpus-v1`.
It records separate retrieval relevance, answer/evidence, and refusal expectations. It is not yet
accepted by the Milestone 1 runner: metric execution and reporting remain later Milestone 3 work.

Issue #56 đã hoàn thành Production Retrieval V2: native Gemini API `gemini-embedding-2` với input
policy bất đối xứng bất biến, calibration threshold `0.657410732025`, re-embedding trên Chunk Sets
hiện hữu, `fts-m3-or-v2`, `rrf-v2`, và paired vector/hybrid configurations với branch budget 8.
Manual acceptance `issue-56-v5` đã PASS; final code review được gom vào release review toàn bộ M3.

## Tài liệu liên quan

- [Biến môi trường mẫu](.env.example)
- [Current World Model](CONTEXT.md)
- [Architecture Standard](docs/standards/architecture.md)
- [Hướng dẫn evaluation Milestone 1](docs/evaluation.md)
- [Issue #50 M3 evaluation dataset acceptance evidence](.agents/manual-tests/milestone-3/50-evaluation-dataset.evaluations.jsonl)
- [Issue #56 Production Retrieval V2 authority](docs/design/m3-retrieval-rrf-v2-authority-proposal-r9.md)
- [Issue #56 accepted execution evidence](.agents/manual-tests/milestone-3/56-production-retrieval-v2.evaluations.jsonl)
- [Spec Milestone 1 — Cited RAG](docs/specs/done/milestone-1-cited-rag.md)
- [Module seams Milestone 1](docs/design/milestone-1-module-seams.md)
- [Module seams Milestone 2](docs/design/milestone-2-module-seams.md)
- [Milestone 2 completion record](docs/specs/done/milestone-2-production-ingestion.md)
- [Milestone 2 closed specification and design ledger](https://github.com/NhiBuaa/knora-agent/issues/14)
- [Milestone 2 accepted release gate](https://github.com/NhiBuaa/knora-agent/issues/21)
- [Issue #19 design/acceptance guide](.agents/manual-tests/milestone-2/19-public-polling-reprocess-r14.md)
- [Issue #19 accepted execution evidence](.agents/manual-tests/milestone-2/19-public-polling-reprocess-approved-20260810-01.json)
- [Issue #19 delivery ledger](.agents/issue-19-feature-delivery.json)
- [Issue #20 locked manual test guide](.agents/manual-tests/milestone-2/20-object-lifecycle-metrics-r9.md)
- [Issue #20 accepted execution evidence](.agents/manual-tests/milestone-2/20-object-lifecycle-metrics.evaluations.jsonl)
- [Issue #21 accepted release Evaluation](.agents/manual-tests/milestone-2/21-regression-release-gate-r3-run-20260811-01-approved.json)
- [ADR 0009 — ingestion job HTTP contract](docs/adr/0009-ingestion-job-http-contract.md)
- [ADR 0010 — Document Version reprocess API](docs/adr/0010-document-version-reprocess-api.md)
- [ADR 0014 — Object Lifecycle Maintenance](docs/adr/0014-object-lifecycle-maintenance.md)
- [Hướng dẫn làm việc trong repository](AGENTS.md)

## Trạng thái phát triển

- Issue #15 đã triển khai durable PDF submission, ObjectStore persistence, source-version commit,
  request idempotency và queued Ingestion Job.
- Issue #16 đã hoàn tất `PdfTextExtractor` deterministic, normalized physical pages, page-bounded
  chunking và resource isolation.
- Issues #17 và #18 đã hoàn tất worker coordination, PDF derivation, activation, retry và
  supersession persistence.
- Issue #19 đã hoàn tất public polling, upload/reprocess idempotency, audit projection, serving
  state, safe terminal result và connected upload → worker → poll → cited-answer flow. Manual
  acceptance `m2-issue-19-20260810-acceptance-01` đã `PASSED` với human approval; full suite là
  `341 passed, 3 skipped` và focused acceptance là `117 passed`.
- Issue #20 đã hoàn tất object lifecycle maintenance, 24-hour failed-upload diagnostic retention,
  delete-time ownership fencing, reconciliation, Operational Metrics V1, versioned alerts và
  S3-compatible ObjectStore support. Locked guide `m2-issue-20-r9` đã `PASSED` với human
  approval sau integration; verification là `434 passed, 3 skipped`.
- Issue #21 đã hoàn tất release gate và được human approval. Candidate
  `1ac2aac7259d2dcd0faf307883aeafb471e8ac0d` có `434 passed, 3 approved skipped`; ba locked
  manual PDF fixtures chạy riêng với `KNORA_RUN_MANUAL_ACCEPTANCE=1` đều pass. Traceability map
  118/118 criteria về evidence `PASSED`, không còn technical blocker.
