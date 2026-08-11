# Knora — AI Support & Knowledge Agent

## Tầm nhìn

Knora là một service AI độc lập giúp các nhóm support và product tìm thông tin trong tài liệu nội bộ, trả lời có dẫn nguồn, tóm tắt hội thoại và đề xuất hành động có kiểm soát.

Dự án được xây dựng như dự án portfolio thứ hai sau KittaChat. Trọng tâm không chỉ là một chatbot gọi LLM, mà là năng lực thiết kế backend, retrieval, evaluation, safety và integration boundary có thể kiểm chứng.

## Bài toán sản phẩm

Tài liệu hỗ trợ thường phân tán, hội thoại dài và câu trả lời khó kiểm chứng. Người dùng cần một hệ thống có thể:

- tìm thông tin liên quan trong knowledge base;
- trả lời kèm citation tới đúng tài liệu và đoạn nguồn;
- từ chối trả lời khi không có đủ bằng chứng;
- đo chất lượng bằng dataset và metrics có thể chạy lại;
- đề xuất tool action và chỉ thực thi write action sau human approval;
- tích hợp với KittaChat mà không phụ thuộc trực tiếp vào dữ liệu nội bộ của KittaChat.

## Nguyên tắc kiến trúc

```text
KittaChat / Web Client
        |
        | REST API / webhook / bot message
        v
Knora Agent Service
        |
        +-- PostgreSQL + pgvector
        +-- Durable ingestion jobs + ProcessIngestionJob worker
        +-- ObjectStore (filesystem local; S3-compatible khi cần)
        +-- LLM / embedding providers
        +-- external tools
```

- Knora sở hữu documents, chunks, embeddings, traces và evaluations.
- KittaChat sở hữu users, conversations và messages.
- Hai hệ thống giao tiếp qua explicit API/event contracts.
- Retrieval luôn tôn trọng workspace boundary.
- Prompt, model, chunking và retrieval configuration đều có version.
- Read tools và write tools được phân loại riêng; write tools mặc định cần approval.
- Side effect phải có idempotency key và audit trail.
- Chỉ thêm multi-agent khi evaluation chứng minh lợi ích.

## Lộ trình

### Milestone 1 — Cited RAG tracer bullet

- Nạp corpus Markdown/text mẫu.
- Chunk, embed và lưu trong PostgreSQL + pgvector.
- Hỏi đáp qua API.
- Trả lời có citation hoặc từ chối khi thiếu bằng chứng.
- Dataset 15–20 câu hỏi ban đầu.
- Lưu retrieval trace, latency và token usage.

### Milestone 2 — Production-shaped ingestion

Status: delivered through GitHub Issue #19.

- Issue #15: durable PDF upload, Workspace-scoped request idempotency, source-version commit và
  ObjectStore staging.
- Issue #16: deterministic, isolated PDF extraction, normalized physical pages và page-bounded
  chunking.
- Issues #17–#18: fenced worker coordination, retries, PDF derivation/embedding persistence,
  activation CAS và supersession.
- Issue #19: public six-state polling, lifecycle/retry/serving projections, upload and reprocess
  idempotency, explicit reprocess configuration selection, audit projection và connected
  upload → worker → poll → cited-answer flow.

The current application composes `ProcessIngestionJob` and the durable-work PDF handler. A
deployment-specific daemon or queue scheduler is still an operational concern, and S3-compatible
storage remains reserved for the later object-lifecycle work.

The next planned Milestone 2 slice is [Issue #20 — object lifecycle metrics](https://github.com/NhiBuaa/knora-agent/issues/20).

### Milestone 3 — Hybrid retrieval và evaluation

- Kết hợp vector search với PostgreSQL full-text search.
- Đo Recall@k, MRR, citation correctness và latency.
- Mở rộng dataset lên 50–100 cases.
- Ghi lại baseline, failure taxonomy và một cải tiến có số liệu.

### Milestone 4 — Tools và human approval

- Một read-only support tool.
- Một write tool tạo ticket.
- Vòng đời `proposed -> approved/rejected -> executing -> succeeded/failed`.
- Schema validation, idempotency và audit log.

### Milestone 5 — UI và observability

- Document management, streaming chat và citation viewer.
- Retrieval trace và evaluation report.
- Latency, token usage và estimated cost.

### Milestone 6 — KittaChat integration

- Mention `@assistant` gửi authenticated event sang Knora.
- Cited answer quay lại bằng idempotent callback.
- Timeout/failure có user-visible fallback và không ảnh hưởng message delivery.

## Ngoài phạm vi bản đầu

- Multi-agent orchestration.
- Autonomous destructive actions.
- Fine-tuning.
- Voice assistant.
- Kubernetes.
- Marketplace tools.
- Hỗ trợ nhiều định dạng tài liệu cùng lúc.

## Câu chuyện portfolio

> Xây dựng một knowledge agent có cited RAG, hybrid retrieval, human-approved tool execution và evaluation pipeline; sau đó tích hợp nó vào hệ thống chat realtime KittaChat thông qua API contract độc lập.
