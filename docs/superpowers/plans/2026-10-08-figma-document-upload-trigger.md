# Figma Document Upload trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development for implementation and independent review.

**Goal:** Match the Documents header Upload button's source154×38px allocation and15px plus glyph.

**Architecture:** Correct the owning DocumentList Button callsite using existing Tailwind utilities; shared Button and upload logic stay authoritative. Add real-browser geometry and local dialog interaction checks.

**Tech Stack:** Next.js, TypeScript, Tailwind CSS v4, Playwright.

**Spec:** [Approved Figma integration](../specs/2026-10-05-figma-ui-integration-design.md); direct MCP128:120 retained in this conversation, exact node54:193/194/195 excerpt in `.superpowers/sdd/2026-10-08-figma-document-upload-trigger/source-54-193-excerpt.md`.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Every maintained frontend change requires format, then format:check.
- No manual generated OpenAPI edits; no shared Button/CSS/token changes.
- Only local fixture interactions, no API writes. Mobile is adaptation because no source mobile frame exists.
- Preserve prior captures; all captures for this task use `.verification/figma/q1/evidence/document-upload-trigger-2026-10-08/`.

## File structure

DocumentList owns header geometry and upload-open state. Existing figma-ui-interactions composes
the real module with production CSS, fonts and exact GET fixtures. Coverage records source parity
and remaining gaps. Modify exactly those three files; ignored task source/report/evidence is separate.

## Task 1: Correct and prove the Upload trigger

**Modify exactly:** `frontend/components/documents/DocumentList.tsx`,
`frontend/tests/e2e/figma-ui-interactions.spec.ts`, `docs/development/figma-ui-visual-coverage.md`.

**Consumes:** existing Button, prepareFixture(page,"128:120"), captureIdentity,
fixture host and existing Documents local interaction cases.
**Produces:** source154×38 allocation, plus15 and label13; unchanged real dialog open/cancel/Escape/focus.

- [ ] Read source excerpt and owning code. Use systematic-debugging and test-driven-development. The root cause is auto sizing against a fixed source allocation; inspect computed font/padding/gap and content fit to confirm.
- [ ] Add a dedicated desktop1440×960/mobile390×844 browser case using prepareFixture. Capture current header before asserting exact width154 and height38. Assert plus font15, label13, gap8, radius8, full text/content fit and document horizontal fit. Derive expected values from MCP, not code helpers. Prove RED against current production.
- [ ] Apply the minimal local callsite correction: width154, existing height/min-height38, prevent flex shrink, plus text15. Adjust only local padding if loaded-font content cannot fit154; never clip text or change the shared primitive. A proposed class uses `w-[154px] shrink-0` alongside the current height, and the decorative span gets `text-[15px]`. Measure before selecting padding.
- [ ] GREEN both viewports: open actual Upload dialog through the trigger, assert disabled empty submit, cancel and reopen/Escape with focus restored. No file submission. Wait fonts/images, verify leaf18×18 and caret8×5 exact nonempty local asset slots/callsites. Record geometry and captures in new folder. Unexpected requests/writes must be empty. Inspect both viewport images.
- [ ] Run the new focused fixture case and existing Documents local interactions (move that existing test's outputs to the new task folder so old files survive reruns). Preserve every existing interaction assertion. Run relevant document component regressions only if handler/markup behavior changes beyond style.
- [ ] Run sequentially format → format:check → typecheck → git diff --check. Record commands/exits; no broad unrelated suite/build. If test changes after GREEN, run affected cases again.
- [ ] Update coverage residual to current dimensions and describe actual padding/content fit. Keep menu origin/status/copy/whole-frame/native differences open. Self-review, commit exact3files, report source map, RED/GREEN and captures. No child agents; controller owns review.
