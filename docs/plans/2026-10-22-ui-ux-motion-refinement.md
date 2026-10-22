# UI/UX Motion Refinement Implementation Plan

> **For agentic workers:** Dùng Skill `executing-plans` nếu thực sự có trong catalog của phiên agy; đọc source trước khi dùng. Triển khai từng việc theo checkpoint. Không tự sinh subagent hoặc Issue con.

**Goal:** Giữ nhận diện Knora, làm rõ thao tác và trạng thái, thêm chuyển động mở ngắn có thể tắt theo preference, giữ nội dung đọc ổn định.

**Architecture:** Tái sử dụng native dialog, Menu, focus helper, token và CSS cạnh component. Không đổi API công khai của Dialog/Menu, không thêm exit/presence state, không trì hoãn thao tác vì animation.

**Tech Stack:** React 18.3.1, Next 15.5.24, CSS/Tailwind hiện có, Vitest, Playwright cài sẵn 1.63.0.

**Spec:** [Tinh chỉnh trải nghiệm và chuyển động](../specs/2026-10-22-ui-ux-motion-refinement.md).

**Trạng thái:** kế hoạch đề xuất theo yêu cầu người dùng, chưa được duyệt để sửa mã. Liên quan [#212](https://github.com/NhiBuaa/knora-agent/issues/212). Người dùng xác nhận giữ nhận diện; #212 yêu cầu duyệt thiết kế/phạm vi cụ thể trước implementation.

## Global Constraints

- Giữ màu xanh, Inter, Roboto Slab, nhận diện lá, bố cục ba vùng Conversation và hệ thống component hiện có.
- Không thêm thư viện chuyển động, lớp quản lý hiện diện hoặc trì hoãn focus.
- Hiệu ứng mở ngắn, đóng tức thì; không animation lại answer/history khi polling/selection/resize.
- Menu 140ms, dialog 180ms, drawer/sheet 200ms ease-out; control color 120ms; reduced motion hiện ngay.
- Giữ ngoại lệ chữ trắng/nút xanh đã ghi trong visual tokens; không tuyên bố full WCAG AA.
- Mobile target độc lập 44px là mục tiêu sản phẩm; AA 2.5.8 dùng 24px với ngoại lệ đúng ngữ cảnh.
- Không thay domain/API, authorization, mutation/retry/revision, generated OpenAPI, prompt/generation, OTP/cooldown hoặc provider.
- Không gộp #179 clipboard, #171 reupload semantics, #183/#191 policy hoặc Workbench chưa tích hợp.
- Không merge/deploy/đóng Issue hoặc liên hệ chủ nhiệm khác ngoài quyền đã có.
- Spec và kế hoạch giữ đúng docs/specs và docs/plans; tiến độ trong #212/PR khi có quyền công bố.

## Bản đồ file và phạm vi có điều kiện

Đường dẫn là repository-relative. Đọc AGENTS tại worktree và quy tắc con trước sửa. Chỉ sửa file có finding được duyệt.

| Phần việc | File sản phẩm | Test/fixture sở hữu | Vai trò |
| --- | --- | --- | --- |
| Motion và vùng bấm dùng chung | frontend/styles/tokens.css, frontend/styles/controls.css, frontend/components/ui/Dialog.tsx, frontend/components/ui/Menu.tsx | frontend/tests/dialog-menu.test.tsx, frontend/tests/ui-primitives.test.tsx, frontend/tests/design-tokens.test.tsx | CSS mở, bounds/focus, native submit |
| Navigation drawer nếu còn reachable | frontend/components/shell/MobileDrawer.tsx và CSS sở hữu selector mobile-navigation-panel | frontend/tests/sidebar.test.tsx | Không đổi nested-modal ownership |
| Conversation và evidence | frontend/components/conversations/ConversationPanels.tsx, conversations.css, ConversationComposer.tsx, TurnCard.tsx; frontend/components/citations/CitationViewer.tsx, EvidenceInspector.tsx | frontend/tests/conversation-panels.test.tsx, conversation-view.test.tsx, answer-rendering.test.tsx, citation-viewer.test.tsx | Target, drawer/sheet, copy refusal có duyệt |
| Documents/Workspace | frontend/components/documents/UploadDocumentDialog.tsx, DocumentDetail.tsx, DocumentList.tsx; frontend/components/workspaces/WorkspaceSelector.tsx, CreateWorkspaceDialog.tsx | frontend/tests/documents-management.test.tsx, document-figma-states.test.tsx, conversation-list.test.tsx | Chỉ khoảng cách, hit area, nhãn/trạng thái đã xác nhận |
| Feedback | frontend/components/ui/Notice.tsx, LeafLoading.tsx, leaf-loading.css | frontend/tests/smoke-feedback.test.tsx, smoke-feedback-controls.test.tsx | Giữ semantic status, không tạo animation mới cho mọi notice |
| Browser | Không đổi config mặc định để che test lỗi | frontend/tests/e2e/figma-ui-interactions.spec.ts, figma-ui-visual.spec.ts, conversation-scroll.spec.ts và support/figma-state-fixtures.ts | Baseline và before/after, animation bật/tắt rõ ràng |
| Auth/operator bổ sung | Chỉ file trình bày được liệt kê sau G0 và duyệt G1 | Các test hiện có theo Feature Map; themes/knora/login/resources/css/knora.css nếu cần | Không tự mở rộng sang logic bảo mật hoặc report/backend |

Không phải danh sách phải sửa hết. MobileDrawer hiện không được AppShell render trực tiếp; trước khi thêm motion phải chứng minh route/caller thật còn sử dụng. Không sửa component chết để tăng độ phủ danh nghĩa.

## G0. Chốt đúng đối tượng và bổ sung baseline ứng dụng

**Đầu vào:** SHA nền d1efd6999310067462c17062bccdf8e6a4b8f7c5, spec, artifact fixture cục bộ.
**Đầu ra:** bảng finding có reproduction, ảnh/trạng thái, đề xuất file/copy, phạm vi được xin duyệt. Chưa sửa sản phẩm.

- [ ] Đọc CONTEXT.md, docs/agents/domain.md, docs/agents/issue-tracker.md, docs/standards/architecture.md, các seam được AGENTS yêu cầu, docs/runbooks/agent-environment.md và docs/development/feature-map.md.
- [ ] Kiểm tra đích và quyền sở hữu. Không dùng primary codex/test hay worktree #183/#191/#192.

```powershell
git -C C:\Developer\Projects\knora-agent-worktree\docs-ui-ux-motion-design rev-parse --show-toplevel
git -C C:\Developer\Projects\knora-agent-worktree\docs-ui-ux-motion-design branch --show-current
git -C C:\Developer\Projects\knora-agent-worktree\docs-ui-ux-motion-design status --short
git -C C:\Developer\Projects\knora-agent-worktree\docs-ui-ux-motion-design worktree list --porcelain
```

- [ ] Đọc lại #212 và thảo luận bằng gh; đối chiếu main và các PR giao nhau. Không tự rebase/merge công việc khác. Nếu nền đổi, ghi delta và xét lại ảnh/contract liên quan.
- [ ] Xác nhận CodeGraph status riêng worktree trước truy vết; catalog agy không mặc nhiên giống Codex. Không cài skill/tool/hook hoặc sửa config toàn máy.
- [ ] Kiểm tra manifest và JUnit baseline. 21 visual + 9 interaction là fixture; không dùng thay app.
- [ ] Theo agent-environment, kiểm tra Docker/dependency/browser, chọn project test mới và result dir mới; kiểm tra quyền sở hữu và deterministic-local trong -Run trước browser mutation. Nếu port bận bởi session khác, dừng nhánh runtime này và báo chủ dự án; không kill để lấy chỗ.
- [ ] Rà app ở 1440×960 và 390×844: sign-in, tạo/chọn Workspace, upload Markdown nhỏ, document detail/archive, tạo/đổi Conversation, mở nguồn, session-expired/permission/error đã có trong harness. Không khởi động worker hay provider để lấy answer đẹp; dùng fixture cho answered/refused nếu app chỉ queued.
- [ ] Đo F2/F3 bằng DOM sau layout ổn định. Với composer, so sánh empty/multiline/clear, Enter/Shift+Enter/composition, resize 390→1440→390; ghi rõ nếu không tái hiện F3 thì bỏ sửa composer.
- [ ] Rà native login/register/reset/OTP bằng nguồn/harness hiện có; nếu cần realm/OTP profile chưa sẵn hoặc khác quyền, ghi chưa kiểm chứng, không đổi theme/auth logic chỉ để có số liệu.
- [ ] Rà dark/system, 320px và zoom 200% trên các vùng sẽ sửa. Với screen reader/điện thoại thật chưa có, ghi khoảng trống, không ghi PASS.
- [ ] Lập danh sách before/after dự kiến: ID finding, route/state, old/new copy nếu có, file, tiêu chí AC liên quan, ảnh/hash, rủi ro. Giữ những bề mặt tốt nguyên trạng.

**Checkpoint:** Sau tối đa 60 phút baseline độc lập, báo phát hiện và thiếu dữ liệu. Đây là mốc báo cáo, không phải quyền bỏ bước bắt buộc. Không lặp khởi động vô hạn khi cùng lỗi.

## G1. Chủ dự án duyệt thiết kế và phạm vi

- [ ] Trình spec cùng danh sách G0 để duyệt cụ thể: motion mở/đóng tức thì, target mobile, copy refusal, composer chỉ nếu tái hiện, file auth/operator thực sự cần sửa.
- [ ] Ghi approval tham chiếu phiên hoặc comment #212 có thật; không tự đánh dấu duyệt vì người dùng đã yêu cầu phân tích/lập kế hoạch.
- [ ] Nếu chưa duyệt: dừng sửa mã, giữ artifact và báo trạng thái đang chờ duyệt. Có thể tiếp tục đọc/hoàn thiện bằng chứng không phụ thuộc approval.
- [ ] Khi duyệt và bắt đầu capability mới, theo hướng dẫn Hindsight của phiên đó để ghi initiative trước code; không tự thay đổi memory cục bộ của người dùng.
- [ ] Tạo/tái sử dụng worktree triển khai được giao tại canonical container. Đề xuất branch `feat/ui-ux-motion-refinement`, thư mục `feat-ui-ux-motion-refinement`, từ commit tài liệu đã xác minh hoặc main mới được thống nhất. Kiểm tra ref/path chưa có và thông báo đích trước sửa. Không sửa trên branch docs chỉ vì nó đang mở.

## Task 1. Motion mở và target dùng chung

**Interfaces:** Giữ `Dialog({open,title,onClose,children,className})`, `Menu({label,children,boundarySelector})`; không public prop/state mới.
**Phụ thuộc:** G1 đạt; hunk giao nhau có ACK nếu cần.
**Deliverable:** overlay được duyệt có motion mở, thao tác và focus giữ nguyên trong mọi chế độ.

- [ ] Chọn các test hiện có trong dialog-menu/ui-primitives/sidebar và browser fixture làm regression gate. Thêm test chỉ cho hành vi mới/rủi ro thật: mở→Escape→mở ngay, backdrop, focus restoration và native menu submit một lần. Chạy test mới trước sửa; xác nhận thất bại đúng yêu cầu mới, không vì môi trường.
- [ ] Thêm duration/easing vào token chỉ nếu dùng chung; dùng keyframe/class trong controls.css. Ví dụ thiết kế (phải tích hợp theo layer CSS có sẵn, không dán thành override toàn trang):

```css
.kn-dialog__content {
  animation: kn-dialog-enter 180ms ease-out;
}
@keyframes kn-dialog-enter {
  from { opacity: 0.85; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .kn-dialog__content { animation: none; }
}
```

- [ ] Giữ dialog parent/bounds/modality/focus nguyên vòng đời; không thêm timeout, animationend listener hoặc delayed unmount. Menu giữ phần tử đo geometry/ref/role/event bên ngoài; motion bên trong nếu cần transform. Không làm native submit button bị unmount trước submit.
- [ ] Tăng hit area target được duyệt, giữ icon/label đúng nhận diện. Kiểm tra wrapper không clip ring hoặc tạo vùng bấm chồng nhau.
- [ ] Chạy subset owning tests, browser mở nhanh ở no-preference và reduce; so sánh menu bounds trước/sau, Tab/Shift+Tab/arrows/Home/End/Escape, background inert và focus trả về.
- [ ] Rà diff và commit riêng cho nhóm shared UI sau format/typecheck. Không sửa unrelated callers.

**Ví dụ browser test mới dùng helper hiện có** trong source-fixtures describe; G0 xác nhận fixture ID/label trước tích hợp:

```typescript
test("workspace dialog remains usable through rapid reopen with reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const unexpected = await prepareFixture(page, "152:128");
  const trigger = page.getByRole("button", { name: "Create workspace", exact: true });
  const dialog = page.getByRole("dialog", { name: "Create workspace" });
  await trigger.click();
  await expect(page.getByLabel("Workspace name", { exact: true })).toBeFocused();
  expect(await dialog.locator(".kn-dialog__content").evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await trigger.click();
  await expect(dialog).toBeVisible();
  await page.waitForTimeout(250); // Cross the longest old animation window to detect a stale close.
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  expect(unexpected).toEqual([]);
});
```

Bổ sung phiên bản no-preference riêng với kiểm tra thời lượng/kết thúc. Không dùng screenshot animations=disabled trong test timing. Test giảm chuyển động không tự chứng minh bản bình thường có hiệu ứng đúng.

## Task 2. Conversation, evidence và phản hồi hàng ngày

**Interfaces:** Giữ submit handler, draft, readOnly/archived guards, EvidenceSelection và panel preferences theo identity/workspace.
**Deliverable:** vùng bấm rõ, mở sheet/rail nhẹ, nội dung chat ổn định; chỉ copy/refinement đã được duyệt.

- [ ] Thêm test hành vi đã duyệt vào conversation-panels/view/answer-rendering/citation-viewer và browser fixture. Với F3 chỉ thêm test reproduction khi có số đo app; không test giả thiết từ screenshot.
- [ ] Áp 200ms/12px cho nội dung rail drawer/evidence sheet qua CSS owner, thay rule chung dialog bằng selector rõ thứ tự. Không animate cột desktop hoặc divider.
- [ ] Tăng mobile hitarea Ask/panel controls đã duyệt; kiểm tra bàn phím ảo không che action và composer giữ 44–160px theo nội dung nếu sửa được duyệt.
- [ ] Nếu copy refusal được duyệt, chỉ đổi trình bày tại TurnCard. Giữ result.decision/refusal_reason, trace, citation validation và renderer. Giữ mã chẩn đoán trong lớp phụ theo thiết kế đã duyệt.
- [ ] Không thêm typewriter, optimistic answer, tự scroll mỗi poll hoặc replay fade trên history. Chọn citation không sửa answer hoặc source_version.
- [ ] Với status updates, tái dùng LeafLoading/Notice đúng role; không thêm alert cho mọi error/info. Nhãn stage tiếp tục tồn tại khi art tĩnh.
- [ ] Chạy owning tests và conversation-scroll fixtures; thử nhiều Turn, selection qua lại, close/reopen, route/workspace switch, refresh, archived/read-only, no-preference/reduce.
- [ ] Nếu diff chạm AnswerContent/presentation.py/prompt, dừng hunk đó và đối chiếu #183/#191; không giải quyết bằng copy đoạn mã của nhánh khác.

## Task 3. Documents/Workspace và phần bổ sung đã duyệt

**Interfaces:** Không đổi request/retry/If-Match, dedup/archive semantics hoặc Document projection.
**Deliverable:** hành động/status dễ hiểu, không báo thành công trước backend; vùng phụ chỉ sửa theo finding.

- [ ] Viết test cho target/copy/error mới đã duyệt trong owning test; tái dùng state fixtures sẵn có, không thay payload để làm ảnh đẹp.
- [ ] Kiểm tra upload selected→submitting→accepted/error; giữ khác biệt accepted/processing/Ready. Không thêm auto retry, không âm thầm restore archived document khi reupload.
- [ ] Tinh chỉnh spacing/hitarea/lỗi cạnh field ở component cần sửa; không nâng chiều cao mọi hàng/dàn lại layout toàn trang.
- [ ] Kiểm tra dialog Cancel/Escape không gửi mutation; nút submit chỉ một request; chọn/xóa file bằng keyboard/touch.
- [ ] Nếu G1 không duyệt auth/operator thì dừng ở ghi nhận inventory. Nếu duyệt, liệt kê file cụ thể từ G0 và giữ form/security/provenance contract; cần kiểm tra no-JS/OTP bằng profile đúng cho phần auth tác động.
- [ ] Rerun documents-management, document-figma-states, owning Workspace/operator/auth tests liên quan. Không dùng fixture thay thật cho auth/permission/ingestion.

## Task 4. Kiểm chứng, review và bàn giao nghiệm thu

**Deliverable:** diff nhỏ có bằng chứng gắn exact SHA; chủ dự án quyết định tích hợp.

- [ ] Từ đúng worktree triển khai, chạy owning tests trước; sau đó typecheck, lint, format và build. Đọc exit code và output. Các lệnh mẫu cho tập thay đổi chính:

```powershell
npm --prefix frontend test -- tests/dialog-menu.test.tsx tests/ui-primitives.test.tsx tests/sidebar.test.tsx tests/conversation-panels.test.tsx tests/conversation-view.test.tsx tests/answer-rendering.test.tsx tests/citation-viewer.test.tsx tests/documents-management.test.tsx tests/document-figma-states.test.tsx tests/design-tokens.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run build
git diff --check
```

- [ ] Nếu sửa maintained shared files trong danh sách package.json, chạy format:shared và format:shared:check. Nếu không sửa Python, không chạy/sửa Python hàng loạt. Không hand-edit generated/knora-openapi.ts.
- [ ] Rerun selected21 visual và selected9 interaction với output dir mới; mở ảnh before/after cùng viewport/theme/data. Mở rộng test cho bề mặt thực sự đã sửa, không chỉ rerun subset cũ.
- [ ] Chạy test timing mới với animation bật; thêm kiểm tra reduce thay đổi trong lúc đang mở. Capture ảnh cuối không thay bằng chứng chuyển động.
- [ ] Thử 10 lần chuỗi open/close/reopen, Escape khi animation chưa xong, menu submit khi chưa xong, citation đổi nhanh. Không còn modal ẩn chặn click/focus, stale callback hoặc duplicate mutation.
- [ ] Đo performance trước/sau cùng máy/browser/viewport/fixture/CPU setting và workload. Quan sát trace render/layout ở cửa sổ animation 200ms; nếu chưa đo thì chỉ ghi thiết kế tránh animate layout, không tuyên bố nhanh/mượt hơn.
- [ ] Chạy luồng application đúng agent-environment cho thao tác bị tác động. Nếu profile release áp dụng, chạy exact commit theo CI runbook; fixture không thay thế:

```powershell
$sha = (git rev-parse HEAD).Trim()
./scripts/run-runtime-verification.ps1 -SubjectSha $sha -WorkflowSha $sha -Profile application -RunId local -RunAttempt 1
```

- [ ] Nếu sửa native auth/OTP presentation, chọn thêm profile otp theo runbook; không tự reuse project có dữ liệu hoặc runtime envelope #183. Không chạy provider thật để “xác nhận UI”.
- [ ] Rà keyboard, screen-reader status/focus và touch trên thiết bị có sẵn. Nếu thiếu thiết bị/công cụ, ghi khoảng trống để chủ dự án quyết định nghiệm thu; không kết luận accessibility đầy đủ.
- [ ] Trước commit/push: kiểm tra lại worktree, branch, diff, base và PR destination. Tài liệu/commit riêng được phép trong công việc được giao; push/PR theo quyền hiện tại. Không tự công bố nếu chưa được phép.
- [ ] Review connected callers và exact diff; kiểm tra response/citation/permission/archive invariants. Với CI, ghi run/head và CI required; sửa mới sau kiểm tra phải chạy lại phần liên quan.
- [ ] Báo riêng: đã sửa code; kiểm tra local; CI; application runtime; motion/performance; review; merge; deploy. NO_MATCH, skipped, timeout và pending không là PASS.
- [ ] Giữ artifact/hashes/cleanup evidence. Cleanup chỉ stack/process do lượt chạy này sở hữu; không xóa worktree/branch hoặc node_modules junction của phiên khác.

## Đồng hồ, điều kiện dừng và tiếp tục

- Sau mỗi task: báo diff, test thực chạy, rủi ro còn lại; không chờ hết toàn bộ frontend.
- Một kiểm tra bị timeout/lỗi phải ghi kết quả thật; chỉ chạy lại sau có nguyên nhân và thay đổi điều kiện rõ ràng. Không đổi timeout/gate chỉ để xanh.
- Dừng phần phụ thuộc khi thiếu approval G1, ACK hunk chung, quyền worktree, đúng subject SHA, listener ownership hoặc công cụ có sẵn. Tiếp tục các việc đọc độc lập.
- Không vượt gate bằng đổi primary branch, stash/reset, chép thay đổi vào worktree khác, tắt sandbox hoặc sửa permission/credential.
- Khi resume: đọc #212/spec/plan, xác minh subject và diff; dùng artifact/path/hash, không tin lời báo của agent trước làm bằng chứng.
- Không lập master plan viết lại frontend, không phát sinh Issue con tự động. Chỉ đề xuất tách việc khi finding mới vượt phạm vi được duyệt.
