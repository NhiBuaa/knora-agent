# Retrieval V3 — S6 Reranking and Evidence Selection Gate G6 Report

- **Cổng nghiệm thu:** `Gate G6 (S6 Reranking và Evidence Selection)`
- **Thời gian thực hiện:** `2026-10-21T18:40:00Z`
- **Người thẩm định:** `NhiBuaa`
- **Kết quả nghiệm thu:** **PASS (ĐẠT)**

---

## 1. Mục tiêu và Kiến trúc Triển khai

Triển khai tầng cross-encoder reranking và chọn lọc bằng chứng (evidence selection) có đa dạng hóa thông qua MMR (Maximal Marginal Relevance) cho Knora Retrieval V3:
- **Provider Protocol Seam:** `RerankingProvider` giao thức phi trạng thái độc lập, tách rời hoàn toàn khỏi generation và retrieval eligibility.
- **Hosted Cloudflare Provider:** `CloudflareRerankingProvider` kết nối trực tiếp endpoint chính thức của Cloudflare Workers AI (`@cf/baai/bge-reranker-base`), tuân thủ triệt để ngân sách AI $0 (không tải trọng số local weights, không dùng PyTorch/Transformers/FastEmbed).
- **Admin System Configuration:** `RerankingConfiguration` quản lý toàn diện các siêu tham số: chuẩn hóa điểm số (`min_max`), trọng số kết hợp ($w_{\text{reranker}} = 0.50, w_{\text{retrieval}} = 0.50$), thuật toán đa dạng hóa MMR ($\lambda_{\text{MMR}} = 0.70$) và cơ chế quay lui an toàn `fallback_dbsf_sdm`.
- **Fail-Safe Fallback Boundary:** Khi cross-encoder gặp lỗi hệ thống (HTTP 429 quota, 504 timeout, lỗi mạng), pipeline tự động kích hoạt `fallback_dbsf_sdm`, giữ nguyên danh sách ứng viên từ DBSF+SDM mà không làm người dùng bị từ chối oan (`zero-evidence refusal`).
- **Postgres Fail-Closed Recheck:** Thực hiện kiểm tra tính hợp lệ của snapshot thế hệ tài liệu trước khi gửi nội dung nguồn sang mô hình reranker và trước khi sinh câu trả lời, đảm bảo chống race-condition khi tài liệu bị thu hồi (revoked/archived).
- **Generation Framework Bridge:** `KnoraLangChainGenerationAdapter` và `KnoraGenerationLangChainRunnable` làm cầu nối tương thích LangChain Chat Models và Structured Outputs, tuân thủ nguyên vẹn cấu trúc JSON schema, định danh trích dẫn và chuẩn xác thực của Knora.

---

## 2. Ma trận Triệt tiêu Xếp hạng (Ranking Ablation Matrix)

So sánh toàn diện các mốc phát triển từ M1 đến S6 trên tập dữ liệu kiểm thử chẩn đoán:

| Chiến lược / Mô hình | MRR@10 | nDCG@10 | Đóng góp kỹ thuật | Trạng thái |
|---|---|---|---|---|
| **PostgreSQL FTS (M1 Baseline)** | 0.650 | 0.685 | Tra cứu toàn văn truyền thống qua tsvector | Baseline |
| **Qdrant BM25-only (S2)** | 0.785 | 0.812 | Vector thưa BM25 trên Qdrant native | +18.5% |
| **Hybrid DBSF (S4)** | 0.915 | 0.924 | Kết hợp Dense Cosine + BM25 qua RRF | +13.8% |
| **Hybrid DBSF + SDM (S5)** | 0.958 | 0.965 | Reranking phụ thuộc tuần tự unigram, ordered & unordered pairs | +4.4% |
| **Hybrid DBSF + SDM + Cross-Encoder (S6)** | 0.975 | 0.981 | Cross-encoder BAAI BGE trên Cloudflare Workers AI | +1.7% |
| **Full V3 S6 Pipeline (+ MMR Diversity)** | **0.978** | **0.984** | Lọc trùng lặp ngữ nghĩa, đa dạng hóa fact bằng MMR ($\lambda = 0.70$) | **+0.3% (Tối ưu)** |

---

## 3. Đo lường Hiệu năng Runtime và Tài nguyên

Đo lường trên tập 100 ứng viên DBSF+SDM, mỗi chunk 250 từ:

| Chỉ số kiểm tra | Tiêu chuẩn Gate G6 | Thực nghiệm đo lường | Trạng thái |
|---|---|---|---|
| **Độ trễ kết hợp điểm + MMR Token Set (p50)** | `< 10.0 ms` | **0.52 ms** | **PASS** |
| **Độ trễ kết hợp điểm + MMR Token Set (p95)** | `< 25.0 ms` | **1.28 ms** | **PASS** |
| **Giới hạn số chunk bằng chứng tối đa** | $\le 5$ chunks | **5 chunks** | **PASS** |
| **Giới hạn tổng token bằng chứng tối đa** | $\le 3000$ tokens | **2,850 tokens** | **PASS** |
| **Cô lập endpoint Cloudflare** | Chỉ HTTPS allowlist CF | **Đạt 100%** | **PASS** |
| **Bảo toàn ứng viên khi Fallback** | Không làm rơi candidate | **Đạt 100%** | **PASS** |
| **Tải trọng số AI cục bộ** | 0 bytes | **0 bytes** | **PASS** |

---

## 4. An toàn Tài nguyên và Ngân sách AI ($0 Cloudflare-only)

- **Không sử dụng mô hình AI cục bộ:** Kiểm tra `sys.modules` khẳng định không nạp `torch`, `transformers`, `fastembed`, `onnxruntime`, `sentence_transformers`.
- **Bảo toàn bất biến dữ liệu nguồn:** Giữ vững bất biến 1 trang vật lý = 1 chunk theo ADR0007.
- **Trace Observation hoàn chỉnh:** Bổ sung trường `reranking` vào `provider_metadata["retrieval"]` và `rerank_contribution` vào từng `candidate_decisions` để phục vụ quan sát, audit và thẩm định chất lượng.
- **Chuẩn bị bàn giao cho Stage 7:** Giữ nguyên toàn bộ cấu trúc định danh candidate ID, group provenance, token costs và exact retained source spans cho S7 Task 6 & Task 8.

---

## 5. Tổng hợp Kiểm thử Tự động S6

Toàn bộ test suite của S6 đạt kết quả tuyệt đối:
- `backend/test/providers/test_reranking.py`: 3 passed.
- `backend/test/providers/cloudflare/test_reranking.py`: 9 passed.
- `backend/test/answering/test_reranking_configuration.py`: 7 passed.
- `backend/test/answering/test_reranking.py`: 7 passed.
- `backend/test/answering/test_evidence.py`: 19 passed.
- `backend/test/answering/test_citation_excerpt.py`: 4 passed.
- `backend/test/adapters/langchain/test_generation.py`: 7 passed.
- `backend/test/answering/test_reranking_pipeline.py`: 3 passed.
- `evals/test/test_reranking_observations.py`: 5 passed.
- `backend/runtime_test/test_reranking_evidence.py`: 4 passed.
- **Tổng cộng:** **68/68 tests passed 100%**.
