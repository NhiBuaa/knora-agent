# Specification — Milestone 1: Cited RAG Tracer Bullet

Status: Done
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
- Hai provider contracts tối thiểu: `GenerationProvider` và `EmbeddingProvider`.
- Deterministic local adapters cho repeatable unit/integration tests.
- OpenAI-compatible generation và embedding adapters cho demo và model-backed evaluation, bật
  bằng environment variables.
- Minimal `X-API-Key` authentication và WorkspacePrincipal authorization cho workspace endpoints.
- `GET /health`.
- Synchronous HTTP và CLI entrypoints dùng chung `IngestDocument` application use case.
- `POST /v1/questions`.
- Citation chứa document id, chunk id và source label.
- Refusal khi retriever không trả evidence.
- Schema và migration nền cho workspaces, documents, chunks và question traces.
- Sample corpus, JSONL evaluation dataset và runner skeleton.
- Unit/API tests tại public seams.
- Ordinary request/response delivery với complete validated answer; không streaming.
- 20–25 curated Evaluation Cases để prove evaluation pipeline end-to-end.

### Out of scope

- Upload UI và Next.js frontend.
- PDF parsing và background worker.
- Hybrid ranking hoàn chỉnh.
- Provider fallback hoặc routing nhiều provider.
- Provider abstraction tổng quát hơn hai contract đã xác định.
- Authentication/authorization production.
- Tool calling và human approval.
- KittaChat integration.

## 4. HTTP contracts

### Authentication

- `/health` public và chỉ trả minimal status.
- Workspace endpoints yêu cầu `X-API-Key`.
- Processing order là
  `authenticate key → create principal → authorize workspace → lookup resource`.
- Missing/invalid key trả `401 UNAUTHENTICATED`; workspace mismatch trả
  `403 WORKSPACE_ACCESS_DENIED` mà không tiết lộ resource existence.
- Một key thuộc đúng một Workspace; một Workspace có thể có nhiều key.
- Runtime config chỉ chứa `key_id`, `key_hash`, `workspace_id`, `enabled`; constant-time secret
  comparison, không lưu/log raw key.
- CLI tạo explicit Workspace Principal và dùng cùng authorization policy.

### `GET /health`

Response `200`:

```json
{"status": "ok", "service": "knora-agent"}
```

### `POST /v1/workspaces/{workspace_id}/documents`

Nhận một raw Markdown/plain-text file tối đa 1 MiB cùng `source_key`. `source_key` unique theo
`(workspace_id, source_key)` và xác định logical Document.

- `201 Created` khi bất kỳ resource nào trong derivation chain được tạo mới.
- `200 OK` khi toàn bộ chain được reuse.

Response:

```json
{
  "outcome": "created",
  "document_id": "...",
  "document_version_id": "...",
  "chunk_set_id": "...",
  "embedding_set_id": "...",
  "chunk_count": 3,
  "chunking_configuration_id": "...",
  "embedding_configuration_id": "...",
  "activation_changed": true
}
```

Cùng `source_key`, checksum, Chunking Configuration và Embedding Configuration thì reuse. Cùng
`source_key` với checksum mới tạo Document Version; khác `source_key` luôn là Document khác.

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
  "decision": "ANSWER",
  "answer": "Yêu cầu hoàn tiền được chấp nhận trong 30 ngày. [[E1]]",
  "citations": [
    {
      "evidence_id": "E1",
      "document_id": "refund-policy",
      "document_version_id": "...",
      "source_key": "support/refund-policy",
      "source_name": "refund-policy.md",
      "heading_path": ["Chính sách hoàn tiền"],
      "start_line": 3,
      "end_line": 5,
      "excerpt": "Khách hàng có thể yêu cầu hoàn tiền trong vòng 30 ngày...",
      "content_checksum": "sha256:..."
    }
  ],
  "refusal_reason": null,
  "trace_id": "..."
}
```

Response khi không có evidence:

```json
{
  "decision": "REFUSAL",
  "answer": "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.",
  "citations": [],
  "refusal_reason": "INSUFFICIENT_EVIDENCE",
  "trace_id": "..."
}
```

`citations` chứa mỗi Evidence Alias đúng một lần theo first appearance trong answer. `source_key`
là logical identifier ổn định, `source_name` là display name và không được chứa internal filesystem
path. `excerpt` do server resolve, tối đa 500 ký tự, không phải toàn bộ raw Chunk.

`GENERATION_OUTPUT_INVALID` trả HTTP `502` cùng error code rõ ràng; không chuyển thành refusal.

Flow bắt buộc là `retrieve → generate hoàn chỉnh → validate structured output và citation markers
→ resolve Citation Projection → persist trace → trả response`. Không expose token, partial answer
hoặc citation chưa validate. `trace_id` chỉ là correlation handle; streaming/progress events cần
contract riêng và được xem xét ở UI/observability milestone, không mặc định ở Milestone 2.

## 5. Data model ban đầu

- `workspaces`: tenant boundary.
- `documents`: stable source identity, nullable `active_embedding_set_id` và monotonic `revision`.
- `document_versions`: normalized content và checksum bất biến; unique theo
  `(document_id, normalized_content_checksum)`.
- `chunking_configurations`: immutable parser, chunker, tokenizer và size parameters.
- `chunk_sets`: một derivation của Document Version; unique theo
  `(document_version_id, chunking_configuration_id)`.
- `chunks`: `ordinal`, `heading_path`, `start_line`, `end_line`, `content_checksum`, `token_count`
  và text; unique theo `(chunk_set_id, ordinal)`.
- `embedding_configurations`: immutable `provider`, `model`, `dimensions` và `distance_metric`.
- `embedding_sets`: vectorization của một Chunk Set; unique theo
  `(chunk_set_id, embedding_configuration_id)`.
- `chunk_embeddings`: `vector(1536)` của từng Chunk trong một Embedding Set.
- `question_traces`: question, retrieved chunk ids, answer, refusal state, latency và provider metadata.
- `evaluation_cases`: versioned expected behavior, acceptable sources/chunks, required facts và
  reference answer khi phù hợp.
- `evaluation_reports`: structural, retrieval, generation semantic và system metrics cùng provenance.

Milestone 1 khóa embedding storage ở `1536` dimensions, PostgreSQL `vector(1536)` và cosine
distance. Mỗi lần chạy chọn đúng một Embedding Configuration bất biến. Các configuration đã được
phê duyệt cho Milestone 1 là:

- `embedding-local-m1-v2`: `deterministic-local`, model label `text-embedding-3-small`,
  `1536` dimensions, cosine; dùng cho test repeatable và structural evaluation.
- `embedding-openai-m1-v1`: `openai-compatible`, model `text-embedding-3-small`, `1536`
  dimensions, cosine; dùng cho OpenAI-compatible model-backed evaluation.
- `embedding-gemini-m1-v1`: `openai-compatible`, model `gemini-embedding-001`, `1536`
  dimensions, cosine; embedding space versioned riêng được phê duyệt cho semantic baseline Issue
  #7 qua Gemini OpenAI-compatible endpoint.

`embedding-gemini-m1-v1` là migration/storage identity riêng: corpus phải được re-embed thành
Embedding Set mới dưới configuration này trước khi activation, không được chỉ đổi environment
variable, không được dùng lại Embedding Set của configuration khác và không được trộn embeddings
giữa các configuration dù cùng dimension. Mọi model hoặc dimension mới ngoài danh sách trên phải
được version hóa thành Embedding Configuration/Embedding Set mới với migration/storage tương thích
trước khi sử dụng.

### Chunking baseline

- Input chỉ gồm Markdown và plain text, normalize UTF-8 và line endings trước SHA-256.
- Split ưu tiên theo heading/paragraph với `target_tokens = 500`, `overlap_tokens = 75` và
  `max_tokens = 650`.
- Chunking Configuration khóa `parser_version`, `chunker_version`, `tokenizer_name`,
  `tokenizer_version`, `target_tokens`, `overlap_tokens` và `max_tokens`.
- Nội dung checksum thay đổi mới tạo Document Version; chunking configuration thay đổi tạo Chunk
  Set; embedding configuration thay đổi tạo Embedding Set.
- Re-chunk và re-embed không tạo Document Version mới và không sửa derivation cũ tại chỗ.
- Synchronous ingestion giới hạn `max_normalized_tokens = 50_000` và `max_chunks = 100`. Vượt bất
  kỳ giới hạn nào trả `DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION` trước embedding.

### Persistence boundary

- Parse, chunk, embed và validate toàn bộ vectors trước khi mở transaction.
- Transaction ngắn re-check idempotency rồi persist atomically toàn bộ derivation chain.
- Không giữ transaction khi gọi provider và không để lại partial Chunk Set/Embedding Set khi lỗi.
- Unique constraints chống duplicate persistence. Duplicate embedding calls khi có concurrent
  requests là limitation được chấp nhận trong Milestone 1; lease/distributed lock nằm ngoài scope.
- CLI gọi cùng `IngestDocument` use case và validation như HTTP, không truy cập repository/ORM
  trực tiếp.

### Active Embedding Set

- `Document.active_embedding_set_id` có thể `NULL` và chỉ trỏ tới completed Embedding Set thuộc
  đúng Document, Workspace và Embedding Configuration.
- Active pointer dùng foreign key `ON DELETE RESTRICT`; active set không được xóa.
- Use case đọc `expected_revision` trước provider call. Transaction cuối persist/reuse chain rồi
  compare-and-swap active pointer theo revision và increment revision.
- Revision thay đổi làm rollback toàn bộ transaction với `DOCUMENT_CONCURRENTLY_UPDATED`.
- Reuse historical chain có thể activate lại; response giữ `outcome: reused` và trả riêng
  `activation_changed`.
- Retrieval resolve active sets nhất quán trong một request; set cũ immutable nhưng không được
  search.

### Retrieval baseline

- Exact pgvector cosine search; chưa HNSW/IVFFlat, hybrid search hoặc reranker.
- `similarity = 1 - cosine_distance`; threshold `0.65` áp dụng trên similarity và trace lưu cả
  distance lẫn similarity.
- Versioned Retrieval Configuration gồm `candidate_k = 8`, `max_evidence_chunks = 5`,
  `max_evidence_tokens = 3000`, `min_similarity = 0.65` và overlap-redundancy policy.
- Query áp dụng trực tiếp Workspace, Active Embedding Set và Embedding Configuration filters.
- Deterministic order là `similarity DESC → document_id ASC → chunk_ordinal ASC → chunk_id ASC`.
- Evidence selection loại adjacent Chunks overlap mạnh trong cùng Chunk Set, không merge Chunks,
  và giới hạn đồng thời theo chunk count lẫn token budget.
- Mỗi candidate có một trace outcome: `SELECTED`, `BELOW_THRESHOLD`, `REDUNDANT_OVERLAP` hoặc
  `TOKEN_BUDGET_EXCEEDED`.
- Không có qualified candidate thì deterministic Refusal và không gọi Generation Provider. Có
  evidence vẫn cho phép provider trả structured Refusal nếu evidence chưa đủ kết luận.
- `min_similarity = 0.65` là baseline cần calibration qua evaluation, không phải quality claim.

### Generation and citations

Application cấp request-scoped aliases `E1`, `E2`, ... và giữ mapping
`evidence_id → chunk_id`; provider không nhận database Chunk IDs.

Structured contract:

```text
decision: ANSWER | REFUSAL
answer: string | null
cited_evidence_ids: string[]
refusal_reason: INSUFFICIENT_EVIDENCE | null
```

- Answer dùng inline marker như `[[E2]]`.
- `ANSWER` yêu cầu answer không rỗng, có marker, mọi alias thuộc Evidence Set, IDs unique và
  `cited_evidence_ids` khớp chính xác marker order.
- `REFUSAL` yêu cầu `answer = null`, không marker/citation, empty IDs và
  `refusal_reason = INSUFFICIENT_EVIDENCE`; application tạo refusal message chuẩn hóa.
- Schema, membership hoặc marker consistency sai trả `GENERATION_OUTPUT_INVALID`; không đổi thành
  Refusal và không repair retry trong Milestone 1.
- Server resolve document, heading và line range từ database; không tin provider metadata.
- Runtime không tuyên bố semantic citation correctness/faithfulness; các thuộc tính đó do
  evaluation đo.
- Trace lưu generation status, alias mapping, parsed markers, validation outcome, finish reason,
  provider request ID nếu có, provider/model, prompt version, usage và latency. Không yêu cầu hoặc
  lưu model chain-of-thought.

### Provider modes

- Local mode kiểm tra orchestration, schemas, citation/refusal flow và trace persistence.
- OpenAI-compatible mode dùng model thật cho demo và semantic evaluation.
- Local mode không tạo bằng chứng hợp lệ cho semantic-quality metrics.
- Không có automatic fallback giữa hai mode trong Milestone 1; cấu hình không hợp lệ phải fail
  rõ ràng khi service khởi động.
- Local Embedding Provider cũng trả vector 1536 chiều để integration test dùng cùng production
  schema.
- Adapter validate dimension ngay sau provider response; mismatch trả
  `EMBEDDING_DIMENSION_MISMATCH` trước khi ghi database.

## 6. Acceptance criteria

1. Service khởi động và `GET /health` trả đúng contract.
2. Với retriever trả evidence, question service trả answer và citations tương ứng.
3. Với retriever không trả evidence, service trả refusal chuẩn và không tạo citation.
4. HTTP endpoint validate request, sử dụng application service và serialize đúng response.
5. PostgreSQL + pgvector khởi động bằng Docker Compose và migration tạo được schema nền.
6. Evaluation runner đọc JSONL dataset, gọi question endpoint và tạo JSON report.
7. Test suite và static lint chạy xanh từ hướng dẫn trong README.
8. Cả hai provider contracts có local và OpenAI-compatible adapters, được chọn rõ ràng qua runtime
   configuration và không tự động fallback.
9. Evaluation report phân biệt deterministic pipeline checks với model-backed semantic metrics.
10. Mọi Embedding Set tham chiếu một immutable Embedding Configuration và retrieval không trộn
    Chunks giữa các configuration.
11. Embedding dimension mismatch tạo lỗi `EMBEDDING_DIMENSION_MISMATCH` và không có partial write.
12. Ingestion tuân thủ ba idempotency keys của Document Version, Chunk Set và Embedding Set.
13. Citation trace được tới Chunk metadata gồm heading path, line range và content checksum.
14. HTTP trả `201/created` cho chain mới và `200/reused` cho chain đã tồn tại với đầy đủ resource
    IDs và configuration IDs.
15. Oversized synchronous input fail trước embedding bằng
    `DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION`.
16. Provider call chạy ngoài transaction; persistence atomic và re-check idempotency trong một
    transaction ngắn.
17. Concurrent ingestion hoàn thành muộn fail bằng `DOCUMENT_CONCURRENTLY_UPDATED` và không thay
    active pointer mới hơn.
18. Question Trace lưu `embedding_set_id`, `chunk_set_id`, `embedding_configuration_id` và
    `retrieved_chunk_ids` dùng cho request.
19. Reusing một historical chain có thể đổi activation và phản ánh bằng `activation_changed` mà
    không đổi `outcome: reused`.
20. Exact retrieval áp dụng tenant/configuration filters trong SQL và trả candidates theo thứ tự
    deterministic đã khóa.
21. Evidence selection ghi outcome cho mọi candidate và tuân thủ chunk-count, token-budget cùng
    overlap-redundancy constraints.
22. Không có qualified evidence thì không gọi Generation Provider; model-backed structured
    Refusal vẫn hợp lệ khi evidence có liên quan nhưng không đủ kết luận.
23. Structured Generation Result và inline Evidence Alias markers phải thỏa toàn bộ schema,
    membership, uniqueness và ordering invariants trước khi trả response.
24. Invalid generation trả `GENERATION_OUTPUT_INVALID`; valid structured Refusal dùng message do
    application sở hữu.
25. Question Trace không lưu chain-of-thought và chứa đủ generation/citation validation metadata
    để debug.
26. Question response có explicit `decision`, refusal reason/citation invariants, version-pinned
    Citation Projections, bounded excerpts và opaque workspace-authorized `trace_id`.
27. Authentication luôn chạy trước resource lookup và trả đúng `UNAUTHENTICATED` hoặc
    `WORKSPACE_ACCESS_DENIED` mà không leak existence.
28. Integration tests bao phủ missing key, invalid key, matching workspace, mismatched workspace
    và CLI workspace isolation.
29. HTTP response chỉ được trả sau khi generation, citation validation, Citation Projection và
    trace persistence hoàn tất; không có token/partial output exposure.
30. Evaluation dataset Milestone 1 có 20–25 curated cases thuộc đủ bốn behavior categories và
    runner phân biệt structural, retrieval, generation-semantic và system metrics.
31. Structural hard gates đạt 100%, không cross-Workspace retrieval, không citation ngoài Evidence
    Set, trace persist được, runner repeatable và report có đủ provenance versions.
32. Semantic metrics không có arbitrary threshold trước baseline run; claim trên CV yêu cầu ít nhất
    50 cases cùng dataset size và measurement method.

## 7. Test seams đã phê duyệt

- HTTP seam: `GET /health`.
- HTTP seam: `POST /v1/questions`.
- HTTP seam: `POST /v1/workspaces/{workspace_id}/documents`.
- Application seam: `AnswerQuestion.execute(question, workspace_id)`.
- Application seam: `IngestDocument.execute(...)` được dùng bởi cả HTTP và CLI.
- Evaluation seam: CLI runner nhận dataset path, endpoint và report path.

Tests kiểm tra observable behavior qua các seam trên, không mock implementation nội bộ của vector database hoặc framework.

## 8. Definition of Done

Milestone 1 chỉ hoàn thành khi corpus thực được ingest, retrieval dùng PostgreSQL/pgvector, cả hai
provider modes được nối qua `GenerationProvider` và `EmbeddingProvider`, eval report được sinh và
toàn bộ acceptance criteria có evidence. Scaffold hiện tại chỉ tạo nền và không đồng nghĩa
Milestone 1 đã hoàn thành.
