# Figma Operator tab journeys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Exercise the eight remaining Operator tab transitions against the owned live harness.

**Architecture:** Extend the existing authorized Operator journey with actual tab clicks and destination assertions. Keep application code and backend observations unchanged; record only the transitions actually proved.

**Tech Stack:** Next.js, TypeScript, Playwright, existing Tailwind CSS v4 frontend and isolated Figma services.

**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md), Operator prototype edges in [coverage](../../development/figma-ui-visual-coverage.md).

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Every maintained frontend change requires format, then format:check.
- No production data, SMTP credentials or real accounts in screenshot fixtures.
- Use the existing guarded Figma harness only; no realm import, password changes, OTP binding or physical outage attempts.
- Preserve prior evidence. New captures go to `.verification/figma/q1/evidence/operator-tab-journeys-2026-10-08/`.
- This bounded verification does not accept whole-design parity or native identity gates.

## File structure

The existing `frontend/tests/e2e/figma-operator.spec.ts` owns live Operator setup and navigation. Extend it without creating a parallel harness or changing production components. The coverage ledger owns per-edge claims; the implementation record owns commands and limitations. Generated captures and the task report remain ignored.

## Task 1: Verify missing Operator tab directions

**Modify exactly:**
- `frontend/tests/e2e/figma-operator.spec.ts`
- `docs/development/figma-ui-visual-coverage.md`
- `docs/development/figma-ui-implementation-record.md`

**Consumes:** existing local `login(page, username)`, `workspace(page, name)`, `select(page, id)`, `captureIdentity(page, path)` and the authorized five-state journey's real `QuestionResponse.trace_id`.
**Produces:** live navigation evidence for edges54,55,56,58,60,61,63,64, without replacing backend response data.

- [ ] Read repository guidance and the existing Operator journey/components to confirm current accessible names and URL forms. Do not fetch new Figma context for this test-only extension: retained direct-MCP contexts and the exact transition ledger are the authority.
- [ ] Extend the existing first journey, reusing its authenticated Workspace and trace. Move all its captures into the new evidence directory so reruns preserve the historical folder. Leave the second authorization-denial test's scope intact.
- [ ] Exercise each transition from its named source state. Assert source UI before clicking; use a real link click; assert destination pathname, meaningful heading/lookup state, and the selected Workspace after navigation. Lookup destinations must have empty fields and disabled submit buttons. Detail sources must display the actual trace; unavailable-report sources must display the requested report's unavailable state.

| Edge | Source | Actual link | Destination |
| --- | --- | --- | --- |
| 54 | Operations | Evaluations | Empty evaluation lookup |
| 55 | Empty trace lookup | Operations | Operations |
| 56 | Empty trace lookup | Evaluations | Empty evaluation lookup |
| 58 | Actual trace detail | Operations | Operations |
| 60 | Empty evaluation lookup | Operations | Operations |
| 61 | Empty evaluation lookup | Traces | Empty trace lookup |
| 63 | Evaluation unavailable | Operations | Operations |
| 64 | Evaluation unavailable | Traces | Empty trace lookup |

Use focused local helpers only where repeated setup/assertions warrant them. A navigation assertion should follow this form (derive exact route query conventions from the existing route implementation):

```ts
await page.getByRole("link", { name: "Operations", exact: true }).click();
await expect(page).toHaveURL(/\/operator\/operations(?:\?.*)?$/);
await expect(page.getByRole("heading", { name: "Operations", exact: true })).toBeVisible();
await expect(page.getByRole("button", { name: `Switch workspace: ${observed.name}` })).toBeVisible();
```

- [ ] Save one destination capture per new edge, named `edge-54.png` etc., under the new evidence directory. Screenshots supplement assertions; they do not prove a transition by themselves. Inspect representative source/destination captures.
- [ ] Run from `frontend`: `npm exec playwright test -- --config=playwright.figma-operator.config.ts`. Existing config supplies the guarded application harness; set `FIGMA_TEST_MODE=application` if required by its validation. Run both tests once to cover navigation and existing authorization denials. If existing assertions fail, diagnose against current source and report any production defect before broadening the three-file scope. Do not weaken authorization or observation assertions.
- [ ] Update exactly the eight new edge claims and any existing Operator evidence paths moved by this test. State test evidence and remaining visual/native limitations honestly.
- [ ] Run from root, sequentially: `npm --prefix frontend run format`, `npm --prefix frontend run format:check`, `npm --prefix frontend run typecheck`, then `git diff --check`. If formatting changes semantics or tests were edited after the live run, rerun affected live cases. A full unrelated suite/build is unnecessary for this test-only change.
- [ ] Self-review and commit exactly the three maintained files. Write the task report with commands, exit codes, capture paths, changes and concerns. Leave root `node_modules/` untouched; deletion was rejected earlier. No child agents; independent review belongs to the controller.
