# Figma remaining Operator prototype comparisons — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Compare actual production compositions with the three newly available Operator prototypes.
**Architecture:** Extend the existing isolated fixture union with three explicit prototype states,
rendering the current production views with synthetic typed projections. Capture and classify source
differences individually; confirmed product defects receive separate scoped implementation tasks.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns Workspace authorization, runtime observations, trace/candidate provenance and reports.
- Synthetic fixture projections prove presentation only; never infer real authorization or outcomes.
- Use actual production components, shared semantic tokens, fonts and assets; no screenshot-as-UI.
- Implement exclusively from full MCP structures; PNGs are visual comparison targets.
- No production fixture routes, API/schema/generated-contract/dependency changes.
- Preserve original51-item visualStates inventory and all existing source/capture hashes.
- Frontend maintained changes require format then format:check.
- No live API writes, services/workers/realm/password/Vault/deletion/outage actions or installs.
- No merge, push, branch/worktree deletion or full-goal acceptance from fixture evidence.

## Exact directory ownership

| Maintained path | Responsibility |
| --- | --- |
| `frontend/tests/e2e/support/figma-state-fixtures.ts` | Add216:345/216:573/216:755 to separate fixtureStates union and exact route mapping |
| `frontend/tests/e2e/support/figma-fixture-view.tsx` | Compose current OperationsView/TraceView/EvaluationView with typed synthetic projections |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Three focused source-comparison cases and desktop/mobile fit checks |
| `docs/development/figma-ui-visual-coverage.md` | Per-prototype observed match, deviation and remaining implementation action |

Ignored source/capture root `.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/` contains
full216-345.md/216-573.md/216-755.md, MCP screenshots and source-index hashes. Source frames1440×960,
returned PNGs1024×683, no annotation strip. Preserve source and previous lookup artifacts.
No production component changes in this comparison task; amend a separate implementation plan
for a confirmed defect rather than silently broadening this scope.

## Task 1: Compare Operations, trace detail and evaluation unavailable

**Dependency:** Archived inspector context independently reviewed; record exact starting HEAD.
**Skills:** figma-design-to-code, verification-before-completion, requesting-code-review.
No product behavior change: this task verifies existing compositions, so no artificial product RED.

- [ ] Read full three cached MCP structures and view their PNGs; inspect current production views,
  fixture union and generated projection types. Note source static copy/layout independently of
  illustrative data values. Confirm existing static asset call sites and rendered dimensions.
- [ ] Add three separate fixture states without changing visualStates or original51 source cases.
  Map216:345 to Operations path,216:573 to existing trace-detail path,216:755 to existing report
  observation path. Reuse current production views and narrow request interception.
- [ ] Existing51 fixtures stay unchanged. For new prototypes use explicit generated TypeScript
  projections with synthetic source-like data to exercise zero/nonzero/unavailable signals,
  selected candidate/excerpt/provenance and report-unavailable context. Do not prepopulate live
  routes or claim that a synthetic trace/report ID exists in backend data. No app-side calculation
  of a missing outcome, metric, score or availability.
- [ ] Add three focused browser cases, each1440×960 and390×844. Assert actual production section
  names, complete dynamic values/provenance for the supplied projections, no fabricated evaluation
  scores, zero retained and explicit missing fields. Measure named section widths/gaps/typography
  and source positions against full MCP structures; classify every observed deviation, do not
  make a tolerant assertion and call it exact parity. Narrow viewport asserts readable fit only,
  since no mobile source geometry is supplied.
- [ ] API doubles reject unexpected requests; assert no writes. Do not trigger workers, uploads,
  trace generation, recovery, deletion or services. Source comparison is a fixture-only exercise.
- [ ] Create artifact directory recursively before writes. Capture only the three new prototypes,
  with geometry JSON and whole-frame side-by-side HTML at common display width. Do not crop34px
  or overwrite original51 screenshots/comparisons. Preserve prior lookup evidence.
- [ ] Run only the three added cases; diagnose actual test failures before changing assertions.
  If a real production mismatch prevents a required check, record exact source/current evidence
  and report it for the owning implementation task; never relabel it as passed parity.
- [ ] Update coverage with three individually named comparison rows and unresolved deviations.
  Five sources retrieved is different from five source comparisons accepted. Retain native/reset/
  MFA/Vault/CSP/outage, unexercised edges and Q2 full-regression gaps.
- [ ] Run format→format:check→typecheck, focused browser cases and git diff --check; write exact
  commands/results, projection/authority limits, assets, hashes and mismatch list to this plan's
  report. Commit exact four maintained paths and release preview3300. Independent originalBASE→HEAD
  review requires spec compliance and quality verdicts.

**Finish condition:** Three production compositions have durable named source comparisons with
traceable geometry and complete deviation records; no Important review finding. Real parity defects
remain implementation work and the full Figma goal is not complete until they are resolved.
