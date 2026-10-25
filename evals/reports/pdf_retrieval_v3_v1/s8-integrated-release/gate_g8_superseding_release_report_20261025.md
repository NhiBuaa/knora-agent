# Retrieval V3 — Gate G8 Superseding Release & Remediation Report (R6)

- **Cổng nghiệm thu:** `Gate G8 (S8 Integrated Release & Remediation)`
- **Thời gian lập báo cáo:** `2026-10-25T18:10:00+07:00`
- **Nhánh tích hợp / Owning PR:** `feat/retrieval-v3-integrated-release` (PR #221)
- **Kế hoạch triển khai đã duyệt:** `docs/plans/2026-10-22-retrieval-v3-review-remediation.md` (§16 R6 tại commit `f706bf7c7e039ecd229dc767bb17a113cd5f562f`)
- **Tài liệu thay thế (Superseding):** Báo cáo này thay thế toàn bộ nội dung diễn giải của các báo cáo trước đó, khôi phục chính xác 100% ngữ nghĩa registry 32 IDs theo §16.2 và ghi nhận trung thực các giới hạn kỹ thuật / cổng chưa đạt.
- **Quyền hạn & Phạm vi:** *Báo cáo này là bằng chứng kỹ thuật phục vụ Independent Review và trình nghiệm thu; tuyệt đối KHÔNG tự ý ghi nhận owner acceptance, KHÔNG merge main, KHÔNG deploy production và KHÔNG đóng Issue #153.*

---

## 1. Bảng Tổng hợp 32 Dispositions theo Chuẩn Registry §16.2

### A. 15 Remediation Items (Sửa chữa theo kết quả Independent Review R5/R6)

| ID | Owning Stage / PR | Vấn đề được xác định trong Review | Giải pháp kỹ thuật đã triển khai | Trạng thái hiện tại |
|---|---|---|---|---|
| **F03** | S3 / PR #216 | Ghép block theo hình học nhưng tìm offset theo stream order; vỡ cấu trúc khi đảo stream | Thống nhất reading-order geometric assembly (`\n\n`.join), phân biệt văn xuôi 2 cột (`_is_prose_columns`) với bảng dữ liệu, gán monotonic offsets trực tiếp; loại bỏ fallback offset giả | **REMEDIATED** |
| **F24** | S3 / PR #216 | `ThreadPoolExecutor` context manager chặn thread sleep làm trễ timeout; parent RSS check chặn nhầm | Truyền deadline còn lại (`timeout=remaining`) trực tiếp vào transport HTTP client; quản lý executor rõ ràng với `shutdown(wait=False, cancel_futures=True)`; parent RSS check qua psutil; timeout ngắt ngay lập tức không rò rỉ thread | **REMEDIATED** |
| **F05** | S4 / PR #217 | Corpus transition (kể cả warm profile transition) bỏ sót canonical members trong `DocumentTable` | Cả cold activation và warm transition đều bắt buộc đối chiếu tập submission với toàn bộ tài liệu canonical unarchived trong workspace (`DocumentTable.archived.is_(False)`); thiếu tài liệu lập tức fail-closed | **REMEDIATED** |
| **F23** | S4 / PR #217 | Readback vector chuẩn hóa từ Qdrant chỉ kiểm tra cosine similarity, bỏ sót sai số tọa độ | Bỏ qua nới lỏng cosine, bắt buộc kiểm tra giới hạn sai số tọa độ tuyệt đối `max(|u_i - v_i|) <= 1e-4` trên vector chuẩn hóa đơn vị | **REMEDIATED** |
| **F25** | S4 / PR #217 | Qdrant configuration qualification thiếu actual pinned-server positive/negative/readback | Đã có validator collection configuration nghiêm ngặt (`native_search_index.py:186`); tuy nhiên **thiếu actual pinned Qdrant server evidence** ở môi trường live -> ghi nhận đúng trạng thái | **FAIL (thiếu actual server evidence)** |
| **F08** | S5 / PR #218 | Cache hit trả thống kê trước khi xác thực checksum, che giấu tamper chunk content | Luôn xác thực `sha256(chunk.content) == chunk.content_checksum` trên toàn bộ chunks trước khi trả cache; chunk bị tamper lập tức fail-closed và xóa cache; tính toán và lưu trữ unigram, ordered pair và window pair frequencies | **REMEDIATED** |
| **F13** | S7 / PR #220 | Snapshot khác rỗng vẫn bị coi là đủ proof cho absence; recovery materialize toàn bộ rows trước cap | Bắt buộc store chứng minh scope hoàn chỉnh (`has_complete_scope_proof(...) is True`) mới được trả `VERIFIED_ABSENT`, thiếu proof trả `UNVERIFIED`; áp dụng bound retrieval limit 1000 trong PostgreSQL query | **REMEDIATED** |
| **F14** | S7 / PR #220 | Đổi dấu câu (dấu phẩy `,`) là vượt kiểm tra hoán đổi dữ kiện 7/30 ngày; đồng nghĩa sai "bảo hành"="bảo trì" | Phân tách mệnh đề chặt chẽ theo dấu phẩy, chấm phẩy, chấm, xuống dòng; bắt buộc khớp số-đơn vị với nội dung mệnh đề nguồn; xóa bỏ cặp đồng nghĩa sai `("bảo hành", "bảo trì")`; chấp nhận paraphrase hợp lệ | **REMEDIATED** |
| **F18** | S7 / PR #220 | Follow-up bắt đầu bằng "Bao gồm những chương nào?" không neo vào tài liệu/câu hỏi trước | Mở rộng `_FOLLOWUP_PREFIX` và `_REFERENCE_CUE` nhận diện các câu hỏi tiếp nối ("bao gồm", "gồm những", "chương nào"), neo retrieval query vào chủ thể của turn trước | **REMEDIATED (scoped)** |
| **R3-N04**| S7 / PR #220 | Refusal bypass snapshot fence làm sai lệch read fence | Phân biệt pre-search clarification với post-retrieval refusal; chỉ bypass khi `CLARIFICATION_REQUIRED`, bảo toàn snapshot fence cho toàn bộ truy vấn tra cứu | **PASS (scoped)** |
| **F16** | S8 / PR #221 | Dataset 4 mẫu phát triển cũ không được đóng vai release held-out; thiếu sealed package >= 12 PDFs / 60 câu | Entrypoint release `load_release_dataset()` fail-closed từ chối dataset < 60 câu hoặc < 12 PDFs; **chưa có gói mới >= 12 PDFs / 60 questions từ curator/owner** -> ghi nhận blocker | **DEFECT (chờ sealed package)** |
| **F17** | S8 / PR #221 | Docker build context allowlist thiếu mã nguồn downstream; runtime admission nhận dummy testcases 0 calls; lỗi cú pháp script | Docker context allowlist cập nhật đủ 196 source files và 55 migrations cho toàn bộ downstream stages; runtime evidence `validate_release` reject dummy testcase 0 server/provider calls; sửa cú pháp script PowerShell | **REMEDIATED** |
| **F21** | S8 / PR #221 | Runbook dùng thuộc tính không khai báo; healthcheck rollback chỉ resolve một offline constant | Cập nhật runbook dùng `s.lexical_qdrant_url` đã khai báo; healthcheck rollback kiểm tra cấu hình đang phục vụ thực tế (Effective Running Configuration) qua API health endpoint và trạng thái database | **REMEDIATED** |
| **R2-N03**| S6 / PR #219 | Bảo toàn default test collection và contract của reranker | Toàn bộ hợp đồng reranker tại Stage 6 chạy thành công | **PASS (scoped)** |
| **R5-N03**| S8 / PR #221 | Báo cáo 32 IDs sai registry, gán số runtime/quality chưa được chứng minh | Lập báo cáo thay thế này (`gate_g8_superseding_release_report_20261025.md`) đúng chuẩn registry §16.2, ghi nhận trung thực trạng thái kỹ thuật và các điểm đang chờ | **REMEDIATED** |

---

### B. 17 Anti-Regression Items (Bảo toàn nguyên vẹn)

| ID | Phạm vi / Stage | Mô tả yêu cầu bất biến | Trạng thái |
|---|---|---|---|
| **N01** | Stage 3 / S3 | Bảo toàn Alembic migration sequence và database schema | **PASS (scoped)** |
| **F01** | Stage 3 / S3 | Python 3.12 dataclass super call / guard và tương thích typing kế thừa | **PASS (scoped)** |
| **F02** | Stage 3 / S3 | Cloudflare PDF understanding envelope parsing và wire format | **PASS (scoped)** |
| **F04** | Stage 3 / S3 | Giới hạn trang và token theo ADR0007 (1 trang vật lý <= 650 tokens, không xuyên trang) | **PASS (scoped)** |
| **F06** | Stage 4 / S4 | Giám sát cấu hình Cloudflare-only AI, không phát sinh chi phí ($0 budget) | **PASS (scoped)** |
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
- **Cổng G4 (Stage 4):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F05, F23, F17; tests offline pass. Thiếu bằng chứng kiểm định thực tế trên server Qdrant ghim định danh (F25).
- **Cổng G5 (Stage 5):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F08, F17; tests offline pass. Thiếu bằng chứng kiểm tra chuyển đổi trên worker DB thực tế.
- **Cổng G6 (Stage 6):** **CHƯA ĐẠT**. Hợp đồng reranker đạt 109/109 tests, F17 allowlist cập nhật, nhưng bị chặn bởi các cổng upstream G4/G5 và thiếu bằng chứng đo đạc telemetry live provider.
- **Cổng G7 (Stage 7):** **CHƯA ĐẠT**. Đã hoàn thành sửa code F13, F14, F18, F17; tests offline pass 89/89. Cần thu thập bằng chứng runtime end-to-end với full request fences.
- **Cổng G8 (Stage 8):** **CHƯA ĐẠT**. Đã sửa F16 (release entrypoint fail-closed khi thiếu quy mô), F17 (Docker allowlist 271 files, reject dummy testcase), F21 (effective running config check), R5-N03 (báo cáo chuẩn hóa). Bị chặn bởi **F16 (chưa có gói held-out mới >= 12 PDFs / 60 questions từ curator)** và các cổng upstream G3–G7.

---

## 3. Danh sách Commit HEAD của 6 Worktrees

| Stage / PR | Nhánh Git | Đường dẫn Worktree | Commit HEAD hiện hành |
|---|---|---|---|
| **S3** (PR #216) | `feat/retrieval-v3-document-understanding` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-document-understanding` | `b5632c9215ba05be6cebf473c52e6fca78e100f0` |
| **S4** (PR #217) | `feat/retrieval-v3-dense-hybrid-search` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-dense-hybrid-search` | `e5683b82aecbe506f91bfe3cb56862992f24e864` |
| **S5** (PR #218) | `feat/retrieval-v3-sequential-dependence-ranking`| `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-sequential-dependence-ranking`| `6cf6fdcb8fc2d29cdd7e05fa9c4358f69264a63c` |
| **S6** (PR #219) | `feat/retrieval-v3-reranking-evidence` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-reranking-evidence` | `cf84f937062f50a36e67fe57e27bbdb92218e080` |
| **S7** (PR #220) | `feat/retrieval-v3-query-understanding-coverage` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-query-understanding-coverage` | `a24d759fb042c74b78346505ed26b8fa251aa34c` |
| **S8** (PR #221) | `feat/retrieval-v3-integrated-release` | `C:\Developer\Projects\knora-agent-worktree\feat-retrieval-v3-integrated-release` | 7074a66670bc117d46f1deab23af5bf85c7892f9 |

---

## 4. Cam kết Ràng buộc An toàn

1. **Ngân sách AI $0:** 100% Cloudflare Workers AI free tier, tuyệt đối không cài đặt hay sử dụng thư viện local model weights (`torch`, `onnx`, `fastembed`, `huggingface`).
2. **Kiến trúc Authoritative:** PostgreSQL là nguồn sự thật duy nhất cho documents, versions, chunks và corpus statistics. Qdrant chỉ là derived projection.
3. **Quy tắc Trích dẫn (ADR0007):** Các trang dài được chia thành nhiều chunks $\le 650$ tokens, tuyệt đối không tạo chunk xuyên trang.
4. **Giới hạn Quyền:** Giữ nguyên 6 PR đang mở; **tuyệt đối không merge main, không deploy production, không đóng Issue #153, và không tự ý ghi nhận owner acceptance.**
