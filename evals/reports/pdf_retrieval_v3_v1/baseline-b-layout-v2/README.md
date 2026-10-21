# Baseline B — dừng ở câu 001

**Cập nhật sau báo cáo ban đầu:** Owner đã duyệt sửa evaluator và revalidate offline tại
[#153](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6185933495).
[Kết quả revalidation](offline-revalidation/README.md) chấp nhận structure/provenance của cùng
saved response/trace; chưa chọn vào collection hoặc resume B. Các kết quả và đề nghị Q1 bên dưới
là lịch sử tại thời điểm dừng, không bị đổi thành PASS.

Ngày 15/10/2026. Run `s1-runtime-binding-20261015-01`, code `ffcbd4283c8b29ae34afba26f087f9760c2f7f1c`. Đây là **partial report**, chưa hoàn thành Baseline B hoặc semantic acceptance. PR #189 giữ Draft.

## Kết quả thực chạy

| Chỉ tiêu | Kết quả |
| --- | ---: |
| Gold cases / PDFs giữ nguyên | 60 / 16 |
| Attempted / observed hợp lệ cho evaluator | 1 / 0 |
| Observation failed / provider failed | 1 / 0 |
| Not run | 59 |
| Retrieval evaluable theo contract hiện hữu | 0 |
| Query embedding attempts / generation attempts bổ sung | 1 / 1 |
| Document embedding / ingestion mới | 0 / 0 |
| Judge / export | 0 / 0 |
| Paid allowance | 0 USD |

Guard dừng `CASE_FAILED_NO_RETRY`; lỗi gốc lưu riêng `observation_failure_code=CITATION_STRUCTURAL_ERROR`. Không có request cho câu002–060, không retry câu001. [Report nguyên contract](report.json), [candidate vs selected coverage](candidate-vs-selected-coverage.json), [human review đủ60câu](human-review.md). `acceptance=pending_owner_review_and_B` là nhãn cũ của builder hiện hữu, không phải trạng thái B đã hoàn thành. Semantic review vẫn pending, tools `not_run`.

## Lỗi thực tế và bằng chứng

Public response của câu001: **“Phiếu hỗ trợ chuẩn phải được xác nhận trong 24 giờ. [[E1]]”**. Saved trace ghi `generation_status=completed`, `validation_outcome=valid`, `finish_reason=stop`. Đây là dữ liệu để owner review, chưa là semantic PASS.

- Trace: `1540271b-3946-4565-bbe6-aec3a901eb73`.
- Conversation/turn: `d2adebf7-d1c6-4dca-b18a-c0255a7294de` / `4dd3c00a-072a-4985-b69d-843feeaf0eae`.
- Response SHA: `771c285f4bc78ddbfcba89c5d4e181673e322c5a91ba0a9417773d59d0513c9f`.
- E1 trỏ chunk `b75a9997-9248-4268-adea-7e6dc100e0b5`, `clean-02.pdf`, page1, offsets `[0,420)`, version `28008827-fc3a-43dc-9d5b-713b86da62e9`.

Replay offline từ [capture bất biến](captures/case-pdf-v3-001-attempt-1.json), [trace đọc từ DB](operational-evidence/trace-pdf-v3-001.json) và [snapshot sau dừng](operational-evidence/persistence-after-stop.json) tái hiện lỗi tại `evals/runners/milestone_3.py:1025–1027`: shared checker so sánh `citation.excerpt` với `content[:500]`. Production `AnswerQuestion._citation` dùng `knora.answering.excerpt.citation_excerpt(...)`, cắt phần từ dở và thêm dấu“…”. Preview thực tế414ký tự khớp chính xác formatter production; chunk420ký tự. Chỉ thay preview trong bộ nhớ thành raw prefix thì checker cũ chấp nhận. Xem [kết quả replay](operational-evidence/citation-preview-diagnosis.json).

Alias, source/locator, checksum, version, page/line/offsets và trace identity đã được đối chiếu với dữ liệu đã lưu; 47chunks vẫn bằng snapshot đã duyệt. Predicate cũ vẫn tồn tại trên GitHub `main` khi tra ngày15/10/2026 sau PR190. Đây là lỗi tương thích của evaluator với citation preview hiện tại; chưa sửa backend, evaluator hoặc capture để đi tiếp.

## Retrieval và generation: giới hạn kết luận

Trace câu001 có một retrieved candidate, cũng là `SELECTED`, similarity `0.7775003545731415` trên threshold0.65. Required group `g1` có mặt trong cả hai tập. Kết quả này chỉ là **diagnostic từ saved trace của case failed**, không được đưa vào numerator của report.

Report coverage dùng cùng cohort hiện hữu: case observed, có positive evidence groups và mỗi group có ít nhất một approved binding. Cohort hiện bằng0, nên cả candidate coverage lẫn selected coverage đều `null`; không phải0% hoặc100%. “Candidates” là post-threshold final-decision pool, không phải toàn bộ vector branch hits. Metric `all_evidence_groups_covered` hiện hữu tiếp tục dùng selected evidence, không đổi contract.

Chưa có đủ dữ liệu để kết luận chất lượng Retrieval/Generation cho toàn bộ60câu, multi-hop, follow-up, refusal hoặc PDF phức tạp. 25anchors missing và hai scan ingestion failures lịch sử vẫn được giữ; `extraction_or_mapping_missing=0` trong report lượt này do chưa có observed case đi vào nhánh đó, không có nghĩa extraction đã được sửa.

## Quota và tài nguyên

[Admission](operational-evidence/free-before-batch-01.json) xác nhận account khớp credentials, WorkersFree / Current plan, daily usage114.07/10,000, còn9,885.93neurons, đủ admission8,500. Chỉ hai models/endpoint đã duyệt, không gateway hoặc nâng cấp. [Checkpoint sau dừng](operational-evidence/usage-after-stop.json) vẫn hiển thị114.07; dashboard có thể trễ/chia sẻ nên delta0 không được xem là model consumption0.

Saved generation usage nằm trong trace: **543prompt +156completion =699tokens**. Theo [rates đã tra](https://developers.cloudflare.com/workers-ai/platform/pricing/), generation tương đương khoảng14.127414neurons; embedding usage không có trong metadata. Đây là quy đổi rates, không phải invoice. Builder không lấy được usage từ failed row vì validation dừng trước bước thêm metadata; trace/operational evidence vẫn giữ số thật. Một case này chưa đủ checkpoint12câu để xác nhận dự toán7,500neurons hoặc ngoại suy chi phí60câu. Gate lỗi đã chặn continuation.

Counters ingestion lịch sử giữ14document embedding HTTP attempts/47strings; cộng B là15embedding HTTP attempts/48strings, generation1. Không reset allowance. Owned container `knora153s1-postgres-1` đã stopped; DB `knora153s1_baseline`, volume và objects được giữ để review. Không mở listener8153; không dùng dailyDB hoặc tài nguyên session khác. Coordination/release: [#158](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6185765630).

## Freeze và provenance

- Corpus SHA: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`.
- Gold SHA: `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`.
- Approved proposal SHA: `3796d4228f8bd5d6677b162125c34d551e644fe5488133c31df8b0f306488a9d`.
- Derivation SHA: `fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2`.
- Binding review SHA: `7d7efbb47e548392eca3846a576552d238eb850f862bda7f9e16f7dc7bfb3288`.
- 47persisted Qwen1024d chunks; 61approved mappings/25missing; pypdf layout-v2, GPT-OSS20B max_tokens1024, threshold0.65 và prompt/config không đổi.

`validate_approval` kiểm owner/status/haiSHA; `approved_commit` là metadata của record, không phải điều kiện được validator kiểm trực tiếp. So sánh Git riêng bảo vệ frozen bytes.

[Archive manifest](archive-manifest.json) liệt kê SHA-256 các bản sao byte-identical. Canonical source vẫn là `.verification/issue153/run`; archived captures là review mirrors của cùng run/case/attempt, không phải lần chạy hay authority thứ hai. `operational-evidence` là đọc lại DB/quota và diagnostic, không tự bổ sung một scored observation. [Launcher](source/baseline-b-runtime.py.txt), [mock selfcheck](source/baseline-b-runtime-selfcheck.py.txt), [report builder](source/baseline-b-build-report.py.txt) là source archive; ROOT/path gốc được ghi trong scripts, không chạy trực tiếp tại thư mục archive.

## Kiểm chứng và quyết định tiếp theo

Trước live: independent review không còn Critical/Important findings; mock qua provider adapters thật với transport giả lập cho phép60query/60generation và chặn cả hai request61 trước dispatch, kiểm sticky failures, counters, batch12/13 và saved-case skip. Sau dừng: replay lỗi offline, kiểm identities/caps/full60denominator, source/checksum/provenance và archive hashes. Không chạy model/full tests lại để làm report.

❓ **Q1 — Duyệt sửa tương thích evaluator và kiểm lại saved capture offline?**

➡️ Khuyến nghị sửa shared excerpt check để so sánh chính xác với formatter production `citation_excerpt`, giữ các kiểm alias, source/locator, checksum/version/page/offsets và metric contract; thêm focused regression cho preview hợp lệ và preview bị sửa. Phối hợp #158 trước khi sửa seam chung. Sau đó trình kết quả revalidation của cùng response/trace, giữ capture failed ban đầu và lịch sử attempts. **Không gọi model hoặc tự resume trong bước sửa này.**

Việc chọn cách đưa saved case001 đã revalidate vào collection và tiếp tục59câu phụ thuộc kết quả sửa/review, sẽ trình ở vòng sau. Lượt đã gửi vẫn tính1/60query và1/60generation; chưa có quyền retry, vượt allowance hoặc thay cấu hình. Không tự merge/deploy/Done.
