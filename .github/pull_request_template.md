## Issue liên quan

<!-- Ví dụ: Closes #123 -->

## Thay đổi chính

-

## Kiểm thử đã chạy

<!-- Theo docs/runbooks/ci.md#verification-contract và mục matching-quality-claims-to-evidence. Trước khi sửa, ghi yêu cầu chất lượng bị ảnh hưởng, nguồn yêu cầu, điều kiện đạt và cách kiểm tra dự kiến tại đây hoặc dẫn tới Issue. Chỉ chọn phần liên quan, gồm luồng thành công, lỗi và ranh giới an toàn; cập nhật khi phát hiện ảnh hưởng mới. Không yêu cầu full E2E/model inference cho mọi PR. -->

Yêu cầu / điều kiện đạt và kế hoạch kiểm chứng (hoặc liên kết Issue):

Checkout/SHA đã kiểm tra (kèm dirty diff nếu có):

<!-- Trước khi đăng lệnh, thay token/password và mọi giá trị bí mật bằng [REDACTED], kể cả đối số và giá trị môi trường nội tuyến. Giữ executable/subcommands, tên flags/biến, quoting và đối số không nhạy cảm để tái hiện; chỉ cấp secrets thật qua cấu hình local đã được phép. -->

| Điều kiện cần chứng minh | Lệnh tái hiện (đã che secrets) / thư mục chạy | Phạm vi, số test và exit/result | Evidence / report / run |
| ------------------------ | --------------------------------------------- | ------------------------------- | ----------------------- |
|                          |                                               |                                 |                         |

<!-- Giữ bằng chứng lần FAIL, nguyên nhân và kết quả chạy lại. Nêu test chưa chạy, blocker và vì sao browser/runtime cần hoặc không cần; fixture PASS không chứng minh live backend hay chất lượng AI. Chỉ dẫn evidence đã khử secrets. -->

## Trạng thái có bằng chứng

<!-- Dùng định nghĩa trong CI runbook; với mỗi trạng thái ghi evidence hoặc pending / blocked / not run / not applicable + lý do. Không tự suy ra trạng thái khác từ test PASS. -->

- Implemented:
- Local Verified:
- CI Verified (PR head SHA + CI required run; đối chiếu ci-subject):
- Runtime Verified (journey/profile + build/environment):
- Reviewed / Merged / Deployed (ghi riêng từng trạng thái):

## Tri thức tái sử dụng

<!-- Theo docs/agents/issue-tracker.md#selective-closeout: ghi “Không có”, hoặc file đã cập nhật + nguồn bằng chứng, hoặc đề xuất ngoài phạm vi cần duyệt. Sửa nhỏ, an toàn trong phạm vi đã duyệt không cần xin duyệt riêng từng bài học. -->

## Rủi ro hoặc lưu ý còn lại

<!-- Đối chiếu từng điều kiện với bằng chứng: đạt, không đạt hoặc chưa kiểm chứng. Nêu đánh đổi, lý do bỏ qua kiểm tra không liên quan và nhận định chưa được chứng minh; thiếu bằng chứng bắt buộc thì chưa hoàn tất. Ghi rõ rủi ro, giới hạn hoặc việc cần theo dõi; nếu không có, ghi “Không có”. -->
