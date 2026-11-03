# Kế hoạch triển khai: Mặc định hóa Tìm kiếm Kết hợp (Hybrid Search) với Qdrant và Reranker (Retrieval V3)

> **Dành cho agent thực thi:** SUB-SKILL BẮT BUỘC: Sử dụng `subagent-driven-development` (khuyến nghị) hoặc `executing-plans` để thực hiện kế hoạch này theo từng tác vụ. Các bước sử dụng cú pháp ô kiểm (`- [ ]`) để theo dõi tiến độ.

**Mục tiêu:** Chính thức đưa Tìm kiếm Kết hợp với Qdrant và Xếp hạng lại (`retrieval-hybrid-rerank-top8-v3`) trở thành cấu hình tìm kiếm mặc định trên toàn hệ thống Knora (Docker Compose, cấu hình backend, bộ khởi chạy phát triển và tài liệu vận hành).

**Kiến trúc:** Bổ sung dịch vụ `qdrant` tiêu chuẩn vào nhóm dịch vụ cốt lõi của `docker-compose.dev.yml` và `docker-compose.yml` (tuân thủ nghiêm ngặt quy tắc tối đa 2 nguồn Compose và bảo vệ tính cô lập của `verification-qdrant`), cập nhật các giá trị mặc định trong `settings.py` và `.env.example`, nâng cấp `scripts/start-dev.ps1` với cơ chế kiểm tra volume ownership và healthcheck cho Qdrant, đồng thời đồng bộ tài liệu hướng dẫn.

**Ngăn xếp công nghệ:** Qdrant v1.19.2, Docker Compose, Python / FastAPI / Pydantic Settings, PowerShell Job Objects.

**Tài liệu đặc tả (Spec):** [`docs/specs/2026-11-03-default-hybrid-qdrant-retrieval.md`](file:///C:/Developer/Projects/knora-agent-worktree/refactor-compose-consolidation/docs/specs/2026-11-03-default-hybrid-qdrant-retrieval.md)

---

## Các Ràng buộc Bất biến Toàn cục (Global Constraints)

- **Tối đa hai nguồn Compose:** Duy trì duy nhất `docker-compose.yml` và `docker-compose.dev.yml`, không tạo file thứ ba hoặc dùng `include`/`extends` trỏ ra ngoài.
- **Cô lập dữ liệu kiểm thử:** Volume phát triển hàng ngày `knora-dev_knora_qdrant_data` không bao giờ được dùng chung cho các bài test fixture; dịch vụ `verification-qdrant` (profile `retrieval-test`/`retrieval-http-test`, cổng 16433) giữ nguyên vẹn.
- **Thứ bậc dự phòng đa tầng:** Lỗi Reranker $\to$ lùi về DBSF + SDM; Qdrant mất kết nối $\to$ Fail-Fast với lỗi `LEXICAL_RETRIEVAL_UNAVAILABLE`.
- **Ngân sách AI cục bộ \$0:** Không nạp thư viện AI nặng trên máy trạm; toàn bộ embedding và rerank ủy quyền cho Cloudflare Workers AI.

---

## Chi tiết các Tác vụ (Tasks)

### Tác vụ 1: Cập nhật Cấu trúc Docker Compose (`docker-compose.dev.yml` & `docker-compose.yml`)

**Tệp tin:**
- Sửa: `docker-compose.dev.yml`
- Sửa: `docker-compose.yml`
- Kiểm tra: `backend/test/config/test_compose_inventory.py`

**Giao diện:**
- Cung cấp dịch vụ `qdrant` trên cổng loopback `127.0.0.1:6333:6333` với volume `knora_qdrant_data:/qdrant/storage`.

- [ ] **Bước 1: Chạy kiểm tra hợp đồng phân loại Compose hiện tại**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m pytest backend/test/config/test_compose_inventory.py
  ```
  Kỳ vọng: 34 passed.

- [ ] **Bước 2: Bổ sung dịch vụ `qdrant` vào `docker-compose.dev.yml`**
  Thêm định nghĩa dịch vụ `qdrant` không gán profile (chạy mặc định):
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
  Khai báo top-level volume: `knora_qdrant_data:`.

- [ ] **Bước 3: Bổ sung dịch vụ `qdrant` vào `docker-compose.yml`**
  Thêm dịch vụ `qdrant` đồng bộ và bổ sung `qdrant: { condition: service_healthy }` vào `depends_on` của dịch vụ `api`. Khai báo top-level volume: `knora_qdrant_data:`.

- [ ] **Bước 4: Kiểm tra tính hợp lệ cú pháp của hai file Compose**
  ```powershell
  docker compose -f docker-compose.yml config --quiet
  docker compose -f docker-compose.dev.yml config --quiet
  ```
  Kỳ vọng: Cả 2 lệnh thoát mã 0.

- [ ] **Bước 5: Chạy kiểm tra lại `test_compose_inventory.py`**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m pytest backend/test/config/test_compose_inventory.py
  ```
  Kỳ vọng: 34 passed (không vi phạm giới hạn 2 nguồn Compose).

- [ ] **Bước 6: Tạo commit Git**
  ```bash
  git add docker-compose.yml docker-compose.dev.yml
  git commit -m "feat(compose): add standard qdrant service to dev and prod topologies"
  ```

---

### Tác vụ 2: Cập nhật Cấu hình Hệ thống (`settings.py` & `.env.example`)

**Tệp tin:**
- Sửa: `backend/src/knora/infrastructure/settings.py`
- Sửa: `.env.example`
- Sửa: `C:\Developer\Projects\knora-agent\.env` (nếu cần đồng bộ môi trường cục bộ)
- Kiểm tra: `backend/test/test_bootstrap.py`

**Giao diện:**
- `settings.retrieval_configuration_id`: `"retrieval-hybrid-rerank-top8-v3"`
- `settings.lexical_qdrant_url`: `"http://127.0.0.1:6333"`
- `settings.lexical_qdrant_collection`: `"knora"`

- [ ] **Bước 1: Chạy kiểm tra bootstrap hiện tại**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m pytest backend/test/test_bootstrap.py
  ```
  Kỳ vọng: PASS.

- [ ] **Bước 2: Cập nhật giá trị mặc định trong `backend/src/knora/infrastructure/settings.py`**
  ```python
  retrieval_configuration_id: str = "retrieval-hybrid-rerank-top8-v3"
  lexical_qdrant_url: str | None = "http://127.0.0.1:6333"
  lexical_qdrant_collection: str | None = "knora"
  ```

- [ ] **Bước 3: Cập nhật mẫu `.env.example` và `.env`**
  Thay thế dòng chú thích cũ bằng:
  ```dotenv
  KNORA_RETRIEVAL_CONFIGURATION_ID=retrieval-hybrid-rerank-top8-v3
  KNORA_LEXICAL_QDRANT_URL=http://127.0.0.1:6333
  KNORA_LEXICAL_QDRANT_COLLECTION=knora
  ```

- [ ] **Bước 4: Chạy kiểm tra hợp đồng cấu hình và bootstrap**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m pytest backend/test/test_bootstrap.py backend/test/answering/test_retrieval_configuration.py backend/test/answering/test_dense_hybrid_contract.py
  ```
  Kỳ vọng: Tất cả các bài kiểm tra đều PASS.

- [ ] **Bước 5: Định dạng mã nguồn Python**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m ruff check backend/src/knora/infrastructure/settings.py
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m ruff format backend/src/knora/infrastructure/settings.py
  ```

- [ ] **Bước 6: Tạo commit Git**
  ```bash
  git add backend/src/knora/infrastructure/settings.py .env.example
  git commit -m "feat(config): promote retrieval-hybrid-rerank-top8-v3 to default configuration"
  ```

---

### Tác vụ 3: Nâng cấp Bộ khởi chạy Phát triển (`scripts/start-dev.ps1`)

**Tệp tin:**
- Sửa: `scripts/start-dev.ps1`
- Kiểm tra: `backend/test/adapters/cli/test_dev_launcher.py`

**Giao diện:**
- Tham số: `[int]$QdrantPort = 6333`
- Lưu trữ sở hữu: `knora-dev_knora_qdrant_data`
- Quản lý dịch vụ: Bổ sung `'qdrant'` vào `$storageServices`

- [ ] **Bước 1: Chạy kiểm tra launcher hiện tại**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m pytest backend/test/adapters/cli/test_dev_launcher.py -k "test_preflight or test_ownership"
  ```

- [ ] **Bước 2: Cập nhật `scripts/start-dev.ps1`**
  1. Thêm `[int]$QdrantPort = 6333` vào khối `param()`.
  2. Thêm kiểm tra cổng `$QdrantPort` trong danh mục kiểm tra an toàn cổng.
  3. Đăng ký volume `"${composeProject}_knora_qdrant_data"` vào `$expectedVolumeConfig`:
     ```powershell
     "${composeProject}_knora_qdrant_data" = @{
         Service = 'qdrant'
         Destination = '/qdrant/storage'
         Role = 'knora_qdrant_data'
     }
     ```
  4. Bổ sung `'qdrant'` vào `$storageServices`:
     ```powershell
     $storageServices = @('postgres', 'minio', 'qdrant')
     if ($useBundledKeycloak) { $storageServices += 'keycloak-dev' }
     ```
  5. Thiết lập biến môi trường lan truyền:
     ```powershell
     if (-not $env:KNORA_LEXICAL_QDRANT_URL) {
         $env:KNORA_LEXICAL_QDRANT_URL = "http://127.0.0.1:$QdrantPort"
     }
     if (-not $env:KNORA_LEXICAL_QDRANT_COLLECTION) {
         $env:KNORA_LEXICAL_QDRANT_COLLECTION = 'knora'
     }
     ```
  6. Thêm `Write-Output "QDRANT_URL=$env:KNORA_LEXICAL_QDRANT_URL"` vào thông tin preflight.

- [ ] **Bước 3: Chạy kiểm tra lại `test_dev_launcher.py`**
  ```powershell
  & "C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe" -m pytest backend/test/adapters/cli/test_dev_launcher.py
  ```
  Kỳ vọng: Tất cả tests PASS.

- [ ] **Bước 4: Kiểm tra trực tiếp lệnh preflight**
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -EnvFile C:/Developer/Projects/knora-agent/.env -PreflightOnly
  ```
  Kỳ vọng: Đạt `PRECHECK_OK` và in ra `QDRANT_URL=http://127.0.0.1:6333`.

- [ ] **Bước 5: Tạo commit Git**
  ```bash
  git add scripts/start-dev.ps1
  git commit -m "feat(dev): integrate qdrant lifecycle and storage verification into start-dev.ps1"
  ```

---

### Tác vụ 4: Đồng bộ Tài liệu Vận hành và Kiến trúc

**Tệp tin:**
- Sửa: `docs/runbooks/local-development.md`
- Sửa: `README.md`
- Sửa: `README.vi.md`

- [ ] **Bước 1: Cập nhật sơ đồ Runtime Layout và danh mục cổng trong `docs/runbooks/local-development.md`**
  Thêm `Qdrant (Dense & Lexical Hybrid)` vào sơ đồ Docker Desktop và bảng cổng mặc định (`127.0.0.1:6333`).

- [ ] **Bước 2: Cập nhật phần tổng quan kiến trúc và công nghệ trong `README.md` & `README.vi.md`**
  Ghi nhận Qdrant là thành phần tìm kiếm kết hợp mặc định bên cạnh PostgreSQL.

- [ ] **Bước 3: Định dạng tài liệu và mã nguồn chia sẻ**
  ```powershell
  npm --prefix frontend run format:shared
  npm --prefix frontend run format:shared:check
  ```

- [ ] **Bước 4: Tạo commit Git**
  ```bash
  git add docs/runbooks/local-development.md README.md README.vi.md
  git commit -m "docs: document qdrant hybrid search as default runtime component"
  ```

---

### Tác vụ 5: Kiểm chứng Nghiệm thu Toàn diện (End-to-End Acceptance)

**Tác vụ thực nghiệm:**
- [ ] **Bước 1: Khởi tạo lại cụm dịch vụ lưu trữ sạch gồm Qdrant**
  ```powershell
  docker compose -f docker-compose.dev.yml -p knora-dev up -d --wait postgres minio keycloak-dev qdrant
  ```
- [ ] **Bước 2: Khởi chạy toàn bộ stack phát triển**
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -EnvFile C:/Developer/Projects/knora-agent/.env
  ```
  Xác nhận `DEV_READY` với đầy đủ 4 PID tiến trình.
- [ ] **Bước 3: Kiểm tra sức khỏe các điểm đầu cuối**
  - `http://127.0.0.1:8000/health` $\to$ `status: ok`.
  - `http://127.0.0.1:6333/healthz` $\to$ HTTP 200.
  - `http://127.0.0.1:3000` $\to$ HTTP 200.
- [ ] **Bước 4: Kiểm tra collection Qdrant đã được backend tạo tự động**
  ```powershell
  (Invoke-RestMethod http://127.0.0.1:6333/collections).result.collections
  ```
  Xác nhận có collection `knora`.
- [ ] **Bước 5: Dừng stack sạch sẽ và xác nhận không rò rỉ tài nguyên**
