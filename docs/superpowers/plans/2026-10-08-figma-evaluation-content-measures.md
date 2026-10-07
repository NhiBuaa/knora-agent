# Figma Evaluation content measures — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Match the measured Evaluation context hierarchy and explanation allocation.
**Architecture:** Adjust local EvaluationView text regions and natural minimum heights. Source
relative measures determine presentation; backend projections remain unchanged.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, Workspace identity, observations and availability. No invented metrics.
- Preserve all current actions, navigation, true outcomes, full opaque IDs and missing-data semantics.
- Full MCP structures supply source geometry; screenshots verify actual composition only.
- Reuse exact local assets at intrinsic sizes; no SVG edits or temporary Figma URLs.
- Semantic tokens, contrast, focus, responsive readable text and keyboard use remain required.
- No shared primitives/styles, generated API, backend/schema/client/dependency or production fixture edits.
- Run frontend format then format:check. No services/workers/realm/password/Vault/deletion/outage
  actions, installs, merge, push or branch/worktree removal.
- Native/full-regression and remaining source deviations remain separate unresolved requirements.

## Exact directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/operator/EvaluationView.tsx` | Local context heading, row and explanation measures |
| `frontend/tests/operator/operator-figma.test.tsx` | Actual available/unavailable/error observation preservation |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Measured Evaluation RED/GREEN and mobile text fit |
| `docs/development/figma-ui-visual-coverage.md` | Addressed relative geometry and residuals |

Source: complete cached216:755 and current geometry under
`.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/`. No redundant source retrieval.
No OperatorFrame/selector/Trace/sharedBadge edits; existing assets and dimensions remain invariants.

## Task 1: Match Evaluation relative content measures

**Dependency:** Trace internal measures independently reviewed; record clean original BASE.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read source216:794–811 and current owning view and measurements before editing. Source
  context heading216:797 is22px/24px region; current32px. First context row40px versus current41.
  Explanation216:796 is680×70 with16px/20px text; current680×60. Main title and unavailable badge
  already have named source font/shape; retain their established presentation.
- [ ] Add actual-browser RED for named content region/minimum measures and relative offsets,
  with full projection copy, four context meanings and no horizontal overflow. Actual component
  checks preserve available, contract-unavailable, observation-failure and absent-value semantics.
- [ ] Set local Report context title22px/24px; adjust first-row gap against source relative44px
  start below title. Row baseline minimum40px includes divider; use text regions/padding derived
  from source24px region and divider29px after its start, then10px until next row. Longer IDs or
  wrapped mobile rows grow naturally. Do not force fixed heights or reproduce source value300px
  overflow beyond its380px context column.
- [ ] Preserve field split170/remaining/gap10 and full IDs/codes. Source display name is illustrative;
  do not replace authoritative Workspace ID or add a client/backend dependency for it.
- [ ] Give explanation a70px minimum allocation at desktop with existing680px max measure and
 16px/20px type. Preserve complete contract copy and naturally taller mobile/long text. Derive
  relative gap from source heading top300/text region32 and explanation top344; account for
  badge28px flex alignment without clipping. Do not infer global page coordinates from this task.
- [ ] Run relevant component tests and focused Evaluation unavailable case1440/390 GREEN. Then
  run five existing Operator/guidance cases once for measurement-helper regression. Keep all
  previous caret/lookup/badge/Trace geometry, no writes/unexpected requests and readable mobile.
- [ ] Refresh only Evaluation captures/JSON and combined Operator comparison HTML. Preserve all
  four other Operator outputs and original51/unrelated hashes; exclude only root-owned active
  regression-preflight logs. If shared test helper recaptures unchanged cases, retain their prior
  artifacts byte-for-byte after confirming dimensions/content unchanged, recording that action.
- [ ] Record remaining absolute origins, title/badge position, opaque-code wrapping and semantic
  contrast honestly. No accepted parity flag or broad tolerance; unknown/mobile references remain
  adaptation evidence. Run format→format:check→typecheck, report concise RED/GREEN/commands and
  residual JSON links, self-review and commit four paths. Release3300 and independent review.

**Finish condition:** Named relative measures verified with complete authoritative data and mobile
growth; no Important finding. Whole-page/native/full-goal acceptance remains open.
