# Specification — Milestone 1: Cited RAG Tracer Bullet

Status: Approved for scaffold  
Date: 2026-07-31

## 1. Mục tiêu

Tạo vertical slice nhỏ nhất chứng minh Knora có thể nhận câu hỏi, truy xuất evidence từ một corpus cố định và trả về câu trả lời có citation. Khi không tìm thấy evidence, hệ thống phải từ chối thay vì tự suy diễn.

Milestone này ưu tiên một public contract ổn định và evaluation có thể chạy lại. Chất lượng production, UI và KittaChat integration thuộc milestone sau.

## 2. Người dùng và use cases

Người dùng chính là support engineer hoặc product team member.

1. Người dùng hỏi một câu có câu trả lời trong corpus và nhận answer cùng citations.
2. Người dùng hỏi một câu ngoài corpus và nhận refusal rõ ràng, không có citation giả.
3. Kỹ sư chạy evaluation dataset để phát hiện retrieval/generation regression.
4. Kỹ sư kiểm tra health endpoint để xác nhận service đang hoạt động.

## 3. Phạm vi

### In scope

- FastAPI service với versioned HTTP API.
- PostgreSQL 16 và pgvector qua Docker Compose.
- Domain/application layer không phụ thuộc FastAPI hoặc một LLM provider cụ thể.
- Contracts cho retriever, answer generator và embedding provider.
- `GET /health`.
- `POST /v1/questions`.
- Citation chứa document id, chunk id và source label.
- Refusal khi retriever không trả evidence.
- Schema và migration nền cho workspaces, documents, chunks và question traces.
- Sample corpus, JSONL evaluation dataset và runner skeleton.
- Unit/API tests tại public seams.

### Out of scope

- Upload UI và Next.js frontend.
- PDF parsing và background worker.
- Hybrid ranking hoàn chỉnh.
- Gọi LLM/embedding API thật.
- Authentication/authorization production.
- Tool calling và human approval.
- KittaChat integration.

## 4. HTTP contracts

### `GET /health`

Response `200`:

```json
{"status": "ok", "service": "knora-agent"}
```

### `POST /v1/questions`

Request:

```json
{
  "workspace_id": "demo",
  "question": "Chính sách hoàn tiền là gì?"
}
```

Response khi có evidence:

```json
{
  "answer": "...",
  "citations": [
    {
      "document_id": "refund-policy",
      "chunk_id": "refund-policy:0",
      "source": "refund-policy.md"
    }
  ],
  "refused": false
}
```

Response khi không có evidence:

```json
{
  "answer": "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.",
  "citations": [],
  "refused": true
}
```

## 5. Data model ban đầu

- `workspaces`: tenant boundary.
- `documents`: source metadata và content checksum.
- `chunks`: text, position, metadata, search vector và embedding.
- `question_traces`: question, retrieved chunk ids, answer, refusal state, latency và provider metadata.

Embedding dimension của scaffold là `1536` và phải được đổi bằng migration khi chọn model khác.

## 6. Acceptance criteria

1. Service khởi động và `GET /health` trả đúng contract.
2. Với retriever trả evidence, question service trả answer và citations tương ứng.
3. Với retriever không trả evidence, service trả refusal chuẩn và không tạo citation.
4. HTTP endpoint validate request, sử dụng application service và serialize đúng response.
5. PostgreSQL + pgvector khởi động bằng Docker Compose và migration tạo được schema nền.
6. Evaluation runner đọc JSONL dataset, gọi question endpoint và tạo JSON report.
7. Test suite và static lint chạy xanh từ hướng dẫn trong README.

## 7. Test seams đã phê duyệt

- HTTP seam: `GET /health`.
- HTTP seam: `POST /v1/questions`.
- Application seam: `AnswerQuestion.execute(question, workspace_id)`.
- Evaluation seam: CLI runner nhận dataset path, endpoint và report path.

Tests kiểm tra observable behavior qua các seam trên, không mock implementation nội bộ của vector database hoặc framework.

## 8. Definition of Done

Milestone 1 chỉ hoàn thành khi corpus thực được ingest, retrieval dùng PostgreSQL/pgvector, provider thật hoặc deterministic local provider được nối qua contracts, eval report được sinh và toàn bộ acceptance criteria có evidence. Scaffold hiện tại chỉ tạo nền và không đồng nghĩa Milestone 1 đã hoàn thành.

