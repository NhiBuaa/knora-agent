# Knora: nghiên cứu 14 track cho refactor và portfolio Backend & AI Systems

Ngày khảo sát: **2026-10-05**. Phạm vi: source hiện tại, kiến trúc tham chiếu, tài liệu kỹ thuật chính thức và mục tiêu nghề nghiệp trong Career. Đây là kết quả nghiên cứu và các thí nghiệm đề xuất; các phép đo/gate trong tài liệu chưa được thực thi trong lượt nghiên cứu này.

## 0. Cách đọc và kết luận điều hành

**Hướng đề xuất:** củng cố Knora thành một dịch vụ knowledge có citations, đo được chất lượng và vận hành được; tạo các bài thực hành có giới hạn cho những năng lực JD cần nhưng chưa phù hợp với đường chạy chính. Research đầy đủ 14 track không có nghĩa triển khai đồng thời 14 nhóm thay đổi.

Các kết luận phải được đọc theo bốn mức:

- **Đã xác minh:** source tại commit ghi bên dưới, tracker được đọc qua `gh`, hoặc tài liệu do nhà phát triển công nghệ công bố.
- **Suy luận từ source:** rủi ro hoặc giới hạn kiến trúc; chưa đồng nghĩa lỗi đã tái hiện trong runtime.
- **Chưa biết:** cần workload, người dùng, benchmark, đánh giá hoặc kiểm tra deployment thật.
- **Đề xuất:** ứng viên thiết kế/thí nghiệm và tiêu chí quyết định; chưa phải canonical domain decision hay implementation plan đã được duyệt.

### Baseline và nguồn định hướng

| Nguồn | Snapshot | Cách dùng |
| --- | --- | --- |
| Knora GitHub `main` | `ee7572583d558676c6d75ed266cc4a1f4fe0286d` | Source và trích dẫn kỹ thuật được pin vào commit này |
| Checkout khảo sát `codex/test` | `7102d45fe084b9b8850a1cbc54a861a34690d12b` | Backend/frontend/evals/scripts/workflow/Compose không khác baseline main; có khác biệt tài liệu |
| Career `main` | `46a13eae3e508344d6814991e9f241427ee814fe` | Mục tiêu nghề nghiệp và chuẩn evidence, không dùng các trạng thái kỹ thuật cũ thay source mới |
| GitHub issue/PR | Kiểm tra lại ngày khảo sát: 0 issue mở, 0 PR mở | CLOSED/completed và CLOSED/not_planned có ý nghĩa khác nhau |
| Kiến trúc hiện tại | [Báo cáo boundary đã hoàn thành](knora-current-architecture-boundaries-2026-10-05.md) | Chi tiết callers, transaction ownership, F01–F10 và các invariants |

Career xác định hướng **Software Engineer — Backend & AI Systems**, ưu tiên Backend/SWE, Full-stack có backend đáng kể và Applied AI thiên về sản phẩm. Career yêu cầu shipped system, số liệu có thể tái lập, người dùng/đánh giá bên ngoài và khả năng tự giải thích, sửa, debug đường chạy chính. Nguồn: [Targeting Strategy](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Job-Search/Targeting-Strategy.md), [Ship-First Standard](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Roadmaps/Internship-Ship-First-2026.md), [Skill Matrix](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Skills/Market-Skill-Matrix-2026.md).

Quy định Career cập nhật 2026-10-02 yêu cầu chuyển Nice-to-Have của JD mục tiêu thành **học → bài thực hành có giới hạn → kiểm tra/đo → evidence**. Nếu có lý do kiến trúc, tích hợp vào sản phẩm; nếu chưa có lý do, giữ như lab cạnh dự án. Vì vậy, kết luận “chưa cần migration Qdrant” vẫn phải kèm cách chứng minh thực hành Qdrant. Nguồn: [Target-JD Nice-to-Have Coverage Rule](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Roadmaps/Internship-Ship-First-2026.md).

Kế hoạch Career mong muốn flagship KittaChat + Knora, với hợp đồng xác thực, idempotency, traceability và failure isolation; first slice không ngầm mở M4 write authority. Knora vẫn có Workspace/Conversation/DB riêng; tích hợp qua hợp đồng không làm Knora trở thành module sở hữu dữ liệu KittaChat. Nguồn: [Integrated Flagship Plan](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Roadmaps/Integrated-Flagship-Execution-2026.md), [ownership hiện tại](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/CONTEXT.md#L7).

**Cần tránh dùng snapshot Career cũ như release ledger:** `Projects/KnoraAgent.md` còn ghi M5.4 mở và CI vắng mặt ở lần kiểm tra trước. Issue #92 hiện CLOSED/completed; tree hiện có workflow Prettier. Roadmap Knora cũng còn đoạn mô tả các kế hoạch public demo trong #101, trong khi #101 đã CLOSED/not_planned. Đây là lệch tài liệu/tracker, không chứng minh public demo đã ship. Nguồn: [Career project snapshot](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Projects/KnoraAgent.md), [#92](https://github.com/NhiBuaa/knora-agent/issues/92), [workflow](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/.github/workflows/frontend-formatting.yml), [#101](https://github.com/NhiBuaa/knora-agent/issues/101). Không sửa Career hoặc đổi tracker trong lượt này.

Career là repo private. Các đường dẫn Career là nguồn định hướng cho chủ dự án; evidence gửi nhà tuyển dụng cần nằm ở demo/artifacts/repo họ truy cập được, không phụ thuộc vào quyền đọc Career.

### Bản đồ quyết định cho 14 track

Ma trận này là tổng hợp đề xuất; nguồn và lý do nằm trong từng track phía dưới.

| Track | Định hướng cho Knora | Evidence nên tạo |
| --- | --- | --- |
| 1. Current architecture | Giữ authority/identity/transactions; cải thiện các seam có rủi ro cụ thể | Boundary map, characterization tests, ADR cho thay đổi được chọn |
| 2. Reference architecture | Học pipeline/measurement/operations; chọn từng pattern theo nhu cầu | So sánh pin source, một pattern áp dụng có lý do |
| 3. RAG | Giữ native hybrid; đo failure theo từng stage trước thêm rewrite/decomposition | Ablation retrieval → evidence → generation trên bộ dữ liệu cố định |
| 4. Vector | Giữ pgvector làm baseline; Qdrant adapter + benchmark trong lab | Recall/latency/filter/consistency/recovery và báo cáo trade-off |
| 5. Reranking | Ưu tiên thử nghiệm có số liệu; production có điều kiện | Paired nDCG/answer/latency, PyTorch vs ONNX parity |
| 6. GraphRAG | Neo4j lab có multihop gold; chưa đủ bằng chứng tích hợp | Entity/relation provenance, graph vs hybrid baseline |
| 7. Frameworks | Native domain core; LangChain/LangGraph lab theo workflow thật | Native/framework comparison, restart/replay/HITL tests |
| 8. Agent/tools | Bounded read/propose bridge; giữ executor M4 là authority | Task success, bounds, no unauthorized side effects |
| 9. MCP | Consume một read-only integration trước; expose có client/gate riêng | Official client/server interoperability, auth-negative cases |
| 10. Evaluation | Nền tảng để quyết định mọi thay đổi AI | Frozen heldout evaluation, regression artifacts và review |
| 11. Security | Gate trước public ship | Threat model, adversarial corpus, isolation/authority tests |
| 12. Production | Đo failure/recovery, backup và bounded execution | Fault matrix, recovery/restore drill, RPO/RTO có bằng chứng |
| 13. Observability | Đo toàn request, queue và cost; OTel phù hợp seam | Correlated traces/dashboard, load results, accounting rõ unknown |
| 14. Deployment/career | CI sớm, public staging có gate, portfolio dễ kiểm chứng | Release artifact, reproducible deployment, case study và demo |

## Track 1 — Current Knora Architecture

**Câu hỏi cuối:** Knora hiện mạnh/yếu/chật ở boundary nào?

**Trả lời:** Knora mạnh ở ownership, immutable derivations, durable work và side-effect authority. Những seam chật nhất là các consumer read model khác nghĩa nhưng đang dùng chung đường đọc, DB đồng bộ trong orchestration async, generation policy/provenance không đồng nhất và phần vận hành/chất lượng chưa có đủ bằng chứng. Khối lượng file hoặc tên thư mục tự nó chưa phải lý do rewrite. Chi tiết nằm trong [báo cáo boundary](knora-current-architecture-boundaries-2026-10-05.md).

| Boundary | Điểm mạnh đã xác minh | Điểm yếu/chật hoặc điều kiện cần làm rõ |
| --- | --- | --- |
| `answering/` | Orchestrates admission → embedding → retrieval → evidence → validated generation → trace/result | Có sync store calls trong async; calibration/cutover/reembedding cùng namespace nhưng không chứng minh runtime Q&A phụ thuộc chúng |
| Ingestion | Immutable versions/sets; atomic commit/CAS; PDF worker có leases/fencing/retry và resource budget | PostgreSQL/ObjectStore không atomic; reconciler/source retention là correctness, thread detach không phải physical cancellation |
| Retrieval | Workspace/profile/active-set predicates; vector + FTS + deterministic RRF | Chưa có benchmark xác nhận bottleneck; rewrite/rerank/graph cần eval trước |
| Evidence | Pure versioned selection, token/count/overlap budgets | Preserve unique facts và điều kiện khi dedup; không dùng relevance score như semantic truth |
| Generation | Small provider port; aliases và schema/citation validation | Adapter/model prompt khác nhau; structural validity không chứng minh factual correctness |
| Conversations | Idempotent durable Turn; bounded untrusted context; committed-result recovery có consumer port | Reference resolution là heuristic; historical citation/projection semantics và event-loop delay cần characterization |
| Tools | Approval khác dispatch authority; signed resource bindings; provider-first reconciliation | Model-to-tool bridge và MCP chưa hiện diện trong Q&A; M4 hiện là contract/reference provider |
| Auth | Keycloak identity → persisted private Workspace owner; admission trước mutation | BFF refresh coordinator chỉ một Node process; cần gate riêng nếu scale replicas |
| Operator | Workspace/capability guards, sanitized projections, operational snapshots | Evaluation endpoint trả unavailable; historical reader gắn active sets có rủi ro mất old trace sau cutover |
| Provider ports | Embedding role asymmetry và profile/digest identity rõ; generation port nhỏ | Giữ `embed_documents`/`embed_queries`; không ép một generic wrapper làm mất input-role policy |
| DB ownership | Transaction-family stores, shared canonical registry, migration lineage | Shared registry được M2 chấp nhận; generic repository/table-per-service hoặc tách DB có thể phá atomicity |

Nguồn trực tiếp: [AnswerQuestion](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/answering/module.py#L100), [PG retrieval](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/adapters/postgres/answering_store.py#L64), [evidence](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/answering/evidence.py#L44), [worker](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/ingestion/job_processing.py#L988), [Conversation runner](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/conversations/runner.py#L201), [tools executor](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/tools/execution.py#L125), [Workspace authorization](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/access/workspace_authorization.py#L14), [single-process BFF](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/frontend/lib/auth/session-refresh.ts#L11), [Operator historical reader](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/adapters/postgres/evaluation_reader.py#L168), [embedding port](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/providers/embedding.py#L73), [shared registry policy](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/design/milestone-2-module-seams.md#L174).

**Issues hiện tại:** không có backlog đang mở tại snapshot. #115/#136/#138/#140/#142 đã completed, còn #105/#101/#128/#129/#144 not_planned. Vì thế không cần giả định phải “làm hết issue cũ rồi mới refactor”; cần chọn một baseline acceptance mới dựa trên source và các release gates còn hợp lệ. Các ý tưởng đã dừng không trở thành capability được ship. Nguồn: [#105](https://github.com/NhiBuaa/knora-agent/issues/105), [#128](https://github.com/NhiBuaa/knora-agent/issues/128), [#129](https://github.com/NhiBuaa/knora-agent/issues/129), [#144](https://github.com/NhiBuaa/knora-agent/issues/144), [issue snapshot đầy đủ](knora-current-architecture-boundaries-2026-10-05.md).

**Thử nghiệm refactor đầu tiên:** characterize old trace sau activation, fresh/recovered citation equality và async heartbeat dưới DB delay. Tách consumer historical read khỏi evaluator sealed/current-corpus read nếu test xác nhận khác nghĩa. Gate: không đổi citation identity, cross-Workspace denial, Turn fencing và immutable activation semantics. Sau đó mới chốt seam/ADR và implementation plan. Đây là đề xuất từ rủi ro source, chưa phải lỗi đã tái hiện hay thay đổi đã phê duyệt.

**Portfolio:** một case study ngắn trình bày “boundary → lỗi/rủi ro cụ thể → phép kiểm tra → seam mới → behavior giữ nguyên” có thể chứng minh năng lực refactor. Cleanup không có lợi ích correctness/ship hoặc evidence rõ nên có ưu tiên thấp hơn việc đo và ship flagship theo Career.

## Track 2 — Reference architecture: WeKnora, RAGFlow và Haystack

**Câu hỏi cuối:** các hệ thống trưởng thành giải quyết retrieval, agent, storage, observability, deployment thế nào? Knora nên học gì và không nên copy gì?

**Trả lời câu hỏi:** Knora nên học cách làm rõ từng giai đoạn retrieval, giới hạn tài nguyên, kiểm tra evidence và quan sát vận hành. Chưa có cơ sở thay application seams bằng toàn bộ framework hoặc sao chép topology của hệ thống tham chiếu.

Khảo sát tài liệu chính thức ngày **2026-10-05** chọn Tencent/WeKnora cùng **RAGFlow và Haystack**. Đây là bằng chứng về capability của dự án tham chiếu, không phải kết quả benchmark, kiểm toán security hay acceptance của Knora. Latest release đọc qua GitHub API là WeKnora **v0.8.2** (2026-09-24), RAGFlow **v1.0.0-rc1** (2026-09-29), Haystack **v3.3.0** (2026-10-01). Source `main` được pin riêng; không coi mọi capability trên `main` đã có trong release. [WeKnora release](https://github.com/Tencent/WeKnora/releases/tag/v0.8.2), [RAGFlow release](https://github.com/infiniflow/ragflow/releases/tag/v1.0.0-rc1), [Haystack release](https://github.com/deepset-ai/haystack/releases/tag/v3.3.0).

| Reference | Retrieval và agent | Storage, observability, deployment | Bài học có thể áp dụng |
| --- | --- | --- | --- |
| **WeKnora** | Pipeline có query understanding/rewrite, parallel chunk/entity search, rerank, merge, truncation và generation; Q&A và ReAct agent là các chế độ khác nhau | Go app + Python docreader; PostgreSQL/ParadeDB và Redis mặc định; vector/graph/object-store bổ sung qua Compose profiles; Langfuse và task dashboard | Tách raw recall khỏi kết quả sau rerank; dùng source aliases theo request; stage timing và lỗi rõ ràng |
| **RAGFlow** | DeepDoc cho layout/OCR/table, retrieval testing, fused ranking, agentic retrieval nhiều lượt, citation và chunk preview | Snapshot 1.0 dùng Go/DeepDoc trong process, metadata MySQL, document engine, MinIO, Kvrocks, NATS JetStream và ClickHouse; có Compose và HTTP readiness | Debug parsing → chunk → metadata → retrieval trước khi sửa prompt; kiểm tra citation ngay trên source |
| **Haystack** | Library với typed pipeline graph, retriever/joiner/ranker; loops/branches và Agent/tools; RRF là một `DocumentJoiner` mode | DocumentStore qua integration; tracing opt-in và OpenTelemetry integration; ứng dụng sở hữu API, auth, durable state và deployment | Component inputs/outputs rõ; async concurrency có giới hạn; chỉ chọn thư viện cho seam thật sự hưởng lợi |

Nguồn bảng: [WeKnora architecture, SHA bccb4b1](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/website-docs/02-architecture/01-overview.md), [WeKnora RAG pipeline](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/website-docs/02-architecture/04-rag-pipeline.md), [RAGFlow README, SHA 2400ca8](https://github.com/infiniflow/ragflow/blob/2400ca8eb51432b1d304266d0de9ca232d9b53fa/README.md), [RAGFlow deployment](https://github.com/infiniflow/ragflow/blob/2400ca8eb51432b1d304266d0de9ca232d9b53fa/docker/README.md), [Haystack 3.3 pipelines](https://docs.haystack.deepset.ai/docs/pipelines), [joiner](https://docs.haystack.deepset.ai/docs/documentjoiner), [Agent](https://docs.haystack.deepset.ai/docs/agents), [tracing](https://docs.haystack.deepset.ai/docs/tracing).

**Fit/gap:** Knora đã có hybrid PostgreSQL, versioned fusion, Evidence Selection, alias validation, server-resolved citation và durable fenced ingestion. Các ứng viên refactor là retrieval/trace/recovery ownership, generation policy và async DB execution được baseline ghi nhận; thêm pipeline framework không tự giải quyết chúng. [Baseline hiện tại](knora-current-architecture-boundaries-2026-10-05.md).

**Không nên copy:** WeKnora phát references trước streaming completion và bỏ unknown aliases; Knora yêu cầu validate hoàn chỉnh rồi persist trace trước final response, đồng thời phân biệt invalid output với refusal. Haystack có ví dụ loop sửa generation, nhưng contract M1 Knora không cho repair retry. RAGFlow đang chuyển implementation sang Go, nên diagram Python/Redis cũ không mô tả release khảo sát. Không thay policy Knora vì reference làm khác; cũng không thêm Redis, graph DB hoặc nhiều service chỉ để giống topology. [WeKnora citation/stream pipeline](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/website-docs/02-architecture/04-rag-pipeline.md), [Knora generation/delivery](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L730), [Haystack loops](https://docs.haystack.deepset.ai/docs/pipelines).

**Thí nghiệm nhỏ:** làm một seam scorecard cho năm chặng `retrieve → rank → select evidence → generate → validate/cite`; chọn một capability mới như reranker để lập hai change maps: giữ port Knora và dùng library adapter. Characterize timeout, provider error, stale activation, invalid alias và historical citation trước khi chọn design. Đếm số callers phải biết storage/model, transaction boundaries bị thay, dependencies phải vận hành và số điểm policy bị lặp. **Go** khi lựa chọn giảm knowledge của caller mà giữ toàn bộ invariants; **no-go** khi framework chỉ bọc thêm hoặc yêu cầu giao ownership DB/citation cho framework. Đây là design evidence, chưa phải acceptance runtime.

**Portfolio:** một architecture decision có rejected alternatives, contract tests và correlated trace của capability thực sự shipped có giá trị hơn danh sách framework. Haystack có thể là lab adapter hữu ích; không cần đưa cả ba reference vào runtime.

## Track 3 — RAG architecture: nâng retrieval ở đâu?

**Câu hỏi cuối:** RAG hiện tại đã đủ chưa? Cần nâng retrieval ở đâu?

**Trả lời câu hỏi:** nền correctness đã khá đầy đủ; chất lượng đáp ứng use case và production SLO chưa được chứng minh đầy đủ. Hybrid/RRF hiện có không phải gap cần xây lại. Nâng retrieval theo failure taxonomy: thiếu source/chunk, branch miss, fusion rank, Evidence Selection, rồi mới generation.

Baseline đã xác nhận Workspace/active/profile filtering trong từng branch, deterministic RRF, bounded evidence, version-pinned citations và trace provenance; chưa có query rewrite/decomposition hoặc reranker trong runtime được khảo sát. Production V2 và các evaluation trials có provenance riêng; không suy một trial thành chất lượng production profile hiện tại. [Baseline](knora-current-architecture-boundaries-2026-10-05.md), [Knora retrieval policy](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L650).

| Kỹ thuật | Khi có lý do thử | Guardrail của Knora |
| --- | --- | --- |
| **Query rewrite** | Follow-up có đại từ, tên viết tắt hoặc câu hỏi thiếu chủ thể | Original question vẫn là answer intent; history là untrusted context; version rewrite prompt/model, giới hạn input/output, timeout và route |
| **Query expansion** | Gold evidence bị lexical/semantic miss vì nhiều cách diễn đạt | Giữ original query; cap số variants và tổng candidates; dedup bằng Chunk ID; ghi provenance mỗi variant |
| **Decomposition** | Câu hỏi so sánh hoặc cần facts từ các nguồn khác nhau mà một query không lấy đủ | Tối đa 2–3 subqueries trong lab; hợp nhất **source chunks** làm evidence; subanswers/generated text không thành authority |
| **Hybrid/fusion** | Eligible union có gold nhưng top ranks thiếu gold | Tune branch budgets/lexical policy trước; version weights/tie-breaks; RRF không phải calibrated confidence |
| **Context expansion** | Fact mất do page break hoặc chunk quá nhỏ | Lấy source chunks có identity riêng; vẫn count/token budget; thay page-bounded chunking cần quyết định mới và derivation version |
| **Rerank** | Gold đã trong candidate pool nhưng Evidence Set chọn sai | Thử track 5; giữ pre/post-rank observations và canonical IDs |

Rewrite và decomposition khác mục đích: rewrite làm câu hỏi tự đủ nghĩa; decomposition tách thông tin cần tìm. WeKnora thể hiện các stage rewrite/search/rerank riêng. Haystack đưa decomposition vào pipeline retrieval/subquestions; cách reasoning của ví dụ cần điều chỉnh để Knora chỉ cite source evidence. RAGFlow nhấn mạnh kiểm tra nội dung đã parse/chunk đúng trước khi tune retrieval. [WeKnora query pipeline](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/website-docs/02-architecture/04-rag-pipeline.md), [Haystack decomposition của tác giả framework](https://haystack.deepset.ai/blog/query-decomposition), [RAGFlow retrieval testing](https://github.com/infiniflow/ragflow/blob/2400ca8eb51432b1d304266d0de9ca232d9b53fa/docs/guides/dataset/retrieval_testing.md).

**Thí nghiệm nhỏ:** đầu tiên annotate khoảng 20 lỗi trên development cases bằng taxonomy Knora; chỉ chọn **một** intervention từ lỗi lớn nhất. So sánh baseline với rewrite hoặc bounded decomposition qua cùng public Q&A seam, corpus và exact trace correlation; không đổi model, chunking và ranking đồng thời. Nếu parser bỏ fact hoặc evidence token budget loại fact, rewrite không phải remedy trực tiếp. [Failure taxonomy và measurement governance](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L779).

### Contract đo chung cho các lab 3–6

Các con số sau là **đề xuất lab để chốt trước chạy**, không thay acceptance gate hiện có:

- Tách development tuning khỏi một tập **ít nhất 50 cases mới, held-out, frozen**; ghi cả denominator từng category. `m3-dataset-v1` đã development-exposed, dùng regression/development comparison, không evidence cho unbiased improvement. Freeze source bytes, Chunk Set bindings, embedding profile/model digest, generation/scorer/prompt, Git SHA và hardware/runtime.
- Paired runs chỉ đổi intervention được khai báo. Thiết lập có seal, active corpus closure và post-run drift check. Algorithm lab có thể dùng frozen artifacts để khám phá; core claim phải đi qua public production seam/correlated trace đúng contract. Báo execution/observation errors riêng, không biến thành zero quality hoặc bỏ im lặng.
- Retrieval dùng Recall@8 và MRR đúng existing definition; refusal không vào recall denominator. Nếu thêm **nDCG@8**, cần metric contract mới: gold grades `2 = trực tiếp support fact`, `1 = context liên quan`, `0 = không liên quan`; `DCG@8 = Σ(2^grade−1)/log2(rank+1)`, chia ideal DCG; ideal DCG bằng 0 thì không áp dụng. Đóng băng grades và tie policy trước chạy; không đổi historical M3 reports.
- Tách **candidate recall**, evidence fact coverage, required-fact answer correctness, semantic citation entailment và refusal correctness. Scorer citation chỉ thấy public answer/citation excerpts theo contract; source oracle/full text dùng cho retrieval gold và fact coverage, không lén đưa vào citation scorer.
- Báo paired deltas và confidence interval, breakdown lỗi, p50/p95 riêng cho từng stage và end-to-end, token/cost, peak RAM/VRAM và timeout rate. Các aggregate/CI là lab metric version mới cần chốt; current M3.2 không tự cấp authority cho latency aggregation.
- Security/citation structure/provenance phải **100%**, zero cross-Workspace hoặc inactive/wrong-profile candidates. Không có numerical gain bù cho lỗi authority. Gate quality đề xuất cho query intervention: Recall@8 tăng ít nhất **5 điểm phần trăm**, CI của delta không chứa 0, không giảm citation/refusal guardrails; chi phí và p95 nằm trong budget owner chốt trước. Nếu tập quá nhỏ làm CI không rõ, kết quả là inconclusive.

Nguồn constraints: [Knora evaluation governance](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L779), [canonical evaluation identities/semantics](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/CONTEXT.md#L327). Gate số và cách nDCG/CI trên là **suy luận thiết kế thí nghiệm**, chưa được repository duyệt.

Ngưỡng 50 cases là mức tối thiểu theo policy portfolio của repository, không chứng minh statistical power hoặc tính đại diện. Cần thiết kế sample size/source families theo effect và uncertainty muốn đo; hàng trăm paraphrases từ một PDF không trở thành hàng trăm nguồn độc lập. Các ngưỡng 5 điểm phần trăm, 30%, 0.05, 500 ms và 10 điểm phần trăm phía dưới chỉ là **ví dụ để đăng ký trước**, không phải SLO/acceptance đã duyệt; chốt theo baseline/use case trước candidate run, không sửa ngưỡng sau khi xem kết quả.

**Portfolio:** ưu tiên một retrieval improvement có ablation, held-out evidence và error analysis. Các trục tokenization, similarity, ranking, inference và evaluation trực tiếp hợp nhóm Must Have trong JD AI Engineer Intern được user dẫn; framework/tool keywords là Nice to Have. [JD chính chủ Innotech](https://innotech-vn.com/career/ai-engineer-intern/).

## Track 4 — Vector retrieval: pgvector, Qdrant và landscape

**Câu hỏi cuối:** có vấn đề production nào buộc Knora rời pgvector không? Nếu thử Qdrant thì adapter/benchmark hay migration?

**Trả lời câu hỏi:** chưa có performance, cardinality hoặc deployment evidence buộc Knora rời pgvector. Bước hợp lý cho Qdrant là **bounded adapter/benchmark lab**, sau đó mới quyết định có cần migration. Giá trị học Qdrant cho career vẫn đáng theo đuổi dù core chưa cần đổi.

| Lựa chọn | Capability chính thức đáng xét | Fit và cost với Knora |
| --- | --- | --- |
| **PostgreSQL/pgvector** | Exact search mặc định; HNSW/IVFFlat; iterative scan cho filtered ANN; SQL joins và PostgreSQL FTS | Giữ activation, profile, tenant và retrieval trong cùng DB snapshot; đo/tune query plan trước khi tách storage |
| **Qdrant** | Payload filtering/index, tenant field/index; dense/sparse/multivector và multi-stage Query API; distributed replication/sharding | Hợp lab filtered search và dedicated serving; thêm network, sync/deletion/recovery và consistency contract với authoritative PG |
| **Milvus** | Dense/sparse, BM25 full-text; kiến trúc tách storage/compute và nhiều deployment modes | Đáng khảo sát khi cần scale và topology tương ứng; không có số liệu Knora chứng minh lợi ích vận hành phân tán |
| **Weaviate** | BM25 + vector hybrid; `relativeScoreFusion`/`rankedFusion`; tenant shards | Thuận tiện cho object/hybrid/tenant use cases; fusion semantics và operational model khác PG, cần policy/mapping rõ |

Nguồn: [pgvector v0.8.7 README](https://github.com/pgvector/pgvector/blob/v0.8.7/README.md), [Qdrant multitenancy](https://qdrant.tech/documentation/manage-data/multitenancy/), [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/), [Milvus overview](https://milvus.io/docs/overview.md), [Milvus architecture](https://milvus.io/docs/architecture_overview.md), [Weaviate hybrid](https://docs.weaviate.io/weaviate/concepts/search/hybrid-search), [Weaviate tenants](https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy).

**Hai chi tiết dễ làm benchmark sai:** pgvector HNSW có thể filter sau physical index scan, dù SQL predicates vẫn nằm trong search query; iterative scan/partition/index choices ảnh hưởng filtered recall. Đây không cho phép retrieve toàn cục rồi lọc tại application. Qdrant hiện có RRF với `k` mặc định **2**, trong khi Knora `rrf-v1/v2` dùng **60** và deterministic Chunk-ID tie-break. Phải kiểm tra cả rank origin, công thức/normalization và ties; chỉ đặt cùng `k` chưa chứng minh tương đương. Weaviate default relative-score fusion cũng không tương đương Knora. Đổi DB đồng thời đổi sparse/BM25/fusion là benchmark một retrieval system khác, không chứng minh storage nhanh hơn. [pgvector filtering](https://github.com/pgvector/pgvector/blob/v0.8.7/README.md#filtering), [Qdrant RRF](https://qdrant.tech/documentation/search/hybrid-queries/), [Knora fusion semantics](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L650).

**Thí nghiệm nhỏ:** pin Qdrant **v1.19.1** và clients; export một frozen, non-secret, profile-compatible corpus projection. Giữ PostgreSQL source of truth; external point ID ánh xạ về canonical Chunk/Embedding Set identity. So sánh PG exact, PG tuned ANN và Qdrant ANN trên cùng dense vectors/metric/filter/top-k trước; hybrid riêng giữ lexical/fusion policy tương đương hoặc công khai đổi policy. Dùng corpus thật cho quality, generated scale copies chỉ cho load: ví dụ 10k/100k/1m vectors và concurrency 1/8/32 nếu hardware budget cho phép. Có nhiều Workspace lệch cardinality, rare matches, inactive versions, wrong profiles và archive/deletion cases. [Qdrant release](https://github.com/qdrant/qdrant/releases/tag/v1.19.1).

**Go/no-go:** đo Recall@8 so với exact gold, p95 theo filter selectivity/concurrency, ingestion throughput, index-build time, RAM/disk, restore time và projected operating cost. Ví dụ gate lab chốt trước: ANN recall ≥ **0.95** so với exact, p95 giảm ≥ **30%** tại **workload mục tiêu đã chọn**, correctness giữ 100%; gate này không phải SLO production hiện tại. Nếu PG tuned đáp ứng workload/cost hoặc lợi ích Qdrant chỉ xuất hiện ở scale không dự kiến, giữ PG core và publish lab result. Không gắn số triệu vectors chung chung với một ngưỡng migration.

**Nếu sau đó tích hợp live:** cần authority design riêng cho durable projection publication, activation generation, idempotent replay, reconciliation và rollback. Mỗi search branch phải có server-derived Workspace **và authoritative eligible active/profile scope trước ranking/limit**. Payload `is_active` bị replication lag không đủ làm authority; hậu kiểm PG chỉ là defense bổ sung, không thay prefilter contract. Một phương án cần đánh giá là pinned eligible manifest/snapshot hoặc generation-scoped projection với admission fail-closed khi chưa đồng bộ. Qdrant read/write consistency và ordering chỉ điều khiển Qdrant replicas; không tạo atomic transaction với PostgreSQL. Không đồng nhất Qdrant ack với Ingestion Job success/activation. [Qdrant consistency](https://qdrant.tech/documentation/scaling/consistency-guarantees/), [Knora active state](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L142), [required branch predicates](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L650).

**Core priority: thấp cho migration hiện tại. Career lab priority: cao, phạm vi có giới hạn.** Portfolio artifact nên là adapter contract, reproducible filtered-search benchmark và failure/recovery note với negative result cũng được báo. Qdrant là Nice to Have cụ thể trong JD, không phải lý do bỏ PG authority. Milvus/Weaviate giữ ở comparison note cho tới khi có câu hỏi khác biệt cần đo. [JD](https://innotech-vn.com/career/ai-engineer-intern/).

## Track 5 — Reranking/ML: PyTorch, Transformers và ONNX

**Câu hỏi cuối:** reranker có cải thiện measurable Recall/nDCG/answer quality đủ để đáng thêm không?

**Trả lời câu hỏi:** chưa có paired evidence cho thấy reranker cải thiện Knora đủ để tích hợp. Đây là ứng viên lab có ưu tiên cao vì nối retrieval evaluation với deep-learning inference; core adoption phụ thuộc gain trên held-out và latency/cost budget.

Cross-encoder nhận `(query, passage)` cùng lúc và chấm relevance; bi-encoder embed hai phía riêng để tìm nhanh. Reranker thích hợp cho candidate pool hữu hạn, không search toàn corpus. Nó không đưa gold chunk bị miss vào pool: với cùng pool, **recall của toàn pool không đổi**; Recall@8, nDCG@8 và evidence coverage có thể đổi vì thứ tự/top-k đổi. [Sentence Transformers retrieve/rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).

**Fit/gap:** đặt bounded rank step sau eligible hybrid candidates, trước Evidence Selection; chưa viết một generic model-routing subsystem. Port đề xuất trả canonical candidate IDs, rank scores và model/runtime provenance; application sở hữu identity, deterministic ties, evidence budgets và citation. Khả năng lỗi cần typed policy rõ: timeout/provider error không tự thành insufficient-evidence refusal hoặc silent fallback. Đây là interface cần design approval, không phải port hiện có.

**Thí nghiệm nhỏ:** chọn một multilingual cross-encoder, ví dụ **BAAI/bge-reranker-v2-m3**. Card chính chủ có Transformers `AutoTokenizer`/`AutoModelForSequenceClassification`, PyTorch `eval`/no-grad, paired tokenization, truncation và logits; score qua sigmoid vẫn không thành xác suất evidence sufficiency được calibrated cho Knora. Nhãn multilingual không chứng minh chất lượng tiếng Việt của corpus này. Pin model commit, tokenizer, max sequence length, precision, pair batch size và hardware; không fine-tune trong lượt đầu. [BAAI model card](https://huggingface.co/BAAI/bge-reranker-v2-m3), [Transformers inference](https://huggingface.co/docs/transformers/main/tasks/sequence_classification).

Thiết kế ablation **2 × 2**: current branch budgets 8 so với proposed wider budgets (ví dụ 32); mỗi mức chạy RRF-only và RRF + reranker. Giữ cùng eligible pool trong cặp để tách ranking gain khỏi gain do over-retrieval. Frozen corpus, aliases/citations, generation và Evidence Selection giữ nguyên. Trace phân biệt pre-rerank fused order với post-rerank order; không đổi nghĩa historical `final_rank` âm thầm. Đo lỗi truncation khi query và passage dài; 650 tokens theo chunk tokenizer có thể vượt cap của reranker tokenizer.

**Go/no-go đề xuất:** nDCG@8 tăng ≥ **0.05 tuyệt đối**, paired CI không chứa 0; required-fact correctness hoặc evidence coverage có improvement đã khai báo; Recall@8/citation entailment/refusal không regression vượt policy; structural authority 100%. Ví dụ budget lab cho CPU rerank p95 ≤ **500 ms** với pool đã chọn, cùng peak RAM và concurrency budget đã chốt; thay budget trước run nếu target hardware khác. Không integrate chỉ vì retrieval score tăng mà public answer quality đứng yên hoặc latency vượt budget. Báo riêng warm/cold start và contention với local generation/embedding.

**ONNX sau baseline:** Sentence Transformers hỗ trợ PyTorch, ONNX, OpenVINO và export/optimization/quantization. Chọn ONNX khi đo cho thấy inference bottleneck trên target CPU; không coi acceleration luôn thắng. So sánh cùng checkpoint/tokenizer/activation; kiểm tra numeric score drift và ranking inversions, nDCG/citation/refusal regression, warm-up, batch/sequence lengths và artifact checksum. Export một lần trong build/lab, không export lúc request. [Cross-encoder efficiency](https://sbert.net/docs/cross_encoder/usage/efficiency.html).

**Portfolio:** PyTorch/Transformers inference thực sự với ablation, profiling, ONNX parity và trade-off report chứng minh hiểu AI systems mà không cần làm training research. **Core priority: trung bình, nếu ranking failure có headroom. Career lab priority: cao**, sau baseline evaluation; chỉ một model/runtime baseline rồi một optimization đủ tạo câu chuyện có chiều sâu.

## Track 6 — GraphRAG, Neo4j và entity resolution

**Câu hỏi cuối:** corpus/use case của Knora có thực sự cần multi-hop relationship retrieval không?

**Trả lời câu hỏi:** chưa có bằng chứng corpus/use case Knora thực sự cần multi-hop relationship retrieval. Category `multi_source` chỉ chứng minh cần nhiều nguồn, không tự chứng minh cần graph. GraphRAG/Neo4j đáng một lab giới hạn cho career; đưa vào core chỉ sau khi chứng minh câu hỏi relationship mà hybrid + decomposition chưa giải quyết đủ.

Phân biệt ba nhu cầu:

1. **Entity/relationship lookup:** “dịch vụ A phụ thuộc B; B do nhóm nào vận hành?” cần paths và facts có nguồn.
2. **Microsoft GraphRAG local:** mở rộng entities liên quan sang relations và source text units.
3. **Microsoft GraphRAG global:** trả câu hỏi tổng quan corpus bằng community reports và map-reduce; khác với chỉ thêm Neo4j vào vector RAG.

Microsoft pipeline extract entities/relations/claims, community detection và summaries; output mặc định gồm Parquet và configured vector store, nên library GraphRAG không mặc nhiên yêu cầu Neo4j. Global search tốn tài nguyên; hướng dẫn chính chủ cảnh báo indexing có thể tiêu thụ nhiều LLM resources. Neo4j phù hợp graph persistence/traversal và có KG builder; đó là capability riêng với graph algorithm/pipeline. [GraphRAG index](https://microsoft.github.io/graphrag/index/overview/), [local](https://microsoft.github.io/graphrag/query/local_search/), [global](https://microsoft.github.io/graphrag/query/global_search/), [resource guidance](https://microsoft.github.io/graphrag/get_started/), [Neo4j KG builder](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html).

**Fit/gap và correctness:** graph là derivation từ immutable Document Version/Chunks, không là ownership hoặc source truth mới. Mỗi entity mention và relation phải có Workspace, source Chunk/version, extractor/schema/prompt version và qualifiers như thời gian/phủ định. Traversal phải bắt đầu và mở rộng trong authoritative active scope trước rank; không đi qua hidden/archive/wrong-Workspace nodes rồi lọc cuối. Public citation vẫn quay về source chunks có evidence aliases; summary/community report chưa có citation derivation contract không được thay source evidence. Việc persist graph/projection/retention là domain decision mới, chưa được baseline duyệt. [Knora identity/evidence authority](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/CONTEXT.md#L16).

**Entity resolution là risk lớn:** Neo4j builder mặc định có bước merge nodes cùng label/name. Quy tắc này không tự giải quyết aliases, tên trùng, sản phẩm khác phiên bản hoặc entity cùng tên ở hai Workspaces. Lab cần schema/key có Workspace và entity type, explicit alias decisions, confidence/ambiguity handling, reversible provenance và manual gold resolution. Không dùng similarity/name match một mình làm merge authority. [Neo4j resolution behavior](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html#skip-entity-resolution).

**Thí nghiệm nhỏ theo hai bước:** lấy 10–20 tài liệu support/architecture có relations thật; annotate gold entities, edges, source chunks và 20–30 relationship questions trong development lab. So sánh hybrid, hybrid + bounded decomposition, và **gold graph oracle** trước để đo headroom; graph đơn giản có thể thử bằng PostgreSQL edge table/joins. Nếu oracle không vượt baseline rõ, dừng core route; vẫn hoàn tất lab learning/evidence. Nếu có headroom, dùng Neo4j trên cùng graph rồi thêm một extractor, tối đa hai hops/fan-out/token budget đã chốt. So sánh gold graph với extracted graph để phân biệt retrieval gain và extraction/merge error. Dùng contract held-out ≥50 cases ở mục 3 trước semantic portfolio/core claim; tập nhỏ ban đầu chỉ là feasibility evidence.

**Go/no-go đề xuất:** held-out relationship required-fact accuracy tăng ≥ **10 điểm phần trăm** so với hybrid + decomposition, CI không chứa 0; structural citation/provenance 100%, semantic source support được đo riêng theo guardrail đăng ký trước; không giảm single-hop/refusal beyond policy; edge precision/recall và false-merge rate công khai; measured extraction cost, refresh/restore time và p95 trong budget owner đã chốt. Cần thử ambiguous aliases, temporal contradiction, activation change, deletion, duplicate extraction và cross-Workspace injection. Nếu graph gain chỉ có với hand-cleaned oracle mà extractor làm mất gain, không tuyên bố GraphRAG solved.

**Core priority: thấp, phụ thuộc relationship use case. Career lab priority: trung bình đến cao nếu JD mục tiêu nhấn Neo4j/graph**, sau eval/rerank hoặc cùng một portfolio slice nhỏ. Deliverables là query suite, gold/extracted graph comparison, entity-resolution errors, reproducible Cypher/query plans và source-citation demo; chưa cần community clustering/global summaries nếu câu hỏi chỉ cần two-hop traversal. Microsoft GraphRAG release khảo sát **v3.2.0**; Neo4j GraphRAG Python **1.22.0**. [GraphRAG release](https://github.com/microsoft/graphrag/releases/tag/v3.2.0), [Neo4j release](https://github.com/neo4j/neo4j-graphrag-python/releases/tag/1.22.0), [JD](https://innotech-vn.com/career/ai-engineer-intern/).

### Nguồn chính và snapshot cho tracks 2–6

- Knora main: **ee7572583d558676c6d75ed266cc4a1f4fe0286d**; baseline đọc từ [báo cáo boundary](knora-current-architecture-boundaries-2026-10-05.md). Không chạy runtime benchmark trong khảo sát này.
- WeKnora main: **bccb4b151bae403508da77fbb174efc79dc47c1a**; [architecture](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/website-docs/02-architecture/01-overview.md), [RAG pipeline](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/website-docs/02-architecture/04-rag-pipeline.md).
- RAGFlow main: **2400ca8eb51432b1d304266d0de9ca232d9b53fa**; [current README](https://github.com/infiniflow/ragflow/blob/2400ca8eb51432b1d304266d0de9ca232d9b53fa/README.md), [Docker guide](https://github.com/infiniflow/ragflow/blob/2400ca8eb51432b1d304266d0de9ca232d9b53fa/docker/README.md), [retrieval testing](https://github.com/infiniflow/ragflow/blob/2400ca8eb51432b1d304266d0de9ca232d9b53fa/docs/guides/dataset/retrieval_testing.md).
- Haystack main: **9983863f36266558ff76212b6a14bc4eb2c6e0ce**; official web docs resolved **3.3** ngày đọc; [pipeline source](https://github.com/deepset-ai/haystack/tree/9983863f36266558ff76212b6a14bc4eb2c6e0ce/haystack/core/pipeline), [DocumentJoiner](https://docs.haystack.deepset.ai/docs/documentjoiner), [human-in-the-loop](https://docs.haystack.deepset.ai/docs/human-in-the-loop).
- Vector landscape: [pgvector v0.8.7](https://github.com/pgvector/pgvector/blob/v0.8.7/README.md); [Qdrant v1.19.1](https://github.com/qdrant/qdrant/releases/tag/v1.19.1) và [consistency](https://qdrant.tech/documentation/scaling/consistency-guarantees/); [Milvus docs](https://milvus.io/docs/overview.md); [Weaviate docs](https://docs.weaviate.io/weaviate/concepts/search/hybrid-search).
- Rerank/inference: [Sentence Transformers retrieve/rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html), [efficiency/ONNX](https://sbert.net/docs/cross_encoder/usage/efficiency.html), [BAAI author model card](https://huggingface.co/BAAI/bge-reranker-v2-m3), [Transformers inference](https://huggingface.co/docs/transformers/main/tasks/sequence_classification). Chưa pin model weight commit vì chưa chạy/model-select lab.
- Graph: [Microsoft indexing](https://microsoft.github.io/graphrag/index/overview/), [local search](https://microsoft.github.io/graphrag/query/local_search/), [global search](https://microsoft.github.io/graphrag/query/global_search/), [Neo4j KG builder](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html).
- Career evidence dùng riêng [JD AI Engineer Intern của Innotech](https://innotech-vn.com/career/ai-engineer-intern/); một JD không đại diện toàn thị trường. Lab career priority là khuyến nghị theo mục tiêu user, không suy ra production necessity.

## Track 7 — LLM frameworks: native, LangChain, LangGraph và AutoGen

**Câu hỏi cuối:** phần nào nên giữ native, phần nào framework giúp giảm complexity hoặc mở capability thật?

**Trả lời:** giữ domain/application authority và cited RAG native. LangChain đáng học qua adapter/lab nhỏ; LangGraph mở capability rõ khi workflow cần state, nhánh, review và resume qua restart. Chưa có evidence để thay Conversation/ingestion durability hiện tại bằng graph runtime.

### Capability đối chiếu từ nguồn chính thức

LangChain cung cấp model/tool abstractions, agent loop và middleware; LangGraph là runtime orchestration mức thấp có state/persistence/streaming và human input, có thể dùng không cần LangChain. `ToolRuntime` giúp inject runtime context/dependencies ẩn khỏi model tool schema; application vẫn phải xác thực nguồn context đó. Nguồn: [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents), [tools/runtime](https://docs.langchain.com/oss/python/langchain/tools), [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview).

Checkpointer lưu state/history và replay. Replay chạy lại nodes sau checkpoint, kể cả LLM/API calls. Durability modes `exit`, `async`, `sync` có trade-off write overhead và intermediate recovery. Rename/remove node hoặc đổi state key/type có thể làm saved/interrupted thread không tương thích; workflow versioning/migration vẫn là trách nhiệm vận hành. Nguồn: [checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers), [graph migrations](https://docs.langchain.com/oss/python/langgraph/graph-api#graph-migrations).

| Giữ native trong Knora | Framework có thể bao ngoài, không thay semantics |
| --- | --- |
| Workspace/resource authorization | Verified principal phải đến từ application, không model arguments |
| Evidence aliases, validation, citations | Framework documents/messages không thành evidence authority |
| Immutable source/derivation/activation | Knora sở hữu identity, retention, CAS và DB transaction |
| Turn admission/claim/lease/fencing/deadline/recovery | Checkpoint không tự cấp publication authority hay chống stale dispatch |
| Proposal/decision/executor/provider reconciliation | Human review không thay current execution authorization |
| Eval seal/provenance/denominator | Framework output validated không có nghĩa semantic acceptance |

Nguồn đối chiếu: [Q&A](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/answering/module.py#L100), [Turn runner](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/conversations/runner.py#L50), [tool authority ADR](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/adr/0015-human-approved-tool-execution-boundary.md#L5).

### Khi nào gain đáng cost?

| Lựa chọn | Gain có thể chứng minh | Cost cần đo/thiết kế |
| --- | --- | --- |
| Native typed orchestration | Ít abstraction mới, cùng lifecycle/trace | Tự xây routing/pause/resume nếu use case tăng |
| LangChain adapter/lab | Model/tool schema, integrations và middleware | Mapping types, behavior/retry defaults, dependency/version cost |
| LangGraph workflow riêng | Branch transitions, checkpoint, human input, restart/resume | Saved state migration/retention, replay effects, hai lifecycle/state stores nếu gắn vào Knora |
| AutoGen hoặc Microsoft Agent Framework | Học agent/team/event hoặc typed workflow | Thêm orchestration stack; multi-agent chưa có first-slice use case |

**Seam ứng viên:** workflow runner nhận/trả Knora types; graph là implementation detail. Domain/public ports không nhận framework message/tool/checkpoint types làm authority. So sánh complexity qua caller knowledge, change surface, ownership, failure modes và dependency operations; không dùng số dòng code đơn thuần.

**AutoGen hiện tại:** README chính thức ghi maintenance mode, community managed và không nhận feature/enhancement mới; Microsoft khuyên new users dùng Microsoft Agent Framework và có migration guide. Vì JD có AutoGen, đọc kiến trúc và một sample nhỏ có thể tạo familiarity evidence; không chọn dependency mới chỉ để thêm tên, cũng không cần triển khai cả AutoGen và LangGraph trong core. Nguồn: [AutoGen README](https://github.com/microsoft/autogen), [Microsoft migration guide](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/).

**Lab đề xuất:** (1) LangChain typed tool calling/structured result tới một authorized read operation; (2) LangGraph `read context → draft → human review → finish`, persistent checkpoint, restart giữa review/resume. Dùng cùng fixtures/adapters với native version. Gate: output contract/authorization tương đương; đo calls/tokens/latency/cost, change surface khi thêm branch và recovery sau restart. Forged principal, cross-Workspace, stale resume, repeated resume không tạo unauthorized result/effect. Portfolio có graph, ADR, comparison và demo restart; chỉ quyết định production integration sau gate.

## Track 8 — Agent/tool architecture: ReAct, tool calling, stateful workflow và HITL

**Câu hỏi cuối:** M4 hiện tại có cần nâng thành agent workflow không? LangGraph có use case thật hay chỉ keyword?

**Trả lời:** M4 không cần một agent loop để các contract đã nghiệm thu tiếp tục đúng. Model-to-tool bridge là capability mới, chưa có trong answering. LangGraph có use case thật nếu cần branching/review/resume; bounded lab giúp chứng minh JD, production phải có workflow cụ thể và authority design.

Tool calling là model sinh structured name/arguments để application xử lý; ReAct xen kẽ quyết định/action/observation; workflow có transitions do application định trước. Paper ReAct không chứng minh quality/safety cho Knora. Nguồn: [ReAct paper](https://arxiv.org/abs/2210.03629), [tool use protocol](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview), [workflows vs agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents).

### Bridge có giới hạn

Đề xuất chỉ cho model chọn `answer`, một allowlisted read operation hoặc `draft proposal`. Server validate schema, resolve resource/binding và current authority; model intent là input candidate. Nếu thêm writes sau này, đường chạy phải giữ:

`candidate → immutable validated proposal → human decision → current executor authorization → fenced dispatch → provider observation/reconciliation`

- Model không cung cấp principal/credential/ownership/signed dispatch envelope.
- Text “user approved” không tạo decision record; edit payload phải có proposal/approval semantics phù hợp.
- Revoked capability, archived Workspace, changed binding, expired decision/lost lease đều chặn dispatch.
- External timeout sau effect không cho free retry; giữ uncertainty và reconcile provider truth.
- Tool observation có resource/provenance/freshness; text trả về không tự thành cited source evidence.

Nguồn baseline: [authorized read](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/tools/read.py#L36), [approved executor](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/tools/execution.py#L125).

### HITL và replay

LangChain middleware có approve/edit/reject/respond; LangGraph `interrupt` có thể chờ vô hạn và resume chạy lại node từ đầu. Side effect trước interrupt có thể lặp. Functional API có completed-task recovery, nhưng started/uncompleted task có thể chạy lại; checkpoint không atomic với external provider. Nguồn: [HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop), [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [functional replay/idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api).

**Đề xuất riêng:** không giữ active Turn lease suốt thời gian human review. Nếu đưa vào production, cần thiết kế trạng thái chờ/admission/resume riêng; graph giữ references tới authoritative records, resume lấy current permission và claim hợp lệ. `recursion_limit` chỉ giới hạn graph super-steps, không thay budgets về calls/tokens/output/time/retry. Nguồn: [recursion limit](https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit).

**Lab:** một model, một read integration, draft/review/final proposal; chưa external write, không multi-agent. Test injected tool text, unknown tool, forged resource, rejected/stale review, repeated resume, restart trước/sau checkpoint, exhausted budget và timeout. Đo task success, selection/argument accuracy, denied attempts, E2E/cost/calls. Native/framework phải cùng expected outcomes. Portfolio gồm bounded execution policy, negative cases và restart demo; điều này chứng minh agent engineering mà không mở rộng first M6 slice sang M4 write.

## Track 9 — MCP và integrations

**Câu hỏi cuối:** Knora nên consume MCP, expose MCP hay cả hai? Authority nằm ở đâu?

**Trả lời:** consume một read-oriented integration trước để học và đo; expose một thin knowledge adapter khi có client/use case thật, hoặc lab riêng. Hai hướng có gates độc lập. Authority vẫn ở Knora application/persisted ownership và provider sở hữu external resource/effect; MCP description, model intent và graph checkpoint không cấp quyền.

### Snapshot protocol và SDK

`latest` được kiểm tra ngày khảo sát trỏ tới **MCP 2026-07-28**: request version/capabilities tự đủ, bỏ initialize/session trên đường protocol mới; Tasks chuyển thành optional extension. Client/server cũ có compatibility concerns cần pin khi implementation. Nguồn: [spec](https://modelcontextprotocol.io/specification/2026-07-28), [key changes](https://modelcontextprotocol.io/specification/2026-07-28/changelog).

Official Python SDK docs đọc được mô tả **v2 stable**, revision mới cùng legacy fallback; Tasks extension mới chưa implement. Đây là trạng thái docs tại ngày đọc, chưa có package/connection này được cài hoặc kiểm tra trong Knora. LangChain MCP docs hiện dùng `MCPAdapter` qua `langchain[mcp]>=1.4.0`, built on FastMCP, beta. Không copy API cũ theo trí nhớ hoặc coi MCP Tasks thay durable Turn. Nguồn: [Python SDK v2](https://py.sdk.modelcontextprotocol.io/whats-new/), [LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp).

| Hướng | Use case | Phạm vi đề xuất |
| --- | --- | --- |
| Consume | Đọc GitHub issue/file hoặc external support context | Một configured resource, read-only tools, typed gateway |
| Expose | IDE/chat/client dùng knowledge query/citation Knora | Adapter mỏng gọi existing use cases, không mở lifecycle/write từ đầu |
| Cả hai | Knora vừa nhận context ngoài vừa phục vụ client | Hai designs/acceptance độc lập |
| Native HTTP | KittaChat authenticated first slice | Vẫn hợp lệ; MCP không là điều kiện shipping |

### Authority và credential/resource binding

Consume cần server-side registry `verified principal/Workspace → external installation/account/resource được phép → credential reference`; provider/MCP server vẫn kiểm tra quyền của credential. Expose validate token rồi resolve identity và gọi cùng application authorization. User/model-supplied Workspace ID, repo/file/ticket ID, URL hoặc state handle chỉ là locator.

HTTP MCP authorization yêu cầu resource indicators/audience binding; token cho Knora không tự thành token cho GitHub/Drive. Security guidance cấm token passthrough và yêu cầu bind state handle với verified principal server-side. Tool annotations untrusted; server validate/access-control/rate-limit/sanitize, client validate result/timeout/audit. Resource URI không chứng minh ownership. Nguồn: [authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), [security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices), [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources).

Nếu import external content thành corpus, đi qua ingestion identity/provenance/ownership. Live observation giữ freshness/access policy riêng. Không truyền nguyên mọi MCP tool vào model rồi dựa vào prompt để cấm mutations.

### Hai lab có thể kiểm chứng

**Consume lab:** official GitHub MCP server, một repository được allowlist server-side, chỉ `issue_read` hoặc `get_file_contents`, scoped read credentials. Server có individual tool allowlist và `--read-only`; lockdown content filtering không phải authorization boundary. Đối chiếu native REST gateway cùng payload để đo adapter effort, provenance/denial parity, schema/discovery context và latency. Nguồn: [GitHub MCP server](https://github.com/github/github-mcp-server).

**Expose lab:** thin knowledge query/citation service với real SDK client; Inspector cho protocol QA. Ghi rõ client thực sự dùng result/citations; `tools/list` screenshot chỉ là protocol discovery evidence. Chưa mở ingestion/lifecycle/dispatch capability ở lab đầu.

**Gate chung:** cross-Workspace/resource denial, forged handle, wrong audience/issuer, expired/revoked credential, scope mismatch, arbitrary endpoints/SSRF, malformed/oversized output, private-cache isolation, injection trong issue/file, timeout/retry và trace correlation. Pin protocol/SDK/toolset; negotiated version ghi vào artifacts. Portfolio gồm client demo, binding/permission matrix, negative cases và native-vs-MCP comparison. Drive/tickets chỉ thêm sau khi một resource binding model đã được chứng minh.

## Track 10 — Evaluation và chất lượng AI

**Câu hỏi: Làm sao chứng minh thay đổi AI tốt hơn bằng số liệu, không phải cảm giác?** Chạy baseline và candidate trên cùng một tập heldout đã đóng băng, qua chính HTTP/Q&A production, rồi so sánh từng case với provenance đầy đủ, guardrail và chi phí. Một điểm tổng hợp hoặc một demo đẹp chưa đủ.

### Knora đã có gì, và chưa chứng minh gì?

Architecture Standard đã quy định correlated `(workspace_id, trace_id)`, corpus seal, immutable dataset/corpus/configuration, Recall@8 và MRR với denominator rõ ràng, paired vector/hybrid runs, tách observation failure khỏi quality miss. Citation có hai tầng: cấu trúc phải hợp lệ; entailment phải chấm từ **public answer và public citation excerpts**, không đưa hidden retrieval chunks cho citation scorer. Đây là nền tảng cần mở rộng, không nên thay bằng dashboard/framework khác rồi bỏ governance. [Knora evaluation governance](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L779).

Bằng chứng lịch sử mới nhất được baseline đọc là một development-exposed seed-105 GPT-OSS two-stage dedup probe đạt 11/11 structural/literal/semantic review; CPU latency 66.702–171.070 giây, median 101.199 giây. Profile này thuộc evaluation, không phải provider production một-stage. Tập đã được dùng để tuning không trở thành heldout chỉ bằng cách đổi tên. Vì vậy **chưa thể nói production AI quality đã được chứng minh**. [Artifact và giới hạn](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/evals/reports/vietnamese_rag_v2/issue105_gptoss_migration_checkpoint.md#L343).

### Thiết kế đo lường đề xuất

1. Tách development/calibration, regression và heldout release; tránh câu hỏi hoặc tài liệu gần trùng qua các split. Giữ bộ tiếng Việt có lexical, paraphrase, multi-source, reference follow-up, thiếu bằng chứng, PDF khó và adversarial input. Domain expert xác nhận gold/required facts; synthetic cases chỉ là một nguồn bổ sung. Chốt manifest/checksum, source SHA, model digest/profile, prompt, corpus, chunking, embedding, retrieval, scorer trước khi chạy. OpenAI cũng khuyến nghị eval theo use case, typical/edge/adversarial cases và human calibration. Các ngưỡng số trong ví dụ của họ **không phải ngưỡng Knora**. [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
2. Đăng ký primary metric và guardrails trước khi xem kết quả. Mỗi thử nghiệm thay một yếu tố hoặc ghi rõ toàn bộ bundle thay đổi; chạy paired cases và giữ failed observations trong báo cáo hệ thống. Với generation ngẫu nhiên, lặp lại có budget đăng ký trước, báo variability. Đề xuất CI cho paired delta bằng resampling theo case/source family phù hợp; SciPy có paired bootstrap, nhưng phương pháp và đơn vị resampling phải được versioned trong metric contract. [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).
3. Đọc lỗi theo stage: corpus/provenance, retrieval branch, fusion, evidence selection, generation, citation, refusal và infrastructure. Chỉ cải thiện metric tổng có thể che regression của multi-source hoặc false refusal.

| Tầng | Metric cần công bố | Giới hạn diễn giải |
| --- | --- | --- |
| Retrieval | Recall@8, MRR hiện có; nDCG@k nếu thêm relevance grading/version mới; evidence coverage | nDCG bổ sung phải có contract mới, không sửa M3 metric lịch sử. BEIR là nguồn tham khảo implementation IR metrics. |
| Answer | Required-fact correctness, faithfulness, relevance | Faithfulness với context khác correctness với sự thật/reference. |
| Citation | Structural validity, semantic entailment, coverage của factual claims | Trace provenance không tự chứng minh citation hỗ trợ claim. |
| Refusal | Correct refusal, false refusal trên answerable cases, unsupported answer trên unanswerable cases | Refusal cases không bị gán zero retrieval recall. |
| Tools | Proposal/argument validity, authorization, đúng external effect và reconciliation | Knora hiện chưa có model-driven tool selection; chỉ đánh giá bridge khi capability này được xây. |
| System | Client E2E, phase timings, provider/error rate, observed tokens, estimated cost | Quality denominator và execution-success denominator phải xuất hiện cùng nhau. |

Nguồn metric: [BEIR](https://github.com/beir-cellar/beir), [Ragas faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/). Có thể dùng Ragas hoặc scorer riêng sau đánh giá compatibility; không có lý do bắt buộc thay harness Knora.

### Gate và portfolio

**Engineering hard gates:** structural invariants 100%, đúng Workspace/provenance, không citation ngoài Evidence Set, không execution/observation failure bị che thành quality score, report lặp lại được. **Semantic gates:** đo baseline trước, đăng ký ngưỡng cải thiện và tolerance regression theo use case trước candidate run; không tự đặt 0.9/95% hoặc “11/11 nghĩa là đạt”. Repo yêu cầu ít nhất 50 cases trước khi claim semantic metric trong portfolio; đó vẫn chưa phải chứng minh production generalization. [Knora gates](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L810).

LLM judge là phép đo cần hiệu chuẩn. Dùng rubric/reference versioned, human-labelled calibration subset, blind/đảo thứ tự pairwise, rà soát disagreement và báo agreement; không gọi judge output là ground truth. Nghiên cứu MT-Bench chỉ ra position, verbosity, self-enhancement bias và giới hạn reasoning. [MT-Bench paper](https://arxiv.org/abs/2306.05685).

CI đề xuất: PR chạy contracts/security và regression nhỏ; release/nightly chạy model-backed paired suite theo budget; heldout chỉ dùng cho quyết định release đăng ký trước, rồi bổ sung bộ mới khi đã exposure. Portfolio artifact nên là dataset card, frozen manifests, per-case paired report/CI, failure annotations, selected-improvement record có latency/cost trade-off. Lưu ý cập nhật 2026-10-05: OpenAI guide hiện thông báo hosted Evals sẽ read-only 2026-10-31 và shutdown 2026-11-30; dùng phương pháp của guide, giữ harness/artifact độc lập vendor. [Thông báo trong guide](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

## Track 11 — Security, privacy và threat model

**Câu hỏi: Public Knora hiện có attack surface nào chưa được kiểm soát?** Source cho thấy các boundary authorization mạnh; khảo sát này chưa có public URL/topology, reverse-proxy policy hoặc runtime adversarial evidence để kết luận một exploit đang tồn tại. Kết luận phù hợp là **có các bề mặt cần chứng minh mức kiểm soát trước public acceptance**, không gán nhãn public vulnerabilities từ khoảng trống tài liệu.

### Boundary hiện mạnh

Backend kiểm chứng issuer/subject rồi persisted Workspace ownership và capability; retrieval áp dụng Workspace/active/profile/archive predicates tại SQL. Tool executor revalidate authority, approval, fencing và provider outcome; prompt/model không sở hữu authorization. [Workspace authorization](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/access/workspace_authorization.py#L14), [retrieval filters](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/adapters/postgres/answering_store.py#L223), [tool authority ADR](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/adr/0015-human-approved-tool-execution-boundary.md#L5).

PDF processing đã có raw/page/decoded-stream/time/memory budgets và process isolation. Không coi mọi PDF như byte upload không được bảo vệ; cần chứng minh hard limit thật trên OS/container deploy. [PDF configuration](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/ingestion/pdf.py#L12), [Windows isolation preflight](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/adapters/cli/worker.py#L66).

### Ma trận kiểm chứng đề xuất

| Bề mặt | Khoảng trống cần kiểm chứng | Control và negative test |
| --- | --- | --- |
| User/PDF/retrieved text/history | Indirect injection, hidden PDF text, instructions giả, poisoned facts | Mọi nội dung này là untrusted data; giữ system/policy và code authority riêng; attack corpus đo cả unsupported claims lẫn attempted disclosure/action. |
| Corpus ingestion | Authorized writer đưa tài liệu sai/độc vào đúng Workspace | Source identity/checksum và immutable version chứng minh lineage, không chứng minh sự thật; cần provenance review, source trust policy và anomaly/quarantine theo use case. |
| Workspace và history/trace/object access | Leak qua alternate route, archived resource, worker race, trace reader/caches | Cross-Workspace negative tests ở từng seam; filters fail closed trước candidate selection; authorization lại khi dispatch side effect. |
| Public resource consumption | Concurrent generation/upload, backlog, token/spend exhaustion | Chưa thấy per-user quota/rate-limiter trong composition đã đọc; kiểm tra proxy/deploy trước kết luận. Đề xuất authenticated quotas, queue/admission bounds, input/token/output caps, overload response và spend budget. |
| Provider/tool networking | User-influenced destination, redirects, private-IP/DNS rebinding khi có URL fetch/MCP | Hiện chưa chứng minh user-controlled URL route. Khi thêm: destination allowlist, connection-time IP validation, egress controls, redirect policy và scoped credentials. |
| Telemetry/export | Query, snippets, answer, PDF/PII, token/session leakage | Default metadata-only telemetry, allowlist/redaction trước mọi exporter, retention/access/deletion policy; protected content store tách observability quyền rộng. |
| Browser/BFF và deployment | Refresh/logout nhiều replica, cookie/TLS/CSRF/CORS/secrets thực tế | Refresh coordination hiện bảo đảm trong một Node process; hai replica cần shared coordination và race acceptance trước rollout. |

OWASP 2025 mô tả prompt injection, poisoning, vector cross-context leaks, excessive agency và unbounded consumption; đây là taxonomy threat model, không phải kết quả scan Knora. [Prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [poisoning](https://genai.owasp.org/llmrisk/llm042025-data-and-model-poisoning/), [vector risks](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/), [resource consumption](https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/). OWASP cũng không coi prompt/filter là bảo đảm tuyệt đối; structured JSON hợp lệ vẫn có thể chứa claim sai hoặc instruction độc.

MCP là phạm vi tương lai trừ khi runtime inventory chứng minh đã có connection. Khi thêm, tool descriptions/results/resources cũng untrusted; validate server identity/token audience, tránh token passthrough/confused deputy, SSRF và cấp quyền tối thiểu. Consent kết nối không thay thế Knora approval từng write action. [MCP security 2026-07-28](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices), [OWASP SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [complete mediation và human approval](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).

**Engineering gates:** mọi unauthorized cross-Workspace/resource/action test bị từ chối; không raw credentials trong response/telemetry; expired/stale approval và worker không publish/dispatch; PDF limit có bằng chứng trên deployment thật; topology auth được xác nhận. **AI adversarial gates:** báo attack-success/false-refusal rate với scope, dataset và uncertainty; đăng ký tolerance trước run, không hứa “immune to prompt injection”. Portfolio: threat model trust-boundary/data-flow, attack/control/evidence matrix, redacted adversarial report, deployment checklist và residual-risk log. [BFF topology limit](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/frontend/lib/auth/session-refresh.ts#L11).

## Track 12 — Production reliability và recovery

**Câu hỏi: Nếu Postgres/provider/worker/vector backend chết thì Knora phản ứng thế nào?** Có durable coordination mạnh cho ingestion và Conversation; chưa có evidence đo outage/restore toàn deployment. **pgvector hiện nằm cùng PostgreSQL 16**, nên DB và vector backend chưa là hai failure domain độc lập. [Compose](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docker-compose.yml#L2).

| Sự cố | Behavior thấy trong source/standard | Acceptance cần bổ sung |
| --- | --- | --- |
| Generation/embedding transport thất bại | Provider adapter dùng timeout và map HTTP failure thành `PROVIDER_REQUEST_FAILED`; HTTP map 502; SSE phát terminal failure event. | Delayed/429/5xx/reset/malformed responses có bounded failure, safe code, accounting và không biến thành `INSUFFICIENT_EVIDENCE`. |
| PostgreSQL down/slow | Retrieval/authorization/trace/claims phụ thuộc PG; sync AnsweringStore trong async Q&A; không có generic ORM outage→503 mapping được chứng minh. | DB delay/disconnect/ambiguous commit, event-loop và heartbeat; đúng unavailable/error contract; không trả answer success trước required durable trace. |
| PDF worker chết/lease mất | Four attempts total; full-jitter windows `[0,5s]`, `[0,30s]`, `[0,2m]`; lease 2m, heartbeat30s, runtime15m; recovery-first, DB-time fencing. | Kill/pause/partition ở claim, extraction, embedding và commit; late result không activate; restart resume và exhaustion đúng. |
| Conversation worker chết | Recovery đọc committed result/trace rồi fenced apply; provider error terminalizes Turn với error code. | Sau trace commit/trước finish không gọi model lần hai; không committed result thì đúng recovery outcome, không mặc định auto-regenerate success. |
| ObjectStore unavailable/missing | Storage transient và deterministic missing/input/config failure có taxonomy riêng; lifecycle delete/reconcile tách DB. | Upload/source-read/delete timeout, orphan và external-delete ambiguity; retained source không bị mất do cleanup race. |
| Vector query/index lỗi | Vector+FTS search chung PG seam/snapshot; không có bằng chứng fallback branch độc lập được nghiệm thu. | Missing extension/index/dimension drift và branch failure phải có explicit policy; không âm thầm đổi hybrid thành lexical/vector-only rồi giữ provenance cũ. |

Nguồn: [provider adapter](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/providers/openai_compatible/generation.py#L19), [HTTP mapping](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/main.py#L378), [SSE](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/answering/module.py#L310), [retry/lease standard](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docs/standards/architecture.md#L226), [Conversation finalize/recovery](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/conversations/runner.py#L157).

Đề xuất dependency policy gồm timeout/deadline budget, capacity isolation, classified retry, backoff/jitter, retry budget và circuit state theo dependency. Chỉ retry operation an toàn với cùng identity/fingerprint; ambiguous side effect giữ indeterminate/reconcile. Coordination-store ambiguous commit không được đổi tên thành business `DATABASE_TRANSIENT`. Invalid model output không “repair retry” để tạo một answer nhìn có vẻ thành công; timeout/refusal/validation failure là ba outcome khác nhau. AWS giải thích retry một nơi để tránh amplification và side effects cần idempotency; circuit breaker cũng có modal behavior cần test, nên không thêm mặc định vào mọi dependency. [AWS retries](https://d1.awsstatic.com/builderslibrary/pdfs/timeouts-retries-and-backoff-with-jitter.pdf), [idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/), [circuit breaker states](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker).

Thread detach/cancel advisory chưa kill external I/O; giữ slot/capacity cho tới khi call physically returns là phần safety hiện có. Fault injection nên chạy môi trường cô lập, có invariant/expected-state, trigger, detector, recovery và evidence cho từng row; không suy test definitions thành test vừa PASS. [Google SRE reliability testing](https://sre.google/sre-book/testing-reliability/).

### Backup/restore phải kiểm tra cả graph dữ liệu

RPO/RTO do owner chọn theo user impact trước drill; hiện chưa có số đo. PostgreSQL PITR cần base backup và continuous archived WAL, còn config files phải backup riêng. DB restore không phục hồi source objects hay external tool ledger. [PostgreSQL16 PITR](https://www.postgresql.org/docs/16/continuous-archiving.html).

Đề xuất restore vào môi trường cô lập: DB+migrations/config, source object bytes/checksums, immutable parser/chunker/embedding/profile identities, model artifacts/configuration cần thiết và identity/authorization mapping. Kiểm tra active pointers, chunks/vector dimensions, retained source, old trace/citation/history, pending jobs/leases và external-tool reconciliation. Không “fix” incompatible vectors bằng activate profile mới sau restore. Reconcile provider outcome từ external authority, không replay mọi tool write từ backup Knora. Đo dữ liệu bị mất, thời gian service sử dụng được và post-restore quality sample; backup success không đồng nghĩa restore success. Portfolio: failure matrix, fault-injection evidence, restore drill có measured RPO/RTO, runbook và residual risks.

## Track 13 — Observability, SLO, performance và cost

**Câu hỏi: Production có đo được một request từ đầu đến cuối, bottleneck, quality và cost không?** Hiện đo được một phần answering qua Question Trace và operational snapshots. Chưa có evidence full BFF→API→async worker→DB/provider/tool distributed trace, production SLO/load acceptance hoặc complete cost ledger.

### Khoảng trống cụ thể từ source

Question Trace ghi retrieval/evidence/embedding/generation timing, provider/model/prompt, usage/cost khi adapter cung cấp. Tuy nhiên `trace_ended` được lấy **trước** `persist_trace`; trace latency không bao gồm trace commit và không phải client E2E. SSE hiện stream stage events và validated final result, nên first event không là model TTFT. Operator evaluation endpoint cố ý trả unavailable, chưa là persisted evaluation report reader. [Trace metadata/timing](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/answering/module.py#L276), [trace construction](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/answering/module.py#L438), [evaluation unavailable](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/adapters/postgres/operator_reader.py#L20).

OpenAI-compatible adapter tính cost từ usage×configured prices và dùng `usage.get(...,0)`; thiếu usage có thể ra amount0 mặc dù quantity chưa biết. Đây là risk về measurement semantics từ code, chưa phải runtime billing incident được tái hiện. Ollama ghi token counts khi có, không có invoice cost. Cần `unknown != 0`, `estimated != actual`. [Cost calculation](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/providers/openai_compatible/generation.py#L80), [Ollama usage](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/src/knora/providers/ollama/generation.py#L150).

### Instrumentation đề xuất

Dùng OTel cho HTTP/BFF/API, auth/admission, queue wait, Conversation attempt, embedding, vector/FTS/fusion/evidence, generation/validation, trace commit và tool dispatch/reconciliation. Persist/propagate trace context qua durable queue; worker span có parent/link phù hợp với deferred execution và từng attempt. Giữ domain `trace_id`, Turn/job/action IDs và OTel trace ID có mapping rõ; tracing context không thành authorization. OTel có W3C context propagation, producer/consumer kinds và span links. [Propagation](https://opentelemetry.io/docs/concepts/context-propagation/), [Trace API](https://opentelemetry.io/docs/specs/otel/trace/api/).

Lưu ý version: GenAI conventions đã chuyển sang repo riêng; current client spans vẫn mang status Development. Pin SDK/instrumentation/schema mapping và document upgrade, không tuyên bố mọi `gen_ai.*` đã stable. Logical GenAI span bao gồm retry; nội dung input/output mặc định không capture. [Official GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md).

Langfuse là optional sink để đọc generations, prompt versions, scores và cost; không sở hữu Workspace authorization hay durable operational truth. Có thể export OTel vào OTLP endpoint của Langfuse sau compatibility test; cloud/self-host cần independent access, retention và region decision. Masking phải xảy ra trước mọi exporter: hook Langfuse không mask copy đi exporter khác. [Langfuse OTel](https://langfuse.com/integrations/native/opentelemetry), [masking](https://langfuse.com/docs/observability/features/masking).

### Dashboard và gates

- **User outcome/SLI:** valid answer hoặc đúng refusal; provider/unavailable/invalid-output là technical failures riêng. False refusal là quality issue. Định nghĩa denominator, latency boundary, window, overload/cancellation policy trước SLO; không chọn 99.9% từ cảm giác. Đo baseline rồi owner duyệt objective/error budget. [Google SRE SLOs](https://sre.google/workbook/implementing-slos/), [SLO alerting](https://sre.google/workbook/alerting-on-slos/).
- **Latency/capacity:** client E2E, queue age, job time-to-ready, p50/p95/p99, phase share, throughput, concurrency, DB pool waits, CPU/memory, event-loop/heartbeat và provider saturation. Báo sample size, workload/corpus/model/hardware, warm/cold conditions; 11 requests không tạo bằng chứng tail-latency đáng tin. Giữ histograms, không average các percentiles. [Google monitoring](https://sre.google/workbook/monitoring/).
- **Quality:** liên kết offline paired reports/versioned scores với đúng request/profile; production sample review và feedback không tự là gold labels. Operator historical trace reader cần immutable provenance semantics để đọc sau corpus activation mới.
- **Cost:** provider-reported usage, billed/estimated tokens, cache/reasoning categories, pricing version, currency và reconciliation với bill tách riêng. Tính cả embedding/ingestion, retry/failed calls và eval judge; local model cần CPU/GPU/runtime cost, không gán zero vì không có token invoice. Langfuse phân biệt ingested/inferred cost và cảnh báo double counting overlapping buckets. [Token/cost tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking).
- **Privacy/cardinality:** raw question/snippet/output/credentials không làm metric label hoặc baggage. IDs ở protected spans/logs; metric labels bounded theo route, stage, outcome, provider/profile. Minimize/redact trước export, monitor dropped spans/cardinality overflow. [OTel privacy](https://opentelemetry.io/docs/security/handling-sensitive-data/), [cardinality limits](https://opentelemetry.io/docs/specs/otel/metrics/sdk/#cardinality-limits).

Engineering gates đề xuất: một request/async job nối được các boundary; failure trước domain trace vẫn có operational error/span; exporter down không làm hỏng business request; redaction áp dụng mọi sink; metrics không double-count; synthetic slow dependency xuất hiện đúng bottleneck. Performance/quality/cost gates cần baseline và budget đăng ký trước. Portfolio: trace walkthrough đã redact, dashboard/SLO document, reproducible load report, cost accounting examples và một investigation từ alert→bottleneck→verified fix. Đây là đề xuất research; lượt này chưa chạy các acceptance đó.

## Track 14 — Deployment, SDLC và evidence để apply jobs

**Câu hỏi cuối:** còn thiếu gì để vừa deploy thật vừa tạo recruiter-readable evidence?

**Trả lời:** thiếu một release baseline gắn code/model/corpus, CI kiểm tra correctness ngoài format, môi trường staging tái lập có security/recovery/cost gates, phép đo trên đường người dùng thật và evidence trình bày ngắn. Framework breadth không thay được các đầu ra này. Đồng thời, Nice-to-Have của JD mục tiêu vẫn cần bài thực hành có giới hạn để chứng minh familiarity.

### 14.1. Đối chiếu source, CI và deployment hiện tại

Tree khảo sát chỉ có `.github/workflows/frontend-formatting.yml`: `npm ci` và `format:check` trên PR/push vào main, permissions `contents: read`, Node 22. Workflow này bảo vệ format frontend; không chạy pytest, Ruff, TypeScript, Vitest, build, E2E hay AI eval. Source đã có các command/test infrastructure nên có thể bổ sung CI từng lớp. Nguồn: [workflow](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/.github/workflows/frontend-formatting.yml), [frontend commands](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/frontend/package.json), [backend tooling](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/pyproject.toml).

Backend Dockerfile dùng `python:3.12-slim` và `pip install .`; dependencies đa phần là version ranges. Compose cung cấp local PostgreSQL/pgvector, MinIO/API và acceptance-test services. Có fixture/test services trong Compose không có nghĩa chúng nên được expose trong public topology. Survey không tìm thấy Terraform/Pulumi manifests hay release image/SBOM workflow trong tree, và README không claim hosted production. Nguồn: [Dockerfile](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/Dockerfile), [dependencies](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/backend/pyproject.toml#L9), [Compose](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/docker-compose.yml), [deployment claim](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/README.md#L7).

**Đề xuất triển khai CI từ lúc có executable contract**, mở rộng theo khả năng đo và thay đổi, không đợi hoàn thành refactor lớn:

| Tầng đề xuất | Gate | Environment và giới hạn |
| --- | --- | --- |
| Mọi PR | Existing Prettier; Ruff; backend deterministic tests; frontend typecheck/Vitest/build; OpenAPI drift; Compose validation | Provider selectors test-only, dependencies/config được pin; không load `.env` dev chứa provider thật |
| PR chạm DB/ingestion/conversations/tools | Disposable PG + migrations + transaction/fencing/auth/integration tests; object-store test khi cần | Tách khỏi DB/volumes thật; job phải báo required test bị skip, không coi skip là acceptance |
| PR chạm retrieval/prompt/model | Deterministic contracts + frozen offline retrieval/evidence regressions; model eval được scope riêng | Không bắt mọi format-only PR chịu model latency/cost; AI candidate activation vẫn cần eval gate |
| Scheduled/manual hoặc candidate release | Real-provider heldout eval, auth/browser E2E, fault/load/restore drills | Model/hardware/dataset pin; lưu artifacts có provenance và bảo vệ dữ liệu |
| Release | SAST/SCA/image scan/SBOM, image digest/provenance, migration rehearsal, staging smoke/E2E, deploy health và rollback/roll-forward plan | Budget, credentials và protected deploy environment rõ; không deploy từ untrusted PR |

Đây là CI design đề xuất, chưa thêm workflow hay required statuses mới. Giữ required `Prettier format check` theo policy hiện tại. GitHub hỗ trợ pytest workflows; dùng các commands đã có nhưng cần cấu hình disposable services rõ để chạy đủ tests. Nguồn: [GitHub Python testing](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [repo verification commands](https://github.com/NhiBuaa/knora-agent/blob/ee7572583d558676c6d75ed266cc4a1f4fe0286d/README.md#L594).

### 14.2. Public staging và IaC có phạm vi phù hợp

**Topology ứng viên để đánh giá chi phí:** một frontend/BFF process theo constraint auth hiện tại, API, ingestion/Conversation workers được supervise/restart, PostgreSQL+pgvector, private object storage, Keycloak và model/provider khả dụng. Cùng với KittaChat, integration đi qua service authentication và logical invocation IDs; ordinary chat không đợi Knora. Managed services hay VM/Compose là lựa chọn phải chốt theo ngân sách, inference hardware, RPO/RTO và workload; survey chưa có dữ liệu để chọn cloud/vendor cụ thể.

FastAPI deployment cần giải quyết HTTPS, startup, restart, replication, memory và bước khởi tạo trước runtime; nhiều process có thể tăng model memory. Không thể suy readiness từ Dockerfile build được. Nguồn: [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/).

**Gate trước khi đưa lên Internet:** identity/ownership đúng; corpus demo được phép công bố; quotas/rate/concurrency/output limits; credentials/secrets ngoài Git; private DB/object store; admission và side effects fail closed; dependency failure có terminal outcome; restore đã thử; latency/cost budget có baseline. Đường guest/recruiter demo cần scope/decision riêng, không bật API key/OIDC bypass từ config test.

IaC nên mô tả một environment đủ tái tạo compute/network/storage/DNS/secrets references; không cần Kubernetes để chứng minh deployment. Terraform có workflow write/plan/apply và state; Terraform state/plan có thể chứa sensitive values ngay cả khi output được đánh dấu sensitive, nên state access/encryption/locking phải nằm trong thiết kế. Nguồn: [Terraform overview](https://developer.hashicorp.com/terraform/intro), [sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).

### 14.3. SAST, SCA, SBOM và supply chain

- **SAST:** code scanning phân tích lỗi/vulnerability candidates trong source; CodeQL hoặc công cụ xuất SARIF là lựa chọn. Scan không thay tests prompt injection, isolation hoặc tool authority ở track 11. [GitHub code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning).
- **SCA:** dependency review kiểm tra thay đổi dependencies và vulnerability/license concerns; resolve/pin backend dependency set để artifact có thể tái lập. [GitHub dependency review](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review).
- **Workflow integrity:** pin third-party Actions vào verified full commit SHA, permissions tối thiểu, không đưa secrets vào untrusted PR job. Workflow hiện dùng `@v4` tags; đây là ứng viên hardening, không kết luận đã bị compromise. [GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use).
- **Release identity:** pin container digest, tạo inventory/SBOM gắn image digest; build provenance/attestation giúp kiểm tra artifact được tạo từ input/process nào. SBOM không tự chứng minh không có vulnerability; provenance không tự chứng minh code đúng. [Artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations), [SLSA tracks v1.2](https://slsa.dev/spec/v1.2/tracks).
- **Deploy identity:** nếu cloud hỗ trợ, GitHub OIDC cho credential ngắn hạn thay long-lived secret; trust policy phải giới hạn repo/ref/environment. OIDC không tự cấp an toàn nếu trust policy quá rộng. [GitHub cloud OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-cloud-providers).

Không claim “SLSA level đạt được” chỉ vì tạo một attestation. Cần kiểm tra đầy đủ requirements của track/level đã chọn. Các job scanner phải có owner triage, severity policy và exception có thời hạn; badge xanh không đủ portfolio evidence.

### 14.4. JD cụ thể → năng lực → artifact

Trang employer Innotech đang công bố đúng JD người dùng trích: FastAPI/RAG, Qdrant/Neo4j, ReAct/LangChain/AutoGen/MCP, Rust/TypeScript/graph databases. Must-Have còn nhấn Python, ML/DL và LLM mechanics, inference/evaluation, Docker/Linux/Git. Đây là mẫu JD mục tiêu, không phải kết luận toàn thị trường cần toàn bộ stack. Nguồn: [Innotech AI Engineer Intern](https://innotech-vn.com/career/ai-engineer-intern/).

| Năng lực JD/Career | Evidence hiện tại | Bài thực hành/evidence bổ sung đề xuất |
| --- | --- | --- |
| Python/FastAPI/PostgreSQL/backend | Native modules/transactions và test source | Public release; tự giải thích/debug một request và một DB transaction; review/modify có giới hạn |
| RAG/vector/citations | Hybrid retrieval, evidence/citation contracts và eval harness | Frozen heldout benchmark + error analysis + một cải thiện có số liệu |
| Qdrant | Chưa có adapter production được khảo sát | Qdrant adapter lab cùng profile/filter dataset, comparison và failure recovery |
| Neo4j/graph | Chưa có graph production hoặc multihop gold | Graph retrieval lab, entity resolution/provenance, graph-vs-hybrid ablation; giữ lab nếu không thắng |
| LangChain/ReAct/LangGraph | Native M4 authority, chưa có model-tool bridge | Typed read/propose lab; LangChain API thực hành; LangGraph checkpoint/restart/HITL và native comparison |
| AutoGen | Chưa có implementation được khảo sát | Đọc/đối chiếu architecture và maintenance status; sample nhỏ nếu target yêu cầu rõ, không thêm orchestration stack vào core mặc định |
| MCP | Chưa có client/server path được khảo sát | Một consume read-only hoặc thin expose lab có real client, binding/auth-negative cases |
| PyTorch/Transformers/ONNX, ML fundamentals | Embedding/generation APIs không tự chứng minh ML fluency | Reranker inference lab, batching/truncation/device/parity, explain tensors/logits/scoring; không cần training campaign |
| TypeScript | Next.js/BFF và auth source hiện hữu | Tự sửa typed API/error flow, tests/typecheck/build; không tự suy independent fluency từ agent-written code |
| Rust | Chưa có evidence | Mức ưu tiên sau các gap trực tiếp hơn; nếu JD mạnh cần Rust, bài tập nhỏ có interface/test/benchmark, không rewrite FastAPI |
| Linux/DevOps/quality | Docker/Compose, tests, local operations | CI/release/deploy/restore/fault artifacts và log-based investigation |

Một employer khác trong Career, Vitraga, cũng nhấn API/AI integrations và preferred LangChain/vector/agents, hỗ trợ lý do làm bounded familiarity labs. JD này không yêu cầu Knora đổi database/auth sang Supabase hoặc đổi backend sang Node. Nguồn: [Vitraga employer JD](https://www.vitraga.com/careers/software-engineer-intern).

**Portfolio packet đề xuất:** README entry dễ hiểu trong 10–30 giây, live staging/demo có giới hạn, 2–3 minute walkthrough, versioned benchmark/eval report, failure/restore case study, ADR trade-offs, reproducible commands, release SHA/image/model/corpus manifest và test/CI links. Mỗi metric ghi environment, population, date và scope; không gọi local CPU experiment là production scale.

**Independent ownership gate theo Career:** chủ dự án tự đi từ HTTP request đến authorization/retrieval/evidence/result commit; tự debug một failure; tự sửa một bounded behavior và test; giải thích vì sao giữ pgvector/native và khi nào chọn Qdrant/LangGraph. Một lab thất bại nhưng phân tích đúng vẫn là evidence của thực hành, còn CV claim cải thiện X% chỉ dùng khi đã đo và có artifact. Nguồn: [Career proof gates](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Skills/Market-Skill-Matrix-2026.md), [Ship-First evidence](https://github.com/NhiBuaa/Career/blob/46a13eae3e508344d6814991e9f241427ee814fe/Roadmaps/Internship-Ship-First-2026.md).

## 15. Trình tự đề xuất sau research

Đây là thứ tự quyết định để giảm phạm vi, chưa là lịch triển khai hay phê duyệt architecture mới. Các mốc ngày trong Career là mục tiêu cũ cần đối chiếu; không tuyên bố milestone đã đạt chỉ theo ngày.

1. **Chốt fixed point mới:** pin source/schema/provider/profile/prompt/corpus; giữ lại release contracts đã accepted, liệt kê gaps. Review các đoạn Career/README stale khi được giao cập nhật.
2. **Thiết lập evidence nền:** isolated deterministic/integration CI; frozen quality baseline; threat model; full request timing và resource/cost accounting. Characterize history/recovery và DB-delay risks từ track 1.
3. **Refactor có lý do cụ thể:** chọn một seam giải quyết correctness hoặc blocker shipping; giữ behavior, verify regression, ADR trước thay semantics. Không gộp đổi database/model/agent vào cùng scope behavior-preserving refactor.
4. **Ship flagship có giới hạn:** kiểm chứng M5 baseline hiện tại, thiết kế M6 authenticated/failure-isolated slice, public staging, fault/restore/load/quality gates. #92 completed không thay gate dành cho sản phẩm/model mới.
5. **Nice-to-Have labs theo JD:** ưu tiên Qdrant benchmark và LangChain/LangGraph/MCP familiarity; reranker cho retrieval/ML evidence; Neo4j multihop lab theo JD/use case. Mỗi lab có câu hỏi, baseline, artifacts, giới hạn và stop condition. Không dùng 14-track survey làm tiền đề cho một đợt rewrite toàn dự án.
6. **Tích hợp khi gate đạt:** production recommendation cần quality/correctness/latency/cost/operations cùng đạt; nếu không đạt, giữ lab và viết trade-off. Đưa evidence thật vào public packet/CV, tiếp tục apply theo Career.

### Điều gì có thể quyết định ngay, điều gì còn phải đo?

| Có thể kết luận từ research | Chưa thể kết luận trước thí nghiệm |
| --- | --- |
| Authority/identity/provenance phải nằm ở Knora và provider sở hữu effect | Reranker, rewrite, graph hoặc model nào cải thiện heldout answer quality bao nhiêu |
| Qdrant trước hết là adapter/benchmark ứng viên, chưa có lý do migration được đo | Corpus/concurrency hiện tại có vượt retrieval/PG SLO không |
| LangGraph/MCP không thay lease/fencing/Workspace ownership | Native vs framework có giảm complexity/change surface trên workflow thực không |
| Structural citation validation khác semantic correctness | Provider production profile hiện đạt quality/latency/cost gate nào |
| Full E2E latency/cost/fault/restore evidence cần cho public ship | Deployment cloud/topology nào phù hợp ngân sách và RPO/RTO |
| Nice-to-Have liên quan cần bài thực hành có evidence | Năng lực độc lập của chủ dự án đã đạt proof gate nào |

## 16. Giới hạn và kiểm tra báo cáo

Research dùng local source tương đương GitHub baseline, `gh` cho issue/Career và web cho tài liệu chính thức. Các docs công nghệ là snapshot ngày đọc và có thể thay đổi; khi implementation phải pin dependency/model/protocol/schema/hardware phù hợp. Những thay đổi phiên bản lớn được ghi ở track tương ứng; không áp dụng API từ trí nhớ.

Không chạy model benchmark, load test, exploit, fault injection, restore hoặc browser acceptance trong lượt này. Không có số liệu cải thiện mới hay claim production-ready. Thay đổi repository chỉ là tài liệu research; không install stack, đổi runtime, migration, issue hay commit/push.

Kiểm tra tài liệu: coverage đủ 14 track và câu hỏi cuối; citations source Knora pin vào đúng SHA và line tồn tại; relative report link tồn tại; không có Markdown fence chưa đóng hay ký tự thay thế encoding. Các runtime verification commands sẽ cần chạy cho implementation tương ứng, không được suy PASS từ việc kiểm tra Markdown.
