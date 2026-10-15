# Baseline B — đề nghị owner duyệt riêng

Ngày 15/10/2026. **Chưa được phép thực hiện.** Approval runtime binding không cấp quyền Q&A, generation hoặc scoring. Phạm vi dưới đây là khuyến nghị để owner chốt theo `$grilling`, không phải quyết định đã duyệt.

## 1. Phạm vi và giới hạn requests

Tái sử dụng run `s1-runtime-binding-20261015-01`, workspace `ee8acee6-6fea-4aaf-b472-d5ae1609516f`, 47 persisted chunks và [approved binding](binding-review.json). Giữ nguyên corpus/gold 16 PDF/60 câu, 25 missing, parser pypdf layout-v2, Qwen3 Embedding 0.6B1024d, GPT-OSS20B `max_tokens=1024`, threshold 0.65 và prompt/retrieval configuration hiện tại.

| Hoạt động | Giới hạn lượt đầu được đề nghị |
| --- | ---: |
| Upload / ingestion / document embeddings mới | 0 |
| Query embedding HTTP attempts / strings bổ sung | tối đa 60 /60 |
| Generation HTTP attempts bổ sung | tối đa 60 |
| Requested completion allowance | tối đa 61,440 tokens (`60×1024`) |
| LLM judge / gold generation / paid gateway | 0 |
| Paid allowance / reserve | 0 USD /0 USD |

60 câu gồm 44 stateless question submissions và 16 conversation turns trong 8 conversations (8 câu cha, 8 follow-ups 029–036). Mỗi câu đến answering có một query embedding; generation có thể bị bỏ qua khi production logic trả refusal. Parent lỗi có thể chặn child dispatch, vẫn giữ child trong mẫu số 60. Không bỏ 8 REFUSAL hoặc các câu thiếu evidence để tăng tỷ lệ pass.

Giữ counters ingestion đã có: 14 document embedding HTTP attempts/47 strings, generation0. Ghi rõ phạm vi B bổ sung và tổng tích lũy; nếu mọi câu đến embedding thì tổng là 74 embedding HTTP attempts/107 strings. Không reset counters hoặc dùng cap cũ 2,500 strings/70 generation để suy ra quyền chạy thêm. Không retry tự động hoặc reserve requests ngoài giới hạn trên.

## 2. Dự toán Free quota

[Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) được tra ngày 15/10/2026: Free 10,000 neurons/ngày, reset 00:00 UTC (07:00 Việt Nam). Qwen3 Embedding 1,075 neurons/M input tokens; GPT-OSS20B 18,182/M input và 27,273/M output. Không đăng ký Paid hoặc AI Gateway credits.

Sizing offline dùng tokenizer `cl100k_base` đã cache, chặn socket; không inference:

- Query embeddings: 2,042–2,268 local tokens, gồm instruction; đầu trên giả định mọi follow-up cần prefix câu cha.
- Evidence tối đa 3,000 tokens/câu và transcript tối đa 2,048 cho mỗi follow-up: tổng 196,384 local tokens. Đây là giới hạn production hiện có, không thay đổi.
- Đếm request scaffold hiện tại bằng `CLOUDFLARE_SYSTEM_PROMPT`, `user_message`, `STRUCTURED_RESULT_SCHEMA`, 5 aliases rỗng và wrapper follow-up: 34,422 local tokens cho 60 serialized request bodies.
- Tổng proxy input 230,806; làm tròn **300,000 input tokens** cho planning (~30% headroom). Dùng output allowance 61,440 và embedding proxy 2,268.
- Quy đổi planning: `0.300×18182 + 0.06144×27273 + 0.002268×1075 ≈ 7,132.7 neurons`; **đề nghị dành khoảng 7,500 Free neurons**, khởi chạy khi còn ít nhất **8,500** để có headroom account chia sẻ.

Đây là proxy dự toán, **không phải hard cap billed tokens/neurons**, invoice hoặc bảo đảm chạy xong trong một ngày. Tokenizer/chat template, JSON escaping/schema và reasoning accounting của provider có thể khác. [Model docs](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/) ghi reasoning mặc định medium; provider adapter hiện không gửi `reasoning_effort`. Giữ request hiện tại, không tự giảm reasoning/config để pass. `max_tokens=1024` là trường giới hạn request; không suy diễn thành 1,024 visible-answer tokens ngoài reasoning.

Số dashboard 96.62/10,000 sau ingestion là bằng chứng lịch sử có thể trễ, không dùng để admission B. Trước B phải kiểm actual account khớp credentials, **Workers Free / Current plan**, eligibility đúng hai models, quota thực trong 15 phút trước startup; phối hợp account window với #158/session khác. Tiếp tục convention sẵn có: lưu raw fractional usage và dùng ceil cho integer preflight, không cần mở rộng validator. Kiểm lại quota sau mỗi nhóm tối đa 12 câu; các nhóm chỉ để vận hành, không thay 5 batch gold đã duyệt.

## 3. Các bước sau khi owner duyệt

1. Phối hợp qua #158 trước khi dùng Docker/DB/ports/account; dùng đúng owned `knora153s1` container/volume, DB `knora153s1_baseline` trên loopback55453 và objects hiện có. Không sửa shared files hoặc tài nguyên session khác khi chưa phối hợp.
2. Đọc lại persisted chunks bằng production reader, tái tạo proposal; phải khớp approved proposal `3796d4228f8bd5d6677b162125c34d551e644fe5488133c31df8b0f306488a9d` và derivation `fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2`. Kiểm corpus/gold approval, baseline config và completed embedding profile. Drift thì dừng, trình lại binding; không re-ingest/đổi parser/fuzzy match.
3. Chuẩn bị launcher tối thiểu, tái sử dụng production HTTP/composition và `PdfHttpExecutor`/`collect_cases`; chỉ chạy conversation worker, không ingestion worker. Kiểm bằng mocked transport trước live: queries-only60, generation60/model/max_tokens, mọi document embedding/judge/endpoint ngoài scope đều bị chặn; counters được persist trước dispatch. Nếu chọn listener8153 phải claim trước và đóng sau; không cần expose public port. Không sửa production algorithm trong bước B.
4. Sau fresh Free/quota admission mới collect tuần tự toàn bộ 60 câu bằng run/case/attempt IDs hiện có, giữ chain câu cha/con. Lưu immutable public response, exact trace/provider metadata, source/chunk provenance và pending dispatch theo runner hiện có.
5. Dùng cùng observations để lập báo cáo local theo mục 5, không gọi lại Q&A cho mỗi tool. Đối chiếu counters, derivation và tài nguyên; trả container về stopped, giữ DB/volume/objects/observations cho review và resume.

## 4. Dừng và resume

Dừng khi 402/403/429, thiếu quota/headroom, preflight hết ngày, request cap, provider/network/parse/persistence/provenance lỗi. Không fallback trả phí, upgrade, đổi threshold/config hoặc retry vòng lặp. Không xử lý tiếp để tạo demo pass.

Sau quota reset, được tiếp tục phần chưa hoàn tất **trong allowance còn lại**, sau fresh Free/quota và coordination. Giữ dữ liệu/config, không chạy lại case thành công. Pending dispatch không có kết quả đã được no-clobber publication chặn replay; phải đối chiếu trace/turn/provider evidence trước khi quyết định retry. Các attempt đã gửi vẫn tính vào cap dù lỗi/quota. Nếu cần vượt cap60/60, hoặc trạng thái gửi không xác định, trình số requests bổ sung cụ thể cho owner duyệt; không mặc định được hưởng cap70 cũ. Nếu không thể hoàn thành bằng Free, báo owner quyết định sau.

## 5. Evaluation đồng hành và boundary #158

Đề nghị cho phép ngay trong B: validation cấu trúc/citations/provenance, báo cáo retrieval/group coverage và các checks deterministic hiện có; chuẩn bị response review cho owner trên cùng captures. Không xem binding coverage là retrieval quality pass. Giữ đủ mẫu số60, báo riêng attempted/observed/error/not-run, missing-required-groups và REFUSAL; quality pass chỉ khi đủ bằng chứng theo #153/#181.

Tái sử dụng canonical per-case run/case/attempt/trace artifacts của runner làm đầu vào #158. #158 quản lý DeepEval/Ragas/judges/Langfuse và correlation/export; thống nhất format/phiên bản tích hợp qua discussion trước khi nối. Không xây framework, gold hoặc nguồn observations thứ hai; không chạy lại answer chỉ để chấm bằng tool khác. Tool chưa thực chạy ghi `not_run`/`unavailable`; không trì hoãn local evaluation để chờ #158. Khuyến nghị lượt này **LLM judge0, Langfuse export off, Ragas sinh gold off**; phần cần model/export được trình riêng sau.

## Quyết định còn mở

❓ **Q1 — Cho phép thực hiện Baseline B theo scope và Free quota plan này?**

➡️ Khuyến nghị duyệt chuẩn bị launcher/mock checks và một lượt 60 câu, queries≤60/generation≤60 bổ sung, không request reserve; chỉ live sau coordination, đọc lại exact approved runtime binding và fresh Workers Free/quota, còn ≥8,500 neurons. Thiếu quota thì dừng/tiếp tục sau reset trong allowance còn lại; vượt request cap phải trình riêng. Paid0USD, PR #189 Draft, chưa merge/deploy/Done.

❓ **Q2 — Phạm vi evaluation trong lượt B?**

➡️ Khuyến nghị duyệt local deterministic report và chuẩn bị human response review từ cùng 60 captures ngay từ đầu; LLM judge0/export off. Chưa tuyên bố semantic acceptance hoặc các tool #158 pass khi chưa chạy. Mọi lượt judge/model bổ sung cần dự toán và approval riêng.
