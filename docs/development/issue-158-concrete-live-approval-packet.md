# Gói Phê Duyệt Live Inference & Nghiệm Thu Công Cụ Đánh Giá V3 (Issue #158)

Tài liệu này là gói phê duyệt cụ thể (**Concrete Live Approval Packet V3**) theo quy định tại §8 Task T8 của kế hoạch chuẩn [`docs/plans/evaluation-tools-acceptance.md`](file:///C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance/docs/plans/evaluation-tools-acceptance.md) (bản sửa đổi v2 được Owner phê duyệt ngày 2026-10-24).

> [!IMPORTANT]
> **Trạng thái hiện tại**: Đang chờ Owner phê duyệt trước khi kích hoạt bất kỳ lệnh live nào.
> Mọi kết nối live inference (Cloudflare Workers AI) và export cloud (Langfuse) hiện đang ở trạng thái **TẮT (OFF)**.
> Tuyệt đối không tự động dispatch inference, không tự ý merge [PR #231](https://github.com/NhiBuaa/knora-agent/pull/231) vào `main`, và không tự ý đóng [Issue #158](https://github.com/NhiBuaa/knora-agent/issues/158).

---

## 1. Cơ sở Kỹ thuật & Pinned Pins

- **Issue**: [#158](https://github.com/NhiBuaa/knora-agent/issues/158)
- **Pull Request**: [#231](https://github.com/NhiBuaa/knora-agent/pull/231)
- **Nhánh triển khai**: `feat/evaluation-tools-acceptance`
- **Full Tested Code Commit SHA**: `f98777396faac0effbf735ad5935bddeb7a89f57`
- **Worktree**: `C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance`
- **Kế hoạch đã duyệt**: [`docs/plans/evaluation-tools-acceptance.md`](file:///C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance/docs/plans/evaluation-tools-acceptance.md) (§8 bản sửa đổi v2)
- **CI Required Run**: [Run 40067138930](https://github.com/NhiBuaa/knora-agent/actions/runs/40067138930)
- **Kết quả kiểm chứng offline**: 512 tests passed, 0 failures, `ruff check`/`format` clean, OpenAPI schema clean, `git diff --check` clean.

---

## 2. Kiểm kê Dữ liệu Pinned (12 Items) & Provenance (R4, R11, T1)

### 2.1. Sáu (6) Real ANSWER Captures (Nhánh Saved - Baseline B Continuation)
Được kiểm kê tại [`docs/development/issue-158-pilot-audit-and-input-inventory.md`](file:///C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance/docs/development/issue-158-pilot-audit-and-input-inventory.md), khớp 100% SHA256 với archive manifest, bảo toàn nguyên bản native `attempt` (=2), `run_id`, `trace_id`, candidates `SELECTED` aliased (`E1, E2, E3` cho ca `045`), và load đúng chunks PDF Gold của #153 qua `load_approved_pdf_chunks`:

1. **`pdf-v3-004`**: Trace `2a0e4c698f1649989d44f6f7b1db92c3`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-004:2"`
2. **`pdf-v3-005`**: Trace `5b3e2b2fbba34e3489fe203a72dff124`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-005:2"`
3. **`pdf-v3-012`**: Trace `f8ebff5d75d34f26b52a95c9a9244c41`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-012:2"`
4. **`pdf-v3-014`**: Trace `43102c011e404be1b88e00e47087858c`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-014:2"`
5. **`pdf-v3-019`**: Trace `8bb40fa3d66649f8af6256c9a35e7df5`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-019:2"`
6. **`pdf-v3-032`**: Trace `ad4928cf508543f886f3db537db1d3f5`, attempt 2 (follow-up của `004` trong cùng conversation context)

### 2.2. Hai (2) REFUSAL Controls (0 calls, deterministic)
1. **`pdf-v3-053`**: Trace `9557a27eb2a64c489c4fc07b539ba947` (expected REFUSAL -> actual REFUSAL: CORRECT_REFUSAL)
2. **`pdf-v3-002`**: Trace `8c8bfa55a6d5423f85890b07b396e959` (expected ANSWER -> actual REFUSAL: FALSE_REFUSAL control)

### 2.3. Bốn (4) Synthetic Controls (Deterministic offline variants, kỳ vọng trượt < 0.5)
1. **`pdf-v3-004-wrong-fact`**: Parent `004` | Phép biến đổi: "Cảnh báo P1 phải báo trực trong 150 phút." | Kỳ vọng trượt: `correctness < 0.5`
2. **`pdf-v3-005-off-topic`**: Parent `005` | Phép biến đổi: "Màu yêu thích của tôi là xanh dương. Tôi thích thời tiết đẹp." | Kỳ vọng trượt: `answer_relevancy < 0.5`
3. **`pdf-v3-014-unsupported`**: Parent `014` | Phép biến đổi: "Evidence means approval by the Tokyo office within 3 minutes..." | Kỳ vọng trượt: `faithfulness < 0.5`
4. **`pdf-v3-012-missing-exception`**: Parent `012` | Phép biến đổi: "Bản nháp thường giữ 30 ngày. Hồ sơ tranh chấp không có quy định riêng." | Kỳ vọng trượt: `correctness < 0.5`

### 2.4. Một (1) Ragas Proposal Batch
- 1 HTTP attempt, `@cf/openai/gpt-oss-20b`, tối đa 2 candidate drafts tiếng Việt, sinh từ source chunks đã pin thuộc #153.
- Kết quả đưa vào phụ lục độc lập, không tự động thăng hạng (promote) vào Gold.

---

## 3. Phân bổ Ngân sách, Hạn mức & Invariants V3 (R1, R2, R3, R5)

| Slot | Mục tiêu | Số calls tối đa | Trạng thái nhánh Saved |
| :--- | :--- | :---: | :--- |
| `corpus_prepare` | Fallback chuẩn bị corpus (tối đa 6 PDF) | 6 | **SKIPPED** (0 calls, dùng saved branch) |
| `qa_gold_v1_answer` | Fallback sinh đáp án 6 câu | 12 | **SKIPPED** (0 calls, dùng saved branch) |
| `ragas_vi_draft` | Sinh draft tiếng Việt | 1 | **Sẵn sàng chạy** |
| `judge_real` | Chấm 6 captures thật (DeepEval GEval, Relevancy, Faithfulness) | 72 | **Sẵn sàng chạy** (tối đa 12 calls/item) |
| `judge_synthetic` | Chấm 4 synthetic controls | 48 | **Sẵn sàng chạy** (tối đa 12 calls/item) |
| `refusal_deterministic` | 2 refusal controls | 0 | **Deterministic** (0 calls) |
| **Tổng cộng dự kiến** | | **121 attempts** | Dưới trần cứng 139 attempts |

- **Bảo toàn Invariant SQLite 5-chiều**: Invariant `requests == SUM(items.attempts)` được kiểm toán nghiêm ngặt ở mức cơ sở dữ liệu.
- **Cô lập Item Counters (Per-item Cap)**: Mỗi item có trần cứng $\le 12$ attempts độc lập. Một item đạt 12 attempts sẽ dừng với `LIVE_ITEM_CAP`, tuyệt đối không chuyển nhượng attempts giữa các items.
- **Atomic `first_dispatch_at` Anchoring**: Ghim thời điểm khởi động đầu tiên một cách nguyên tử (`WHERE first_dispatch_at IS NULL`), neo cửa sổ hạn chót 7 ngày.
- **Proof Refresh Append-Only**: Cập nhật proof quota trực tiếp trong cùng file journal, bảo toàn approval ban đầu.
- **Mô hình**:
  - Generation / Ragas / Judge: `@cf/openai/gpt-oss-20b` (max input 8192 bytes, max output 2048 tokens).
  - Không fallback provider, redirects OFF, retries OFF, timeout 30s, concurrency=1.
- **Chi phí tiền mặt**: **USD 0 (Bắt buộc Cloudflare Workers Free)**.

---

## 4. Giới hạn Thời gian, Cửa sổ & Trách nhiệm Tài nguyên

- **Số lần khởi động Stack Runtime**: **0** (Nhánh saved captures hoàn toàn không cần khởi động local Docker runtime stack!).
- **Cửa sổ thực thi**: Tối đa 2 windows × tối đa 60 phút mỗi window.
- **Hạn chót gói (Deadline)**: 7 ngày kể từ first dispatch anchor.
- **Cơ chế dừng (Emergency Stop)**: Ghi vào `.stops` journal sẽ lập tức hủy bỏ mọi quyền dispatch tiếp theo.

---

## 5. Langfuse Bridge Hardened (R7, R8, R9, T6)

- **Vùng Cloud**: `https://jp.cloud.langfuse.com` (Hobby Free, owner-only).
- **Điều kiện tiên quyết Dual Digests**: Trước POST đầu tiên, bắt buộc cung cấp cả `canary_payload_sha256` và `real_payload_sha256`. Nếu digest tính toán từ payload thực không khớp, bridge dừng ngay với `CANARY_SHA_MISMATCH` hoặc `REAL_SHA_MISMATCH`.
- **Dọn dẹp Bắt buộc khi Lỗi**: Toàn bộ thao tác POST được bọc trong `try...finally/except`; nếu xảy ra bất kỳ lỗi nào sau POST, bridge tự động gọi `delete_traces` và `verify_deleted` để xóa sạch traces đã đẩy lên cloud.
- **Hỗ trợ Reconcile & Phân trang**: Hỗ trợ `reconcile_receipt` để dọn dẹp các trace còn sót lại từ receipt trước đó; hỗ trợ phân trang cho `readback_observations` và `readback_scores`.
- **Hạn mức nghiêm ngặt**:
  - Tối đa **2 POSTs**: 1 canary (1 trace + 1 observation) + 1 real (tối đa 2 traces + 2 observations).
  - Tối đa **2 DELETEs**: 1 xóa canary + 1 xóa real (chỉ xóa đúng exact owned IDs).
  - Tối đa **120 GETs** polling readback verification (concurrency=1, max 10 GET/phút).
  - **0 scores**: Tuyệt đối không gửi hay tạo scores trên cloud.
- **Trạng thái hiện tại**: **OFF**. Chỉ kích hoạt khi có lệnh explicit của Owner.

---

## 6. Tiêu chí Acceptance Finalizer (R6, R11, T5)

- **10 Judged Items (6 real + 4 synthetic)**: Bắt buộc đủ 3 metrics (`correctness`, `answer_relevancy`, `faithfulness`) có trạng thái `scored` và điểm số hữu hạn trong đoạn $[0, 1]$.
- **4 Synthetic Controls**: Bắt buộc điểm số $< 0.5$ tại metric chỉ định:
  - `pdf-v3-004-wrong-fact`: `correctness < 0.5`
  - `pdf-v3-005-off-topic`: `answer_relevancy < 0.5`
  - `pdf-v3-014-unsupported`: `faithfulness < 0.5`
  - `pdf-v3-012-missing-exception`: `correctness < 0.5`
  Nếu bất kỳ control nào $\ge 0.5$, finalizer lập tức chặn nghiệm thu với lỗi `CONTROL_NOT_REJECTED`.
- **Human Labels Validation**: Digest của gói nhãn người phải khớp chính xác với `packet_sha256` của gói câu hỏi được xuất (`HUMAN_PACKET_DIGEST_MISMATCH`).

---

## 7. Trình tự Ba Bước Nghiệm Thu Có Chủ Đích (§8.5)

1. **Bước 1 (Hiện tại - Task T8)**: Owner xem xét và phê duyệt Gói Live Cụ thể V3 này.
2. **Bước 2 (Task T9)**: Sau khi được duyệt:
   - Chạy preflight kiểm tra cấu hình.
   - Gọi 1 HTTP attempt cho Ragas sinh draft tiếng Việt.
   - Runner xuất gói Human Review Blind 12 mục (`issue-158-human-review-packet.md`).
   - **Dừng chờ Owner chấm nhãn độc lập** (tuyệt đối không judge trước khi Owner trả nhãn).
3. **Bước 3 (Task T9 tiếp nối)**:
   - Nhận nhãn độc lập từ Owner, validate và freeze nhãn.
   - Chạy DeepEval judge từng item với transport chuẩn của LiveAdmission.
   - Chạy chu trình Langfuse pilot (nếu có key) hoặc xác nhận an toàn.
   - Chạy acceptance finalizer, lập dossier nghiệm thu cuối cùng trình Owner đóng [Issue #158](https://github.com/NhiBuaa/knora-agent/issues/158).

---

## 8. Phiếu Phê Duyệt Của Chủ Sở Hữu (Owner Decision)

Để bắt đầu Bước 2 (Preflight, Ragas & Xuất gói Human Review), xin Owner xác nhận các mục sau:

- [ ] **1. Phê duyệt Gói Envelope V3** cho commit SHA `f98777396faac0effbf735ad5935bddeb7a89f57` với trần tối đa 121 inference calls (USD 0).
- [ ] **2. Phê duyệt Nhánh Saved Captures**: Xác nhận skip `corpus_prepare` và `qa_gold_v1_answer`, sử dụng trực tiếp 6 clean captures từ baseline B continuation.
- [ ] **3. Phê duyệt Quy trình Human Review Trước Judge**: Đồng ý xuất gói 12 mục để Owner trả nhãn độc lập trước khi kích hoạt DeepEval judge.
- [ ] **4. Quyết định Pilot Langfuse**: Xác nhận trạng thái chạy chu trình pilot Langfuse (chạy với key hợp lệ hay giữ tắt hoàn toàn trong đợt này).
