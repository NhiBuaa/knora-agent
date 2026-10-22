# Retrieval V3 Production Release Runbook

- **Mục đích:** Hướng dẫn vận hành chuẩn (SOP), quy trình chuyển giao (cutover), quan sát chất lượng (observation), và khôi phục sự cố (rollback) cho Knora Retrieval V3.
- **Phạm vi áp dụng:** Môi trường phát triển nội bộ, dàn kiểm thử tự động CI/CD và triển khai thực tế.
- **Tài liệu tham chiếu:** Issue #153, ADR0007, ADR0018, [Gate G8 Report](file:///evals/reports/pdf_retrieval_v3_v1/s8-integrated-release/gate_g8_integrated_release_report.md).

---

## 1. Các Ràng buộc Bất biến Cốt lõi (Core Invariants)

1. **Ngân sách AI Cục bộ $0 (Cloudflare-only AI):**
   - Tuyệt đối không cài đặt hoặc nạp các thư viện mô hình nặng (`torch`, `fastembed`, `onnxruntime`, `sentence_transformers`) vào máy chủ ứng dụng hoặc máy trạm.
   - Mọi tác vụ AI (dense embedding, cross-encoder reranking, selective OCR, structured query planning) được ủy quyền xử lý hoàn toàn qua Cloudflare Workers AI.
2. **Bảo tồn ranh giới 1 trang vật lý = 1 chunk (ADR0007):**
   - Đảm bảo trích dẫn nguồn PDF chính xác theo số trang thực tế. Bảng biểu và danh sách được giữ nguyên vẹn qua trích xuất Docling.
3. **Bảo toàn định danh kỹ thuật (Protected Spans):**
   - Các mã định danh (`AUTH_403`, `ISO_27001`), chỉ số phân đoạn (`Chương 2`, `mục 3.1`), ngày tháng và từ phủ định không bao giờ bị viết lại hoặc đánh mất trong bước Query Planning.
4. **Hệ thống Dự phòng Đa tầng (Multi-tier Fallback Hierarchy):**
   - Cross-Encoder Reranker lỗi/timeout $\to$ DBSF + SDM cục bộ $\to$ BM25 cục bộ (`retrieval-bm25-top8-v1`).
   - Lưu ý: Phrase Boost chỉ sử dụng trong đánh giá và đo đạc thử nghiệm (evaluation comparator), không dùng làm fallback trong production.
   - Không để lỗi mạng của nhà cung cấp AI đám mây làm gián đoạn toàn bộ dịch vụ hỏi đáp.

---

## 2. Quy trình Triển khai và Chuyển giao (Deployment & Cutover Sequence)

### Bước 1: Kiểm tra Điều kiện Tiên quyết (Pre-flight Checks)
Xác nhận cấu hình môi trường và tính khả dụng của các dịch vụ:
```powershell
# 1. Kiểm tra biến môi trường Cloudflare Workers AI
if (-not $env:CLOUDFLARE_ACCOUNT_ID -or -not $env:CLOUDFLARE_API_TOKEN) {
    throw "Thiếu thông tin xác thực Cloudflare Workers AI"
}

# 2. Kiểm tra tiến trình reindex ở chế độ dry-run
python -m knora.adapters.cli.reindex_search --workspace-id <TARGET_WORKSPACE_ID> --dry-run

# 3. Kiểm tra tính toàn vẹn của OpenAPI artifacts và format code
python scripts/export_openapi.py --check
python -m ruff check .
```

### Bước 2: Tái lập Chỉ mục và Chuyển đổi Dữ liệu (Re-indexing / Backfill)
Chạy lệnh đánh chỉ mục cho toàn bộ các tài liệu hiện có trong workspace:
```powershell
# Đánh chỉ mục đồng thời cả dense vector và lexical BM25/SDM theo checkpoint và batch
python -m knora.adapters.cli.reindex_search --workspace-id <TARGET_WORKSPACE_ID> --batch-size 100 --checkpoint-file checkpoint.json
```

### Bước 3: Kiểm chứng Môi trường Thực thi (Runtime Verification)
Chạy profile kiểm thử `retrieval-v3` để đảm bảo chuỗi xử lý hoạt động trọn vẹn:
```powershell
$rcSha = (git rev-parse HEAD).Trim()
./scripts/run-runtime-verification.ps1 `
    -SubjectSha $rcSha `
    -WorkflowSha $rcSha `
    -Profile retrieval-v3 `
    -RunId "release-check-$([guid]::NewGuid().ToString('N'))" `
    -RunAttempt 1

# Xác minh tính toàn vẹn của hồ sơ chứng cứ
python scripts/runtime_evidence.py validate $rcSha .verification/runtime/retrieval-v3/evidence.json --profile retrieval-v3
```

### Bước 4: Kích hoạt Chế độ Hoạt động (Traffic Cutover)
Cập nhật cấu hình retrieval mặc định sang `retrieval-hybrid-rerank-top8-v3`:
```json
{
  "retrieval_configuration_id": "retrieval-hybrid-rerank-top8-v3",
  "candidate_k": 200,
  "max_evidence_chunks": 5,
  "max_evidence_tokens": 3000,
  "reranker_model": "@cf/baai/bge-reranker-base",
  "embedding_model": "@cf/baai/bge-m3"
}
```

---

## 3. Quy trình Khôi phục Khẩn cấp (Emergency Rollback Procedure)

Khi phát hiện sự cố nghiêm trọng (ví dụ: Cloudflare Workers AI tê liệt trên diện rộng, độ trễ p95 vượt quá 1000ms kéo dài, hoặc tỷ lệ lỗi hệ thống tăng cao):

1. **Hạ cấp tức thì về chế độ tìm kiếm từ khóa cục bộ (Local Lexical Fallback):**
   Chuyển đổi cấu hình `retrieval_configuration_id` sang `retrieval-bm25-top8-v1`. Hệ thống sẽ lập tức chuyển sang tìm kiếm từ khóa BM25 cục bộ mà không cần gọi API đám mây:
   ```json
   {
     "retrieval_configuration_id": "retrieval-bm25-top8-v1"
   }
   ```
2. **Khôi phục trạng thái bộ nhớ:**
   Tất cả các bản ghi chỉ mục nguồn trong PostgreSQL và Qdrant được bảo toàn nguyên vẹn, không cần xóa cơ sở dữ liệu khi rollback.

---

## 4. Giám sát Chỉ số và Vận hành (Metrics & Telemetry)

Các chỉ số then chốt cần theo dõi qua Prometheus/Grafana hoặc trace log:
- **`retrieval_planning_duration_ms`:** Thời gian phân tích kế hoạch truy vấn (mục tiêu p50 < 10ms).
- **`retrieval_rerank_duration_ms`:** Thời gian xếp hạng lại qua Cloudflare AI (mục tiêu p50 < 50ms).
- **`retrieval_source_recovery_count`:** Số lượt gọi phục hồi nguồn có mục tiêu (tối đa 1 lượt / request).
- **`retrieval_fallback_events_total`:** Số lần kích hoạt cơ chế dự phòng an toàn (phải bằng 0 trong điều kiện bình thường).
- **`retrieval_evidence_token_count`:** Tổng số token bằng chứng được cấp cho LLM sinh câu trả lời (phải $\le 3000$ tokens).

---

## 5. Chẩn đoán Sự cố Thường gặp (Troubleshooting)

| Triệu chứng | Nguyên nhân khả dĩ | Biện pháp xử lý |
|---|---|---|
| Lỗi `Cloudflare Workers AI timeout / 504 Gateway Timeout` | Mạng chập chờn hoặc API Cloudflare bị quá tải | Hệ thống tự động fallback về DBSF+SDM; kiểm tra trạng thái Cloudflare Status |
| Bằng chứng trích dẫn thiếu một phần câu hỏi so sánh | Truy vấn phức hợp bị bỏ sót nhánh thông tin | Kiểm tra `Subquestion` trong trace log và xác nhận cơ chế 1-pass recovery đã kích hoạt |
| Token bằng chứng vượt quá ngân sách | Tài liệu có các trang chứa văn bản quá dài | Cơ chế MMR tự động cắt tỉa tại trần 3000 tokens và gán cờ `TOKEN_BUDGET_EXCEEDED` |
| `runtime evidence provenance is incomplete` | Thiếu một trong các trường metadata bắt buộc | Chạy lại kiểm thử runtime qua `run-runtime-verification.ps1` có truyền đủ SHA và profile |
