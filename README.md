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

Scaffold sử dụng deterministic demo adapters nên chạy được mà không cần API key. Milestone 1 tiếp theo sẽ thay chúng bằng PostgreSQL/pgvector retriever và provider thật qua các contracts hiện có.

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

1. Viết ingestion command cho `sample_data/*.md`.
2. Tạo chunks có version và checksum.
3. Thêm embedding provider.
4. Implement PostgreSQL/pgvector retriever sau `Retriever` port.
5. Persist question traces.
6. Mở rộng eval dataset lên 15–20 cases trước khi tối ưu retrieval.

