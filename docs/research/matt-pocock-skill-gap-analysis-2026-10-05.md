# Những skill Matt Pocock còn thiếu và giá trị cho KnoraAgent / KittaChat

Ngày khảo sát: **05/10/2026**, múi giờ Asia/Saigon. Đây là khảo sát và đề xuất; chưa cài hoặc kích hoạt skill mới.

**Cập nhật sau khảo sát — 05/10/2026:** Theo yêu cầu của người dùng, hướng dẫn đang dùng của
KnoraAgent và KittaChat đã chuyển sang nguồn skill `C:/Users/NhiBuaa/.codex/skills`.
Các mục lựa chọn workflow, domain guide và runbook M5 đã được cập nhật để tham chiếu skill
hiện có. Những chênh lệch mô tả dưới đây là bằng chứng tại thời điểm khảo sát trước thay đổi,
không phải yêu cầu tiếp tục sử dụng bộ skill cũ. Các ứng viên upstream vẫn là đề xuất chưa cài.

## Kết luận

Có những **nhiệm vụ chuyên biệt chưa có skill tương đương trong bộ đang được cung cấp cho phiên này**. Bốn ứng viên hỗ trợ phát triển đáng xem xét nhất là **retro**, **triage**, **wayfinder** và **to-questionnaire**. `writing-for-agents` là phần hỗ trợ đáng cân nhắc cùng `retro`; `teach` hữu ích cho học và chuẩn bị phỏng vấn. Đây là đánh giá độ phù hợp từ nội dung skill và bối cảnh dự án, chưa phải kết quả đo hiệu quả sử dụng.

Không nên cài nguyên bộ hoặc thay các workflow có quản trị bằng bản upstream chỉ vì cùng tên. Một số năng lực đã có ở Superpowers; một số đã được ghi trong quy định repo nhưng nguồn skill hiện không còn ở đường dẫn quy định.

## Phạm vi và bằng chứng

- Nguồn upstream: [mattpocock/skills, commit 24fe0ef](https://github.com/mattpocock/skills/tree/24fe0ef7737efae15c87225755e9f6f5965e4888). GitHub API trả SHA đầy đủ `24fe0ef7737efae15c87225755e9f6f5965e4888`; ngày commit `2026-10-04T12:48:05Z`. Khảo sát **37 file SKILL.md**: 20 engineering, 7 productivity, 4 misc, 6 in-progress. Các liên kết trong báo cáo cố định ở commit này; thư mục `in-progress` được coi là tín hiệu cần thận trọng, không phải chứng nhận chất lượng.
- Trên máy: **16 skill người dùng** ở [C:/Users/NhiBuaa/.codex/skills](C:/Users/NhiBuaa/.codex/skills) và **5 skill hệ thống trên đĩa** dưới `.system`. `review-agent` có file nhưng không nằm trong danh sách skill được cung cấp cho phiên hiện tại. Bốn skill hệ thống còn lại có trong danh sách đó.
- **C:/Users/NhiBuaa/.agents/skills không tồn tại** tại thời điểm kiểm tra. Không tính những tên từng xuất hiện trong lịch sử chat là skill đang cài.
- Bộ được cung cấp cho phiên còn có plugin về Figma, tài liệu, bảng tính, trình chiếu, hình ảnh, visualization, Sites, computer use và Google Drive. Chúng giúp làm artifact hoặc thao tác ứng dụng; không tương đương lifecycle triage, retrospective môi trường agent hay bản đồ quyết định dài hạn. So sánh plugin dựa trên catalog của phiên, không quét toàn bộ cache plugin và không coi mọi thư mục cache là skill đang hoạt động.
- Nguồn local đã đọc: [Knora AGENTS.md](C:/Developer/Projects/knora-agent/AGENTS.md), [CONTEXT.md](C:/Developer/Projects/knora-agent/CONTEXT.md), [domain guide](C:/Developer/Projects/knora-agent/docs/agents/domain.md), [tracker guide](C:/Developer/Projects/knora-agent/docs/agents/issue-tracker.md), [Architecture Standard](C:/Developer/Projects/knora-agent/docs/standards/architecture.md), hai tài liệu module seams; [Kitta working agreement](C:/Developer/Projects/kitta-chat/.agents/AGENTS.md), [Kitta CONTEXT](C:/Developer/Projects/kitta-chat/.agents/CONTEXT.md), [README](C:/Developer/Projects/kitta-chat/README.md), tracker/triage docs và package scripts.

“Thiếu” ở đây nghĩa là thiếu quy trình chuyên biệt, không có nghĩa agent hoàn toàn không làm được nhiệm vụ đó. “Đã ghi trong repo” cũng không chứng minh skill tương ứng đang được cung cấp và cho phép chạy.

## Vấn đề cần đối chiếu trước khi bổ sung

**Knora:** AGENTS.md vẫn liệt kê `feature-delivery`, `domain-modeling`, `manual-acceptance`, `implement`, `code-review`, `session-continuity` và các workflow khác. Những tên này không có trong 16 thư mục skill người dùng vừa kiểm tra. Tuy nhiên [runbook M5](C:/Developer/Projects/knora-agent/.agents/workflows/m5-codex-skills-workflow.md) chủ đích dùng 13 skill dưới `.codex/skills` và cấm `feature-delivery`. Vì vậy đây là chênh lệch giữa nguồn workflow và phạm vi được phép dùng, cần xác định theo từng nhiệm vụ; chưa đủ bằng chứng kết luận tất cả tham chiếu cũ đều bị xóa nhầm.

**KittaChat:** [working agreement](C:/Developer/Projects/kitta-chat/.agents/AGENTS.md) chọn `~/.agents/skills` làm nguồn chính và nêu nhiều tên không còn tìm thấy ở đó: `triage`, `teach`, `to-prd`, `to-issues`, `test-craft`... Trong khi [triage-labels.md](C:/Developer/Projects/kitta-chat/docs/agents/triage-labels.md) đã có bảng năm trạng thái. Đó là cấu hình sẵn và tham chiếu workflow, không phải bằng chứng skill được cài.

Upstream hiện dùng `GLOSSARY.md`/`GLOSSARY-MAP.md`; Knora dùng `CONTEXT.md`, Kitta dùng `.agents/CONTEXT.md`. Khi đưa skill upstream vào phải nối lại đường dẫn domain, giữ ADR và luật repo. Không tạo glossary thứ hai hoặc đồng nhất `to-spec` với `to-prd`, `to-tickets` với `to-issues`, hay `implement-spec` với `feature-delivery` chỉ bằng tên gần giống.

## Bốn ứng viên chính

| Ưu tiên | Skill / nhiệm vụ bổ sung | KnoraAgent | KittaChat | Mức trùng và điều kiện |
| --- | --- | --- | --- | --- |
| 1 | **retro**: nhìn lại một phiên coding để cải thiện môi trường agent | Tìm vì sao đọc sai invariant, mất thời gian tìm seam, hoặc lặp lỗi kiểm chứng/evaluation | Phân tích các phiên migration, xử lý race condition, benchmark K4; tìm guardrail còn thiếu | Khác code review và debug: đầu ra là đề xuất cải thiện cách làm các phiên sau. Phụ thuộc `writing-for-agents`. |
| 2 | **triage**: xử lý báo lỗi/feature request đầu vào thành brief có thể giao | Làm rõ vấn đề ingestion, retrieval, auth trước khi giao implementation | Phân loại lỗi reconnect, unread, call lifecycle từ tester | Repo Kitta đã mô tả nhiệm vụ nhưng nguồn skill không còn; là khôi phục khả năng dùng hơn là ý tưởng mới hoàn toàn. Cần tracker, mapping labels, quyền comment/đóng issue. |
| 3 | **wayfinder**: bản đồ quyết định cho việc còn nhiều điều chưa rõ, vượt một phiên | Điều tra một tích hợp Knora–Kitta hoặc thay đổi kiến trúc lớn trước khi viết spec | Chia những quyết định migration/scaling còn mơ hồ thành câu hỏi có phụ thuộc | Trùng một phần brainstorming/planning; khác ở canonical map và decision tickets trên tracker. Chỉ dùng cho việc đủ lớn. |
| 4 | **to-questionnaire**: viết bảng câu hỏi cho người khác trả lời bất đồng bộ | Hỏi người giữ tri thức về nguồn tài liệu, quyền truy cập, tiêu chí answer/refusal | Hỏi tester/người dùng về reconnect, thông báo, trải nghiệm call | Khác brainstorming trực tiếp: người giữ thông tin không ở trong cuộc chat. Có ích khi có stakeholder thật. |

Nguồn cho nhiệm vụ từng hàng: [retro](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/retro/SKILL.md), [triage](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/triage/SKILL.md), [wayfinder](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wayfinder/SKILL.md), [to-questionnaire](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/to-questionnaire/SKILL.md). Các ví dụ cho hai dự án là đề xuất của người nghiên cứu dựa trên tài liệu local, không phải tính năng skill đã thực hiện.

### Phụ thuộc và tác động cụ thể

- **retro**: đọc nguồn của phiên và lệnh kiểm tra đang có, rồi trình bày ứng viên cải thiện theo mức độ. Cần giữ phân biệt đề xuất với thực thi thay đổi. Không tự chạy cơ chế truy cập session log không có trong môi trường. [Nguồn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/retro/SKILL.md).
- **triage**: gọi `grilling`, `domain-modeling` khi cần; dùng tài liệu brief/out-of-scope đi kèm. Có thể comment, đổi labels, đóng issue và viết `.out-of-scope/`. Knora không coi PR là đầu vào yêu cầu và chỉ cho `ready-for-agent` sau khi nghĩa triage được duyệt; Kitta đã có mapping năm trạng thái. Không tự áp dụng nguyên trạng upstream. [Nguồn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/triage/SKILL.md), [Knora tracker](C:/Developer/Projects/knora-agent/docs/agents/issue-tracker.md), [Kitta labels](C:/Developer/Projects/kitta-chat/docs/agents/triage-labels.md).
- **wayfinder**: phụ thuộc `grilling`, `domain-modeling`, `research`, `prototype` và tracker có “Wayfinding operations”. Tạo/assign/đóng issue, gắn dependency, có nhánh research; mỗi phiên thường giải quyết một ticket. Knora tracker hiện chưa có mục operations đó. Cần cấu hình và cho phép rõ trước khi chạy; giữ worktree đúng container và quyền Git của từng repo. [Nguồn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wayfinder/SKILL.md).
- **to-questionnaire**: hỏi người dùng ai nhận và cần biết gì, sau đó tạo Markdown. Không có bước tự gửi cho người khác; việc gửi vẫn cần yêu cầu riêng. [Nguồn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/to-questionnaire/SKILL.md).

## Những phần hữu ích nhưng trùng một phần hoặc có điều kiện

| Skill | Phần thực sự thêm | Điều kiện và đánh giá |
| --- | --- | --- |
| **writing-for-agents** | Thiết kế context pointers, tổ chức tài liệu agent và tiêu chí kết thúc bước | Trùng `writing-skills` và `skill-creator`; phạm vi rộng hơn skill authoring. Đáng xem cùng retro; phải lấy cả `SKILL-MECHANICS.md`. |
| **teach** | Workspace học nhiều phiên có mission, records, lessons và reference | Visualization đã có nhưng chưa có tiến trình học bền vững tương đương. Hợp học RAG/evaluation hoặc giải thích distributed chat để phỏng vấn. Nên dùng thư mục học riêng, tránh tạo file khóa học ở root ứng dụng. |
| **wizard** | Script tương tác hướng dẫn các thao tác chỉ con người làm được | Hợp cấu hình provider/S3/CI secrets. Dùng bash, template và `gh`; PowerShell hiện tại cần Git Bash/WSL hoặc adaptation. Có ghi `.env`/GitHub secrets nên phải tuân thủ luật secrets và xác nhận. Không chạy end-to-end thay người dùng. |
| **prototype** | Code bỏ đi để trả lời câu hỏi logic/state hoặc nhiều biến thể UI | Trùng spike của brainstorming và visualization; khác ở workflow lưu nguồn prototype. Có bước commit nhánh riêng và cập nhật issue, cần quyền Git; không đưa prototype vào production hoặc bỏ qua acceptance. |
| **setup-pre-commit** | Chuẩn hóa Husky + lint-staged + Prettier trước commit | Các dự án đã có CI/scripts nên không phải thiếu toàn bộ quality gate. Thêm dependency, `prepare`, hooks; upstream có bước stage tất cả rồi commit. Phải thay bằng phạm vi file đã duyệt và quyền commit hiện có. Không thay CI bằng hook local. |
| **setup-ts-deep-modules** | Enforcement import boundary qua dependency-cruiser | Khác thiết kế bằng lời, nhưng ở `in-progress` và mặc định `src/packages`. Knora frontend dùng TS; Kitta hiện JS/JSX. Không ép layout hoặc mở migration ngôn ngữ chỉ để dùng skill này. |
| **migrate-to-shoehorn** | Chuyển assertion trong test TypeScript sang helper chuyên dụng | Chỉ hữu ích nếu có vấn đề fixture/`as` cụ thể. Không dùng production và không có lý do áp dụng vào Kitta JS hiện tại. |

Nguồn: [writing-for-agents](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/writing-for-agents/SKILL.md), [teach](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/teach/SKILL.md), [wizard](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wizard/SKILL.md), [prototype](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/prototype/SKILL.md), [pre-commit](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/misc/setup-pre-commit/SKILL.md), [TS boundaries](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/setup-ts-deep-modules/SKILL.md), [shoehorn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/misc/migrate-to-shoehorn/SKILL.md). Bằng chứng stack: [Knora frontend package](C:/Developer/Projects/knora-agent/frontend/package.json), [Kitta client package](C:/Developer/Projects/kitta-chat/client/package.json).

## Những năng lực không phải khoảng trống mới

- TDD, chẩn đoán bug, lập kế hoạch, triển khai theo task, dispatch agent và code review đã có các skill Superpowers tương ứng. Upstream có khác quy trình, nhưng không nên đánh dấu toàn bộ nhiệm vụ là chưa có. [test-driven-development](C:/Users/NhiBuaa/.codex/skills/test-driven-development/SKILL.md), [systematic-debugging](C:/Users/NhiBuaa/.codex/skills/systematic-debugging/SKILL.md), [writing-plans](C:/Users/NhiBuaa/.codex/skills/writing-plans/SKILL.md), [requesting-code-review](C:/Users/NhiBuaa/.codex/skills/requesting-code-review/SKILL.md), [subagent-driven-development](C:/Users/NhiBuaa/.codex/skills/subagent-driven-development/SKILL.md).
- `research` đã cài và được cung cấp. [Skill local](C:/Users/NhiBuaa/.codex/skills/research/SKILL.md).
- Domain modeling, architecture seams, handoff và ticket decomposition đã là các nhiệm vụ trong quy định repo. Thiếu file skill hiện tại cần xem xét khôi phục/adapt nguồn chính xác, không gọi đó là chưa từng có quy trình.

## Thứ tự đề xuất

1. **Đối chiếu nguồn workflow đang dùng của từng repo** và các tham chiếu thiếu; giữ runbook M5 khi nhiệm vụ thuộc M5. Đây là đề xuất công việc tiếp theo, báo cáo chưa sửa guidance.
2. Nếu muốn thêm năng lực mới ít đụng workflow delivery: xem **retro + writing-for-agents**, và **to-questionnaire** khi cần lấy yêu cầu bên ngoài.
3. Xem **triage** khi bắt đầu nhận báo lỗi/yêu cầu đầu vào thường xuyên; Kitta có cấu hình thuận lợi hơn.
4. Xem **wayfinder** khi thật sự có dự án/milestone nhiều quyết định còn mơ hồ. Tính cả phụ thuộc của nó vào phạm vi cài được duyệt.
5. **teach** phục vụ học; **wizard** phục vụ onboarding thủ công cụ thể. Chưa ưu tiên skill trong `in-progress` hoặc dành cho môi trường Claude/course tooling.

Knora yêu cầu người dùng cho phép rõ trước khi cài/kích hoạt skill bổ sung. Yêu cầu nghiên cứu hiện tại không phải quyền cài tất cả skill hoặc thay governance của hai dự án. [Quy định Knora](C:/Developer/Projects/knora-agent/AGENTS.md).

## Kiểm chứng và giới hạn

Đã đọc snapshot nguồn chính qua GitHub API/raw.githubusercontent.com; công cụ web không mở được endpoint API nên dùng HTTPS từ PowerShell để lấy nguồn chính. Đã đếm đường dẫn `SKILL.md`, kiểm tra thư mục local và đọc tài liệu repo. Phân loại dựa trên nhiệm vụ/đầu ra/phụ thuộc, không chỉ tên. Không đo latency/token/quality của từng skill và không chứng minh tính tương thích bằng chạy workflow. Chỉ tạo báo cáo Markdown; không sửa source code, cài skill, tạo issue hoặc commit.

Không tìm thấy thư mục chuyên lưu research notes hiện hữu khi kiểm tra tracked files ở Knora, nên đặt báo cáo dưới `docs/research/`. Không cần chạy test ứng dụng cho artifact nghiên cứu; kiểm tra file và các liên kết nguồn/local riêng.

## Phụ lục: toàn bộ 37 skill upstream

Danh sách dưới đây dùng liên kết cố định để người đọc kiểm tra nhiệm vụ của từng skill. “Trùng” là trùng nhiệm vụ chính, không phải tương đương mọi quy tắc hoặc được phép thay thế.

| Skill | Nhóm | Đối chiếu |
| --- | --- | --- |
| [ask-matt](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/ask-matt/SKILL.md) | engineering | Router; trùng chọn workflow, chỉ hữu ích nếu chọn cả hệ upstream |
| [code-review](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/code-review/SKILL.md) | engineering | Trùng review; khác tổ chức hai trục Standards/Spec |
| [codebase-design](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/codebase-design/SKILL.md) | engineering | Nhiệm vụ đã được ghi trong repo; nguồn skill hiện thiếu |
| [diagnosing-bugs](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/diagnosing-bugs/SKILL.md) | engineering | Trùng systematic-debugging; upstream bao gồm sửa bug |
| [domain-modeling](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/domain-modeling/SKILL.md) | engineering | Nhiệm vụ đã ghi trong repo; phải adapt CONTEXT |
| [grill-with-docs](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/grill-with-docs/SKILL.md) | engineering | Trùng brainstorming một phần, repo đã tham chiếu |
| [implement-spec](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/implement-spec/SKILL.md) | engineering | Trùng orchestration một phần; không tương đương governance cũ |
| [implement](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/implement/SKILL.md) | engineering | Trùng implementation và TDD |
| [improve-codebase-architecture](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/improve-codebase-architecture/SKILL.md) | engineering | Khảo sát deepening chuyên biệt; đã từng được routing Kitta |
| [pr](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/pr/SKILL.md) | engineering | Template PR; trùng finishing/review, không phải năng lực delivery mới |
| [prototype](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/prototype/SKILL.md) | engineering | Trùng spike/visualize một phần; lưu prototype là khác biệt |
| [research](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/research/SKILL.md) | engineering | Đã cài |
| [retro](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/retro/SKILL.md) | engineering | Khoảng trống chuyên biệt; ưu tiên cao |
| [setup-matt-pocock-skills](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/setup-matt-pocock-skills/SKILL.md) | engineering | Repo đã có config; không chạy setup để ghi đè |
| [tdd](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/tdd/SKILL.md) | engineering | Trùng test-driven-development |
| [to-spec](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/to-spec/SKILL.md) | engineering | Synthesis và publish spec; trùng planning một phần, tác động tracker |
| [to-tickets](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/to-tickets/SKILL.md) | engineering | Nhiệm vụ đã được ghi trong repo; nguồn skill thiếu |
| [triage](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/triage/SKILL.md) | engineering | Thiếu nguồn hiện dùng; lifecycle chuyên biệt |
| [wayfinder](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wayfinder/SKILL.md) | engineering | Khoảng trống bản đồ quyết định nhiều phiên |
| [wizard](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wizard/SKILL.md) | engineering | Khoảng trống thủ tục con người; bash/secrets có điều kiện |
| [claude-handoff](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/claude-handoff/SKILL.md) | in-progress | Claude CLI, không phù hợp chạy trực tiếp trong Codex |
| [loop-me](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/loop-me/SKILL.md) | in-progress | Spec workflow đời sống; trùng brainstorming, ưu tiên thấp |
| [setup-ts-deep-modules](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/setup-ts-deep-modules/SKILL.md) | in-progress | Boundary enforcement cụ thể, in-progress |
| [writing-beats](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/writing-beats/SKILL.md) | in-progress | Soạn bài từng beat; in-progress, ngoài delivery chính |
| [writing-fragments](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/writing-fragments/SKILL.md) | in-progress | Khai thác nguyên liệu bài viết; in-progress |
| [writing-shape](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/in-progress/writing-shape/SKILL.md) | in-progress | Dựng bài từ nguyên liệu; in-progress |
| [git-guardrails-claude-code](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/misc/git-guardrails-claude-code/SKILL.md) | misc | Hooks Claude Code, không bảo vệ tool Codex hiện tại |
| [migrate-to-shoehorn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/misc/migrate-to-shoehorn/SKILL.md) | misc | Migration test TS chuyên biệt, chỉ khi có nhu cầu |
| [scaffold-exercises](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/misc/scaffold-exercises/SKILL.md) | misc | Dành course tooling ai-hero-cli, ngoài hai ứng dụng |
| [setup-pre-commit](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/misc/setup-pre-commit/SKILL.md) | misc | Hook local cụ thể, trùng quality gate một phần |
| [grill-me](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/grill-me/SKILL.md) | productivity | Wrapper grilling; trùng brainstorming một phần |
| [grilling](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/grilling/SKILL.md) | productivity | Interview theo frontier; trùng brainstorming một phần |
| [handoff](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/handoff/SKILL.md) | productivity | Repo đã quy định handoff; bản upstream lưu temp khác convention |
| [teach](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/teach/SKILL.md) | productivity | Học nhiều phiên; thiếu chuyên biệt, ưu tiên học tập |
| [to-questionnaire](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/to-questionnaire/SKILL.md) | productivity | Khoảng trống questionnaire async |
| [wait-what](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/wait-what/SKILL.md) | productivity | Viết lại giải thích plain English; nhiệm vụ giao tiếp chung |
| [writing-for-agents](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/writing-for-agents/SKILL.md) | productivity | Trùng skill authoring một phần, hỗ trợ retro |
