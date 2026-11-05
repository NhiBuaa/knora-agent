# Duy trì phiên đăng nhập trên trình duyệt

Liên quan: [Issue #230](https://github.com/NhiBuaa/knora-agent/issues/230).
Phiên bản đề xuất: **R1, 2026-10-30**. Chờ người dùng duyệt trọn bộ thiết kế/kế hoạch;
các quyết định sản phẩm bên dưới đã được người dùng trả lời trong hội thoại này.

Nguồn kỹ thuật: [thiết kế](../design/browser-session-policy.md),
[nghiên cứu Keycloak](../research/session-persistence-keycloak.md).
Các bước thực hiện thuộc [kế hoạch](../plans/browser-session-persistence.md).

## 1. Vấn đề và bằng chứng nền

Phiên tại môi trường local được chẩn đoán đã hết sau 33 phút nghỉ liên tục: cookie
ban đầu còn 1.798 giây; không có yêu cầu gia hạn trong 1.980 giây; sau đó cookie mất,
`/api/auth/session` trả `{session:null}` và mở Workspace yêu cầu đăng nhập lại.
Realm lúc đo: Keycloak 26.3.3, idle 1.800 giây, max 36.000 giây, access 300 giây,
Remember Me tắt; Knora còn chặn max 8 giờ.

Đây là chẩn đoán một môi trường, không chứng minh mọi trường hợp được báo là lỗi ở
phút thứ 15. Runtime bị phiên khác cập nhật/restart frontend/backend trong lượt đo;
không dùng phép đo đó làm nghiệm thu một build cố định. Nguồn gốc phép đo ngày
29–30/10/2026: thư mục local tạm `knora-session-idle-d0d1b49dc3704759bd2567d74838b6d9`,
đặc biệt `session-persistence-diagnostics.md` và `observations.jsonl`. Không cần dữ liệu
xác thực từ thư mục này để triển khai; không sao chép profile/cookie/log thô vào Git.

## 2. Hành vi đã chốt

| Mã | Yêu cầu |
| --- | --- |
| P1 | Không chọn “Giữ đăng nhập”: idle **1.800 giây**, max **28.800 giây**; cookie Knora theo phiên trình duyệt, không `Max-Age`/`Expires`. |
| P2 | Chọn “Giữ đăng nhập”: idle **604.800 giây**, max **2.592.000 giây**; cookie persistent, không sống lâu hơn refresh token hoặc max phiên. |
| P3 | Access token tối đa **300 giây**; gia hạn khi còn không quá **30 giây**. Không `offline_access`, không heartbeat hoặc timer tự duy trì phiên. |
| P4 | Mọi form đăng nhập mới bỏ chọn mặc định, kể cả có gợi ý Remember Me từ lần trước. Khi nhập sai, giữ lựa chọn vừa gửi. Không tự nhớ lựa chọn ở localStorage/cookie riêng của Knora. |
| P5 | Phiên SSO đang có và còn hạn được dùng lại với đúng chế độ/mốc ban đầu; không nâng chế độ hoặc tính lại max từ callback. Để đổi chế độ, đăng xuất rồi đăng nhập mới. Không ép `prompt=login` trong luồng thường. |
| P6 | Khi hết phiên trong tab chat, giữ bản nháp và khóa gửi. Đăng nhập lại ở tab khác, trở về tab cũ thì tự kiểm tra phiên và tải lịch sử **một lần** nếu cùng issuer + subject. Không tự gửi/replay POST. |
| P7 | Nếu phát hiện đổi issuer hoặc subject, xóa bản nháp, lịch sử và mọi state của hội thoại cũ khỏi màn hình; điều hướng đầy đủ về `/workspaces`. Không chuyển bản nháp sang tài khoản mới. |
| P8 | Bản nháp chỉ trong bộ nhớ của tab đang mở. Đóng/reload tab có thể mất nháp; không sessionStorage, localStorage, IndexedDB, service worker hoặc server autosave cho nháp. |
| P9 | Lỗi mạng/Keycloak tạm thời giữ cookie và nháp trong giới hạn hiện có, báo có thể thử lại; không biến lỗi tạm thành đăng xuất, không gia hạn giả hoặc gửi mutation bằng token hết hạn. |
| P10 | Đăng xuất Knora xóa cookie, thu hồi cục bộ trước khi gọi logout Keycloak. Thu hồi ngoài ứng dụng có thể còn hiệu lực access token đã cấp tối đa **5 phút**; không yêu cầu thu hồi toàn hệ thống tức thời. |
| P11 | Chuyển định dạng phiên: chấp nhận đăng nhập lại **một lần**; cookie cũ không được chuyển thành phiên dài. Không logout toàn realm hoặc đổi `SESSION_SECRET` chỉ để migration. |
| P12 | **Sleep/wake bị loại khỏi phạm vi và tiêu chí hoàn thành**, theo câu trả lời Q7 của người dùng ngày 30/10/2026. Không thêm bước ngủ máy thật hay mô phỏng để thay thế yêu cầu đã bỏ. |

Idle là thời gian từ xác thực/gia hạn cuối của phiên Keycloak, không phải thời gian
từ thao tác chuột/bàn phím cuối. Yêu cầu nghiệp vụ bình thường có thể dẫn tới refresh;
tab nằm yên không có polling đang thực hiện Turn thì không tự tạo request giữ phiên.
Max bắt đầu tại lúc tạo phiên SSO và không trượt theo hoạt động hoặc callback.

Cookie theo phiên không bảo đảm browser xóa sau khi đóng vì tính năng khôi phục phiên.
Máy dùng chung cần chủ động Đăng xuất. Lựa chọn “máy tin cậy” là người dùng tự chọn
Remember Me cho phiên, không là chứng thực thiết bị hoặc phân quyền mới.

## 3. Tình huống và tiêu chí nghiệm thu

| Mã | Tình huống | Đạt khi | Bằng chứng không đủ |
| --- | --- | --- | --- |
| A1 | Hai chế độ đăng nhập thật | Form mặc định unchecked; retry giữ lựa chọn; BFF áp đúng policy và flags cookie | Chỉ sửa realm JSON hoặc render fixture |
| A2 | Nghỉ thật 15 phút | Phiên thường còn dùng được sau **900 giây** không request ở giữa | Đã gọi session probe trong khoảng nghỉ |
| A3 | Nghỉ thật 33 phút | Phiên thường hết hạn; phiên Remember Me còn dùng sau **1.980 giây**, refresh thành công và đọc Workspace đúng chủ | 15 phút rồi probe và chờ thêm 18 phút trên cùng phiên |
| A4 | Biên idle/max | Kiểm thử thời gian giả của BFF chứng minh đúng trước/tại/sau deadline; Keycloak test gia tốc chứng minh giới hạn token và SSO | Đã chờ thực 7/30 ngày khi chỉ giảm timeout |
| A5 | Đóng/mở browser | Persistent profile riêng giữ phiên Remember Me; cookie thường không có thuộc tính persistence. Quan sát riêng hành vi restore của browser đã dùng | Export/import storageState hoặc sao chép cookie |
| A6 | Cùng tài khoản đăng nhập lại | Focus + visibility chỉ một chuỗi probe → history GET; nháp/khóa idempotency giữ nguyên; POST tăng **0** | Chỉ bấm login thành công hoặc history trả 200 |
| A7 | Khác tài khoản | Cùng sub khác issuer và khác sub đều xóa state, không POST nháp cũ; request race bị chặn ở BFF trước gọi API | Chỉ dựa vào Workspace 403 |
| A8 | Lỗi/đồng thời | Timeout/5xx/invalid_grant, response cũ, concurrent refresh/logout/unmount đều theo thiết kế; không hồi sinh phiên | Test happy path đơn lẻ |
| A9 | Cập nhật/hoàn tác | Import mới và realm tồn tại cùng projection; Apply lần hai no-op; rollback projection/safety/readback đạt; cookie v2 bị decoder cũ từ chối | PUT 2xx không đọc lại hoặc re-import volume |
| A10 | An toàn và hiển thị | Không token/password/nháp trong report/storage/URL; header cookie <4.096 byte; keyboard checkbox/recovery và render 390/1440 px dùng được | Test code hoặc screenshot fixture riêng lẻ |
| A11 | Đúng build và cleanup | Source SHA, image IDs, topology, config snapshot, kết quả test và cleanup thuộc cùng lượt riêng | Runtime smoke cũ hoặc CI của SHA khác |

Không cần chờ thực 7 ngày/30 ngày để hoàn thành: thời gian thật kiểm tra A2/A3;
biên dài được chứng minh bằng phép tính BFF và realm gia tốc có nhãn rõ. Không tuyên bố
độ ổn định chạy liên tục 30 ngày từ những kiểm tra này.

## 4. Ranh giới và thẩm quyền

- Tái dùng BFF và một tiến trình Next.js hiện tại; không thêm database/Redis, token
  introspection, backchannel logout hoặc nhiều replica trong issue này.
- Không thay backend Workspace/capability authorization, API-key, OTP/recovery flow,
  redirect URI, SMTP, provider/model hoặc chính sách refresh-token rotation.
- Công việc hiện tại chỉ viết tài liệu. Duyệt thiết kế không tự cấp quyền sửa stack
  dùng chung, merge hay deploy. Lượt chẩn đoán 40 phút cũ đã hết và không được tái dùng.
- Khi triển khai được giao, áp dụng run package trong kế hoạch trên stack disposable.
  Môi trường đang tồn tại/production cần gói activation có đúng target và quyền owner.

## 5. Nguồn quyết định và duyệt

Người dùng chốt 7 ngày/30 ngày trước lượt thiết kế; trả lời Q1–Q4 chọn toàn bộ khuyến
nghị; Q5 chấp nhận cửa sổ thu hồi 5 phút; Q6 chấp nhận đăng nhập lại một lần; Q7 yêu cầu
bỏ tiêu chí sleep/wake. Các tham chiếu này là hội thoại **“Issue #230 — nghiên cứu,
phân tích và thiết kế” ngày 30/10/2026**, không phải URL phê duyệt GitHub.

Bộ R1 cần được duyệt như một bộ trước triển khai. Người nhận ghi đường dẫn kế hoạch,
full commit SHA của tài liệu được duyệt và tham chiếu chính xác câu trả lời duyệt vào
Issue/PR khi đã có quyền công bố; không coi SHA nền là SHA phê duyệt.
