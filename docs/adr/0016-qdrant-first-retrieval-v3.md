# Qdrant-first Retrieval V3 — kiến trúc mục tiêu

Status: proposed — Qdrant-first được chủ dự án lựa chọn ngày 2026-10-09; chi tiết chưa được nghiệm thu bằng implementation/benchmark

Tham chiếu: [#153 — BM25/Hybrid Retrieval](https://github.com/NhiBuaa/knora-agent/issues/153) · [#150 — xóa tài liệu](https://github.com/NhiBuaa/knora-agent/issues/150) · [#148 — KittaChat Group Knowledge](https://github.com/NhiBuaa/knora-agent/issues/148) · [#147 — AI Support Agent](https://github.com/NhiBuaa/knora-agent/issues/147) · [#146 — Cloudflare-first inference](https://github.com/NhiBuaa/knora-agent/issues/146)

## Bối cảnh

Knora hiện có PostgreSQL 16 + pgvector, PostgreSQL FTS/\`ts_rank_cd\`, versioned RRF và các retrieval configuration bất biến. #153 đã quyết định bắt buộc triển khai BM25 production-ready. Chủ dự án chọn **Qdrant** làm hướng triển khai search engine cho Retrieval V3, thay cho hướng **ParadeDB-first** trong bản nghiên cứu #153 trước đó.

Tài liệu này **chỉ ghi định hướng đã chọn và đề xuất kỹ thuật đi kèm**. Nó không khẳng định Qdrant đã được triển khai, đã benchmark hoặc được phép bật production. Không thay đổi ý nghĩa các legacy configurations (\`retrieval-m3-rrf-v1/v2\` và các chính sách gắn với chúng).

## Quyết định nền tảng được lựa chọn

1. **PostgreSQL vẫn là source of truth** cho Workspace, Document, Document Version, Chunk/Chunk Set, Embedding Set, current-source pointer, active-serving pointer, quyền truy cập, trạng thái ingestion, audit, traces và lifecycle. **Qdrant là search/index backend có thể dựng lại**, không là nguồn xác thực quyền hoặc nguồn xác định phiên bản đang phục vụ.
2. **Qdrant là search engine mục tiêu của Retrieval V3**: dense vector search + **BM25 sparse retrieval** + hybrid search/fusion. Dùng \`qdrant-client\` ở backend Python. Không chạy đồng thời Qdrant, ParadeDB, pgvector và FTS như bốn production search engines độc lập. Giữ PostgreSQL legacy retrieval trong migration để đối chứng/rollback, sau đó quyết định loại bỏ dependency dư thừa.
3. **BM25-only, dense-only và BM25+dense hybrid** phải chạy được qua đường ứng dụng thực tế, có configuration IDs mới, trace, provenance và citation. BM25-only **không được buộc thành công ở bước query embedding**. Triển khai BM25 là quyết định đã chốt; tuning và release gating diễn ra sau implementation.
4. **Embedding provider và generation provider thuộc Knora**. Không đổi embedding model/dimension chỉ để đổi vector DB; vẫn dùng \`EmbeddingConfiguration\` đã versioned. Giữ **Cloudflare Workers AI first / Ollama optional** theo #146; Qdrant không thay mô hình sinh trả lời.
5. **Search shape ban đầu:** shared Collection theo embedding/index profile, Point gắn với chunk + derivation/index generation, named dense và BM25 sparse vectors, indexed payload (Workspace, Document/Version, Chunk Set, Chunk, Embedding Set, generation, configuration metadata). Payload-filtered multitenancy là baseline; không tạo Collection cho từng người dùng mặc định.
6. **Retrieval quality:** versioned lexical query processor, nhất quán index/query cho tiếng Việt; benchmark Unicode/multilingual và Vietnamese segmentation, dấu/không dấu, Anh–Việt, mã định danh, exact/phrase semantics. Không mặc nhiên sử dụng English stemming/stopwords. Dùng Qdrant Query API + RRF baseline, so sánh với RRF cũ trong Knora (k=60); không giả định RRF/weighted behavior của hai engine giống nhau. Weighted RRF, budgets và reranker chốt bằng evaluation.
7. **Search Index Lifecycle:** định hướng **staged indexing + PostgreSQL durable outbox + idempotent worker + search index generation + reconciliation**. Index generation mới phải sẵn sàng trước activation; PostgreSQL giữ quyền quyết định active serving. Giữ V1 phục vụ khi V2 đang ingest hoặc thất bại. Archive, restore, revoke, reprocess và hard purge phải có kiểm thử retry/crash/recovery. Không giả định có transaction chung giữa PostgreSQL và Qdrant.
8. **Authorization:** Knora xác thực và quyết định scope; mọi Qdrant search phải nhận filter từ trusted backend, không tin filter/tenant từ client. Kiểm tra lại active eligibility/provenance và quyền citation trước công bố. Thiết kế **pre-filtered candidate recall** và fail-closed khi index/state không đồng bộ; lọc ứng viên lỗi sau Top-K **không đủ** để bảo đảm câu trả lời không bỏ sót. KittaChat vẫn quản lý membership/roles của #148, Knora kiểm tra quyền truy cập tri thức.
9. **Deployment/operations:** local Docker Compose single-node Qdrant, persistent volume, service-to-service private networking; authentication/TLS/secrets theo môi trường. Chọn và pin Qdrant server/client sau compatibility tests. Production hosting, CPU/RAM/disk/cost, snapshot, rebuild, retention, monitoring/index lag, p95 latency, rollback phải có bằng chứng trước rollout.
10. **Future Agent boundary:** Agent/Core của #147 sử dụng Knowledge Retrieval abstraction của Knora, **không gọi Qdrant SDK trực tiếp**. Keycloak, FastAPI, Next.js, object storage và evidence/refusal policy không bị thay thế vì thay search backend.

## Những chi tiết chưa khóa (chờ thiết kế/benchmark)

- Phiên bản Qdrant server/client, native BM25 inference thật trên deployment mục tiêu; server-side vs client-side sparse-vector generation/FastEmbed.
- Index schema thực tế, Collection topology, deterministic Point IDs, per-tenant IDF, HNSW/quantization, payload index/filter plan, query consistency và index-readiness checks.
- Transactional outbox/worker contract cụ thể, fencing/CAS, search generation activation, concurrent reader behavior, delete reconciliation/backup retention và safe failover.
- Vietnamese tokenizer/segmentation, BM25 k1/b, phrase/exact matching, query routing, RRF constants/weights, candidate Top-K, reranker (Cross-encoder/ColBERT).
- Chỉ tiêu p95 latency, quality margins, release infrastructure và chi phí. Đo baseline, triển khai BM25, benchmark/tune, **khóa gates trước held-out final evaluation**, rồi nghiệm thu production. Hard gates cho 0 cross-Workspace leak, 0 stale-version evidence và đúng source/citation trong bộ tests bắt buộc.

## Quan hệ với các ADR và issues hiện có

- **ADR 0011:** giữ nguyên việc \`current_document_version_id\` tách khỏi \`active_embedding_set_id\`; search index generation chỉ là derivation có thể xây lại, không làm mất semantic này.
- **#153:** là parent issue của Retrieval V3. Phải cập nhật thiết kế ParadeDB-first/SQL-first cũ thành Qdrant-first trước khi tạo implementation plan. Không xóa baseline hoặc các acceptance gates đã phê duyệt.
- **#150:** bổ sung Qdrant Points purge, retention/snapshot và idempotent reconciliation.
- **#148:** tenant/group knowledge filtering, current membership revocation và citation access; không thay UX/roles đã thống nhất.
- **#147:** giữ Knowledge tool abstraction và ranh giới quyền/human approval.
- **#146:** giữ chiến lược Cloudflare-first; xác minh model/embedding compatibility và triển khai demo.

## Điều kiện và bước tiếp theo

- **Chưa triển khai code, migration, deployment, chưa tạo implementation issue con và chưa merge ADR chỉ vì đã ghi bản nháp này.**
- Sau khi owner xác nhận chi tiết kiến trúc, cập nhật chính thức parent #153 + ADR status và phân rã implementation workstreams; code Qdrant/BM25; test/baseline/optimization; nghiệm thu rồi rollout.
- Không được đóng #153 ở mức PoC, feature flag chưa được kiểm chứng hay tài liệu lý thuyết: **BM25 phải được ship thành capability production-ready**.
