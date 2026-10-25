# Retrieval V3 — Gate G8 Superseding Release & Remediation Report (R6)

- **Cổng nghiệm thu:** `Gate G8 (S8 Integrated Release & Remediation)`
- **Thời gian lập báo cáo:** `2026-10-25T15:15:00+07:00`
- **Nhánh tích hợp / Owning PR:** `feat/retrieval-v3-integrated-release` (PR #221)
- **Kế hoạch triển khai đã duyệt:** `docs/plans/2026-10-22-retrieval-v3-review-remediation.md` (§16 R6 tại commit `f706bf7c7e039ecd229dc767bb17a113cd5f562f`)
- **Tài liệu thay thế (Superseding):** Báo cáo này thay thế nội dung diễn giải của `gate_g8_integrated_release_report.md` ngày 25/10/2026, khôi phục đúng nghĩa registry 32 IDs theo §16.2 và ghi nhận trung thực các giới hạn kỹ thuật / cổng chưa đạt.
- **Quyền hạn & Phạm vi:** *Báo cáo này là bằng chứng kỹ thuật phục vụ Independent Review và trình nghiệm thu; tuyệt đối KHÔNG tự ý ghi nhận owner acceptance, KHÔNG merge main, KHÔNG deploy production và KHÔNG đóng Issue #153.*

---

## 1. Bảng Tổng hợp 32 Dispositions theo Chuẩn Registry §16.2

### A. 15 Remediation Items (Sửa chữa theo kết quả Independent Review R5/R6)

| ID | Owning Stage / PR | Vấn đề được xác định trong Review | Giải pháp kỹ thuật đã triển khai | Trạng thái hiện tại |
|---|---|---|---|---|
| **F03** | S3 / PR #216 | Ghép block theo hình học nhưng tìm offset theo stream order; vỡ cấu trúc khi đảo stream | Thống nhất reading-order geometric assembly (`\n\n`.join), gán monotonic offsets trực tiếp cho prose/table blocks; loại bỏ fallback offset giả | **REMEDIATED** |
| **F24** | S3 / PR #216 | `ThreadPoolExecutor` context manager chặn thread sleep làm trễ timeout; parent RSS check chặn nhầm | Quản lý executor rõ ràng với `shutdown(wait=False, cancel_futures=True)`; chuyển copy file tạm lên trước, trả `CAPABILITY_UNAVAILABLE` có định kiểu; timeout trả về trong 0.067s | **REMEDIATED** |
| **F05** | S4 / PR #217 | Cold activation chấp nhận submission chỉ có tập con canonical documents | Bắt buộc đối chiếu tập submission với toàn bộ tài liệu canonical unarchived trong workspace (`DocumentTable.archived.is_(False)`); thiếu tài liệu lập tức fail-closed | **REMEDIATED** |
| **F23** | S4 / PR #217 | Readback vector chuẩn hóa đơn vị (unit norm) từ Qdrant Cosine metric bị từ chối | `_vectors_equivalent` bổ sung cờ `allow_normalized=is_cosine`, chấp nhận unit-normalized readback từ Qdrant cho Cosine metric khi `cos_sim >= 1.0 - 1e-4` | **REMEDIATED** |
| **F25** | S4 / PR #217 | Qdrant configuration qualification thiếu actual pinned-server positive/negative/readback | Đã có validator collection configuration nghiêm ngặt (`native_search_index.py:186`); tuy nhiên **thiếu actual pinned Qdrant server evidence** ở môi trường live -> ghi nhận đúng trạng thái | **FAIL (thiếu actual server evidence)** |
| **F08** | S5 / PR #218 | Reader trả cache trước khi kiểm tra; chunk content bị tamper nhưng giữ checksum vẫn accepted | Kiểm tra `sha256(chunk.content) == chunk.content_checksum` trực tiếp từ PostgreSQL chunks, fail-closed khi bị tamper; tính toán và persist `ordered_pair_frequencies` và `window_pair_frequencies` cho SDM | **REMEDIATED** |
| **F13** | S7 / PR #220 | Suy `VERIFIED_ABSENT` từ `complete_catalog` caller đưa vào mà thiếu store proof; LIMIT áp trước boundary filter | Bắt buộc snapshot hợp lệ; không suy absence khi thiếu proof; `answering_store.py` áp dụng regex boundary filter lên toàn bộ ứng viên trước khi phân trang (cursor/limit) | **REMEDIATED** |
| **F14** | S7 / PR #220 | Hoán đổi chủ thể cùng số-đơn vị vẫn được nhận ("đổi trả 30 ngày; bảo hành 7 ngày"); paraphrase đúng bị loại | Bổ sung statement-level grounding liên kết số-đơn vị với chủ thể trong từng mệnh đề; mở rộng hỗ trợ từ đồng nghĩa chuẩn hóa hợp lệ ("khách hàng" $\leftrightarrow$ "người mua") | **REMEDIATED** |
| **F18** | S7 / PR #220 | Follow-up bắt đầu bằng "Bao gồm những chương nào?" không neo vào tài liệu/câu hỏi trước | Mở rộng `_FOLLOWUP_PREFIX` và `_REFERENCE_CUE` nhận diện các câu hỏi tiếp nối ("bao gồm", "gồm những", "chương nào"), neo retrieval query vào chủ thể của turn trước | **REMEDIATED** |
| **R3-N04**| S7 / PR #220 | Refusal bypass snapshot fence làm sai lệch read fence | Phân biệt pre-search clarification với post-retrieval refusal; chỉ bypass khi `CLARIFICATION_REQUIRED`, bảo toàn snapshot fence cho toàn bộ truy vấn tra cứu | **PASS (scoped)** |
| **F16** | S8 / PR #221 | Dataset 4 mẫu phát triển cũ không được đóng vai release held-out; thiếu sealed package >= 12 PDFs / 60 câu | Entrypoint release từ chối chấp nhận bộ mẫu phát triển cũ khi chạy release evaluation; **chưa có gói mới >= 12 PDFs / 60 questions từ curator/owner** -> ghi nhận blocker | **DEFECT (chờ sealed package)** |
| **F17** | S8 / PR #221 | Lỗi cú pháp thừa dấu `}` tại dòng 196 và 308 trong `scripts/run-runtime-verification.ps1` | Đã xóa dấu `}` thừa tại dòng 196, kết nối khối `try` dòng 174 với `finally` dòng 308; xác nhận bằng PowerShell Parser: 0 lỗi; 48/48 tests runtime evidence PASS | **REMEDIATED** |
| **F21** | S8 / PR #221 | Runbook dùng thuộc tính không khai báo (`s.qdrant_url`), thoát 0 khi lỗi; healthcheck chỉ tạo factory BM25 | Cập nhật `docs/runbooks/retrieval-v3-release.md` dùng `s.lexical_qdrant_url` đã khai báo, thoát mã lỗi khác 0 khi thất bại; kiểm tra cấu hình đang phục vụ qua `resolve_retrieval_configuration` | **REMEDIATED** |
| **R2-N03**| S6 / PR #219 | Bảo toàn default test collection của reranker | 34/34 tests hợp đồng reranker tại Stage 6 chạy thành công | **PASS (scoped)** |
| **R5-N03**| S8 / PR #221 | Báo cáo 32 IDs sai registry, gán số runtime/quality chưa được chứng minh | Lập báo cáo thay thế này (`gate_g8_superseding_release_report_20261025.md`) đúng chuẩn registry §16.2, ghi nhận trung thực trạng thái kỹ thuật và các điểm đang chờ | **REMEDIATED** |

---

### B. 17 Anti-Regression Items (Bảo toàn nguyên vẹn)

| ID | Phạm vi / Stage | Mô tả yêu cầu bất biến | Trạng thái |
|---|---|---|---|
| **N01** | Stage 3 / S3 | Bảo toàn Alembic migration sequence và database schema | **PASS (scoped)** |
| **F01** | Stage 3 / S3 | Selective OCR: chỉ gọi Cloudflare AI khi trang thiếu text layer | **PASS (scoped)** |
| **F02** | Stage 3 / S3 | Bảo toàn cấu trúc bảng biểu và danh sách trong PDF | **PASS (scoped)** |
| **F04** | Stage 3 / S3 | Giới hạn tài nguyên trích xuất PDF (memory / time) | **PASS (scoped)** |
| **F06** | Stage 4 / S4 | Giám sát cấu hình Cloudflare-only AI, không phát sinh chi phí | **PASS (scoped)** |
| **F07** | Stage 4 / S4 | Trần pool hợp nhất 100 ứng viên (DBSF / Top-K) | **PASS (scoped)** |
| **F09** | Stage 6 / S6 | Định danh vòng đời và lifecycle của Reranker | **PASS (scoped)** |
| **F10** | Stage 6 / S6 | Envelope và cơ chế dự phòng phân tầng của Reranker (DBSF+SDM fallback) | **PASS (scoped)** |
| **F11** | Stage 4 / S4 | Schema payload và metadata của Embedding vector | **PASS (scoped)** |
| **F12** | Stage 7 / S7 | Phân rã câu hỏi phụ nguyên tử và bảo toàn ràng buộc (subquestions) | **PASS (scoped)** |
| **F15** | Stage 7 / S7 | Cơ chế kích hoạt opt-in V3, tương thích ngược với legacy V1/V2 | **PASS (scoped)** |
| **F19** | Stage 8 / S8 | Thuật toán chấm điểm Recall / MRR / Ranking scorer | **PASS (scoped)** |
| **F20** | Stage 8 / S8 | Tính toàn vẹn băm SHA256 và định dạng xuống dòng Windows LF của frozen gold dataset | **PASS (scoped)** |
| **F22** | Stage 4 / S4 | Trần round-robin inner loop trong tìm kiếm kết hợp | **PASS (scoped)** |
| **R2-N02**| Stage 3 / S3 | Cấu hình mặc định parser identity `cloudflare_native_v2` trong pipeline ingestion | **PASS (scoped)** |
| **R5-N01**| Stage 4 / S4 | Khẳng định trần 100 ứng viên hybrid và cascade qua các giai đoạn downstream | **PASS (scoped)** |
| **R5-N02**| Stage 7 / S7 | Đồng bộ tên cơ sở (basename) của các file test query understanding | **PASS (scoped)** |

---

## 2. Trạng thái Các Cổng Nghiệm thu (Gates G3 – G8)

Đối chiếu trung thực với tiêu chí kỹ thuật:
- **Cổng G3 (Stage 3):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F03, F24, R2-N02; toàn bộ test offline pass. Cần bổ sung bằng chứng đo đạc cgroup v2 trên môi trường Linux CI.
- **Cổng G4 (Stage 4):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F05, F23; tests offline pass 171/171. Thiếu bằng chứng kiểm định thực tế trên server Qdrant ghim định danh (F25).
- **Cổng G5 (Stage 5):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F08 (kiểm checksum chunk content fail-closed, lưu trữ ordered/window pair frequencies); tests offline pass 36/36. Thiếu bằng chứng kiểm tra chuyển đổi trên worker DB thực tế.
- **Cổng G6 (Stage 6):** **CHƯA ĐẠT**. Hợp đồng reranker đạt 34/34 tests, nhưng bị chặn bởi các cổng upstream G4/G5 và thiếu bằng chứng đo đạc telemetry live provider.
- **Cổng G7 (Stage 7):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F13, F14, F18; tests offline pass 63/63. Cần thu thập bằng chứng runtime end-to-end với full request fences.
- **Cổng G8 (Stage 8):** **CHƯA ĐẠT**. Đã sửa cú pháp F17 (PowerShell parser 0 lỗi, 48/48 runtime evidence tests pass), F21 (runbook declared settings), R5-N03 (báo cáo chuẩn hóa). Bị chặn bởi **F16 (chưa có gói held-out mới >= 12 PDFs / 60 questions)** và các cổng upstream G3–G7.

---

## 3. Danh sách Commit HEAD của 6 Worktrees

| Stage / PR | Nhánh Git | Đường dẫn Worktree | Commit HEAD hiện hành |
|---|---|---|---|
| **S3** (PR #216) | `feat/retrieval-v3-document-understanding` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-document-understanding` | `2122e6186580fc28bf6eea4ea3afbe0554c194b1` |
| **S4** (PR #217) | `feat/retrieval-v3-dense-hybrid-search` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-dense-hybrid-search` | `c785161b687d80b000152e6cebd6445c7e1916c4` |
| **S5** (PR #218) | `feat/retrieval-v3-sequential-dependence-ranking`| `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-sequential-dependence-ranking`| `d123feb74fb1cc425353c64e7ebefba31a7d439c` |
| **S6** (PR #219) | `feat/retrieval-v3-reranking-evidence` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-reranking-evidence` | `7fb1795ae982db8200f1118f52263dfa258b46e8` |
| **S7** (PR #220) | `feat/retrieval-v3-query-understanding-coverage` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-query-understanding-coverage` | `cdc372769b70b82599a5a5fe66094cfa4cf4c4e8` |
| **S8** (PR #221) | `feat/retrieval-v3-integrated-release` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-integrated-release` | `[sẽ ghi nhận sau commit]` |

---

## 4. Cam kết Ràng buộc An toàn

1. **Ngân sách AI $0:** 100% Cloudflare Workers AI free tier, tuyệt đối không cài đặt hay sử dụng thư viện local model weights (`torch`, `onnx`, `fastembed`, `huggingface`).
2. **Kiến trúc Authoritative:** PostgreSQL là nguồn sự thật duy nhất cho documents, versions, chunks và corpus statistics. Qdrant chỉ là derived projection.
3. **Quy tắc Trích dẫn (ADR0007):** Các trang dài được chia thành nhiều chunks $\le 650$ tokens, tuyệt đối không tạo chunk xuyên trang.
4. **Giới hạn Quyền:** Giữ nguyên 6 PR đang mở; **tuyệt đối không merge main, không deploy production, không đóng Issue #153, và không tự ý ghi nhận owner acceptance.**
