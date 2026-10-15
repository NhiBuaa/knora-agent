# Revalidation offline của capture 001

Owner duyệt sửa evaluator và kiểm lại cùng saved capture tại
[#153](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6185933495).
Đã thông báo phạm vi shared seam trước khi sửa tại
[#158](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6185933873).

## Kết quả

[`result.json`](result.json) ghi **accepted về structure/provenance** khi replay chính
public response/trace/chunk snapshot đã lưu qua `PdfHttpExecutor`. Shared validator dùng
formatter production `citation_excerpt` với offsets và so sánh chính xác. Không đổi backend,
parser, prompt, threshold, metric contract, corpus/gold hoặc binding.

- Response SHA `771c285f4bc78ddbfcba89c5d4e181673e322c5a91ba0a9417773d59d0513c9f`.
- Trace `1540271b-3946-4565-bbe6-aec3a901eb73`; conversation, turn, run/case/attempt giữ nguyên.
- 18 file frozen byte-identical với `2ce2fe6`; 47 chunks khớp snapshot sau dừng; tái tạo
  proposal và existing binding validator chấp nhận 61 mappings/25 missing.
- Chín negative checks sửa excerpt/source/locator/version/checksum/page/offsets đều bị từ chối.
- 31 archive hashes được kiểm lại; input hashes giữ raw bytes, code hashes dùng text chuẩn hoá LF
  để đối chiếu được giữa Windows/Linux; cả hai được ghi rõ trong result.

Đây là **bằng chứng dẫn xuất offline**, chưa là observation được chọn vào collection.
Không sửa [failed capture](../captures/case-pdf-v3-001-attempt-1.json), counters/stop reason,
report hoặc human-review packet lịch sử: total60, attempted1, observation_failed1, not_run59,
observed0 và retrieval_evaluable0. Semantic review vẫn pending; không tuyên bố quality PASS.

## Cách tái hiện

Từ repository root, dùng Python environment của repository:

```powershell
.\.venv\Scripts\python -m evals.reports.pdf_retrieval_v3_v1.baseline-b-layout-v2.offline-revalidation.revalidate
```

[`revalidate.py`](revalidate.py) chỉ in JSON; không ghi vào captures/report/counters. Transport là
`httpx.MockTransport`, dùng turn envelope dựng từ saved IDs và public response nguyên bản;
reader lấy saved trace + snapshot, không đọc DB hiện tại. Đây không phải xác minh mới trạng thái
persistence/runtime hay replay model. Không gọi network/model/DB/Docker, không ingestion,
judge/export/scoring. Ngân sách trả phí 0 USD.

`validate_approval` kiểm owner/status/hai SHA; `approved_commit` chỉ là metadata.
So sánh frozen bytes với Git được thực hiện riêng. Runtime embedding provenance/active state
vẫn cần fresh preflight nếu owner duyệt tiếp tục live.

## Kiểm chứng bản sửa

- TDD: checker cũ từ chối ba dạng preview hợp lệ (whitespace, dài, PDF interior); sau sửa,
  10 trường hợp regression qua, gồm từ chối raw PDF prefix và excerpt bị sửa.
- Bộ liên quan M3/HTTP/PDF/binding/formatter: **82 passed**.
- Partition backend CI: **1366 passed, 8 failed, 622 deselected**. Cả 8 lỗi do môi trường kế thừa
  SOCKS proxy nhưng thiếu `socksio`. Chạy lại riêng hai file lỗi với `NO_PROXY=*` chỉ trong tiến trình
  test: **61 passed**. Không cài dependency hay sửa config runtime. Một test negative mới được thêm
  sau lần chạy partition và đã nằm trong 82 tests trên; không chạy lại toàn partition.
- `ruff format .`, format check và lint qua; `docker compose config --quiet` qua với cảnh báo
  thiếu hai biến credentials MinIO, không start container hoặc dùng database.
- Review độc lập bản sửa, regression và kết quả replay: không có Critical/Important/Minor findings.
- Không chạy partition DB/Windows/runtime; CI required trên commit mới cần được xác nhận riêng.

## Quyết định tiếp theo — chưa được duyệt

Khuyến nghị cho phép chọn kết quả revalidation của **cùng response/trace/attempt001** qua record
dẫn xuất có hash và đường dẫn về failed capture gốc, không retry/re-answer hoặc xoá lịch sử.
Record cần gắn owner decision URL, input capture SHA, response SHA, trace/attempt IDs, code digest,
proposal/derivation SHA; collector chỉ chọn record sau khi kiểm các identity và approval này.
Phối hợp seam chọn observation qua #158, thêm regression chống hash/identity drift và mock không
dispatch lại001 trước live. Cách chọn đó chưa được triển khai trong lần sửa evaluator này.

Để tiếp tục 59 câu còn lại, cần owner duyệt riêng: tổng allowance vẫn tối đa60 query embeddings/
60 generations (đã dùng1/1, còn tối đa59/59); không ingestion/retry/judge/export; giữ đủ60câu và
25missing. Fresh Workers Free/account/quota và persisted approved binding/config, phối hợp cửa sổ
runtime; nhóm đầu chỉ thêm tối đa11câu để đủ checkpoint12 của cùng lượt, đối chiếu dự toán rồi mới
tiếp tục. Mọi lỗi/drift/quota không bảo đảm thì dừng. PR #189 tiếp tục Draft.
