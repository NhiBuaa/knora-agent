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
- Hai hệ thống giao tiếp qua explicit API/event contracts; không chia sẻ persistence nội bộ.
- Retrieval và mọi mutation phải tôn trọng workspace boundary.
- Prompt, model, chunking và retrieval configuration phải có version khi chúng ảnh hưởng tới
  reproducibility hoặc evaluation.
- Read tools và write tools là hai capability khác nhau; external write mặc định cần authorization và
  human approval phù hợp.
- External side effect phải có logical idempotency (thông qua key/identity phù hợp) và audit trail.
- Chỉ thêm multi-agent khi evaluation chứng minh lợi ích về quality hoặc maintainability.

## System Invariants

Các invariant dưới đây là contract xuyên suốt roadmap. Engineering Design có thể chọn cách thực hiện
khác nhau, nhưng không được làm thay đổi các property này.

1. **Workspace isolation.** Không retrieval hoặc mutation nào được vượt qua Workspace boundary. Mọi
   authorization phải được kiểm tra trước khi resource được lookup hoặc side effect được bắt đầu.
2. **Evidence-first answering.** Cited Answer chỉ được cite Chunks thuộc Evidence Set của chính
   request. Khi evidence không đủ, Knora trả Refusal thay vì suy đoán hoặc tạo citation.
3. **Reproducibility.** Behavior ảnh hưởng tới retrieval, answering hoặc evaluation phải truy được
   về các versioned configuration và provenance phù hợp; không suy ra phiên bản từ trạng thái
   "latest" hoặc dữ liệu không tương quan.
4. **Domain ownership.** Knora và KittaChat chỉ mutate domain mà mình sở hữu. Integration không được
   bypass bounded-context ownership bằng direct persistence coupling.
5. **Controlled writes.** External write side effect chỉ được thực hiện sau authorization và approval
   thích hợp với loại action; read access không mặc nhiên là write authority.
6. **Logical idempotency.** Retry, replay hoặc duplicate delivery không được tạo duplicate logical
   side effect hoặc duplicate logical outcome.
7. **Auditability and traceability.** AI decision và external side effect quan trọng phải có đủ
   provenance để reconstruct request, decision, execution và outcome trong phạm vi được phép.
8. **Fail closed at safety boundaries.** Thiếu hoặc mismatch authorization, approval, proposal identity
   hoặc required evidence phải làm operation fail closed; không được chuyển sang behavior permissive.
9. **Failure visibility.** Failure quan trọng phải có explicit observable state và được truyền qua
   contract phù hợp; không silently fabricate success, answer, citation hoặc completion.

## Lộ trình

M1–M3 bên dưới giữ lại status và implementation history cần thiết của các slice đã/đang thực hiện.
Từ M4 trở đi, mỗi milestone được viết như một contract của target state: Goal, Scope, Architectural
Invariants, Dependencies / Entry Conditions, Exit Criteria và Non-goals. Issue-by-issue execution
history thuộc GitHub hoặc execution evidence, không phải completion proof của roadmap.

### Milestone 1 — Cited RAG tracer bullet

- Nạp corpus Markdown/text mẫu.
- Chunk, embed và lưu trong PostgreSQL + pgvector.
- Hỏi đáp qua API.
- Trả lời có citation hoặc từ chối khi thiếu bằng chứng.
- Dataset 15–20 câu hỏi ban đầu.
- Lưu retrieval trace, latency và token usage.

### Milestone 2 — Production-shaped ingestion

Status / history: completed through GitHub Issue #21.

- The accepted capability includes durable PDF submission, deterministic isolated extraction,
  Workspace-scoped jobs, fenced worker coordination, idempotent reprocessing, PDF citation
  provenance, object lifecycle maintenance and versioned operational metrics/alerts.
- The release gate also preserved Milestone 1 compatibility and verified the connected
  upload → worker → poll → cited-answer flow.
- Detailed issue history and acceptance evidence remain in [Issue #14](https://github.com/NhiBuaa/knora-agent/issues/14),
  [Issue #21](https://github.com/NhiBuaa/knora-agent/issues/21) and the completed
  [Milestone 2 specification](specs/done/milestone-2-production-ingestion.md).

The completed application composes `ProcessIngestionJob`, `ObjectLifecycleMaintenance`,
`OperationalObservability` and typed filesystem or S3-compatible ObjectStore adapters. A
deployment-specific daemon or scheduler remains an operational concern.

### Milestone 3 — Hybrid retrieval và evaluation

Status / history: đang thực hiện. Các slice retrieval seam, versioned evaluation dataset và
Production Retrieval V2 đã hoàn thành qua [Issue #49](https://github.com/NhiBuaa/knora-agent/issues/49),
[Issue #50](https://github.com/NhiBuaa/knora-agent/issues/50) và
[Issue #56](https://github.com/NhiBuaa/knora-agent/issues/56). M3.2
([Issue #51](https://github.com/NhiBuaa/knora-agent/issues/51)) đủ điều kiện tiếp tục các test
case còn lại; M3.4 ([Issue #52](https://github.com/NhiBuaa/knora-agent/issues/52)) vẫn mở.

Target capability của M3 là hybrid retrieval và evaluation có thể chạy lại, đo Recall@k, MRR,
citation correctness, refusal correctness và latency, rồi ghi nhận baseline, failure taxonomy và
ít nhất một cải tiến có số liệu. Runner, report, failure analysis và release review vẫn là các
slice riêng; issue history không phải completion proof của M4–M6.

### Milestone 4 — Tools và human approval

#### Goal

Cho phép Knora chuyển từ việc chỉ cung cấp knowledge sang đề xuất và thực hiện external action có
kiểm soát. Read-only tool có thể cung cấp thêm thông tin trong authorization boundary; write-capable
tool chỉ được tạo external side effect qua một human approval boundary rõ ràng. Model không sở hữu
quyền write tự trị và không được tự approve action của chính nó.

#### Scope

M4 phải chứng minh boundary bằng ít nhất một read-only support capability và một write-capable support
action, ví dụ tạo ticket; external system và exact parameter contract được deferred sang Engineering
Design.

**Read-only tools**

- Phân loại và invoke read-only capability với Workspace authorization, resource authorization và
  failure semantics rõ ràng.
- Trả về kết quả đã được giới hạn theo quyền caller; read-only không đồng nghĩa với unrestricted
  access.

**Write-capable tools**

- Biểu diễn write request thành một proposal có action, target, parameters và identity đủ để human
  xem chính xác điều gì sẽ xảy ra.
- Hỗ trợ lifecycle khái niệm `proposed → approved/rejected → executing → succeeded/failed`.
- Validate schema và parameters trước execution; expose trạng thái và outcome cho caller.
- Bảo vệ external side effect bằng logical idempotency, retry-safe behavior và audit trail.

#### Architectural Invariants

- **Read/write boundary.** Read invocation không được cấp write authority. Cả read và write đều
  phải giữ authenticated caller, Workspace và resource authorization boundary.
- **Explicit approval boundary.** Không external write side effect nào được xảy ra trước explicit
  human approval. Approval là authority thực sự, không phải UI decoration.
- **Approval binding.** Approval phải gắn với đúng proposal/action mà human đã xem. Proposal bị thay
  đổi materially phải tạo approval requirement mới; approval cũ không được tái sử dụng.
- **Fail-closed lifecycle.** Rejected, stale, expired hoặc invalid authorization/proposal không được
  execute. Model không được approve, sửa proposal sau approval rồi tiếp tục execute, hoặc suy ra
  approval từ model confidence.
- **Execution safety.** Supported write action phải schema-validate parameters, chịu được retry/replay
  mà không tạo duplicate logical side effect, và không báo succeeded khi external execution chưa có
  outcome xác thực.
- **Auditability.** Audit trail phải đủ để reconstruct proposal, approval decision và actor, execution
  attempt, external outcome và failure state trong phạm vi authorization.

#### Dependencies / Entry Conditions

- **Hard dependencies:** Workspace Principal và authorization semantics từ M1/M2 phải ổn định; các
  `Cited Answer`, `Evidence Set`, `Refusal` và provenance của `Question Trace` phải đủ ổn định nếu
  proposal được grounded trong knowledge; external tool được chọn phải có explicit capability
  contract gồm input/output, failure và logical-idempotency semantics.
- **Sequencing convenience:** M3 evaluation report giúp đánh giá giá trị của tool use nhưng không
  phải prerequisite cho approval boundary nếu evidence/refusal semantics đã ổn định. M5 chỉ hard-
  depend vào M4 khi UI expose proposal hoặc approval.
- **Parallelizable work:** Read-tool boundary, proposal/approval semantics và M5 user-facing surface
  có thể được thiết kế song song với các evaluation slice của M3. Execution integration chỉ bắt đầu
  sau khi external tool contract và approval semantics đã được chốt ở mức contract.

#### Exit Criteria

M4 chỉ hoàn thành khi có evidence observable rằng:

- Read tool hoạt động đúng trong authenticated authorization và Workspace boundary; cross-Workspace
  hoặc unauthorized access bị từ chối.
- Write action luôn đi qua explicit proposal và approval trước execution; rejected, stale hoặc
  materially mutated proposal không thể execute bằng approval không hợp lệ.
- Model không thể tự approve action của mình.
- Retry hoặc replay của supported write action không tạo duplicate logical external side effect.
- Proposal, approval decision, execution lifecycle và outcome/failure có thể audit và reconstruct.
- External execution failure tạo trạng thái lỗi rõ ràng; không bị report giả thành success.

#### Non-goals

- Autonomous destructive actions.
- Multi-agent orchestration.
- Marketplace hoặc plugin ecosystem.
- Broad workflow automation engine.
- Bypass human approval dựa trên model confidence.

### Milestone 5 — UI và observability

#### Goal

Expose các capability đã xây của Knora thành một usable và inspectable product surface cho user và
operator, trong khi backend vẫn là source of truth cho domain state, evidence, decisions và
observations. M5 không chỉ làm frontend đẹp hơn: nó phải giúp user sử dụng capability và giúp operator
hiểu answer, refusal, latency, cost và failure dựa trên execution thực tế.

#### Scope

**User-facing surface**

- Document management phản ánh các trạng thái ingestion và serving do backend xác định.
- Chat interaction cho Question Request, Cited Answer và Refusal; conversation/message ownership vẫn
  thuộc hệ thống sở hữu chúng và surface chỉ consume explicit contracts.
- Streaming/progress response qua một explicit response contract; final answer và citations vẫn phải
  phân biệt rõ với partial hoặc unvalidated output.
- Citation inspection/viewer hiển thị `Citation Projection` và actual evidence/provenance do server
  resolve.
- Nếu expose tool action, hiển thị proposal, approval decision và execution outcome theo lifecycle
  của M4, không tự tạo authority mới ở client.

**Operator / engineering surface**

- Retrieval trace và evaluation report với provenance của execution, dataset và configuration thực
  tế.
- Latency, token usage và estimated cost với metric boundary và source rõ ràng.
- Trạng thái cần thiết để phân biệt answer, refusal, invalid output, provider failure, ingestion
  failure và các observation failure khác.
- Operational state và alert/report cần thiết để operator biết hệ thống đang làm gì và vì sao một
  outcome không có hoặc không đáng tin.

#### Architectural Invariants

- **Backend ownership.** Frontend không phải source of truth cho Document, Ingestion Job, Question
  Trace, Evaluation Report, tool proposal hoặc approval state.
- **No duplicated domain logic.** UI không được tái hiện business logic quan trọng như retrieval,
  evidence selection, refusal, citation validation, authorization hoặc approval để tự quyết định
  outcome.
- **Evidence fidelity.** Citation viewer phải phản ánh actual server-resolved `Citation Projection`
  và provenance của Evidence Set; client không được tái dựng citation bằng heuristic, current/latest
  lookup hoặc provider-supplied metadata.
- **Execution-bound observability.** Trace, evaluation, latency, token usage và cost phải bind tới
  execution/configuration thực tế. Không được gán observation của request khác hoặc suy ra data bị
  thiếu từ timestamp, UI state hay giá trị mặc định.
- **Missing-data visibility.** Thiếu trace, metric, configuration hoặc provenance phải hiện thành
  unavailable/observation failure phù hợp; UI không được silently fabricate completeness.
- **Authorization boundary.** Documents, traces, evaluations, internal diagnostics, tool data và
  sensitive cost/provider data chỉ được expose trong authorization boundary tương ứng. Opaque
  correlation handle không tự cấp quyền đọc.
- **Streaming safety.** Streaming/progress không được làm cho partial hoặc unvalidated output trở
  thành Cited Answer đã hoàn tất; cancellation và failure phải có semantics rõ ràng ở contract.

#### Dependencies / Entry Conditions

- **Hard dependencies for user surface:** stable ingestion/document lifecycle và serving projections
  từ M2; stable `Cited Answer`, `Refusal` và server-resolved citation contract từ M1/M3; stable
  Workspace authorization từ nền tảng hiện hữu.
- **Hard dependencies for operator surface:** stable `Question Trace`, retrieval provenance và
  Evaluation Report semantics từ M3, cùng operational ingestion/lifecycle observations từ M2.
- **Conditional dependency:** M4 approval lifecycle chỉ là hard dependency cho phần UI expose tool
  action; document/chat/citation surface không cần chờ toàn bộ M4.
- **Sequencing convenience:** Backend projection và public contracts nên ổn định trước khi khóa UI
  behavior, nhưng UI shell, loading/error states và contract-driven views có thể tiến hành song song
  với M3/M4 implementation.

#### Exit Criteria

M5 chỉ hoàn thành khi có evidence observable rằng:

- User có thể quản lý document và sử dụng chat surface; trạng thái hiển thị khớp backend và giữ đúng
  Workspace authorization.
- User có thể inspect citation và thấy đúng evidence/provenance của Cited Answer; Refusal không bị
  hiển thị như answer có citation.
- Nếu có streaming, client phân biệt progress/partial/failure với final validated answer và không
  coi unvalidated citation là final evidence.
- Operator có thể inspect exact retrieval trace, evaluation report, latency, token usage, estimated
  cost và answer/refusal/failure state khi các observation đó tồn tại.
- Missing hoặc unauthorized observation được hiển thị rõ ràng, không được fabricated; sensitive data
  không vượt qua authorization boundary.
- UI không thể tự thay đổi domain outcome, bypass backend authorization, hoặc bypass M4 approval.

#### Non-goals

- Đưa domain state hoặc business logic quan trọng vào frontend.
- Client-side retrieval, citation reconstruction hoặc evaluation scoring thay cho backend/authorized
  evaluator.
- Xây generic observability/BI platform ngoài các execution và operational views cần cho Knora.
- Redesign ingestion, retrieval hoặc answering semantics chỉ để phục vụ presentation.
- Làm KittaChat phụ thuộc vào UI hoặc persistence của Knora; cross-system integration thuộc M6.

### Milestone 6 — KittaChat integration

#### Goal

Tích hợp Knora vào realtime conversation flow của KittaChat thông qua authenticated, explicit và
failure-isolated contracts mà không làm KittaChat phụ thuộc vào availability của Knora. Flow mục tiêu
là `message accepted/delivered → assistant event → Knora → callback/result`; message delivery không
được biến thành `message → wait for Knora → message delivery`.

#### Scope

- KittaChat phát assistant request/event từ conversation flow qua explicit integration contract; Knora
  nhận đủ authenticated context để xử lý trong đúng Workspace boundary.
- Knora trả Cited Answer, Refusal hoặc explicit assistant failure qua public result/callback contract;
  Knora không ghi trực tiếp bot message vào persistence của KittaChat.
- Event delivery và callback có semantics cho duplicate, retry, out-of-order hoặc delayed delivery,
  cùng user-visible fallback khi assistant interaction không hoàn thành.
- Cross-system request, Knora execution và callback/result có correlation đủ để debug và audit.
- Nếu assistant flow chạm tới write-capable tool, M4 proposal/approval/execute policy vẫn là authority
  boundary; integration không được tạo đường tắt.

#### Architectural Invariants

- **Ownership boundary.** Knora không trực tiếp sở hữu hoặc mutate KittaChat users, conversations,
  messages hay internal KittaChat persistence. KittaChat không truy cập persistence nội bộ của Knora.
  Hai hệ thống chỉ giao tiếp qua authenticated public/explicit API hoặc event contracts.
- **Availability isolation.** Ordinary KittaChat message delivery không được phụ thuộc vào Knora
  availability. Knora timeout/down không được rollback hoặc corrupt message delivery; assistant
  interaction phải có fallback phù hợp và có thể complete độc lập.
- **Authentication and authorization.** Cross-service interaction phải authenticated. Request phải
  mang identity/context đủ để Knora enforce Workspace và resource boundary mà không đọc trực tiếp
  internal database của KittaChat; thiếu hoặc mismatch authority phải fail closed.
- **Logical idempotency.** Duplicate/retried event hoặc callback không được tạo duplicate logical
  assistant outcome, duplicate bot response hoặc duplicate external side effect.
- **Traceability.** Một assistant request phải correlate được với Knora execution, Cited Answer/
  Refusal/failure và callback/result trong phạm vi dữ liệu được phép.
- **Failure visibility.** Timeout, unavailable dependency, rejected authorization và callback failure
  phải có explicit observable state; không report assistant success khi Knora outcome chưa được xác
  nhận.

#### Dependencies / Entry Conditions

- **Hard dependencies from Knora:** public assistant invocation và result contract đã ổn định cho
  `Cited Answer`, `Refusal` và failure; Workspace authorization semantics; logical-idempotency
  semantics cho một logical assistant interaction; và trace/observability đủ để bind request →
  execution → result.
- **Hard dependencies from KittaChat:** explicit event/callback seam, authenticated service identity,
  và ordinary message flow có thể accept/deliver message trước khi chờ assistant result.
- **Conditional dependency:** M4 chỉ là hard dependency nếu M6 cho phép assistant flow đề xuất hoặc
  thực hiện write action; khi đó M6 phải consume M4 authority, không định nghĩa authority riêng.
- **Sequencing convenience:** M5 không phải hard dependency của integration. Operator surface và
  correlation views của M5 có thể phát triển song song, miễn là public result/failure semantics và
  trace contract đã ổn định trước end-to-end integration.

#### Exit Criteria

M6 chỉ hoàn thành khi có evidence observable rằng:

- KittaChat thực hiện authenticated assistant invocation và Knora trả Cited Answer, Refusal hoặc
  explicit failure qua explicit contract.
- Duplicate hoặc retried event/callback không tạo duplicate logical outcome hoặc duplicate bot response.
- Knora timeout/unavailable tạo user-visible fallback; ordinary KittaChat message delivery vẫn hoạt
  động bình thường trong cùng điều kiện.
- Không có direct database/domain-internal coupling giữa hai service; ownership boundary được giữ
  qua contract.
- Cross-system request correlate được với Knora execution và callback/result đủ để debug và audit.
- Authorization mismatch, missing result hoặc ambiguous failure không bị diễn giải thành success; nếu
  có write-capable action, approval policy của M4 vẫn được chứng minh end to end.

#### Non-goals

- Merge Knora thành module nội bộ của KittaChat.
- Shared database ownership.
- Làm KittaChat synchronous-dependent vào Knora.
- Autonomous action vượt approval policy của Knora.
- Generic integration framework cho mọi external product.

### Dependency and sequencing summary for M4–M6

- M4 cần stable authorization và evidence/refusal semantics; M3 evaluation report là sequencing
  input, không phải lý do để biến toàn bộ M4 thành dependency tuyến tính.
- M5 user-facing document/chat/citation surface có thể tiến hành khi M2 và M1/M3 public contracts ổn
  định. Chỉ operator surface cần M3 trace/evaluation contracts; chỉ action UI cần M4 approval
  lifecycle.
- M6 cần public Knora service contract, explicit failure semantics, logical idempotency và
  traceability trước khi connect với KittaChat. M5 UI không phải prerequisite; M4 chỉ là conditional
  dependency cho write-capable assistant flow.

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
