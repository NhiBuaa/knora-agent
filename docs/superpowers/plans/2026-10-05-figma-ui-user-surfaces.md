# Figma user surfaces — Implementation Plan

> For agentic workers: use executing-plans or subagent-driven-development task by task.

**Goal:** Implement the 11 Workspace, six Document and nine Conversation variants and their flows.

**Architecture:** Existing feature components keep API/lifecycle behavior and compose focused
presentation components. Shared shell/primitives come from F2; backend projections come from F1.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS v4, Vitest, Playwright.

**Spec:** [Integration design](../specs/2026-10-05-figma-ui-integration-design.md).

**Directory structure:** Read the current/target tree, module responsibilities and dependency rules
in [the workflow's directory analysis](2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).
The task's file list and this structure must remain consistent throughout execution.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Every maintained frontend change requires format, then format:check.
- Render real server outcomes; no fabricated answers, metrics, dates or deletion success.
- Preserve idempotency, revisions, authorization, session recovery and historical citation identity.
- Use F2 semantic Tailwind utilities on migrated surfaces; retain custom CSS for specialized panel
  behavior. Remove superseded selectors only after checking remaining consumers.

## Task 1: U1 — Workspace navigation and lifecycle

**Skills:** executing-plans or subagent-driven-development, test-driven-development,
verification-before-completion; Figma connector prerequisite when reading changed nodes.

**Dependency:** F1 + F2 reviewed.

**Modify:** frontend/components/workspaces/WorkspaceManagement.tsx, WorkspaceHome.tsx;
frontend/components/shell/WorkspaceSidebar.tsx;
frontend/app/workspaces/page.tsx, [workspaceId]/page.tsx;
frontend/lib/navigation/routes.ts.
Also allow frontend/components/shell/AppShell.tsx, frontend/app/workspaces/layout.tsx and
frontend/app/operator/layout.tsx for the bounded composition change that injects WorkspaceSelector
through an optional ReactNode slot. Keep server authentication/capability resolution unchanged.
The shell must not import the Workspace feature; a feature-owned client composition host derives
route context and supplies the selector. Preserve AppShell's existing caller contract.
Also allow frontend/components/shell/MobileDrawer.tsx only for keyboard ownership when an open
drawer launches a native feature Dialog: Escape/Tab must act on the top modal, then return focus
to the still-open drawer. Preserve normal drawer Escape/focus trapping and all other behavior.

**Create:** frontend/components/workspaces/WorkspaceSelector.tsx,
CreateWorkspaceDialog.tsx, ArchiveWorkspaceDialog.tsx, ArchivedWorkspaceList.tsx;
frontend/components/workspaces/WorkspaceShell.tsx (client composition host for the shell slot);
frontend/app/workspaces/archived/page.tsx;
frontend/components/workspaces/workspaces.css.

**Exact assets:** frontend/public/icons/figma/{23c31,21b31,a4e11,ed1ac}.svg,
frontend/public/icons/figma/figma-assets.json and .gitattributes (`*.svg -text`).
Copy only originals with actual U1 selector/no-results callsites from the shared Figma cache;
preserve bytes and intrinsic root dimensions. Record provenance/checksums and verify effective
browser geometry. U2 may add d9407.svg for its Documents selector and append the same manifest;
later owners may append their own referenced icons. Do not create an icon framework.

**Tests:** existing frontend/tests/workspace-preference.test.tsx,
workspace-page-rendering.test.ts, canonical-entry.test.tsx;
frontend/tests/user-pages.test.tsx and sidebar.test.tsx for existing lifecycle/navigation behavior;
frontend/tests/operator/operator-theme.test.tsx only to refresh its navigation mock for the new
WorkspaceShell composition dependency;
new frontend/tests/workspace-figma-flows.test.tsx.
Refresh actual test filenames at task start if an existing file has moved.

**Consumes:** F1 workspace list q/cursor; existing WorkspaceResponse/ResolutionResponse,
workspace-selection BFF, create Idempotency-Key and mutate If-Match revision.
**Produces:** WorkspaceSelector as a client view using the existing selection request:

~~~tsx
type WorkspaceSelectorProps = {
  workspaceId: string | null;
  workspaceName: string | null;
  disabled?: boolean;
};
~~~

- [ ] Add RED cases for W1–W5: selector/change, create, no active workspace, archive confirmation,
  archived list, empty/no-results distinction, restore, read-only, limited and denied access.
  Test a match located on a later page through q; stale request responses must not replace a newer query.
- [ ] Implement the selector and dialogs using shared primitives. Preserve backend resolver after
  archive/restore; never select a different identity's workspace from a stored preference.
  Compose selector-in-shell through WorkspaceShell and the optional shell slot, as required by
  the workflow's dependency rules. Route IDs are hints; resolve names/access with the authenticated
  backend when absent from the first loaded page. Operator layout supplies only validated context.
  After a successful selection request, preserve the surface for direct U2/O1 consumers: Documents
  opens the selected Workspace's Documents list, discarding an old document ID; Operator reloads
  the known subsection index (operations/traces/evaluations), or /operator, discarding old trace/
  report IDs and query context. Other selections keep Workspace Home navigation. Do not add props
  or infer authority from pathname; test these destinations and refreshed server context.
- [ ] Add /workspaces/archived before the dynamic workspace route resolves it as an ID.
  “Back” returns to a valid workspace or /workspaces; denied state does not disclose its name.
- [ ] Verify this interaction expectation with the fixture's selected workspace:

~~~tsx
await user.click(screen.getByRole("button", { name: /archive workspace/i }));
expect(screen.getByRole("dialog", { name: /archive workspace/i })).toBeVisible();
await user.click(screen.getByRole("button", { name: /cancel/i }));
expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
// Assert the mutation request count remains zero after Cancel.
~~~

- [ ] Run scoped Vitest, typecheck, format, format:check. Compare all 11 W nodes from the inventory.
- [ ] Reproduce nested drawer Create/Archive Escape/Tab ownership before fixing it; cover modal
  dismissal/focus return and subsequent normal drawer dismissal in focused tests/browser evidence.
- [ ] Review/commit as feat: implement Figma workspace flows.

## Task 2: U2 — Documents, upload and detail lifecycle

**Skills:** executing-plans or subagent-driven-development, test-driven-development,
verification-before-completion.

**Dependency:** U1, F1 document projection.

**Modify:** frontend/components/documents/DocumentList.tsx, DocumentDetail.tsx;
frontend/app/workspaces/[workspaceId]/documents/page.tsx,
[workspaceId]/documents/[documentId]/page.tsx.

**Create:** frontend/components/documents/UploadDocumentDialog.tsx,
DocumentActionsMenu.tsx, DeletionRequestDialog.tsx, documents.css;
frontend/lib/documents/presentation.ts.

**Exact assets:** allow frontend/public/icons/figma/d9407.svg and append figma-assets.json only
for the actual Documents-heading selector callsite. Reuse reviewed U1 originals/attributes;
preserve exported bytes/root dimensions and verify effective geometry. Compose WorkspaceSelector
in the heading with feature presentation rules; do not duplicate selection lifecycle or change
its approved props. Documents switching opens the new Workspace's list without an old detail ID.

**Tests:** frontend/tests/documents-management.test.tsx, documents-page-workspace.test.tsx;
new frontend/tests/document-figma-states.test.tsx.

**Consumes:** generated DocumentResponse plus IngestionJobStatusResponse, existing upload,
reprocess/archive/unarchive/deletion endpoints.
**Produces:** a presentation adapter, not a domain state engine:

~~~ts
export type DocumentStatusView = {
  label: string;
  tone: "normal" | "success" | "warning" | "error";
  detail: string | null;
};
export function documentStatus(document: DocumentResponse): DocumentStatusView;
~~~

Priority: explicit deletion outcome → archive → active/failed ingestion notice plus independent
serving explanation → readiness. Never hide “previous version still served” under a single failed badge.
Ready only describes the appropriate backend readiness; answer availability renders independently.

- [ ] Add RED behavior tests for selected file/cancel/upload, duplicate click/idempotent retry,
  queued/processing/retry/failed/current/previous, search, archived visibility, menu actions,
  ready/archived detail, reprocess conflict, deletion confirmation/result and reload persistence.
- [ ] Implement the list row geometry, upload dialog, details two-column layout and menus.
  Keep existing file/media limits and durable polling; display only backend-supported progress.
- [ ] Implement six D nodes and ten Document prototype frames. For deletion preserve this assertion:

~~~tsx
expect(screen.getByText(/deletion.*blocked/i)).toBeVisible();
expect(screen.getByText(/policy.*unavailable/i)).toBeVisible();
expect(screen.queryByText("Deletion requested — not used for grounded answers"))
  .not.toBeInTheDocument();
~~~

Use a separate explicit requested-state fixture for 128:131 / 124:424. It must not replace the real
blocked response in live E2E. For all other states display the returned request state and reason.

- [ ] Render missing last_processed_at as Unavailable; “Source version” distinguishes current and
  previous served versions. Link source details through authorized routes.
- [ ] Run:

~~~powershell
npm --prefix frontend run test -- tests/documents-management.test.tsx tests/documents-page-workspace.test.tsx tests/document-figma-states.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run format
npm --prefix frontend run format:check
~~~

- [ ] Compare six D nodes and upload/archive/delete prototype transitions; review/commit as
  feat: implement Figma document lifecycle interface.

## Task 3: U3 — Conversation panels, answers and evidence

**Skills:** executing-plans or subagent-driven-development, codebase-design,
test-driven-development, verification-before-completion.

**Dependency:** U1 + U2 + shared F2 primitives.

**Modify:** frontend/components/conversations/ConversationList.tsx, ConversationView.tsx;
frontend/components/citations/CitationViewer.tsx;
frontend/app/workspaces/[workspaceId]/conversations/page.tsx,
[workspaceId]/conversations/[conversationId]/page.tsx.
Also allow frontend/components/shell/AppShell.tsx and frontend/app/workspaces/shell.css for the
bounded composition change that removes F2's interim desktop rail once ConversationPanels owns
the final ConversationRail. Preserve AppShell's existing caller contract; render one rail with
one sizing/preference owner, and retain workspace access through the shared navigation/drawer.

**Create:** frontend/components/conversations/ConversationPanels.tsx, ConversationRail.tsx,
TurnCard.tsx, ConversationComposer.tsx, conversations.css;
frontend/components/citations/EvidenceInspector.tsx;
frontend/lib/conversations/panel-preferences.ts.

**Exact assets:** allow frontend/public/icons/figma/{5b324,97a8a,cd6f9,832ce}.svg and append
figma-assets.json only for actual owning-context callsites. Reuse existing original brand/orbit
files; preserve bytes/root dimensions and verify every illustration layer. Screenshot exports
are reference evidence only. Do not create an icon renderer or redraw provided SVGs.

**Tests:** frontend/tests/conversation-view.test.tsx, conversation-list.test.tsx,
citation-viewer.test.tsx; new frontend/tests/conversation-panels.test.tsx.

**Consumes:** existing generated TurnResponse/ConversationResponse and citation array from
TurnResponse.result. Preserve current durable polling/submission handler in ConversationView.

**Produces:**

~~~ts
export type PanelPreferences = {
  rail: "expanded" | "collapsed" | "hidden";
  railWidth: number;
  inspectorOpen: boolean;
  inspectorWidth: number;
};
export type EvidenceSelection = {
  turnId: string;
  citationIndex: number;
};
~~~

EvidenceSelection indexes the immutable citation array of the selected Turn, never a global list
or current document. On history/workspace change validate the selection or clear it.
Keep UI preferences in sessionStorage keyed by safe identity scope + workspace; store no evidence.
Use observed Figma widths as defaults, then clamp to the available center-column minimum.
The authenticated server conversation route may pass only safe issuer/subject scope into its
feature component; never pass token/session secrets. Include a bounded preferences-clear export
for I3's sign-out integration, removing this module's namespaced keys only. AccountMenu remains
I3-owned; no U3 edit there. Keep preference storage separate from immutable EvidenceSelection.

- [ ] Add RED tests for five panel states, drag/keyboard/reset, citation focus, session restore,
  narrow-screen drawer/sheet, and composer placement.
- [ ] Add RED tests for answered/processing/refusal/interrupted/system-error; keep original tests
  for uncertain submission, 401 recovery, busy, archived and pagination.
- [ ] Extract presentation components while preserving the request/recovery logic. Map stage labels
  from known server values; unknown stages use a generic Processing label.
- [ ] Implement evidence selection and the selected source inspector. Example acceptance:

~~~tsx
await user.click(screen.getByRole("button", { name: /citation 1/i }));
expect(screen.getByRole("complementary", { name: /evidence/i })).toBeVisible();
expect(screen.getByText("Historical excerpt from the selected turn")).toBeVisible();
// Fixture includes a newer document version; assert its replacement excerpt is absent.
~~~

- [ ] Implement suggestion chips that fill the draft, explicit send, authentic source metadata,
  archive read-only notice and restore action. Restore does not override an archived Workspace.
  “Try again” first reconciles uncertain history and reuses the existing request identity as required.
- [ ] Add sidebar search using q with debouncing/cancellation; maintain load-more and archived list.
- [ ] Run:

~~~powershell
npm --prefix frontend run test -- tests/conversation-view.test.tsx tests/conversation-list.test.tsx tests/citation-viewer.test.tsx tests/conversation-panels.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run format
npm --prefix frontend run format:check
~~~

- [ ] Compare all nine A variants, nine conversation prototype frames and the ten interaction/state
  examples. Review/commit as feat: implement Figma conversation and evidence panels.

**Acceptance:** no status timer fabricates an answer; controlled refusal and system error differ;
historical citations remain pinned; resizing never moves the composer into another column.
