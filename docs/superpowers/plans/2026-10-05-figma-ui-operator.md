# Figma Operator — Implementation Plan

> For agentic workers: use executing-plans or subagent-driven-development task by task.

**Goal:** Implement Operations, trace lookup/detail and evaluation lookup/unavailable.

**Architecture:** Restyle existing read-only observation components using F2 primitives and existing
operator projections. Preserve M4 tool observations and all server-side authorization.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS v4, Vitest, Playwright.

**Spec:** [Integration design](../specs/2026-10-05-figma-ui-integration-design.md).

**Directory structure:** Read the current/target tree, module responsibilities and dependency rules
in [the workflow's directory analysis](2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).
The task's file list and this structure must remain consistent throughout execution.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Every maintained frontend change requires format, then format:check.
- Authorize before operator identifier lookup. Missing observations are never zero or success.
- Use F2 semantic Tailwind utilities; retain specialized CSS only where needed and check legacy
  unlayered selectors do not override the utilities.

## Task O1: Operator observation surfaces

**Skills:** executing-plans or subagent-driven-development, test-driven-development,
verification-before-completion. Use dispatching-parallel-agents only if executing independently
of U2/U3 after F2 and U1 with disjoint file ownership and a separate worktree.

**Dependency:** F1/F2 stable and U1 WorkspaceSelector interface reviewed; consume shared
ProductHeader and WorkspaceSelector without editing them.

**Modify:**

- frontend/components/operator/OperationsView.tsx, TraceView.tsx, EvaluationView.tsx,
  ToolObservationView.tsx
- frontend/app/operator/operator.css
- frontend/app/operator/page.tsx
- frontend/app/operator/operations/page.tsx, content.tsx
- frontend/app/operator/traces/page.tsx, traces/[traceId]/page.tsx
- frontend/app/operator/evaluations/page.tsx, evaluations/[reportId]/page.tsx
- frontend/lib/operator/presentation.ts

**Tests:** existing operator view/design/state/BFF tests under frontend/tests;
new frontend/tests/operator/operator-figma.test.tsx;
frontend/tests/e2e/m5-operator-flows.spec.ts.
The existing BFF handlers are regression targets; change them only if the approved contract requires it.

**Consumes:** OperatorOperationsResponse, OperatorTraceResponse, OperatorEvaluationResponse,
existing M4 projections and safe presentation helpers.
**Produces:** the same component exports and routes with the Figma layout; no new operator authority.

- [ ] Add failing assertions for O1 metrics, O2 provenance/citation mapping and O3 unavailable;
  include missing metric versus zero, empty candidate list, refused/failed trace, denied workspace
  and missing identifier. Verify lookup forms encode user-entered identifiers safely.
- [ ] Preserve the existing presentation contract:

~~~ts
expect(presentMetric(0)).toEqual({ value: "0", state: "available" });
expect(presentMetric(undefined)).toEqual({
  value: "Unavailable",
  state: "unavailable",
});
~~~

- [ ] Implement the 1200px content layout, workspace selector, tabs, metric sections, trace summary,
  observed result, candidate provenance, context, citation mapping and timing.
  Bind all values to response data; retain schema/config IDs and source version metadata.
- [ ] Implement lookup forms and disabled/loading/failure states. Evaluation lookup renders the
  actual unavailable response and reason, with no fabricated score or download.
- [ ] Keep tool lifecycle observations reachable; adapt their typography/status styling to the
  shared system without dropping approval/reconciliation facts.
- [ ] Run scoped tests:

~~~powershell
npm --prefix frontend run test -- operator
npm --prefix frontend run typecheck
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run test:e2e -- m5-operator-flows.spec.ts
~~~

- [ ] Compare nodes 194:194, 198:200, 206:206 and all five Operator prototype frames.
- [ ] Review/commit as feat: align Operator observations with Figma.

**Acceptance:** three final variants plus both lookup intermediates work with real authorized data;
cross-workspace/unauthorized access is rejected before lookup; unavailable stays visibly unavailable.
