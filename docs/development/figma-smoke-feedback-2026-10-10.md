# Figma smoke feedback implementation plan

Goal: implement the user review from 2026-10-10 without dropping any listed requirement.
Architecture: an unsaved conversation lives only in the browser; existing authenticated and idempotent APIs admit its first question. Keep authorization, optimistic revisions and authoritative recovery intact.
Stack: Next.js, React, TypeScript, Tailwind v4, Python, Keycloak theme.
Execution: sequential, using systematic-debugging, test-driven-development and verification-before-completion. Reuse feat/figma-ui-implementation; update the local test checkout after verification.

## Accepted behavior and files

- [x] Login always lands at /workspaces; logout returns to login. Files: app/page.tsx, api/auth/callback/route.ts, auth entry tests. Keep RP logout and CSRF checks.
- [x] Brand returns to /workspaces; header Documents selects a valid active workspace from the management page. Files: AppShell.tsx, WorkspaceShell.tsx, ProductHeader.tsx; header tests.
- [x] Selecting, creating and restoring workspace enters new conversation; old detail URL redirects. Files: navigation/routes.ts, workspace components, workspace page; navigation tests.
- [x] One draft only, never persisted until first submission; New conversation in draft is a no-op. Files: ConversationList.tsx, ConversationView.tsx, ConversationPanels.tsx; draft and creation tests.
- [x] Draft shows empty illustration immediately without a history fetch. Stable recent list, no promotion on selection. Archive uses theme Dialog and redirects selected conversation to draft, including the last conversation. Files: ConversationView.tsx, ConversationList.tsx; list/view tests.
- [x] Workspace actions move into one per-row menu with rename modal; workspace links look actionable. Files: WorkspaceManagement.tsx and workspaces.css; workspace tests.
- [x] Focus border belongs to composer/search wrapper. Enter sends, Shift+Enter inserts newline, IME does not send, textarea grows to bounded height. Files: ConversationComposer.tsx, search wrappers, controls.css; keyboard tests and browser checks.
- [x] Suggestions submit directly, follow the question language (Vietnamese/English). Processing dots animate with reduced-motion fallback. Files: TurnCard.tsx, ConversationView.tsx, conversations.css; suggestion tests.
- [x] Upload drop target reacts to file drag and resets after leave/drop. Files: UploadDocumentDialog.tsx; drag tests.
- [x] Portrait Keycloak layout avoids overlap at intermediate widths; leaf favicon for app and login. Files: theme CSS, theme.properties, app/layout.tsx; portrait browser checks.
- [x] Remove separate header Menu; account avatar remains the entry to appearance/logout. Theme choices use styled accessible controls; hover on recent/archived rows. Files: AppShell.tsx, AccountMenu.tsx, ThemeControl.tsx, Menu.tsx; account/theme tests.
- [x] Excerpt cuts at complete words and clearly marks omission; investigate page chunk starts without fabricating source text or changing historical locators. Files: answering projection and tests, PDF chunking if necessary. Any derivation change requires a versioned configuration and preserves historical evidence.

## Verification cycle
For each behavior: write regression test, run to observe expected failure, implement, rerun targeted suite. Finish with frontend format, format:check, typecheck and full tests; backend focused/full tests for changed projections, Ruff, OpenAPI check, both Compose configurations and git diff --check. Browser checks cover portrait login, draft first send, selected archive, header navigation, focus, drop and logout. Preserve existing data and useful tests; do not remove old persisted empty conversations automatically.

## Implementation and verification record

All listed behavior changes are implemented. Unit/component verification: 431 frontend cases passed before the final cleanup; a final sequential run is in progress. Backend verification: 1685 passed, 16 skipped, 28 warnings. Ruff, generated OpenAPI check and both Compose configurations passed. Compose emitted warnings about optional credentials absent in the validation shell; this is structural validation, not deployment validation.

Browser verification on the feature preview used a uniquely named local synthetic workspace. First question admission produced a conversation titled from its Vietnamese question; New Conversation returned a clean unsaved draft; a second first question produced a different ID. Archiving the selected second conversation and then the last remaining first conversation both returned to the empty draft and removed each from Recent. Header Documents/Conversations worked; search and multiline composer focus outlines were visually inspected. The expanded composer exposed a shrinking illustration; the illustration now retains its own height and the content pane scrolls.

Final daily-port login/portrait/logout verification remains pending until the test branch receives the source commit. Do not infer this verification from component tests.

Excerpt previews omit potentially partial edge words and add an ellipsis. A clear sentence-ending mark retains the last word. This conservative preview can omit an already complete word when no adjacent page character is available. Original chunk bytes, historical ranges, checksums and source access remain intact.

Existing persisted empty conversations are retained; this change prevents future eager creation and does not delete user history. No extra scope was deferred. Browser suites that asserted eager creation or browser confirmation were updated to the approved draft and themed-dialog behavior.
