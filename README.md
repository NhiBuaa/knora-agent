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

1. Implement exact PostgreSQL/pgvector retrieval trên active Embedding Sets.
2. Thêm evidence selection, deterministic refusal và Question Trace.
3. Kết nối OpenAI-compatible providers cho demo/evaluation model-backed.
4. Mở rộng evaluation dataset trước khi tối ưu retrieval.
