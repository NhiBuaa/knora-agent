# Knora Agent

Knora là AI support và knowledge agent trả lời dựa trên tài liệu có citation. Repo hiện chứa scaffold cho [Milestone 1](docs/specs/milestone-1-cited-rag.md); đây chưa phải implementation RAG production hoàn chỉnh.

Đọc [bức tranh tổng quan](docs/PROJECT_OVERVIEW.md) trước để hiểu product boundary và roadmap.

## Chạy local

Yêu cầu: Python 3.12–3.14 và Docker.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\backend[dev]"
docker compose up -d postgres
Set-Location backend
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\uvicorn knora.main:app --reload
```

Mở API docs tại `http://localhost:8000/docs`.

`/health` là public. Các Workspace endpoint yêu cầu `X-API-Key`; runtime chỉ nhận hash của key,
không nhận hoặc lưu raw key. Ví dụ tạo một credential local:

```powershell
$rawKey = "local-demo-key"
$keyHash = .\.venv\Scripts\python -c `
  "from knora.access.api_keys import hash_api_key; print(hash_api_key('local-demo-key'))"
$env:KNORA_API_CREDENTIALS_JSON = ConvertTo-Json -Compress -InputObject @(
  @{
    key_id = "local-demo"
    key_hash = $keyHash
    workspace_id = "demo"
    enabled = $true
  }
)
```

Gửi raw key qua header `X-API-Key`; không commit key này hoặc ghi nó vào log. Ingestion HTTP dùng
`multipart/form-data` tại `POST /v1/workspaces/{workspace_id}/documents` với fields `source_key`
và `file`.

### OpenAI-compatible provider mode

Mặc định Knora dùng `deterministic-local` để test lặp lại được. Để chạy cả ingestion và cited
answers qua một endpoint OpenAI-compatible, đặt các biến sau trước khi khởi động API hoặc chạy
`knora-ingest`:

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

Embedding Configuration của Milestone 1 vẫn khóa ở `text-embedding-3-small`, 1536 dimensions và
cosine distance. Prompt content và version `m1-cited-answer-v1` được khóa cùng nhau trong code để
Question Trace luôn có provenance chính xác. Có thể pin thêm
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
```

## Chạy evaluation skeleton

Sau khi API đang chạy:

```powershell
.\.venv\Scripts\python evals\runners\run_http_eval.py `
  --dataset evals\datasets\milestone_1.jsonl `
  --report evals\reports\milestone_1.json
```

## Bước implementation tiếp theo

1. Hoàn thiện concurrency và Workspace isolation failure semantics.
2. Mở rộng evaluation dataset trước khi tối ưu retrieval.
