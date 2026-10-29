# Duy trì phiên đăng nhập — nghiên cứu nguồn Keycloak

Ngày: 2026-10-30. Phục vụ [Issue #230](https://github.com/NhiBuaa/knora-agent/issues/230).
Đối tượng triển khai: Keycloak **26.3.3**, tương ứng `keycloak.version` trong
`infra/keycloak/providers/email-otp-reset/pom.xml`. Đây là nghiên cứu và đề xuất thiết kế;
không phải bằng chứng đã triển khai hoặc đã chạy thử phiên bản mới.

## Phương pháp và giới hạn

Đã dùng Context7 `resolve-library-id` cho Keycloak, sau đó `query-docs` trên
`/keycloak/keycloak/26.3.2` (bản gần nhất được liệt kê) và `/keycloak/keycloak` để đối chiếu
tài liệu hiện hành. Các kết luận dưới đây được kiểm lại bằng **mã nguồn và tài liệu ghim
tag 26.3.3**, không lấy hành vi ở nhánh `main` áp cho bản đang dùng. Không đổi cấu hình
realm, gọi token endpoint hay chạy lại phép đo nghỉ thực tế trong lượt nghiên cứu này.

## 1. Idle, thời hạn tối đa và thời hạn token là ba giới hạn khác nhau

`SSO Session Idle` được đặt lại khi có yêu cầu xác thực hoặc đổi refresh token. `SSO
Session Max` là thời hạn tuyệt đối của phiên. Remember Me có idle/max riêng; giá trị
không dương dùng cấu hình thường. Mã 26.3.3 thực tế lấy **giá trị lớn hơn giữa cấu hình
thường và Remember Me** cho phiên được ghi nhớ. Vì vậy không cấu hình Remember Me ngắn
hơn thường rồi kỳ vọng nó thắng.
[Tài liệu timeout 26.3.3](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_admin/topics/sessions/timeouts.adoc),
[SessionExpirationUtils](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/models/utils/SessionExpirationUtils.java).

Client idle/max có thể ghi đè cấu hình realm và làm phiên được ghi nhớ hết sớm. Với client
đích, chọn realm `clientSessionIdleTimeout=0`, `clientSessionMaxLifespan=0`, và không có
client attribute dương `client.session.idle.timeout` hoặc `client.session.max.lifespan`.
Khi đó cả hai chế độ thừa hưởng đúng idle/max tương ứng của SSO. Max của client luôn bị
chặn bởi max của phiên SSO cha.
[Thuật toán client timeout](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/models/utils/SessionExpirationUtils.java),
[tên attribute chính xác](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/protocol/oidc/OIDCConfigAttributes.java).

Refresh token có `exp = min(client idle deadline, client/session absolute deadline)`.
Token response trả `refresh_expires_in = refreshToken.exp - thời gian máy chủ hiện tại`.
Access token dùng lifespan realm/client rồi cũng bị chặn bởi max của phiên.
`refresh_expires_in` là **thời gian còn lại**, không phải thời hạn ban đầu hoặc bằng chứng
người dùng đã chọn Remember Me. Phiên được ghi nhớ gần ngày thứ 30 cũng có thể chỉ còn
vài phút.
[TokenManager.getExpiration, build và getTokenExpiration](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/TokenManager.java).

Ghi chú “cộng hai phút cho idle” trong tài liệu 26.3.3 chỉ áp dụng khi persistent user
sessions không hoạt động. Không mặc định cộng hai phút vào hợp đồng BFF; BFF chặn theo
deadline token đã nhận. Kết quả thực tế cần ghi rõ cấu hình persistent sessions của đích.
[Ghi chú idle chính thức](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_admin/topics/sessions/timeouts.adoc).

### Các giá trị chính sách đã được người dùng chốt

| Trường realm | Giá trị |
| --- | ---: |
| `rememberMe` | `true` |
| `ssoSessionIdleTimeout` | `1800` |
| `ssoSessionMaxLifespan` | `28800` |
| `ssoSessionIdleTimeoutRememberMe` | `604800` |
| `ssoSessionMaxLifespanRememberMe` | `2592000` |
| `clientSessionIdleTimeout` | `0` |
| `clientSessionMaxLifespan` | `0` |
| `accessTokenLifespan` | `300` |

Không xin `offline_access`, không dùng offline token và không thêm heartbeat để kéo dài
phiên. Idle ở đây là không còn yêu cầu xác thực/refresh; đây không phải phép đo thao tác
chuột hoặc bàn phím.

## 2. Cookie và lựa chọn mặc định trên form

Keycloak bật `rememberMe` để hiện checkbox. Với phiên thường, identity cookie là session
cookie; với phiên được ghi nhớ, cookie đó có Max-Age. `KEYCLOAK_REMEMBER_ME` là gợi ý tên
đăng nhập, không phải bằng chứng quyền sử dụng phiên cho BFF.
[Tài liệu Remember Me](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_admin/topics/login-settings/remember-me.adoc),
[AuthenticationManager.createLoginCookie/createRememberMeCookie](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/services/managers/AuthenticationManager.java).

Native `UsernamePasswordForm.authenticate` tự điền `rememberMe=on` nếu có gợi ý tên từ
cookie Remember Me cũ. Điều đó xung đột với quyết định **mọi form đăng nhập mới mặc định
không chọn**, dù trước đó đã chọn. Tuy nhiên phải giữ lựa chọn vừa gửi khi đăng nhập sai.
[UsernamePasswordForm](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/authenticators/browser/UsernamePasswordForm.java).

Có thể sửa riêng hai checkbox hiện hữu trong `themes/knora/login/login.ftl` thành:

```ftl
<@field.checkbox name="rememberMe" label=msg("rememberMe")
    value=(login.password?? && (login.rememberMe!'')?lower_case == 'on') />
```

Đây là kiểm tra **sự có mặt** của trường password, tuyệt đối không xuất nội dung password
ra HTML. Initial form chỉ có username/rememberMe gợi ý. `AuthenticationProcessor.Result.form`
đưa decoded form parameters của POST vào `LoginBean`, kể cả password rỗng; các challenge
đăng nhập sai dùng lại provider đó. Vì vậy cách trên giữ lựa chọn đã gửi cho sai mật khẩu,
tên không tồn tại, khóa do brute force hoặc tài khoản bị vô hiệu hóa. Chỉ dùng
`messagesPerField.existsError('username','password')` sẽ bỏ sót lỗi toàn form như tài khoản
bị vô hiệu hóa. Test render phải dùng password sentinel và khẳng định nó không có trong HTML.
So sánh `on` không phân biệt hoa/thường khớp điều kiện native; giá trị lạ không hiện là đã chọn.
[AuthenticationProcessor.Result.form](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/AuthenticationProcessor.java),
[LoginBean](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/forms/login/freemarker/model/LoginBean.java),
[AbstractUsernameFormAuthenticator](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/authenticators/browser/AbstractUsernameFormAuthenticator.java).

Đây là thiết kế cho form username/password hiện hữu. Silent SSO không hiện form nên giữ
nguyên chế độ của phiên SSO; checkbox không âm thầm đổi chế độ cho một phiên đang tồn tại.
Session cookie không phải lời hứa trình duyệt sẽ luôn xóa sau khi đóng: khả năng phục hồi
phiên của trình duyệt phụ thuộc trình duyệt. Nút Đăng xuất mới là thao tác kết thúc phiên
chủ động; không mô tả đóng tab thành đăng xuất.
[Luồng gắn phiên hiện hữu](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/AuthenticationProcessor.java),
[MDN Set-Cookie: session restore](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#expiresdate).

## 3. BFF cần nhận chế độ từ token đã xác thực

`UserSessionModel.isRememberMe()` là thuộc tính riêng; nó không tự trở thành user-session
note. Mapper native `UserSessionNoteMapper` chỉ đọc `userSession.getNote(name)`; tạo mapper
note tên `rememberMe` không đọc được thuộc tính này. `IDToken` không định nghĩa một claim
Remember Me mặc định.
[UserSessionModel](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi/src/main/java/org/keycloak/models/UserSessionModel.java),
[UserSessionNoteMapper](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/mappers/UserSessionNoteMapper.java),
[IDToken](https://github.com/keycloak/keycloak/blob/26.3.3/core/src/main/java/org/keycloak/representations/IDToken.java).

`auth_time` có mapper native, nhưng là thời điểm xác thực, không phải chế độ Remember Me.
`AuthenticationManager` cập nhật note này sau xác thực không phải SSO; nó không phải mốc
`userSession.getStarted()` bất biến của phiên đang được dùng. Không lấy `iat`, `auth_time`,
cookie đọc được bằng JavaScript, query parameter hoặc độ dài `refresh_expires_in` làm bằng
chứng chọn chế độ.
[OIDCLoginProtocolFactory: auth_time mapper](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/OIDCLoginProtocolFactory.java),
[AuthenticationManager: cập nhật AUTH_TIME](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/services/managers/AuthenticationManager.java).

### So sánh hai cách

| Cách | Đúng trong điều kiện nào | Hạn chế |
| --- | --- | --- |
| BFF chỉ cap 30 ngày và tin `refresh_expires_in` | Realm/client được quản lý đúng; expiry của Keycloak luôn chặn cả hai chế độ | Không phân biệt session cookie của chế độ thường; không tự bảo vệ max 8 giờ khi realm bị cấu hình sai; không đáp ứng yêu cầu cookie đã chốt |
| Mapper ID token ký mode + mốc tạo phiên | BFF xác thực issuer/audience/signature và kiểm tra kiểu/giá trị claim | Thêm một mapper nhỏ trong JAR sẵn có, cần kiểm thử SPI và rollout phối hợp |

**Chọn mapper ID token** vì yêu cầu session cookie khi không chọn Remember Me. Không thêm
dịch vụ hoặc dependency mới. Chỉ mapper gắn trên client Knora; không cho input người dùng
hay user attribute ghi đè các claim này.

### Hợp đồng mapper được đề xuất

- Class mới: `com.knora.keycloak.reset.KnoraSessionPolicyMapper` trong provider Maven hiện hữu.
- Provider ID: `knora-session-policy`.
- Claim ID token: `knora_remember_me` là boolean JSON; `knora_session_started_at` là số nguyên
  giây Unix lấy từ `UserSessionModel.getStarted()`.
- Chỉ phát trên ID token của phiên online. Không thêm lên access token, userinfo hoặc token
  response không ký.
- BFF lấy mode/cap chỉ **sau** xác thực ID token. Missing/malformed claim từ chối phiên mới;
  không tự nâng cấp bằng fallback thời gian dài.
- Refresh hợp lệ có ID token mới khi scope ban đầu là OIDC (`openid`); mapper được chạy lại.
  BFF phải kiểm tra mode/mốc khớp với session đã lưu, không đặt lại cap theo thời điểm refresh.
[TokenManager.refreshAccessToken/generateIDToken](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/TokenManager.java).

Chữ ký SPI chính xác ở 26.3.3:

```java
public final class KnoraSessionPolicyMapper extends AbstractOIDCProtocolMapper
        implements OIDCIDTokenMapper {
    @Override
    public IDToken transformIDToken(
            IDToken token,
            ProtocolMapperModel model,
            KeycloakSession session,
            UserSessionModel userSession,
            ClientSessionContext clientSession) {
        if (userSession == null || userSession.isOffline() || userSession.getStarted() <= 0) {
            return token;
        }
        token.getOtherClaims().put("knora_remember_me", userSession.isRememberMe());
        token.getOtherClaims().put("knora_session_started_at", userSession.getStarted());
        return token;
    }
}
```

Đây là phần lõi, chưa phải class đầy đủ. Metadata bắt buộc: `getId()` trả provider ID trên;
`getDisplayType()` trả `Knora session policy`; `getDisplayCategory()` trả `TOKEN_MAPPER_CATEGORY`;
`getHelpText()` giải thích hai claim; `getConfigProperties()` trả `List.of()`. Lifecycle và
`getProtocol()` đã có trong `AbstractOIDCProtocolMapper`. Dùng override trực tiếp
`transformIDToken` để mapper cố định không phụ thuộc một cờ cấu hình include-token ẩn.
[AbstractOIDCProtocolMapper](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/mappers/AbstractOIDCProtocolMapper.java),
[OIDCIDTokenMapper](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/mappers/OIDCIDTokenMapper.java).

Thêm dòng tên class đầy đủ vào resource mới
`src/main/resources/META-INF/services/org.keycloak.protocol.ProtocolMapper` của module hiện hữu.
Các dependency `keycloak-services`, core và SPI 26.3.3 đã có ở scope provided; không cần đổi POM.
Mapper của client trong realm JSON và migration có dạng:

```json
{
  "name": "knora-session-policy",
  "protocol": "openid-connect",
  "protocolMapper": "knora-session-policy",
  "consentRequired": false,
  "config": {}
}
```

Unit tests dùng fake `UserSessionModel` theo pattern test Java sẵn có, kiểm tra true/false,
integer started, null/offline/started không dương không phát claim, metadata/service loading.
Kiểm thử thật phải đi qua code exchange và refresh trên đúng image/JAR/realm; BFF xác thực
ID token và mới tạo session. Test đọc projection policy từ cookie synthetic JWE thật trong
memory chứng minh mapper có tác dụng qua BFF mà không thêm endpoint lộ ID token. Kết hợp
unit test bắt buộc verify signature/issuer/audience/nonce; không gọi cách này là thanh tra
raw ID-token payload. Unit test mapper trực tiếp không chứng minh Keycloak đã nạp provider.

## 4. Thay import fixture không cập nhật realm đang có

Startup `--import-realm` bỏ qua realm đã tồn tại. Không dùng xóa realm, xóa volume hoặc import
`--override` làm migration cho thay đổi này. Admin `PUT /admin/realms/{realm}` nhận
`RealmRepresentation`; mã cập nhật các trường timeout/rememberMe khi chúng khác null.
Vì vậy dùng PATCH theo nghĩa nghiệp vụ bằng **PUT body chỉ chứa trường thuộc quyền quản lý**,
không gửi lại export đầy đủ có SMTP/secrets/user/client khác.
[Import/export 26.3.3](https://github.com/keycloak/keycloak/blob/26.3.3/docs/guides/server/importExport.adoc),
[RealmAdminResource.updateRealm](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/services/resources/admin/RealmAdminResource.java),
[DefaultExportImportManager.updateRealm](https://github.com/keycloak/keycloak/blob/26.3.3/model/storage-private/src/main/java/org/keycloak/storage/datastore/DefaultExportImportManager.java).

Migration cần preflight realm/client identity, giá trị trước, provider ID đã nạp, mapper trùng
tên/ID và client timeout overrides. Chỉ sửa sau khi owner cho phép đúng đích. Ghi snapshot
allowlist không chứa secret; PUT các trường ở bảng, thêm mapper client; đọc lại rồi so sánh.
Không coi HTTP 204 riêng lẻ là đã đúng. Khi rollback chỉ phục hồi đúng trường/mapper thuộc
migration sau khi so sánh trạng thái hiện tại còn khớp giá trị migration đã ghi; có drift thì
dừng để tránh ghi đè thay đổi của owner khác.

Có thể tạo UUID mapper ở phía script trước snapshot rồi gửi trong representation:
`RepresentationToModel.toModel` giữ rep.id, `ClientAdapter.addProtocolMapper` dùng ID
được cấp khi khác null. Điều này cho snapshot biết đúng ID để kiểm rollback dù API tạo
mapper thành công nhưng lượt chạy mất trước khi ghi receipt.
[RepresentationToModel26.3.3](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/models/utils/RepresentationToModel.java#L912-L919),
[ClientAdapter26.3.3](https://github.com/keycloak/keycloak/blob/26.3.3/model/jpa/src/main/java/org/keycloak/models/jpa/ClientAdapter.java#L397-L412).

Người dùng đã chấp nhận một lần đăng nhập lại để bỏ toàn bộ cookie cũ. Thiết kế BFF vì vậy
có thể từ chối JWE/HS256 cũ không có policy version mới; không cần migration nội dung cookie.
Đây là quyết định trong hội thoại, không phải hành vi native của Keycloak. Rollback cũng
phải đánh giá cookie version/cap hiện tại; khôi phục riêng realm không tự biến một cookie
BFF dài hạn đang có thành session cookie.

## 5. Những gì nguồn này không chứng minh

- Chưa biên dịch mapper hoặc chạy thử cấu hình mới; kế hoạch phải cung cấp kiểm thử cụ thể.
- Chưa đánh giá hạ tầng nhiều tiến trình BFF hoặc bổ sung back-channel logout. Người dùng
  chấp nhận cửa sổ tối đa 5 phút cho thu hồi phiên bên ngoài theo access-token lifespan.
- Theo quyết định mới trong hội thoại, tiêu chí ngủ/thức máy đã được bỏ khỏi Issue #230;
  không thay bằng mô phỏng rồi gọi đó là bằng chứng ngủ/thức thực tế.

## 6. Ranh giới cookie của Next.js 15

Đã tra Context7 riêng Next.js15 (`/websites/nextjs/15`) sau resolve-library-id. API cookies
là async. Server Component đọc được request cookie nhưng không set/delete; ghi cookie ở
Route Handler/Server Action hoặc NextResponse middleware. Vì vậy giữ kiến trúc renew trong
Node middleware trước SSR và ghi request/response cookie, không chuyển refresh vào render.
[cookies v15](https://nextjs.org/docs/15/app/api-reference/functions/cookies),
[middleware cookies v15](https://nextjs.org/docs/15/app/api-reference/file-conventions/middleware#using-cookies).
