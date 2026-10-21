# Figma Operator lookup guidance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Implement the missing guidance sections on the two Operator lookup screens.
**Architecture:** A presentation-only feature component renders the source's trace/report guidance
below the existing lookup form, composed only by the lookup routes. Existing detail views,
navigation, Workspace authority and backend observation contracts remain their current owners.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, Workspace scope, trace, evaluation and missing-data observations.
- Never fabricate report/trace results, scores, candidate provenance or runtime numbers.
- Browser requests continue through the existing BFF and canonical Operator routes.
- Use existing semantic tokens, Inter/Roboto Slab and production feature components.
- Use high-fidelity Figma MCP structures as implementation authority; screenshots compare rendering.
- Never hand-edit frontend/generated/knora-openapi.ts; no API/schema/dependency additions.
- Run frontend format then format:check for maintained frontend changes.
- No service/worker/realm/password/deletion actions, merge, push or branch/worktree removal.
- Native identity/outage/full-regression gates remain separate and unresolved.

## Fresh source and directory ownership

On Oct7 user reconnected Figma. MCP get_design_context returned complete structures and screenshots
for216:345,216:448,216:573,216:698,216:755, none sparse. Local ignored source root:
`.verification/figma/q1/evidence/operator-prototypes-2026-10-07/` (source-index.json, five.md/five.png).
This task implements only216:448 trace lookup and216:698 report lookup, specifically221:212 and
221:227 guidance. Remaining three prototype comparisons are subsequent coverage work.

| Exact path | Responsibility |
| --- | --- |
| Create `frontend/components/operator/OperatorLookupGuidance.tsx` | Static trace/report source guidance, responsive feature presentation |
| Modify `frontend/app/operator/traces/page.tsx` | Compose trace guidance after unchanged lookup form |
| Modify `frontend/app/operator/evaluations/page.tsx` | Compose report guidance after unchanged lookup form |
| Modify `frontend/tests/operator/operator-figma.test.tsx` | Actual async lookup route/component and navigation regressions |
| Modify `frontend/tests/e2e/support/figma-fixture-view.tsx` | Actual production route-equivalent lookup composition for two prototype states |
| Modify `frontend/tests/e2e/support/figma-state-fixtures.ts` | Exact216:448/216:698 fixture route/state mapping |
| Modify `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Two lookup guidance layout/navigation fixture cases, focused captures |
| Modify `docs/development/figma-ui-visual-coverage.md` | Fresh five-source availability and two implemented guidance states, remaining gaps |

No OperatorFrame/detail view/backend change. Diagnose and amend scope before editing additional
files. Guidance has no state, network request, identifiers, runtime data or new action.

## Task 1: Add trace and report lookup guidance

**Dependency:** OTP resend fallback independently reviewed and preview3300 lease released.
**Skills:** figma-design-to-code, test-driven-development, verification-before-completion,
requesting-code-review. Record exact starting HEAD and own SDD workspace.
**Interface:** `OperatorLookupGuidance({kind}: {kind: "trace" | "report"})`.

- [ ] Read full cached216-448.md and216-698.md, the two existing routes, existing lookup tests and
  fixture composition. Check each static source asset already exists at its production call site;
  guidance itself introduces no asset. Do not reconstruct source structure from screenshots.
- [ ] Add actual async route tests that require the correct source heading and all three source
  guidance items, and preserve encoded trace/report + Workspace query redirect behavior.
- [ ] Run focused operator-figma tests RED: the missing source guidance must cause the failure.
- [ ] Implement the bounded feature component and compose it below each route's current form.
  Use these exact source strings:

| kind | Heading and introduction | Three items: label — body |
| --- | --- | --- |
| trace | What this trace shows / Open an exact Trace ID to inspect one question’s recorded retrieval and validation evidence. | DECISION & VALIDATION — Final answer or refusal, plus the validation outcome. / CANDIDATE PROVENANCE — Ranked evidence with source, chunk, score, and selection decision. / CITATIONS & TIMING — Citation mapping and per-phase timing for the request. |
| report | What this report provides / Open an exact Report ID. Knora only shows persisted evaluation data that the backend actually provides. | PERSISTED REPORT — Evaluation data appears only when a persisted report is available. / WORKSPACE SCOPED — Report context stays tied to the workspace it was observed for. / NO INVENTED METRICS — Missing reports remain explicitly unavailable instead of becoming synthetic scores. |

```tsx
<>
  <OperatorLookup kind="trace" workspaceId={workspaceId} />
  <OperatorLookupGuidance kind="trace" />
</>
```

- [ ] Desktop source guidance is1200wide, heading Roboto Slab18/semibold, introduction Inter14,
  three360wide columns with60gaps, top divider per item, label12/semibold/muted, body14/20/muted.
  Follow cached positions within a natural responsive layout; preserve the existing optional
  Workspace override and usable empty-input disabled submit. On narrow viewports stack columns,
  grow for wrapped text and avoid clipping. Do not insert a fake source Trace/Report ID.
- [ ] Run actual route/component GREEN and existing lookup encoding/same-route retry tests.
- [ ] Extend the two exact fixture states using real OperatorFrame/OperatorLookup/Guidance; no
  production fixture route. Keep exported visualStates as the original51-item capture inventory;
  export a separate fixtureStates union with the two named Operator prototypes for host lookup
  and narrow fixture-request recognition. This avoids silently extending the51-state visual loop.
  Requests remain intercepted/guarded, no API writes. At1440 check
  section and columns against cached geometry, then390 no horizontal overflow or clipped copy.
  Enter an exact synthetic lookup ID and verify encoded target navigation/Workspace scope using
  existing intercepted observation fixtures; do not claim backend authorization from fixture.
- [ ] Capture only the two affected prototype states, record geometry deviations explicitly.
  Source frames are1440×960; returned MCP PNGs are1024×683 with no annotation strip. Compare
  whole-frame proportions at a common display size; do not crop34px or replace existing51 captures.
- [ ] Update coverage: five references now retrieved through MCP, two lookup guidance states
  implemented/checked; other new-source and native/full-regression gaps remain open.
- [ ] Run format→format:check→typecheck, focused Operator tests and two fixture cases. Report actual
  RED/GREEN, commands, geometry, artifacts and limitations. Commit exact owned paths and release
  preview3300. Independent originalBASE→HEAD review requires spec and quality verdicts.

**Finish condition:** Both actual lookup routes show source guidance, preserved navigation tests
and focused layout checks pass, and no Important review finding. This does not accept all five
Operator prototypes, all Q1 transitions or full native/Figma completion.
