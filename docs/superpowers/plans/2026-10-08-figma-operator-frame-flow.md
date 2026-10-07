# Figma Operator frame flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Match the shared Operator content flow, tab slots and lookup alignment from direct MCP structure.
**Architecture:** Local OperatorFrame layout translates source absolute slots into natural vertical
flow. Keep authoritative data, responsive growth and existing controls. Do not alter shared header.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, Workspace identity, observations, outcomes and availability.
- Preserve all existing actions, optional Workspace scope, provenance, full IDs, zero/missing semantics.
- Implement from complete MCP structures; screenshots compare composition only, never production assets.
- Preserve exact local brand/caret intrinsic geometry, semantic tokens, keyboard focus and mobile readability.
- No shared header/primitives/tokens, generated API, backend/client/dependencies or production fixtures edits.
- Frontend format then format:check is mandatory. No service/worker/realm/Vault/password/deletion/outage
  actions, installs, merge, push, cleanup or branch/worktree disposition.
- Source browser fixtures do not prove backend/native/full-goal acceptance; record remaining deviations.

## Directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/operator/OperatorFrame.tsx` | Shared flow, navigation slots/divider and lookup alignment |
| `frontend/tests/operator/operator-figma.test.tsx` | Existing exact scoped navigation, refresh and optional-scope behavior |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Actual shared frame measures across five compositions |
| `docs/development/figma-ui-visual-coverage.md` | Resolved relative/global geometry and honest residuals |

No changes to OperationsView, TraceView, EvaluationView, WorkspaceSelector, guidance or shared styles.
Sources: five complete structures in `operator-prototypes-2026-10-07`; fresh direct MCP216:467 in
`.superpowers/figma/q1/evidence/operator-flow-source-2026-10-08/216-467.md`. Metadata confirms text
dimensions omitted by `normal` in original generated JSX. Root retained full screenshot response.

## Task 1: Correct shared Operator flow and lookup slots

**Dependency:** Operations81ff9e9 independently approved; clean original BASE recorded by root.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read source216:467–488 and all five current compositions. Source content origin globaly109
  (header sourcebodyy65 +44); currenty108. Shared header remains64 in production, so local main
  desktop top padding45 reproduces source content origin without adding a page-wide frame border.
  Keep desktop x120; source Operationsx121 remains a separately recorded border-model difference.
- [ ] Add meaningful actual-browser RED to existing five cases, measuring relative to Workspace label:
  selector top18,height26; title top58,height42; description top105; nav top151, contentheight42;
  divider top193,height1. Source trace/Operations description19px with16px type; Evaluation region24.
  Full copy must grow at mobile and cannot be clipped to a fixed height. Desktop trace max-width870
  follows source; use a19px line region for trace/Operations and24 for Evaluation. Font ink bounds
  remain separate from allocated line boxes. Do not fabricate an exact line box from PNG pixels.
- [ ] Minimal OperatorFrame local flow:

  ```tsx
  // Main startsy109 under unchanged64px shared header.
  className="... pt-[45px] ..."
  // Existing selector natural44px allocation and14px title gap remain.
  // Title42px ends at100;5px gap gives description top105.
  className={`mt-[5px] mb-0 text-base text-text-muted ${active === "evaluations" ? "leading-6" : "leading-[19px]"} ${active === "traces" ? "max-w-[870px]" : ""}`}
  // Source description ends124 or129; natural gap gives nav151.
  className={`... min-h-[42px] ... ${active === "evaluations" ? "mt-[22px]" : "mt-[27px]"}`}
  ```

  Keep nav42px allocated region plus a separate1px source divider after it, rather than asserting
  a43px nav including border equals42px source nav. Natural responsive content may increase height.
  Use an aria-hidden decorative divider; preserve nav accessible name and active state.
- [ ] Tabs source offsets0/104/182 with28px gaps and widths76/50/82,27px height at7.5px below navtop.
  Trace label17px region top5 inside tab; active2px underline at25,3px after label end. Operations
  source216:374–380 uses label17px at top0 and8px gap before the same underline at25; preserve this
  variant with top0/padding-bottom8. Evaluation nodes216:726/728/730 and783/785/787 instead allocate20px labels,400 inactive and
  500 active. Preserve that explicit source variant:20px line, top5/no bottom gap plus border2.
  Use existing Link elements and explicit minimum widths/27px minimum; trace17px line,
  top5/padding-bottom3 and border2; Operations17px/top0/bottom8/border2. Active underline visible and inactive transparent. Retain
  trace/Operations500 inactive/600 active, Evaluation400 inactive/500 active. No stronger width
  clamp that clips enlarged/translated text. Desktop min slots
  establish source offsets for supplied labels; mobile accessible links remain keyboard reachable.
- [ ] Lookup source top211 relative content; divider bottom194→17px gap. Use17px local form gap.
  Natural label13px region then5px gap gives field/button top229. Evaluation source label has24px
  allocated region overlapping its controls by6px; preserve natural13px region to avoid overlap,
  use its source500 weight (trace600), and record24→13 allocation as a deliberate natural-flow
  adaptation rather than a parity claim. Input34 vs button36 should top-align,
  replacing center alignment's trace-only1px field drift. Keep all existing field/button widths,
  font sizes and minimum heights, input padding, pending growth, error and optional scope disclosure.
  Source lookup56 allocation exceeds label13+gap5+button36=54; use56px form minimum, mobile naturally
  taller. This is source trailing2px allocation and moves guidance to relative326 with its59px gap.
  Lookup fields/buttons sourceglobal338; guidance sourceglobal435 and columns527. Preserve guidance
  internal92px offset and dimensions, and all previous per-view minimums; global origins shift naturally.
- [ ] Reuse source geometry helper without duplicating blocks. Measure tab boxes and text regions;
  verify all five compositions at1440×960 and390×844. RED on intended geometry then GREEN once
  for five cases; retry only a concrete failed covering case. Asset readiness uses existing bounded
  polling and exact dimensions/hashes. Set consistent owned child color environment.
- [ ] Run relevant Operator component tests covering scoped GET navigation, same-ID refresh, optional
  Workspace overrides, menu/keyboard and unchanged default selector presentation. Tests assert actual
  behavior, not only class strings. No write/unexpected request and complete mobile text fit.
- [ ] Refresh five affected desktop/mobile PNG/JSON and both comparison HTMLs; hash preserve original51,
  native/source structures and all unrelated artifacts, excluding only root active regression-preflight.
  Fresh216:467 source file is part of before inventory and must remain unchanged. No crop/asset edits.
- [ ] Record remaining body/header border-model x differences, natural data wrapping and supported extra
  controls, semantic contrast and unavailable native proof. Do not accept whole-page parity solely for
  corrected frame. Format→format:check→typecheck sequentially, self-review, exact four-path commit.
  Full report includes source map, RED/GREEN/commands, retention and residuals. Release owned3300
  before root originalBASE→HEAD independent review; no optional full frontend suite (root owns it).

**Finish condition:** Shared frame/lookup relative measures proven at desktop, responsive copy/actions
preserved, no Important review finding. Remaining full-design/native acceptance stays open.
