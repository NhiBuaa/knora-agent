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

Status: completed through GitHub Issue #21.

- Issue #15: durable PDF upload, Workspace-scoped request idempotency, source-version commit và
  ObjectStore staging.
- Issue #16: deterministic, isolated PDF extraction, normalized physical pages và page-bounded
  chunking.
- Issues #17–#18: fenced worker coordination, retries, PDF derivation/embedding persistence,
  activation CAS và supersession.
- Issue #19: public six-state polling, lifecycle/retry/serving projections, upload and reprocess
  idempotency, explicit reprocess configuration selection, audit projection và connected
  upload → worker → poll → cited-answer flow.
- Issue #20: durable object lifecycle maintenance, bounded failed-upload diagnostic retention,
  authoritative cleanup/reconciliation fencing, Operational Metrics V1, versioned alerts và
  S3-compatible ObjectStore support.
- Issue #21: final regression and release gate. It accepted the full production-shaped ingestion
  lifecycle, PostgreSQL concurrency/atomicity coverage, PDF boundary fixtures, citations,
  reprocessing, object lifecycle, operational metrics, migrations, documentation and Milestone 1
  compatibility.

The completed application composes `ProcessIngestionJob`, `ObjectLifecycleMaintenance`,
`OperationalObservability` and typed filesystem or S3-compatible ObjectStore adapters. A
deployment-specific daemon or scheduler remains an operational concern.

### Milestone 3 — Hybrid retrieval và evaluation

- Đang thực hiện. M3.1 đã hoàn thành qua [Issue #49](https://github.com/NhiBuaa/knora-agent/issues/49): một retrieval seam dùng chung cho vector-only và hybrid `rrf-v1`, PostgreSQL full-text policy `fts-v1`, tenant/active-set/config filtering trong từng branch, và trace provenance có tương quan.
- M3.3 đã hoàn thành qua [Issue #50](https://github.com/NhiBuaa/knora-agent/issues/50): versioned evaluation dataset và gold judgments.
- Production Retrieval V2 đã hoàn thành qua [Issue #56](https://github.com/NhiBuaa/knora-agent/issues/56): native Gemini embedding, frozen calibration, re-embedding không rechunk, `fts-m3-or-v2`, `rrf-v2`, và paired vector/hybrid retrieval configurations.
- M3.2 ([Issue #51](https://github.com/NhiBuaa/knora-agent/issues/51)) nay đủ điều kiện tiếp tục TC-02/03/04; M3.4 ([Issue #52](https://github.com/NhiBuaa/knora-agent/issues/52)) vẫn còn mở.
- Đo Recall@k, MRR, citation correctness và latency.
- Issue #50 đã hoàn thành bộ dữ liệu 50 case có versioned gold relevance, answer/evidence và
  refusal judgments; dataset/corpus manifests được checksum-bind.
- Runner, metric execution/reporting, baseline và failure analysis vẫn là các slice Milestone 3
  riêng; #50 không thêm các behavior này.
- Ghi lại baseline, failure taxonomy và một cải tiến có số liệu.
- Final code review được thực hiện ở release gate sau khi toàn bộ M3 hoàn tất, theo quyết định của
  repository owner; Issue #56 đã hoàn tất implementation và manual acceptance nhưng không tự nhận
  một review riêng là release review.

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
