# Review binding gold → chunks: pypdf layout-v2 (offline)

**Trạng thái: NhiBuaa đã duyệt nội dung/occurrence offline ngày 2026-10-15. Chưa có binding approval runtime.**

[Quyết định của owner](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6183912900):
duyệt 58 mapping duy nhất, chọn `g5→#0`, `g6→#1`, `t17→#1` và ghi nhận 25 missing
trong packet tại commit `f18ef8d5577b6b880e65b42f6a153088b0117cde`, đúng hai digest bên dưới.
Giữ nguyên chunks/proposals và frozen corpus/gold. Đây không phải approved runtime binding
record hoặc quyền chạy Baseline B/model/scoring. Các bảng `proposed`/`ambiguous`/`missing`
giữ kết quả của proposer trước review; khuyến nghị trong packet đã được owner chấp thuận
ở phạm vi nội dung offline này.

[Runtime preparation / reuse inspection / ingestion inventory](runtime-preparation.md):
đã kiểm tra read-only tài nguyên #153; chờ owner duyệt ingestion embedding-only.
Actual runtime proposal SHA chưa có; corpus/gold và snapshot này giữ nguyên.

## Phạm vi và danh tính

- Giữ nguyên 16 PDF / 60 câu / 86 anchors đã freeze. Không gọi model, không dùng database/runtime/Docker/ports; chi phí trả phí 0 USD.
- Dùng production `PypdfTextExtractor`, `PdfExtractionConfiguration.layout_preserving()` và existing `propose_bindings`; không fuzzy matching, OCR, parser mới hoặc thay gold.
- `offline/...` là nhãn đối chiếu nội dung, không phải UUID của chunks đã persist. Hai digest dưới đây chỉ nhận diện snapshot offline, không được dùng làm approval cho runtime/scoring.
- `approved_commit` trong corpus/gold approval record là provenance metadata. `validate_approval` kiểm tra status, owner và hai SHA, không trực tiếp kiểm chứng commit. Nội dung frozen được so với Git commit riêng.
- Nội dung frozen tại `2ce2fe63096e4fd244ea6aa7e9f77f73b30e89af`; approval record đã ghi tại `9804f0af161aacb00748cdee6b08929e898bbd3a`.
- Corpus SHA: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`.
- Gold SHA: `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`.
- Code dùng chuẩn bị snapshot: `9804f0af161aacb00748cdee6b08929e898bbd3a`.
- Offline proposal SHA: `2fa44a4d7acefbf60bf4f5fef457b7a28b97de46d76120b51c0a4453fbc44075`.
- Offline chunks derivation SHA: `b4d5a22177e14b3d02e5d762460a0f3d32de47c913c464e6ea68759650157f99`.
- [chunks.json](chunks.json): cấu hình, phiên bản package, lỗi extraction, toàn bộ 47 chunks và checksum/content/offset.
- [proposals.json](proposals.json): toàn bộ candidates và occurrence indexes (0-based).

```json
{
  "configuration": {
    "parser_version": "pypdf-6.14.2-layout-v2",
    "extraction_options_version": "pypdf-layout-lines-v2",
    "normalizer_version": "pdf-normalizer-m2-v1",
    "tokenizer_name": "cl100k_base",
    "tokenizer_version": "tiktoken-0.12.0",
    "chunking_policy_version": "page-block-v1",
    "target_tokens": 500,
    "overlap_tokens": 75,
    "max_tokens": 650,
    "max_raw_bytes": 26214400,
    "max_pages": 500,
    "max_page_stream_bytes": 4194304,
    "max_total_stream_bytes": 67108864,
    "extraction_timeout_seconds": 30.0,
    "extractor_memory_bytes": 268435456,
    "minimum_extracted_characters": 1
  },
  "package_versions": {
    "pypdf": "6.14.2",
    "tiktoken": "0.12.0"
  }
}
```

## Kết quả theo tài liệu

58 anchor có một exact occurrence, 3 ambiguous, 25 missing. Đây là độ sẵn có của source binding, không phải điểm retrieval hay kết quả baseline.

| PDF nguồn | Chunks | Duy nhất | Mơ hồ | Thiếu |
| --- | ---: | ---: | ---: | ---: |
| [clean-01](../../../corpora/pdf_retrieval_v3_v1/clean-01.pdf) | 2 | 6 | 0 | 0 |
| [clean-02](../../../corpora/pdf_retrieval_v3_v1/clean-02.pdf) | 1 | 4 | 2 | 0 |
| [hierarchy-01](../../../corpora/pdf_retrieval_v3_v1/hierarchy-01.pdf) | 1 | 6 | 0 | 0 |
| [hierarchy-02](../../../corpora/pdf_retrieval_v3_v1/hierarchy-02.pdf) | 1 | 6 | 0 | 0 |
| [hierarchy-03](../../../corpora/pdf_retrieval_v3_v1/hierarchy-03.pdf) | 2 | 6 | 0 | 0 |
| [columns-01](../../../corpora/pdf_retrieval_v3_v1/columns-01.pdf) | 1 | 6 | 0 | 0 |
| [columns-02](../../../corpora/pdf_retrieval_v3_v1/columns-02.pdf) | 1 | 0 | 0 | 6 |
| [table-01](../../../corpora/pdf_retrieval_v3_v1/table-01.pdf) | 1 | 7 | 1 | 0 |
| [table-02](../../../corpora/pdf_retrieval_v3_v1/table-02.pdf) | 1 | 8 | 0 | 0 |
| [table-03](../../../corpora/pdf_retrieval_v3_v1/table-03.pdf) | 1 | 8 | 0 | 0 |
| [scan-01](../../../corpora/pdf_retrieval_v3_v1/scan-01.pdf) | 0 | 0 | 0 | 4 |
| [scan-02](../../../corpora/pdf_retrieval_v3_v1/scan-02.pdf) | 1 | 0 | 0 | 4 |
| [scan-03](../../../corpora/pdf_retrieval_v3_v1/scan-03.pdf) | 0 | 0 | 0 | 4 |
| [academic-phobert](../../../corpora/pdf_retrieval_v3_v1/academic-phobert.pdf) | 14 | 0 | 0 | 2 |
| [academic-phonlp](../../../corpora/pdf_retrieval_v3_v1/academic-phonlp.pdf) | 13 | 1 | 0 | 1 |
| [academic-vit5](../../../corpora/pdf_retrieval_v3_v1/academic-vit5.pdf) | 7 | 0 | 0 | 4 |

## Ba lựa chọn mơ hồ — owner đã duyệt nội dung offline

| Anchor | Bằng chứng PDF | Occurrences trong chunk | Lựa chọn owner duyệt offline |
| --- | --- | --- | --- |
| g5 | clean-02 p1, x45/y498, dòng phí thứ nhất | clean-02/000: #0 `[297,333)`, #1 `[334,370)` | #0 theo đúng vị trí dòng thứ nhất |
| g6 | clean-02 p1, x45/y446, dòng phí thứ hai | clean-02/000: #0 `[297,333)`, #1 `[334,370)` | #1 theo đúng vị trí dòng thứ hai |
| t17 | table-01 p1, hàng TB-20, cột Còn chờ, đơn vị đơn | table-01/000: #0 `[164,165)` là chữ số 9 trong TB-19; #1 `[183,184)` là ô 9 của TB-20 | #1; loại #0 vì sai hàng/cột/ngữ nghĩa |

g5/g6 có cùng câu “Không thu phí xác nhận phiếu hỗ trợ.” và cùng chunk, nhưng hai vùng nguồn khác nhau. Giữ đúng hai occurrence và OR group hiện có; không nhập hai anchors làm một.

## Những trường hợp thiếu và bằng chứng đối chiếu

- **c21–c26 (6):** PDF columns-02 trang 1 có hai cột độc lập. Extractor ghép theo dòng ngang, chèn cột kia vào giữa câu. Ví dụ gold `Evidence nghĩa là bằng chứng nguồn, không phải câu trả lời.` trở thành hai dòng dưới đây. Giữ missing trong exact-match proposal; không suy diễn rằng PDF thiếu bằng chứng.

```text
Evidence nghĩa là bằng chứng nguồn, không Answer means a response supported by
phải câu trả lời. source evidence.
```

- **s11–s14, s21–s24, s31–s34 (12):** đã nhìn thấy bằng chứng trong ảnh ở ba scan PDF trang 1. scan-01/03 thất bại extraction; scan-02 có chunk title/footer nhưng không có text của ảnh. Không bind title/footer vào evidence.
- **pb1, pb2, pn1 (3):** PDF gốc trang 1 có abstract đúng source anchors; text pypdf xen cột và thay đổi xuống dòng. Không đổi hyphen/newline/wording của frozen gold để tạo match. PhoBERT vẫn đúng hai phiên bản; pn1 vẫn đủ POS/NER/dependency parsing.
- **v51–v54 (4):** ViT5 trang 1 có nội dung abstract/introduction đúng vùng nguồn; snapshot pypdf chỉ giữ footer và mất body. Không bind footer vào evidence.

## Kiểm tra agent đã thực hiện

- Đối chiếu bằng mắt các trang PDF chứa 86 source anchors (15 trang synthetic và trang 1 của mỗi academic PDF), region/heading/row/column/unit với snapshot text.
- Đọc 58 candidates duy nhất trong ngữ cảnh: mã hồ sơ, điều kiện/ngoại lệ phân cấp, ngữ nghĩa hai cột, hàng/cột/đơn vị bảng. Không dùng số trùng khác vị trí để thay source region.
- `pn2` khớp `Apache License 2.0.` của toolkit PhoNLP ở abstract trang 1; không phải license của PDF. Gold vẫn yêu cầu phân biệt hai đối tượng.
- So raw source SHA qua frozen dataset loader; so Gold/manifest với frozen commit riêng; kiểm tra checksum, page/range, source identity và exact text tại mỗi candidate.
- Tạo lại proposals bằng existing function từ 47 chunk records và so toàn bộ JSON/digests. Không ghi approved binding review file và không scoring.
- pypdf có cảnh báo rotated text / degraded layout; giữ cấu hình baseline và ghi nhận giới hạn, không bỏ tài liệu lỗi.

## Toàn bộ 86 anchors

Range `[start,end)` tính theo ký tự trên trang đã normalize, 0-based, không phải tọa độ PDF. Nhãn chunk rút gọn bỏ tiền tố `offline/`; JSON giữ đầy đủ. Mỗi checksum/full content nằm trong chunks.json. `proposed` chỉ là candidate đã đối chiếu, vẫn chờ owner.

| Anchor | Nguồn/trang/vùng gold | Text gold | Kết quả / candidates |
| --- | --- | --- | --- |
| r1 | clean-01 p1; left text block; x=45, y=706 PDF points from bottom | Mã A-17 tra cứu hồ sơ QD-42. | proposed: #0 clean-01/chunk/000 [78,106) |
| r2 | clean-01 p1; left text block; x=45, y=654 PDF points from bottom | Mã B-08 tra cứu hồ sơ TB-19. | proposed: #0 clean-01/chunk/000 [107,135) |
| r3 | clean-01 p1; left text block; x=45, y=602 PDF points from bottom | Mã C-31 tra cứu hồ sơ SC-07. | proposed: #0 clean-01/chunk/000 [136,164) |
| r4 | clean-01 p2; left text block; x=45, y=706 PDF points from bottom | Mã D-12 tra cứu hồ sơ COL-58. | proposed: #0 clean-01/chunk/001 [78,107) |
| r5 | clean-01 p2; left text block; x=45, y=654 PDF points from bottom | Mã E-24 tra cứu hồ sơ QD-63. | proposed: #0 clean-01/chunk/001 [108,136) |
| r6 | clean-01 p2; left text block; x=45, y=602 PDF points from bottom | Mã F-09 tra cứu hồ sơ TB-27. | proposed: #0 clean-01/chunk/001 [137,165) |
| g1 | clean-02 p1; left text block; x=45, y=706 PDF points from bottom | Phiếu hỗ trợ chuẩn phải được xác nhận trong 24 giờ. | proposed: #0 clean-02/chunk/000 [81,132) |
| g2 | clean-02 p1; left text block; x=45, y=654 PDF points from bottom | Phiếu hỗ trợ khẩn phải được xác nhận trong 2 giờ. | proposed: #0 clean-02/chunk/000 [133,182) |
| g3 | clean-02 p1; left text block; x=45, y=602 PDF points from bottom | Giờ xác nhận không phải thời gian giải quyết hoàn tất. | proposed: #0 clean-02/chunk/000 [183,237) |
| g4 | clean-02 p1; left text block; x=45, y=550 PDF points from bottom | Hạn xác nhận được tính theo giờ liên tục, kể cả cuối tuần. | proposed: #0 clean-02/chunk/000 [238,296) |
| g5 | clean-02 p1; left text block; x=45, y=498 PDF points from bottom | Không thu phí xác nhận phiếu hỗ trợ. | ambiguous: #0 clean-02/chunk/000 [297,333); #1 clean-02/chunk/000 [334,370) |
| g6 | clean-02 p1; left text block; x=45, y=446 PDF points from bottom | Không thu phí xác nhận phiếu hỗ trợ. | ambiguous: #0 clean-02/chunk/000 [297,333); #1 clean-02/chunk/000 [334,370) |
| h11 | hierarchy-01 p1; left column; x=45, y=706 PDF points from bottom; heading path QD-42 | QD-42: mức bồi hoàn tối đa là 350.000 đồng. | proposed: #0 hierarchy-01/chunk/000 [79,122) |
| h12 | hierarchy-01 p1; left column; x=45, y=653 PDF points from bottom; heading path 1. Phạm vi | 1. Phạm vi: áp dụng cho đơn hàng nội địa. | proposed: #0 hierarchy-01/chunk/000 [123,164) |
| h13 | hierarchy-01 p1; left column; x=61, y=600 PDF points from bottom; heading path 1.1. Đơn chuẩn | 1.1. Đơn chuẩn: được đổi trong 48 giờ sau khi nhận. | proposed: #0 hierarchy-01/chunk/000 [165,216) |
| h14 | hierarchy-01 p1; left column; x=61, y=547 PDF points from bottom; heading path 1.2. Đơn vùng xa | 1.2. Đơn vùng xa: được đổi trong 72 giờ sau khi nhận. | proposed: #0 hierarchy-01/chunk/000 [217,270) |
| h15 | hierarchy-01 p1; left column; x=77, y=494 PDF points from bottom; heading path 1.2.1. Ngoại lệ | 1.2.1. Ngoại lệ: không nhận đổi hàng đã mở niêm phong. | proposed: #0 hierarchy-01/chunk/000 [271,325) |
| h16 | hierarchy-01 p1; left column; x=45, y=441 PDF points from bottom; heading path 2. Hoàn tiền | 2. Hoàn tiền: xử lý trong 5 ngày làm việc. | proposed: #0 hierarchy-01/chunk/000 [326,368) |
| h21 | hierarchy-02 p1; left column; x=45, y=706 PDF points from bottom; heading path QD-63 | QD-63: thời hạn lưu bản sao là 90 ngày. | proposed: #0 hierarchy-02/chunk/000 [75,114) |
| h22 | hierarchy-02 p1; left column; x=45, y=653 PDF points from bottom; heading path 1. Quyền truy cập | 1. Quyền truy cập: người đọc chỉ được xem tài liệu. | proposed: #0 hierarchy-02/chunk/000 [115,166) |
| h23 | hierarchy-02 p1; left column; x=61, y=600 PDF points from bottom; heading path 1.1. Biên tập viên | 1.1. Biên tập viên: được sửa bản nháp, không được công bố. | proposed: #0 hierarchy-02/chunk/000 [167,225) |
| h24 | hierarchy-02 p1; left column; x=61, y=547 PDF points from bottom; heading path 1.2. Chủ sở hữu | 1.2. Chủ sở hữu: được công bố bản đã duyệt. | proposed: #0 hierarchy-02/chunk/000 [226,269) |
| h25 | hierarchy-02 p1; left column; x=45, y=494 PDF points from bottom; heading path 2. Lưu trữ | 2. Lưu trữ: bản nháp thường được giữ 30 ngày. | proposed: #0 hierarchy-02/chunk/000 [270,315) |
| h26 | hierarchy-02 p1; left column; x=61, y=441 PDF points from bottom; heading path 2.1. Hồ sơ tranh chấp được giữ 90 ngày, thay cho 30 ngày. | 2.1. Hồ sơ tranh chấp được giữ 90 ngày, thay cho 30 ngày. | proposed: #0 hierarchy-02/chunk/000 [316,373) |
| h31 | hierarchy-03 p1; left column; x=45, y=706 PDF points from bottom; heading path 1. Cảnh báo P1 | 1. Cảnh báo P1: phải báo trực trong 15 phút. | proposed: #0 hierarchy-03/chunk/000 [76,120) |
| h32 | hierarchy-03 p1; left column; x=61, y=653 PDF points from bottom; heading path 1.1. Cảnh báo P2 | 1.1. Cảnh báo P2: phải báo trực trong 60 phút. | proposed: #0 hierarchy-03/chunk/000 [121,167) |
| h33 | hierarchy-03 p1; left column; x=77, y=600 PDF points from bottom; heading path 1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ. | 1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ. | proposed: #0 hierarchy-03/chunk/000 [168,213) |
| h34 | hierarchy-03 p2; left column; x=45, y=706 PDF points from bottom; heading path 2. Người trực phải xác nhận đã nhận cảnh báo. | 2. Người trực phải xác nhận đã nhận cảnh báo. | proposed: #0 hierarchy-03/chunk/001 [76,121) |
| h35 | hierarchy-03 p2; left column; x=61, y=653 PDF points from bottom; heading path 2.1. Khi chưa có xác nhận, gọi lại sau 5 phút. | 2.1. Khi chưa có xác nhận, gọi lại sau 5 phút. | proposed: #0 hierarchy-03/chunk/001 [122,168) |
| h36 | hierarchy-03 p2; left column; x=61, y=600 PDF points from bottom; heading path 2.2. Không gửi nội dung khách hàng qua kênh công khai. | 2.2. Không gửi nội dung khách hàng qua kênh công khai. | proposed: #0 hierarchy-03/chunk/001 [169,223) |
| c11 | columns-01 p1; left text block; x=45, y=706 PDF points from bottom | COL-58: tổng hạn mức là 42 lượt. | proposed: #0 columns-01/chunk/000 [74,106) |
| c12 | columns-01 p1; left text block; x=45, y=654 PDF points from bottom | Hạn mức đầu kỳ cấp 14 lượt. | proposed: #0 columns-01/chunk/000 [139,166) |
| c13 | columns-01 p1; left text block; x=45, y=602 PDF points from bottom | Hạn mức chuyển kỳ tối đa 28 lượt. | proposed: #0 columns-01/chunk/000 [211,244) |
| c14 | columns-01 p1; right text block; x=315, y=706 PDF points from bottom | Không cộng dồn lượt đã hết hạn. | proposed: #0 columns-01/chunk/000 [107,138) |
| c15 | columns-01 p1; right text block; x=315, y=654 PDF points from bottom | Lượt chuyển kỳ được dùng trước lượt đầu kỳ. | proposed: #0 columns-01/chunk/000 [167,210) |
| c16 | columns-01 p1; right text block; x=315, y=602 PDF points from bottom | Hạn mức được kiểm tra lúc 09:00 mỗi thứ Hai. | proposed: #0 columns-01/chunk/000 [245,289) |
| c21 | columns-02 p1; left text block; x=45, y=706 PDF points from bottom | Evidence nghĩa là bằng chứng nguồn, không phải câu trả lời. | missing: Cột trái/phải xen giữa câu; không có chuỗi liên tục đúng gold. |
| c22 | columns-02 p1; left text block; x=45, y=637 PDF points from bottom | Citation nghĩa là trích dẫn chỉ đến bằng chứng nguồn. | missing: Cột trái/phải xen giữa câu; không có chuỗi liên tục đúng gold. |
| c23 | columns-02 p1; left text block; x=45, y=568 PDF points from bottom | Refusal nghĩa là từ chối trả lời khi thiếu bằng chứng. | missing: Cột trái/phải xen giữa câu; không có chuỗi liên tục đúng gold. |
| c24 | columns-02 p1; right text block; x=315, y=706 PDF points from bottom | Answer means a response supported by source evidence. | missing: Cột trái/phải xen giữa câu; không có chuỗi liên tục đúng gold. |
| c25 | columns-02 p1; right text block; x=315, y=637 PDF points from bottom | A citation does not replace the required answer facts. | missing: Cột trái/phải xen giữa câu; không có chuỗi liên tục đúng gold. |
| c26 | columns-02 p1; right text block; x=315, y=568 PDF points from bottom | A refusal must not invent a missing source fact. | missing: Cột trái/phải xen giữa câu; không có chuỗi liên tục đúng gold. |
| t11 | table-01 p1; merged-header table; row 1; column Mã hồ sơ; unit đơn; x=60, y=527 PDF points from bottom | TB-19 | proposed: #0 table-01/chunk/000 [160,165) |
| t12 | table-01 p1; merged-header table; row 1; column Đã xử lý; unit đơn; x=180, y=527 PDF points from bottom | 12 | proposed: #0 table-01/chunk/000 [166,168) |
| t13 | table-01 p1; merged-header table; row 1; column Còn chờ; unit đơn; x=300, y=527 PDF points from bottom | 18 | proposed: #0 table-01/chunk/000 [169,171) |
| t14 | table-01 p1; merged-header table; row 1; column Tổng; unit đơn; x=420, y=527 PDF points from bottom | 30 | proposed: #0 table-01/chunk/000 [172,174) |
| t15 | table-01 p1; merged-header table; row 2; column Mã hồ sơ; unit đơn; x=60, y=467 PDF points from bottom | TB-20 | proposed: #0 table-01/chunk/000 [175,180) |
| t16 | table-01 p1; merged-header table; row 2; column Đã xử lý; unit đơn; x=180, y=467 PDF points from bottom | 7 | proposed: #0 table-01/chunk/000 [181,182) |
| t17 | table-01 p1; merged-header table; row 2; column Còn chờ; unit đơn; x=300, y=467 PDF points from bottom | 9 | ambiguous: #0 table-01/chunk/000 [164,165); #1 table-01/chunk/000 [183,184) |
| t18 | table-01 p1; merged-header table; row 2; column Tổng; unit đơn; x=420, y=467 PDF points from bottom | 16 | proposed: #0 table-01/chunk/000 [185,187) |
| t21 | table-02 p1; merged-header table; row 1; column Mã hồ sơ; unit phút; x=60, y=527 PDF points from bottom | TB-27 | proposed: #0 table-02/chunk/000 [169,174) |
| t22 | table-02 p1; merged-header table; row 1; column Trực tuyến; unit phút; x=180, y=527 PDF points from bottom | 45 | proposed: #0 table-02/chunk/000 [175,177) |
| t23 | table-02 p1; merged-header table; row 1; column Tại chỗ; unit phút; x=300, y=527 PDF points from bottom | 15 | proposed: #0 table-02/chunk/000 [178,180) |
| t24 | table-02 p1; merged-header table; row 1; column Tổng; unit phút; x=420, y=527 PDF points from bottom | 60 | proposed: #0 table-02/chunk/000 [181,183) |
| t25 | table-02 p1; merged-header table; row 2; column Mã hồ sơ; unit phút; x=60, y=467 PDF points from bottom | TB-28 | proposed: #0 table-02/chunk/000 [184,189) |
| t26 | table-02 p1; merged-header table; row 2; column Trực tuyến; unit phút; x=180, y=467 PDF points from bottom | 20 | proposed: #0 table-02/chunk/000 [190,192) |
| t27 | table-02 p1; merged-header table; row 2; column Tại chỗ; unit phút; x=300, y=467 PDF points from bottom | 10 | proposed: #0 table-02/chunk/000 [193,195) |
| t28 | table-02 p1; merged-header table; row 2; column Tổng; unit phút; x=420, y=467 PDF points from bottom | 30 | proposed: #0 table-02/chunk/000 [196,198) |
| t31 | table-03 p1; merged-header table; row 1; column Mã hồ sơ; unit kg; x=60, y=527 PDF points from bottom | KT-09 | proposed: #0 table-03/chunk/000 [153,158) |
| t32 | table-03 p1; merged-header table; row 1; column Sáng; unit kg; x=180, y=527 PDF points from bottom | 2,5 | proposed: #0 table-03/chunk/000 [159,162) |
| t33 | table-03 p1; merged-header table; row 1; column Chiều; unit kg; x=300, y=527 PDF points from bottom | 4,0 | proposed: #0 table-03/chunk/000 [163,166) |
| t34 | table-03 p1; merged-header table; row 1; column Tổng; unit kg; x=420, y=527 PDF points from bottom | 6,5 | proposed: #0 table-03/chunk/000 [167,170) |
| t35 | table-03 p1; merged-header table; row 2; column Mã hồ sơ; unit kg; x=60, y=467 PDF points from bottom | KT-10 | proposed: #0 table-03/chunk/000 [171,176) |
| t36 | table-03 p1; merged-header table; row 2; column Sáng; unit kg; x=180, y=467 PDF points from bottom | 1,5 | proposed: #0 table-03/chunk/000 [177,180) |
| t37 | table-03 p1; merged-header table; row 2; column Chiều; unit kg; x=300, y=467 PDF points from bottom | 2,0 | proposed: #0 table-03/chunk/000 [181,184) |
| t38 | table-03 p1; merged-header table; row 2; column Tổng; unit kg; x=420, y=467 PDF points from bottom | 3,5 | proposed: #0 table-03/chunk/000 [185,188) |
| s11 | scan-01 p1; raster-only evidence block; image x=95,y=270 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | SC-07: phí lưu kho là 27.000 đồng mỗi ngày. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s12 | scan-01 p1; raster-only evidence block; image x=95,y=425 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Kho ảnh mở từ 08:30 đến 17:30. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s13 | scan-01 p1; raster-only evidence block; image x=95,y=580 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Kho ảnh không nhận hàng vào Chủ nhật. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s14 | scan-01 p1; raster-only evidence block; image x=95,y=735 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Người nhận phải xuất trình mã nhận hàng. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s21 | scan-02 p1; raster-only evidence block; image x=95,y=270 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | MX-11: hồ sơ đã kiểm có 23 trang. | missing: Chỉ có title/footer searchable; bằng chứng trong ảnh không được trích xuất. |
| s22 | scan-02 p1; raster-only evidence block; image x=95,y=425 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Trong hồ sơ có 5 trang phụ lục ảnh. | missing: Chỉ có title/footer searchable; bằng chứng trong ảnh không được trích xuất. |
| s23 | scan-02 p1; raster-only evidence block; image x=95,y=580 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Bản số hóa không thay thế bản gốc có chữ ký. | missing: Chỉ có title/footer searchable; bằng chứng trong ảnh không được trích xuất. |
| s24 | scan-02 p1; raster-only evidence block; image x=95,y=735 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Ngày kiểm tra hồ sơ là 14/10/2026. | missing: Chỉ có title/footer searchable; bằng chứng trong ảnh không được trích xuất. |
| s31 | scan-03 p1; raster-only evidence block; image x=95,y=270 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | RX-03: thiết bị đo có sai số tối đa 0,2 độ C. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s32 | scan-03 p1; raster-only evidence block; image x=95,y=425 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Kiểm chuẩn thiết bị mỗi 6 tháng. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s33 | scan-03 p1; raster-only evidence block; image x=95,y=580 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Không dùng thiết bị khi tem kiểm chuẩn đã hết hạn. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| s34 | scan-03 p1; raster-only evidence block; image x=95,y=735 pixels from top; embedded image occupies PDF x=45..550,y=110..700 | Nhiệt độ bảo quản từ 15 đến 25 độ C. | missing: PDF_TEXT_INSUFFICIENT / INSUFFICIENT_EXTRACTABLE_TEXT; bằng chứng nằm trong ảnh. |
| pb1 | academic-phobert p1; page 1; Abstract, left column, opening sentence | public large-scale monolingual language mod-<br>els pre-trained for Vietnamese. | missing: Cột xen kẽ và/hoặc xuống dòng khác source transcription; exact match không tìm thấy. |
| pb2 | academic-phobert p1; page 1; Abstract opening; base/large are typographic subscripts attached to PhoBERT; transcribed without adding a hyphen | We present PhoBERT with two versions—<br>PhoBERTbase and PhoBERTlarge | missing: Cột xen kẽ và/hoặc xuống dòng khác source transcription; exact match không tìm thấy. |
| pn1 | academic-phonlp p1; page 1; Abstract opening, left column; joint Vietnamese POS tagging, NER and dependency parsing sentence | model—named PhoNLP—for joint Viet-<br>namese part-of-speech (POS) tagging, named<br>entity recognition (NER) and dependency<br>parsing. | missing: Cột xen kẽ và/hoặc xuống dòng khác source transcription; exact match không tìm thấy. |
| pn2 | academic-phonlp p1; page 1; Abstract, left column, toolkit release license sentence | Apache License 2.0. | proposed: #0 academic-phonlp/chunk/000 [1246,1265) |
| v51 | academic-vit5 p1; page 1; Abstract opening, left column; based continues hyphenated Transformer- from preceding line | based encoder-decoder model for the Viet-<br>namese language. | missing: pypdf chỉ còn phần footer; mất body có bằng chứng trên PDF trang 1. |
| v52 | academic-vit5 p1; page 1; Abstract, left column, benchmark sentence | two downstream text generation tasks | missing: pypdf chỉ còn phần footer; mất body có bằng chứng trên PDF trang 1. |
| v53 | academic-vit5 p1; page 1; Abstract, left column, benchmark sentence; stractive continues hyphenated Ab- from preceding line | stractive Text Summarization and Named En-<br>tity Recognition. | missing: pypdf chỉ còn phần footer; mất body có bằng chứng trên PDF trang 1. |
| v54 | academic-vit5 p1; page 1; Introduction, right column near bottom | the Viet-<br>namese monolingual subset of CC100 | missing: pypdf chỉ còn phần footer; mất body có bằng chứng trên PDF trang 1. |

## 60 câu và AND/OR groups

Không thay thế đánh giá retrieval. Với 58 candidates duy nhất: 33 câu có candidate cho đủ groups, 2 câu còn phụ thuộc occurrence mơ hồ, 17 câu thiếu group, 8 câu no-answer không có positive groups. Nếu owner chấp nhận ba lựa chọn trên, 35 câu có candidate cho đủ groups; 17 câu thiếu vẫn giữ nguyên trong mẫu số và gold. Các lựa chọn g5/g6 vẫn phải được review dù là OR alternatives.

| Câu | Groups (AND giữa các ngoặc; OR trong ngoặc) | Độ sẵn có candidate |
| --- | --- | --- |
| pdf-v3-001 | (g1) | đủ unique candidates; chờ owner |
| pdf-v3-002 | (h12) AND (h13) | đủ unique candidates; chờ owner |
| pdf-v3-003 | (h24) | đủ unique candidates; chờ owner |
| pdf-v3-004 | (h31) | đủ unique candidates; chờ owner |
| pdf-v3-005 | (c12) | đủ unique candidates; chờ owner |
| pdf-v3-006 | (s12) | missing required group |
| pdf-v3-007 | (s21) AND (s24) | missing required group |
| pdf-v3-008 | (s31) | missing required group |
| pdf-v3-009 | (g1) AND (g2) AND (g3) | đủ unique candidates; chờ owner |
| pdf-v3-010 | (h13) AND (h14) AND (h15) | đủ unique candidates; chờ owner |
| pdf-v3-011 | (h22) AND (h23) | đủ unique candidates; chờ owner |
| pdf-v3-012 | (h25) AND (h26) | đủ unique candidates; chờ owner |
| pdf-v3-013 | (h31) AND (h32) AND (h33) | đủ unique candidates; chờ owner |
| pdf-v3-014 | (c21) AND (c22) | missing required group |
| pdf-v3-015 | (c23) AND (c24) AND (c26) | missing required group |
| pdf-v3-016 | (pb1) AND (v51) AND (v52) | missing required group |
| pdf-v3-017 | (pn1) AND (v52) AND (v53) | missing required group |
| pdf-v3-018 | (t11) AND (t14) AND (t15) AND (t18) | đủ unique candidates; chờ owner |
| pdf-v3-019 | (t11) AND (t12) AND (t13) AND (t14) | đủ unique candidates; chờ owner |
| pdf-v3-020 | (t15) AND (t16) AND (t17) | ambiguous required group |
| pdf-v3-021 | (t21) AND (t22) AND (t23) AND (t24) | đủ unique candidates; chờ owner |
| pdf-v3-022 | (t25) AND (t26) AND (t27) AND (t28) | đủ unique candidates; chờ owner |
| pdf-v3-023 | (t31) AND (t32) AND (t33) AND (t34) | đủ unique candidates; chờ owner |
| pdf-v3-024 | (t35) AND (t36) AND (t37) AND (t38) | đủ unique candidates; chờ owner |
| pdf-v3-025 | (h34) AND (h35) | đủ unique candidates; chờ owner |
| pdf-v3-026 | (h36) | đủ unique candidates; chờ owner |
| pdf-v3-027 | (c14) AND (c15) | đủ unique candidates; chờ owner |
| pdf-v3-028 | (s22) AND (s23) | missing required group |
| pdf-v3-029 | (g4) AND (g5 OR g6) | ambiguous required group |
| pdf-v3-030 | (h16) | đủ unique candidates; chờ owner |
| pdf-v3-031 | (h24) | đủ unique candidates; chờ owner |
| pdf-v3-032 | (h33) | đủ unique candidates; chờ owner |
| pdf-v3-033 | (c13) AND (c16) | đủ unique candidates; chờ owner |
| pdf-v3-034 | (s13) AND (s14) | missing required group |
| pdf-v3-035 | (s22) | missing required group |
| pdf-v3-036 | (s32) AND (s33) | missing required group |
| pdf-v3-037 | (g2) | đủ unique candidates; chờ owner |
| pdf-v3-038 | (h11) | đủ unique candidates; chờ owner |
| pdf-v3-039 | (h21) | đủ unique candidates; chờ owner |
| pdf-v3-040 | (c11) | đủ unique candidates; chờ owner |
| pdf-v3-041 | (s11) | missing required group |
| pdf-v3-042 | (s34) | missing required group |
| pdf-v3-043 | (c25) | missing required group |
| pdf-v3-044 | (pb2) | missing required group |
| pdf-v3-045 | (pn2) | đủ unique candidates; chờ owner |
| pdf-v3-046 | (v54) | missing required group |
| pdf-v3-047 | (r1) AND (h11) | đủ unique candidates; chờ owner |
| pdf-v3-048 | (r2) AND (t11) AND (t14) | đủ unique candidates; chờ owner |
| pdf-v3-049 | (r3) AND (s11) | missing required group |
| pdf-v3-050 | (r4) AND (c11) | đủ unique candidates; chờ owner |
| pdf-v3-051 | (r5) AND (h21) | đủ unique candidates; chờ owner |
| pdf-v3-052 | (r6) AND (t21) AND (t24) | đủ unique candidates; chờ owner |
| pdf-v3-053 | — | no-answer; không suy thành positive PASS |
| pdf-v3-054 | — | no-answer; không suy thành positive PASS |
| pdf-v3-055 | — | no-answer; không suy thành positive PASS |
| pdf-v3-056 | — | no-answer; không suy thành positive PASS |
| pdf-v3-057 | — | no-answer; không suy thành positive PASS |
| pdf-v3-058 | — | no-answer; không suy thành positive PASS |
| pdf-v3-059 | — | no-answer; không suy thành positive PASS |
| pdf-v3-060 | — | no-answer; không suy thành positive PASS |

## Boundary trước scoring và runtime binding còn phải duyệt

Runtime chunk IDs/chunk-set IDs được tạo UUID4 khi persist kết quả ingestion thành công, sau `embed_documents`. Reader chỉ trả active/current completed chunk+embedding sets. Snapshot này không chứng minh có hay không có một derivation đã persist trong session khác; không truy cập runtime dùng chung khi chưa phối hợp.

Code đối chiếu: `backend/src/knora/ingestion/job_processing.py` (`PdfDerivationHandler.execute`), `backend/src/knora/adapters/postgres/ingestion_jobs/coordination.py` (success persistence), `backend/src/knora/adapters/postgres/evaluation_reader.py` (`read_pdf_chunks`), `evals/runners/pdf_retrieval_v3.py` (propose/collect), `evals/runners/pdf_source_binding.py` (digest/review).

Owner đã duyệt nội dung/occurrence offline ở packet này: 58 unique candidates, g5→#0/g6→#1/t17→#1 và ghi nhận 25 missing, không sửa gold. Chưa được chuyển lựa chọn đó thành approved runtime review file.

Khi ingestion thực được cho phép và đã phối hợp runtime: xác minh Free plan/quota thực, không phát sinh phí; lấy persisted chunks và đề xuất bằng lệnh hiện có; đối chiếu source SHA/config/page/offset/checksum/content với packet này; trình actual proposal SHA + IDs cho owner duyệt riêng trước scoring/collect. B/model vẫn chưa được duyệt chạy trong bước này.

Không freeze lại corpus/gold, không mở rộng S1, không đổi threshold 0.65, không merge PR #189 (Draft).
