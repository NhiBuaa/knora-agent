# Figma archived Workspace evidence notice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Add the missing archived Workspace notice to the actual Evidence Inspector.

**Architecture:** Pass the existing backend-derived Workspace archive projection to the shared
inspector. Render the source notice separately from Turn outcome and historical citation content.
No restore action, backend mutation, new state owner or API client is needed.

**Tech Stack:** React 18.3.1, TypeScript, Tailwind CSS v4, Vitest and Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).
**Reference:** Figma 183:176, node183:304 read-only workspace notice, cached full MCP structure
under foundations `.verification/figma/2026-10-05/workspaces/183-176.md`.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Workspace archived state comes from the server projection, not browser preference.
- Historical citations retain Turn, Document Version, excerpt and provenance.
- Do not fabricate answers, metrics or citation labels to match illustrative content.
- Use Tailwind CSS v4 mapped to existing semantic tokens; no generated OpenAPI edits.
- Frontend changes require format then format:check; no dependency additions.
- Existing isolated worktree and source fixtures only. No service, identity, worker, deletion,
  schema, merge, push or worktree disposition changes.
- This fixes one remaining visual requirement; full Q1/native/Q2 gates remain unresolved.

## Directory ownership and interfaces

| Exact maintained file | Responsibility |
| --- | --- |
| `frontend/components/citations/EvidenceInspector.tsx` | Optional `workspaceArchived` prop and source notice |
| `frontend/components/conversations/ConversationView.tsx` | Pass backend-derived archived prop for detail inspector |
| `frontend/components/conversations/ConversationPanels.tsx` | Pass archived prop for list Hub inspector |
| `frontend/tests/conversation-panels.test.tsx` | Actual inspector/Turn provenance and archived notice regression |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Focused notice geometry/responsive/selected-source check |
| `docs/development/figma-ui-visual-coverage.md` | Update only W5A notice evidence and retained deviations |

Consume current optional Workspace archive state; default false for existing callers. No new files
besides the task report. Existing fixture already supplies workspaceArchived for W5A; diagnose
and amend exact support scope before editing if it does not reach the actual component.

## Task 1: Archived Workspace notice in Evidence Inspector

**Dependency:** conversation parity task review accepted. Record exact starting HEAD.
**Skills:** test-driven-development, verification-before-completion, requesting-code-review;
systematic-debugging for unexpected failures.

- [ ] Read full cached MCP structure. Node183:304 is a bordered surface-subtle card below source
  context: 340×82 in the 376px inspector, 14px horizontal/13px vertical padding, 8px radius/gap.
  Copy: heading `READ-ONLY WORKSPACE`, body `Workspace archived. Restore it to ask new questions
  or make changes.` Verify exact heading/copy from source before implementation.
- [ ] Add actual component RED: archived Workspace displays notice alongside its historical
  citation; active Workspace and Conversation-only archive do not show a Workspace notice.
- [ ] Run focused existing test to confirm absence failure.
- [ ] Add optional prop and render the source card through existing semantic tokens. Pass the
  validated archive boolean in detail and list compositions. Do not infer archive from Turn
  status, disable source links, replace citation content or introduce a second restore button.
- [ ] Run focused tests confirming same returned source/version/excerpt/provenance and unchanged
  refusal/processing/interrupted presentation. Missing prop retains existing appearance.
- [ ] Add focused fixture interaction for archived notice, desktop width/fit and mobile evidence
  overlay without overflow; keyboard focus and inspector close/return remain intact.
- [ ] Recapture W5A only and regenerate its comparison/hash/workspaces sheet. Keep original MCP
  structure and PNG unchanged; record actual remaining illustrative content/control deviations.
- [ ] Update exact W5A coverage row; do not claim full screen or complete goal acceptance.
- [ ] Run format, format:check and typecheck sequentially; production build only after source is
  final. No broad80 capture repeat or live data mutation is needed for this presentation state.
- [ ] Self-review/commit exact paths; write task report and release fixture3300lease. Independent
  reviewer receives original BASE→HEAD package and separate spec/quality verdicts.

**Finish condition:** current W5A inspector implements the source notice with tests and affected
comparison evidence; no Important review finding. Continue remaining native identity/UI gates.
