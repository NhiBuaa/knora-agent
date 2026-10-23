# Evaluation tools acceptance implementation plan

> **For Anti:** thực hiện lần lượt bằng Skill `executing-plans` nếu Skill thực sự có trong phiên;
> đọc nguồn trước khi dùng. Không cài Skill hoặc tạo runner, workflow, dataset store hay state store
> mới. Kế hoạch này tiếp nối #158 sau Workbench #192 / PR #202.

**Goal:** hoàn tất tích hợp và đối chiếu DeepEval, Ragas, Langfuse trên tập đại diện đã chốt để
Owner có thể nghiệm thu #158; chất lượng release đầy đủ của Retrieval V3 vẫn thuộc #153.

**Architecture:** dùng capture, provenance, scorer, admission journal và báo cáo do Knora sở hữu.
Mở rộng có phiên bản các hợp đồng hiện hữu để nhận capture PDF và gói nghiệm thu hữu hạn; không
đi vòng qua Workbench bằng một hệ thống đánh giá khác. Cloud chỉ nhận dữ liệu đúng quyền riêng
của từng đích; Langfuse chỉ nhận metadata đã duyệt và được xóa ngay sau pilot.

**Tech stack:** Python, pytest, PostgreSQL/pgvector, SQLite admission journal; giữ
`deepeval==4.2.8`, `ragas==0.4.3`, `langfuse==4.17.0`; Cloudflare Workers AI và Langfuse Hobby Tokyo.

**Spec:** [ADR 0018](../adr/0018-knora-evaluation-tool-authority.md),
[Workbench design](../design/evaluation-workbench.md), [evaluation guide](../evaluation.md).
Kế hoạch triển khai ban đầu là [evaluation tools](2026-10-14-evaluation-tools.md);
[corpus review fixes](evaluation-corpus-review-fixes.md) giữ lịch sử sửa và tích hợp PR #202.

## 1. Phiên bản, thẩm quyền và điểm xuất phát

Ngày soạn: 2026-10-22. Đây là **bản v1 để Owner duyệt toàn bộ và giao Anti**. Các quyết định
Q1–Q10 dưới đây đã được Owner trả lời trực tiếp trong hội thoại Codex về phần còn lại của #158.
Chúng chưa phải phê duyệt chạy live cho một SHA/envelope cụ thể. Không có URL GitHub hay SHA
phê duyệt kế hoạch mới tại thời điểm soạn; không bịa tham chiếu đó.

- Baseline đọc mã/tài liệu: `dcf15fe1f3b04a5d47b2140b485327f12c965939`.
- Worktree soạn kế hoạch: `<WORKTREE_ROOT>/docs-evaluation-tools-acceptance`, nhánh
  `docs/evaluation-tools-acceptance`. Đây là nhánh tài liệu, không phải đích triển khai tính năng.
- PR #202 đã merge tại `d04b8fa8fe9b193b3533bfde7b4495a34ea2727f`; head được kiểm tra trước
  merge là `cd8a625f593bb222b9497d703752fd5a090868f7`. CI cũ không xác minh code Anti sẽ viết.
- [#192 đã được Owner chấp thuận](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6339856495).
  Không mở lại #192 hoặc sửa PR #202 đã merge để theo dõi phần còn lại.
- [#158 vẫn mở](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6339871916).
  #181 vẫn chờ cả #153 và #158; đóng #158 không đóng thay #153 hoặc #181.
- Worktree cũ `issue-192-evaluation-workbench` / `codex/issue-192-workbench-contract` và stack
  `knora-dev` đang phục vụ kiểm thử thủ công. Không sửa, dừng, dùng DB/volume/cache của chúng.

Sau khi Owner duyệt v1, Anti ghi **đường dẫn kế hoạch, full commit SHA chứa bản được duyệt và
tham chiếu đúng phê duyệt** vào #158/PR mới trong quyền công bố được giao. Nếu duyệt qua chat,
ghi trung thực chat và phiên bản/hash, không tạo URL phê duyệt giả. Mọi delta về phạm vi,
tiêu chí nghiệm thu hoặc ranh giới an toàn cần duyệt riêng; sửa trình bày không đổi nghĩa thì tiếp tục.

### Quyết định đã chốt trong hội thoại

| Quyết định | Nội dung được Owner chọn                                                                                                                                                           |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1         | Nghiệm thu tích hợp trên tập đại diện; toàn bộ chất lượng 16 PDF/60 câu và Retrieval V3 thuộc #153.                                                                                |
| Q2         | Owner review theo gói, trước judge; Anti tự tiếp tục sau phản hồi trong quyền đã có.                                                                                               |
| Q3         | Langfuse pilot metadata, xóa ngay và xác minh qua API; export mặc định OFF.                                                                                                        |
| Q4         | Audit và giữ nguyên lịch sử pilot cũ; loại khỏi bằng chứng tuân thủ/nghiệm thu mới.                                                                                                |
| Q5         | 12 mục: 6 ANSWER thật, 4 synthetic controls, 2 REFUSAL; judge tối đa 10 mục.                                                                                                       |
| Q6         | Nếu không phục hồi được exact evidence: chuẩn bị tối đa 6 PDF thuộc #153, chạy mới đúng 6 câu đã chọn, không retry/chọn lại để lấy đáp án đẹp.                                     |
| Q7         | Gói mới tối đa 139 inference HTTP attempts, USD0, 7 ngày từ dispatch đầu, 8 windows × tối đa 60 phút, 2 stack startups; một lần duyệt gói live cụ thể trước khi chạy.              |
| Q8         | Ngưỡng 0,5 chỉ để đối chiếu pilot; 4 controls phải bị bác ở metric đã chỉ định. Thiếu metric bắt buộc hoặc false acceptance của control thì chưa nghiệm thu.                       |
| Q9         | Tối đa 1 Ragas call sinh tối đa 2 draft tiếng Việt; Owner review phụ lục cùng gói; không Gold promotion/Q&A cho draft. Tiếng Anh kiểm tra offline, NoiseSensitivity ngoài phạm vi. |
| Q10        | 139 = 6 corpus embedding + 12 Q&A (6 query embedding + 6 generation) + 1 Ragas + 120 judge. Tổng embedding có thể là 12.                                                           |

### Hướng dẫn và lịch sử quyết định

> 🧠 **From Hindsight memory (Issue158 incremental DeepEval Ragas Langfuse evaluation)** —
> Knora sở hữu Gold/runs/gates; #153 sở hữu PDF Gold và baseline, #158 bổ sung các công cụ.
> Đã đối chiếu lại bằng ADR 0018 và trạng thái GitHub hiện hành; ghi nhớ cũ không chứng minh
> trạng thái merge hoặc quyền live hiện tại.

Đọc `AGENTS.md`, `CONTEXT.md`, `docs/agents/domain.md`, `docs/agents/issue-tracker.md`,
`docs/standards/architecture.md`, hai Milestone Module Seams, ADR 0018,
`docs/runbooks/ci.md`, `docs/runbooks/agent-environment.md`, `docs/development/feature-map.md`,
`docs/agents/skill-evals.md` và hai verification docs #158/#192 trước khi sửa. Bộ hướng dẫn
`1429d18001b4be17dab9dc108740482ed6efbb65` là mốc lịch sử được yêu cầu đọc; nếu thiếu ở branch,
đọc `git show <SHA>:<path>` hoặc GitHub read-only, không merge/rebase chỉ để lấy hướng dẫn.
Đối chiếu thêm hướng dẫn hiện hành; không hạ chuẩn về bản cũ.

Các con số 24 và 33 requests, hai READY PDFs, 3 startups, windows 15 phút và clocks trong
ADR/approval cũ **vẫn là thẩm quyền của gói cũ**. Chúng không cấp quyền cho v1 này. Task 3 phải
ghi addendum cho hợp đồng mới sau khi v1 được duyệt, giữ nguyên phần lịch sử và các kiểm thử V1.
Không âm thầm thay hằng số cũ rồi dùng lại approval/journal cũ.

## 2. Ranh giới toàn cục và cách tự tiếp tục

- Không thay Gold #153, 60 câu, thresholds, frozen bindings, baseline, lịch sử run hoặc FAILED source.
  Capture mới là run khác; không ghi đè capture cũ hoặc đổi ngữ nghĩa revalidation cùng attempt.
- Không production, deploy, merge, nâng gói trả phí, mở provider/model, Guardrails hoặc NoiseSensitivity.
- Không cài host tools, mở Docker Desktop, sửa quyền Docker/Task Scheduler/Keycloak, đổi credential,
  xóa lock hoặc nhận tài nguyên của người khác để vượt gate. Thiếu quyền thì checkpoint đúng chỗ.
- Không retry model/ingestion/export để tìm kết quả tốt. Error, timeout, truncation hoặc dispatch
  không rõ kết quả vẫn tiêu ngân sách; không refund reservation hoặc chuyển phần dư giữa slot.
- Mỗi invocation có ownership và output riêng; journal của **gói mới** tồn tại xuyên windows.
  Tái sử dụng cơ chế journal hiện hữu, không tái sử dụng dữ liệu journal cũ hoặc tạo journal khác
  để reset ngân sách cùng gói. Không sửa journal bằng SQL ngoài API có kiểm thử.
- Xác minh Skill trong catalog phiên Anti, đọc nguồn rồi áp dụng; dùng
  `verification-before-completion` khi có. Skill ngoài chưa được phép ghi BLOCKED/UNVERIFIED.
  Không coi file trên đĩa, MCP có tên hay self-report là bằng chứng đã kích hoạt/chạy đúng.
- Dùng CodeGraph đúng worktree khi đọc luồng gọi/phạm vi ảnh hưởng: status trước,
  MCP với `projectPath` tuyệt đối; CLI fallback theo AGENTS nếu không có MCP. Không tạo lại DB có lỗi.
- Tra Context7 cho SDK/API/cloud đúng phiên bản; nguồn chính thức là fallback khi thiếu chi tiết.
  Kiểm tra mã cài thực tế trước khi khẳng định request count hoặc schema tương thích.
- Các bước đọc, viết code/test offline, sửa lỗi trong phạm vi, chạy checks và chuẩn bị PR được
  giao trong prompt triển khai thì Anti tự làm liên tục. Không hỏi lại từng gate kỹ thuật đã có quyền.
- Chỉ dừng phần phụ thuộc khi thiếu phê duyệt mới, human review, quyền/ownership, budget/quota,
  drift hoặc an toàn không đạt. Tiếp tục phần độc lập còn hợp lệ; checkpoint không phải PASS.

### Các điểm cần Owner tham gia

1. Duyệt toàn bộ v1 và giao triển khai; cho phép commit/push/PR mới/cập nhật #158 nếu prompt
   bàn giao ghi quyền đó. Lượt soạn plan này không tự công bố hoặc gửi tin nhắn cho Anti.
2. Anti làm xong code, review, CI rồi gom **một gói live cụ thể** gồm SHA, inputs, hai nhánh
   saved/fallback, models, resources và budgets. Chờ Owner duyệt đúng gói trước side effect live.
3. Owner review **một gói 12 mục + phụ lục tối đa 2 Ragas drafts**, sau capture/Ragas nếu cần,
   trước judge. Anti không giữ stack chờ phản hồi. Kết quả judge mới chưa được tạo/tiết lộ trước đó.
4. Owner nghiệm thu tích hợp và quyết định merge/đóng Issue cuối cùng. Không tự ký thay Owner.

Không thể hứa “tự chạy đến nghiệm thu không dừng”: các đánh giá độc lập của Owner và phê duyệt
live cụ thể là gate thật. Đó là các gói cần người quyết định, không phải câu hỏi lặp cho thao tác nhỏ.

## 3. Tập nghiệm thu và hợp đồng dữ liệu

### 3.1 Capture thật, controls và ngữ cảnh

Nguồn ưu tiên: `evals/reports/pdf_retrieval_v3_v1/baseline-b-layout-v2-continuation/` và archive
canonical được README ở đó chỉ định. Baseline có 9 ANSWER/51 REFUSAL, semantic vẫn pending.
Đó là dữ liệu của #153, không phải kết quả tool mới của #158.

Chốt sáu case: **`pdf-v3-004`, `005`, `012`, `014`, `032`, `045`**.
Giữ đủ prefix `pdf-v3-` trong artifact. Tập có VI/EN/mixed, simple, comparison, follow-up,
typo/identifier; không đại diện thống kê hoặc bao phủ toàn bộ 16 PDF/60 câu.

`pdf-v3-032` là follow-up của `pdf-v3-004`: giữ conversation, parent turn, context selection
và trace provenance. Nếu phải capture mới, chạy 004 trước 032 trong cùng context hợp lệ;
không thêm một Q&A ngoài sáu câu để dựng parent và không hỏi 032 như câu độc lập.

Hai REFUSAL controls lấy saved capture: **053** (expected REFUSAL → actual REFUSAL) và **002**
(expected ANSWER → actual REFUSAL). Giữ false refusal của 002; không chấm lời từ chối bằng DeepEval,
không loại khỏi mẫu số. Không có ngân sách Q&A mới cho hai controls này.

Mỗi ANSWER thật phải giữ `run_id`, `case_id`, `attempt_id`, `attempt`, `trace_id`, workspace,
`response_sha256`, dataset/corpus/derivation/binding hashes và selected-attempt identity.
Không hardcode attempt=1, match bằng question/time/latest trace hoặc thay run ID bằng hash report M3.

Exact generation evidence phải là output hợp lệ của `project_generation_evidence`: full content
của selected candidates, aliases liên kết 1:1 và hashes đã đối chiếu với đúng trace/capture.
Candidate pool, citation excerpts và thứ hạng không thay thế alias/evidence thực sự.
Các file đã đọc chưa chứng minh đủ aliases/full evidence cho cả sáu câu. Anti phải phục hồi
archive hợp lệ trước, không suy diễn phần thiếu. Giữ `UNAVAILABLE` của acceptance khi scorer
trả `not_applicable` do thiếu evidence; đây không phải miễn trừ metric bắt buộc trong pilot.

Nếu một trong sáu capture không đạt cổng này và không phục hồi được, dùng nhánh fallback đã duyệt
trong gói live: chạy mới sáu case cố định, không trộn chọn old/new theo điểm đẹp. Tối đa sáu PDF
public/synthetic thuộc corpus #153, raw hashes/locators/binding và danh sách cụ thể được pin trong
gói trước live. Không cần nạp toàn bộ 16 PDF. Corpus thu gọn là **scope pilot khác baseline**;
không tuyên bố tương đương retrieval/baseline B. Nếu không chứa được mọi nguồn/ngữ cảnh cần thiết
trong sáu PDF hoặc request caps thì báo blocker, không cắt bớt Gold/evidence để vừa ngân sách.

Capture fallback phải có actual ANSWER và exact evidence cho cả sáu mới đủ pilot judge. Actual
REFUSAL/error vẫn giữ nguyên; không replay hoặc thay bằng case khác. Phần còn lại chưa nghiệm thu.

### 3.2 Bốn synthetic controls

Tạo offline, deterministic, từ các parent captures đã chọn. Không gọi model để tạo controls.
Mỗi control có `validation_variant_id`, parent capture SHA, transformation version/digest,
answer bytes và metric dự kiến bị bác. Đây là input kiểm tra judge, **không phải output Knora
thật**; không tạo runtime trace giả hoặc nhập Gold/run observations như kết quả ứng dụng.

| Control           | Parent | Phép biến đổi cố định                                                                                                                                                                                 | Metric phải < 0,5 |
| ----------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| wrong-fact        | 004    | Thay đáp án bằng “Cảnh báo P1 phải báo trực trong 150 phút.”                                                                                                                                          | correctness       |
| off-topic         | 005    | Thay đáp án bằng “Màu yêu thích của tôi là xanh dương. Tôi thích thời tiết đẹp.”                                                                                                                      | answer_relevancy  |
| unsupported       | 014    | Thay đáp án bằng “Evidence means approval by the Tokyo office within 3 minutes. Citation means a mandatory payment of 500 USD to that office.”; xác minh các claim này không có trong exact evidence. | faithfulness      |
| missing-exception | 012    | Thay đáp án bằng “Bản nháp thường giữ 30 ngày. Hồ sơ tranh chấp không có quy định riêng.”; bỏ và phủ nhận ngoại lệ 90 ngày.                                                                           | correctness       |

Owner xác nhận lỗi/metric dự kiến trong packet trước khi chấm. Nếu parent evidence thật hỗ trợ
một claim synthetic hoặc control không có ý nghĩa theo nguồn, dừng hoàn thiện packet và xin duyệt
delta cụ thể; không tự chỉnh control sau khi biết điểm. Gói riêng bind cả bốn variant digests;
quyền response-derived của parent không tự cho phép sửa đáp án rồi chấm.

### 3.3 Human review và kết luận judge

- Pin packet digest và shuffle order một lần trước review. Ghi lịch sử exposure nếu Owner đã thấy
  câu/điểm cũ; “chưa thấy điểm judge của đợt mới” không đồng nghĩa blind research hoàn toàn.
- Mỗi mục: identity/hash, question, actual answer/refusal, reference/required facts, exact evidence,
  source anchors và citation verdict theo Knora. Không đưa judge scores/rationale vào bản review.
- Owner ghi reviewer, thời điểm, từng nhãn `accept/reject/unavailable`, lý do, evidence anchor cho
  correctness, answer relevancy, faithfulness; REFUSAL có nhãn decision/reason riêng.
- Giữ review gốc, review bổ sung và adjudication bất đồng riêng, không ghi đè nhãn ban đầu.
- Chỉ sau khi nhận đủ review bắt buộc, Anti mới bind và chạy tối đa 10 judge items. Sáu thật và
  bốn synthetic có ba metric bắt buộc; hai REFUSAL dùng contract deterministic, 0 judge calls.
- Điểm `>=0.5` là “judge nhận” chỉ trong bảng đối chiếu pilot. Không biến success/threshold của
  tool thành gate release Knora; citation/refusal/security tiếp tục theo contract riêng.
- Cả bốn controls phải có metric chỉ định `<0.5`. Metric missing/error/truncated hoặc một control
  được nhận thì pilot chưa đạt; không retune/rerun cùng packet. Chỉ điều tra offline trong quyền
  đã có; chạy một đợt khác cần thiết kế và approval mới, không tái dùng phần dư.
- Sáu câu thật: báo điểm, human labels, confusion matrix, false positive/negative, disagreements
  và rationale cho Owner quyết định. Không đặt thêm tỷ lệ agreement hoặc tự chấm semantic PASS.
- Mỗi metric và mỗi nhóm báo `selected/applicable/scored/unavailable/error/not_run`, công khai `n`.
  Không bỏ missing khỏi bảng, chuyển missing thành điểm 0, trộn controls vào chất lượng ứng dụng
  hoặc tuyên bố calibration/độ cải thiện benchmark từ mười mẫu.

### 3.4 Ragas

Tái sử dụng `generate_review_packet`, đúng `ragas==0.4.3`, `language="vi"`, `count=2`,
`retries_left=0`; tối đa một HTTP call, không repair call. Dùng source chunks public/synthetic
đã pin ở cùng corpus scope, exact quotes/locators và provenance thật, không regenerate 60 câu #153.

Giữ cả số draft thực trả, validation rejects, missing/invalid anchors, duplicate hops và nhận xét
Owner trong phụ lục review chung. Ít hơn hai draft không được ghi thành hai. Draft vẫn pending
review; Owner có thể bác với lý do. Không tự freeze/promote Gold hoặc Q&A trên draft. Nếu không
có draft hợp lệ/đủ bằng chứng multi-hop thì báo chất lượng draft chưa được chứng minh; kết nối
API chạy được không biến nó thành multi-hop PASS. Kiểm thử tiếng Anh offline, không thêm live call.

## 4. Envelope mới và tài nguyên

Đây là **thiết kế đã được chọn**, không là lệnh live đang có hiệu lực. Chỉ concrete approval ở
Task 6 kích hoạt quyền cho đúng build/resources. Gói cũ, L6 cũ, envelope hết hạn/bị thu hồi,
retained L1 hay quota từ ngày khác không được kế thừa.

### 4.1 Inference HTTP attempts

| Operation slots cố định của phiên bản mới |           Số mục |                                           Cap mỗi mục | Tổng cap |
| ----------------------------------------- | ---------------: | ----------------------------------------------------: | -------: |
| Chuẩn bị corpus fallback                  |     Tối đa 6 PDF | Các embedding request digests được pin, tổng tối đa 6 |        6 |
| Q&A fallback                              |   6 case cố định |               1 query embedding + tối đa 1 generation |       12 |
| Ragas VI draft                            |          1 batch |                                                     1 |        1 |
| Judge real                                |       6 captures |                                                    12 |       72 |
| Judge synthetic                           |       4 variants |                                                    12 |       48 |
| REFUSAL deterministic                     | 2 saved captures |                                                     0 |        0 |
| **Tổng**                                  |                  |                                                       |  **139** |

Trần embedding toàn gói là 12: 6 corpus + 6 query. Generation tối đa 6, Ragas 1, judge 120.
Nếu tái sử dụng được sáu captures sạch thì corpus/Q&A slots được đánh dấu SKIPPED trước binding,
không chuyển 18 calls đó sang judge. DeepEval hiện thường dùng 9 calls/item (2 GEval + 3 relevancy

- 4 faithfulness), tức thường 90 cho 10 items; 12 là hard cap, không là quyền retry.

* Models: embedding `@cf/qwen/qwen3-embedding-0.6b` (1024d), generation/Ragas/judge
  `@cf/openai/gpt-oss-20b`, cùng Cloudflare account đã được kiểm tra và duyệt, không provider fallback.
* Q&A generation giữ cap của projection được chọn (baseline B dùng `max_tokens=1024`), không đổi
  retrieval threshold `0.65` hoặc prompt/method để cải thiện điểm. Judge/Ragas output cap tối đa
  2048; query/corpus embedding output cap 0 theo native endpoint. Nếu actual model/prompt cap
  không tương thích thì fail trước dispatch, không tự nâng cap.
* Giữ và kiểm tra input-byte caps của provider contract hiện tại (chat tối đa 8192, embedding
  tối đa 4096), timeout HTTP tối đa 30s, redirects/retries OFF, concurrency=1. Pin exact bytes
  cho corpus/Ragas; Q&A/judge derived requests theo pinned builder/schema và responses hợp lệ.
  Không truncate evidence hoặc chia thêm batch để vượt trần; gói cụ thể phải chứng minh fit offline.
* Paid cost **USD0**, Workers Free bắt buộc. Paid/unknown plan, account mismatch, egress không rõ
  hoặc quota không xác minh được đều chặn. API billing 403 có thể dùng dashboard đúng account;
  bằng chứng quota không tự cấp quyền inference.
* Kiểm tra Free/quota mới cho mỗi admission, tuổi proof/authority tối đa 5 phút, kiểm tra trước
  từng dispatch và sau cửa sổ. Không yêu cầu dành sẵn quota cho toàn bộ 139 calls; chỉ chạy phần
  admission hiện tại có upper bound đủ an toàn. Không đủ cho lượt kế thì checkpoint **trước** lượt đó.
  Tính cả traffic dùng chung/độ trễ dashboard; usage delta không phải invoice hay chi phí riêng run.
* Cap/quota/clock/revocation kiểm tra ở điểm dispatch, không chỉ lúc bắt đầu script.

### 4.2 Clocks, journal và ownership

- Concrete approval pin thời hạn bắt đầu (đề xuất trong 24h từ approval); sau first dispatch,
  hard package deadline là first-dispatch UTC + 7 ngày. Lưu anchor atomically một lần trước
  dispatch; admission pending/crash không được tạo anchor khác. Đồng hồ không reset khi restart.
- Tối đa **8 windows**, mỗi window tối đa **60 phút**, kết thúc trước package deadline; đồng hồ
  bao gồm startup, readiness, execution và cleanup. Không nhận slot mới khi không đủ cleanup time.
- Tối đa **2 local runtime stack startup attempts** của đợt nghiệm thu, bao gồm startup thất bại.
  Có thể chạy judge/Ragas/metadata từ saved inputs không cần stack. CI disposable services có
  counts riêng; không che local startup trong tên “test”. Không giữ stack chờ human review/quota.
- Package/slot/request/window/startup reservations atomic, monotonic, persist qua process restart.
  Window cho CLI khác startup stack; không dùng window thứ ba làm startup thứ ba.
- Nhánh saved/fallback là lựa chọn một lần dựa vào preflight evidence, trước operation binding.
  Chỉ cho các exact case/variant slots đã pin; browser body không mở rộng quyền.
- Cơ chế journal hiện có không phải bảo vệ trước người có quyền sửa filesystem/SQLite trực tiếp.
  Retain original files và per-window hashes/receipts độc lập, so reconciliation sau crash; phát hiện
  rollback/mất lịch sử/identity mismatch thì dừng và báo UNKNOWN, không tự “sửa counters”.
- Mỗi invocation có project/ports/process handles/output riêng. Trước startup kiểm tra Docker
  daemon/permission và ownership. Không tự mở Docker Desktop hoặc chiếm port/tài nguyên khác.
- Reuse launcher/helpers hiện hữu **sau khi đọc source và kiểm tra pins/compatibility**. Không chạy
  script temp cũ có reset SQL. Không dùng synthetic Figma harness làm bằng chứng live model: harness
  đó mặc định deterministic và không worker. Nếu cần wrapper hữu hạn, sửa launcher được sở hữu
  trong repository, có regression; không tạo launcher/harness song song ở Temp.
- Concrete packet phải ghi tên Docker project, port bindings, absolute owned DB/volume/object
  namespace, output/journal, owner, image IDs/digests, worker lifecycle, cleanup/watchdog command.
  Không dùng lại PostgreSQL L1/15492, `knora-dev` hoặc DB checkout khác chỉ vì có credential.
- Kiểm thử watchdog/revoke/cleanup bằng mocks trước. Sau runtime, snapshot jobs/attempts/chunks/
  vectors/provenance/active pointers và Gold/FAILED/history **trước** cleanup; export bằng chứng
  an toàn. Chỉ xóa disposable resources thực sự do invocation tạo, không xóa retained lịch sử.

### 4.3 Langfuse pilot riêng, nằm trong concrete approval cùng gói

Langfuse export không phải Cloudflare inference và không được giả thành một slot inference.
Dùng export approval riêng được Owner duyệt trong cùng packet; export mặc định OFF cả trước/sau.

- Region `https://jp.cloud.langfuse.com`, Hobby Free; kiểm tra project/account, quota, quyền API key,
  org members/invites/roles. Hobby không có project RBAC riêng: không đủ bằng chứng owner-only
  thì dừng, không tự xóa member/tạo org/rotate key. Không dùng khóa production.
- Chỉ opaque project-scoped IDs, allowlisted diagnostics và numeric metadata đã preview. Không
  question/answer/reference/evidence/rationale, PDF title/name, raw errors, credentials, paths,
  email, user identifiers hoặc cloud dataset. Pin actual serialized wire bytes, không chỉ JSON preview.
- Một canary **1 trace + 1 observation**, readback rồi delete+verify trước khi gửi real metadata.
  Sau đó tối đa **2 traces + 2 observations** từ captures đã chọn. Tổng tối đa **3 traces,
  3 observations, 0 scores**; tối đa 6 billable units theo inventory, quota thực kiểm tra lại.
- Tối đa **2 ingestion POSTs + 2 exact-ID batch DELETEs**, 0 write retries, 0 redirects;
  tối đa **120 GETs** cho toàn pilot, concurrency=1, không quá 10 GET/phút, polling cách tối thiểu
  30 giây. Mỗi batch chờ visibility/deletion tối đa 20 phút; toàn pilot tối đa 60 phút và không
  vượt package deadline. Chừa đủ thời gian xóa trước khi export batch real.
- Dùng v4 OTLP endpoint và existing `export_preview`; không thêm decorators/autoinstrumentation.
  Deterministic span ID không chứng minh dedup của OTLP v4. Trước POST, exclusive durable receipt
  reserve approval/project/payload SHA, exact trace/observation IDs và fixed import time. Restart,
  pending hoặc timeout không gửi lại; chỉ GET reconcile rồi xóa đúng IDs đã sở hữu nếu tồn tại.
- Receipts là artifact bằng cơ chế atomic/no-clobber hiện hữu, không thêm DB/state store.
  Ghi receipt hậu kiểm mới, không ghi đè reservation hoặc giả “sent” khi không có acknowledgement.
- GET readback phải đối chiếu trace/observations và raw input/output/metadata thực tế: allowlist,
  IDs, counts và provenance. Không chỉ nhìn UI hoặc preview. Không có score nào được phép tạo.
- DELETE `/api/public/traces` chỉ exact owned trace IDs. Xóa async; HTTP accepted không chứng minh
  đã xóa. Đọc lại traces, paginated v2 observations và v3 scores với fixed time bounds/cursor.
  401/403/timeout/read-window hết hạn không được hiểu là empty. Không delete all project.
- Nếu canary/real/delete/readback lỗi, không export tiếp. Timeout POST/DELETE là uncertain write,
  giữ receipt, không retry. Quyền reconcile/xóa IDs đã sở hữu phải được ghi trong concrete packet,
  kể cả sau khi dừng inference, vẫn trong cleanup deadline. Hết thời hạn còn dữ liệu thì báo
  BLOCKED cleanup với IDs trong private packet; export OFF, không tuyên bố retention PASS.
- Logical API deletion ngay sau pilot đáp ứng target tối đa 7 ngày ở tầng ứng dụng nếu đã xác minh.
  Hobby read window 30 ngày không phải retention; Hobby không tự xóa sau 7 ngày. Không hứa xóa
  vật lý khỏi backup vendor; không thêm cron/cleanup service để giải quyết khác phạm vi.

## 5. Công việc triển khai và kiểm chứng

### Task 1 — Pin nguồn, audit pilot cũ và chọn dữ liệu sạch (0 live calls)

**Đọc/ghi:** hai verification docs #158/#192; artifact audit sanitized tham chiếu từ #158/PR mới.
Không sửa original journal, backups, Gold hoặc lịch sử comments. Kế hoạch này sở hữu bước làm;
Issue/PR sở hữu tiến độ, không thêm session state ledger.

- [ ] Refresh read-only Issue #158/#153/#192, PR #202 và refs. Tạo nhánh
      `feat/evaluation-tools-acceptance` từ main hiện hành trong direct child
      `<WORKTREE_ROOT>/feat-evaluation-tools-acceptance` nếu chưa có đích thuộc nhiệm vụ; không chiếm
      worktree cùng tên của phiên khác. Mang đúng plan revision đã duyệt sang nhánh, không cherry-pick
      thay đổi code cũ đã merge. Kiểm tra top-level/branch/status/worktree list trước mọi edit/commit.
- [ ] Đọc hướng dẫn trong §1 và inventory công cụ/Skills thực tế. CodeGraph status đúng worktree;
      truy vấn nơi dùng `capture_saved_cases`, `score_capture`, `LivePackage`, `export_preview`.
      Báo tool/lệnh đã chạy, projectPath, kết quả và ảnh hưởng; không suy đã dùng từ lịch sử.
- [ ] Read-only audit thư mục cũ
      `<USER_HOME>/AppData/Local/Temp/evaluation-runtime-preparation-b00cf2f5c2/`: hash file gốc,
      journal/backups/receipts và scripts; SQLite `mode=ro` + `PRAGMA query_only=ON`, không execute scripts.
- [ ] Reconcile bốn bản `package/admission.sqlite3{,.bak,.pre_w2_20261021_170226.bak,.pre_w2_20261021_170510.bak}`
      theo tên thực trên disk. Bản đã kiểm tra lần lượt ghi attempts/startups 26/3, 2/3, 6/3, 6/1;
      union có ít nhất **6 startup reservation timestamps** khác nhau dù cap cũ 3. Phân biệt reservation
      với Docker startup thật và counts retained với upper bound network thật. Các script
      `reset_and_clean.py`, `reset_journal_for_ragas.py`, `reset_w2_state.py`, `reset_for_w3.py`
      có thao tác giảm/xóa lịch sử; file tồn tại không tự chứng minh script nào đã được execute.
- [ ] Ghi quan sát, lower bounds và UNKNOWN riêng. Giữ corpus receipt hai succeeded jobs,
      hai attempts, hai vectors 1024d và snapshots Gold nếu có; không xóa thực tế từng xảy ra.
      Tuy nhiên pilot cũ chỉ diagnostic theo Q4: không dùng 26/3, điểm 1.0 hoặc lời handoff làm
      compliance/quality acceptance mới. Không sửa hồi tố “0 calls” của một cửa sổ offline thành tổng lịch sử.
- [ ] Giữ run `faacf17180f24a2bb5ab6c9e36917c6a`: `COMPLETED / SEMANTIC_PENDING`, expected ANSWER
      nhận REFUSAL. Không sửa vì một pipeline mới chạy được.
- [ ] Inventory sáu selected captures và hai refusal captures: exact bytes/SHA, selected attempt,
      archive linkage, aliases/full evidence, public/synthetic egress permission, original-PDF anchors.
      Kết luận saved branch hoặc fallback, không đánh giá theo điểm câu trả lời. Pin nguồn/chunks của Ragas.

**Outcome:** audit có thể reviewer tái hiện, danh sách input cố định và gap/fallback rõ ràng.
**Failure:** dữ liệu nguồn/canonical selection không reconcile được thì chưa bind live; không sửa để PASS.
**Budget:** 0 inference, 0 startups, 0 cloud writes.

### Task 2 — Nối native PDF capture và review packet vào scorer hiện hữu

**Modify:** `evals/scorers/deepeval_cloudflare.py`, `evals/runners/run_deepeval_capture.py`,
`backend/src/knora/evaluation/scoring.py`; chỉ sửa capture persistence trong
`evals/runners/pdf_retrieval_v3.py` nếu cần giữ missing aliases/full evidence cho capture mới.
**Reuse:** `evals/runners/milestone_3.py::project_generation_evidence`, PDF selected-attempt validator,
existing atomic report writer và Ragas review writer. Giữ M3 legacy behavior tương thích.
**Tests:** `evals/test/test_deepeval_capture.py`, `evals/test/test_pdf_retrieval_v3.py`,
`backend/test/evaluation/test_scoring.py`, HTTP scoring test nếu public projection đổi.

**Interfaces:** mở rộng các hàm capture hiện hữu nhận explicit `capture_format="pdf-gold-v1"`
và native identities/selected records, không giả PDF thành M3 report. Các controls đi cùng
validation-origin descriptor pin parent/variant/transformation; scorer vẫn `score_capture` và
supplement là local artifact. Không thêm public endpoint hoặc fake runtime run cho control.

Giữ native `attempt_id` và `attempt` khi chuyển sang preview Langfuse; opaque export IDs là
projection một chiều có provenance, không thay canonical IDs trong local report. Khi thêm trường
vào persisted supplement, giữ consumer cũ đọc được và kiểm thử schema/round-trip.

- [ ] Viết regression trước: native attempt=2 phải giữ nguyên; changed response/capture hash,
      wrong trace/workspace, duplicate selected attempts, raw001 thay reviewed selection, missing
      alias/content, private egress hoặc forged synthetic parent phải bị bác trước mocked HTTP.
      Actual REFUSAL giữ deterministic/not-applicable judge với 0 calls.
- [ ] Regression cụ thể trong `backend/test/evaluation/test_scoring.py`, dùng fixture `saved`
      hiện hữu để bắt hardcoded attempt ngay ở adapter (không gọi model):

  ```python
  def test_saved_capture_preserves_native_attempt(saved):
      from knora.evaluation.scoring import capture_saved_cases

      runs, _, run, owner = saved
      run = deepcopy(run)
      run["observations"]["answer"].update(
          attempt=2, attempt_id="saved-run:answer:2"
      )
      item = capture_saved_cases(runs, run, owner, ("answer",))[0]
      assert item["status"] == "READY"
      assert item["capture"]["attempt"] == 2
      assert item["capture"]["attempt_id"] == "saved-run:answer:2"
  ```

  Baseline hardcode attempt=1 nên test phải RED. Khi thêm full native provenance validation,
  mở rộng fixture bằng metadata hợp lệ rồi thêm negative tests cho metadata bị sửa; không
  bỏ validation để giữ fixture nhỏ. Assert identity=2 xuyên scorer, supplement và Langfuse preview.

- [ ] Chạy đúng tests mới, ghi RED của symptom; nối minimal adapter qua existing validators,
      rồi GREEN. Giữ provenance mọi metric/supplement và counts của unavailable cases.
- [ ] Tạo deterministic control packet đúng §3.2, xác minh parent/input digests và không chạm
      original bytes. Reviewer labels không có default accept hoặc chữ ký tự sinh.
- [ ] Test serializer lồng nhau bằng secret/raw-content sentinels và no-network default import/CLI.
      Actual DeepEval metrics chạy bằng mocked transport đúng version, telemetry/dotenv/key discovery OFF.
- [ ] Chuẩn bị review draft offline, chưa gửi judge; Ragas appendix chưa có generation thì giữ
      `not_run` cho tới Task 7. Không bịa draft hoặc nhãn người để hoàn thiện packet.
- [ ] Commit thay đổi đã kiểm chứng cùng regression; không commit raw captures/private inputs.

**Outcome:** captures/variants qua cùng scorer, identity thật và exact evidence kiểm chứng được.
**Failure:** legacy ID fallback hoặc thiếu evidence bị chấp nhận thì regression chưa khép.
**Budget:** 0 inference/startups, mock calls có inventory riêng.

### Task 3 — Phiên bản mới cho admission/corpus, bảo toàn V1

**Modify:** `backend/src/knora/evaluation/live_admission.py`,
`backend/src/knora/evaluation/corpus_preparation.py`,
`backend/src/knora/adapters/postgres/corpus_preparation.py`, trusted-host composition/callers hiện hữu,
ADR 0018 addendum và evaluation guide. Không mở default live registry.
**Tests:** `backend/test/evaluation/test_live_admission.py`, `test_live_host_composition.py`,
`test_corpus_preparation.py` trong cùng thư mục; PostgreSQL tests/CI partition theo nguồn hiện hành.

**Interfaces:** `LivePackage.initialize`/load/bind/dispatch giữ API hiện hữu, dispatch manifest
theo `manifest_version` rõ ràng. V1 thiếu version vẫn theo contract 33/3 cũ; version mới có exact
finite selection/slots, aggregate139/window8/startup2, first-dispatch anchor và synthetic origin.
Không dùng arbitrary user-supplied list/cap để tạo generic execution engine. Corpus preparation
plan version mới pin 1–6 READY PDFs đã duyệt; V1 vẫn exact2. Không đổi approved plan khi runtime.

Nguồn chọn mới là manifest/Gold #153 đã duyệt và pinned selection của nó. Không import lại
60 câu vào một Gold authority khác chỉ để dựng corpus. Nếu cần representation nội bộ cho plan,
nó là immutable projection có source digest/selection rõ ràng, không có lifecycle freeze/approve
song song; mọi nguồn phải thuộc tập #153 đã pin và workspace disposable được sở hữu.

- [ ] Regression RED cho version2 không được hỗ trợ và giới hạn cần thay; giữ toàn bộ tests V1.
      Table-driven checks: request thứ140, judge item thứ13, startup thứ3, window thứ9, window>60min,
      age proof>5min, deadline+7day, revoked/drift đều bác **trước** side effect.
- [ ] Kiểm thử two-process reservation, pending crash/restart, stopped slot, changed manifest/file
      identity, quota/account/model/input/prompt/schema drift, synthetic parent/variant drift và stop
      giữa response validation/dispatch/activation. Cùng slot đã STARTED không replay để chạy tiếp.
- [ ] Nối corpus version mới vào mọi count check/service/store/fenced activation; không chỉ đổi
      `len(sources)==2` ở một chỗ. One attempt/source, all pins và FK flush order giữ nguyên;
      thất bại không tự requeue qua ordinary worker. Bác FAILED/cross-workspace/extra PDF trước mutation.
- [ ] Build pins bao phủ mọi source runner/scorer/adapter/bridge/launcher/schema mới ảnh hưởng
      admission, bên cạnh full first-party backend pins hiện có; không tái tạo khoảng hở P1 cũ.
      Approval không hợp lệ sau code/dependency change, dù git SHA chưa đổi trong dirty working tree.
- [ ] Không coi SQLite FK test là Postgres locking/runtime. Chọn actual disposable PostgreSQL
      CI partition cho SQL/activation changes, giữ V1 data migration compatibility. Nếu đổi schema DB
      thật thì dùng migration hiện hữu và kiểm tra heads; không tự thêm head không cần thiết.
- [ ] ADR addendum ghi rõ v1 này là gói nghiệm thu mới, scope public/synthetic #153≤6PDF,
      controls riêng và clocks mới; old corpus2/33/3 vẫn lịch sử, không được hồi tố mở quyền.
- [ ] GREEN targeted checks rồi commit. Không initialize live journal hay chạy models ở task này.

**Outcome:** một cơ chế admission có version, immutable finite operation list và counters bền vững.
**Failure:** caller bypass, cap transfer, reset/replay hoặc unpinned runtime source còn tồn tại.
**Budget:** 0 live calls/local runtime startups; CI disposable database được ghi riêng theo run.

### Task 4 — Hoàn thiện Langfuse preview/export/readback/delete hữu hạn

**Modify:** `evals/runners/langfuse_bridge.py`, `evals/test/test_langfuse_bridge.py`,
`docs/evaluation.md`; tái sử dụng atomic/no-clobber output helpers. Không thêm worker/SDK auto tracing.

**Interfaces:** CLI mặc định vẫn local preview, không load Cloud keys; explicit approved export
chỉ nhận pinned preview/capture identity. Thêm thao tác reconcile/readback/delete trong cùng bridge,
scope exact owned IDs và durable artifact receipts; không tạo framework quản lý cloud.

- [ ] Test RED: native attempt/case/trace joins, full serialized wire sentinels, mismatched project/
      JP region/code/payload/approval, expired/revoked authority → 0 network writes.
- [ ] Test concurrent exclusive reservation → đúng 1 POST; restarted/PENDING/timeout → 0 POST mới.
      Pin import time và wire SHA trước reserve, giữ metadata deterministic theo cùng input.
- [ ] Implement bounded API flow trong §4.3 với mocked endpoints: canary precedes real export,
      401/403/429/500/partial success không thành PASS, không hidden retries của SDK/http client.
- [ ] Test paginated observation/score queries, unexpected raw IO/extra IDs, delete accepted nhưng
      data vẫn còn, GET error khác empty, finite GET/time cap, default export OFF sau mọi outcome.
- [ ] Đọc official OpenAPI và SDK 4.17.0 tại lúc implement cho API signatures; dùng raw guarded
      HTTP đang có nếu SDK không đáp ứng retry/digest/timeout contract. Không nâng version cho tiện.
- [ ] GREEN targeted tests, commit. Không tạo project, ingest hay delete cloud trong task này.

**Outcome:** Anti thực thi được pilot/deletion cùng bridge, có readback bằng dữ liệu API thật khi live.
**Failure:** dedup giả định từ spanID, cleanup không phân biệt accepted/completed hoặc payload leak.
**Budget:** 0 cloud writes/inference/startups; mock transport counts không ghi thành runtime.

### Task 5 — Offline verification, review, CI và PR trước live

**Modify:** `docs/development/issue-158-evaluation-verification.md` bằng checkpoint mới;
`docs/evaluation.md` hướng dẫn đã kiểm thử. Chỉ cập nhật #192 verification để sửa/addendum lịch sử
nếu cần; không mở lại phạm vi Workbench đã được chấp thuận. Giữ progress trong #158/PR mới.

- [ ] Re-read final diff vs main, affected callers/config/exports, toàn bộ shared-boundary changes.
      Nhờ review độc lập qua workflow thực có quyền; không coi self-review hoặc CI là human acceptance.
- [ ] Chạy các lệnh bên dưới bằng Python env được cấp, từ đúng worktree. Kiểm tra count/exit/XML;
      ghi RED và GREEN, skips cùng lý do. Không tự cài package/host tools khi thiếu.
- [ ] Nếu chạm frontend, format/format:check và chọn journey Workbench phù hợp từ Feature Map;
      quan sát UI lẫn authoritative backend. Bước backend-only/CLI không ép UI smoke. Không mở in-app
      browser/Edge hay stack chỉ để tạo screenshot không liên quan.
- [ ] Trước push: xác minh path/branch/diff/PR target, bỏ secrets và raw private artifacts khỏi diff.
      Trong quyền prompt bàn giao, push nhánh mới và tạo PR vào `main`, body theo template, không
      `Closes #158` trước nghiệm thu. Attach PR bằng công cụ app nếu có; đọc lại Issue/PR sau cập nhật.
- [ ] Đợi CI required trên **đúng final SHA**, và các workflow liên quan thực sự chạy. Ghi run URLs,
      job counts, result; Security Shadow không thay CI required. Mỗi edit mới cần evidence phù hợp mới.
      Không dùng runs của PR #202 để chứng minh PR mới. Không tự merge/rebase để xử lý drift chưa rõ.
- [ ] Chuẩn bị gói live ở Task 6 sau khi review/blocking findings và required CI đã khép.

```powershell
Set-Location '<WORKTREE>'
& '<PYTHON_ENV>/Scripts/python.exe' -B -m pytest backend/test/evaluation evals/test/test_deepeval_capture.py evals/test/test_pdf_retrieval_v3.py evals/test/test_ragas_review.py evals/test/test_langfuse_bridge.py backend/test/adapters/http/test_http_evaluation_scoring.py -q -p no:cacheprovider -p no:deepeval --basetemp '<OUTPUT>/pytest' --junitxml '<OUTPUT>/suite.xml'
& '<PYTHON_ENV>/Scripts/python.exe' -m ruff format .
& '<PYTHON_ENV>/Scripts/python.exe' -m ruff format --check .
& '<PYTHON_ENV>/Scripts/python.exe' -m ruff check .
& '<PYTHON_ENV>/Scripts/python.exe' scripts/export_openapi.py --check
git diff --check
```

`<OUTPUT>` phải mới cho invocation; chọn thêm actual PostgreSQL partition từ `.github/workflows/`
và CI runbook cho thay đổi service/store, không chạy command đoán vào DB sống. Nếu sửa maintained
shared files thì chạy `npm --prefix frontend run format:shared` và `format:shared:check`; nếu sửa
frontend thì `format` và `format:check` theo AGENTS. Chỉ regenerate OpenAPI bằng exporter nếu
contract thực sự đổi; không sửa generated TypeScript bằng tay.

**Outcome:** PR reviewable, code checks và exact-SHA CI có bằng chứng; runtime/AI quality vẫn pending.
**Budget:** 0 live inference/cloud writes. Mọi local runtime startup khác cần scope/authority riêng
và báo counts; không giấu trong offline claim. Tests dùng disposable data theo workflow hiện hữu.

### Task 6 — Một concrete approval packet, preflight rồi mới dispatch

**Output:** artifact private ở output riêng và bản sanitized link trong #158/PR. Không thêm state store.

- [ ] Packet pin plan revision/approval, final code full SHA + clean content/dependency digests,
      reviewed source/response builder/schema pins, CI/review refs và người sở hữu executor.
- [ ] Pin exact case IDs, selected capture/attempt/trace/response hashes, dataset/corpus/derivation,
      aliases/evidence export digests; bốn control answer bytes/digests và target metrics; source
      chunks/digests/request của Ragas. Pin fallback PDF list≤6, chunks, embedding batches/request
      digests và jobs/activation plan nếu cần. Chứng minh ≤6 corpus HTTP attempts, không cứ mỗi PDF
      mặc định một call. Không thêm batch nếu actual chunks vượt caps.
- [ ] Packet chứa reviewed request derivation cho Q&A/judge, token/input/time caps, per-slot139
      allocation và deterministic no-transfer/skip rules. Bind response-dependent prompts khi có
      validated responses theo đúng case; mock request hashes không thể cấp quyền real prompts.
- [ ] Packet ghi ownership resources/ports/commands/worker/DB/volume/output/journal, fresh Free
      account/quota proof và USD0 guarantee, start-by/7day/window8/startup2 clocks; cleanup/watchdog
      trước deadline và quyền đọc/xóa **chỉ** tài nguyên sở hữu khi run dừng.
- [ ] Langfuse cùng packet: Hobby JP owner-only/quota proof, exact project/key fingerprint,
      metadata allowlist/wire digest/canary+real IDs (hoặc deterministic derivation từ capture mới),
      2 POST/2 DELETE/120 GET/60min caps và deletion/readback authority. Chưa có credentials thì
      không xin token qua chat, không bật export; chỉ báo missing config theo tên biến.
- [ ] Trình Owner duyệt **đúng packet/hash/SHA** một lần. Phê duyệt thiết kế Q1–Q10 hoặc lời
      handoff không thay thế bước này. Nếu thiếu approval thì chỉ làm offline độc lập.
- [ ] Ngay trước operation, revalidate tất cả gates và publish expected outcome/check/failure/
      current consumed/remaining budget. Không xin lại approval cho thao tác nhỏ vẫn đúng packet.

**Outcome:** một envelope mới có provenance và quyền thực tế; hoặc blocker cụ thể trước side effect.
**Failure:** Docker/permission/quota/ownership/drift/expiry/revocation không đạt → 0 dispatch tiếp theo,
ghi actual calls/jobs/startups thay vì mặc định0 nếu đã tiêu trước đó.

### Task 7 — Chạy capture/Ragas, review theo gói, judge, metadata và cleanup

Đây là chuỗi phụ thuộc; không chạy tất cả trong một window giữ stack chờ người.

- [ ] Nếu saved branch đủ: không corpus/Q&A; preserve selection và skip slots đúng journal.
      Nếu fallback: một owned runtime window chuẩn bị≤6 PDF, one attempt/source; chạy đúng sáu
      case, 004 trước032 có conversation context. Capture full trace/evidence ngay; failure/refusal
      giữ nguyên và dừng phần phụ thuộc. Không thêm case/retry/parent Q&A ngoài selection.
- [ ] Snapshot trước/sau: jobs/attempt IDs và statuses/counts, chunks/vectors dimensions và content
      provenance, active pointers, source statuses, hashes/revisions Gold/threshold/history; giữ
      FAILED và mọi resource khác không đổi. Mỗi PDF activation qua fenced adapter đã kiểm chứng.
      Local fixture PASS không thay dữ liệu Postgres runtime. Nếu không có corpus mutation thì ghi
      `not exercised` cho corpus runtime mới, không copy receipt cũ vào cột runtime mới.
- [ ] Chạy Ragas một call nếu đúng scope/gates, lưu packet và validation results, không Q&A/promote.
      Đóng stack và xác minh owned cleanup, giữ artifact an toàn. Nếu human packet chưa đủ thì
      không chấm judge; gửi một gói review theo §3, chờ Owner thực sự trả nhãn.
- [ ] Nhận review, pin digest/thời điểm và completeness; Anti tự resume các bước được duyệt.
      Nếu chờ quá deadline thì expired, không tự gia hạn 7 ngày. Không forge labels/adjudication.
- [ ] Mở window CLI từ saved captures, fresh quota/admission. Chạy từng judge item tuần tự,
      ≤12 calls/item, ≤120 tổng; ghi reservations, dispatch/response/provenance và actual counts.
      Quota hết thì checkpoint trước lượt kế. Một item đã bắt đầu rồi dừng/error không replay hoặc
      chấm lại bằng ledger mới; báo incomplete và xin gói mới nếu thật sự cần tiếp đợt khác.
- [ ] Lập comparison theo §3.3, giữ các disagreement. Controls không đạt hoặc thiếu metric thì
      chưa nghiệm thu; real answer quality giữ kết luận người review, không pipeline-derived PASS.
- [ ] Chạy Langfuse canary/readback/delete-verify rồi tối đa hai metadata traces thật. Exact wire
      allowlist, observations/scores readback, deletion proof; thiếu owner-only/permission/quota thì
      dừng trước POST và vẫn ghi Langfuse BLOCKED, không đổi plan/cloud provider để né gate.
- [ ] Mỗi window kết thúc: journal/counters/status reconciliation, quota/cost observation, artifact
      hashes, resource/listener/process cleanup của invocation; xác minh foreign resource identities
      không đổi. Package deadline dừng dispatch và mutation; cleanup theo quyền/clock đã pin.

**Outcome:** runtime evidence mới ràng buộc với exact code/inputs/permissions; kết quả có thể là
đạt, không đạt hoặc blocked. Không làm “đẹp” lịch sử khi ứng dụng/judge thất bại.
**Budget:** tối đa §4; báo model requests riêng cloud metadata requests và local jobs/startups.

### Task 8 — Closeout, PR ready và nghiệm thu #158

- [ ] Nộp Owner bảng acceptance trong §6 cùng comparison, Ragas review, Langfuse deletion proof,
      audit correction và no-secret artifacts. Code/runtime findings sửa offline trong phạm vi,
      chạy lại affected checks/CI đúng SHA; code edit làm invalid live pins thì không gán runtime cũ
      cho SHA mới. Không re-run model theo mặc định để lấp khoảng này.
- [ ] Cập nhật verification doc theo checkpoint mới, Issue #158 và PR mới bằng liên kết, không
      chép nguyên plan/logs. Sau commit evidence-only, phân biệt runtime tested-code SHA với evidence
      commit SHA; chứng minh executable source không đổi, và required CI trên PR head mới.
- [ ] Reviewer đọc whole PR diff, compatibility V1/new native inputs, security/egress/budget/
      cleanup/rollback limits và disagreements. PR ready khi code+CI+review đạt; nếu runtime hoặc
      owner acceptance thiếu thì ghi rõ, không dùng auto-close keyword cho #158.
- [ ] Owner quyết định chấp thuận tích hợp representative set và merge. **Không tự merge hoặc
      đóng #158**; chỉ cập nhật trạng thái theo lời Owner và quyền được giao. #153/#181 vẫn đúng scope.
- [ ] Selective closeout: chỉ sửa nguồn canonical khi có finding kiểm chứng được. Báo ngắn bốn mặt:
      hướng dẫn/Skills/tool thực dùng; outcome task; compliance và evidence; calls/time/work tránh được.
      Dẫn records để reviewer đối chiếu; không tự chấm thay reviewer hoặc tuyên bố baseline improvement.

## 6. Checklist nghiệm thu và cách báo trạng thái

| Mặt                                 | Điều kiện / bằng chứng bắt buộc                                                                                                                                                                                                                           |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Đã triển khai (Implemented)         | Diff mới reuse existing seams, native identity/evidence, versioned admission, Ragas packet và guarded Langfuse lifecycle; review không còn blocker.                                                                                                       |
| Đã kiểm tra cục bộ (Local Verified) | Commands/exit/counts/RED→GREEN trên final code; failure/concurrency/privacy/compatibility assertions cụ thể. SQLite chỉ có phạm vi SQLite.                                                                                                                |
| CI đã xác minh (CI Verified)        | Required CI đúng PR head, actual PostgreSQL partition cho thay đổi persistence/activation; URLs/jobs/results, không dùng CI #202.                                                                                                                         |
| Chạy thực tế (Runtime Verified)     | Concrete approval + fresh gates + execution IDs/journal/receipts mới; Postgres snapshots nếu exercised; model responses/provenance/counters; owned cleanup.                                                                                               |
| AI quality                          | 6 real captures + 4 labeled controls có metric đầy đủ; controls đạt criterion Q8; 2 deterministic refusal checks giữ false refusal; human comparison/disagreements, Ragas review. Owner chấp thuận phạm vi tích hợp; không đại diện #153 release quality. |
| Cloud data policy                   | Owner-only/Hobby/JP verified; raw IO absent; canary/real limits; exact-ID deletion, traces/observations/scores API readback empty đúng scope; không claim backup purge.                                                                                   |
| Tuân thủ lịch sử                    | Audit correction giữ originals; old pilot diagnostic-only; no rollback/reset/replay, no historical semantic rewrite.                                                                                                                                      |
| Reviewed / Merged / Deployed        | Báo từng trạng thái thật. Ready/green không là merge; merge do Owner, deployment ngoài phạm vi.                                                                                                                                                           |

Đóng #158 chỉ khi Owner chấp thuận tích hợp và dữ liệu/thẩm quyền/cleanup bắt buộc đã đủ.
Control không đạt, thiếu exact evidence, quota/permission thiếu hoặc deletion pending là blocker
cụ thể, không đổi thành “đã hoàn tất, còn vài hạn chế”. Đề xuất bước tiếp theo với đúng quyền cần
bổ sung và phần đã tiêu, không hứa một vòng chạy nào chắc chắn PASS.

### Receipt tối thiểu mỗi checkpoint

```text
Subject: task + full code SHA + plan revision + input/manifest hashes
Authority: approval reference, account/resource fingerprints, clocks, scope
Observed: commands; exit; selected/executed/passed/failed/skipped counts; IDs
Budget: reserved/dispatched/confirmed/uncertain model attempts by slot;
        corpus jobs/attempts/activations; window/startup counts;
        Langfuse POST/DELETE/GET and object counts; remaining caps
Safety: Gold/FAILED/history before-after, quota/cost proof, owned cleanup
Conclusion: Implemented / Local / CI / Runtime / AI quality + specific gaps
Next: exact resumable unstarted step, or blocking decision/permission
```

Sanitize công bố: `[REDACTED]`, `<USER_HOME>`, `<WORKTREE>`, `<PYTHON_ENV>`, `<OUTPUT>`.
Giữ nguyên executable/subcommands/flags/quoting; không đưa `.env`, token/password/cookies,
auth URLs, account IDs hay đường dẫn cá nhân vào Issue/PR/log public. Private evidence giữ quyền
truy cập thích hợp, public receipt chỉ chứa fingerprints/hashes và liên kết an toàn.

## 7. Nguồn nghiên cứu và giới hạn

Đã đọc mã repo và API cài thực tế ở phiên nghiên cứu; Anti phải kiểm tra lại dependency/build
đúng SHA trước triển khai. Công cụ CodeGraph MCP `codegraph_explore` đã dùng đúng projectPath
`<WORKTREE_ROOT>/issue-192-evaluation-workbench` cho `derive_captures`, `score_capture`,
`validate_free_preflight`, `ScoringPlan` và `EvaluationScoringService`. Nó chỉ hỗ trợ khám phá mã,
không chứng minh runtime và không là bản đồ cho worktree mới. Không khẳng định lịch sử trước đó.

- DeepEval đúng tag 4.2.8: [GEval](https://github.com/confident-ai/deepeval/blob/python-v4.2.8/deepeval/metrics/g_eval/g_eval.py),
  [relevancy](https://github.com/confident-ai/deepeval/blob/python-v4.2.8/deepeval/metrics/answer_relevancy/answer_relevancy.py),
  [faithfulness](https://github.com/confident-ai/deepeval/blob/python-v4.2.8/deepeval/metrics/faithfulness/faithfulness.py).
  Request inventory 2+3+4 áp dụng method hiện tại, không đảm bảo mọi malformed response vẫn hoàn tất.
- Đối chiếu người–judge và false acceptance: [DeepEval official](https://deepeval.com/blog/llm-as-a-judge),
  [G-Eval paper](https://arxiv.org/abs/2303.16634). Tập nhỏ không chứng minh hiệu chỉnh toàn benchmark.
- [Ragas NoiseSensitivity](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/noise_sensitivity/)
  cần input riêng và không thay recall/citation/refusal; đã chủ động để ngoài phạm vi mới.
- Langfuse: [pricing](https://langfuse.com/pricing),
  [billable units](https://langfuse.com/docs/administration/billable-units),
  [retention](https://langfuse.com/docs/administration/data-retention),
  [RBAC](https://langfuse.com/docs/administration/rbac),
  [OTLP v4](https://langfuse.com/integrations/native/opentelemetry/migration-to-v4),
  [deletion](https://langfuse.com/docs/administration/data-deletion),
  [API limits](https://langfuse.com/faq/all/api-limits),
  [public API](https://langfuse.com/docs/api-and-data-platform/features/public-api),
  [OpenAPI](https://cloud.langfuse.com/generated/api/openapi.yml).
  API/service policy có thể đổi; refresh qua Context7/official sources trước concrete approval.

Nghiên cứu/soạn plan không chạy lại model, không startup stack, không sửa DB hoặc Langfuse:
**0 live inference, 0 jobs/activations, 0 runtime startups, 0 cloud writes trong lượt này**.
Các kết quả runtime lịch sử được nêu ở Task 1 là đối tượng audit, không là hoạt động mới của lượt soạn.
