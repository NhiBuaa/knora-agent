# Figma Operator geometry corrections — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Correct the measured shared-selector, lookup, runtime and detail geometry deviations.
**Architecture:** Extend the existing selector with an optional Operator presentation variant,
then correct owning Operator components' geometry using current semantic tokens. Backend state,
metrics, candidate provenance, routing and all existing feature actions retain their owners.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, Workspace archive/revision, outcomes, metrics and observations.
- Preserve all current actions, safe navigation, historical provenance and missing-data semantics.
- Never substitute illustrative Figma values for runtime data or invent report quality scores.
- Full MCP structures supply source geometry; PNG comparison verifies actual composition.
- Reuse existing local assets at their intrinsic dimensions; only download the exact missing
  bab86.svg through the mechanism permitted by Figma MCP response guidance. No SVG editing.
- Use semantic tokens and preserve accessibility contrast, focus, responsive text fit and keyboard use.
- No generated API edits, backend/schema/client/dependency additions or production fixture routes.
- Run frontend format then format:check; no services/workers/realm/password/Vault/deletion/outage
  actions, installs, merge, push or branch/worktree removal.
- Native/full-regression and remaining source deviations are separate unresolved requirements.

## Exact directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/workspaces/WorkspaceSelector.tsx` | Optional Operator presentation variant, default behavior preserved |
| `frontend/components/operator/OperatorFrame.tsx` | Consume variant and source lookup input/button sizes |
| `frontend/components/operator/OperationsView.tsx` | Runtime signal band source108px inclusive borders |
| `frontend/components/operator/TraceView.tsx` | Detail column and answer measure geometry |
| `frontend/components/operator/EvaluationView.tsx` | Local unavailable badge source rectangle geometry |
| Create `frontend/public/icons/figma/bab86.svg` | Exact trace/evaluation caret asset supplied by MCP, intrinsic geometry preserved |
| `frontend/tests/operator/operator-figma.test.tsx` | Presentation variant/lookup/detail behavior regressions |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Focused actual-component desktop geometry RED/GREEN/mobile preservation |
| `docs/development/figma-ui-visual-coverage.md` | Correct addressed geometry statuses, preserve remaining gaps |

Source cache `.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/` has five full MCP
contexts and comparison measurements. Local `frontend/public/icons/figma/a4e11.svg` exists.
No shared Menu/StatusBadge primitive or stylesheet change. Amend scope before touching extra files.

## Task 1: Correct measured geometry in existing modules

**Dependency:** Three Operator prototype comparisons independently reviewed. Record exact BASE.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read all five full MCP structures and measured comparison JSONs; inspect current selector,
  OperatorFrame/Lookup, runtime band, TraceView and EvaluationView before edits.
- [ ] Add browser RED assertions for source selector26px height, closed caret asset a4e11 and
  its actual intrinsic root geometry in source10×6wrapper; trace lookup field34px, evaluation
  lookup field36px and buttons36px,
  trace button104wide/report124wide; runtime band108px including borders; trace left780/right380
  gap40 and answer measure630px; unavailable badge92×28 with8px radius. Trace/evaluation caret
  uses exactbab86 in10×5slot with source negative inset (effective11.4×6.4). Assert existing source
  state copy/provenance and no overflow alongside geometry. Record actual failed measurements.
- [ ] Add actual component checks that the optional selector variant is consumed only by Operator
  and default consumers retain their established selector markup/asset/action behavior. Existing
  menu actions remain accessible; constrain only Operator heading/menu trigger box to26px without
  hiding or deleting it. Example interface:

```tsx
type WorkspaceSelectorProps = {
  workspaceId: string | null;
  workspaceName: string | null;
  disabled?: boolean;
  presentation?: "default" | "operator";
};
```

- [ ] Default presentation stays unchanged. Operations closed caret uses existing exact a4e11 asset
  in10×6source wrapper; trace/evaluation use exactbab86 supplied by MCP in their10×5source slot,
  preserving source negative inset and intrinsic SVGroot size. Parameterize only presentation
  choices; never infer authorization from route/variant. No SVGroot width/height override;
  open-state current behavior remains usable.
  Keep name truncation/mobile fit and archive/restore/create/selection routing authority intact.
- [ ] Set trace lookup input34px and evaluation lookup input36px, with specific button
  width/min-height36px in OperatorLookup, overriding
  inherited primitive40px locally. Long pending text may grow; do not clip it to force source size.
- [ ] Correct runtime band total108px including its top/bottom borders; preserve natural growth
  for wrapped unavailable/long content and responsive two-column layout. At390px ensure the
  known label/value Unavailable remains whole and readable by adjusting local responsive sizing,
  padding or columns; never convert the actual missing observation into a zero or abbreviated value.
- [ ] Match TraceView desktop left780/right380 gap40 and max630 answer measure. Preserve all real
  answer/provenance/candidate text, extra metadata disclosures, timing/validation availability and
  no fixed candidate height that truncates dynamic excerpts. Recorded source102px candidate versus
  actual dynamic131.375px is not permission to clip or delete provenance.
- [ ] Prevent SELECTED badge word-breaking on narrow candidate rows: permit the surrounding
  row to wrap while preserving the complete badge label and full source name/provenance. Assert
  actual390px text geometry and no overflow; keep validation/timing reachable through natural scroll.
- [ ] Set only EvaluationView's unavailable badge to source92×28 rectangular8px style, preserving
  semantic role/text/tone and genuine other observation states. Keep opaque IDs fully readable,
  allowing wrapping instead of replacing them with illustrative names/codes.
- [ ] Run focused component tests GREEN and affected actual fixture geometry GREEN at1440/390.
  Preserve scoped navigation/API request interception/no writes. Re-run only five affected Operator
  prototype cases, not original51-state suite; save new affected captures/JSON/comparison HTML.
- [ ] Record remaining page coordinates, added controls, dynamic text/provenance and token-contrast
  differences honestly. Source dimensions must be exact where specified; natural growth exceptions
  must have explicit content-fit evidence, not a broad tolerance threshold.
- [ ] Run format→format:check→typecheck, covering Operator/selector tests and focused browser cases;
  self-review/report exact RED/GREEN, commands, asset callsite+slot+rendered sizes, remaining gaps.
  Commit exact owned files, release preview3300, independent originalBASE→HEAD spec/quality review.

**Finish condition:** Named measured dimensions/assets corrected with preserved actions/state and
mobile readability, no Important finding. Remaining full-page typography/coordinates or dynamic
content differences require their own evidence; this task does not declare full Figma/native acceptance.
