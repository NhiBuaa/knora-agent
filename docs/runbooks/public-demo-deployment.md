# Knora Public Demo — Hướng dẫn Triển khai Tối ưu Chi phí ($0)

Tài liệu này hướng dẫn chi tiết quy trình đưa **Knora Public Demo** lên môi trường public độc lập với chi phí gần như **0 USD**, tận dụng các gói miễn phí (Free Tier) của **Vercel**, **Render**, **Supabase**, **Cloudflare R2**, **Qdrant Cloud**, và **Cloudflare Workers AI**.

---

## 1. Sơ đồ Kiến trúc & Phân bổ Tải

```
[ Người dùng / Recruiter ]
          │ (HTTPS)
          ▼
   [ Vercel: Frontend & BFF ] ─────────────────────────┐
          │                                            │ (OIDC Auth)
          │ (Internal API Forward)                     ▼
          ▼                                    [ Keycloak Service ]
   [ Render: Knora Backend ]                    (Render Web Service)
    ├── FastAPI Web API (Uvicorn)
    ├── PDF Ingestion Worker (Background)
    └── Conversation Worker (Background)
          │
    ┌─────┴──────────────────┬──────────────────┬─────────────────┐
    ▼                        ▼                  ▼                 ▼
[ Supabase ]          [ Cloudflare R2 ]   [ Qdrant Cloud ]  [ Cloudflare Workers AI ]
PostgreSQL + pgvector S3 Object Storage   Hybrid Search     Qwen3 0.6B Embedding
Relational Authority  PDF Files           BM25 + Dense      GPT-OSS 20B Generation
```

---

## 2. Chuẩn bị Hạ tầng Miễn phí (Chỉ mất 5–10 phút)

### Bước 1: Tạo Database trên Supabase (PostgreSQL + pgvector)
1. Đăng nhập [supabase.com](https://supabase.com) và tạo Organization / Project mới (chọn Region `Singapore`).
2. Vào **Project Settings** → **Database** → kéo xuống mục **Connection string**:
   - Chọn tab **URI**, chọn chế độ **Transaction / Session** (port `6543` hoặc `5432`).
   - Copy chuỗi kết nối: `postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`
   - Đổi tiền tố thành `postgresql+psycopg://...` và thêm `?sslmode=require` ở cuối.
3. Vào **SQL Editor** trong Supabase, kiểm tra/kích hoạt extension vector:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

### Bước 2: Tạo Object Storage trên Cloudflare R2
1. Đăng nhập [dash.cloudflare.com](https://dash.cloudflare.com) → vào mục **R2**.
2. Nhấn **Create bucket** → Đặt tên bucket: `knora-public-demo`.
3. Nhấn **Manage R2 API Tokens** → **Create API Token**:
   - Quyền: **Object Read & Write**.
   - Lưu lại: `Access Key ID`, `Secret Access Key`, và `Endpoint URL` (dạng `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`).

### Bước 3: Tạo Vector Database trên Qdrant Cloud
1. Đăng nhập [cloud.qdrant.io](https://cloud.qdrant.io).
2. Tạo cụm **Free Tier (1 GB Cluster)** (hoàn toàn miễn phí, chọn region AWS hoặc GCP gần nhất).
3. Sau khi cụm tạo xong, copy:
   - **Cluster URL** (dạng `https://xxxx-xxxx.us-east4-0.gcp.cloud.qdrant.io:6333`).
   - Vào **API Keys** → Tạo key mới và lưu lại `API Key`.

---

## 3. Triển khai Backend & Auth trên Render

### Bước 4: Deploy Keycloak Service trên Render
1. Trên [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
2. Kết nối tới repository `NhiBuaa/knora-agent` (nhánh `feat/public-demo`).
3. Cấu hình dịch vụ:
   - **Name**: `knora-keycloak`
   - **Language**: `Docker`
   - **Dockerfile Path**: `infra/keycloak/Dockerfile`
   - **Instance Type**: `Free`
4. Cấu hình **Environment Variables**:
   - `KEYCLOAK_VAULT`: `""`
   - `KC_BOOTSTRAP_ADMIN_USERNAME`: `admin`
   - `KC_BOOTSTRAP_ADMIN_PASSWORD`: `<đặt_mật_khẩu_admin_mạnh>`
   - `KC_DB`: `postgres`
   - `KC_DB_URL`: `jdbc:postgresql://<SUPABASE_HOST>:5432/postgres?sslmode=require`
   - `KC_DB_USERNAME`: `postgres`
   - `KC_DB_PASSWORD`: `<mật_khẩu_supabase>`
   - `KC_HOSTNAME`: `https://knora-keycloak.onrender.com` (hoặc URL mà Render cấp)
   - `JAVA_OPTS_KC_HEAP`: `-Xms32m -Xmx192m` cho instance Free 512 MiB; đây chỉ là giới hạn Java heap, không phải tổng RAM của tiến trình.
5. **Start Command**:
   ```bash
   /opt/keycloak/start-public-demo.sh
   ```
   Provider cập nhật listener `knora-default-capabilities` trong cùng tiến trình sau migration/import, kể cả khi realm đã tồn tại. Kiểm tra log `Public-demo realm capabilities listener reconciled.`; không chạy thêm `kcadm` trong instance 512 MiB. Tài khoản đã đăng ký trước bản sửa cần đăng xuất và đăng nhập lại để nhận quyền mặc định.

### Bước 5: Deploy Knora Backend API trên Render
1. Trên Render Dashboard → **New** → **Web Service**.
2. Kết nối repository `NhiBuaa/knora-agent` (nhánh `feat/public-demo`).
3. Cấu hình:
   - **Name**: `knora-backend`
   - **Language**: `Docker`
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Instance Type**: `Free`
4. **Start Command**:
   ```bash
   /app/scripts/start-render.sh
   ```
5. Cấu hình **Environment Variables** (theo file mẫu `.env.production.template`):
   - `KNORA_DATABASE_URL`: `postgresql+psycopg://...` (từ Bước 1)
   - `KNORA_OBJECT_STORE_BACKEND`: `s3_compatible`
   - `KNORA_OBJECT_STORE_S3_ENDPOINT`: Endpoint R2 (từ Bước 2)
   - `KNORA_OBJECT_STORE_S3_BUCKET`: `knora-public-demo`
   - `KNORA_OBJECT_STORE_S3_REGION`: `auto`
   - `KNORA_OBJECT_STORE_S3_ACCESS_KEY`: Access Key R2
   - `KNORA_OBJECT_STORE_S3_SECRET_KEY`: Secret Key R2
   - `KNORA_LEXICAL_QDRANT_URL`: URL Qdrant Cloud (từ Bước 3)
   - `KNORA_LEXICAL_QDRANT_COLLECTION`: `knora`
   - `KNORA_LEXICAL_QDRANT_API_KEY`: API Key Qdrant Cloud
   - `KNORA_EMBEDDING_PROVIDER`: `cloudflare-workers-ai`
   - `KNORA_GENERATION_PROVIDER`: `cloudflare-workers-ai`
   - `KNORA_CLOUDFLARE_ACCOUNT_ID`: Account ID Cloudflare của bạn
   - `KNORA_CLOUDFLARE_API_TOKEN`: API Token Cloudflare Workers AI
   - `KNORA_RETRIEVAL_CONFIGURATION_ID`: `retrieval-hybrid-top8-v3`
   - `KNORA_KEYCLOAK_ISSUER`: `https://knora-keycloak.onrender.com/realms/knora-dev`
   - `KNORA_KEYCLOAK_AUDIENCE`: `knora-web`
   - `KNORA_KEYCLOAK_JWKS_URL`: `https://knora-keycloak.onrender.com/realms/knora-dev/protocol/openid-connect/certs`

---

## 4. Triển khai Frontend trên Vercel

1. Đăng nhập [vercel.com](https://vercel.com) → **Add New Project** → Chọn repository `NhiBuaa/knora-agent`.
2. Cấu hình dự án:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: `frontend` (nhấn Edit và chọn thư mục `frontend`).
3. Cấu hình **Environment Variables** trên Vercel:
   - `KNORA_API_URL`: `https://knora-backend.onrender.com`
   - `KEYCLOAK_AUTHORIZATION_URL`: `https://knora-keycloak.onrender.com/realms/knora-dev/protocol/openid-connect/auth`
   - `KEYCLOAK_TOKEN_URL`: `https://knora-keycloak.onrender.com/realms/knora-dev/protocol/openid-connect/token`
   - `KEYCLOAK_REDIRECT_URI`: `https://<ten-app-cua-ban>.vercel.app/api/auth/callback`
   - `KEYCLOAK_POST_LOGOUT_REDIRECT_URI`: `https://<ten-app-cua-ban>.vercel.app/`
   - `KEYCLOAK_ISSUER`: `https://knora-keycloak.onrender.com/realms/knora-dev`
   - `KEYCLOAK_JWKS_URL`: `https://knora-keycloak.onrender.com/realms/knora-dev/protocol/openid-connect/certs`
   - `KEYCLOAK_CLIENT_ID`: `knora-web`
   - `KEYCLOAK_AUDIENCE`: `knora-web`
   - `SESSION_SECRET`: Một chuỗi ngẫu nhiên 32 ký tự (ví dụ: chạy `openssl rand -hex 32` để lấy).
4. Nhấn **Deploy**.

---

## 5. Quy trình Kiểm tra Nghiệm thu Live (Verification Checklist)

Sau khi cả 3 dịch vụ đều đã online:
- [ ] **Đăng ký / Đăng nhập**: Truy cập URL Vercel → Bấm **Register** → Tạo tài khoản mới → Tự động đăng nhập thành công và khởi tạo Workspace riêng biệt.
- [ ] **Upload PDF**: Tải lên một tài liệu PDF có văn bản (ví dụ `Teacher Manh - Guidelines 2024.pdf`) → File được lưu trữ lên Cloudflare R2, PDF worker bóc tách nội dung, sinh embedding và lập chỉ mục hybrid vào Qdrant Cloud.
- [ ] **Hỏi đáp & Citation**: Đặt câu hỏi có trong tài liệu (ví dụ: *"Báo cáo đồ án cần trình bày bao nhiêu chương?"*) → Câu trả lời trả về kèm liên kết trích dẫn (citation) mở đúng đoạn văn bản trích dẫn.
- [ ] **Kiểm tra Refusal**: Đặt câu hỏi hoàn toàn không có trong tài liệu (ví dụ: *"Thời tiết Paris ngày mai thế nào?"*) → Hệ thống trả lời từ chối lịch sự (Refusal), không bịa đặt nguồn dẫn (no fabricated citations).
- [ ] **Bảo vệ Secrets & Cô lập Tenant**: Kiểm tra Inspect Network trên trình duyệt: tuyệt đối không lộ Cloudflare Token, R2 secret hay Supabase password trong network payload hoặc console logs. Người dùng không thể truy cập tài liệu hay hội thoại của Workspace khác.

---

## 6. Vận hành, Khôi phục & Rollback

- **Khởi động lại (Restart)**: Trên Render Dashboard, nhấn **Manual Deploy** → **Clear build cache & deploy** hoặc **Restart Service**.
- **Rollback**: Khi cần quay về commit trước:
  - Trên Render: Chọn tab **Deploys** → Chọn bản deploy thành công trước đó → **Rollback to this deploy**.
  - Trên Vercel: Chọn tab **Deployments** → Chọn commit trước đó → **Redeploy**.
- **Khôi phục dữ liệu**: Supabase tự động lưu giữ point-in-time recovery và backup; dữ liệu PDF nằm an toàn trên Cloudflare R2 độc lập với vòng đời của container Render.
