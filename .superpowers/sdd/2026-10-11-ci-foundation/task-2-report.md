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
- `npm test` — passed: 49 files, 446 tests.
- focused exporter/selection Vitest — passed: 2 files, 6 tests.
- `FIGMA_TEST_MODE=fixture npx playwright test --config playwright.figma.config.ts --list` — 136 collected tests; no guarded application journeys listed.
- `FIGMA_TEST_MODE=application ... --list` — 26 application tests across 3 files; no fixture-only titles listed.
- `npm run lint` — passed with three pre-existing `no-img-element` warnings.
- `npm run build` — passed with the same warnings.
- Java 21 renderer — passed in `maven:3.9.9-eclipse-temurin-21` with the three pinned artifacts; all nine native HTML fixtures rendered. The worktree host lacks Java 21, so the host-side exporter was not run; Chromium itself was installed for the fixture attempt.

The Chromium fixture run was attempted after installing Chromium: 136 collected, 128 passed, 8 failed, 0 skipped. Three failures are fresh-checkout absence of the existing untracked operator source-index evidence; five are existing fixture contract failures (two operator geometry expectations, two archived Workspace route expectations, and one read-only suggestion submission). No assertions or visual baselines were changed; these remain open for the owning fixture/product slices and are not claimed as a passing CI gate.

No visual baselines were changed.
