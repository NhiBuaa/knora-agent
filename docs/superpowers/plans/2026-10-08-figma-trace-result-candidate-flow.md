# Figma Trace result and candidate flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Correct Trace result and candidate internal flow using complete direct MCP structure.
**Architecture:** Keep TraceView's typed observations and disclosure controls; map source slots to
natural layout with minimum regions and responsive growth. Canonical IDs and evidence remain complete.
**Tech Stack:** Next.js 15.5.24, React 18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
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
| `frontend/components/operator/TraceView.tsx` | Result, citation and candidate natural flow |
| `frontend/tests/operator/operator-views.test.tsx` | Existing typed Trace behavior and full disclosure checks |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Trace relative measures and keyboard/mobile evidence |
| `docs/development/figma-ui-visual-coverage.md` | Resolved internal flow and retained adaptations |

No edits to OperatorFrame, guidance, selectors, other Operator views or shared styles.
Source: complete fresh direct MCP `216:635` and returned render at
`.superpowers/figma/q1/evidence/trace-content-source-2026-10-08/216-635.md` and `216-635.png`.
Complete prior frame source remains `operator-prototypes-2026-10-07/216-573.md`.
No new assets in this inner region.

## Task 1: Match result and candidate slots while retaining disclosure

**Dependency:** Frame-flow independently approved; record clean BASE before dispatch.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.
**Interfaces:** Consume existing `TraceView({ trace }: { trace: OperatorTraceResponse })`;
produce unchanged interface and authoritative display semantics.

- [ ] Read full source and current TraceView/tests. Relative to detail column:
  result heading top0,height24; decision badge top0,height28; answer top34,height40,width630;
  citation region top82,height24; provenance heading top126,height24; description top156,height18;
  first candidate top190,width760. Candidate inner slots: name top7,height20,max420;
  badge top4,height28,width150; metadata top33,height17; excerpt top60,height20,max610.
  Source candidates102 high and8 apart; source last divider at101.
- [ ] Extend existing geometry collector once for result heading/answer/citations/provenance/list,
  candidate name/badge/metadata/excerpt/disclosure offsets. Browser assertions compare source
  allocations relative to column/candidate, separately recording glyph ink. RED targeted Trace
  comparison `216:573` at desktop1440×960/mobile390×844, before production edit.
  Existing full typed fixture copy and selectors must remain unchanged.
- [ ] Align result header items-start rather than center. Keep28px minimum from badge.
  Answer natural margin6 from result row gives34. Refusal status continues natural growth.
  Answer20 line-height and630max-width unchanged. Citation row margin8,min-height24, explicit16px
  text line, gap8; marker minimum38×22, medium label and existing semantic tokens. Retain actual
  marker values, count, no-marker Unavailable, no fabricated source aliases or force width clamp.
  Citation row may wrap; provenance margin20 after it gives126 for the supplied two-line answer.

  ```tsx
  <div className="flex max-w-[760px] flex-wrap items-start justify-between gap-3">
  <p className="mt-1.5 mb-0 max-w-[630px] text-sm leading-5">
  <div className="mt-2 flex min-h-6 flex-wrap items-center gap-2 text-xs leading-4 text-text-muted">
  <span className="flex min-h-[22px] min-w-[38px] items-center justify-center rounded-full border border-border bg-surface-subtle px-2 font-medium">
  <section aria-labelledby="candidate-heading" className="mt-5 mb-0 border-0 bg-transparent p-0">
  ```

- [ ] Keep provenance description margin6 and18px line/730max. List natural margin16 gives190.
  List gap8 between candidates. Candidate padding-top4; header minimum28 with items-start;
  name margin-top3,line20,max420; metadata margin1,min-height17,leading16; excerpt margin10,
  min-height20,leading18,max610. Preserve all source, rank, line, fusion and content values and
  responsive wrapping. Do not replace dynamic excerpt with short sample.

  ```tsx
  <ol className="mt-4 mb-0 grid list-none gap-2 p-0">
  <li className="m-0 min-h-[102px] max-w-[760px] border-b border-border pt-1 pb-[21px]">
  <div className="flex min-h-7 flex-wrap items-start justify-between gap-3">
  <strong className="mt-[3px] min-w-0 max-w-[420px] text-[15px] leading-5 font-semibold [overflow-wrap:anywhere]">
  <p className="mt-px mb-0 min-h-[17px] text-xs leading-4 text-text-muted [overflow-wrap:anywhere]">
  <p className="mt-2.5 mb-0 min-h-5 max-w-[610px] text-[13px] leading-[18px] [overflow-wrap:anywhere]">
  ```

  Preserve existing `Retrieval details` after excerpt, margin8 and explicit18px natural line-height,
  full Chunk ID/Document Version/Chunk Set/fusion/reason/vector/FTS disclosures.
  Source excerpt ends80 then21px trailing+divider gives102; retained disclosure adds26px natural
  content and yields128 minimum for short rows. Record this adaptation, not102 parity. Second row
  follows actual prior row height+8, not source absolute300. Expanded disclosures/mobile/full text
  increase height naturally; no fixed outer420 or page960 clamp.
- [ ] Relevant component RED/GREEN checks: full answer/refusal/unavailable, empty candidates,
  all persisted markers, long full candidate identity and both branch contributions remain
  inspectable after expanding details. Reuse existing tests; add only missing behavior.
  No class-string-only proof and no unnecessary new fixture.
- [ ] GREEN targeted Trace comparison once; all previous Trace summary/context/badge and frame checks
  still pass. Desktop asserts source-relative slots and documented128 adapted candidate minimum;
  mobile asserts full copy fits available parent, no horizontal overflow, keyboard disclosure
  open/close with complete IDs visible and natural growth. Expanded details test must not overwrite
  collapsed reference capture; capture collapsed first and disclose measured mobile growth.
  Only rerun covering cases after a concrete failure; no unrelated five-case or full-suite rerun.
- [ ] Refresh only Trace desktop/mobile PNG/JSON and comparison HTMLs. Before/after hash inventory
  covers whole Q1 except root active regression-preflight; original51/native/source/unrelated outputs
  unchanged. Both HTMLs may be byte-identical. Root fresh216:635 source retained unchanged.
- [ ] Document relative resolved geometry and adaptations: retained disclosures128 vs source102,
  second-row natural drift, opaque data/alias differences, semantic theme, no native/backend parity.
  Run format→format:check→typecheck sequentially; investigate any failure before rerun.
  Self-review and commit exactly four owned paths. Report commands/results/RED/GREEN/retention/source
  and unresolved items. Release owned3300 before independent originalBASE→HEAD review.

**Finish condition:** Relative result/candidate source slots verified, full dynamic observations and
accessible disclosure retained, no Important independent-review finding. Whole-design/native goal open.

