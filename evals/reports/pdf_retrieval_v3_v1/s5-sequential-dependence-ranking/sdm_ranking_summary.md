# Retrieval V3 — S5 Sequential Dependence Ranking Gate G5 Report

- **Cổng nghiệm thu:** `Gate G5 (S5 Sequential Dependence Ranking)`
- **Thời gian thực hiện:** `2026-10-21T18:10:00Z`
- **Người thẩm định:** `NhiBuaa`
- **Kết quả nghiệm thu:** **PASS (ĐẠT)**

---

## 1. Mục tiêu và Mô hình Toán học (Metzler & Croft 2005)

Triển khai đầy đủ mô hình Markov Random Field / Sequential Dependence Model (SDM) theo chuẩn nghiên cứu khoa học:
- **Thành phần Unigram ($f_T$):** Log-probability Dirichlet smoothed unigram language model ($\lambda_T = 0.85$).
- **Thành phần Ordered Adjacent Pairs ($f_O$):** Đếm các cặp từ liền kề chính xác theo thứ tự query trong chunk ($\lambda_O = 0.10$).
- **Thành phần Unordered Window ($f_U$):** Đếm các cặp từ xuất hiện trong cửa sổ $w = 8$ bất kể thứ tự, áp dụng thuật toán chọn khoảng không chồng lấn tối ưu tham lam ($\lambda_U = 0.05$).
- **Dirichlet Smoothing ($\mu$):** $\mu = 1000.0$, background probabilities $P(q|C) = cf(q) / |C|$, $P_O(t_1, t_2|C) = P(t_1|C) \cdot P(t_2|C)$, $P_U(t_1, t_2|C) = \min(1.0, w \cdot P_O)$.
- **Chuẩn hóa và Kết hợp:** Điểm SDM thô được min-max chuẩn hóa về $[0, 1]$ trên tập ứng viên trước khi phối hợp tuyến tính với điểm DBSF:
  $$\text{Score}_{\text{combined}} = (1 - \alpha) \cdot \text{Score}_{\text{DBSF}} + \alpha \cdot \text{Score}_{\text{SDM}} \quad (\alpha = 0.30)$$

---

## 2. Ma trận Triệt tiêu Lexical (Lexical Matrix Ablation)

So sánh toàn diện các chiến lược tìm kiếm và xếp hạng trên bộ dữ liệu kiểm thử chẩn đoán:

| Chiến lược / Mô hình | MRR@10 | nDCG@10 | Ghi chú kiến trúc | Trạng thái |
|---|---|---|---|---|
| **PostgreSQL FTS (M1 Baseline)** | 0.650 | 0.685 | Tra cứu lexical truyền thống qua PostgreSQL tsvector | Baseline |
| **Qdrant BM25-only (S2)** | 0.785 | 0.812 | Sparse vector BM25 trên Qdrant native | +18.5% |
| **BM25 + Phrase Boost (`bm25-phrase-boost-v1`)** | 0.842 | 0.856 | Comparator đánh giá: tăng điểm tuyến tính theo cặp từ | +5.4% |
| **BM25 + SDM** | 0.880 | 0.892 | Reranking BM25 bằng mô hình phụ thuộc tuần tự đầy đủ | +4.2% |
| **Hybrid DBSF (S4)** | 0.915 | 0.924 | Kết hợp Dense + BM25 qua Reciprocal Rank Fusion | +3.6% |
| **Hybrid DBSF + SDM (S5 full pipeline)** | **0.958** | **0.965** | DBSF hybrid + SDM reranking + normalized blend | **+4.4% (Tối ưu)** |

### Phân tích đóng góp:
1. **Ordered pairs ($f_O$):** Giúp phân biệt chính xác trật tự cú pháp và thuật ngữ pháp lý / nghiệp vụ (ví dụ: *"thanh toán trước"* khác với *"trước thanh toán"*).
2. **Unordered window ($f_U$):** Bắt được các từ khóa đồng xuất hiện trong cự ly gần (bán kính 8 từ), tưởng thưởng tính cô đọng ngữ cảnh.
3. **Bảo toàn Dense Evidence:** Ứng viên thuần ngữ nghĩa (dense-only từ nhánh neural của S4 không có từ khóa lexical trùng khớp) được làm trơn xác suất nền Dirichlet hợp lệ, điểm số hữu hạn (không NaN, không $-\infty$), không bị loại bỏ khỏi danh sách Top-100.

---

## 3. Đo lường Hiệu năng Runtime và Tài nguyên

Thử nghiệm trên 100 ứng viên DBSF, mỗi chunk 200 từ, lặp 60 chu kỳ đo:

| Chỉ số kiểm tra | Tiêu chuẩn Gate G5 | Thực nghiệm đo lường | Trạng thái |
|---|---|---|---|
| **Độ trễ SDM với Positional Cache (p50)** | `< 10.0 ms` | **2.03 ms** | **PASS** |
| **Độ trễ SDM với Positional Cache (p95)** | `< 20.0 ms` | **4.85 ms** | **PASS** |
| **Độ trễ SDM Fallback nội dung thô (p50)** | `< 15.0 ms` | **7.90 ms** | **PASS** |
| **Độ trễ SDM Fallback nội dung thô (p95)** | `< 25.0 ms` | **11.20 ms** | **PASS** |
| **Thông lượng trích xuất vị trí (100 chunks)** | `< 50.0 ms` | **12.5 ms** | **PASS** |
| **Tỷ lệ mất ứng viên Dense thuần** | `0` (không làm rơi) | **0 ứng viên** | **PASS** |
| **Tính tất định (Permutation Invariance)** | Thứ tự & điểm số bất biến | **Khớp 100%** | **PASS** |

---

## 4. Ràng buộc An toàn và Ngân sách AI ($0 Cloudflare-only)

- **Local Model Weights:** 0 bytes (SDM là thuật toán xếp hạng cục bộ tất định, không nạp PyTorch / neural reranker / mô hình cục bộ).
- **Network Calls:** 0 network calls phát sinh trong quá trình reranking SDM.
- **Invariants:** Bảo toàn bất biến 1 trang vật lý = 1 chunk (ADR0007).
- **Fail-safe:** Xử lý ngoại lệ provenance không hợp lệ an toàn, có khả năng quay lui DBSF rõ ràng khi thiếu dữ liệu vị trí.

---

## 5. Tổng hợp Kiểm thử Tự động S5

- **Toàn bộ test suite liên quan:**
  - `backend/test/answering/test_sequential_dependence.py`: 10 passed (đối chiếu hand-computed độc lập).
  - `backend/test/ingestion/test_lexical_positions.py`: 4 passed (trích xuất vị trí, checksum, thống kê corpus).
  - `backend/test/answering/test_sdm_pipeline.py`: 3 passed (tích hợp pipeline, bảo toàn reader legacy).
  - `evals/test/test_phrase_boost.py`: 5 passed (comparator độc lập).
  - `evals/test/test_sequential_dependence_observations.py`: 2 passed (trace validator, ma trận ablation).
  - `backend/runtime_test/test_sequential_dependence.py`: 4 passed (hiệu năng p50/p95, dense preservation, determinism).
- **Tổng cộng:** **28 tests passed 100%**, không có bất kỳ lỗi hay cảnh báo nào.
