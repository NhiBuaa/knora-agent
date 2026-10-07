# Figma archived Conversation bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Match A9 archived Conversation bar copy and local control geometry while preserving archive authority.
**Architecture:** Reuse ConversationComposer; source presentation applies to authoritative archived
Conversation with existing restore callback. Server-rejected read-only state keeps generic copy.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend remains source of truth for Conversation/Workspace state, revision, authorization and restore.
- Preserve submission, uncertain recovery, session expiry, archived history and existing restore handler.
- Do not infer Conversation archive from generic read-only or WORKSPACE_ARCHIVED rejection.
- Complete direct MCP structure drives layout; screenshot is a visual target, not a production asset.
- Preserve semantic tokens, exact existing assets, keyboard and mobile natural growth.
- No backend/API/fixtures/generated contracts/shared styles/Workspace composer or dependency changes.
- Mandatory frontend format then format:check. No realm/password/Vault/service/SMTP/outage/deletion/worker
  actions, installs, merge/push/cleanup or branch/worktree disposition.
- Fixture assertions do not prove live archive or full-design acceptance.

## Directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/conversations/ConversationComposer.tsx` | Existing archived Conversation presentation only |
| `frontend/tests/conversation-panels.test.tsx` | Existing revision restore, read-only and Workspace separation |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | A9 local geometry/keyboard/mobile composition |
| `docs/development/figma-ui-visual-coverage.md` | A9 correction and retained residuals |

Source complete fresh MCP128:119 and returned uncropped PNG in this plan's ignored `source/`.
Nodes46:130/131/132/180/182 define local bar. Inner region has no new static asset.

## Task 1: Correct authoritative archived Conversation bar

**Dependency:** Reset presentation independently reviewed; record clean original BASE before dispatch.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read full source and existing composer/caller. `archived` currently consumes effective readOnly;
  `onRestore` exists only when authoritative projection.archived true. Server409 can mark read-only
  from either WORKSPACE_ARCHIVED or CONVERSATION_ARCHIVED. Do not alter that admission behavior.
  Source bottom container72px, inner bar48px minimum, radius10, left padding14/right8;
  label13px normal and exact "Archived conversation · Read-only"; source restore151×34,radius8,
  label13 semibold. Width748 is source796-column minus48 outer padding; production current panel
  width is authoritative, use full available width, no forced748.
- [ ] Add meaningful component RED to existing restore case: authoritative archive exact label and
  status; keyboard/button still existing revision3 mutation. Keep generic server-rejected copy
  "This Conversation is read-only." where onRestore absent, no archive/restore claim. Existing
  Workspace composer unaffected, simultaneously archived Workspace blocks Conversation restore.
  No class-string-only proof.
- [ ] Browser RED existing prepareFixture128:119 at1440×960/390×844: local72/48 allocation,
  button151×34, text/radius/inner14/8; source copy and no question submission. Use actual modules.
  Existing fixture data/source IDs unchanged; no live mutation. Capture actual history/evidence
  untouched. Original51 outputs remain historical; new captures use separate A9 evidence folder.
- [ ] Apply minimal local archived branch:
  ```tsx
  <div
    aria-label={onRestore ? "Archived conversation controls" : "Read-only conversation controls"}
    className="flex min-h-12 w-full flex-wrap items-center justify-between gap-2 rounded-[10px] border border-border bg-surface-subtle py-1.5 pl-3.5 pr-2 text-[13px] text-text-muted"
  >
    <p role="status" className="m-0">
      {onRestore ? "Archived conversation · Read-only" : "This Conversation is read-only."}
    </p>
  ```
  Existing button stays onRestore-gated/restoreDisabled/onClick unchanged. Its local class:
  ```tsx
  className="m-0 flex min-h-[34px] w-[151px] max-w-full items-center justify-center rounded-lg border border-action bg-action/10 px-3 py-2 text-[13px] leading-4 font-semibold text-action-text disabled:opacity-50"
  ```
  Natural34 =16line+16padding+2border; desktop source151slot, mobile wraps naturally if needed.
  Preserve outer72 minimum and all active composer markup. Existing theme-aware action tint remains
  intentional source-color adaptation; no invented token/hardcoded source color.
- [ ] GREEN targeted browser once, collapsed desktop/mobile captures with full history and evidence;
  assert button keyboard focus and enabled semantics without calling blocked restore endpoint.
  Component tests exercise actual existing onRestore mutation/revision; no new live action.
  Mobile full text fit, no horizontal overflow, label/button may wrap/grow without clipping.
  Local source allocations only; don't claim global panel/answer/rail parity.
- [ ] Before/after Q1 inventory excludes root active regression-preflight only. Add new captures/JSON
  in A9 subdirectory; all pre-existing artifacts, native exports/source/original51/Operator outputs
  unchanged. Record no new assets and current existing brand/caret positions unchanged.
- [ ] Run focused conversation-panels + relevant ConversationView read-only/uncertain/session cases.
  No optional full suite or all51 capture rerun. Format→format:check→typecheck sequentially,
  self-review, exact4path commit, release owned3300. Report source map/RED/GREEN/commands/retention,
  authoritative/generic guard, mobile growth/extra controls/color/answer residuals. Root independent
  originalBASE→HEAD review.

**Finish condition:** Authoritative archived label and control geometry proven, generic rejection and
Workspace separation retained, no Important review finding. Whole-design/native acceptance remains open.

