# Figma Document menu destinations — Implementation Plan

> **For agentic workers:** use subagent-driven-development sequentially with independent Spec and Quality review.

**Goal:** Reach the authoritative Archived/Ready detail after successful menu Archive/Restore, matching prototype16/27.

**Spec:** [Approved integration](../specs/2026-10-05-figma-ui-integration-design.md). Direct MCP read on Oct8 confirms117:715 →124:231 and117:894 →124:141; retained exact response is in the native-runtime SDD source audit. These controls are not deferred in Issues149–152.

**Architecture:** DocumentList owns the existing scoped mutation and revision precondition. Use its acknowledged response and canonical Next router destination. DocumentDetail continues reading backend projections. Preserve failure/conflict/abort behavior.

**Tech Stack:** Next.js15, React18, Tailwind4, Vitest/Testing Library and Playwright.

## Global Constraints

- Execute after native OTP functional work, in the existing Figma worktree with clean tracked source; record fresh BASE. One implementer, no children.
- No backend/API/permission/lifecycle/schema/shared Menu/fixture changes. No artificial archive projection or navigation before server success.
- Preserve If-Match, scope abort, duplicate submission guard and safe errors. No deletion confirmation, purge, outage or container cleanup.
- Preserve all prior evidence; new evidence goes under `.verification/figma/q1/evidence/document-menu-destinations-2026-10-08/`.
- Maintained frontend edits require format → format:check → typecheck. Exact originalBASE →finalHEAD review.

## Task 1: Navigate only after acknowledged Archive/Restore

**Modify:** `frontend/components/documents/DocumentList.tsx`, `frontend/tests/document-figma-states.test.tsx`, `frontend/tests/e2e/figma-document-navigation.spec.ts`, `docs/development/figma-ui-visual-coverage.md`, `docs/development/figma-ui-implementation-record.md`.

**Interfaces:** Existing archive(document: DocumentResponse) consumes scoped POST200 plus loaded revision. It produces router.push(routes.document(workspaceId,id)) after success. Detail performs normal server-authorized GET; archived back returns checked list, restored back returns bare list. Component tests mock useRouter; live test exercises owned synthetic data and source-version stability.

- [ ] Add RED to owning component tests: successful Ready menu archive invokes the canonical detail destination; successful Archived menu restore invokes the same destination. Verify exact POST archive/unarchive plus If-Match, no duplicate mutation while pending, no push while response unresolved. Replace the old assertion expecting an empty list after archive.

```tsx
await userEvent.click(screen.getByRole("menuitem", { name: "Archive document" }));
await waitFor(() =>
  expect(navigation.push).toHaveBeenCalledWith("/workspaces/ws-1/documents/doc-1"),
);
expect(new Headers(fetcher.mock.calls[1][1].headers).get("If-Match")).toBe("7");
```

- [ ] Add failure cases409,403,401 and rejected fetch: no navigation; existing conflict reload and error wording remain. Add held response resolved after Workspace rerender/unmount: old scope cannot navigate or modify new scope. Use deferred Promise/actual user events, no tests mirroring only class strings.
- [ ] Run focused RED: `npm --prefix frontend exec vitest run tests/document-figma-states.test.tsx tests/documents-management.test.tsx` from root, or equivalent existing npm test command with scoped paths from frontend. Record actual commands/exits and the missing destination failure.
- [ ] Apply minimal local implementation: import/useRouter and replace only successful archive() tail after existing scope/status guards. Keep reprocess, upload and deletion behavior untouched.

```tsx
const router = useRouter();
// Inside archive(), after aborted/conflict/non-OK guards:
router.push(routes.document(workspaceId, id));
```

- [ ] Update the existing named live Documents journey to assert exact detail immediately after menu Archive200/Restore200. Capture new Archived/Ready destination states and JSON route/status/source identity. Back out through actual detail links to exercise existing menu/View details/filter coverage. Retain version IDs, revision increments, available→unavailable→available, null deletion and synchronous Markdown/null job qualification. Preserve the original artifacts; change this journey's evidence directory only to the new folder.
- [ ] Run named live journey via `FIGMA_TEST_MODE=application` and existing `playwright.figma.config.ts`, with owned services ready. Playwright owns frontend3300. No parallel dev server. Use fresh retained synthetic account/Workspace/Document, never delete them. A failing destination GET is a real gap, not fixture success.
- [ ] Run scoped component GREEN, format then format:check then typecheck, and named live journey after final frontend edits. Inspect new captures and JSON; audit existing Q1 hashes unchanged. Update only observed rows16/27 and current summary; source filenames/data composition remain qualified, no physical deletion/PDF processing/full89 acceptance.
- [ ] Self-review, commit exactly five paths, write report and request independent Spec/Quality review of original recorded range. No whole-design completion or merge claim.
