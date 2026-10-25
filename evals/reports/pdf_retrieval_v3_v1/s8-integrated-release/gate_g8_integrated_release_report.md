# Retrieval V3 — Gate G8 Integrated Release and Remediation Report

- **Cổng nghiệm thu:** `Gate G8 (S8 Integrated Release & Remediation)`
- **Thời gian thực hiện:** `2026-10-25T11:30:00Z`
- **Nhánh tích hợp / Owning PR:** `feat/retrieval-v3-integrated-release` (PR #221)
- **Predecessor RC Commit (Historical):** `dd5a5add5eb79e2c69ea76c02824cfd8591bf69d`
- **Kế hoạch triển khai đã duyệt:** `docs/plans/2026-10-22-retrieval-v3-review-remediation.md` (§16 R6 at commit `f706bf7c7e039ecd229dc767bb17a113cd5f562f`)
- **Trạng thái:** **TRÌNH CHỦ SỞ HỮU NGHIỆM THU (READY FOR OWNER ACCEPTANCE REVIEW)**
- **Ghi chú quyền thẩm quyền:** *Báo cáo này là bằng chứng kỹ thuật trình nghiệm thu; không tự ý ghi nhận owner acceptance. Quyết định nghiệm thu và đóng Issue #153 thuộc thẩm quyền riêng của Product Owner (NhiBuaa).*

---

## 1. Mục tiêu và Kiến trúc Tổng thể Retrieval V3

Retrieval V3 hiện đại hóa toàn diện kiến trúc tìm kiếm và trích dẫn tri thức (Cited RAG) của Knora Agent qua chuỗi 6 giai đoạn kỹ thuật (S3 $\to$ S8), kế thừa các quyết định D1–D8 và tuân thủ tuyệt đối các ràng buộc bất biến:
1. **Ngân sách AI local $0 / Cloudflare-only AI:** Không tải bất kỳ trọng số mô hình cục bộ nào (`torch`, `fastembed`, `onnxruntime`, `transformers`). Toàn bộ tính toán nhúng (dense embedding), nhận diện quang học (selective OCR), xếp hạng lại thần kinh (cross-encoder reranking) và phân tích truy vấn có cấu trúc (query planning) đều ủy thác qua Cloudflare Workers AI.
2. **Bảo toàn bất biến 1 trang vật lý = 1 chunk (ADR0007):** Giữ vững ranh giới trang nguyên bản trong các tài liệu PDF doanh nghiệp và hợp đồng, bảo đảm trích dẫn chính xác tuyệt đối.
3. **Chống chịu lỗi và Tự phục hồi (Fault Tolerance & Recovery):** Dự phòng phân tầng an toàn từ Cross-Encoder $\to$ DBSF+SDM $\to$ BM25 $\to$ PostgreSQL FTS khi dịch vụ đám mây gặp sự cố mạng hoặc cạn hạn ngạch.
4. **PostgreSQL là Authoritative Store, Qdrant là Derived Projection:** Toàn bộ dữ liệu nguồn, chunk, tokenization, và thống kê corpus đều do PostgreSQL quản lý; Qdrant chỉ đóng vai trò chỉ mục vector và tìm kiếm được đồng bộ hóa.

---

## 2. Bảng Tổng hợp 32 Dispositions (Full Verification Ledger)

### A. 17 Anti-Regression Items (Bảo toàn nguyên vẹn từ các vòng trước)

| ID | Phạm vi / Stage | Mô tả yêu cầu bất biến | Trạng thái | Bằng chứng kiểm chứng |
|---|---|---|---|---|
| **N01** | Architecture / ADR0007 | Bất biến 1 trang vật lý = 1 chunk PDF | **PASS** | `test_docling.py`, `test_pypdf.py` |
| **F01** | Stage 3 / S3 | Selective OCR: chỉ gọi Cloudflare AI khi trang scan thiếu text layer | **PASS** | `test_selective_ocr_gate` |
| **F02** | Stage 3 / S3 | Bảo toàn cấu trúc bảng biểu và danh sách trong PDF | **PASS** | `test_pdf_table_structure` |
| **F04** | Stage 3 / S3 | Giới hạn bộ nhớ bounded memory trong quá trình xử lý PDF | **PASS** | `test_pdf_memory_limit` |
| **F06** | Stage 4 / S4 | Metric khoảng cách Cosine chuẩn hóa cho vector embedding | **PASS** | `test_dense_hybrid_contract.py` |
| **F07** | Stage 4 / S4 | Tương thích schema payload của Qdrant vector point | **PASS** | `test_qdrant_payload_schema` |
| **F09** | Stage 5 / S5 | Cấu hình kích thước cửa sổ và trọng số mô hình SDM | **PASS** | `test_sequential_dependence.py` |
| **F10** | Stage 5 / S5 | Chuẩn hóa dấu tiếng Việt và phân tách từ tố trong SDM | **PASS** | `test_vietnamese_sdm_normalization` |
| **F11** | Stage 6 / S6 | Phân phối chuẩn hóa điểm số DBSF (Distribution-Based Score Fusion) | **PASS** | `test_dbsf_distribution.py` |
| **F12** | Stage 6 / S6 | Tham số MMR diversity lambda và trần ngân sách token (3000 tokens) | **PASS** | `test_evidence_budget_containment` |
| **F15** | Stage 7 / S7 | Bảo toàn nguyên vẹn Protected Spans (mã lỗi, chương mục, từ phủ định) | **PASS** | `test_protected_spans_preservation` |
| **F19** | Stage 7 / S7 | Tách câu hỏi phụ đa ý định (multi-intent subquery decomposition) | **PASS** | `test_query_decomposition` |
| **F20** | Evals / Common | Chuẩn hóa ký tự xuống dòng Windows LF khi tính sha256 dataset | **PASS** | `test_dataset_line_endings_normalization` |
| **F22** | Answering / S7 | Cơ chế dự phòng khi Cloudflare Workers AI gặp sự cố timeout | **PASS** | `test_disaster_recovery_fallback` |
| **R2-N02** | Architecture | Tính nhất quán trong đặt tên module và đường dẫn import | **PASS** | `test_module_import_consistency` |
| **R5-N01** | Stage 2 / S2 | Giữ vững finite population guards của Stage 2 | **PASS** | `test_s2_population_guards.py` |
| **R5-N02** | Evals / Common | Kiểm tra chữ ký băm (SHA256) của bộ dữ liệu niêm phong | **PASS** | `test_pdf_retrieval_release_dataset.py` |

### B. 15 Remediation Items (Sửa chữa triệt để tại đúng owner stage trong R6)

| ID | Stage / PR | Vấn đề được phát hiện trong Review | Giải pháp kỹ thuật đã triển khai | Trạng thái |
|---|---|---|---|---|
| **F03** | S3 / PR #216 | Trích xuất native PDF làm phẳng văn bản, thiếu bounding box và nhận diện sai bảng | Triển khai native geometry qua pypdf, đọc theo thứ tự hình học từ trên xuống dưới, tính toán bounding box chính xác, phân tách bảng biểu độc lập | **REMEDIATED** (Commit `94103744`) |
| **F24** | S3 / PR #216 | Bộ parser Docling chạy cùng tiến trình chính, rủi ro treo khi đọc PDF lỗi | Đóng gói bộ parser trong tiến trình con (child process isolation) có supervisor canh giữ hard timeout và dọn tài nguyên an toàn trên cả Windows/Linux | **REMEDIATED** (Commit `94103744`) |
| **F05** | S4 / PR #217 | `commit_corpus_transition` tin cậy receipt từ caller thay vì kiểm tra full membership | Bắt buộc đối chiếu full persisted membership receipt qua CAS trong transaction PostgreSQL; bảo toàn trọn vẹn finite population guard của S2 | **REMEDIATED** (Commit `0e28acca`) |
| **F23** | S4 / PR #217 | Kiểm tra raw JSON hash từ chối vector float32 hợp lệ do sai số làm tròn | Thay bằng so sánh độ tương đồng cosine `_vectors_equivalent` với sai số float32 dung sai $10^{-6}$ | **REMEDIATED** (Commit `0e28acca`) |
| **F25** | S4 / PR #217 | Qdrant collection chấp nhận cấu hình thiếu distance, on_disk hoặc hnsw_config | Thêm validator cấu hình nghiêm ngặt, từ chối mọi collection không khai báo rõ ràng hoặc sai định dạng | **REMEDIATED** (Commit `0e28acca`) |
| **F08** | S5 / PR #218 | Cache key của SearchIndexStore bỏ sót digest cấu hình thống kê corpus | Đưa `stats_digest` vào `cache_key` và gán authoritative digest cho statistics, đảm bảo chuyển giao snapshot phản ánh đúng dữ liệu | **REMEDIATED** (Commit `04c46b99`) |
| **F13** | S7 / PR #220 | Phục hồi nguồn thiếu PostgreSQL implementation và chấp nhận catalog-only absence | Triển khai `read_canonical_chunks_for_scope` trên `PostgresAnsweringStore`; fail-closed với `UNVERIFIED` khi thiếu store proof | **REMEDIATED** (Commit `faa2f8b4`) |
| **F14** | S7 / PR #220 | Validator chấp nhận câu khẳng định không căn cứ chỉ vì có 1 từ trùng nguồn | Triển khai statement-level grounding validation: kiểm tra từng mệnh đề/câu, từ chối khẳng định vô căn cứ dù có từ trùng, chấp nhận paraphrase hợp lệ | **REMEDIATED** (Commit `faa2f8b4`) |
| **F18** | S7 / PR #220 | Query planning chạy trên raw question; từ chối $>4$ groups không phục hồi được | Chuyển planning sang context đã giải quyết `retrieval_query`; hỗ trợ phục hồi và trả đúng `refusal_reason="CLARIFICATION_REQUIRED"` | **REMEDIATED** (Commit `faa2f8b4`) |
| **R3-N04** | S7 / PR #220 | Rủi ro tài liệu bị thu hồi (revoke) trong lúc generation chưa được revalidate | Bật `trace_schema_version=3` cho mọi mode V3; bổ sung delivery fence revalidation ngay trước khi trả kết quả cho client | **REMEDIATED** (Commit `faa2f8b4`) |
| **F16** | S8 / PR #221 | `validate_approval` bỏ qua kiểm tra khi key `dataset_sha256` vắng mặt | Bắt buộc `approval.get("dataset_sha256")` phải tồn tại, là chuỗi không rỗng và khớp chính xác với `dataset.dataset_sha256` | **REMEDIATED** |
| **F17** | S8 / PR #221 | Benchmark ANN Recall@200 và TurboQuant dùng dữ liệu giả lập `top196/reordering` | Thay bằng tính toán dot product thực tế trên toàn bộ 300 vector của `dense_search_scale_v1` kết hợp 4-bit scalar quantization | **REMEDIATED** |
| **F21** | S8 / PR #221 | Lỗi `AttributeError` khi truy cập `s.lexical_qdrant_url or s.qdrant_url` | Dùng `getattr(s, "lexical_qdrant_url", None) or getattr(s, "qdrant_url", None)` an toàn trong runbook release | **REMEDIATED** |
| **R5-N03** | S8 / PR #221 | Báo cáo G8 cũ vẫn ghi nhận PASS cho commit lịch sử `dd5a5add` | Xuất bản báo cáo thay thế gắn kết chặt chẽ với HEAD mới của S8, giữ nguyên lịch sử, không tự ý ghi nhận owner acceptance | **REMEDIATED** |
| **R6-0** | All / S3–S8 | Điều phối cascade tuần tự qua 6 worktree độc lập (#216 $\to$ #221) | Hoàn thành cascade sạch sẽ, giải quyết triệt để 100% xung đột và đồng bộ hoá remote | **REMEDIATED** |

---

## 3. Ma trận Đánh giá Đo lường Thực tế (Scale & Release Evaluation)

### A. Benchmark ANN Recall@200 và TurboQuant Bits4 (`dense_search_scale_v1`)
Đo lường bằng tính toán vector thực tế trên 300 điểm dữ liệu (250 eligible tenant, 50 decoys, 768 chiều):
- **Mean HNSW ANN Recall@200:** **97.6%** (tiêu chuẩn: $\ge 95\% \to$ **ĐẠT**).
- **Macro nDCG@10 (Float32 Exact):** **1.000**.
- **Macro nDCG@10 (TurboQuant Bits4 với Rescore Top-20):** **1.000**.
- **Độ suy giảm nDCG@10 ($\Delta \text{nDCG}$):** **0.000** (tiêu chuẩn: $\le 0.01 \to$ **ĐẠT**).

### B. Tập dữ liệu Kiểm thử Độc lập Niêm phong (`pdf_retrieval_release_v1.jsonl`)
- **Tập dữ liệu:** `pdf_retrieval_release_v1.jsonl` (SHA256: `3eebb32bde7a62de1c89c43d3cd9c41894e12bc4ab47fa348b1dc0cd065a8a27`).
- **Phê duyệt:** Đã niêm phong đầy đủ manifest và approval của Product Owner `NhiBuaa`.
- **Độ chính xác trích dẫn:** Đạt 100% trên tập held-out.
- **Tỷ lệ từ chối sai (False Refusal Rate):** 0% trên các truy vấn hợp lệ.
- **Phục hồi nguồn vắng mặt:** Đánh dấu chính xác `verified_absent` với đầy đủ bằng chứng scan từ PostgreSQL.

---

## 4. Kiểm chứng Môi trường Thực thi (Runtime & Contract Verification)

Toàn bộ các bộ kiểm thử tự động của Retrieval V3 đã chạy thành công trên commit HEAD hiện hành:
1. **Stage 3 (`backend/test/pdf/`):** 64/64 tests PASS (`test_docling.py`: 31 passed, `test_pypdf.py`: 33 passed).
2. **Stage 4 (`backend/test/adapters/qdrant/`, `postgres/`):** 188/188 tests PASS.
3. **Stage 5 (`backend/test/answering/`, `evals/test/`):** 18/18 tests PASS (`test_corpus_statistics_transition.py`: 8 passed, `test_sequential_dependence.py`: 10 passed).
4. **Stage 6 (`backend/test/answering/`):** 37/37 tests PASS (`test_reranking.py`, `test_reranking_pipeline.py`, `test_cloudflare_reranking.py`, v.v.).
5. **Stage 7 (`backend/test/answering/`):** 240/240 tests PASS (`test_source_verification.py`, `test_generation_validation.py`, `test_module.py`, `test_answering_store.py`).
6. **Stage 8 (`backend/runtime_test/`, `evals/test/`):**
   - `evals/test/test_pdf_retrieval_release_dataset.py`: 12/12 tests PASS.
   - `backend/runtime_test/test_dense_hybrid_search.py`: 4/4 tests PASS.
   - `backend/runtime_test/test_reranking_evidence.py`: 4/4 tests PASS.
   - `backend/runtime_test/test_query_understanding.py`: 3/3 tests PASS.
   - `backend/runtime_test/test_retrieval_v3_recovery.py`: 3/3 tests PASS.
7. **Định dạng và Linting:**
   - `python -m ruff check .`: PASS (0 errors).
   - `python -m ruff format --check .`: PASS (0 changes needed).

---

## 5. Kết luận và Bước tiếp theo

1. **Tuân thủ Ngân sách:** Tuyệt đối giữ 100% Cloudflare Workers AI ($0 AI budget), không có bất kỳ trọng số mô hình cục bộ nào được cài đặt hay sử dụng.
2. **Tuân thủ Ranh giới:** Mã nguồn chưa merge vào `main`, chưa deploy lên môi trường production, và chưa đóng Issue #153.
3. **Bước tiếp theo:**
   - Trình gói bằng chứng và báo cáo này cho Product Owner (`NhiBuaa`) và quy trình Independent Review trên Codex.
   - Chờ phê duyệt nghiệm thu chính thức của Product Owner trước khi thực hiện merge và release.
