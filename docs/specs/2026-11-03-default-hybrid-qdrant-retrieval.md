# Đặc tả kỹ thuật: Mặc định hóa Tìm kiếm Kết hợp (Hybrid Search) với Qdrant và Reranker (Retrieval V3)

- **Ngày lập:** 03/11/2026
- **Tác giả:** Antigravity (Cặp lập trình cùng Người vận hành)
- **Trạng thái:** Đã hoàn thành triển khai và kiểm chứng (PR #244)
- **Kho mã & Bản làm việc (Worktree) đích:** `C:\Developer\Projects\knora-agent-worktree\refactor-compose-consolidation`
- **Nhánh:** `refactor/compose-consolidation`
- **Công việc liên quan:** #153 (Nâng cấp Retrieval V3), #237 / PR #244 (Gom gọn Docker Compose)

---

## 1. Bối cảnh và Mục tiêu

### 1.1 Bối cảnh
Nhiệm vụ #153 (PR #221) đã hoàn thành toàn bộ chuỗi tính năng Retrieval V3:
- Tìm kiếm vector dày đặc (Dense Vector Search) và tìm kiếm từ khóa theo vị trí BM25 / SDM (Sequential Dependence Model) thông qua bộ điều hợp `NativeQdrantSearchIndex`.
- Thuật toán hợp nhất phân phối điểm DBSF (Distribution-Based Score Fusion) để kết hợp các ứng viên tìm kiếm.
- Bộ xếp hạng lại ngữ cảnh chuyên sâu Cross-Encoder (`@cf/baai/bge-reranker-base`) qua Cloudflare Workers AI.
- Cơ chế tự động xử lý chỉ mục khi nạp tài liệu trong `main.py` (`DerivationJobHandler`, `DynamicSearchIndexHandler`).

Tuy nhiên, hệ thống hiện tại vẫn ghim `retrieval-m1-v1` (chỉ dùng PostgreSQL pgvector / full-text search) làm cấu hình mặc định trong `settings.py`, `.env.example` và bộ khởi chạy `scripts/start-dev.ps1`. Qdrant hiện chỉ nằm cô lập trong `docker-compose.dev.yml` dưới các profile năng lực `retrieval-test` / `retrieval-http-test` phục vụ cho việc kiểm thử tự động.

### 1.2 Mục tiêu
Chính thức đưa **Tìm kiếm Kết hợp với Qdrant và Xếp hạng lại (`retrieval-hybrid-rerank-top8-v3`)** trở thành chiến lược tìm kiếm mặc định của Knora trên toàn hệ thống:
1. Giá trị mặc định của cấu hình hệ thống (`settings.py`, `.env.example`).
2. Cấu trúc Docker Compose (`docker-compose.dev.yml` và `docker-compose.yml`), tuân thủ nghiêm ngặt quy tắc duy trì tối đa 2 nguồn Compose vận hành.
3. Bộ khởi chạy phát triển hàng ngày (`scripts/start-dev.ps1`), tích hợp kiểm tra quyền sở hữu volume lưu trữ và kiểm tra sức khỏe tự động.
4. Hướng dẫn đánh lại chỉ mục (re-indexing / backfill) cho các tài liệu cũ đã có sẵn trong cơ sở dữ liệu.

---

## 2. Các Ràng buộc Bất biến và Ranh giới Kiến trúc

1. **Ràng buộc duy trì tối đa hai nguồn Docker Compose:**
   - Dự án chỉ duy trì tối đa hai nguồn Compose: `docker-compose.yml` (stack môi trường sản xuất) và `docker-compose.dev.yml` (môi trường phát triển, profile kiểm thử và dàn thử nghiệm cô lập).
   - Tuyệt đối không sinh file Compose thứ ba, không đổi tên hoặc dùng lệnh `include`/`extends` trỏ ra ngoài để lách luật.
2. **Ràng buộc cô lập dữ liệu (Storage Isolation):**
   - Dữ liệu phát triển hàng ngày (`knora-dev_knora_qdrant_data`) không bao giờ được dùng chung hoặc tái sử dụng cho các bài kiểm thử tự động.
   - Dịch vụ `verification-qdrant` (profile `retrieval-test`, `retrieval-http-test`, cổng `16433:6333`, volume `verification-qdrantdata`) tiếp tục được giữ nguyên độc lập cho các bộ kiểm thử S2/S8.
3. **Thứ bậc dự phòng đa tầng (Multi-tier Fallback Hierarchy):**
   - Lỗi kết nối hoặc hết thời gian chờ (timeout) bộ Reranker $\to$ tự động lùi về xếp hạng kết hợp DBSF + SDM nội bộ mà không làm chết ứng dụng.
   - Cụm Qdrant ngừng hoạt động hoặc mất kết nối $\to$ báo lỗi dứt khoát `LEXICAL_RETRIEVAL_UNAVAILABLE` (nguyên tắc Fail-Fast) để người vận hành khắc phục, không âm thầm trả về kết quả rỗng.
4. **Ngân sách AI cục bộ \$0 (Cloudflare-only AI):**
   - Tuyệt đối không cài đặt các thư viện mô hình nặng (`torch`, `fastembed`, `onnxruntime`) lên máy chủ ứng dụng hoặc máy trạm phát triển; toàn bộ tác vụ embedding và rerank ủy quyền cho Cloudflare Workers AI.

---

## 3. Đặc tả Kỹ thuật Chi tiết cho từng Thành phần

### 3.1 Cấu trúc Docker Compose

#### A. Môi trường phát triển: `docker-compose.dev.yml`
- Bổ sung dịch vụ `qdrant` vào nhóm dịch vụ cốt lõi mặc định (không gán profile):
  ```yaml
  qdrant:
    image: qdrant/qdrant:v1.19.2@sha256:b7b0444c4c351c970b98e90a6f89c2ee4287c65b44e52b4cb503fa5b2aa927ad
    environment:
      QDRANT__TELEMETRY_DISABLED: "true"
    ports:
      - 127.0.0.1:${KNORA_EVAL_QDRANT_HOST_PORT:-6333}:6333
    healthcheck:
      test:
        - CMD-SHELL
        - exec 3<>/dev/tcp/127.0.0.1/6333 && echo -e 'GET /healthz HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n' >&3 && grep -q '200 OK' <&3
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - knora_qdrant_data:/qdrant/storage
  ```
- Khai báo volume lưu trữ cấp cao:
  ```yaml
  volumes:
    knora_postgres_data:
    knora_minio_data:
    knora_qdrant_data:
  ```
- Dịch vụ `verification-qdrant` hiện có trong `retrieval-test` / `retrieval-http-test` giữ nguyên vẹn.

#### B. Môi trường sản xuất độc lập: `docker-compose.yml`
- Bổ sung dịch vụ `qdrant` đồng bộ tương tự vào nhóm dịch vụ sản xuất.
- Bổ sung điều kiện phụ thuộc cho dịch vụ `api`:
  ```yaml
  depends_on:
    postgres:
      condition: service_healthy
    minio:
      condition: service_healthy
    minio-init:
      condition: service_completed_successfully
    qdrant:
      condition: service_healthy
  ```
- Khai báo volume cấp cao: `knora_qdrant_data:`.

---

### 3.2 Cấu hình hệ thống: `settings.py` và `.env.example`

Trong `backend/src/knora/infrastructure/settings.py`:
```python
retrieval_configuration_id: str = "retrieval-hybrid-rerank-top8-v3"
lexical_qdrant_url: str | None = "http://127.0.0.1:6333"
lexical_qdrant_collection: str | None = "knora"
```

Trong `.env.example`:
```dotenv
# Cấu hình tìm kiếm mặc định sang Retrieval V3 Hybrid kết hợp Qdrant và Cloudflare BGE Reranker
KNORA_RETRIEVAL_CONFIGURATION_ID=retrieval-hybrid-rerank-top8-v3
KNORA_LEXICAL_QDRANT_URL=http://127.0.0.1:6333
KNORA_LEXICAL_QDRANT_COLLECTION=knora
```

---

### 3.3 Bộ khởi chạy phát triển: `scripts/start-dev.ps1`

1. **Tham số khởi chạy:**
   - Bổ sung tham số `[int]$QdrantPort = 6333` để hỗ trợ tùy chỉnh cổng khi cần.
2. **Tập hợp dịch vụ lưu trữ:**
   - Đưa `qdrant` vào danh sách `$storageServices`:
     ```powershell
     $storageServices = @('postgres', 'minio', 'qdrant')
     if ($useBundledKeycloak) { $storageServices += 'keycloak-dev' }
     ```
3. **Kiểm tra quyền sở hữu lưu trữ (`Test-DevStorageOwnership`):**
   - Đăng ký cấu hình kiểm tra volume Qdrant vào `$expectedVolumeConfig`:
     ```powershell
     "${composeProject}_knora_qdrant_data" = @{
         Service = 'qdrant'
         Destination = '/qdrant/storage'
         Role = 'knora_qdrant_data'
     }
     ```
4. **Lan truyền biến môi trường:**
   - Tự động gán biến môi trường cho các tiến trình con:
     - `$env:KNORA_LEXICAL_QDRANT_URL = "http://127.0.0.1:$QdrantPort"`
     - `$env:KNORA_LEXICAL_QDRANT_COLLECTION = "knora"`
     - `$env:KNORA_RETRIEVAL_CONFIGURATION_ID = "retrieval-hybrid-rerank-top8-v3"`
5. **Tiền kiểm tra (`-PreflightOnly`):**
   - Báo cáo xác nhận `QDRANT_URL=http://127.0.0.1:$QdrantPort` và kiểm tra cổng 6333 không bị chiếm bởi tiến trình lạ.

---

## 4. Kế hoạch Kiểm chứng và Tiêu chí Nghiệm thu

1. **Kiểm tra cú pháp và cấu trúc tĩnh:**
   - `docker compose -f docker-compose.yml config --quiet` $\to$ mã thoát 0.
   - `docker compose -f docker-compose.dev.yml config --quiet` $\to$ mã thoát 0.
   - `pytest backend/test/config/test_compose_inventory.py` $\to$ 34/34 tests đạt (không vi phạm giới hạn 2 file Compose).
2. **Kiểm tra đơn vị và hợp đồng (Unit & Contract Tests):**
   - `pytest backend/test/adapters/cli/test_dev_launcher.py` $\to$ kiểm tra quyền sở hữu volume và mock khởi chạy đạt.
   - `pytest backend/test/test_bootstrap.py` $\to$ đạt.
   - `pytest backend/test/answering/test_dense_hybrid_contract.py` $\to$ đạt.
3. **Nghiệm thu môi trường thực tế (Runtime Acceptance):**
   - Chạy `.\scripts\start-dev.ps1 -PreflightOnly` $\to$ đạt `PRECHECK_OK`, in đúng URL Qdrant và cấu hình V3.
   - Khởi chạy stack qua `.\scripts\start-dev.ps1` $\to$ các container `postgres`, `minio`, `keycloak-dev`, `qdrant` đều đạt trạng thái `Healthy`.
   - Gửi câu hỏi qua giao diện web hoặc API $\to$ vết kiểm tra (trace) xác nhận sử dụng chiến lược `retrieval-hybrid-rerank-top8-v3`, tìm kiếm qua Qdrant và gọi bộ xếp hạng lại BGE Reranker thành công.
4. **Cập nhật tài liệu hướng dẫn:**
   - Cập nhật [local-development.md](file:///C:/Developer/Projects/knora-agent-worktree/refactor-compose-consolidation/docs/runbooks/local-development.md) để ghi nhận Qdrant trong topology hàng ngày.
   - Cập nhật sơ đồ kiến trúc và tổng quan runtime trong `README.md` và `README.vi.md`.
