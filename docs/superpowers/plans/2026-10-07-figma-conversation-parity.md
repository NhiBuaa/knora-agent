# Figma Conversation parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans
> to implement this plan task-by-task. This is follow-up work within the user's approved full
> Figma implementation, derived from verified Q1 deviations; it does not reduce that objective.

**Goal:** Implement repeated-citation deselection and the archived Workspace bottom restore action.

**Architecture:** Keep Conversation selection local and Turn-bound. Pass the server-validated
Workspace revision into the existing Conversation surface and call the existing Workspace restore
API; backend resolution and signed preference decide the resulting destination. No backend schema,
identity, outcome or ownership changes are needed.

**Tech Stack:** Next.js 15.5.24, React 18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.

**Spec:** [Approved Figma integration design](../specs/2026-10-05-figma-ui-integration-design.md).
**Source:** Figma file BOVOx0bt1qYJFg9nBq6EaQ, prototype edge44 and archived Workspace screen
183:176. Full cached MCP structures are retained in the foundations worktree under
`.superpowers/figma/2026-10-05/`; read structure before comparing PNGs.
**Diagnosis:** Q1 coverage document records both unimplemented behaviors. Repeated citation
selection flows directly to `setSelection`; the composer only receives a Conversation restore
callback when the Conversation itself is archived. Workspace archive also makes it read-only,
but its bottom Workspace restore action is absent.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, reset codes and passwords in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual
  generated OpenAPI edits.
- Historical citations remain bound to their Turn, Document Version and returned provenance.
- Do not clear archived state, change a revision or fabricate success locally.
- Frontend changes require `npm --prefix frontend run format`, then `format:check`.
- Use the existing isolated worktree and guarded knora-figma-e2e graph. No realm, service,
  database schema, deletion request or worker changes; retain synthetic data and volumes.
- Q1 source evidence is partial. Native OTP/Vault/MFA/CSP/outage, missing source references and
  other recorded deviations remain required work; this plan cannot waive them.
- No merge, push, branch deletion or worktree removal without the user's integration choice.

## Directory ownership and interfaces

| Files | Responsibility |
| --- | --- |
| `frontend/components/conversations/ConversationView.tsx` | Turn selection, restore orchestration and current authoritative props |
| `frontend/components/conversations/ConversationComposer.tsx` | Bottom archived state and correct restore control |
| `frontend/app/workspaces/[workspaceId]/conversations/page.tsx` and `[conversationId]/page.tsx` | Server-authorized Workspace and Conversation projections |
| `frontend/components/workspaces/ArchiveWorkspaceDialog.tsx` | Existing `resolveWorkspaceAfterMutation(hint)`; consume unchanged |
| `frontend/tests/conversation-panels.test.tsx` | Selection, focus, mutation and archived-state regressions |
| `frontend/tests/auth-figma-integration.test.tsx` | Existing route composition/authorized Workspace projection regression |
| `frontend/tests/e2e/support/figma-fixture-view.tsx`, `figma-state-fixtures.ts` | Actual module composition with deterministic test-only data |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Focused fixture interaction and owned live verification |
| `docs/development/figma-ui-visual-coverage.md` | Updated evidence and remaining gaps |

No new general state framework or API client. If a required route test belongs elsewhere, diagnose
the existing test and amend exact scope before editing. Keep source files readable under Prettier.

## Task 1: Citation deselection and archived Workspace restore

**Skills:** test-driven-development, systematic-debugging for unexpected failures,
verification-before-completion, requesting-code-review.

**Dependency:** Q1 Important review corrections accepted. Record exact HEAD as this task's BASE.

**Modify:** the exact Conversation component/route/test/fixture/coverage files in the table above.
Do not modify ArchiveWorkspaceDialog.tsx or backend/generated files; consume its existing seam.

**Consumes:** `EvidenceSelection { turnId, citationIndex }`, validated Workspace revision from
`WorkspaceResponse`, `browserRequest`, and `resolveWorkspaceAfterMutation(workspaceId)`.
**Produces:** toggle behavior and a backend-authorized Workspace restore CTA. Existing
Conversation restore remains distinct. Keep added props optional for existing consumers;
missing validated revision cannot authorize or enable Workspace restore.

- [ ] Read cached full MCP structure for 183:176 and edge44 source/target. Confirm the 72px bottom
  bar, text `Archived workspace · Read-only`, `Restore the workspace to make changes again.`
  and `Restore workspace` button (184×40 desktop target). Respect responsive wrapping.
- [ ] Add selection RED: same Turn/citation twice clears the selected inspector and pressed state;
  another Turn with the same index selects its own citation. Verify mouse and keyboard action.
- [ ] Run the focused existing panel test and confirm failure for the actual missing toggle.
- [ ] Implement a functional selection update comparing both IDs. Preserve historical evidence,
  panel preferences and mobile focus return; do not close unrelated panels or alter Turn outcomes.
- [ ] Run affected selection tests, including different citations and stale/missing citation reset.
- [ ] Add archived Workspace RED with a validated revision. Assert the bottom Workspace CTA and
  POST `/v1/workspaces/{encodedId}/restore` with `If-Match` equal to that revision.
- [ ] Add missing-revision, pending duplicate click, 401/403/conflict and successful restore tests.
  Failure keeps the archived state and shows an error. No Conversation restore POST is substituted.
- [ ] Add both-archived regression: after successful Workspace restoration, the Conversation is
  still archived until its distinct native restore succeeds. Do not render an active composer early.
- [ ] Pass `workspace.revision` from both server routes. Route tests prove the value comes from the
  already-authorized projection, not browser hints or a constant. Keep existing identity scope.
- [ ] Wire the bottom action through the existing request/resolve/preference flow. Navigate only
  after success; preserve read-only until authoritative reload/navigation. Resolver failure after
  a successful mutation must explain recovery without claiming the mutation failed.
- [ ] Retain existing Conversation restore label/behavior for Conversation-only archive. Expired
  session cannot start either mutation. Do not mask denied access with local state changes.
- [ ] Update the test host composition with the validated synthetic revision and existing restore
  projection interception; unexpected paths remain rejected. Replace old edge44 persistence
  assertion with the desired toggle regression.
- [ ] Run only affected unit/route tests and focused fixture interactions. Check bottom CTA fit at
  1440×960 and 390×844, keyboard activation, focus and no horizontal overflow.
- [ ] Through the existing guarded live harness, archive/restore a newly owned synthetic Workspace
  from its Conversation bottom CTA. Verify actual returned status and resolved destination. Keep
  a second archived Conversation archived. No deletion, worker or identity actions are needed.
- [ ] Recapture only affected A7/W5A states and transition evidence; regenerate their comparisons,
  hashes and sheets. Do not overwrite original Figma structures or accept a screenshot baseline
  as source parity. Update exact coverage rows; leave unrelated gaps explicit.
- [ ] Run format, format:check, typecheck and production build sequentially. Record exact commands,
  RED/GREEN outputs, artifact IDs, remaining deviations and frontend lease release in the task report.
- [ ] Self-review, commit exact paths and hand the original BASE→HEAD diff to an independent reviewer
  for separate spec and quality verdicts. Fix Important findings before accepting this task.

**Completion condition:** both required behaviors are implemented with authoritative live/fixture
evidence and no Important review finding. This completes this follow-up task, not full Q1/Q2 or
the full Figma goal. Continue to the remaining UI/identity gates in the approved workflow.
