# Runtime binding preparation — 2026-10-15

**Báo cáo chuẩn bị tại commit 71bf691, trước approval ingestion.** Owner đã duyệt và lượt ingestion sau đó hoàn tất; [actual runtime packet](../binding-layout-v2-runtime/README.md) trình SHA/IDs mới, đang chờ owner duyệt binding trước scoring. Nội dung bên dưới giữ bằng chứng và proposal tại thời điểm chuẩn bị.

## Phê duyệt và phạm vi giữ nguyên

Owner đã review commit `5610ecd` và chấp thuận kết quả binding offline: 58 mappings duy nhất,
`g5→#0`, `g6→#1`, `t17→#1` (61 mappings), cùng 25 anchors missing.
Đây không phải approval runtime IDs/digest, B generation/60 câu hỏi hoặc scoring.
Corpus/gold vẫn là 16 PDF/60 câu đã freeze; parser pypdf layout-v2,
Qwen3 Embedding 0.6B/1024d và mọi cấu hình/threshold giữ nguyên.

## Kiểm tra persisted chunks có thể reuse

Đã điều phối tại [#158](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6184482236),
đối chiếu ownership cũ và Docker labels: `knora153s1-postgres-1` thuộc worktree #153,
project `knora153s1`, volume `knora153s1_knora_postgres_data`, loopback55453.
Container được khởi động chỉ để đọc rồi đã trả về **stopped**. Không API/worker/model.

Inspection lúc **2026-10-15 04:35:03 UTC / 11:35:03 Việt Nam**:

- Catalog chỉ có `knora` và `postgres`; chưa có `knora153s1_baseline`.
- Database `knora` có 474 PDF version records từ kiểm thử.
- Truy vấn theo **raw SHA256 của cả 16 PDF frozen**, không chỉ source name:
  **0 matching versions, 0 chunks, 0 current completed chunks cho từng PDF**.
- Một số fixtures có nhãn config Cloudflare/Qwen3/layout-v2, nhưng không cùng raw SHA.
  Nhãn config không chứng minh đây là provider outputs của corpus; không được reuse.
- PostgreSQL `default_transaction_read_only=on`, explicit `BEGIN READ ONLY`,
  `transaction_read_only=on`, statement timeout10s. Không migrations/DML/write.
- Bằng chứng chi tiết giữ local tại `.verification/runtime-binding-reuse-inspection.json`;
  one-off inspection dùng catalog/provenance read-only, không tạo/chèn chunk giả.

**Kết luận trong phạm vi đã kiểm:** không có persisted corpus chunks hợp lệ để reuse.
Chưa truy cập DB5432, knora-dev55432 hoặc database/volume của session khác.
Đã hỏi qua #158 về derivation có thể chia sẻ; chưa có identity/ownership bàn giao.
Không suy ra rằng mọi database trên máy đều không có dữ liệu phù hợp. Nếu có bàn giao
derivation khác trước khi chạy, kiểm tra reuse trước và giảm inventory, không gọi lại vô ích.

## Cloudflare thực tế và budget

Đã đọc dashboard đăng nhập sẵn, **không inference/probe hoặc đổi subscription**:

- Workers plans hiển thị **Free / $0 / Current plan**.
- Workers AI usage sau reload hiển thị **95.88 /10,000 neurons used today**
  trong cửa sổ kiểm tra khoảng 04:33–04:35 UTC; còn khoảng **9,904.12 neurons**.
  Dùng daily counter; biểu đồ Last24hours không phải quota hôm nay.
- Account trong cấu hình local primary khớp account dashboard; token key hiện diện.
  Không in/lưu token vào Git; token permissions/validity chưa gọi API để kiểm chứng.
- Endpoint trong provider là direct `api.cloudflare.com/.../ai/run/@cf/qwen/qwen3-embedding-0.6b`,
  không AI Gateway billing route. Chỉ model này nằm trong đề xuất ingestion.
- Đây là inspection evidence, **chưa phải fresh admission preflight cho một lượt được phép**.
  Trước startup phải làm mới plan/usage trong 15phút, kiểm account/credentials thực nạp và
  phối hợp các session dùng cùng quota. Nếu cần số nguyên cho guard hiện có, làm tròn usage
  lên (95.88→96), giữ số đo gốc; không làm tròn xuống hoặc sửa validator.

[Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
công bố Free10,000neurons/ngày, reset00:00UTC/07:00Việt Nam; vượt quota Free dừng,
không nâng cấp. Qwen3 embedding được liệt kê **1,075 neurons /1M input tokens** và không nằm
trong nhóm yêu cầu paid billing method ở tài liệu được kiểm hôm nay.
[Model documentation](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/).
Không gọi thử model để chứng minh access trước phê duyệt; nếu access bị từ chối thì dừng.

**Paid allowance: 0 USD**, không reserve, không upgrade, không overage hoặc paid gateway.
Usage/quota có thể đổi do session khác; bằng chứng này không đặt chỗ quota hoặc bảo đảm đủ.

## Inventory ingestion mới đề nghị — chưa thực hiện

| Hạng mục | Lượt đầu không retries |
| --- | ---: |
| PDF upload vào local API | 16 POST |
| PDF dự kiến extraction được / lỗi trước embedding | 14 /2 |
| Chunks / embedding input strings | 47 /47 |
| Cloudflare Qwen3 embedding HTTP POST | **14** |
| Query embedding / generation / judge requests | **0 /0 /0** |
| PDF bytes / số trang | 2,083,688 /35 |
| Text content UTF8 gửi embed, chưa JSON overhead | 53,772 bytes |
| Local cl100k sizing (không phải Qwen tokenizer accounting) | 16,307 tokens |

14 requests vì handler gọi `embed_documents` theo từng PDF; provider batch32,
mỗi PDF đọc được ở snapshot có dưới32 chunks. Không ghép14documents thành2requests.
scan-01/03 vẫn upload rồi giữ extraction failure; scan-02 chỉ title/footer vẫn được ghi nhận.

Nếu dùng local token count làm proxy với pricing trên, 16,307×1,075/1M ≈ **17.53 neurons**.
Đây chỉ là ước lượng, không phải usage provider hoặc trần quota: Qwen tokenizer, special
tokens và retries khác local sizing. Không đưa giá trị USD tương đương thành ngân sách trả phí.

**Khuyến nghị phạm vi lượt đầu: tối đa14 embedding HTTP attempts /47 strings; không tự retry
model request khi lỗi/timeout/persist thất bại.** Dừng để xem attempt artifacts, không tạo
run/job mới để né counter. Các scan failure terminal đã biết không gọi model và không bị
loại khỏi corpus. Nếu14/47 không đủ do extraction khác snapshot, dừng và trình khác biệt.

Worker hiện có mặc định tối đa4 job attempts; để owner hiểu inventory: nếu cho phép toàn bộ
retry envelope sẽ lên56POST/188strings trong cùng extraction, chưa được đề xuất cấp quyền
ở lượt đầu này. Không dùng cap rộng2,500strings/70generation làm permission.

## Tài nguyên và cách chạy sau khi được duyệt

- Reuse container/volume riêng `knora153s1`, DB mới `knora153s1_baseline`, loopback55453;
  API8153, object root riêng trong worktree, một workspace/run identity bền vững.
- Chỉ API upload/poll và production ingestion worker, max concurrency1; không Turn worker,
  không `/questions`, query embeddings, generation/judge, Langfuse Cloud export hoặc Ragas.
- **Không chạy nguyên `pdf_baseline_runtime.main`** cho scope này: nó khởi động cả ingestion
  và conversation loops. Dùng composition `build_evaluation_app`/production worker hiện có
  trong launcher local tối thiểu chỉ start ingestion; không đổi extraction/persistence logic.
  Chặn outbound ngoài document-embedding endpoint và chặn generation/query trước network;
  giữ FreeOnlyGuard, scope counters14/47 và stop-before-retry. Kiểm tra guard bằng mock trước
  live; không xây budget framework hay thêm framework/dataset.
- Cấu hình extractor giữ nguyên: child memory256MiB,30s, raw25MiB/PDF, max500pages;
  không GPU/Ollama/frontend/MinIO/Keycloak. Dung lượng2.08MB nguồn và192,512bytes float32
  vectors chỉ là payload; PostgreSQL/index/process overhead lớn hơn, không nhận là RAM cap tổng.
- Migrations chỉ DB mới được sở hữu sau approval. Không dùng DB kiểm thử `knora` hoặc DB daily.
- Fresh Free/quota/account coordination trước start; 429/quota hết thì giữ run/chunks/config và
  dừng chờ reset, 402/403 dừng kiểm access. Không tự trả phí hoặc chuyển model/parser.

## Đầu ra cần trình owner trước scoring

1. Đọc current/active/completed persisted derivations bằng reader hiện có, tạo actual proposal.
2. So từng chunk với snapshot theo rawSHA, parser/normalizer/chunker config, page/range,
   checksum/content; UUID chunk/version/set/workspace khác là identity thực, không được tự thay
   bằng nhãn offline hoặc dùng lại offline proposal SHA.
3. Đối chiếu **61 mappings đã duyệt**, chọn đúng vị trí g5/g6/t17; giữ25 anchors missing.
   Nếu actual extraction/proposals khác, báo rõ; không sửa gold, fuzzy match hoặc tự nhận mapping mới.
4. Trình actual runtime proposal SHA, derivation SHA, IDs và bảng mọi khác biệt cho owner duyệt.
   Không tạo approved runtime review record trước quyết định; chưa collect/scoring/B60questions.

**Actual runtime proposal SHA: chưa có** — không có derivation hợp lệ trong tài nguyên đã kiểm
và chưa được phép ingestion/model. Không dùng SHA của empty fixture hoặc offline snapshot thay thế.

PR#189 giữ Draft; không merge/deploy/Done. Chưa sửa production code, chưa gọi model hoặc chạy
full tests cho báo cáo chuẩn bị này.
