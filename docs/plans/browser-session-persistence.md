# Browser Session Persistence Implementation Plan

> **For agentic workers:** Thực hiện tuần tự bằng `executing-plans` nếu có trong catalog.
> Đọc spec và design trước Task 0. Đây là kế hoạch giao Antigravity, không phải lệnh
> triển khai ngay; không tự phân phối sang chat người dùng khác hoặc tự sửa stack dùng chung.

**Goal:** Giữ đăng nhập theo lựa chọn người dùng và khôi phục tab chat an toàn sau thời
gian nghỉ, theo [Issue #230](https://github.com/NhiBuaa/knora-agent/issues/230).

**Architecture:** Keycloak phát mode và mốc phiên SSO trong ID token ký qua mapper nhỏ
trong JAR hiện hữu. Next BFF lưu policy/deadline cố định trong cookie JWE v2, gia hạn khi
có nhu cầu và chặn identity đổi trước forward request của chat. UI giữ nháp trong tab.

**Tech Stack:** Keycloak 26.3.3 / Java21 / Maven hiện hữu; Next15 / React18 / jose5 /
TypeScript; Vitest4 / Playwright1.63; PowerShell7 / pytest cho managed configuration.
Giữ version thực tế của lockfile/POM; không nâng dependency trong nhiệm vụ này.

**Spec:** [browser-session-persistence.md](../specs/browser-session-persistence.md).
**Design:** [browser-session-policy.md](../design/browser-session-policy.md).
**Primary research:** [session-persistence-keycloak.md](../research/session-persistence-keycloak.md).

## Global Constraints

- Normal: idle **1800**, max **28800** giây, session cookie. Remember Me: idle **604800**,
  max **2592000** giây, persistent cookie. Access **300**, refresh threshold **30** giây.
- Form mới unchecked; retry giữ lựa chọn vừa gửi. SSO còn hạn giữ mode/mốc cũ.
- Không heartbeat, offline_access, tự replay POST, hoặc lưu nháp ngoài bộ nhớ tab.
- Cùng issuer+subject thì giữ nháp; đổi một trong hai thì xóa và về `/workspaces`.
- Chấp nhận đăng nhập lại một lần khi dùng cookie v2; không chuyển cookie cũ sang dài hạn.
- Thu hồi ngoài Knora có cửa sổ access tối đa300s; một tiến trình Next. Không thêm Redis,
  introspection/backchannel hoặc nhiều replica; giữ nguyên refresh-token rotation hiện có.
- **Không có tiêu chí sleep/wake**, kể cả yêu cầu thử thật hoặc mô phỏng riêng cho nó.
- Giữ backend ownership/capability/API-key, OTP/SMTP, provider/model, redirects và theme
  identity. Không sửa generated OpenAPI vì thay đổi chỉ là hợp đồng nội bộ BFF.
- Không dùng dữ liệu/profile/cookie của người dùng. Không secret/token/password/draft
  trong Git, command output, report, screenshot, trace/video hoặc URL được lưu.
- Không merge/deploy/activation môi trường dùng chung nếu chưa có quyền đúng target.
  Không tái dùng grant chẩn đoán40 phút đã hết.

## 0. Đầu vào, đích và quyền thực hiện

Nguồn khảo sát: `9d5f8435afca5e5fa38b93426a7ebc674be71cfc`.
Bản tài liệu R1 hiện ở nhánh `docs/session-persistence-design`, worktree
`C:\Developer\Projects\knora-agent-worktree\docs-session-persistence-design`.
Full SHA tài liệu được duyệt phải lấy từ bàn giao/câu trả lời duyệt, không thay bằng SHA
nền trên hoặc tự coi tip mới nhất là được duyệt.

- [ ] Đọc `AGENTS.md`, `CONTEXT.md`, domain/issue-tracker, architecture, hai module-seams,
  CI verification contract, agent-environment và Feature Map tại revision được giao.
- [ ] Xác minh phê duyệt **bộ R1** và giao việc triển khai. Nếu chỉ có duyệt thiết kế mà
  chưa giao thực hiện, dừng trước sửa code; nói chính xác còn thiếu quyền triển khai.
- [ ] Lập worktree `C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence`,
  nhánh `fix/browser-session-persistence` từ **commit tài liệu được duyệt** (đã bao gồm
  nền khảo sát). Nếu đích đã có, chỉ tái dùng sau khi chứng minh thuộc Issue230; không
  reset/stash/chuyển nhánh/chiếm worktree. Native tool không hỗ trợ canonical container
  thì dùng Git theo policy, không di chuyển worktree do app quản lý.
- [ ] Tại đích chạy và đọc `git rev-parse --show-toplevel`, `git branch --show-current`,
  `git status --short`, `git worktree list --porcelain`; thông báo target/branch/task.
  So các file trong manifest §1 với nguồn khảo sát. Thay đổi upstream ảnh hưởng hợp đồng
  thiết kế cần chốt delta trước; không tự đổi thiết kế để né conflict.
- [ ] Kiểm tra CodeGraph status đúng đích; init/sync theo AGENTS, không dùng index primary.
  Tìm callers trước khi sửa. Kiểm tra Python/Node/Java/Maven/PowerShell và dependency
  trong worktree, không dùng node_modules junction của worktree khác hoặc tự cài host tools.

Hai gói quyền độc lập sau khi được giao implementation:

| Gói | Ranh giới đã thiết kế, cần người giao việc cho phép khi đến bước tương ứng |
| --- | --- |
| Local code/checks | Sửa đúng manifest; local format/unit/typecheck/lint/build; không DB thật hoặc provider |
| Disposable runtime | Một lượt mới tối đa90 phút, project/ports §8, synthetic users/volumes, image build theo Dockerfiles, đọc/ghi session-policy test trong realm riêng, không AI, cleanup trong reservation |

Thiếu gói runtime vẫn hoàn thành code/local checks độc lập rồi báo phần nghiệm thu còn
chờ; không tự chuyển sang port3000 hoặc sửa realm8180. Cài công cụ/dependency host,
published PR/Issue và activation existing realm là quyền riêng nếu chưa được giao.

## 1. Manifest và các hợp đồng không được tự đổi

Tất cả đường dẫn dưới đây tương đối với worktree implementation đã xác minh ở Task0.

| Task | Create | Modify / reuse |
| --- | --- | --- |
| 2 — Keycloak | `infra/keycloak/providers/email-otp-reset/src/main/java/com/knora/keycloak/reset/KnoraSessionPolicyMapper.java`; `src/test/java/com/knora/keycloak/reset/KnoraSessionPolicyMapperTest.java`; `src/main/resources/META-INF/services/org.keycloak.protocol.ProtocolMapper` trong cùng Maven module | `themes/knora/login/login.ftl`; `test/fixtures/keycloak/dev-realm.json`; `test/fixtures/keycloak/figma-realm.json`; `infra/keycloak/providers/email-otp-reset/src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java`; `frontend/tests/e2e/support/FigmaThemeRenderer.java` |
| 3 — Migration | `scripts/configure-keycloak-session-policy.ps1`; `backend/test/config/test_keycloak_session_policy.py` | Tái dùng pattern guard của `scripts/configure-keycloak-auth-flow.ps1`; không đổi daily startup |
| 4 — BFF policy | `frontend/lib/auth/session-policy.ts`; `frontend/tests/auth-session-policy.test.ts`; `frontend/tests/auth-session-route.test.ts` | `frontend/lib/auth/session.ts`; `frontend/lib/auth/session-refresh.ts`; `frontend/middleware.ts`; `frontend/app/api/auth/{callback,session,logout}/route.ts`; các auth unit tests |
| 5 — Identity boundary | `frontend/tests/conversation-identity-bff.test.ts` | `frontend/app/api/[...path]/route.ts`; giữ evaluation block/operator proxies; unit tests BFF liên quan |
| 6 — Recovery | Không module/hook auth toàn ứng dụng mới | `frontend/components/conversations/ConversationView.tsx`; `frontend/components/conversations/ConversationPanels.tsx` xác nhận hub chuyển identity xuống draft; `frontend/app/workspaces/[workspaceId]/conversations/page.tsx`; `frontend/app/workspaces/[workspaceId]/conversations/[conversationId]/page.tsx`; `frontend/tests/conversation-view.test.tsx`, `conversation-panels.test.tsx`, `conversation-page-workspace.test.tsx`, `conversation-copy.test.tsx` |
| 7/8 — E2E | `frontend/tests/e2e/session-persistence.spec.ts`; `frontend/tests/e2e/support/session-policy.ts` | `frontend/tests/e2e/support/figma-auth.ts`; offline renderer và fixture callers; không đổi default runtime profile/testMatch |
| 9 — Docs | Không ledger/ADR/glossary mới | Mục Browser session renewal của `docs/runbooks/local-development.md`; auth section `docs/development/feature-map.md`; links trong `docs/runbooks/agent-environment.md` |

Dockerfile/POM hiện hữu đã build JAR và có dependency SPI26.3.3: **không sửa** trừ khi
compile chỉ ra một lỗi factual của kế hoạch; khi đó báo delta và chỉ sửa trong thiết kế
đã duyệt, không nâng version. Không sửa backend business/security hoặc schema.

### Hợp đồng hàm mới

```typescript
// frontend/lib/auth/session-policy.ts — pure, no env/network/cookies
export type SessionPolicy = {
  policyVersion: 1;
  rememberMe: boolean;
  sessionStartedAt: number;
  sessionExpiresAt: number;
};
export const SESSION_POLICY_VERSION = 1;
export function policyFromClaims(
  claims: Record<string, unknown>, now: number,
): SessionPolicy; // throws Error("SESSION_POLICY_INVALID") on invalid claims
export function isSessionPolicy(value: unknown, now: number): value is SessionPolicy;
export function tokenDeadlines(
  policy: SessionPolicy, expiresIn: unknown, refreshExpiresIn: unknown,
  requestedAt: number, now: number,
): { expiresAt: number; refreshExpiresAt: number };
// tokenDeadlines throws Error("SESSION_TOKEN_RESPONSE_INVALID").
// session.ts: KnoraSession = SessionPolicy + required fields in design §3.
// encodeSession(session: KnoraSession): Promise<string>
// sessionCookie(value: string, session: KnoraSession): existing cookie result shape
// clearSessionCookie(): existing shape, name knora_session_v2
// clearLegacySessionCookie(): same shape, name knora_session
// session-refresh.ts: isSessionRevoked(sessionId: string): boolean
```

`isSessionPolicy` phải kiểm tra object, policyVersion===1, boolean, safe integer anchor,
anchor≤now+30, cap bằng **đúng** anchor+mode.max, cap>now. `tokenDeadlines` kiểm tra cả hai
duration và phép cộng trước khi clamp; yêu cầu resulting deadlines>now và
expiresAt≤refreshExpiresAt. Không export token/expiry ra browser session JSON.

## Task 2: Keycloak phát policy thật và hiện checkbox đúng

**Consumes:** Native online UserSessionModel26.3.3. **Produces:** Hai signed ID-token
claims trong design §2 ở code exchange và refresh; realm projection cố định.

- [ ] Thêm Java unit tests trước class, dùng JUnit5 và Proxy fake theo pattern hiện hữu:

```java
var online = (UserSessionModel) java.lang.reflect.Proxy.newProxyInstance(
        UserSessionModel.class.getClassLoader(), new Class<?>[]{UserSessionModel.class},
        (proxy, method, args) -> switch (method.getName()) {
            case "isOffline" -> false;
            case "isRememberMe" -> true;
            case "getStarted" -> 1_700_000_000;
            default -> throw new UnsupportedOperationException(method.getName());
        });
var token = new KnoraSessionPolicyMapper().transformIDToken(
        new IDToken(), new ProtocolMapperModel(), null, online, null);
assertEquals(true, token.getOtherClaims().get("knora_remember_me"));
assertEquals(1_700_000_000, token.getOtherClaims().get("knora_session_started_at"));
```

  Thêm trường hợp false, null/offline/start0/start âm không phát cả hai; không thêm claim
  access/userinfo; metadata và ServiceLoader resource có class đúng một lần.
- [ ] Chạy `mvn -B -f infra/keycloak/providers/email-otp-reset/pom.xml -Dtest=KnoraSessionPolicyMapperTest test`,
  xác nhận lỗi thiếu class/behavior (không coi thiếu Java/dependency là RED nghiệp vụ).
- [ ] Viết class theo lõi và đủ metadata trong research §3. Imports:
  `org.keycloak.models.{KeycloakSession,UserSessionModel,ProtocolMapperModel,ClientSessionContext}`,
  `org.keycloak.protocol.oidc.mappers.{AbstractOIDCProtocolMapper,OIDCIDTokenMapper}`,
  `org.keycloak.provider.ProviderConfigProperty`, `org.keycloak.representations.IDToken`,
  `java.util.List`. getId `knora-session-policy`; getDisplayType `Knora session policy`;
  category `TOKEN_MAPPER_CATEGORY`; help text `Signed browser session mode and SSO start`;
  getConfigProperties `List.of()`. Resource service có đúng FQCN class.
- [ ] Cập nhật hai realm fixtures bằng projection research §1, mapper JSON research §3;
  xóa hai client timeout override; set access.token.lifespan `"300"`; giữ key khác.
  Không thêm offline_access scope, không đổi revokeRefreshToken/maxReuse.
- [ ] Ở **cả hai** macro checkbox trong login.ftl dùng:

```ftl
value=(login.password?? && (login.rememberMe!'')?lower_case == 'on')
```

- [ ] Trong `EmailOtpResetFlowIT.java`, dùng `templateData()` và `render("login","login.ftl",data)` thêm matrix
  data: hintremember on không password→unchecked; password sentinel +on→checked;
  password sentinel không remember→unchecked; empty password+on→checked;
  malformed off→unchecked; global error account disabled+password+on→checked.
  Assert sentinel không xuất hiện trong HTML. Không tạo authenticator cho checkbox.
  `FigmaThemeRenderer.java` bật rememberMe trong login fixtures và thêm hai trạng thái
  checked/unchecked; giữ các fixture URL hiện hữu, không thay hình dáng các form khác.
- [ ] Chạy Spotless apply rồi unit/flow tests:

```powershell
mvn -B -f infra/keycloak/providers/email-otp-reset/pom.xml spotless:apply
mvn -B -f infra/keycloak/providers/email-otp-reset/pom.xml -Dit.test=EmailOtpResetFlowIT verify
```

  Mong đợi tests mapper+theme+OTP hiện hữu thực sự executed,0failed/error; không chỉ
  compilation. `EmailOtpResetFlowIT` là kiểm tra protocol/render offline theo Javadoc,
  không cần stack Docker; không nhầm nó với runtime acceptance hoặc bỏ bằng skipTests.
- [ ] Commit local phần đã kiểm tra: `fix(auth): publish signed browser session policy (#230)`.

## Task 3: Managed session-policy migration cho realm đã tồn tại

**Consumes:** Mapper đã có trong image, realm/client thật được phép sửa.
**Produces:** Inspect/Diff/Apply/Rollback có projection, snapshot/readback an toàn.

- [ ] Thêm tests pytest theo wrapper/mock PowerShell ở
  `backend/test/config/test_keycloak_theme.py:259–434`. Mock docker, Invoke-RestMethod,
  realm/client/serverinfo/provider metadata; không gọi DB/network. Viết case Apply→readback
  →Apply no-op→Rollback và injected failure trước script implementation.
- [ ] Chạy `python -m pytest backend/test/config/test_keycloak_session_policy.py -q -p no:cacheprovider`;
  xác nhận fail vì script/hành vi chưa có.
- [ ] Script có parameter contract cố định:

```powershell
param(
  [ValidateSet('Inspect','Diff','Apply','Rollback')][string]$Mode='Inspect',
  [string]$BaseUrl='http://127.0.0.1:8180', [string]$Realm='knora-dev',
  [ValidatePattern('(?-i)^(knora-dev|knora-figma-e2e(?:-[a-z0-9][a-z0-9-]{0,39})?)$')]
  [string]$Project='knora-dev',
  [string]$AdminUsername=$env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME,
  [string]$AdminPassword=$env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD,
  [string]$SnapshotPath
)
```

  `$ErrorActionPreference='Stop'`. Chỉ8180 với knora-dev,8380 với project harness;
  exact realm/client. Copy guard ambient Docker/Compose từ script mẫu, không nạp .env
  vào output. Credentials qua parameter/env đã có, không inline secret trong lệnh lưu.
- [ ] Projection/algorithm trong design §6 là bắt buộc. Provider metadata đọc từ
  `/admin/serverinfo` protocolMapperTypes `openid-connect`, chứa id `knora-session-policy`.
  Client resolve qua `/admin/realms/knora-dev/clients?clientId=knora-web`, kiểm tra chính xác
  một ID; mapper collection `/clients/{uuid}/protocol-mappers/models`. Không hard-code UUID.
  Scan cả mapper client và các default/optional client scopes gắn với client để từ chối
  claim.name trùng hoặc provider id trùng. Không tự sửa scope dùng chung.
- [ ] Snapshot schema `knora-session-policy-snapshot-v1`: target/baseUrl/realm/project,
  clientUuid; before/after realm projection; before/after ba managed attributes có cờ
  `present`; mapper before/model và after/model/ID; completedSteps. Nếu mapper chưa có,
  tạo UUID bằng `[guid]::NewGuid().ToString()` **trước snapshot**, lưu after/model/id rồi
  gửi chính ID đó trong POST mapper. Keycloak26.3.3 giữ ID được cấp; readback phải khớp ID.
  Mapper đã có đúng shape thì giữ ID hiện hữu; khác shape là conflict.
  Snapshot tạo mới
  độc quyền bằng FileMode.CreateNew. Journal progress `.progress.json` cạnh snapshot,
  chỉ enum bước+UTC+verified projection, không HTTP body/admin token.
- [ ] Mutate mapper→client→realm, readback mỗi bước, cuối readback toàn projection;
  không gửi full realm. Client attrs PUT dùng full **attribute map hiện tại** đã merge
  ba key quản lý, không full client chứa secrets; rollback restore present/absent đúng.
  So projection ngay trước write. Document không có CAS REST: yêu cầu owner giữ window
  độc quyền; không tuyên bố atomic transaction hoặc concurrent-owner safety tuyệt đối.
- [ ] Define safe outputs chính xác:
  `KEYCLOAK_SESSION_POLICY_INSPECTED`, `..._DIFF`, `..._ALREADY_SET`,
  `..._APPLY_VERIFIED`, `..._ROLLBACK_VERIFIED`, snapshot path.
  Failure codes: `KEYCLOAK_EXACT_TARGET_REQUIRED`, `KEYCLOAK_PROJECT_OWNERSHIP_REQUIRED`,
  `KEYCLOAK_SESSION_POLICY_PROVIDER_REQUIRED`, `KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT`,
  `KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE`,
  `KEYCLOAK_SESSION_POLICY_SNAPSHOT_TARGET_REJECTED`,
  `KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED`.
  Không output error body hoặc tokens.
- [ ] Tests phải có: unknown target/project/client, foreign port, missing provider,
  duplicate name/provider/claim source, unrelated attrs preserved, absent key rollback,
  readback mismatch, partial failure receipts, existing snapshot refusal, repeat no-op,
  drift before Apply và before Rollback. Failed readback không được report verified.
- [ ] Chạy targeted pytest ở trên + `backend/test/config/test_keycloak_theme.py`;
  mong đợi0failed/error, selected tests executed. Commit:
  `fix(auth): manage Keycloak session policy with guarded rollback (#230)`.

## Task 4: BFF policy v2 và expiry thống nhất

**Consumes:** Signed claims Task2; module signature §1.
**Produces:** Strict v2 session, cookie đúng mode, tất cả renew/persist/logout paths đồng bộ.

- [ ] Thêm tests policy và mở rộng auth tests trước implementation. Core test mẫu:

```typescript
it.each([
  [false, 28_800, 1_800], [true, 2_592_000, 604_800],
] as const)("bounds mode %s", (rememberMe, maximum, idle) => {
  const start = 1_800_000_000;
  const p = policyFromClaims({
    knora_remember_me: rememberMe, knora_session_started_at: start,
  }, start);
  expect(p.sessionExpiresAt).toBe(start + maximum);
  expect(tokenDeadlines(p, 300, 9_000_000, start, start)).toEqual({
    expiresAt: start + 300, refreshExpiresAt: start + Math.min(idle, maximum),
  });
  expect(isSessionPolicy(p, start + maximum)).toBe(false);
});
```

  Thêm near-max remembered vẫn remember true dù refresh chỉ còn60s; anchor tương lai31s;
  missing/string bool; numeric string/NaN/Infinity/non-safe integer; cap bị sửa; expired;
  negative/0 expires; expires301; response về sau deadline; không tạo deadline overflow.
- [ ] Từ frontend chạy `node node_modules/vitest/vitest.mjs run tests/auth-session-policy.test.ts --no-cache`;
  RED phải do module/hành vi chưa có. Không chạy ở primary checkout.
- [ ] Implement module pure theo design §3, constants thời hạn ở một chỗ. `isSessionPolicy`
  không gọi network/env. `policyFromClaims` gọi validator với cap đã tính; tokenDeadlines
  bảo thủ requestStartedAt. Callback và refresh dùng cùng hàm.
- [ ] Sửa KnoraSession/type/encode/decode: issuer, policy, sessionId và refresh bắt buộc;
  bỏ fallback defaults ở encode và HS256 decoder, v2 name. Schema decode kiểm tra
  `exp===min(refreshExpiresAt,sessionExpiresAt)`, numeric finite/safe và access≤refresh≤max.
  Không yêu cầu access còn hạn khi decode: cookie cần đọc được để refresh access đã hết.
- [ ] `exchangeCode` ghi requestedAt trước fetch, thêm no-store+AbortSignal.timeout10000,
  validate required string tokens/nonempty subject và durations; jwtVerify+nonce hiện hữu;
  tạo policy, deadlines và sessionId. Callback error dùng trang lỗi an toàn hiện hữu,
  không ghi token; không resolver Workspace trước khi policy hợp lệ.
- [ ] `refresh` dùng requestedAt, verify ID token như hiện hữu, rồi compare mode/start;
  mismatch/malformed policy hợp lệ chữ ký→null. Response/transport/JWKS transient theo
  bảng design §4. Giữ request10s, cache256/30s, không reset sessionId/cap. Renew kiểm tra
  refresh expiry/cap/revoked trước fast path; invalidateSession dùng cap bắt buộc.
  Export `isSessionRevoked(sessionId:string):boolean` từ cùng coordinator; ở getSession
  và middleware kiểm lại revoked + deadline **sau await encodeSession**, ngay trước
  set cookie đồng bộ. Nếu không còn hợp lệ thì clear thay vì persist; không await thêm
  giữa lần kiểm cuối và cookie write. Không tạo map revocation thứ hai ở module khác.
- [ ] Đổi đủ ba sessionCookie callers; persist bằng v2; clearLegacy ở response callback,
  logout, session và middleware có cookie cũ. `getSession(false)` không ghi cookie;
  middleware sync request+response cookie để SSR đọc token mới. Invalid v2 được clear ở
  getSession(true)/middleware; không clear cookie vì lỗi503.
- [ ] Auth/session thêm issuer, no-store cho mọi outcome;503 không trả session null.
  Logout giữ same-origin/local revoke/Keycloak fallback/preference clear, xóa hai names.
- [ ] Cập nhật factory fixtures trong tests dùng session đủ schema, không thêm optional
  defaults production chỉ để tests cũ pass. Các tests cố ý cookie cũ phải assert rejected.
  Giữ coverage nonce/state/PKCE/callback-origin và resolver-failure retry hiện hữu.
- [ ] Chạy từ frontend:

```powershell
node node_modules/vitest/vitest.mjs run tests/auth-session-policy.test.ts tests/auth-session.test.ts tests/auth-refresh.test.ts tests/auth-session-route.test.ts tests/auth-callback-resolver.test.ts tests/auth-logout-origin.test.ts --no-cache
```

  Cần assert normal cookie không maxAge/expires; remembered maxAge clamp; encrypted token
  không plaintext; legacy JWE/HS256 rejected; configured issuer mismatch; malformed cookie;
  middleware request+response; concurrent same refresh1call; logout thắng renewal; revoked
  remembered cap; timeout/5xx503/no cookie write; invalid_grant401; session JSON không token;
  cookie4KB. Không test normal33min bằng fake expired token rồi gọi đó runtime.
- [ ] Commit: `fix(auth): enforce bounded renewable browser sessions (#230)`.

## Task 5: BFF chặn identity đổi trước dùng bản nháp

**Consumes:** Session v2 issuer/subject; headers design §5.
**Produces:** Additional deny guard trước body/API, không thay backend authorization.

- [ ] Tạo `conversation-identity-bff.test.ts`, mock getSession và global fetch, import POST/GET
  route như pattern BFF hiện hữu. RED ví dụ request của alice với session bob phải401 và
  `fetch` không được gọi. Bao cả issuer khác nhưng cùng subject.
- [ ] Trong `forward`, sau có session trước base/headers/body/fetch:

```typescript
const expectedIssuer = request.headers.get("x-knora-expected-issuer");
const expectedSubject = request.headers.get("x-knora-expected-subject");
const composerPost = request.method === "POST" &&
  /^\/v1\/workspaces\/[^/]+\/conversations(?:\/[^/]+\/turns)?\/?$/.test(normalizedPath);
if ((composerPost || expectedIssuer !== null || expectedSubject !== null) &&
    (expectedIssuer !== session.issuer || expectedSubject !== session.subject)) {
  return NextResponse.json({ detail: "SESSION_IDENTITY_MISMATCH" }, {
    status: 401, headers: { "cache-control": "no-store" },
  });
}
```

  Không clear cookie trên mismatch. Strip cả hai expected headers khỏi forwarded Headers;
  browser không được override Authorization. Giữ nguyên evaluation route block trước
  session, path decoding/error handling và mọi operator route.
- [ ] Tests exact matching/missing/half headers, percent-encoded/path variant, GET có pair
  mismatch rejected, GET không pair vẫn tương thích, normal unrelated POST giữ nguyên,
  body getter không được đọc trên reject, matching forward bearer/Idempotency-Key/body
  đúng và strip headers, no-store401; không gọi Keycloak/backend khi không cần.
- [ ] Tìm synthetic E2E/test callers của hai POST và thêm cặp identity từ **session JSON
  thật**; không tắt guard hoặc fake production session để seed. Caller không thuộc hai
  route không bị bắt thêm header.
- [ ] Run từ frontend:
  `node node_modules/vitest/vitest.mjs run tests/conversation-identity-bff.test.ts tests/operator/evaluation-proxy.test.ts tests/operator/operator-oidc-bff.test.ts --no-cache`.
  Mong đợi0failed; test evaluation boundary cũ vẫn403/404 đúng contract.
- [ ] Commit: `fix(auth): bind conversation requests to draft identity (#230)`.

## Task 6: Khôi phục chat một lần khi quay về tab

**Consumes:** Auth/session JSON mới; PanelIdentityScope hiện hữu; identity guard Task5.
**Produces:** Recovery design §5, cùng-account giữ nháp/key, khác-account không lộ/gửi nháp.

- [ ] Thêm tests ConversationView trước code. Reuse deferred response pattern đang có,
  mock session probe riêng history GET. Case đầu:401→draft giữ→session cùng issuer/sub→
  focus+visibility→1probe+1historyGET và0POST, text/key không đổi. Thêm changed identity
  response trong khi có history/POST cũ pending.
- [ ] Truyền identity thật từ hai protected pages; không còn conditional issuer undefined
  cho session v2. Hub→draft giữ identityScope. Key component gồm issuer/sub/workspace/id.
  Fixtures chỉ-render có thể thiếu scope nhưng submit bị khóa, không tạo header undefined.
- [ ] Tạo `expectedIdentityHeaders` từ baseline scope đã được SSR cấp, không từ dữ liệu
  browser tự nhập; gắn vào **mọi** browserRequest trong ConversationView. Hai POST merge
  cả `Idempotency-Key` hiện có. Giữ browserRequest chung là wrapper fetch không retry.
- [ ] Implement recovery trong component hiện hữu: `recoveryInFlight` promise,
  `needsIdentityCheck` ref, generation token và trạng thái checking/identityChanged.
  `blur/hidden` đặt needsIdentityCheck; visible+focus enqueue một callback0ms và consume
  flag trước network. Trong authRequired vẫn chờ lần return/Retry, không vòng tự gọi.
  Return cùng promise khi duplicate. Dùng **run token riêng** để xác định promise nào
  đang sở hữu recoveryInFlight/checking; không dùng authenticationGeneration để giữ/xóa
  promise, vì requireAuthentication() tự tăng generation khi chính probe nhận401/null.
  Cleanup listeners/timer/AbortController khi unmount. Khóa submit đồng bộ qua ref trước
  fetch, không chỉ chờ setState render lại.
- [ ] `recoverSession()` có flow cố định dưới đây; test toàn bộ nhánh trước khi mở gửi:

```text
lock submit; capture generation
GET /api/auth/session no-store
  stale/unmounted -> discard
  503/network -> keep draft+keys; retryable notice; remain locked
  null/401 -> requireAuthentication; keep draft+keys
  valid identity differs/no baseline -> hide all old UI; clear state+refs;
                                        location.replace('/workspaces'); return
  same -> GET history (or Workspace for unadmitted draft), expected headers included
     stale/unmounted -> discard
     401 -> requireAuthentication; keep draft+keys; no POST
     403 -> permission message; locked; no automatic retry
     other failure -> keep draft+keys; Retry
     success -> update authoritative history; unlock; resume pending poll; no POST
finally: if recovery run token still owns the in-flight slot, clear that slot/checking;
         do not unlock authentication here; never clear a newer run's busy state
```

- [ ] Mismatch401 từ mutation cũng kích hoạt một identity probe để phát hiện account đổi
  dù chưa có focus event; không tự POST lại sau probe. Existing generic401 giữ nháp như cũ.
  Nếu create Conversation đã được xác nhận trước lỗi Turn, giữ admittedConversation ref
  cho cùng identity; khác identity xóa cả ref. Pending/uncertain Turn phải đọc lại history
  trước explicit retry với cùng key, không tự sinh key mới sau lỗi.
- [ ] Recovery UI giữ native login link tab mới và nút thử lại; thêm nhãn chờ ngắn
  `Checking your session…` và lỗi tạm `Unable to verify your session. Retry.` theo copy
  hiện hữu. Dùng status/alert phù hợp, disable submit khi checking; không modal/banner
  trang trí, không ngắt focus khỏi composer khi same identity. History403 dùng thông báo
  quyền hiện hữu. IdentityChanged chỉ hiện `Your account changed. Opening Workspaces…`.
- [ ] Tests còn lại: subject khác; cùngsubject khácissuer; missingbaseline; sessionnull;
 503; history403; stale-probe/history/poll/POST response không unfreeze hoặc refill nháp;
  unmount; two return episodes đúng2probes; no request khi idle/hidden; no storage writes
  chứa nháp; recovery+Retry concurrent singleflight; explicit submit sau recovery dùng
  keys cũ; probe null/401→requireAuthentication tăng generation→promise vẫn được clear→
  Retry sau signin tạo GET mới và recover thành công; copy/archived/scroll/composer vẫn đúng.
- [ ] Run từ frontend:

```powershell
node node_modules/vitest/vitest.mjs run tests/conversation-view.test.tsx tests/conversation-panels.test.tsx tests/conversation-page-workspace.test.tsx tests/conversation-copy.test.tsx tests/conversation-identity-bff.test.ts --no-cache
```

- [ ] Commit: `fix(auth): recover the mounted conversation without replay (#230)`.

## Task 7: Xây journey runtime và kiểm tra local đầy đủ

**Consumes:** Tasks2–6; existing Figma application harness.
**Produces:** Executable test cho từng A1–A11; chưa là bằng chứng khi chỉ viết/collect.

- [ ] Thêm `session-persistence.spec.ts`, không sửa default `testMatch`/profile hoặc
  evidence validator để test không liên quan vô tình kéo dài33 phút. Dùng FIGMA_TEST_MATCH
  chọn riêng. `workers=1`, retries0; trace/video/offline storage export tắt như figma config.
- [ ] Test helpers trong `support/session-policy.ts` có hợp đồng:

```typescript
export async function withAcceleratedSessionPolicy<T>(
  project: string, run: () => Promise<T>,
): Promise<T>;
```

  Helper gọi ownership check hiện hữu trước mutation; chỉ figma project selected và exact
  issuer8380, không8180/3000. Save realm projection và trạng thái present/value của
  `knora-web.attributes["access.token.lifespan"]` trong memory. PUT realm normal idle10/max30,
  remembered idle20/max60/access5, client realm timeouts0; merge riêng client attribute
  `access.token.lifespan="5"` vào map hiện tại vì client ưu tiên hơn realm. Verify readback
  **cả realm và client** trước gọi run. `finally` restore chính xác realm projection và
  client attribute value hoặc trạng thái absent ban đầu, giữ mọi key khác, verify cả hai.
  Bất kỳ restore/readback lỗi thì test fail và dừng lượt. Không exposed API/production env knob mới.
  Chỉ helper test được đổi giá trị gia tốc; script managed luôn fixed policy thật.
- [ ] Thêm vào `support/figma-auth.ts` hàm
  `signInFigmaUser(page:Page,identity:"m5-user"|"m5-other-workspace"|"m5-no-operator",rememberMe=false):Promise<void>`.
  Đọc credential synthetic đúng username từ `test/fixtures/keycloak/figma-realm.json`
  theo cách đang dùng trong figma-ui-interactions; không print giá trị. Gọi openFigmaLogin,
  fill username/password, set checkbox `#rememberMe` bằng check/uncheck rồi click kc-login,
  chờ về origin3300 và session không null. Không query flag giả cho BFF. Case formfresh
  dùng context mới; forced reauth dùng prompt=login có chủ đích; case SSO thường không prompt.
- [ ] Thêm `readOwnedBrowserPolicy(context:BrowserContext)` trong support/session-policy.ts:
  chỉ đọc cookie **thật** `knora_session_v2` của loopback3300 trong memory sau ownership
  check. Dùng jose.jwtDecrypt với SHA256 của SESSION_SECRET trả bởi
  `figmaRuntimeEnvironment(figmaEnvironment())`; không đổi process.env để né ambient guard.
  Return projection `{rememberMe,sessionStartedAt,sessionExpiresAt,expiresAt,refreshExpiresAt}`
  đã validate kiểu; không trả/log token, subject hoặc raw cookie. Đọc expiry/flags cookie
  cùng projection này để kiểm mode/start/max; không chế tạo hoặc import cookie.
- [ ] Add runtime tests có tên rõ:
  1. `native remember choice and retry preserve mode`: fresh hint/new formunchecked,
     wrongpassword on/off preserved, successful both modes, checked keyboard bằng Space;
     sanitized screenshots390/1440px chỉ vùng form/recovery đã mask, không auth URL.
  2. `online policy claims survive code exchange and refresh`: provider metadata đúng,
     exact realm/client readback; đăng nhập native hai mode và đọc projection v2 thật bằng
     helper trên. V2 được tạo qua BFF verify ID token đang chạy, không helper dựng session.
     Chờ access còn≤30s rồi GET session, đọc v2 mới, assert start/mode/max không đổi và
     access/refresh deadline mới đúng; chỉ ghi booleans `modeVerified/startStable`.
     Unit tests Task4 xác minh BFF bắt buộc chữ ký/issuer/aud/nonce; runtime này xác nhận
     mapper thực sự có tác dụng qua BFF, không ghi đã thanh tra raw ID-token payload.
  3. `accelerated idle and absolute limits`: isolated native logins, normal nghỉ14s
     hết; remembered nghỉ14s còn; remembered nghỉ24s hết. Các phiên độc lập. Một cặp
     khác gọi session mỗi3s để giữ idle, normal không vượt30s, remembered không vượt60s;
     deadline/grace quan sát theo persistent sessions đang bật. Không cộng grace vào BFF.
  4. `remembered browser profile reopens`: temp persistent profile thuộc run, native
     remember login, đóng browserprocess/context rồi reopen cùng profile, protected GET
     còn dùng; assert policy thường chỉ session cookie. Không storageState/importcookies.
     Quan sát nếu browser restore normal session cookie, không kết luận lỗi trái spec.
  5. `recovery keeps same account draft and rejects account switch`: native reauth cùng
     user; khác user `m5-other-workspace` đã có fixture; focus/visibility; assert
     draft/POST count, old UI gone/new workspace. Không cần worker hoặc kết quả Turn.
  6. `logout and revoked refresh`: logout cookie/SSO, no oldcookie reuse; admin thu hồi
     đúng session synthetic của riêng `m5-no-operator`, không dùng user này ở case khác.
     Resolve exact user và GET `/users/{uuid}/sessions`, yêu cầu đúng1 online session
     có client knora-web, DELETE `/sessions/{sessionUuid}`. Không có đúng1 thì dừng;
     sau access expiry refresh bị từ chối.
     Không logout-all realm/users khác. Test401/503 concurrency chi tiết ở unit; không
     bịa fault endpoint sản phẩm để mock Keycloak network trong runtime proof.
  7. `continuous real idle 15 and 33 minutes`: §8 quy định chi tiết.
- [ ] Chạy local format/check trước full regression; không đụng dữ liệu thật:

```powershell
python -m ruff format .
python -m ruff format --check .
python -m ruff check .
python -m pytest backend/test/config/test_keycloak_session_policy.py backend/test/config/test_keycloak_theme.py backend/test/config/test_figma_e2e_harness.py -q -p no:cacheprovider
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test -- --no-cache
npm --prefix frontend run build
mvn -B -f infra/keycloak/providers/email-otp-reset/pom.xml spotless:apply
mvn -B -f infra/keycloak/providers/email-otp-reset/pom.xml -Dit.test=EmailOtpResetFlowIT verify
```

  Scope Python tests không DB bằng mock. Inspect formatter diff, giữ ngoài-scope changes
  không stage; không reset thay đổi owner khác. Shared formatting chỉ cần nếu sửa file
  được format:shared chọn, không sửa ci.md/Compose/AGENTS chỉ để chạy check dư thừa.
- [ ] Unit/Vitest/Java/pytest0failed/error, typecheck/lint/build/format exit0 mới đi runtime.
  Case skipped/missing dependency phải báo chờ, không ghi “local verified” toàn bộ.
- [ ] Commit local tests: `test(auth): cover native session persistence journeys (#230)`.

## Task 8: Chạy targeted runtime trên stack riêng

Chỉ sau gói quyền Task0. Một project mới cho một attempt; tối đa90 phút cả startup,
journeys và cleanup, không reset budget do lỗi. Target cố định: frontend3300, API8800,
Keycloak8380, Postgres5543, MinIO9900/9901, SMTP1025/Mailpit8025. Foreign listener hoặc
reservation khác là blocker; không kill/stop/reconfigure.

- [ ] Kiểm tra sạch/commit SHA, frontend dependency containment, Docker/build/network
  đúng grant, và `$project`/runRoot fresh. Chuẩn bị command trong cùng PowerShell process:

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
$subjectSha = (git rev-parse HEAD).Trim()
$project = 'knora-figma-e2e-session-' + [guid]::NewGuid().ToString('N').Substring(0,12)
$runRoot = Join-Path $repoRoot "frontend/test-results/$project"
if (Test-Path -LiteralPath $runRoot) { throw 'Evidence directory already exists' }
./scripts/prepare-figma-e2e.ps1 -CheckFrontendOnly
if ($LASTEXITCODE -ne 0) { throw 'Frontend check failed' }
./scripts/prepare-figma-e2e.ps1 -Project $project -CheckConfigurationOnly
if ($LASTEXITCODE -ne 0) { throw 'Configuration check failed' }
./scripts/prepare-figma-e2e.ps1 -Project $project -Run {
  param($project, $composeArgs)
  if ((git rev-parse HEAD).Trim() -ne $subjectSha) { throw 'Subject drift' }
  if (git status --porcelain) { throw 'Dirty runtime subject' }
  docker compose @composeArgs ps -a
  $ids = @(docker ps -a --filter "label=com.docker.compose.project=$project" --quiet)
  foreach ($id in $ids) {
    docker inspect --format '{{.Name}} {{.Image}} {{index .Config.Labels "com.docker.compose.project"}}' $id
  }
  Invoke-RestMethod http://127.0.0.1:8800/health | Out-Null
  $discovery = Invoke-RestMethod http://127.0.0.1:8380/realms/knora-dev/.well-known/openid-configuration
  if ($discovery.issuer -cne 'http://127.0.0.1:8380/realms/knora-dev') { throw 'Wrong issuer' }
  Invoke-RestMethod http://127.0.0.1:8025/api/v1/info | Out-Null
  docker compose @composeArgs exec -T figma-api alembic current
  if ($LASTEXITCODE -ne 0) { throw 'Migration observation failed' }
  docker compose @composeArgs exec -T figma-api python -c 'from knora.infrastructure.settings import Settings; s=Settings(); print(s.provider_mode, s.embedding_provider, s.generation_provider)'
  if ($LASTEXITCODE -ne 0) { throw 'Provider observation failed' }
  $null = New-Item -ItemType Directory -Path $runRoot
  $testCompose = docker compose @composeArgs config --format json | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) { throw 'Owned synthetic configuration unavailable' }
  $testAdminUsername = $testCompose.services.'figma-keycloak'.environment.KC_BOOTSTRAP_ADMIN_USERNAME
  $testAdminPassword = $testCompose.services.'figma-keycloak'.environment.KC_BOOTSTRAP_ADMIN_PASSWORD
  $policyArgs = @{
    BaseUrl='http://127.0.0.1:8380'; Project=$project
    AdminUsername=$testAdminUsername; AdminPassword=$testAdminPassword
  }
  ./scripts/configure-keycloak-session-policy.ps1 @policyArgs -Mode Inspect
  ./scripts/configure-keycloak-session-policy.ps1 @policyArgs -Mode Diff
  ./scripts/configure-keycloak-session-policy.ps1 @policyArgs -Mode Apply -SnapshotPath (Join-Path $runRoot 'session-policy-before.json')
  $env:FIGMA_TEST_PROJECT = $project
  $env:FIGMA_TEST_MODE = 'application'
  $env:FIGMA_TEST_MATCH = 'session-persistence.spec.ts'
  $env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = Join-Path $runRoot 'session-persistence.xml'
  node frontend/node_modules/@playwright/test/cli.js test `
    --config frontend/playwright.figma.config.ts `
    --reporter list,junit --output "$runRoot/results"
  if ($LASTEXITCODE -ne 0) { throw 'Session persistence journey failed' }
}
```

  Đọc Doctor output: cần migration `head` và `deterministic-local None None` đúng runbook;
  không có thì dừng trước browser. Ghi SHA/imageIDs/migrationhead/providers/issuer đúng
  trong evidence. `$testCompose` chỉ xử lý trong memory, không print/serialize vì có
  credentials; không đưa `$policyArgs` vào log. Các lệnh script phải throw/exit nonzero
  khi lỗi, không đi tiếp Playwright sau failed readback.
  Fixtures mới có thể đã đúng nên Apply no-op. Để kiểm migration thật, helper test đổi
  projection riêng về baseline cũ đã nêu trong spec §1 rồi Apply→readback→Apply no-op→
  Rollback→readback→Apply về desired. Toàn bộ trong reservation, trước native tests,
  không đổi OTP/SMTP/user. Thiếu provider hoặc mismatch target dừng ngay.
- [ ] Case thời gian thật đặt `test.setTimeout(45*60_000)`, chạy **ba context độc lập**:
  normal15, normal33, remembered33; login native riêng, đợi ổn định và không pending Turn.
  Bắt đầu quiet windows cùng lúc; không gọi health/session/protected-page trong từng
  context trước mốc của nó. Count mọi browser request có thể renew sau quiet-start;
  yêu cầu0. Không print URL/headers/token của request.
- [ ] Sau900s, chỉ normal15 gửi GET session+Workspace→còn đăng nhập. Sau1980s, normal33
  GET session→null/protected UI yêu cầu login; remembered33 GET protected page→refresh
  và vào đúng Workspace không form login. Request của normal15 không được dùng chung
  cookie/profile/SSO session với hai context còn lại. Ghi quiet start/end UTC + elapsed
  monotonic, counters, mode và outcomes không giá trị cookie.
- [ ] Trước/sau wait xác minh source/image/policy không drift; restart/build drift làm
  case không hợp lệ, không ghi PASS. Trong lúc runner chờ, agent vẫn cập nhật ngắn cho
  người dùng tối đa60s giữa các thông báo, không thêm probe vào browser để báo tiến độ.
- [ ] Evidence JSON `schemaVersion:1`, subjectSha, project, KeycloakVersion, policyDigest,
  context case names, real/accelerated label, startedAt/finishedAt/elapsedSeconds,
  zeroRenewingRequestsDuringIdle, booleans kết quả và screenshots masked relative paths.
  Không dump storageState, request/response bodies, full token claims hoặc auth URLs.
- [ ] Dùng Try/finally cleanup persistent profiles/context do test sở hữu; harness cleanup
  trong reservation. Phải có `FIGMA_CLEANED=$project`; query containers/volumes/networks
  theo project rỗng; listeners của lượt biến mất; foreign resources giữ nguyên. Cleanup
  lỗi là gate chưa đạt, không tự xóa rộng/compose down ngoài reservation.

Expected: cả7 named runtime tests thực sự executed,0failed/0skipped; A1–A11 có bằng
chứng tương ứng. Không suy runtime PASS từ `--list`, smoke cũ hoặc application profile
chưa chọn tests này. Gia tốc chỉ chứng minh giới hạn/config; không gọi đã chờ7/30 ngày.

## Task 9: Docs, review, tích hợp và activation

- [ ] Cập nhật mục phiên của local-development: hai chế độ/cookie, one-time signin,
  không lưu nháp, auto recovery, giới hạn revocation/topology, script Inspect/Diff/
  Apply/Rollback. Thay câu “không tăng timeout để che lỗi” bằng chính sách managed đã
  duyệt cùng giới hạn không sửa rotation để né lỗi. Link design/research thay copy toàn bộ.
- [ ] Feature Map auth link targeted test/journey mới, phân biệt evidence mới và smoke
  lịch sử. Agent-environment link cách chọn FIGMA_TEST_MATCH; không sửa smoke lịch sử
  thành đã đạt expiry và không biến tests33ph thành default profile.
- [ ] Kiểm link/file/command, `git diff --check`, frontend format:check; ruff/Spotless nếu
  còn code đổi. Sau sửa code cuối phải rerun affected checks; không dùng evidence cũ.
- [ ] Review độc lập đúng diff/head và reports: yêu cầu kiểm nguồn mode/anchor, expiry,
  migration/rollback/drift, SSR persistence, account-switch race, no replay/storage,
  401vs503, native checkbox, secret masking và0-request idle proof. Review findings hợp
  lệ sửa trong phạm vi và rerun; chưa có reviewer thì ghi còn chờ, không coi tự-review là
  đã review độc lập. Có thể dùng fresh reviewer agent nếu công cụ/quyền trong phiên cho phép.
- [ ] Chỉ sau quyền publication: tạo PR với template repository, gắn Issue230, đường dẫn
  bộ R1, **full approved-document SHA** và tham chiếu duyệt hội thoại, source head,
  commands/counts/results và evidence sanitized. Attach PR vào chat nếu công cụ hỗ trợ.
  Issue body chỉ cập nhật scope bỏ sleep/wake và links theo câu trả lời người dùng,
  không paste plan vào Issue. Nếu chưa có quyền, chuẩn bị nội dung local để owner đăng.
- [ ] `CI required` phải xanh cho head hiện tại, đối chiếu ci-subject artifact/head/checkout
  SHA. CI không thay targeted runtime. New push invalidates old head CI claim. Runtime
  application release profile chỉ khi quy trình release yêu cầu; nó không thay các case
  expiry. Không tự merge/deploy/đóng Issue.

### Activation existing local realm — chỉ khi có grant riêng

Đích dự kiến `knora-dev`, issuer `http://127.0.0.1:8180/realms/knora-dev`, frontend3000.
Stack đang có owner khác thì phải có phép sử dụng/restart đúng window; grant cũ không có
hiệu lực. Không chạy đoạn này chỉ vì PR được duyệt.

1. Owner cấp maintenance window độc quyền, exact code/image/target, quyền restart provider+
   frontend, snapshot path và rollback. Kiểm sạch target/branch/SHA và clients không có
   app ngoài phạm vi sẽ bị realm policy ảnh hưởng; gặp app ngoài dự kiến thì dừng activation.
2. Snapshot/diff projection trước thay đổi, giữ image digests và code version cũ; provider
   image mới phải giữ OTP/JPA schema/version. Không reinstall/reimport/delete volume.
3. Nạp image Keycloak mới theo launcher owner đang dùng, giữ DB và secret/flows. Xác minh
   provider metadata; Apply script8180 + readback. Sau đó rollout BFF mới; v2 cookie tách biệt.
4. Native signin hai mode, refresh, Workspace owner read, same-account recovery/logout;
   record exact deployed image/source. Không cần lặp wait33ph nếu acceptance SHA không
   đổi; nếu source/config khác bộ đã verify thì chưa thể nhận acceptance tương đương.
5. Lỗi provider/policy/token/recovery →ngừng traffic trong window, về BFF cũ, script
   Rollback snapshot bằng reverse receipts, image Keycloak cũ; readback/login thường.
   Nếu drift, dừng rollback field đó và báo owner, không overwrite. v2 cookie bị code cũ
   bỏ qua; người dùng signin lại. Không đổi SESSION_SECRET hoặc realm-wide logout.

Production ngoài local guard cần deployment package riêng; không thêm target tùy ý vào
script để vượt ranh giới. Trạng thái Deployed chỉ ghi khi có record và quan sát version.

## 10. Coverage, stop rules và bàn giao

| Yêu cầu spec | Task thực hiện | Bằng chứng chính |
| --- | --- | --- |
| P1/P2/P3/P5 | 2,3,4 | Signed mapper tests + token boundary tests + A2/A3/A4 |
| P4 | 2,7 | FTL render matrix + native form/keyboard |
| P6/P7/P8 | 5,6,7 | Identity deny-before-forward + deferred recovery/noPOST/storage tests + native reauth |
| P9/P10 | 4,6,7 | 401/503/concurrency/logout + revoked refresh after access expiry |
| P11 | 3,4,8,9 | v2-only decoder, no-op migration/readback/rollback, old decoder ignores v2 name |
| P12 | Global Constraints | Không task sleep/wake; không nói đã kiểm chứng nó |
| A1–A11 | 2–9 | Named assertions, real idle, masked UI, exact subject, cleanup |

Stop đúng phần phụ thuộc khi: thiếu authority/approved revision, foreign stack/port,
missing prerequisite, conflicting mapper/claim, config/source drift, unsafe log/secret,
runtime90ph hết, required test/review/cleanup fail hoặc thiết kế cần thêm distributed
session/new external service. Không tự tắt assertion/gate, sửa rotation, tăng timeout
khác chính sách hoặc bỏ case khó để báo đạt. Tiếp tục phần độc lập an toàn đã được phép.

Bàn giao kết quả bằng các trạng thái riêng: **đã sửa mã; đã kiểm tra local; CI đã đạt;
đã chạy targeted runtime; đã review; đã được owner chấp thuận; đã merge; đã deploy**.
Mỗi trạng thái có đúng SHA/commands/counts/report hoặc ghi chưa làm/lý do. Không nhận
hoàn tất issue khi thiếu A1–A11; không cần nghiệm thu AI quality hoặc sleep/wake.

## 11. Tình trạng duyệt của chính tài liệu này

R1 là bộ spec/design/research/plan trong nhánh tài liệu ngày30/10/2026, **chưa được
người dùng duyệt triển khai** tại lúc viết. Full SHA của commit tài liệu được cung cấp
trong báo cáo bàn giao; tham chiếu phê duyệt chỉ được ghi khi người dùng thực sự trả lời.
Không có URL phê duyệt GitHub ở hiện tại; không bịa hoặc coi decisions Q1–Q7 là approval
tự động cho mọi chi tiết kỹ thuật/activation trong bộ này.
