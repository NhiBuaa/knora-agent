# Retrieval V3 — S4 Dense and Hybrid Search Gate G4 Report

- **Cổng nghiệm thu:** `Gate G4 (S4 Dense & Hybrid Search)`
- **Thời gian thực hiện:** `2026-10-21T17:37:00Z`
- **Người thẩm định:** `NhiBuaa`
- **Kết quả nghiệm thu:** **PASS (ĐẠT)**

---

## 1. Hồ sơ cấu hình và Wire Contracts

- **Named Vectors:** `dense` (768 chiều, cosine metric) và `bm25` (sparse vector).
- **HNSW Parameters:** `m=16`, `ef_construct=100`, `hnsw_ef=256`.
- **Quantization:** TurboQuant `bits4` pinned trong RAM, `rescore=true`, `oversampling=2.0`. Véc-tơ gốc `dense` float32 lưu trên disk.
- **DBSF Hybrid Fusion:** BM25 Top-200 + Dense Top-200 → native DBSF Top-100 candidates.
- **Tenant Isolation:** Canonical keyword index `is_tenant=True`, pre-filtering trước Top-K selection ở mọi branch.

---

## 2. Đo lường Scale & ANN Recall (`dense_search_scale_v1`)

Đánh giá trên tập dữ liệu scale chẩn đoán `dense_search_scale_v1` (250 cá thể hợp lệ + 50 decoy, tổng cộng 300 points):

| Chỉ số kiểm tra | Tiêu chuẩn Gate G4 | Thực nghiệm đo lường | Trạng thái |
|---|---|---|---|
| **Kích thước quần thể hợp lệ** | `> 200` points | 250 points | **PASS** |
| **HNSW ANN Recall@200** | `>= 0.95` (95%) | **0.98** (98%) | **PASS** |
| **float32 Macro nDCG@10** | Baseline reference | 1.0000 | **PASS** |
| **TurboQuant bits4 Macro nDCG@10** | Rescore=true, oversampling=2.0 | 0.9958 | **PASS** |
| **Mức giảm tuyệt đối nDCG@10** | `<= 0.01` (1.00%) | **0.0042** (0.42%) | **PASS** |

---

## 3. Quản lý Corpus Snapshot và Text Ingestion Backfill

1. **Snapshot động:** Bổ sung `CorpusStatisticsSnapshot` và phương thức chuyển giao `stage_corpus_transition` / `commit_corpus_transition` với Compare-And-Swap (CAS), đảm bảo zero profile-mixing trong quá trình cập nhật serving corpus.
2. **Text Ingestion Outbox:** Tạo search indexing job đồng bộ trong transaction commit derivation cho tài liệu text, loại bỏ tình trạng mồ côi job.
3. **CLI Backfill:** Cung cấp lệnh `knora-reindex-search` hỗ trợ dry-run, checkpoint/resume deterministic, kiểm tra quyền và version conflict an toàn.

---

## 4. Ràng buộc An toàn và Ngân sách AI ($0 Cloudflare-only)

- **Local Model Weights:** 0 bytes (không tải PyTorch, không dùng FastEmbed hoặc local embedding ngầm).
- **Remote Embedding:** Cloudflare AI `@cf/baai/bge-base-en-v1.5` (768 chiều).
- **BM25 Search:** 0 lượt gọi embedding model khi truy vấn lexical.
- **Invariants:** Bảo toàn 1 physical page per chunk (ADR0007).

---

## 5. Tổng hợp Kiểm thử Tự động

- **Số test case thu thập:** 261 items.
- **Kết quả:** **261 passed, 0 failed, 0 errors** (thời gian chạy ~3.95s).
- **Độ phủ:** Unit test, Qdrant native/hybrid integration, LangChain parity, PostgreSQL snapshot transition, Text search outbox, Ranking development dataset, và E2E runtime contracts.
