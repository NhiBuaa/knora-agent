# Gói Phê Duyệt Live Inference & Nghiệm Thu Công Cụ Đánh Giá (Issue #158)

Tài liệu này là gói phê duyệt cụ thể (**Concrete Live Approval Packet**) theo quy định tại §5 Task 6 của `docs/plans/evaluation-tools-acceptance.md` (được Owner duyệt tại commit `51f11e721ba9fe95a155f40da010136b068a5cfd`).

> [!IMPORTANT]
> **Trạng thái hiện tại**: Đang chờ Owner phê duyệt trước khi kích hoạt bất kỳ lệnh live nào.
> Mọi kết nối live inference (Cloudflare Workers AI) và export cloud (Langfuse) hiện đang ở trạng thái **TẮT (OFF)**.
> Tuyệt đối không tự động dispatch inference, không tự ý merge PR #231 vào `main`, và không tự ý đóng Issue #158.

---

## 1. Cơ sở Kỹ thuật & Pinned Pins

- **Issue**: [#158](https://github.com/NhiBuaa/knora-agent/issues/158)
- **Pull Request**: [#231](https://github.com/NhiBuaa/knora-agent/pull/231)
- **Nhánh triển khai**: `feat/evaluation-tools-acceptance`
- **Full Commit SHA**: `962d80774b643f03e38973640cf94649d1c3e93e`
- **Worktree**: `C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance`
- **Kế hoạch đã duyệt**: `docs/plans/evaluation-tools-acceptance.md` (commit `51f11e721ba9fe95a155f40da010136b068a5cfd`)
- **CI Required Run**: [Run 39958525531](https://github.com/NhiBuaa/knora-agent/actions/runs/39958525531)
- **Kết quả kiểm chứng offline**: 485 tests passed, 0 failures, ruff check/format clean, OpenAPI schema clean.

---

## 2. Kiểm kê Dữ liệu Pinned (12 Items)

### 2.1. Sáu (6) Real ANSWER Captures (Baseline B Continuation)
Được kiểm kê tại `docs/development/issue-158-pilot-audit-and-input-inventory.md`, khớp 100% SHA256 với archive manifest, bảo toàn full candidates content và context liên kết:

1. **`pdf-v3-004`**: Trace `2a0e4c698f1649989d44f6f7b1db92c3`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-004:2"`
2. **`pdf-v3-005`**: Trace `5b3e2b2fbba34e3489fe203a72dff124`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-005:2"`
3. **`pdf-v3-012`**: Trace `f8ebff5d75d34f26b52a95c9a9244c41`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-012:2"`
4. **`pdf-v3-014`**: Trace `43102c011e404be1b88e00e47087858c`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-014:2"`
5. **`pdf-v3-019`**: Trace `8bb40fa3d66649f8af6256c9a35e7df5`, attempt 2, `attempt_id="pdf-retrieval-v3-baseline-b-layout-v2-continuation:pdf-v3-019:2"`
6. **`pdf-v3-032`**: Trace `ad4928cf508543f886f3db537db1d3f5`, attempt 2 (follow-up của `004` trong cùng conversation context)

### 2.2. Hai (2) REFUSAL Controls (0 calls, deterministic)
1. **`pdf-v3-053`**: Trace `9557a27eb2a64c489c4fc07b539ba947` (expected REFUSAL -> actual REFUSAL)
2. **`pdf-v3-002`**: Trace `8c8bfa55a6d5423f85890b07b396e959` (expected ANSWER -> actual REFUSAL, false refusal control)

### 2.3. Bốn (4) Synthetic Controls (Deterministic offline variants, kỳ vọng trượt < 0.5)
1. **`ctrl-wrong-fact`**: Parent `004` | Phép biến đổi: "Cảnh báo P1 phải báo trực trong 150 phút." | Kỳ vọng trượt: `correctness < 0.5`
2. **`ctrl-off-topic`**: Parent `005` | Phép biến đổi: "Màu yêu thích của tôi là xanh dương. Tôi thích thời tiết đẹp." | Kỳ vọng trượt: `answer_relevancy < 0.5`
3. **`ctrl-unsupported`**: Parent `014` | Phép biến đổi: "Evidence means approval by the Tokyo office within 3 minutes..." | Kỳ vọng trượt: `faithfulness < 0.5`
4. **`ctrl-missing-exception`**: Parent `012` | Phép biến đổi: "Bản nháp thường giữ 30 ngày. Hồ sơ tranh chấp không có quy định riêng." | Kỳ vọng trượt: `correctness < 0.5`

### 2.4. Một (1) Ragas Proposal Batch
- 1 HTTP attempt, `@cf/openai/gpt-oss-20b`, tối đa 2 candidate drafts tiếng Việt, sinh từ source chunks đã pin thuộc #153.
- Kết quả đưa vào phụ lục độc lập, không tự động thăng hạng (promote) vào Gold.

---

## 3. Phân bổ Ngân sách & Hạn mức (Bounded Envelope V2)

| Slot | Mục tiêu | Số calls tối đa | Trạng thái nhánh Saved |
| :--- | :--- | :---: | :--- |
| `corpus_prepare` | Fallback chuẩn bị corpus (tối đa 6 PDF) | 6 | **SKIPPED** (0 calls, dùng saved branch) |
| `qa_gold_v1_answer` | Fallback sinh đáp án 6 câu | 12 | **SKIPPED** (0 calls, dùng saved branch) |
| `ragas_vi_draft` | Sinh draft tiếng Việt | 1 | **Sẵn sàng chạy** |
| `judge_real` | Chấm 6 captures thật (DeepEval GEval, Relevancy, Faithfulness) | 72 | **Sẵn sàng chạy** (tối đa 12 calls/item) |
| `judge_synthetic` | Chấm 4 synthetic controls | 48 | **Sẵn sàng chạy** (tối đa 12 calls/item) |
| `refusal_deterministic` | 2 refusal controls | 0 | **Deterministic** (0 calls) |
| **Tổng cộng dự kiến** | | **121 attempts** | Dưới trần cứng 139 attempts |

- **Mô hình**:
  - Generation / Ragas / Judge: `@cf/openai/gpt-oss-20b` (max input 8192 bytes, max output 2048 tokens).
  - Không fallback provider, redirects OFF, retries OFF, timeout 30s, concurrency=1.
- **Chi phí tiền mặt**: **USD 0 (Bắt buộc Cloudflare Workers Free)**.
- **Quy tắc chuyển nhượng quota**: 18 calls được tiết kiệm do skip `corpus_prepare` và `qa_gold_v1_answer` **tuyệt đối không được chuyển** sang tăng thêm số calls cho judge.

---

## 4. Giới hạn Thời gian, Cửa sổ & Trách nhiệm Tài nguyên

- **Số lần khởi động Stack Runtime**: **0** (Nhánh saved captures hoàn toàn không cần khởi động local Docker runtime stack!).
- **Cửa sổ thực thi**: Tối đa 2 windows × tối đa 60 phút mỗi window.
- **Hạn chót gói (Deadline)**: 7 ngày kể từ first dispatch anchor.
- **Cơ chế dừng (Emergency Stop)**: Ghi vào `.stops` journal sẽ lập tức hủy bỏ mọi quyền dispatch tiếp theo.

---

## 5. Langfuse Cloud Pilot Envelope (Bảo vệ Dữ liệu)

- **Vùng Cloud**: `https://jp.cloud.langfuse.com` (Hobby Free, owner-only).
- **Hạn mức nghiêm ngặt**:
  - Tối đa **2 POSTs**: 1 canary (1 trace + 1 observation) + 1 real (tối đa 2 traces + 2 observations).
  - Tối đa **2 DELETEs**: 1 xóa canary + 1 xóa real (chỉ xóa đúng exact owned IDs).
  - Tối đa **120 GETs** polling readback verification (concurrency=1, max 10 GET/phút).
  - **0 scores**: Tuyệt đối không gửi hay tạo scores trên cloud.
- **Quy trình tuần tự**:
  1. Canary preview & atomic receipt reservation.
  2. Canary POST -> Readback verify trace & observation -> DELETE canary -> Polling verify đã biến mất hoàn toàn.
  3. Real preview & atomic receipt reservation -> Real POST -> Readback verify -> DELETE real -> Polling verify đã biến mất hoàn toàn.
- **Trạng thái hiện tại**: **OFF**. Chỉ kích hoạt khi có lệnh explicit của Owner.

---

## 6. Phiếu Phê Duyệt Của Chủ Sở Hữu (Owner Decision)

Để tiếp tục bước Task 6 (Preflight & Live Dispatch) hoặc nghiệm thu, xin Owner xác nhận các mục sau:

- [ ] **1. Phê duyệt Gói Envelope V2** cho commit SHA `962d80774b643f03e38973640cf94649d1c3e93e` với trần tối đa 121 inference calls (USD 0).
- [ ] **2. Phê duyệt Nhánh Saved Captures**: Xác nhận skip `corpus_prepare` và `qa_gold_v1_answer`, sử dụng trực tiếp 6 clean captures từ baseline B continuation.
- [ ] **3. Xác nhận Gói Review Blind 12 Mục**: Đã nhận được packet tại `docs/development/issue-158-human-review-packet.md` để phục vụ human review độc lập sau khi có kết quả judge.
- [ ] **4. Chỉ định Chạy Pilot Langfuse**: Có cho phép chạy 2 POSTs / 2 DELETEs trên `jp.cloud.langfuse.com` hay giữ tắt hoàn toàn trong đợt này.
