# Thiết kế chính sách phiên trình duyệt

Trạng thái: **Đề xuất R1**, chờ duyệt trước triển khai.
[Yêu cầu](../specs/browser-session-persistence.md) sở hữu hành vi/thời hạn và tiêu chí;
[nghiên cứu](../research/session-persistence-keycloak.md) sở hữu dẫn chứng Keycloak 26.3.3;
[kế hoạch](../plans/browser-session-persistence.md) sở hữu thứ tự sửa và kiểm chứng.
Issue: [#230](https://github.com/NhiBuaa/knora-agent/issues/230).
Khảo sát mã trên `9d5f8435afca5e5fa38b93426a7ebc674be71cfc`.

## 1. Lựa chọn kiến trúc

| Phương án | Chi phí/giới hạn | Quyết định |
| --- | --- | --- |
| Chỉ tăng timeout realm | Trần 8 giờ và cookie Knora chưa phân biệt mode; bỏ sót recovery/realm tồn tại | Không đáp ứng yêu cầu |
| Realm + BFF cap 30 ngày chung, dựa refresh expiry | Ít mã hơn nhưng không biết khi nào phải tạo session cookie; không độc lập giữ normal max 8 giờ | Không chọn |
| Mapper ID token mode + mốc SSO trong provider sẵn có | Một class Java, service registration, fixture/migration và tests; không thêm dịch vụ/dependency | **Chọn** |

Keycloak sở hữu lựa chọn người dùng, idle và phiên SSO. BFF xác minh ID token rồi lưu
policy và deadline trong JWE HttpOnly. BFF còn chặn độc lập idle/max, không suy mode từ
độ dài refresh token, `auth_time`, query hoặc browser storage. Không thêm kho phiên trung tâm.

```mermaid
sequenceDiagram
  participant U as Người dùng
  participant K as Keycloak 26.3.3
  participant B as Next BFF
  participant A as FastAPI
  U->>K: Form native + lựa chọn Remember Me
  K-->>B: Code → tokens + ID token ký mode/mốc SSO
  B->>B: Verify issuer/audience/nonce, tính deadline cố định
  B-->>U: JWE HttpOnly; session cookie hoặc persistent cookie
  U->>B: Yêu cầu sử dụng thật
  opt Access token còn ≤30 giây
    B->>K: Refresh, không thay mốc/mode
    K-->>B: Token mới hoặc invalid_grant/lỗi tạm
  end
  B->>A: Bearer còn hạn + kiểm tra identity của nháp nếu gửi chat
  A-->>U: Kết quả qua BFF
```

## 2. Claim và cấu hình do Keycloak sở hữu

Thêm `KnoraSessionPolicyMapper` trong provider Maven hiện hữu, đăng ký
`org.keycloak.protocol.ProtocolMapper`, provider ID **`knora-session-policy`**. Mapper
chỉ triển khai `OIDCIDTokenMapper`: `knora_remember_me:boolean` từ
`UserSessionModel.isRememberMe()` và `knora_session_started_at:integer` từ `getStarted()`.
Không có config tùy ý hoặc user attribute. Không phát claim khi phiên null/offline/start≤0.
BFF từ chối token thiếu claim; không chọn fallback dài hoặc âm thầm hạ mode.

Client `knora-web` có đúng một mapper tên `knora-session-policy`, protocol
`openid-connect`, protocolMapper `knora-session-policy`, consentRequired false, config `{}`.
Không phát thêm lên access token/userinfo. Kiểm tra cả code exchange và refresh thật có
hai claim; việc JAR build thành công không chứng minh mapper được nạp.

Realm projection chính xác nằm bảng §1 của nghiên cứu. Cả hai fixture
`test/fixtures/keycloak/{dev-realm,figma-realm}.json` phải có projection đó. Trên
`knora-web`, bỏ override `client.session.idle.timeout` và
`client.session.max.lifespan`, đặt `access.token.lifespan="300"`; giữ nguyên các
attribute/mapper khác và refresh-token rotation. Realm client idle/max =0 để kế thừa.

Thay hai checkbox native bằng biểu thức kiểm tra POST có password và giá trị `on`
được mô tả trong nghiên cứu. Chỉ kiểm tra sự có mặt, không render password. Không đổi
bố cục, component, nhãn `msg("rememberMe")` hoặc đường đăng ký/OTP. Tái dùng macro
`field.checkbox` kế thừa từ theme Keycloak, không sao chép `field.ftl` vào repository.
Thời hạn và lưu ý máy dùng chung được ghi trong mục phiên của runbook; không thêm
component hoặc tài nguyên chỉ để trang trí form.

## 3. Định dạng BFF v2 và các phép tính

Cookie mới tên **`knora_session_v2`**. `knora_session` chỉ được xóa, không đọc hoặc chuyển
đổi. Tên mới ngăn phiên dài bị decoder của bản cũ đọc nhầm khi rollback. Không thay khóa
toàn hệ thống, không logout toàn realm. Phiên Keycloak online cũ còn hợp lệ có thể SSO
về v2 ở chế độ/mốc hiện có; không được nâng Remember Me tự động.

`KnoraSession` mới có các trường bắt buộc:

```typescript
type SessionPolicy = {
  policyVersion: 1;
  rememberMe: boolean;
  sessionStartedAt: number;
  sessionExpiresAt: number;
};
type KnoraSession = SessionPolicy & {
  issuer: string;
  subject: string;
  accessToken: string;
  refreshToken: string;
  workspaceIds: string[];
  capabilities: string[];
  expiresAt: number;
  refreshExpiresAt: number;
  sessionId: string;
};
```

Policy version là phiên bản nội dung, v2 là tên cookie. Không thêm option/env để đổi
duration. Một module thuần `frontend/lib/auth/session-policy.ts` sở hữu constants,
kiểm tra policy và deadline để session/refresh không có fallback khác nhau.

- Nhận claim sau `jwtVerify` hiện có; issuer/audience/RS256/nonce ở callback giữ nguyên.
  `rememberMe` phải boolean; start phải safe integer >0, không ở tương lai quá 30 giây.
- `sessionExpiresAt = sessionStartedAt + (rememberMe ? 2592000 : 28800)`;
  từ chối nếu phép cộng không safe integer hoặc deadline ≤now. Không lấy callback now
  làm mốc mới, không dùng `auth_time`/`iat` thay thế.
- `expires_in` và `refresh_expires_in` phải safe integer >0; `expires_in≤300`.
  Chuỗi rỗng/token thiếu/số âm/string/NaN/Infinity đều không là phiên hợp lệ.
- Ghi thời điểm ngay **trước** token request là `requestedAt`. Sau response xác minh,
  `expiresAt=min(requestedAt+expires_in,sessionExpiresAt)`;
  `refreshExpiresAt=min(requestedAt+refresh_expires_in,requestedAt+idle,sessionExpiresAt)`.
  Kiểm tra cộng safe integer và deadline còn >now sau request. Lấy mốc trước request
  bảo thủ với độ trễ; không cộng thêm thời gian gọi mạng vào quyền sử dụng token.
- Callback tạo `sessionId=randomUUID()` đúng một lần. Refresh giữ nguyên sessionId,
  start, mode và max. ID token refresh phải khớp issuer, subject, mode, start;
  khác/mất/sai policy sau verify là phiên bị từ chối (null), không fallback quyền dài.
- `encodeSession(session:KnoraSession)` không tạo defaults. Chỉ JWE dir/A256GCM;
  `exp=min(refreshExpiresAt,sessionExpiresAt)`; cả hai expiry của access/refresh không
  vượt max. `decodeSession` kiểm tra đủ schema/policy, configured issuer, expiries và
  exp này sau giải mã; từ chối HS256 và mọi định dạng cũ.
- Cookie: HttpOnly, SameSite=Lax, Path=/, Secure khi production. Normal **không**
  `Max-Age`/`Expires`. Remember Me: `maxAge=max(0,min(refreshExpiresAt,sessionExpiresAt)-now)`.
  Không cố định cookie 30 ngày bất kể idle. Kiểm tra Set-Cookie đầy đủ <4.096 byte.

`sessionCookie(value:string,session:KnoraSession)` thay chữ ký cũ; cập nhật đủ ba caller:
`getSession(true)`, middleware, callback. `clearSessionCookie()` xóa v2;
`clearLegacySessionCookie()` xóa tên cũ. Callback/logout/middleware/session-route có cookie
cũ thì xóa; nơi SSR read-only không ghi cookie. Cookie hỏng/hết hạn được xóa ở response
có quyền ghi, trả null/401 hoặc redirect login phù hợp.

## 4. Gia hạn, lỗi và logout

Giữ Node middleware renew trước SSR và ghi cả request lẫn response cookie. SSR chỉ đọc,
không tiêu thụ refresh token. Các BFF/operator/workspace-selection callers dùng
`getSession(true)`, không thêm refresh thứ hai ở browser/client API.

Trước khi trả access token còn hạn cũng phải kiểm tra cap, refresh deadline và revoked
sessionId. Check lại revoked **sau** promise refresh và sau await mã hóa, ngay trước
cookie write đồng bộ qua `isSessionRevoked(sessionId:string):boolean` của cùng coordinator,
giữ logout thắng renew đồng thời. Revocation map hết hạn theo `sessionExpiresAt` thật, không fallback8h.
Cache refresh vẫn single-flight hash refresh-token, 30 giây, tối đa256 entries, timeout10s.

| Kết quả | Xử lý BFF |
| --- | --- |
| Thiếu/hết/hỏng v2, cap/refresh expiry hết, revoked, invalid_grant | null; xóa cookie; API401 / session JSON null / protected-page redirect |
| Verified identity hoặc policy đổi/sai | null, không cấp token hay nâng mode |
| Network, timeout, 429/5xx, token response sai kiểu, JWKS tạm không sẵn sàng | Không ghi cookie/deadline mới. Có thể dùng access cũ còn hạn theo cơ chế hiện tại; nếu không thì503 `SESSION_REFRESH_UNAVAILABLE` |
| Cookie parse/decrypt sai | null, không log payload |

Không retry tự động mutation. Hết cookie idle không được “cứu” bằng cách giải mã bỏ qua
JWE exp. Auth/session luôn `Cache-Control:no-store`, trả đúng
`{session:null}` hoặc `{session:{issuer,subject,workspaceIds,capabilities}}`, không token,
sessionId, refresh expiry hoặc secret. Lỗi refresh tạm trả503 thay vì null.

Logout giữ same-origin check, local invalidation trước Keycloak, xóa cả hai cookie và
workspace preference. Không thêm kênh cross-tab mới. Tab khác phát hiện khi được dùng
lại/request tiếp; không hứa xóa UI mọi tab tức thời. Sau restart Next, revoke map cục bộ
có thể mất; Keycloak logout và giới hạn access300s vẫn là ranh giới đã chốt. Không bật
nhiều Next replica/rotation mới từ kết quả issue này.

## 5. Khôi phục tab chat và chặn đổi danh tính giữa probe/POST

Dùng `PanelIdentityScope {issuer,subject}` đã có, không domain identity mới. Cả page
existing Conversation và hub/draft truyền issuer+subject từ session v2. Component
presentational có thể thiếu identityScope trong fixture, nhưng không được gửi mutation
hoặc khôi phục một nháp không có baseline tin cậy. Key remount thêm issuer+subject để
SSR chuyển account không dùng lại state cũ.

Trong `ConversationViewState`, thêm một recovery promise và cờ kiểm tra identity:

1. `blur` hoặc `visibilitychange→hidden` đánh dấu một lượt rời tab. Khi visible và focus
   trở lại, gom focus/visibility bằng một microtask hoặc timeout0 rồi chạy một recovery
   promise. Không interval. Nút Retry gọi cùng promise. Dedupe các sự kiện của cùng lượt;
   chỉ một probe cho một lượt trở lại, kể cả khi phiên vẫn hợp lệ.
2. Khóa submit trong khi probe; tăng generation để response history/poll/POST cũ không
   cập nhật state sau khi đã rời identity context. GET `/api/auth/session` no-store.
3. Null/401: giữ nháp/key, freeze polling, hiện đăng nhập ở tab mới và Retry.
   Network/503: giữ nháp, thông báo lỗi tạm và nút Retry; không tự loop/focus retry vô hạn.
4. Khác issuer/sub hoặc thiếu baseline: đặt cờ `identityChanged`, render trạng thái rỗng
   thay toàn bộ panel/history/rail; xóa draft, turns, cursor, selection, keys và refs;
   `window.location.replace('/workspaces')`. Nếu điều hướng lỗi vẫn không render dữ liệu cũ.
5. Cùng identity: gọi đúng một GET lịch sử hiện hành; draft mới chưa có Conversation thì
   GET Workspace để kiểm tra quyền. Sau GET thành công mới mở khóa/resume pending Turn
   poll. Giữ draft, creationKey, submitKey. Không `router.refresh()` làm mất nháp.
6. Generation/mounted guard bao mọi bước và finally; response cũ không tắt busy của lượt
   mới. History403 là mất quyền, khóa gửi và báo lỗi; không coi đăng nhập lại sẽ cấp quyền.

Probe browser không đóng được race cookie đổi ngay trước POST. Vì vậy hai POST của
composer (create Conversation và submit Turn) luôn thêm:

```text
X-Knora-Expected-Issuer: <identityScope.issuer>
X-Knora-Expected-Subject: <identityScope.subject>
```

Generic BFF so hai header với session đã renew trước đọc body/gọi API khi có một trong
hai header. Riêng POST đúng `/v1/workspaces/{id}/conversations` hoặc
`/v1/workspaces/{id}/conversations/{id}/turns` bắt buộc có đủ cả hai. Thiếu/mismatch →401
`{detail:"SESSION_IDENTITY_MISMATCH"}`, no-store, **không xóa phiên mới đúng của account
khác**. Component gọi recovery trên lỗi này, không retry POST. Strip hai header trước
forward. Mọi request từ ConversationView (history, Workspace recovery, poll, loadMore,
retry/restore và hai POST) đều gửi cặp header này; GET history cũng không thể nhận
response của account vừa đổi giữa probe và GET. Chúng chỉ thêm điều kiện từ chối, không cấp quyền/đổi Bearer; backend vẫn
authorize Workspace/capability như cũ. Các route/operator/evaluation khác giữ nguyên.

## 6. Managed migration, rollout và rollback

Script mới `scripts/configure-keycloak-session-policy.ps1` theo mẫu guard của
`configure-keycloak-auth-flow.ps1`; Inspect/Diff chỉ đọc, Apply/Rollback có guard target,
project/container/port và snapshot. Không gắn Apply vào daily startup.

- Chỉ target loopback `knora-dev` tại8180 hoặc harness tại8380 theo project pattern
  hiện hữu. Resolve đúng một client `knora-web`. Realm/admin hoặc client lạ →dừng.
- Quản lý đúng realm projection ở §2, ba client attribute ở §2 và mapper đã nêu.
  Không chỉnh offline settings, OTP, SMTP, roles, flows, redirect hoặc client khác.
- Snapshot projection trước và desired, target, client UUID, mapper ID/nội dung và
  trạng thái có/không của từng attribute; không toàn realm, không secret.
- Read-again trước từng write và so projection dự kiến; dùng maintenance window độc
  quyền cho target vì REST không có atomic CAS nhiều đối tượng. Mất exclusivity →dừng.
- Provider phải được build/nạp trước Apply. Từ chối conflict mapper cùng tên/provider,
  mapper khác phát cùng hai claim, hoặc script không chứng minh mapping vô xung đột.
- Apply theo thứ tự mapper → client overrides → realm. Partial PUT realm; client PUT
  merge attributes hiện tại để giữ key không quản lý; mapper qua model API riêng.
  GET readback sau từng bước và cuối. Apply lần hai no-op, không overwrite snapshot.
- Lỗi giữa chừng ghi sanitized progress receipts vào snapshot đồng hành; không tự
  rollback các bước của owner khác. Rollback explicit đảo bước đã áp, kiểm tra current
  khớp after projection của mỗi bước; đã về before thì no-op; drift →dừng.
- Rollout existing realm: maintenance window, snapshot → provider → policy Apply +
  readback → BFF mới → login thử hai mode. Người dùng nhận v2 qua signin/SSO, không
  chuyển cookie cũ. Không logout toàn realm.
- Rollback phối hợp: chặn traffic mới trong maintenance; về BFF cũ, rollback policy
  projection, về image provider/theme cũ, kiểm tra login thường; trình duyệt v2 phải
  đăng nhập lại. Decoder cũ không đọc tên v2 nên không tiếp nhận phiên30d. Cookie v2
  còn trên browser không có quyền ở bản cũ, không cần đổi secret hay delete volume.

Production/realm ngoài exact local guards là gói triển khai riêng, không mở parameter
để script này âm thầm sửa mọi issuer. Kế hoạch không cấp quyền deploy.

## 7. Bằng chứng và giới hạn

Các case A1–A11 ánh xạ tasks trong kế hoạch. Giữ nguyên required CI; runtime targeted
không thay profile release, profile application hiện hữu không thay expiry tests.
Không gọi provider AI, cần worker hay đánh giá chất lượng câu trả lời cho auth issue.
Không đo/khẳng định tăng tốc hoặc usability từ số dòng/test xanh. Cookie/token/nháp
không vào screenshots/logs/traces/video/report; mask form theo harness hiện hữu.
