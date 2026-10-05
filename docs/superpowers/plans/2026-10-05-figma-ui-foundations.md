# Figma UI foundations — Implementation Plan

> For agentic workers: use executing-plans or subagent-driven-development task by task.

**Goal:** Supply truthful display/search contracts and reusable visual foundations.

**Architecture:** Add small backward-compatible projections to existing backend owners. Adapt the
existing primitives/AppShell to Figma using Tailwind CSS v4 and shared semantic tokens without
changing authentication or domain authority.

**Tech Stack:** Python/FastAPI/SQLAlchemy, Next.js/React/TypeScript, Tailwind CSS v4/PostCSS, pytest/Vitest.

**Spec:** [Integration design](../specs/2026-10-05-figma-ui-integration-design.md).

**Directory structure:** Read the current/target tree, module responsibilities and dependency rules
in [the workflow's directory analysis](2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).
The task's file list and this structure must remain consistent throughout execution.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Every maintained frontend change requires format, then format:check.
- Keep ingestion lifecycle, source-version identity and serving state separate.
- Deletion policy remains unavailable; do not silently introduce purge or withdrawal semantics.

## Task 1: F1 — Display projections and complete search

**Skills:** executing-plans, codebase-design, test-driven-development,
verification-before-completion. Use brainstorming/domain-modeling only if an implementation
discovery actually requires a changed domain decision; route confirmed changes through CONTEXT.md
and the relevant ADR rather than inventing a parallel glossary.

**Dependency:** approved spec; isolated worktree and baseline recorded.

**Modify:**

- backend/src/knora/ingestion/documents.py
- backend/src/knora/adapters/postgres/document_reader.py
- backend/src/knora/adapters/http/schemas.py
- backend/src/knora/workspaces/ports.py, service.py
- backend/src/knora/conversations/ports.py, service.py
- backend/src/knora/adapters/postgres/workspace_store.py, conversation_store.py
- backend/src/knora/adapters/http/workspaces.py, conversations.py
- frontend/generated/knora-openapi.ts only through the exporter.

**Tests:** backend/test/adapters/http/test_document_routes.py;
backend/test/adapters/http/test_workspaces.py; backend/test/adapters/http/test_conversations.py;
backend/test/adapters/postgres/test_workspace_store.py;
backend/test/adapters/postgres/test_conversation_store.py;
new backend/test/adapters/postgres/test_document_ui_projection.py;
backend/test/api/test_openapi_contract.py.

**Produces:**

~~~python
# Additive DocumentProjection / DocumentResponse fields
served_document_version_id: str | None = None
last_processed_at: datetime | None = None
answer_availability: Literal["available", "unavailable", "unknown"] = "unknown"
deletion_request: DocumentDeletionRequestProjection | None = None
# HTTP schema uses DocumentDeletionRequestResponse, defined before DocumentResponse.
~~~

The existing deletion projection's fields remain request_id, document_id, state, failure_reason.
All document fields come from one read transaction. Select the latest successful terminal timestamp
for the served version, never the failed latest attempt. Answer availability follows the existing
retrieval/corpus compatibility rules; do not equate non-null pointers with usable evidence.
If a historical record cannot support the answer, emit unknown/null.

Add q: str | None = None as the last optional parameter to existing workspace and conversation
list service/store methods and HTTP query. Trim surrounding whitespace, limit to 200 characters,
case-insensitive literal substring match on name/title, escape SQL wildcard characters. Apply
ownership/archive/q predicates before limit. Preserve existing default behavior when q is absent.
Bind new search cursors to normalized query and archive filter; reject mismatched cursors rather
than silently skipping rows. No frontend-only first-page search for these lists.

- [ ] Add tests: owner-only search; matching item beyond first page; archived filters; literal %/_ input;
  query/cursor mismatch; cross-workspace denied before lookup; projection ready/previous/unavailable;
  failed ingestion does not overwrite last success; blocked deletion survives a fresh GET.
- [ ] Run the scoped pytest files and capture the intended new-contract failures.
- [ ] Implement the additive projections and query propagation through the existing seams.
- [ ] Regenerate the client and check the contract:

~~~powershell
./.venv/Scripts/python scripts/export_openapi.py
./.venv/Scripts/python scripts/export_openapi.py --check
./.venv/Scripts/python -m pytest backend/test/adapters/http/test_document_routes.py backend/test/adapters/http/test_workspaces.py backend/test/adapters/http/test_conversations.py backend/test/adapters/postgres/test_workspace_store.py backend/test/adapters/postgres/test_conversation_store.py backend/test/adapters/postgres/test_document_ui_projection.py backend/test/api/test_openapi_contract.py
npm --prefix frontend run typecheck
npm --prefix frontend run format
npm --prefix frontend run format:check
~~~

**Acceptance assertions** to include in the projection test, using the suite's transaction fixtures:

~~~python
assert projection.serving_state == "previous"
assert projection.served_document_version_id == successful_version.id
assert projection.last_processed_at == successful_job.terminal_at
assert projection.deletion_request.state == "blocked"
assert projection.deletion_request.failure_reason == "DOCUMENT_DELETION_POLICY_UNAVAILABLE"
~~~

- [ ] Review/commit as feat: expose UI document projections and scoped list search.

**Stop condition:** an eligibility projection would require changing retrieval semantics or
retention policy. Keep the proposed UI contract truthful and resolve that domain change separately.

## Task 2: F2 — Tailwind setup, tokens, assets, primitives and product header

**Skills:** executing-plans, codebase-design; test-driven-development for dialog/menu/navigation
behavior. Use figma:figma-design-to-code before refreshing design context.

**Dependency:** F1 schema checkpoint. All surfaces depend on this task's stable interfaces.

**Modify:** frontend/package.json, frontend/package-lock.json;
frontend/styles/tokens.css, typography.css, controls.css;
frontend/app/globals.css; frontend/components/ui/Button.tsx, Field.tsx, Notice.tsx,
StatusBadge.tsx, EmptyState.tsx, PageHeader.tsx;
frontend/components/shell/AppShell.tsx, AccountMenu.tsx, MobileDrawer.tsx;
frontend/app/workspaces/layout.tsx, shell.css; frontend/app/operator/layout.tsx.

**Create:** frontend/postcss.config.mjs; frontend/styles/tailwind-theme.css;
frontend/components/shell/ProductHeader.tsx;
frontend/components/ui/Dialog.tsx, Menu.tsx;
frontend/public/brand/knora-leaf.svg, knora-leaf-large.svg, orbit-inner.png, orbit-outer.png;
frontend/public/brand/figma-assets.json.

**Tests:** existing frontend/tests/ui-primitives.test.tsx, design-tokens.test.tsx,
theme.test.tsx, sidebar.test.tsx, canonical-routes.test.tsx;
new frontend/tests/product-header.test.tsx, dialog-menu.test.tsx.

**Produces these focused contracts:**

~~~tsx
type ProductHeaderProps = {
  activeSection: "conversations" | "documents" | "operator";
  workspaceId: string | null;
  canOpenOperator: boolean;
  account: React.ReactNode;
};
type DialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
};
type MenuProps = {
  label: string;
  children: React.ReactNode;
};
~~~

AppShell retains its existing caller contract while consuming ProductHeader internally.
ProductHeader receives authorized presentation inputs; it does not fetch or infer privileges.
Dialog owns labelled modal semantics, focus trap/return and Escape. Menu owns trigger, keyboard
navigation, dismissal and focus return; feature components own actions and disabled reasons.

- [ ] Install/configure Tailwind at implementation time:

~~~powershell
npm --prefix frontend install tailwindcss@4 @tailwindcss/postcss@4
~~~

Keep existing PostCSS dependency/override; commit resolved versions in package-lock.json.
Create frontend/postcss.config.mjs:

~~~js
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
~~~

Import once at the start of frontend/app/globals.css:

~~~css
@import "tailwindcss";
@import "../styles/tokens.css";
@import "../styles/tailwind-theme.css";
@import "../styles/typography.css";
~~~

Expose existing semantic variables in frontend/styles/tailwind-theme.css:

~~~css
@theme inline {
  --color-page: var(--page);
  --color-surface: var(--surface);
  --color-surface-subtle: var(--surface-subtle);
  --color-text-primary: var(--text-primary);
  --color-text-muted: var(--text-muted);
  --color-action: var(--action);
  --color-action-foreground: var(--action-foreground);
  --color-border: var(--border);
  --color-focus: var(--focus);
}
~~~

Extend mappings for remaining semantic status/signature tokens and local font variables.
Existing data-theme/system-preference overrides remain the dark-mode authority.
Use complete static utility class names for conditional variants so production extraction finds them.

- [ ] Audit Preflight and existing unlayered main/nav/button/section rules. Scope legacy rules to
  remaining consumers and place maintained base/component rules in explicit layers so they do not
  unexpectedly override utilities. Check borders, headings, lists, forms and focus rings.
  Remove superseded CSS only after its consumers have migrated.
- [ ] Refresh representative Figma nodes 128:110, 128:120, 194:194, 228:212 and component 20:2.
  Export original leaf/orbit assets; record node, local path and checksum in figma-assets.json.
  Reuse the exact asset references in the inventory; use no temporary Figma URL in production.
- [ ] Reconcile tokens, typography, spacing, dividers and status badges. Keep accessible foreground,
  focus and dark tokens. Measure contrast for muted text and green controls; log any justified
  difference from Figma in the visual ledger.
- [ ] Add behavior tests, including this dialog acceptance shape:

~~~tsx
render(<Dialog open title="Create workspace" onClose={onClose}>
  <button type="button">Cancel</button>
</Dialog>);
expect(screen.getByRole("dialog", { name: "Create workspace" })).toBeVisible();
await user.keyboard("{Escape}");
expect(onClose).toHaveBeenCalledTimes(1);
~~~

- [ ] Observe RED for new behavior. Implement the shared components and adapt AppShell.
  Top navigation is 64px; account menu uses real safe identity fields. Preserve theme controls.
  Do not remove workspace/conversation functionality while changing shell placement.
- [ ] Verify scoped tests and format:

~~~powershell
npm --prefix frontend run test -- tests/ui-primitives.test.tsx tests/design-tokens.test.tsx tests/theme.test.tsx tests/sidebar.test.tsx tests/canonical-routes.test.tsx tests/product-header.test.tsx tests/dialog-menu.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run format
npm --prefix frontend run format:check
~~~

- [ ] Run npm --prefix frontend run build and inspect the production-rendered page for utility
  generation, semantic colors and responsive variants. Visually compare header, tokens, controls
  and modal at 1440×960; check keyboard/dark mode after Preflight and cascade changes.
- [ ] Review/commit as feat: align shared product UI with Figma.

**Acceptance:** consumers can use the shared header/dialog/menu without implementing authorization,
focus management or duplicate design-token values. Backend contract fixtures still render successfully.

References: [Tailwind with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
and [theme variable mapping](https://tailwindcss.com/docs/theme).
