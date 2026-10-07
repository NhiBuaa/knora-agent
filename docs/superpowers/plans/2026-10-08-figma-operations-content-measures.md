# Figma Operations content measures — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Match Operations accounting, latency bucket and Alerts relative content measures.
**Architecture:** Adjust local OperationsView allocations and text slots using complete MCP source
216:345. Preserve backend projections and natural content growth; screenshots verify composition.
**Tech Stack:** Next.js 15.5.24, React 18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, configuration, observations and availability. Zero remains valid.
- Preserve complete metric values, supplied bucket bounds and sample counts; no illustrative data substitution.
- Full MCP structures supply source geometry; screenshots verify actual composition only.
- Preserve current selector, exact assets, lookup, Trace and Evaluation presentation and behavior.
- Semantic tokens, contrast, focus and responsive readable text remain required.
- No shared primitives/styles, generated API, backend/schema/client/dependency or production fixture edits.
- Run frontend format then format:check. No service/worker/realm/password/Vault/deletion/outage actions,
  installs, merge, push or branch/worktree removal.
- Native/full-regression and remaining source deviations remain separate unresolved requirements.

## Exact directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/operator/OperationsView.tsx` | Local accounting, bucket and Alerts minimum allocations and text slots |
| `frontend/tests/operator/operator-figma.test.tsx` | Actual zero/missing and histogram projection preservation |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Actual Operations browser geometry, mobile fit and capture |
| `docs/development/figma-ui-visual-coverage.md` | Corrected measures and remaining deviations |

Source: `.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/216-345.md` and matching
current desktop/mobile JSON. Do not retrieve unchanged source again. This task follows Evaluation
review because tests and coverage are shared files; do not dispatch implementations concurrently.

## Task 1: Match Operations internal allocations and text slots

**Dependency:** Evaluation content measures independently reviewed; record clean original BASE.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read full source 216:401–447 and existing browser measurement helper. Source accounting
  container is 1200×148, with six 580×49 rows at y0/49/98, columns x0/600. Children occupy147px;
  the container explicitly allocates one further pixel. Buckets container is760×92, with four
  370×40 rows at y0/46 and columns x0/390; children occupy86px, leaving6px bottom allocation.
  Do not stretch rows to divide the containers or add an extra divider.
- [ ] Add actual-browser RED for desktop minimum allocations and internal row/text positioning,
  while preserving source row dimensions, six accounting meanings and all supplied bucket values.
  Capture bounding boxes and computed text regions rather than asserting class strings alone.
  Component coverage must retain zero versus missing values, missing histogram, malformed bucket
  omissions and all valid supplied rows. Reuse existing tests where they already cover the risk.
- [ ] Accounting retains 49px row minimum including bottom divider,20px column gap and20px right
  container inset, with desktop minimum148px. Text has14px type and20px line region, starts14px
  below each row origin; values begin420px from each580px row origin. Use natural padding rather
  than centered alignment (current region begins14.5px). Long content grows naturally; mobile
  remains a single column with readable full values. A desktop-only1px bottom allocation can
  implement the source container difference without changing row sizes.
- [ ] Buckets retain40px row minimum including divider,20px column gap and6px row gap. Give desktop
  container92px minimum using6px bottom allocation. Text is13px/20px, starts10px below row origin;
  values use a60px natural minimum slot starting310px into370px rows, semibold as source. Use
  responsive grid slots with full values and natural growth, not clipping, ellipsis or fixed heights.
  Source decimal spellings are illustrative; do not replace authoritative numeric formatting.
- [ ] Alerts source380×70/radius8, left padding14, top label12 and body35. Use70px minimum,
  label11px/15px semibold and body13px/20px with8px intervening margin, allowing wrapped copy
  to grow on mobile. Preserve role=status and exact unavailable contract statement. Keep existing
  theme-aware semantic color mix; source light #f4eae6 versus current derived background remains
  an explicit token difference for a later shared-token task, not a geometry waiver.
- [ ] Minimal local CSS shape, subject to Prettier and existing responsive variants:

  ```tsx
  // Accounting container: desktop allocation includes one trailing pixel.
  className="... md:pb-px"
  // Accounting row: 14 + 20 + 14 + 1 border = 49 minimum.
  className="grid min-h-[49px] ... items-start pt-3.5 pb-3.5 leading-5 ..."
  // Buckets: source trailing allocation; value slot follows left text region.
  className="... md:pb-1.5"
  className="grid min-h-10 grid-cols-[minmax(0,1fr)_60px] ... pt-2.5 pb-[9px] leading-5"
  // Alerts: label region15px; following body begins35px from top.
  className="... min-h-[70px] ... px-3.5 py-3"
  className="m-0 text-[11px] leading-[15px] font-semibold ..."
  className="mt-2 mb-0 text-[13px] leading-5"
  ```

  Keep existing class names and state properties not contradicted by these local measures;
  class fragments above are implementation guidance, not permission to replace whole elements.
- [ ] Run relevant component tests and focused Operations browser case1440/390 GREEN; then five
  existing Operator/guidance cases once to verify shared measurement helper invariants. Preserve
  Runtime band108px, complete mobile Unavailable, source assets and prior corrected measures.
  API doubles allow only established hydration GET; unexpected requests fail, no API writes.
- [ ] Refresh only Operations PNG/JSON and combined Operator comparison HTML. Hash and retain
  four other Operator outputs and all original51/unrelated source/capture artifacts, excluding
  only root active regression-preflight logs. If helper recaptures unchanged cases, retain their
  prior bytes after confirming unchanged measured dimensions/content and record that action.
- [ ] Append corrected relative measures, full residual JSON links, theme/background and absolute
  origin differences to coverage. No parityAccepted flag or broad tolerance. Mobile has no source
  reference and is adaptation evidence. Run format→format:check→typecheck, self-review and commit
  exactly four owned paths. Write report with commands, RED/GREEN, artifact hashes and limits.
  Release owned3300 process before returning; root performs independent originalBASE→HEAD review.

**Finish condition:** Relative allocations/text slots verified, full observations readable, no
Important review finding. Whole-page, native identity and full-goal acceptance remain open.
