# Figma Trace content measures — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Correct the remaining measured Trace summary, inner content widths and context hierarchy.
**Architecture:** Adjust only TraceView's existing layout/text measures, keeping natural dynamic
growth, semantic outcome badges and disclosure owners. Relative source geometry drives the layout;
absolute whole-page origins remain separately measured rather than guessed.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, Workspace archive/revision, outcomes, metrics and observations.
- Preserve all current actions, safe navigation, historical provenance and missing-data semantics.
- Never substitute illustrative Figma values for runtime data or invent report quality scores.
- Full MCP structures supply source geometry; PNG comparison verifies actual composition.
- Reuse exact local assets at intrinsic dimensions. No SVG editing or temporary asset URLs.
- Use semantic tokens; preserve contrast, focus, responsive text fit and keyboard use.
- No shared primitive/styles, generated API, backend/schema/client/dependency or production fixture edits.
- Run frontend format then format:check. No services/workers/realm/password/Vault/deletion/outage
  actions, installs, merge, push or branch/worktree removal.
- Native/full-regression and remaining source deviations are separate unresolved requirements.

## Exact directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/operator/TraceView.tsx` | Relative summary/content/context measures with dynamic growth |
| `frontend/tests/operator/operator-figma.test.tsx` | Actual Trace outcome/provenance preservation regressions |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Measured RED/GREEN and readable mobile proof |
| `docs/development/figma-ui-visual-coverage.md` | Addressed source measures and truthful remaining geometry |

No changes to OperatorFrame, selector or shared StatusBadge. Source cache:
`.verification/figma/q1/evidence/operator-prototypes-2026-10-07/216-573.md` plus full screenshot
and current desktop/mobile measurementJSONs. No redundant Figma request required.

## Task 1: Correct Trace internal measures

**Dependency:** Typography/badge task independently reviewed. Record clean exact BASE.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read complete source216:573 and current TraceView before edits. Verify current measured
  summary86.140625px versus source84; candidate width780 versus source760; result badge relative
  left670 versus source650; context row40 versus source38; citation/timing headings24 versus22.
- [ ] Add focused browser RED assertions on actual desktop boxes and relative offsets, including
  preserved complete data and no horizontal overflow. Do not manufacture fixed content heights.
- [ ] Summary216:615 is84px inclusive outer borders; inner signal216:616 is82px minimum with
  label216:61713px/17px text region and value216:61822px/26px. Derive local spacing from source
  label top15/value top39, preserving natural growth for long actual labels/values and two-column
  mobile rows. Zero and missing observations retain their actual meanings.
- [ ] Keep detail columns780/380/gap40 and answer measure630. Observed result heading/badge row
  uses source760px content measure inside780px column, so ANSWER starts650px from column origin.
  Candidate source rows216:642/649 are760px wide inside780px column; retain dynamic height and
  Retrieval details. Source names have420px maximum text measure, candidate explanation730px;
  use responsive max widths and surrounding-row wrap, retaining whole150px SELECTED and full text.
- [ ] Match context rows216:664/668/672/676 to38px minimum,13px/17px type, label170/value200/gap10.
  Source text top7px and divider top37px determine padding; long opaque IDs/configurations may
  increase row height naturally. No fixed row height or abbreviated backend IDs.
- [ ] Set only citation-mapping and phase-timing headings to source18px/22px, retaining trace-context
  title20px/24px. Preserve all aliases, mapped ChunkIDs/source names and unavailable timing states;
  extra provenance lines and disclosures remain readable and scrollable.
- [ ] Run relevant actual component regressions and focused Trace prototype case1440/390 GREEN;
  then five affected Operator prototype/guidance cases once to check shared measurement helper.
  Verify all exact prior selector/caret/lookup/badge geometry remains unchanged, including intrinsic
  SVG quantization, no writes/unexpected requests, and whole mobile words/provenance/overflow fit.
- [ ] Update only affected Trace captures/JSON and the combined Operator comparison HTML. Preserve
  four other Operator cases' captures and all original51/unrelated artifacts by hash; exclude only
  root-owned active regression-preflight logs. No full51 recapture in this bounded task.
- [ ] Report current remaining global origins/vertical coordinates, added supported content and
  semantic contrast honestly. Candidate source102px is not a clipping mandate. Full-frame content
  may exceed960px; preserve natural scroll, never omit validation to fit the supplied frame.
- [ ] Run format→format:check→typecheck, focused checks; write concise RED/GREEN/commands and link
  existing JSON for exhaustive residuals. Self-review, commit four owned paths, release3300 and
  submit originalBASE→HEAD for independent spec/quality review. Root final regression remains separate.

**Finish condition:** Named relative source measures match with complete authoritative state,
provenance, default badge behavior and readable mobile growth; no Important review finding.
Remaining whole-page/native/full-goal acceptance remains open.
