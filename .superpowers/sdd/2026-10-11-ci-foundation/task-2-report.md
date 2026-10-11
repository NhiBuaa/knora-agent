# CI Foundation Task 2 report

- Worktree: `C:\Developer\Projects\knora-agent-worktree\ci-fixtures`
- Branch: `codex/ci-fixtures`
- Scope: explicit fixture/application Playwright collection and offline native fixture export.

## Changes

- Fixture mode now excludes the `guarded application journeys` describe before Playwright collection, so fixture JUnit has no application skips.
- Application mode excludes fixture-only describes and the fixture-only PDF classification test.
- Invalid mode/case selection remains fail-closed; focused Vitest coverage checks both selection boundaries.
- Native export no longer invokes Docker, reads live Keycloak CSS, or uses a named Maven volume. It resolves pinned FreeMarker 2.3.32, Keycloak themes 26.3.3, and Keycloak themes vendor 26.3.3 from explicit paths, a repository artifact directory, or local Maven/provider-POM classpaths. The Java renderer verifies the existing PatternFly hashes and the pinned password visibility resource before rendering.

## Verification

- `npm ci` — passed (fresh install; npm reported existing dependency audit warnings).
- `npm run format` — passed.
- `npm run format:check` — passed.
- `npm run typecheck` — passed.
- `npm test` — passed: 49 files, 447 tests.
- focused exporter/selection Vitest — passed: 2 files, 6 tests.
- `FIGMA_TEST_MODE=fixture npx playwright test --config playwright.figma.config.ts --list` — 133 collected tests; guarded application journeys and the three controller-owned Operator prototype comparisons are excluded before collection.
- `FIGMA_TEST_MODE=application ... --list` — 26 application tests across 3 files; no fixture-only titles listed.
- `npm run lint` — passed with three pre-existing `no-img-element` warnings.
- `npm run build` — passed with the same warnings.
- Java 21 renderer — passed in `maven:3.9.9-eclipse-temurin-21` with the three pinned artifacts; all nine native HTML fixtures rendered. The worktree host lacks Java 21, so the host-side exporter was not run; Chromium itself was installed for the fixture attempt.

The first Chromium run exposed stale fixture contracts. The follow-up repaired the approved Operator 26px selector allocation, canonical Workspace conversations route, and the post-`915197b` suggestion Turn submission contract. The three controller-owned Operator prototype comparisons are deselected for PR scope because their source-index evidence is untracked and unavailable in a fresh checkout; they remain manual visual acceptance. Final Chromium fixture run: 133 passed, 0 failed, 0 errors, 0 skipped. JUnit reports `tests=133 failures=0 errors=0 skipped=0`.

No visual baselines were changed.
