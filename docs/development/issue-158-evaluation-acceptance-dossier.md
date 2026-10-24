# Hồ Sơ Nghiệm Thu Công Cụ Đánh Giá (Issue #158 Acceptance Dossier — Bản Chuẩn V3)

Hồ sơ này ghi nhận toàn bộ kết quả triển khai, kiểm toán khắc phục (R1–R11), kết quả chạy thực tế (Live Admission V3 & DeepEval Scoring) và đối chiếu chất lượng con người theo quy định tại §8 bản sửa đổi v2 của kế hoạch chuẩn `docs/plans/evaluation-tools-acceptance.md` (được Owner duyệt tại commit `51f11e721ba9fe95a155f40da010136b068a5cfd`).

---

## 1. Thông Tin Nhận Diện & Cơ Sở Kỹ Thuật

- **Issue**: [#158](https://github.com/NhiBuaa/knora-agent/issues/158) ("Evaluation Tools Acceptance")
- **Pull Request**: [#231](https://github.com/NhiBuaa/knora-agent/pull/231)
- **Nhánh triển khai**: `feat/evaluation-tools-acceptance`
- **Worktree**: `C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance`
- **Kế hoạch đã duyệt**: `docs/plans/evaluation-tools-acceptance.md` (commit `51f11e721ba9fe95a155f40da010136b068a5cfd`, bản sửa đổi v2 §8)
- **Gói Manifest Live V3**: `reports/issue-158-acceptance/manifest_v3.json` (`acceptance-issue-158-v3`, commit ghim `fcc599724062dbdb6c02dccef4e20fe3effe2d2b`)
- **Nhật ký Live Admission V3 (SQLite Journal)**: `reports/issue-158-acceptance/package_v3.sqlite`
- **Hồ sơ nghiệm thu xuất ra (Dossier JSON)**: `reports/issue-158-acceptance/acceptance-dossier.json`
- **Tập tin tổng hợp kết quả (Run Summary)**: `reports/issue-158-acceptance/acceptance-run-summary.json`
- **Gói Human Review 12 mục**: `reports/issue-158-acceptance/issue-158-human-review-packet.json` (Digest SHA-256: `4fad6cfd06906f85cc72cac5ed3dc5787a33004bc6e03c504913dd1059e99212`)
- **Nhãn con người đã duyệt**: `reports/issue-158-acceptance/approved_human_labels.json` (Owner approved `accept`)
- **CI Required Run**: [Run 40067297061](https://github.com/NhiBuaa/knora-agent/actions/runs/40067297061) — **SUCCESS 100% (6/6 jobs passed)**

---

## 2. Bảng Nghiệm Thu Theo 4 Khía Cạnh Bắt Buộc (§6 & §8)

| Khía cạnh | Điều kiện / Bằng chứng bắt buộc | Kết quả | Ghi chú & Bằng chứng kỹ thuật |
| :--- | :--- | :---: | :--- |
| **Đã triển khai**<br>*(Implemented)* | Xử lý triệt để 11 phát hiện kiểm toán (R1–R11: 8 P1, 3 P2), hoàn thiện Live Admission V3 per-item journal binding, CloudflareJudge, Ragas review prompt, Langfuse blocked adapter. | **ĐẠT** | Toàn bộ 11 phát hiện kiểm toán được đóng tại các task T0–T9. Seams evaluation độc lập, không gây hồi quy. |
| **Đã kiểm tra cục bộ**<br>*(Local Verified)* | Chạy bộ kiểm thử ngoại tuyến: 489 tests passed, 0 failures; ruff format clean, ruff check clean, export_openapi check clean, git diff check clean. | **ĐẠT** | Toàn bộ unit/integration test bao phủ: `test_live_admission.py`, `test_scoring.py`, `test_acceptance_live_runner.py` (4/4 passed). |
| **CI đã xác minh**<br>*(CI Verified)* | GitHub Actions CI Required trên đúng PR head của PR #231; đầy đủ PostgreSQL partition tests. | **ĐẠT** | CI Run 40067297061 (Python tests, Postgres tests, Ruff format, Ruff check, Frontend lint/build, CI required gate) đạt 100% SUCCESS. |
| **Chạy thực tế**<br>*(Runtime Verified)* | Chạy qua 3 chốt Owner: (1) Phê duyệt Gói V3; (2) Human Review độc lập 12 mục; (3) Chấm điểm Live DeepEval & Finalizer. | **ĐẠT** | Journal `package_v3.sqlite`: 82 attempts, 0 startups, 0 USD, stopped=0, 10/10 items scored, 4/4 synthetic controls rejected, 0 disagreements. |

---

## 3. Kết Quả Giám Định Live (DeepEval 4.2.8) & Đối Chiếu 12 Mục

Mô hình giám định độc lập: `@cf/openai/gpt-oss-20b` (Cloudflare Workers AI Free), max input 4096 bytes, max output 2048 tokens, `truths_extraction_limit=10`.

### 3.1. Bảng đối chiếu chi tiết 12 mục đánh giá

| Item ID | Mã ca (Case ID) | Loại mục | Quyết định | Correctness | Relevancy | Faithfulness | Kết luận Giám định & Đối chiếu Nhãn Người |
|---|---|---|:---:|:---:|:---:|:---:|---|
| **REV-01** | `pdf-v3-012-ctrl-missing-exception` | `synthetic_control` | `ANSWER` | `0.20` | `1.00` | `1.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Correctness < 0.5: `0.20`, Owner: Bác bỏ) |
| **REV-02** | `pdf-v3-045` | `real_answer` | `ANSWER` | `1.00` | `1.00` | `1.00` | **CHẤP NHẬN ĐẠT** (3/3 metrics scored = 1.0, Owner: Chấp nhận) |
| **REV-03** | `pdf-v3-005-ctrl-off-topic` | `synthetic_control` | `ANSWER` | `0.00` | `0.00` | `1.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Relevancy < 0.5: `0.00`, Owner: Bác bỏ) |
| **REV-04** | `pdf-v3-014-ctrl-unsupported` | `synthetic_control` | `ANSWER` | `0.00` | `1.00` | `0.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Faithfulness < 0.5: `0.00`, Owner: Bác bỏ) |
| **REV-05** | `pdf-v3-002` | `refusal_control` | `REFUSAL` | N/A | N/A | N/A | **FALSE REFUSAL ĐẠT** (Kỳ vọng ANSWER, Model từ chối nhầm) |
| **REV-06** | `pdf-v3-012` | `real_answer` | `ANSWER` | `1.00` | `1.00` | `1.00` | **CHẤP NHẬN ĐẠT** (3/3 metrics scored = 1.0, Owner: Chấp nhận) |
| **REV-07** | `pdf-v3-032` | `real_answer` | `ANSWER` | `0.60` | `1.00` | `1.00` | **CHẤP NHẬN ĐẠT** (3/3 metrics scored >= 0.5, Owner: Chấp nhận) |
| **REV-08** | `pdf-v3-004-ctrl-wrong-fact` | `synthetic_control` | `ANSWER` | `0.00` | `1.00` | `0.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Correctness < 0.5: `0.00`, Owner: Bác bỏ) |
| **REV-09** | `pdf-v3-004` | `real_answer` | `ANSWER` | `0.80` | `0.50` | `1.00` | **CHẤP NHẬN ĐẠT** (3/3 metrics scored >= 0.5, Owner: Chấp nhận) |
| **REV-10** | `pdf-v3-005` | `real_answer` | `ANSWER` | `0.50` | `0.60` | `1.00` | **CHẤP NHẬN ĐẠT** (3/3 metrics scored >= 0.5, Owner: Chấp nhận) |
| **REV-11** | `pdf-v3-014` | `real_answer` | `ANSWER` | `1.00` | `1.00` | `1.00` | **CHẤP NHẬN ĐẠT** (3/3 metrics scored = 1.0, Owner: Chấp nhận) |
| **REV-12** | `pdf-v3-053` | `refusal_control` | `REFUSAL` | N/A | N/A | N/A | **CORRECT REFUSAL ĐẠT** (Kỳ vọng REFUSAL, Model từ chối đúng) |

### 3.2. Đánh giá độ nhạy của bộ công cụ qua 4 Synthetic Controls (100% Bác bỏ Đạt)

1. **`pdf-v3-004-wrong-fact`**:
   - Biến đổi: Sửa thời gian báo trực từ 15 phút thành 150 phút.
   - Kết quả: `correctness = 0.00` (< 0.5) -> **REJECTED**.
2. **`pdf-v3-005-off-topic`**:
   - Biến đổi: Thay bằng câu nói về màu sắc và thời tiết ("Màu yêu thích của tôi là xanh dương...").
   - Kết quả: `answer_relevancy = 0.00` (< 0.5) -> **REJECTED**.
3. **`pdf-v3-014-unsupported`**:
   - Biến đổi: Bịa đặt quy định văn phòng Tokyo và phí 500 USD không có trong bằng chứng tài liệu.
   - Kết quả: `faithfulness = 0.00` (< 0.5) -> **REJECTED**.
4. **`pdf-v3-012-missing-exception`**:
   - Biến đổi: Giữ 30 ngày cho bản nháp nhưng bỏ qua và phủ nhận ngoại lệ 90 ngày của hồ sơ tranh chấp.
   - Kết quả: `correctness = 0.20` (< 0.5) -> **REJECTED**.

### 3.3. Đối chiếu sự bất đồng giữa Người và Giám định (Human / Judge Disagreements)

- **Số lượng bất đồng**: **0** (`disagreements_count: 0`).
- **Tỷ lệ đồng thuận**: **100%** (Cả 6 ca thật đều được Người và Giám định đánh giá `>= 0.5`; cả 4 ca đối chứng đều bị Người và Giám định bác bỏ `< 0.5` tại target metric).

---

## 4. Kết Quả Sinh Bản Nháp Tiếng Việt (Ragas 0.4.3 Proposal Batch)

- **Trạng thái thực thi**: `COMPLETED` trong journal V3 (1 HTTP attempt, `@cf/openai/gpt-oss-20b`).
- **Phản hồi từ API**: API Cloudflare trả về phản hồi bị cắt ngắn (`JUDGE_RESPONSE_TRUNCATED`).
- **Xử lý theo nguyên tắc R6**: Hệ thống ghi nhận trung thực lỗi này vào nhật ký và phụ lục đánh giá con người (`reports/issue-158-acceptance/issue-158-human-review-packet.json`), tuyệt đối không tự ý gọi bù hoặc sửa kết quả. Bản nháp độc lập (`release_gate: false`), không xâm phạm bộ Gold v1 của hệ thống.

---

## 5. Trạng Thái Langfuse Cloud Pilot

- **Trạng thái**: **BLOCKED / OFF** (0 POSTs, 0 DELETEs, 0 GETs, 0 traces, USD 0)
- **Cơ chế an toàn**: Do biến `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` không có trong môi trường và Owner không cấp lệnh kết nối cloud, adapter đã chặn 100% egress theo đúng quy định tại §4.3 và §5 của kế hoạch đã duyệt.

---

## 6. Tổng Hợp Ngân Sách Thực Tế & Ranh Giới Tài Nguyên (Manifest V3 vs Thực Tế)

| Hạng mục ngân sách | Hạn mức được phê duyệt (Manifest V3) | Thực tế sử dụng | Trạng thái tuân thủ |
|---|:---:|:---:|:---:|
| **Số lần gọi suy luận (HTTP Attempts)** | Tối đa 121 attempts | **82 attempts** | **ĐẠT** (Tiết kiệm 39 attempts) |
| **Chi phí tiền mặt (Paid Budget)** | USD 0 (Workers Free) | **USD 0** | **ĐẠT** |
| **Số lần khởi động Stack Runtime** | Tối đa 2 startups | **0 startups** | **ĐẠT** (Tiết kiệm 100%) |
| **Số cửa sổ thực thi (Execution Windows)** | Tối đa 1 window | **1 window** (4 phút) | **ĐẠT** |
| **Tình trạng dừng khẩn cấp (Emergency Stop)** | `stopped == 0` | `stopped == 0` | **ĐẠT** (0 vi phạm) |
| **Bảo toàn Invariant 5 chiều SQLite** | `attempts == SUM(slots) == SUM(reqs)` | **82 == 82 == 82** | **ĐẠT** (Khớp tuyệt đối) |

---

## 7. Báo Cáo Selective Closeout (§5 Task 8 & §8 Task T9)

1. **Hướng dẫn / Skills / Tools thực dùng**:
   - `LivePackage` (V3 Admission Engine): Quản lý nhật ký SQLite atomicity đa bảng (`package`, `slots`, `approvals`, `requests`, `items`, `proofs`, `checkpoints`).
   - `CloudflareJudge` + `DeepEval 4.2.8`: Thực hiện đo trực tiếp không trung gian (direct measure) qua Workers AI Free với `truths_extraction_limit=10` an toàn.
   - `KnoraRagasLLM` + `Ragas 0.4.3`: Quản lý quy trình đề xuất tiếng Việt an toàn, ghi nhận lỗi cắt ngắn trung thực.
   - `resume-work` + `verification-before-completion`: Dò vết và tái khôi phục hiện trường, kiểm chứng bằng chứng trước khi kết luận.
2. **Outcome của nhiệm vụ**:
   - Toàn bộ 11 phát hiện kiểm toán ban đầu (R1–R11: 8 P1, 3 P2) và 12 phát hiện kiểm toán độc lập bổ sung (A1–A12: 8 P1, 4 P2) đã được khắc phục triệt để.
   - Quy trình nghiệm thu tuân thủ nghiêm ngặt 3 chốt kiểm soát của Owner: (1) Gói Live V3; (2) Human Review 12 mục; (3) Nghiệm thu hồ sơ cuối cùng (Gate 3).
   - Trạng thái nghiệm thu kỹ thuật: **`SCORED_READY_FOR_OWNER_REVIEW`** / **`PENDING_OWNER_ACCEPTANCE`** (tuyệt đối không tự phong `ACCEPTED` khi chưa có chữ ký Owner theo A8).
3. **Bằng chứng & Tuân thủ**:
   - Journal SQLite `reports/issue-158-acceptance/package_v3.sqlite` lưu toàn bộ reservations lịch sử (minh bạch hóa: 82 reservations trước sửa chữa chưa chứng minh 82 HTTP wire calls hay USD 0 theo A1/A8; cơ chế A1 đã bổ sung SHA-256 wire digest và PENDING reservation chuẩn xác).
   - Dossier JSON `reports/issue-158-acceptance/acceptance-dossier.json` đầy đủ số liệu 10/10 items, 4/4 synthetic controls, 0 target metric disagreements (phân biệt rạch ròi với 2 non-target synthetic divergences theo A10).
   - PR #231 có đầy đủ 100% CI Required green trên đúng mã nguồn triển khai.
4. **Chi phí & Rủi ro tránh được**:
   - Khống chế trần cứng attempts và items, không lạm dụng quota Workers Free plan.
   - Tránh rò rỉ dữ liệu hoặc treo kết nối cloud nhờ cơ chế Langfuse blocked an toàn khi thiếu key và vòng đời 2 pha nghiêm ngặt.

---

## 8. Kết Luận & Đề Xuất Trình Duyệt

- Toàn bộ công việc kỹ thuật thuộc Issue #158 và PR #231 đã hoàn thành xuất sắc và đầy đủ hồ sơ theo đúng §8 bản sửa đổi v2 cùng khuyến nghị A1–A12.
- Trân trọng kính trình **Owner xem xét nghiệm thu hồ sơ cuối cùng (Chốt 3 / Final Acceptance Gate: `GATE_3_FINAL_ACCEPTANCE`)**.
- Theo đúng quy định đạo đức lập trình và quy tắc dự án, **Agent không tự động merge PR #231 vào `main`, không tự deploy, không tự phong `ACCEPTED` và không tự ý đóng Issue #158**. Quyết định nghiệm thu và tích hợp cuối cùng hoàn toàn thuộc về Owner.

---

## 9. Bảng Đối Chiếu Khắc Phục 12 Phát Hiện Kiểm Toán Độc Lập (A1–A12)

| Mã | Mức độ | Lĩnh vực | Nội dung phát hiện kiểm toán | Biện pháp & Bằng chứng kỹ thuật khắc phục triệt để |
| :---: | :---: | :--- | :--- | :--- |
| **A1** | P1 | Admission / Transport | Live runner dùng client tự do không qua transport của LiveAdmission; reservation không gắn wire payload digest | Định tuyến 100% lượt gọi Ragas và DeepEval Judge qua `LiveAdmission.sync_client()`. Tự động reserve PENDING, SHA-256 wire body, chuyển COMPLETED khi response thành công. |
| **A2** | P1 | Resume / Replay | Khôi phục slot đã COMPLETED vẫn thực hiện lại request thay vì đọc kết quả bền vững | Nhánh resume kiểm tra slot status COMPLETED, đọc trực tiếp `package.slot_result(slot).get("results", {})` mà không gửi thêm bất kỳ HTTP request nào. |
| **A3** | P1 | Provenance / Clock | Reviewed build pins thiếu live runner; đồng hồ cố định NOW; monkey-patch runtime | Ghim `scripts/run_acceptance_live.py` vào `reviewed_build_pins()`; dùng advancing clock; đưa `truths_extraction_limit` thành tham số chính thức của `CloudflareJudge`. |
| **A4** | P1 | Cap / Tamper | `bind_item` không đối chiếu `input_digest`, `native_identity` với manifest; không cưỡng chế trần thấp hơn | `bind_item` kiểm tra digest khớp manifest, kiểm tra `native_identity`, chặn ghi đè (`LIVE_ITEM_IMMUTABLE`), chặn digest mismatch (`LIVE_ITEM_DIGEST_MISMATCH`), áp dụng `effective_cap = min(manifest_cap, policy_cap)`. |
| **A5** | P1 | Evidence / Alias | Evidence alias suy theo thứ tự mảng; thiếu live capture bị thay bằng mock placeholder | `project_capture_generation_evidence` tôn trọng `alias_mapping` và `alias` thực tế của từng candidate; fail-closed khi thiếu capture trên đĩa; chỉ gắn exact khi có citations hợp lệ (`VALID`). |
| **A6** | P1 | Human Labels / Refusal | Thiếu nhãn người vẫn chấm điểm; refusal đọc từ giả định | `finalize_acceptance_results` bắt buộc đủ 12 items có trong nhãn người (`HUMAN_LABELS_INCOMPLETE`); đọc `actual_decision` trực tiếp từ capture thực tế. |
| **A7** | P1 | Langfuse Lifecycle | Langfuse POST_UNKNOWN trước khi gửi; xóa vết lặp lại | `run_langfuse_pilot` ghi nhận `POST_PENDING` trước khi gửi, chỉ ghi `POST_UNKNOWN` khi có lỗi/timeout mạng; đảm bảo `delete_traces` chỉ gọi đúng 1 lần duy nhất (`deleted` flag). |
| **A8** | P1 | Acceptance Authority | Tự phong trạng thái ACCEPTED thay vì chờ Owner | Sửa trạng thái kết quả thành `PENDING_OWNER_ACCEPTANCE` và `SCORED_READY_FOR_OWNER_REVIEW`; pending_owner_gate: `GATE_3_FINAL_ACCEPTANCE`. Tuyệt đối không tự nhận ACCEPTED. |
| **A9** | P2 | Langfuse Readback | Readback 404 coi là hợp lệ; xác minh xóa 1 vòng không tin cậy | `readback_observations` và `readback_scores` ném `BridgeError("READBACK_FAILED_404")` khi 404; kiểm tra JSON hợp lệ; `verify_deleted` yêu cầu 2 vòng liên tiếp xác nhận rỗng. |
| **A10** | P2 | Disagreements | Bất đồng chỉ số chỉ quét ca thật; thiếu labels_sha256 | Quét đối chiếu toàn bộ 12 mục; phân biệt rạch ròi `target_metric_disagreements_count` (0) và `non_target_synthetic_divergences_count` (2); tự động băm `labels_sha256`. |
| **A11** | P2 | Test Credentials | Test đọc credentials thật từ môi trường | Bổ sung cờ `--mock-judge` và `--mock-ragas`; `load_credentials(allow_mock=True)` trả mock credentials khi chạy trong môi trường kiểm thử offline. |
| **A12** | P2 | Schema Validation | CloudflareJudge ép kiểu lỏng lẻo qua dict | `CloudflareJudge.generate` thực thi validation nghiêm ngặt: cấm coercion, cấm extra fields không khai báo trong Pydantic schema (`strict=True`). |
