# Figma Document detail action height — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development.

**Goal:** Correct the existing Request deletion action to the source40px height while retaining
the42px Reprocess/Archive/Restore actions and native dialog behavior.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).
**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS v4, Playwright.

## Source and diagnosis

Complete direct MCP128:122 and128:125 structures plus returned screenshots were read/viewed on
October8 and saved in `.superpowers/sdd/2026-10-08-figma-document-detail-source/source/`.
Source Ready94:254 and Archived101:174 allocate298×40 for Request deletion; normal actions
allocate298×42. Existing DocumentDetail actionClass includes h-[42px]/min-h-[42px] and the
deletion callsite additionally includes h-10/min-h-10. Conflicting Tailwind size declarations
leave the historical rendered deletion action42px tall. Confirm with computed geometry before
fixing. This is a bounded source correction within already approved Documents implementation.

## Global constraints and directory ownership

Only these maintained files belong to this task:

| File | Responsibility |
| --- | --- |
| `frontend/components/documents/DocumentDetail.tsx` | Unambiguous local action height declarations |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Actual desktop/mobile action geometry and dialog checks |
| `docs/development/figma-ui-visual-coverage.md` | Measured source correction and remaining differences |

No shared Button, tokens, CSS, API, fixture/helper, backend or asset changes. Preserve permissions,
busy handling, callbacks, text, provenance and status authority. No reprocess/archive/restore or
deletion confirmation invocation. No live services, auth, integration or cleanup actions.
All existing Q1 files must retain exact hashes; add only `document-detail-action-height-2026-10-08`.
Other source/semantic/color differences remain documented rather than concealed by clipping.

## Task 1: Correct and verify Document detail action allocation

**Dependency:** Documents local interactions independently approved; record fresh clean BASE.
**Skills:** figma-design-to-code, systematic-debugging, test-driven-development,
verification-before-completion, requesting-code-review.

- [ ] Read source128:122/125, DocumentDetail, Button, existing fixture helper and coverage.
  Inventory every existing Q1 hash, excluding regression-preflight. Preserve native HTML/cache.
- [ ] Add one browser case per viewport1440×960/390×844, each preparing Ready then Archived.
  Locate actual Request deletion button and assert computed height40 and min-height40:

  ```ts
  const deletion = page.getByRole("button", { name: "Request deletion", exact: true });
  expect((await deletion.boundingBox())!.height).toBeCloseTo(40, 1);
  expect(await deletion.evaluate((el) => getComputedStyle(el).minHeight)).toBe("40px");
  ```

  Desktop action width298; mobile width fits viewport. Reprocess/Archive in Ready and Restore
  in Archived remain42. Check loaded leaf18×18 and Ready-only status dot7×7 with exact existing
  callsites/non-empty files. Assert unchanged native fields/API GET guards. Run scoped two cases
  before implementation and retain expected height42→40 failure, not an incidental failure.
- [ ] Remove conflicting dimensions from common actionClass, keeping remaining shared classes.
  Add explicit `h-[42px] min-h-[42px]` at Reprocess and Archive/Restore callsites; deletion gets
  only `h-10 min-h-10`. Do not change handler/capability logic or rearrange content.
- [ ] Run scoped browser cases GREEN. Open deletion dialog using existing action, assert name,
  Cancel and confirm control, cancel and reopen/Escape with actual focus return. Never confirm.
  Assert no unexpected API requests or mutations. Capture Ready/Archived full compositions and
  dialog only in task directory after fonts/assets load; view captures, record overflow/fit and
  measured42/40 heights. Natural source/provenance row growth remains an explicit difference.
- [ ] Run relevant existing document component tests once. Run format then format:check then
  typecheck sequentially. After formatting rerun covering browser cases only if source changed.
  Record complete outputs. Inventory after and prove every preexisting artifact unchanged.
- [ ] Update coverage precisely, self-review, commit exact3paths, release3300, save report.
  Controller reviews original recordedBASE→finalHEAD with both Spec and Quality verdicts.

**Finish condition:** Correct local action height independently approved with source geometry and
preserved dialog/focus evidence. Live lifecycle and whole-design acceptance remain open.
