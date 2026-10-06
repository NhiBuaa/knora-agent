# Knora Figma UI — implementation workflow

> For agentic workers: use executing-plans to coordinate these plans, or
> subagent-driven-development for bounded implementation tasks in this session.
> Read the design and each owning slice plan. Checkbox steps are execution tracking, not completed work.

**Goal:** Integrate all selected Figma screens and interactions into the current Knora application.

**Architecture:** Keep backend and Keycloak authority. Build shared styling/navigation first, then
feature surfaces and identity integration, and finish with cross-surface verification.

**Tech Stack:** Next.js 15.5.24, React 18.3.1, TypeScript, Tailwind CSS v4/PostCSS, Python/FastAPI/PostgreSQL,
Keycloak 26.3.3, Vitest and Playwright.

**Spec:** [Figma integration design](../specs/2026-10-05-figma-ui-integration-design.md).

**Approval:** User approved this plan in chat on 2026-10-05 (“tôi duyệt plan”), including
Tailwind CSS v4, the proposed directory structure and the Keycloak email OTP slice.
Implementation may start. Approval does not waive fresh verification or authorize merge/push/deploy.

## Global Constraints

- Canonical skills: C:/Users/NhiBuaa/.codex/skills. Read each SKILL.md before using it.
- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Every maintained frontend change requires format, then format:check.
- Previous milestone gates are owner-accepted; new work requires fresh evidence.
- Every non-primary worktree must be a direct child of C:/Developer/Projects/knora-agent-worktree.
- Do not merge, push, deploy, or remove a worktree/branch without the user's integration choice.

## What has been read

CONTEXT.md, domain/issue-tracker guides, architecture standard, M1/M2 module seams, M5 runbook,
current frontend/BFF/Keycloak implementation and the three Figma pages.

Scope: 41 final screen variants, 38 prototype frames, 89 prototype transitions, five panel layouts
and five response states. Exact mappings are in
[the inventory](../../design/figma-ui-inventory-2026-10-05.json).

The requested OTP choice is confirmed. The remaining design choices are concrete proposals in the
spec, including responsive behavior, search contract and truthful unavailable/deletion states.

## Phân tích cấu trúc thư mục dự kiến

Cây dưới đây là cấu trúc mục tiêu khi thực thi plan, không phải tất cả đã tồn tại.
Ký hiệu: [=] tái sử dụng; [~] sửa; [+] tạo mới. Cây chỉ liệt kê phần liên quan đến UI.
Các dấu ngoặc nhọn/dấu phẩy viết gọn nhiều file, không phải tên file literal.

### 1. Hiện trạng và quyết định tổ chức

| Khu vực hiện có | Phân tích | Quyết định |
| --- | --- | --- |
| frontend/app | Đã tách routes workspace, conversation, document, operator và BFF | Giữ URL; page/layout làm server composition, đọc session và dữ liệu ban đầu |
| components/ui | Có Button, Field, Notice, StatusBadge, ThemeControl | Tái sử dụng, thêm Dialog/Menu; chuyển styling sang Tailwind |
| components/shell | AppShell phối hợp WorkspaceSidebar, MobileDrawer, AccountMenu | Thêm ProductHeader; AppShell tiếp tục phối hợp layout |
| components/conversations | ConversationView chứa polling, submit, recovery và markup | Giữ facade/lifecycle, tách panels/rail/composer/TurnCard trong U3 |
| components/documents | List/detail chứa upload và lifecycle actions | Tách dialog/menu; view vẫn sở hữu request và trạng thái thao tác |
| frontend/lib | Đã phân nhóm api, auth, navigation, operator | Thêm documents/conversations đúng trách nhiệm; không gom vào utils chung |
| frontend/styles | Tokens, typography, controls đã tách riêng | tokens.css là nguồn giá trị, Tailwind theme chỉ ánh xạ |
| backend/src/knora | Use-case đã tách HTTP/Postgres adapters | Mở rộng owner hiện tại; không tạo backend UI service |
| infra/keycloak và themes/knora | Deployment và theme có vị trí riêng | Provider Java ở infra/keycloak/providers, template ở themes/knora |

Giữ components theo tính năng để tận dụng cấu trúc hiện tại. Không chuyển toàn bộ sang frontend/src
hoặc tạo thêm cây features song song: việc đó làm tăng import/route phải đổi mà chưa cải thiện
interface của module. Không tạo một thư mục cho từng mã màn hình A4, D9 hay AU11; chúng là trạng
thái được trình bày bởi các module dùng lại.

### 2. Cây frontend mục tiêu

~~~text
frontend/
├── app/
│   ├── layout.tsx                              [=] root, local fonts, theme
│   ├── globals.css                             [~ F2] Tailwind imports/layers
│   ├── auth/                                   [+ I3] public error pages
│   │   ├── unavailable/page.tsx
│   │   └── failed/page.tsx
│   ├── workspaces/
│   │   ├── layout.tsx                          [~ F2, U1] session + shell composition
│   │   ├── shell.css                           [~ F2, U3] migrate/scoped legacy CSS
│   │   ├── page.tsx                            [~ U1] list/no active workspace
│   │   ├── archived/page.tsx                    [+ U1]
│   │   └── [workspaceId]/
│   │       ├── page.tsx                        [~ U1]
│   │       ├── documents/
│   │       │   ├── page.tsx                    [~ U2]
│   │       │   └── [documentId]/page.tsx        [~ U2]
│   │       └── conversations/
│   │           ├── page.tsx                    [~ U3]
│   │           └── [conversationId]/page.tsx   [~ U3]
│   ├── operator/                               [~ O1; layout F2/U1 composition]
│   │   ├── layout.tsx, page.tsx, operator.css
│   │   ├── operations/{page,content}.tsx
│   │   ├── traces/page.tsx
│   │   ├── traces/[traceId]/page.tsx
│   │   ├── evaluations/page.tsx
│   │   └── evaluations/[reportId]/page.tsx
│   └── api/
│       ├── [...path]/route.ts                  [=] browser BFF
│       ├── workspace-selection/route.ts        [=]
│       ├── auth/{login,callback}/route.ts      [~ I3]
│       ├── auth/{logout,session}/route.ts      [=]
│       └── operator/                           [=] handlers và _proxy.ts
├── components/
│   ├── auth/                                   [+ I3] public outcome composition
│   │   ├── AuthOutcome.tsx                     shared AU3/AU4 markup and safe retry links
│   │   └── auth-outcome.css                    necessary scoped root/layout overrides
│   ├── ui/                                     [~ F2]
│   │   ├── Button.tsx, Field.tsx, Notice.tsx, StatusBadge.tsx
│   │   ├── EmptyState.tsx, PageHeader.tsx, ThemeControl.tsx
│   │   └── Dialog.tsx, Menu.tsx                [+ F2]
│   ├── shell/
│   │   ├── AppShell.tsx                        [~ F2, U1 slot, U3 rail handoff]
│   │   ├── MobileDrawer.tsx                    [~ F2; U1 modal keyboard ownership]
│   │   ├── ProductHeader.tsx                   [+ F2]
│   │   ├── AccountMenu.tsx                     [~ F2 rồi I3]
│   │   ├── account-menu.css                    [+ I3] owned AU5 styling
│   │   └── WorkspaceSidebar.tsx                [~ U1]
│   ├── workspaces/
│   │   ├── WorkspaceManagement.tsx, WorkspaceHome.tsx [~ U1]
│   │   ├── WorkspaceSelector.tsx               [+ U1]
│   │   ├── WorkspaceShell.tsx                  [+ U1] client composition host
│   │   ├── CreateWorkspaceDialog.tsx           [+ U1]
│   │   ├── ArchiveWorkspaceDialog.tsx          [+ U1]
│   │   ├── ArchivedWorkspaceList.tsx           [+ U1]
│   │   └── workspaces.css                      [+ U1 nếu cần rule riêng]
│   ├── documents/
│   │   ├── DocumentList.tsx, DocumentDetail.tsx [~ U2]
│   │   ├── UploadDocumentDialog.tsx            [+ U2]
│   │   ├── DocumentActionsMenu.tsx             [+ U2]
│   │   ├── DeletionRequestDialog.tsx           [+ U2]
│   │   └── documents.css                       [+ U2 nếu cần rule riêng]
│   ├── conversations/
│   │   ├── ConversationList.tsx, ConversationView.tsx [~ U3]
│   │   ├── ConversationPanels.tsx              [+ U3] resize/rail/inspector
│   │   ├── ConversationRail.tsx                [+ U3] history/search
│   │   ├── TurnCard.tsx                        [+ U3] outcome/citation triggers
│   │   ├── ConversationComposer.tsx            [+ U3] draft/submit UI
│   │   └── conversations.css                   [+ U3] resize/scroll rules
│   ├── citations/
│   │   ├── CitationViewer.tsx                  [~ U3] facade hiện có
│   │   └── EvidenceInspector.tsx               [+ U3] selected Turn evidence
│   ├── operator/                               [~ O1]
│   │   └── OperationsView.tsx, TraceView.tsx, EvaluationView.tsx,
│   │       ToolObservationView.tsx
│   └── tools/                                  [=] ToolLifecycle + CSS
├── lib/
│   ├── api/{browser-client,client}.ts          [=] browser/server transport
│   ├── auth/                                   [=] session/refresh/workspace
│   ├── navigation/routes.ts                    [~ U1] archived route helper
│   ├── documents/presentation.ts               [+ U2] projection → label/tone
│   ├── conversations/panel-preferences.ts       [+ U3] scoped UI preferences
│   ├── operator/{api,bff,presentation}.ts       [= API/BFF; ~ O1 presentation]
│   ├── questions/sse.ts                        [=]
│   └── theme.ts, ui-states.ts                   [=]
├── styles/
│   ├── tokens.css                              [~ F2] light/dark semantic values
│   ├── tailwind-theme.css                      [+ F2] @theme inline mapping
│   ├── typography.css                          [~ F2]
│   └── controls.css                            [~ F2] layered/legacy controls
├── public/
│   ├── fonts/                                  [=] Inter/Roboto Slab/licenses
│   ├── brand/                                  [+ F2] leaf/orbits/asset manifest
│   └── icons/figma/                            [+ U1, later feature owners] exact originals
│       ├── *.svg                               selector/no-results/status icons at real callsites
│       │                                       U2: d9407 selector, 97a8a Ready dot; U3 reuses 97a8a
│       └── figma-assets.json, .gitattributes     provenance/checksums, preserve SVG bytes
├── generated/knora-openapi.ts                   [~ F1, chỉ exporter]
├── tests/                                      [~] xem mục 5
├── postcss.config.mjs                           [+ F2]
├── playwright.figma.config.ts                  [+ I1; ~ Q1] isolated identity/visual/live config
├── package.json, package-lock.json              [~ F2]
├── middleware.ts                               [~ I3 nếu cần public error routes]
└── playwright.config.ts                        [~ Q1]
~~~

CSS theo tính năng chỉ tạo khi có rule riêng thật sự; nếu Tailwind đã đủ thì bỏ file CSS rỗng
và ghi vào ledger. Không tạo index.ts barrel chỉ để re-export mọi file.

### 3. Backend, Keycloak và tài liệu

~~~text
backend/
├── src/knora/
│   ├── ingestion/documents.py                  [~ F1] projection/interface
│   ├── workspaces/{ports,service}.py           [~ F1] query-aware listing
│   ├── conversations/{ports,service}.py        [~ F1] query-aware listing
│   └── adapters/
│       ├── http/{schemas,workspaces,conversations}.py [~ F1]
│       └── postgres/{document_reader,workspace_store,conversation_store}.py [~ F1]
└── test/
    ├── adapters/http/                          [~ F1] contract/auth/list tests
    ├── adapters/postgres/                      [~ F1] projection/query/cursor
    │   └── test_document_ui_projection.py      [+ F1]
    ├── api/test_openapi_contract.py             [~ F1]
    └── config/
        ├── test_keycloak_theme.py              [~ I1/I2]
        └── test_figma_e2e_harness.py            [+ I1] exact isolated project/port guards
infra/keycloak/
├── Dockerfile                                  [~ I2]
└── providers/email-otp-reset/                   [+ I2] Java build độc lập
    ├── pom.xml
    ├── .gitignore                              [+ I2] Maven target/ exclusion
    └── src/
        ├── main/java/com/knora/keycloak/reset/
        │   ├── EmailOtpResetAuthenticator.java
        │   ├── EmailOtpResetAuthenticatorFactory.java
        │   ├── OtpChallengeService.java
        │   ├── OtpChallengeStore.java
        │   ├── KeycloakOtpChallengeStore.java
        │   └── persistence/                    [+ I2] private Keycloak DB state
        │       ├── OtpRecoveryWindowEntity.java
        │       ├── OtpChallengeEntity.java
        │       ├── OtpJpaEntityProvider.java
        │       └── OtpJpaEntityProviderFactory.java
        ├── main/resources/META-INF/services/
        │   ├── org.keycloak.authentication.AuthenticatorFactory
        │   └── org.keycloak.connections.jpa.entityprovider.JpaEntityProviderFactory
        ├── main/resources/META-INF/knora-otp-changelog.xml
        ├── test/probe/                         [+ I2] separate storage-proof classifier only
        │   ├── java/com/knora/keycloak/reset/probe/
        │   │   ├── StorageProbeResource.java
        │   │   └── StorageProbeResourceFactory.java
        │   ├── resources/META-INF/services/
        │       └── org.keycloak.services.resource.RealmResourceProviderFactory
        │   └── resources/META-INF/beans.xml      test classifier only
        └── test/java/com/knora/keycloak/reset/
            ├── OtpChallengeServiceTest.java
            ├── EmailOtpResetFlowIT.java
            └── OtpChallengeConcurrencyIT.java
themes/knora/
├── login/
│   ├── theme.properties                        [~ I1]
│   ├── resources/css/knora.css                  [~ I1]
│   ├── resources/fonts/                        [=]
│   ├── resources/images/                       [+ I1–I3] exact original brand/form assets
│   │   └── figma-assets.json, .gitattributes     local provenance/checksums, preserve SVG bytes
│   ├── messages/messages_en.properties         [+ I1]
│   ├── login.ftl, register.ftl                  [+ I1]
│   ├── login-update-password.ftl, info.ftl      [+ I1; info tiếp tục I3]
│   └── knora-reset-email.ftl, knora-reset-otp.ftl [+ I2]
└── email/                                      [+ I2]
    ├── theme.properties
    ├── html/knora-reset-otp.ftl
    ├── text/knora-reset-otp.ftl
    └── messages/messages_en.properties
scripts/
├── export_openapi.py                           [=] sinh frontend contract
├── configure-keycloak-theme.ps1                [=] tooling theme hiện có
├── prepare-figma-e2e.ps1                        [+ I1/I2] idempotent isolated test harness
├── prepare-figma-otp-proof.ps1                  [+ I2] guarded two-node storage proof
├── figma-otp-pg-commit-proxy.py                 [+ I2] test-only lost commit reply, no host port
└── configure-keycloak-auth-flow.ps1             [+ I1/I2] targeted realm migration
test/fixtures/keycloak/
├── dev-realm.json                              [~ I1/I2] fresh realm test/dev
└── figma-realm.json                            [+ I1/I2] isolated test callback/realm fixture
docker-compose.figma-e2e.yml                    [+ I1/I2] standalone task-only test graph
docker-compose.figma-otp-proof.yml              [+ I2] test-only override, loopback second node8381
docs/
├── design/figma-ui-inventory-2026-10-05.json      [đã tạo khi lập plan]
├── research/keycloak-email-otp-reset-2026-10-05.md [đã tạo]
├── superpowers/specs/                          [design của workflow này]
├── superpowers/plans/                          [workflow + năm slice plan]
└── development/
    ├── keycloak-theme.md                       [~ I1/I2/Q2]
    ├── figma-ui-visual-coverage.md              [+ Q1]
    └── figma-ui-implementation-record.md        [+ Q2]
~~~

Provider Java build riêng vì chạy bên trong Keycloak. Frontend/Knora backend không import provider
hay lưu OTP. Store interface là seam nội bộ; adapter phải qua kiểm thử đồng thời của I2.
Các immutable record/enum của challenge được đặt trong module Java này; không sinh sang OpenAPI Knora.

### 4. Chiều phụ thuộc và nơi giữ state

~~~text
app/page.tsx + layout.tsx (server composition)
  → components/shell + feature views
      → components/ui
      → lib/<feature>/presentation hoặc preferences
      → lib/api/browser-client → app/api BFF → backend HTTP → use-case → Postgres adapter

server page / BFF → lib/auth + lib/api/client hoặc lib/operator/bff
backend OpenAPI → exporter → generated/knora-openapi.ts → typed consumers
styles/tokens.css → styles/tailwind-theme.css → Tailwind utilities trong JSX
Keycloak flow → Authenticator → OtpChallengeService → OtpChallengeStore adapter
~~~

| Trách nhiệm | Owner | Quy tắc |
| --- | --- | --- |
| Session, refresh, OIDC transaction | BFF + server lib/auth | Client không import module đọc server secrets/cookies |
| Authorization và durable lifecycle | Backend/Keycloak | UI trình bày projection, gửi intent |
| Draft, modal/menu | Feature client view | State cục bộ; không cần thêm global store |
| Polling, uncertain submit, retry identity | Facade ConversationView/DocumentList/DocumentDetail hiện có | Một owner mỗi lifecycle; module con nhận props/callback |
| Rail width/inspector visibility | ConversationPanels + panel-preferences | Session-scoped; không lưu excerpt/token |
| Citation selection | ConversationView, gắn Turn | Inspector không thay evidence lịch sử bằng version mới nhất |
| Màu và theme | tokens.css | @theme ánh xạ, CSS/utilities dùng chung giá trị |
| OTP budget/generation/consume | Keycloak store | Không nằm ở React state hoặc Knora backend |

components/ui không import feature/shell/API client. lib không import components/app. Feature
không import page.tsx; route phối hợp feature. WorkspaceSelector chỉ phụ thuộc ui và browser client,
không import AppShell. Operator dùng interface của selector, không gọi nội bộ WorkspaceManagement.
Nếu selector cần hiển thị trong shell, truyền qua composition slot để tránh vòng shell ↔ workspaces.
WorkspaceShell là composition host thuộc feature: nhận context đã được xác thực từ server khi có,
dùng route ID làm hint và truyền WorkspaceSelector vào slot ReactNode tùy chọn của AppShell /
WorkspaceSidebar. Giữ server layout phụ trách session/capability; không đưa feature import vào shell.

Chỉ các module dùng browser event/storage mới đặt “use client”. Giữ page/layout ở server khi có thể;
không đổi toàn bộ root layout thành client chỉ để mở một modal.

### 5. Test placement và artifacts

Giữ quy ước test hiện có. Operator tests nằm trong nhóm operator; fixture/E2E không nằm trong app/public.

~~~text
frontend/tests/
├── product-header.test.tsx, dialog-menu.test.tsx [F2]
├── workspace-figma-flows.test.tsx                [U1]
├── document-figma-states.test.tsx                [U2]
├── conversation-panels.test.tsx                 [U3]
├── operator/operator-figma.test.tsx              [O1]
├── auth-figma-integration.test.tsx               [I3]
└── e2e/
    ├── figma-identity.spec.ts                   [I1–I3]
    ├── figma-ui-visual.spec.ts                  [Q1]
    ├── figma-ui-interactions.spec.ts            [Q1]
    └── support/
        ├── figma-environment.ts, figma-auth.ts  [I1; ~ Q1] fixed isolated test contracts
        ├── figma-environment.test.ts           [I1] ambient endpoint rejection
        ├── figma-state-fixtures.ts             [Q1]
        └── figma-fixture-*                     [Q1 if needed] test-only host/server
~~~

Baselines theo quy ước snapshot của Playwright; failure traces/video/screenshots vào
frontend/test-results/e2e. Java target và Next .next là build output, không phải source.
Không copy credentials, email reset thật hoặc asset URL tạm vào fixture/public.

### 6. Thứ tự hình thành cấu trúc và tiêu chí review

1. F1 mở rộng contract trong owner hiện tại, regenerate frontend/generated.
2. F2 thêm Tailwind/PostCSS/theme mapping/primitives, kiểm tra cascade trước feature migration.
3. U1 hoàn thiện WorkspaceSelector; O1 chỉ dùng sau khi interface này được review.
4. U2/U3 tách module con từng phần; giữ regression trước khi gỡ markup/CSS cũ.
5. I1–I3 bổ sung provider/theme/auth error routes trên deployment Keycloak hiện có.
6. Q1/Q2 bổ sung evidence, kiểm tra import graph/server-client separation/duplicate tokens.

- [ ] Mỗi file mới có trách nhiệm trong task, không có wrapper chỉ chuyển tiếp vô ích.
- [ ] Không có hai owner polling/submit hoặc hai bộ token cho cùng giao diện.
- [ ] Không có vòng import; client không kéo server auth vào browser bundle.
- [ ] Đường dẫn task khớp cây này; file mới và file sửa được phân biệt.
- [ ] Chỉ xóa file/selector cũ sau khi kiểm tra consumers; không di chuyển thư mục hàng loạt.
- [ ] Interface dùng chung được review trước khi task phụ thuộc bắt đầu.


## Skill sequence

All workflow skills below exist under the canonical skills directory. The Figma connector additionally
requires figma:figma-design-to-code and figma:figma-use from its installed plugin cache before its
respective tools. These are connector prerequisites, not newly installed canonical skills.

| Step | Work and output | Skills | Dependency / finish condition |
| --- | --- | --- | --- |
| 1 | Capture context, screen inventory and architectural decisions | using-superpowers, brainstorming, codebase-design | This proposal and inventory; user OTP choice recorded |
| 2 | Resolve identity platform details against official sources | research | Cited Keycloak report; code/resend/expiry/SSO/storage seams |
| 3 | Review design and task plans | writing-plans | Approve this concrete scope; no production edits before this checkpoint |
| 4 | Establish isolated base and per-slice ownership | using-git-worktrees | Clean base, baseline evidence, canonical paths |
| 5 | Add required backend display/search contracts | executing-plans, test-driven-development | F1 contract tests and generated client pass |
| 6 | Tailwind/PostCSS setup, tokens, exported assets, primitives and shared header | executing-plans, codebase-design; test-driven-development for behavior | F2 shared interface stable and accessible |
| 7 | Workspaces, documents and conversation/evidence panels | executing-plans or subagent-driven-development, test-driven-development | U1–U3, all 26 user-surface variants covered |
| 8 | Operator operations/trace/evaluation surfaces | executing-plans or subagent-driven-development, test-driven-development | O1, three variants plus lookup/provenance states |
| 9 | Keycloak theme, registration and six-digit email OTP | research, executing-plans, test-driven-development | I1–I3, 12 identity variants and live reset journey |
| 10 | Responsive, accessibility and visual comparison | verification-before-completion; systematic-debugging on failures | Q1 visual ledger and keyboard checks |
| 11 | Independent slice and integrated review | requesting-code-review, receiving-code-review | Spec and quality verdicts; important findings resolved |
| 12 | Full integration verification and handoff | verification-before-completion, finishing-a-development-branch | Q2 evidence, then user's integration choice |

Pure token/spacing edits use visual and contrast verification; do not write tests that merely copy CSS.
Behavior changes use actual failing tests before implementation.

## Slice plans

1. [Foundations and contracts](2026-10-05-figma-ui-foundations.md): F1 backend contracts, F2 UI foundation.
2. [User surfaces](2026-10-05-figma-ui-user-surfaces.md): U1 Workspaces, U2 Documents, U3 Conversations.
3. [Operator](2026-10-05-figma-ui-operator.md): O1 observations.
4. [Identity and OTP](2026-10-05-figma-ui-identity.md): I1 theme, I2 OTP, I3 application integration.
5. [Verification](2026-10-05-figma-ui-verification.md): Q1 visual/interaction coverage, Q2 regression/review.

## Execution order and ownership

Current serialized execution: F1 → F2 → U1 → U2 → U3 → I1 → I2 → I3 → O1 → Q1 → Q2.
Identity precedes O1 to establish its safe isolated live harness while daily services occupy the
existing M5 ports. Dependencies and user scope are unchanged; shared-file edits remain serialized.
Start the identity implementation early after F2 if delivery risk warrants it; its SPI/security tests
are the largest new capability. Keep shared-file changes serialized.

Default execution is sequential, with one coherent commit and review per task. A fresh implementer
can be delegated each task through subagent-driven-development. The M5 runbook allows user and
Operator work to run in parallel with U2/U3 only after F2 and U1's WorkspaceSelector are reviewed
and file ownership is disjoint.
Use dispatching-parallel-agents only for that bounded split or independent read-only investigations;
do not parallelize auth decisions, OpenAPI, shared header/CSS, or edits to the same checkout.

Proposed worktrees, created only at execution time after verifying the container and unused paths:

| Slice | Branch | Child of canonical container |
| --- | --- | --- |
| Integration/foundations | codex/figma-ui-foundations | figma-ui-foundations |
| User surfaces | codex/figma-ui-user | figma-ui-user |
| Operator | codex/figma-ui-operator | figma-ui-operator |
| Identity | codex/figma-ui-identity | figma-ui-identity |
| Verification | codex/figma-ui-verification | figma-ui-verification |

Branch from the accepted integration commit containing this baseline and dependencies, not an
unrelated remote default. Native worktree creation is appropriate only if it honors these paths;
otherwise use the skill's Git fallback. Never silently discard uncommitted user changes.

## Every task's execution loop

- [ ] Read the task, spec, applicable skill and current owning files.
- [ ] Record dependency SHAs and exact allowed files in the progress ledger.
- [ ] For behavior, add the named acceptance test and run it to observe the intended failure.
- [ ] Implement the smallest complete slice, including actual loading/error/permission paths.
- [ ] Run scoped tests and visual checks, then frontend format and format:check if applicable.
- [ ] Self-review the diff; record commands, results and screenshots/trace artifacts.
- [ ] Commit only the task's files and request a task-scoped review with base/head and spec.
- [ ] Evaluate findings using receiving-code-review, fix in the owning worktree and re-verify.
- [ ] Mark complete only after evidence and review; proceed without repeatedly requesting permission.

Use the selected skill's per-plan ledger for delegated work. Copy durable completion evidence into
docs/development/figma-ui-implementation-record.md at integration; include node coverage, commit
SHAs, approved visual deviations and known runtime limitations. A generic “looks good” is insufficient.

## Important scope boundaries

1. OTP is real backend capability in Keycloak, not a six-box frontend simulation.
2. Deletion currently returns blocked. The UI must show that outcome. The requested Figma state can
   be verified with a declared fixture, but live deletion processing is not claimed.
3. Evaluation unavailable remains a supported product state.
4. Example names, dates, answer text, counts and trace metrics are fixtures, not production constants.
5. The three early visual explorations do not become three separate interfaces.
6. Existing dark mode and M4 observations remain functional, though Figma supplies no complete
   replacement dark/M4 design.

## Review and handoff

The proposal is self-reviewed for inventory coverage, missing states, ownership and contract
consistency. Full implementation verification is future work; no test pass is asserted by this plan.

The brainstorming skill and M5 runbook require design/plan approval before implementation/worktree
creation. This document is the concrete approval artifact. After implementation passes Q2, present
the repository's integration choices: local merge, push/create PR, or retain branch as-is.
Do not automatically clean up worktrees or delete branches.
