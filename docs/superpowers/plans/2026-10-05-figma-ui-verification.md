# Figma UI verification — Implementation Plan

> For agentic workers: use executing-plans to coordinate verification; use systematic-debugging
> for failures, requesting-code-review for independent review, and verification-before-completion.

**Goal:** Prove design coverage, real journeys, accessibility and preserved domain behavior.

**Architecture:** Deterministic fixture screenshots verify visual states; isolated live-stack E2E
verifies integrations. Record which evidence is fixture-based and which used real services.

**Tech Stack:** Playwright, Vitest, pytest, Ruff, Docker Compose, Maven.

**Spec:** [Integration design](../specs/2026-10-05-figma-ui-integration-design.md).

**Directory structure:** Read the current/target tree, module responsibilities and dependency rules
in [the workflow's directory analysis](2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).
The task's file list and this structure must remain consistent throughout execution.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Every maintained frontend change requires format, then format:check.
- Previous milestone acceptance is not evidence that new implementation tests passed.
- No production data, SMTP credentials or real accounts in screenshot fixtures.
- Verify Tailwind utility extraction in the production build, semantic-token dark mode and
  Preflight/cascade compatibility across migrated and remaining legacy surfaces.

## Task 1: Q1 — Visual, responsive and interaction coverage

**Skills:** verification-before-completion, systematic-debugging when a defect is observed,
test-driven-development for a behavior regression fix.

**Dependency:** all implementation slices integrated in the verification worktree.

**Create:** frontend/tests/e2e/figma-ui-visual.spec.ts;
frontend/tests/e2e/figma-ui-interactions.spec.ts;
frontend/tests/e2e/support/figma-state-fixtures.ts;
docs/development/figma-ui-visual-coverage.md.

**Modify:** frontend/playwright.config.ts only for an explicit deterministic visual project;
existing live E2E tests when accessible names intentionally change.

**Produces:** one coverage row for each of the 41 screen IDs, five panel states and five response
cards, plus each of the 89 prototype transitions classified as real action, state display or
prototype-only simulation. Each row records owning task, test, screenshot and accepted deviation.

- [ ] Seed deterministic test-only names/timestamps/data matching reference examples. Freeze the
  browser clock for fixture views, load local fonts and wait for them before screenshots.
  Never introduce fixture routes or bypass permissions in production.
- [ ] Capture the product viewport at 1440×960, excluding the Figma annotation strip. Disable
  animation for screenshot stability; separately verify reduced-motion behavior.
- [ ] For each final screen compare geometry, spacing, text hierarchy, borders, color, assets and
  selected/disabled/error state against its Figma reference. Record actual deviations instead of
  accepting a new screenshot baseline as proof that it matches Figma.
- [ ] Use scoped screenshot assertions, for example:

~~~ts
await page.setViewportSize({ width: 1440, height: 960 });
await page.evaluate(() => document.fonts.ready);
await expect(page).toHaveScreenshot("A4-grounded-answer.png", {
  animations: "disabled",
});
~~~

- [ ] Check 1024×768, 768×1024, 390×844: rail drawer, evidence sheet, anchored composer, modal fit,
  wrapping tables, no clipped critical actions and no page-level horizontal overflow.
- [ ] Exercise keyboard focus/return, Escape, menu arrows, tab order, divider arrows/reset,
  OTP paste and labels, errors/live regions, 200% zoom, contrast and existing dark mode.
- [ ] Exercise real document upload/poll/archive/restore/deletion-blocked, workspace lifecycle,
  conversation answer/refusal/interruption/recovery and operator lookups.
  Requested deletion screenshot is explicitly a fixture because the live policy is unavailable.
- [ ] Run the new Playwright suites, fix concrete discrepancies and record screenshot/trace paths.
  Review/commit as test: cover Figma visual and interaction states.

## Task 2: Q2 — Regression, independent review and completion record

**Skills:** requesting-code-review, receiving-code-review, systematic-debugging,
verification-before-completion, finishing-a-development-branch.

**Dependency:** Q1 coverage has no unexplained gap. OTP multi-node tests must pass for identity release.

**Create:** docs/development/figma-ui-implementation-record.md.
**Modify:** docs/development/keycloak-theme.md and relevant development/acceptance docs to reflect
what actually shipped. Update CONTEXT.md/ADRs only for approved changed domain decisions.

- [ ] Run the complete integration commands from repository root, recording exit codes:

~~~powershell
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
./.venv/Scripts/python scripts/export_openapi.py --check
./.venv/Scripts/python -m pytest
./.venv/Scripts/ruff check .
docker compose config --quiet
mvn -f infra/keycloak/providers/email-otp-reset/pom.xml clean verify
npm --prefix frontend run test:e2e
git diff --check
~~~

Use the repository's isolated E2E stack/setup and current environment guardrails. A missing service,
database or browser is a verification limitation, never a passing test. Do not point tests at live
accounts or bypass the local endpoint guardrails. Capture build/provider version and dependency SHAs.

- [ ] Confirm cross-workspace isolation, owner preference, auth-before-lookup, expired sessions,
  idempotent retries, stale revisions, source/derivation identity, historical citation provenance,
  controlled refusal versus error and all existing M4 observations.
- [ ] Give an independent reviewer the design, task plans, exact base/head diff package, evidence,
  node coverage and declared limitations. Require separate spec-compliance and quality verdicts.
- [ ] Evaluate findings, reproduce factual claims, fix in owning worktrees and rerun affected checks.
  Do not broaden test runs without a concrete remaining risk; rerun final gates if their code changed.
- [ ] Record final commits, review verdicts, commands/results, visual deviations and live limitations.
  “All UI states covered” must not be worded as “deletion processing implemented”.
- [ ] Present completed scope and the user's integration choices: merge locally, push/create PR,
  or keep branch. Main requires the Frontend formatting / Prettier format check CI status.
  Do not merge, publish, delete branches or remove worktrees automatically.

**Finish condition:** fresh evidence supports the claimed scope; no unresolved important review
finding; every design state has an implementation/evidence mapping; remaining product limitations
are explicit and consistent with actual backend behavior.
