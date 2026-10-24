# Issue #158 Evaluation Tools Acceptance — Pilot Audit and Input Inventory

- **Task**: Task 1 (Plan `docs/plans/evaluation-tools-acceptance.md` commit `51f11e721ba9fe95a155f40da010136b068a5cfd`)
- **Authority**: Issue [#158](https://github.com/NhiBuaa/knora-agent/issues/158), kế thừa sau khi PR #202 (Issue #192) đã merge vào `main` tại `d04b8fa8fe9b193b3533bfde7b4495a34ea2727f`.
- **Branch**: `feat/evaluation-tools-acceptance`
- **Worktree**: `C:/Developer/Projects/knora-agent-worktree/feat-evaluation-tools-acceptance`
- **Budget consumed**: 0 live inference calls, 0 runtime startups, 0 cloud writes, paid USD 0.

---

## 1. Audit nhật ký pilot cũ (Read-only Journal Reconciliation)

Đã thực hiện kiểm tra đối chiếu chỉ đọc (sử dụng SQLite `mode=ro` và `PRAGMA query_only=ON`, tuyệt đối không thực thi các file script) tại thư mục lưu trữ pilot cũ: `<USER_HOME>/AppData/Local/Temp/evaluation-runtime-preparation-b00cf2f5c2/package/`.

### 1.1. Bảng đối chiếu 4 bản SQLite Journal

| File Journal | SHA256 Hash | Size (bytes) | Ghi nhận Package | Trạng thái Slots | Startup Reservation Timestamps |
|---|---|---|---|---|---|
| `admission.sqlite3` | `86a26953a2696e53c340a8d0723a9d877ad94d8ac552c2596b81f8ccbfb403f1` | 303,104 | attempts: 26, startups: 3, stopped: 0 | 7/7 slots COMPLETED (corpus: 2, qa_gold: 2, refusal: 1, ragas_vi: 1, qa_ragas: 2, judge_gold: 9, judge_ragas: 9) | 1. `2026-10-21T10:17:30.982991+00:00`<br>2. `2026-10-21T17:34:20.036660+00:00`<br>3. `2026-10-21T17:50:01.223545+00:00` |
| `admission.sqlite3.bak` | `74a947f451554215d35bf2acd63ccd130f52ffaf0350120822245d495974d61b` | 315,392 | attempts: 2, startups: 3, stopped: 1 | corpus: 2 (COMPLETED), qa_gold: 0 (BOUND), còn lại 5 slots WAITING | 1. `2026-10-21T10:17:30.982991+00:00`<br>2. `2026-10-21T10:42:41.663319+00:00`<br>3. `2026-10-21T14:01:47.545850+00:00` |
| `admission.sqlite3.pre_w2_20261021_170226.bak` | `867e2037a3a047e8b19870a6fe9f16d5e1f36bd4b9d7aa37a28bb358b197ceb5` | 319,488 | attempts: 6, startups: 3, stopped: 1 | corpus: 2, qa_gold: 2, refusal: 1, ragas_vi: 1 (COMPLETED), còn lại 3 slots WAITING | 1. `2026-10-21T10:17:30.982991+00:00`<br>2. `2026-10-21T10:42:41.663319+00:00`<br>3. `2026-10-21T16:35:11.129769+00:00` |
| `admission.sqlite3.pre_w2_20261021_170510.bak` | `389689ba4cff9a4f7e70468ceeed5430bedb6be48bf9d0fcb21e51edb1e08d60` | 319,488 | attempts: 6, startups: 1, stopped: 0 | corpus: 2, qa_gold: 2, refusal: 1, ragas_vi: 1 (COMPLETED), còn lại 3 slots WAITING | 1. `2026-10-21T10:17:30.982991+00:00` |

### 1.2. Nhận định và kết luận về Pilot cũ (Decision Q4)
1. **Union Startup Reservations**: Hợp nhất các bản journal cho thấy có ít nhất **6 mốc thời gian đăng ký (reservation timestamps)** riêng biệt dù mỗi bản ghi chỉ giới hạn trần `startups=3`. Điều này xác nhận rằng giữa các cửa sổ chạy đã có can thiệp reset trạng thái journal (thông qua các script tồn tại trên đĩa như `reset_and_clean.py`, `reset_journal_for_ragas.py`, `reset_w2_state.py`, `reset_for_w3.py`).
2. **Quy định đối với nghiệm thu mới**: Đúng theo Quyết định Q4 của Owner, kết quả của pilot cũ (kể cả con số 26/3 attempts hay điểm giám khảo 1.0) **chỉ có giá trị chuẩn đoán (diagnostic-only)**, tuyệt đối không được dùng làm bằng chứng tuân thủ hay cơ sở nghiệm thu chất lượng chính thức cho #158.
3. **Bảo toàn dữ liệu lịch sử**: Giữ nguyên toàn bộ file gốc trên đĩa và giữ nguyên kết quả run `faacf17180f24a2bb5ab6c9e36917c6a` (`COMPLETED / SEMANTIC_PENDING`, expected ANSWER nhưng thực tế nhận REFUSAL), không chỉnh sửa hồi tố.

---

## 2. Kiểm kê tập dữ liệu đại diện đã chốt (Target Cases Inventory)

Kiểm kê độc lập 6 ca câu trả lời và 2 ca từ chối (controls) trích xuất từ baseline canonical tại `evals/reports/pdf_retrieval_v3_v1/baseline-b-layout-v2-continuation/captures/`.

| Mã ca (Case ID) | Quyết định (Decision) | Kỳ vọng (Expected) | Attempt | Attempt ID | Trace ID | Kích thước & SHA-256 | Khớp Archive Manifest | Câu trả lời tóm lược | Trích dẫn (Citations) | Candidates (Đủ Content) | Original PDF Anchor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `pdf-v3-004` | ANSWER | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-004:1` | `5df05b2e-f785-4c07-bc02-5db87535112d` | 4,925 bytes<br>`43f01b83c76273b2aaa310d11dbfe209e9a9e110ecf4aa0dd52c009cab75635f` | **ĐẠT** | Cảnh báo P1 phải báo trực trong 15 phút. `[[E1]]` | `['E1']` | 1 (True) | Source: `hierarchy-03`<br>Page: 1 |
| `pdf-v3-005` | ANSWER | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-005:1` | `d2676672-1eb9-4daf-a56d-de9016a86019` | 5,437 bytes<br>`9c10208b97128ed5c7fcef6aa229e8c9840dd09595162b616553523c943be6cc` | **ĐẠT** | Hạn mức đầu kỳ được cấp **14 lượt**. `[[E1]]` | `['E1']` | 1 (True) | Source: `columns-01`<br>Page: 1 |
| `pdf-v3-012` | ANSWER | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-012:1` | `dd080f90-d359-4133-9224-58994aaec0fc` | 5,161 bytes<br>`8c2b33f6128a8d2e07dec1bda2f76b68a0f3d997da39c2c38c28fafcb5a260c4` | **ĐẠT** | Bản nháp thường được giữ 30 ngày; hồ sơ tranh chấp giữ 5 năm. `[[E1]]` | `['E1']` | 1 (True) | Source: `hierarchy-02`<br>Page: 1 |
| `pdf-v3-014` | ANSWER | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-014:1` | `9caa9ab8-ab7a-42d9-b64e-f20ebb1d4411` | 5,376 bytes<br>`fe006940820178c389c83dfec348acd5a2abdc9a352df7da606707bbf6503d7d` | **ĐẠT** | Trong từ điển song ngữ, evidence là nguồn cung cấp dữ liệu. `[[E1]]` | `['E1']` | 1 (True) | Source: `columns-02`<br>Page: 1 |
| `pdf-v3-032` | ANSWER | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-032:1` | `bbbee126-66dc-4c98-a19c-f1eff95ea06d` | 5,099 bytes<br>`ef504d1fd15a67ece1acd6286afe00294db659089d46c111a0425091a9e1d3de` | **ĐẠT** | Không, ngoài giờ không được đổi cảnh báo P1 thành P2. `[[E1]]` | `['E1']` | 1 (True) | Source: `hierarchy-03`<br>Page: 1<br>(Follow-up của 004, cùng Conv ID) |
| `pdf-v3-045` | ANSWER | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-045:1` | `d8e8bf10-9d8d-4d72-8f8b-7afd8c9a20b1` | 13,440 bytes<br>`93f41cda5f763d929c0a2cdbc29db499f8efa114d644c8910a7bf3822dd38f05` | **ĐẠT** | Theo tóm tắt, PhoNLP được phát hành dưới giấy phép Apache License 2.0. `[[E3]]` | `['E3']` | 3 (True) | Source: `academic-phonlp`<br>Page: 1 |
| `pdf-v3-053` | REFUSAL | REFUSAL | 1 | `s1-runtime-binding-20261015-01:pdf-v3-053:1` | `f483e759-cf3a-465b-bd4a-43e2b9ce4018` | 3,993 bytes<br>`8a3e5a0fd756382ce80b4d870e544e72f2cb3c7fb79f81cb4566df0e6950a268` | **ĐẠT** | *(Không có câu trả lời - Đúng chuẩn Refusal)* | `[]` | 1 (True) | Control: True Refusal |
| `pdf-v3-002` | REFUSAL | ANSWER | 1 | `s1-runtime-binding-20261015-01:pdf-v3-002:1` | `9375291d-cbd0-4150-8eab-c1a8108f85c2` | 2,426 bytes<br>`9e0ba2364ff9ef5a27f7c39441cec3626cea93eec387d041d5620723cb20269a` | **ĐẠT** | *(Không có câu trả lời - False Refusal)* | `[]` | 0 (N/A) | Control: False Refusal |

---

## 3. Đánh giá tính khả thi giữa Saved Branch và Fallback Live Branch

1. **Saved Branch khả thi 100%**:
   - Tất cả 8 file capture lưu trữ đều có SHA-256 khớp tuyệt đối với `archive-manifest.json`.
   - Mỗi file đều giữ trọn vẹn `candidates` kèm văn bản `content` nguyên gốc, giúp dựng đầy đủ danh sách bằng chứng `generation_evidence = [["E1", content], ...]`.
   - Mối liên hệ ngữ cảnh hội thoại giữa `pdf-v3-004` và follow-up `pdf-v3-032` (cùng `conversation_id = fd1b6ef7-34e9-4087-8699-8e8d4999ecc1`) được bảo toàn trọn vẹn.
   - Do đó, hoàn toàn có thể triển khai adapter derive capture offline theo nhánh **Saved Branch**, tiết kiệm 100% chi phí Q&A live calls.
2. **Fallback Live Branch**: Chỉ kích hoạt khi và chỉ khi Owner phê duyệt một gói phong bì live (exact-SHA/envelope) mới tại Task 6.

---

## 4. Audit Đợt 2 (V2 Acceptance Journals & Artifacts Audit)

Thực hiện kiểm tra đối chiếu chỉ đọc (SQLite `mode=ro` và `PRAGMA query_only=ON`) toàn bộ 5 bản nhật ký và tập tin liên quan tại thư mục lưu trữ `reports/issue-158-acceptance/`.

### 4.1. Bảng đối chiếu 5 bản SQLite Journal V2 và Artifacts

| Tên tập tin | Kích thước (bytes) | SHA-256 Checksum | Ghi nhận Package | Ghi nhận Requests / Invariant | Ghi nhận `.stops` |
|---|---|---|---|---|---|
| `package_1792762959.sqlite` | 49,152 | `7c220bb8a484acc392bb22cb0a85941dec77847007888f741e9ca08e2b8a4dfe` | attempts: 1, startups: 0, stopped: 0 | 0 requests (`COUNT(requests) != package.attempts`) | `stop_requests: []` (`95827829...`) |
| `package_1792763126.sqlite` | 94,208 | `f9fdd0f3ee1581dc355aada4519827a3f1e47dabd55bec1eb10265c24d23a655` | attempts: 52, startups: 0, stopped: 1 | 52 requests, 52 noncached (`body_digest = sha256({})`) | `stop_requests: ['issue-158-...']` (`ae2fbb25...`) |
| `package_1792763574.sqlite` | 126,976 | `11ddd88f4e06a43f1347fa48a1b5983e4ffb81d21318536779666923af0b1bda` | attempts: 87, startups: 0, stopped: 1 | 87 requests (52 cached + 35 noncached `{}`) | `stop_requests: ['issue-158-...']` (`ae2fbb25...`) |
| `package_1792763879.sqlite` | 126,976 | `430d91a93ab6282a3e639f86186de7b443c7b23c75eab3aa0a974a2cc5b006ab` | attempts: 86, startups: 0, stopped: 1 | 86 requests (52 cached + 34 noncached `{}`) | `stop_requests: ['issue-158-...']` (`ae2fbb25...`) |
| `package_1792764691.sqlite` | 135,168 | `651fb8f923a5daf412a657dc4e412dfa06748abbf41cd445c38ae60efc2df278` | attempts: 85, startups: 0, stopped: 0 | 85 requests (52 cached + 33 noncached `{}`) | `stop_requests: []` (`95827829...`) |
| `acceptance-run-summary.json` | 22,967 | `da31c7df4c525991740580dc734468498a229a92070c3b5fad63a875871ae114` | - | Chứa báo cáo tổng hợp của đợt chạy V2 cũ | - |

### 4.2. Phát hiện Kiểm toán và Đính chính Sự thật (Audit Findings & Reality Correction)

1. **Phân tích 154 Noncached Reservations**:
   - Tổng cộng qua 4 journal có request (`...3126`, `...3574`, `...3879`, `...4691`) ghi nhận 154 lượt reservation không phải cache (52 + 35 + 34 + 33 = 154).
   - **Tất cả 154 bản ghi** này đều chèn `body_digest = 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` (SHA-256 của chuỗi rỗng `{}`), và không có dữ liệu wire response bodies thực tế được lưu lại trong bảng requests.
   - Nguyên nhân: `PackageSlotLedger.reserve()` trong `scripts/run_acceptance_live.py` đã tự ý cập nhật các bộ đếm trong SQLite và ghi nhận trạng thái `COMPLETED` trước khi gửi HTTP mà không truyền payload thực qua `LiveAdmission.sync_client`.
2. **Số lượng HTTP Attempts thực tế và Chi phí**:
   - Do thiếu bằng chứng wire response xác thực và các lần chạy trước bị timeout/dừng (stopped=1) dẫn đến khởi tạo journal mới rồi sao chép kết quả cũ dưới dạng `{"cached": true}`, số lượng HTTP attempts thực tế gửi ra ngoài và chi phí thực tế là **CHƯA ĐƯỢC CHỨNG MINH (UNKNOWN)**.
   - Các tuyên bố trước đây về "85 attempts", "USD 0", và "100% PASS" chỉ là kết quả thử nghiệm chưa hoàn thiện của V2, không được dùng làm bằng chứng tuân thủ hay cơ sở nghiệm thu cho #158.
3. **Lộ điểm Giám khảo & Tính chất Đợt Review mới**:
   - Điểm số và lý do giám khảo cũ đã bị bộc lộ trong quá trình điều tra mã nguồn và kiểm toán nhật ký. Do đó, đợt human review sắp tới sẽ ghi nhận rõ ràng điều này; Owner sẽ đánh giá và gán nhãn độc lập trước khi kích hoạt bất kỳ lượt judge mới nào, không coi đây là một nghiên cứu mù tuyệt đối (blind study).
