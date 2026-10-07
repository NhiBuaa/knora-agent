# Task 1 — Q1 visual, responsive and interaction verification

Date: 2026-10-07. Status: **PARTIAL, ready for independent review**. Original review base:
`eed8f9660a626c6dc181aea01fea4ced6e791a1e`. Controller amendments through `e806806`
approved the exact host, renderer, ignore policy and three diagnosed production fixes.
Full Q1 acceptance is not claimed: native recovery gates, source geometry differences and
unexercised transitions remain explicit below and in the coverage ledger.

## Delivered source and evidence

- Test-only Next host imports actual modules, hooks/providers, production CSS and local fonts.
  No fixture route was added to the production app. Fixture requests fail closed for unexpected
  paths/methods/scopes; deterministic API doubles are not backend authorization evidence.
- Actual maintained FTL is exported with FreeMarker 2.3.32 and Keycloak 26.3.3 parent resources.
  Native fixture forms cannot submit. The disposable pinned Java image is offline, the Maven
  cache is read-only, and classes/HTML/assets remain ignored artifacts.
- All 51 cached full MCP structures and original PNGs were used without changing the source
  index/manifest: 41 screens, five panels and five response cards. Each has a ledger row,
  actual capture, source comparison and explicit observed deviation. Each of 89 prototype
  edges has its own action/state/prototype classification, owner, test, screenshot and gap.
- Durable visual coverage: 51 desktop captures at 1440×960, 24 responsive captures across
  1024×768, 768×1024 and 390×844, and five dark captures. Affected captures were replaced
  after fixes. All 51 hashes now match current captures; affected sheets were regenerated.
- Ignored evidence directory: `.superpowers/figma/q1/evidence/`. Important artifacts:
  `source-comparisons.json`, `<id>-comparison.png`, seven `<group>-source-review.png` sheets,
  `live-create-navigation.json`, `live-turn-terminal.json`, `live-pdf-terminal.json`,
  `live-refusal-terminal.json`, and explicit `live-*.png` / `O*-live.png` images.
  Original queued observations are retained as historical snapshots; terminal observations
  supersede completion uncertainty for the exact processed records.

Coverage detail: `docs/development/figma-ui-visual-coverage.md`. Fixture time is fixed to
2026-10-05T12:00Z. Fixture document/workspace names match reference examples. Live observations
use owned synthetic data and actual returned status/citations; no prototype historical metrics,
184ms timing, two-candidate trace, chapter-count heading or deletion outcome is fabricated.

## Diagnosed production fixes and RED/GREEN evidence

1. **OTP cascade:** generic input CSS overrode the enhanced OTP input with 40px height and visible
   text. With complete parent CSS, computed-style RED failed on 40px versus source 56px.
   The approved two selector changes in `knora.css` restore 56px and transparent enhanced text.
   GREEN verifies actual clipboard paste `000042`, cells, error label, focus and no-JS visible
   single input. Missing parent CSS initially caused a separate fixture overflow; it was repaired
   as a fixture dependency issue before diagnosing the real cascade discrepancy.
2. **Create Workspace navigation:** actual create 201 and preference 200 were followed by
   cancelled management/destination requests. The deferred selection regression failed because
   refresh ran before preference validation. Removing only the two stale refresh calls preserves
   local retry/idempotency/backend authority. Unit scheduling and actual create/navigation then
   passed; no direct navigation workaround hides the original failure.
3. **Refusal projection:** actual backend status `refused`, decision `REFUSAL`, reason
   `INSUFFICIENT_EVIDENCE` and no citations were not rendered because TurnCard/EvidenceInspector
   and fixture data used `REFUSE`/lowercase. The actual projection regression failed on missing
   refusal text; the exact literal correction passed unit and actual preserved native UI checks.
   Only A5 and the compact refusal state were recaptured afterward.

## Commands and observed results

Commands run from the repository root; environment assignments apply only to the test process.
The source exporter is `node frontend/tests/e2e/support/figma-theme-export.mjs`.
It produced nine maintained FTL states. Parent resource hashes:

- Runtime Keycloak theme JAR: `e2a8a0f691a4061d7b510e3fbe3546592332213b73d157efdbf1594e0bb8fd59`.
- `patternfly.min.css`: `60d06da3e8d411c4263558546527ddf294b821fbad5dc777f3c338b47d3cb744`.
- `patternfly-addons.css`: `048733a7b0de85495862f45957a223779d7d0c68d7ad6b32b824b815c6790551`.

The two vendor styles are absent from the theme JAR. Guarded read-only static GETs from the
owned Keycloak resolved them; exporter rejects a hash mismatch. This proves source composition,
not native CSP, password/recovery flow or provider execution. Temporary Docker engine downtime
was a harness outage; the controller recovered the existing owned graph without reset/recreation.

| Command / selection | Observed output |
| --- | --- |
| `npm --prefix frontend run test -- tests/e2e/support/figma-source-inventory.test.ts` | Boundary RED: 1 failed/4 passed; implementation GREEN: 5 passed. Unsupported state/scope/credential/method rejected. |
| Fixture full initial visual + interaction run | 82 passed, 6 failed in 2.9m. Six harness/dependency failures diagnosed; targeted five selector cases passed, and complete-parent OTP mobile case passed. No product failure was silently accepted. |
| `$env:FIGMA_TEST_MODE='fixture'; npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts figma-ui-visual.spec.ts --max-failures=1` | 80 passed in 1.2m; later invocation cleared the original output artifact folder. Corrected durable capture paths, then necessary recapture: 80 passed in 1.0m (handle 62748). No further full 80 repeat. |
| Fixture affected OTP/W5 visuals + interactions | 16 passed in 21.5s after OTP fix. Later corrected D1/W1/W2/archive/account compositions + no-JS/accessibility interaction selection: 25 passed in 29.8s. |
| `npm --prefix frontend run test:e2e -- --config=playwright.figma-operator.config.ts` (fixture mode unset) | 2 passed in 31.4s; actual five-state Operator lookup journey, cross-workspace denial and unavailable report. |
| `$env:FIGMA_TEST_MODE='application'; npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts figma-ui-interactions.spec.ts --grep 'owned document'` | Focused final lifecycle GREEN: 1 passed in 25.3s (handle 34200). |
| Same application command, `--grep 'existing owned'`, `FIGMA_CONTROLLER_PROOF=1` | Actual preserved answer and PDF terminal UI: 2 passed in 17.5s (handle 60939). Controller processed exact existing records separately. |
| Same application command, `--grep 'existing owned unsupported'`, `FIGMA_CONTROLLER_PROOF=1` | Actual refusal RED: missing heading despite authoritative refused projection. Final GREEN: 1 passed in 13.4s (handle 14627); terminal JSON and `live-refusal.png` saved. |
| Fixture visual command, `--grep 'source fixture (128:111\|4:190)'` | Final affected refusal captures: 2 passed in 8.6s (handle 73491). |
| `npm --prefix frontend run test -- tests/conversation-view.test.tsx tests/workspace-figma-flows.test.tsx tests/e2e/support/figma-source-inventory.test.ts` | Final 3 files/40 tests passed in 2.55s; original scheduling and refusal RED retained in this report. |
| `npm --prefix frontend run format` then `npm --prefix frontend run format:check` | Exit 0; all matched files use Prettier style. |
| `npm --prefix frontend run typecheck` | Exit 0. Initial fixture DOM shadowing/test option errors fixed in test source before final verification. |
| `npm --prefix frontend run build` | Exit 0 (handle 82660), 18 static pages generated; existing `no-img-element` warnings retained, no bypass. |
| Bundled Pillow comparison refresh | Two refusal pairs/two affected sheets refreshed; all 51 actual SHA256 values match current durable captures. RGB metrics are descriptive, never source acceptance thresholds. |
| `git diff --check` | Exit 0. |

No trace/video/automatic native error snapshot capture was enabled. Explicit native screenshots
use the existing masked capture helper. Safe artifact JSON stores IDs/status, never credentials,
action URLs, authentication codes or tokens. Test runner emitted existing NO_COLOR/FORCE_COLOR
warnings; source renderer emitted a Java unchecked warning. Neither was suppressed to claim parity.

## Actual application observations

- Native guarded login reached the actual resolver and app. Prior I1 registration/validation proof
  remains in `.superpowers/sdd/2026-10-05-figma-ui-identity/task-1-report.md`; no Q1 fresh
  registration or logout proof is claimed.
- Workspace create/select, rename, archive/restore and Conversation archive/restore passed.
  Document upload, detail/status, archive/restore and deletion-dialog cancel passed.
- Lost response was delivered only after the actual submission response was received; history
  recovered one persisted Turn without duplicating submission. The exact earlier owned Turn
  was later answered by the existing controller runner; actual history/citation/provenance UI
  was checked. New lifecycle queued observations remain distinct from that terminal record.
- Actual PDF first failed extractor availability in the container. The controller preserved that
  retry, proved Windows PDF isolation, and processed the exact job through the existing worker
  to succeeded attempt 2. Owner verified actual Document Ready through UI. No fixture timeout
  or direct DB update supplied completion.
- Actual unsupported Turn became refused through the bounded existing runner; native UI now
  renders insufficient evidence and no invented citations. IDs are in ignored terminal JSON.
- Initial deletion diagnostic unexpectedly returned **202**, not the assumed unavailable 409.
  The attempt was stopped and reported to the controller/user. No cleanup, retry, object worker
  or second deletion submission followed. Its record ID was not saved before the assertion;
  physical outcome remains unverified. Final suite only opens/cancels the confirmation.
  Requested-deletion source presentation remains fixture evidence; release-wide deletion policy
  acceptance is not inferred from this one response.

## Accessibility and source limits

Keyboard/Escape focus return, modal tab trap, menu arrows, actual divider widths/reset, OTP
leading-zero clipboard input/error/no-JS input, live regions, overflow and anchored composer
were exercised. Four real token foreground/background pairs meet 4.5:1 in light/dark; reduced
motion yields zero control transition duration. This is sampled contrast, not a page-wide audit.
CSS zoom 2 reflow was checked; browser chrome 200% zoom is not independently proved.

Panel/response references are compact schematics, not full-screen geometry sources. Dark/mobile
Figma geometry references are absent. Screen target annotation strip (34px) is excluded; the
source PNGs/full structures are unchanged. Side-by-side comparison and ledger record actual
spacing/hierarchy/assets/color differences instead of committing a new acceptance baseline.

Open implementation deviations include extra desktop Menu/panel controls; authoritative answer
body versus the illustrated chapter-count heading; real citation page/source context versus
illustrated label; archived Workspace Conversation composer missing bottom Restore Workspace
CTA; native reset/completion copy/actions; and repeated citation click not clearing selection.
The latter is diagnosed at TurnCard selection callback → ConversationView `onSelect={setSelection}`
line 455; lookup line 309 clears missing citations only. It needs its own approved behavior fix.

Native reset/Vault/MFA/outage/browser CSP, I2 JS-disabled resend minor, I3 configured-origin regex
minor, five fresh Operator prototype contexts and explicitly unexercised edges remain gaps.
There is no native HTTP interrupt endpoint; interrupted state/retry input is fixture/unit evidence,
while thinking-click transitions are prototype simulation. No manual store/DB interruption was used.

## Self-review and handoff

Reviewed all added host/config/renderer/fixture/test paths and the exact production diffs.
Confirmed source-only host isolation, no production routes or generated OpenAPI edits, no new
dependency/install/provider/POM/service changes, and root artifact ignore policy. Boundary tests
reject unknown state, other Workspace, credential POST and delete method. Source comparisons
are current after affected recaptures. Remaining default M5 `REFUSE` fixture is a narrow follow-up
outside this approved Q1 test source scope, reported to the controller.

Preview processes exited after each serial Playwright invocation. Final port 3300 listener check
returned none; the owner releases the frontend lease. Existing containers and synthetic data remain.
Independent controller review should use the original base through this task's scoped commit.
Q2 broader release verification and integration decisions belong to the controller; Q1 is partial.
