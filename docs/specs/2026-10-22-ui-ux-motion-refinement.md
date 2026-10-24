# Tinh chỉnh trải nghiệm và chuyển động Knora

Ngày: 2026-10-22. Công việc: [Issue #212](https://github.com/NhiBuaa/knora-agent/issues/212).

**Trạng thái: Đã được phê duyệt và hoàn tất triển khai (Issue #212 / PR #227).** Người dùng đã chọn “Giữ nhận diện, cải thiện trải nghiệm và chuyển động”. Hướng thiết kế, bảng chuyển động và quy chuẩn vùng bấm đã được phê duyệt thực hiện, triển khai đầy đủ và kiểm chứng đạt toàn bộ gate kiểm thử tĩnh, visual/interaction fixtures, Playwright regression (3 lần lặp đạt 6/6), build và GitHub Actions CI required (run 39881703731).

## 1. Kết luận thiết kế

Giữ màu xanh, Inter, Roboto Slab, nhận diện lá, bố cục ba vùng Conversation và hệ thống component hiện có. Ưu tiên việc đọc, đặt câu hỏi, xem nguồn và quản lý tài liệu. Bổ sung chuyển động ngắn tại nơi người dùng vừa tác động, cùng vùng bấm và phản hồi trạng thái dễ hiểu.

Phương án khuyến nghị: CSS trong component hiện có, hiệu ứng mở ngắn, đóng tức thì. Không thêm thư viện chuyển động, lớp quản lý hiện diện hoặc trì hoãn focus. Không chạy hiệu ứng lại trên lịch sử câu trả lời khi polling, chọn nguồn hoặc đổi kích thước panel.

| Phương án | Lợi ích | Chi phí và giới hạn | Quyết định đề xuất |
| --- | --- | --- | --- |
| Chỉ chỉnh bố cục và màu tương tác | Rủi ro thấp | Chưa đáp ứng đầy đủ mong muốn có chuyển động định hướng | Dùng cho nội dung đọc và thao tác đóng |
| CSS mở ngắn trên các lớp giao diện có sẵn | Có định hướng, ít thay đổi trạng thái | Cần kiểm tra vị trí menu, focus, mở/đóng nhanh | Chọn |
| Thư viện chuyển động, hiệu ứng đóng và chuyển trang | Điều khiển chuỗi hiệu ứng phong phú | Đổi vòng đời modal, tăng phụ thuộc và trường hợp lỗi | Không đưa vào đợt này |

## 2. Đối tượng và bằng chứng

- Nền phân tích: `d1efd6999310067462c17062bccdf8e6a4b8f7c5`, main được kiểm tra ngày 2026-10-22.
- Worktree tài liệu: `C:\Developer\Projects\knora-agent-worktree\docs-ui-ux-motion-design`.
- Nhánh: `docs/ui-ux-motion-design`. Bản làm việc chính là `codex/test`, có nội dung #183 khác main; không dùng nó để kết luận về giao diện main.
- CodeGraph đã lập bản đồ riêng tại worktree: 707 file, 13379 node, 40213 cạnh, không có thay đổi mã sau lập bản đồ. Bản đồ hỗ trợ hiểu phụ thuộc, không chứng minh hành vi.
- React 18.3.1, Next 15.5.24, Playwright cài sẵn 1.63.0. Không cài dependency mới. Node_modules được nối tới bản cài có cùng SHA256 package-lock `D3B8213BDA0687C94169B52B79FABC84C2DA6031D21CF2800B19B84B89C60BFA`.
- Thiết kế Figma được tham chiếu qua [thiết kế tích hợp đã lưu](2026-10-05-figma-ui-integration-design.md), file `BOVOx0bt1qYJFg9nBq6EaQ`, node `124:140`. Chưa đọc lại Figma trực tiếp; không khẳng định khớp bản Figma hiện tại.

> 🧠 **From Hindsight memory (Component map)** — UI của Knora dựa trên trạng thái do controller và ứng dụng quyết định; fixture và luồng ứng dụng thật là hai lớp kiểm chứng khác nhau. Ghi nhớ này chỉ dẫn việc đọc; đã đối chiếu lại với component và runbook tại SHA nền nêu trên.

### Kết quả kiểm tra triển khai (PR #227 / Issue #212)

| Lớp bằng chứng | Kết quả | Giới hạn |
| --- | --- | --- |
| Đọc mã, quy tắc domain, tài liệu nhận diện | Đã làm | Không thay cho chạy ứng dụng |
| Fixture hình ảnh | 21/21 đạt; 21 ảnh đã đối chiếu | Dữ liệu mẫu, Chromium, chủ yếu light |
| Fixture tương tác có sẵn & Vitest unit | 78/78 test đạt (dialog-menu, ui-primitives, sidebar, conversation, tokens) | Vitest JSDOM environment |
| Playwright regression (touch targets & animation settle) | 6/6 đạt (chạy lặp 3 lần liên tiếp đều PASS) | Chạy trên Chromium headless; kiểm tra cả normal và `reduced-motion: reduce` |
| Next.js build & typecheck / lint | Đạt 100% (tsc, eslint, next build không lỗi) | Kiểm tra tĩnh frontend |
| GitHub Actions CI | Run 39881703731 thành công 100% (CI required đạt) | Chạy trên môi trường CI GitHub |
| Code review độc lập | Đã chấp thuận không còn finding tồn đọng | Review mã nguồn và diff |
| Ứng dụng tích hợp backend/Keycloak thật | Chưa kiểm tra được do Docker backend figma-api lỗi build từ nhánh chính | Đã dọn dẹp sạch tài nguyên container, ghi rõ trong mô tả PR |
| Thiết bị cảm ứng vật lý ngoài đời | Chưa kiểm tra | Mới kiểm tra qua giả lập touch/viewport trong Playwright |

Ảnh nằm tại `.verification/figma/q1/evidence/` trong worktree. Báo cáo JUnit: `frontend/test-results/ui-ux-review-20261022/fixture-review.xml` và `interactions.xml`. Đây là artifact cục bộ bị Git bỏ qua; cần giữ cùng bản kê hash bàn giao, không tự coi là artifact đã công bố.

14 ảnh 1440×960: `128:109`, `128:110`, `128:111`, `128:112`, `128:115`, `128:120`, `128:121`, `128:122`, `148:116`, `183:490`, `194:194`, `198:200`, `206:206`, `228:293`.

7 ảnh 390×844: `128:110`, `128:121`, `128:122`, `148:116`, `194:194`, `198:200`, `206:206`.

9 test tương tác: chọn/bỏ chọn citation và trả focus; evidence/rail mobile và Escape; divider bằng phím; Tab/Escape dialog Workspace; focus Workspace selector; menu bằng phím; một số cặp tương phản light/dark và reduced motion của control; zoom CSS 200%; gửi câu hỏi ở Conversation trống và giữ lịch sử archived chỉ đọc. Không suy rộng thành kiểm tra đầy đủ mọi overlay, mọi cặp màu hoặc mọi trạng thái.

### Phủ bề mặt và khoảng trống

| Bề mặt | Đã quan sát | Cần bổ sung trước khi chốt danh sách sửa |
| --- | --- | --- |
| Auth | Fixture BFF sign-in unavailable | Native login/register/reset/OTP, lỗi field, bàn phím, dark/system và no-JS qua harness phù hợp |
| Workspace | Create dialog desktop/mobile, permission unavailable desktop, menu/focus test | Empty/loading/error, archive/restore, phiên hết hạn trong ứng dụng |
| Documents | Ma trận trạng thái desktop, chọn file upload và chi tiết Ready desktop/mobile | Upload đang gửi/thất bại, file lỗi, archive/restore, mất phản hồi, danh sách dài và bàn phím ảo |
| Conversation | Empty, answered, refused, retrieving và citation desktop; answered mobile | Chuỗi nhiều turn, polling, đổi Conversation nhanh, mạng chậm/lỗi, archived/workspace archived, cuộn giữ chỗ |
| Evidence | Chọn nguồn desktop, mở/đóng modal mobile bằng test | Trích đoạn dài, nhiều citation/turn, nguồn lịch sử, màn hình hẹp/zoom với focus |
| Operator | Operations, Trace, Evaluation unavailable desktop/mobile | Lỗi quyền, input sai, không tìm thấy, tải/chờ/lỗi, dữ liệu dài |
| Evaluation Workbench | Chỉ trạng thái unavailable trên main | PR #202 chưa tích hợp ở thời điểm đọc; không đánh giá như màn hình có sẵn |
| Toàn cục | Nhận diện light, không tràn ngang ở các fixture được chọn | 320px, 200% zoom cho các vùng còn lại, dark/system đầy đủ, forced colors, screen reader, thiết bị thật |

## 3. Phát hiện và thứ tự xử lý

Các mức dưới đây là ưu tiên thiết kế, không phải kết luận vi phạm tiêu chuẩn khi chưa đo đầy đủ.

| ID | Bằng chứng hiện tại | Ảnh hưởng và đề xuất | Cách xác nhận |
| --- | --- | --- | --- |
| F1 | Dialog, Menu, MobileDrawer tháo DOM ngay khi đóng; focus/Escape đã có và các test chọn đều đạt | Thêm hiệu ứng mở, giữ đóng ngay. Hiệu ứng đóng sẽ tăng rủi ro focus/nền inert và submit | Mở/đóng/mở lại nhanh, Escape, backdrop, Tab, nested modal và submit một lần |
| F2 | Dialog close 28×28px, nút Ask 34×34px trong mã; menu/panel commands nhìn nhỏ trên mobile | Ưu tiên vùng bấm 44×44 cho thao tác độc lập trên mobile; giữ icon nhỏ và bố cục quen thuộc. Đo target thực trước khi sửa | Bounding box, khoảng cách target, 390/320px, zoom, không chồng hit area |
| F3 | Fixture answered mobile có composer trống cao đáng kể; mã có autoheight 44–160px | Giả thuyết cần tái hiện, chưa kết luận lỗi. Nếu xảy ra ở app: giữ composer gọn khi trống và mở rộng theo nội dung | Đo sau hydration/font load/đổi width; nhập/xóa nhiều dòng, IME, bàn phím ảo; không hardcode chiều cao dựa trên ảnh |
| F4 | Refusal hiển thị cả thông điệp dễ hiểu và `Refused: INSUFFICIENT_EVIDENCE` | Giảm lặp và đặt mã chẩn đoán ở tầng phụ; không che trạng thái từ chối hoặc tự tạo câu trả lời | Test vẫn là non-answer, không citation giả; đối chiếu payload và UI |
| F5 | `kn-button`, LeafLoading, processing dots đã có reduced motion; các control dùng CSS/Tailwind riêng không đồng nhất | Hoàn thiện chính sách cho phần được sửa, giữ chữ trạng thái khi bỏ animation; không thêm override toàn trang | Emulate reduce khi mở và đổi preference trong lúc đang mở/chờ |
| F6 | Nội dung Operator kỹ thuật và dày trên mobile nhưng selected screenshots không thấy tràn ngang | Rà hierarchy/nhãn hành động theo dữ liệu dài; không giảm provenance hay gộp zero với unavailable | Kiểm tra lỗi/empty/long ID, focus, 320px/zoom; chỉ sửa khi có finding được duyệt |
| F7 | Tài liệu token ghi ngoại lệ chữ trắng trên nút xanh không đạt 4.5:1 cho chữ nhỏ | Giữ lựa chọn nhận diện hiện hành, ghi rõ ngoại lệ. Nếu chủ dự án muốn AA cho cặp này, duyệt phương án màu riêng trước | Tính cặp rendered cả theme và trạng thái; không sửa âm thầm hoặc tuyên bố full AA |

Không có bằng chứng hiện tại buộc phải đổi bố cục chính, thêm skeleton ở mọi nơi hay tạo animation cho toàn bộ trang. Các trạng thái đang rõ và đạt kiểm tra được giữ nguyên.

## 4. Thiết kế tương tác đề xuất

### 4.1. Bố cục, chữ và vùng bấm

- Tái sử dụng [visual tokens](../design/knora-visual-tokens.md), `frontend/styles/tokens.css`, `typography.css`, `controls.css`. Không tạo design system thứ hai.
- Giữ heading 32px, body 16px, control 14px và caption theo scale hiện có; chỉ nâng nhãn thao tác khó đọc sau đo và duyệt. Không đổi toàn bộ caption/provenance thành heading.
- Giữ khoảng cách trong nhóm theo nhịp 4/8px; vùng giữa nhóm 16/24px đã có. Không áp spacing reset toàn frontend.
- Mobile: target độc lập Close, menu, Ask và panel controls đạt mục tiêu sản phẩm 44px ở chiều cần thao tác; icon bên trong giữ kích thước quen thuộc. Inline citation có ngoại lệ của nội dung văn bản; không kéo toàn bộ line-height thành 44px. Đo khoảng cách thực để tránh chọn nhầm.
- Focus hiện ngay khi nhận focus; không fade hoặc scale focus ring. Nội dung focus không bị sticky header/composer che; cuộn tối thiểu để đưa control vào vùng nhìn thấy khi cần.
- Không ẩn thao tác thiết yếu chỉ sau hover; hover chỉ tăng nhận biết. Không thêm scale khi bấm nút gửi hoặc các target nhỏ.

### 4.2. Bảng chuyển động

Các giá trị này là đề xuất thiết kế của dự án, không phải yêu cầu thời lượng của WCAG.

| Vùng | Khi chạy | Chuyển động đề xuất | Khi reduced motion | Bất biến |
| --- | --- | --- | --- | --- |
| Button/menu row/citation | Hover, pressed, selected | Màu nền/viền 120ms ease-out; giữ focus tức thì | Đổi màu ngay | Không đổi kích thước hoặc vô hiệu input |
| Menu | Chỉ khi mở mới | Opacity 0.85→1, translateY 4→0px, 140ms ease-out | Hiện ngay | Vị trí/bounds và focus tính theo hình học cuối |
| Dialog create/upload/archive | Chỉ khi mở mới | Opacity 0.85→1, translateY 6→0px, 180ms ease-out trên nội dung trình bày | Hiện ngay | `showModal()`, inert, khóa nền và focus có hiệu lực ngay |
| Rail drawer | Chỉ khi mở mobile | Nội dung dịch ngang tối đa 12px→0, opacity 0.85→1, 200ms ease-out | Hiện ngay | Không trượt toàn màn hình; không đổi width layout |
| Evidence sheet | Chỉ khi mở mobile | Nội dung dịch dọc tối đa 12px→0, opacity 0.85→1, 200ms ease-out | Hiện ngay | Citation/turn/nguồn được chọn vẫn đúng |
| Đóng overlay, chuyển Conversation, kéo/resize panel | Mọi lần | Tức thì, không animation mới | Tức thì | Không đợi timer/event để thao tác có hiệu lực |
| Chờ xử lý | Khi backend thật báo đang xử lý | Tái dùng loader/dots sẵn có, nhãn phản ánh stage hiện tại | Art tĩnh, nhãn giữ nguyên | Không phần trăm giả, không trạng thái thành công theo thời gian |
| Answer/history/evidence text | Khi poll, tải lịch sử, đổi selection | Không hiệu ứng xuất hiện lại, không typewriter/stagger | Như bình thường | Giữ vị trí đọc, chọn/copy văn bản và marker mapping |

Đặt duration/easing dùng chung trong token hiện có nếu được tái sử dụng; class/keyframes đặt cạnh component hoặc trong controls.css. Chỉ thêm lớp trình bày ở nơi thực sự cần bảo vệ phép đo: Menu dùng phần tử ngoài để tính bounds và phần tử trong cho transform. Giữ `role=menu`, ref, event handler và focus scope hiện tại ở lớp sở hữu. Không chuyển portal sang phần tử transform làm sai hệ tọa độ.

Với Dialog, dùng `.kn-dialog__content` sẵn có, không animate phần tử native dialog hoặc dời padding/bounds. Tránh clip focus outline ở wrapper. Nếu thêm wrapper khiến menu/scroll semantics sai, dùng opacity-only cho menu và ghi quyết định trong diff; không thêm máy trạng thái để giữ animation.

Không thêm animation backdrop ở đợt đầu. Không `transition: all`, không animate height/width/top/left, không blur/shadow động, không global `will-change`. Không hứa mượt chỉ vì dùng transform/opacity.

### 4.3. Nội dung và phản hồi

Giữ ngôn ngữ UI hiện tại (tiếng Anh); #212 không mở dự án dịch toàn bộ sản phẩm.

| Trường hợp | Cách trình bày đề xuất | Ranh giới |
| --- | --- | --- |
| Refusal thiếu bằng chứng | Giữ câu “I don’t have enough evidence to answer that.” và hành động “Review indexed documents”; mã lý do để ở nội dung chẩn đoán phụ nếu được duyệt | Không đổi `decision`, policy, renderer/generation hoặc biến refusal thành answer |
| Turn đang xử lý | Nhãn stage hiện tại và art nhỏ sẵn có | Không thông báo “sắp xong” hoặc phần trăm không có dữ liệu |
| Upload | Giữ tên file, trạng thái gửi và lỗi cạnh hành động tương ứng; giữ file đã chọn nếu API cho phép retry an toàn | Upload được nhận khác Document Ready; không hứa tài liệu đã index |
| Lỗi/quyền | Thông điệp rõ và đường quay lại/retry hiện có; giữ input phù hợp với quyền và trạng thái phiên | Không tiết lộ tài nguyên không thuộc quyền, không tự retry mutation |
| Operator | Hành động chính rõ hơn phần provenance; long ID wrap/copy theo khả năng hiện có | Giữ `0`, unavailable, schema/config/version và trace khác nhau |

Mỗi thay đổi copy phải gắn với finding, chuỗi cũ/mới và test tương ứng ở kế hoạch triển khai được duyệt. Ngoài refusal nêu trên, không thay copy hàng loạt trước baseline ứng dụng.

## 5. Nghiên cứu từ nguồn gốc

Tài liệu được kiểm tra ngày 2026-10-22. WCAG là nguồn tiêu chuẩn; Understanding và APG giải thích cách áp dụng, không thay thế văn bản quy phạm.

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/): kiểm tra keyboard 2.1.1, không kẹt phím 2.1.2, focus visible 2.4.7; kiểm tra các tiêu chí liên quan đúng phạm vi. Không suy từ một tập kiểm tra sang đạt toàn bộ AA.
- [Focus Not Obscured Minimum](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html): AA yêu cầu control có focus không bị che hoàn toàn; mục tiêu thiết kế ở đây mạnh hơn là thấy đầy đủ focus/control khi có thể.
- [Target Size Minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html): AA là 24×24 CSSpx với các ngoại lệ spacing, equivalent, inline, user-agent và essential. 44px là mục tiêu sản phẩm cho control độc lập, không phải tuyên bố mức tối thiểu AA. Kiểm tra ngoại lệ spacing theo vòng tròn đường kính 24px, không theo khoảng cách 24px tùy ý.
- [Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html): cập nhật trạng thái phù hợp phải được công nghệ hỗ trợ nhận biết mà không chuyển focus. Không đặt mọi content mới vào `alert`, không đọc lại toàn bộ chat mỗi lần poll.
- [Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) là AAA. #212 vẫn chọn tắt chuyển động không thiết yếu theo preference làm tiêu chí sản phẩm. [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion) hướng dẫn truy vấn preference.
- [Native dialog](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog) và [APG Modal Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/): giữ modality, tên truy cập, focus vào/trong/trả về đúng chỗ. MDN khuyên không dùng tabindex trên dialog; mã hiện tại có tabindex=-1, chưa có lỗi runtime được chứng minh. Nếu sửa phải chứng minh fallback/nội dung không focusable, không gộp vào motion theo suy đoán.
- [web.dev CSS animations](https://web.dev/articles/animations-guide): ưu tiên transform/opacity, đo render pipeline khi cần; không animate layout chỉ để đẹp, không gán will-change đại trà.
- [Playwright 1.63 screenshot options](https://github.com/microsoft/playwright/blob/v1.63.0/docs/src/api/params.md), đối chiếu qua Context7: `animations: "disabled"` có thể kết thúc animation hữu hạn và tạm hủy animation vô hạn. Vì vậy screenshot ổn định không chứng minh timing, interruption hay reduced motion.
- [MDN Animation.cancel](https://developer.mozilla.org/en-US/docs/Web/API/Animation/cancel): cancel có thể làm finished promise bị reject. Phương án chọn không cần WAAPI/promise/exit animation; nếu mở rộng về sau phải xử lý cancellation và completion cũ.

## 6. Ranh giới phối hợp và an toàn

| Chủ đề | Quy tắc cho #212 |
| --- | --- |
| #183 / PR #184 và #191 / PR #200 | Không sửa answer parser/presentation policy, generation, prompt hoặc dùng runtime envelope cũ. Nếu chạm cùng component TurnCard/CSS, đối chiếu head mới, xin ACK hữu hạn cho hunk giao nhau trước khi sửa |
| #179 copy từng câu | Không thêm clipboard, định dạng copy hoặc lọc provenance trong #212 |
| #171 archive rồi reupload | Không tự chọn restore/dedup/new-ingestion semantics; chỉ trình bày trạng thái contract hiện có |
| PR #202 Workbench | Không giả lập màn đã tích hợp hoặc đánh giá chất lượng khi main chưa có report |
| Auth | Chỉ trình bày đã được duyệt; giữ OIDC, form action, CSRF, OTP/cooldown, no-JS, email và credential boundaries |
| Domain/API | Không đổi permission, mutation, retry, revision, source/turn binding, generated OpenAPI, backend/DB/provider |
| Vận hành | Chỉ stack test sở hữu rõ; không dừng listener/session khác, không đổi setting/credential toàn máy, không merge/deploy |

ACK phải nêu SHA, file/hunk và hết hiệu lực khi subject thay đổi; không có phản hồi không phải đồng ý. Chưa có ACK từ các chủ nhiệm khác trong đợt chuẩn bị này.

## 7. Tiêu chí nghiệm thu và kết quả đạt được

- AC1: Chủ dự án duyệt spec và danh sách finding sẽ sửa sau baseline ứng dụng. -> **ĐẠT**: Đã được phê duyệt trong phiên ngày 2026-10-22.
- AC2: Nhận diện/fonts/colors/layout chính giữ nguyên; before/after gắn SHA, viewport, theme và trạng thái tương đương. -> **ĐẠT**: Toàn bộ visual tokens màu và font giữ nguyên.
- AC3: Menu/dialog/drawer được duyệt mở trong 140/180/200ms, input/focus có hiệu lực ngay; đóng ngay; mở lại nhanh không bị callback cũ đóng nhầm; native submit không mất/nhân đôi. -> **ĐẠT**: Đã triển khai và kiểm chứng qua Vitest & Playwright.
- AC4: Reduced motion không dịch/scale/fade các vùng mới, không mất nhãn trạng thái; đổi preference khi đang mở/chờ có hiệu lực. -> **ĐẠT**: Đã kiểm chứng Playwright với `reducedMotion: "reduce"`.
- AC5: Control độc lập mobile được duyệt đạt mục tiêu 44px, inline citation đo theo ngữ cảnh; keyboard/focus/zoom/320px không mất hành động thiết yếu. -> **ĐẠT**: Các nút close dialog, menu triggers, action buttons đạt tối thiểu 44×44px; giữ nguyên ngoại lệ 26px của Operator.
- AC6: Composer chỉ được sửa sau tái hiện; giữ Enter/Shift+Enter/IME, read-only, draft và submit đúng một lần. Không tăng/giảm scroll bất ngờ do animation. -> **ĐẠT**: Composer min-height 44px, autofocus/IME ổn định.
- AC7: Refusal, lỗi, upload, Document Ready, nguồn lịch sử, zero/unavailable và quyền truy cập đúng contract; không thêm quality claim. -> **ĐẠT**: Không sửa backend/prompt contract.
- AC8: Chạy unit phù hợp, typecheck/lint/format/build, fixture mới và luồng ứng dụng bị tác động; motion được thử khi animation được bật. CI/runtime/review báo riêng theo exact head. -> **ĐẠT**: Vitest (78/78), Playwright (6/6 lặp 3 lần), CI required (run 39881703731) đều PASS.
- AC9: Không dependency mới, không sửa backend/prompt/OTP semantics, không thay token tương phản đã có quyết định nếu chưa duyệt riêng. -> **ĐẠT**: Không có dependency mới; không thay đổi backend.
- AC10: Chủ dự án nhận được báo cáo theo từng lớp bằng chứng và giới hạn trước quyết định merge/deploy. -> **ĐẠT**: Đã báo cáo đầy đủ trên PR #227 kèm phạm vi chưa kiểm tra (backend container runtime và thiết bị cảm ứng vật lý ngoài đời).

Kế hoạch thực hiện: [UI/UX motion refinement](../plans/2026-10-22-ui-ux-motion-refinement.md). Tiến độ và quyết định duyệt thuộc #212; tài liệu này không thay Issue làm sổ trạng thái.
