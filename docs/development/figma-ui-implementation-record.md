# Figma UI implementation record — partial

Updated October 10, 2026. The approved objective remains implementation of the complete Figma
design. This is a continuity and evidence record, not Q1/Q2 or full-product acceptance.

## Current integration

Worktree: `C:/Developer/Projects/knora-agent-worktree/figma-ui-identity`.
Branch: `codex/figma-ui-identity`. Latest source slice: Operator detail geometry and Evaluation
value-slot correction (working tree; commit recorded below).
Evaluation, Operations, shared Operator frame and Trace flow have local verification; the latest
read-only review found no Critical defects and identified one evidence/claim correction, which is
recorded below. No merge, push, deployment, branch disposition or worktree removal has occurred.

The stack includes Next.js15.5.24, React18.3.1, TypeScript and Tailwind CSS v4, with local fonts,
semantic tokens, Vitest and Playwright. Canonical backend and Keycloak ownership remain binding.
The approved workflow's folder responsibilities are in
[the directory analysis](../superpowers/plans/2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).

## Recent completed source slices

Earlier source slices received separate independent spec and quality approval. The October 10
geometry follow-ups have local verification only; independent review remains outstanding. This records
its bounded scope; it does not promote fixture checks to native/live backend acceptance.

| Commit | Source change | Verified scope |
| --- | --- | --- |
| `6f7781d` | Citation reselection and authoritative bottom Workspace restore | Focused component, fixture and owned live restore evidence |
| `806dd4c` | Archived Workspace inspector notice | Actual inspector selected-source retention and desktop/mobile composition |
| `89d10f2` | OTP resend enabled without JavaScript | Actual FreeMarker RED/GREEN and two enhanced/no-JS browser cases |
| `5614653` | Completion configured-port/bracketed-IPv6 validation | Actual template RED/GREEN and complete FlowIT source checks |
| `6fd4cb3`, `299aa53` | Operator lookup guidance and fresh output-directory handling | Production compositions, scoped fixture navigation and desktop/mobile checks |
| `eb41be2` | Archived inspector retained-answer context minimum | Actual desktop340×96/mobile natural growth; selected provenance retained |
| `455acfc` | Three remaining Operator prototype comparisons | Synthetic typed observations and measured source deviations; no parity acceptance |
| `827f9f2` | Operator selector/carets, lookup dimensions, runtime band, trace columns and unavailable badge | 70 relevant unit tests and five browser cases at1440/390; no Important review finding |
| `d57a588` | Operator Workspace label and local rectangular Trace badges | 63 relevant unit tests and five browser cases; spec PASS / quality APPROVED |
| `bbf1cc1` | Trace summary, candidate inner widths and context text regions | 32 component tests, focused Trace case and five Operator cases; spec PASS / quality APPROVED |
| `6ff260d` | Evaluation explanation minimum and context text regions/row flow | 36 component tests, focused Evaluation case and five Operator cases; spec PASS / quality APPROVED |
| `81ff9e9` | Operations accounting/bucket allocations, value slots and Alerts text regions | 46 component tests; four Operator cases passed and Operations passed after asset-readiness recovery; spec PASS / quality APPROVED |
| `58d7290` | Shared Operator flow, source-specific tabs, separate divider and top-aligned lookup | Five desktop/mobile browser cases and13 focused component checks; spec PASS / quality APPROVED, no findings |
| `86679dc` | Trace answer/citations/provenance and candidate text/disclosure flow | Browser geometry RED→GREEN at1440/390;24 relevant component checks; spec PASS / quality APPROVED, no Important finding |
| `0a07834` | Operations vertical spacing and runtime/latency geometry aligned to direct MCP measurements | Figma fixture geometry `216:345`, full fixture suite 114 passed/10 skipped; frontend gates passed |
| `7bfba7b` | Trace and Evaluation detail content origins aligned to source | Three Operator fixture cases passed; 406 Vitest tests, format check, production build and typecheck passed |

The follow-up Evaluation value-slot correction was verified with all three Operator prototype
comparisons and the complete Figma fixture suite: 114 passed, 10 skipped. Frontend formatting,
typecheck and production build also passed; existing Next image optimization warnings remain.

Fresh exact-head backend qualification was rerun on the disposable `knora-figma-regression-postgres`
container at loopback port 5544 (the retained Figma database at 5543 was not targeted):
`pytest` passed **1640 tests with 16 skips and 28 warnings**, `ruff check .` passed, and
`docker compose config --quiet` passed with only unset optional Minio credential warnings.

The October 10 independent review found no Critical defects. It identified that the Evaluation
geometry evidence was comparing a row container with a text node and that the long observation
code was narrower than the direct Figma value slot. The comparison now keeps the row's measured
padding and divider separate from its label/value measurements, and the desktop observation code
uses the source's 300px value slot while remaining responsive below the desktop breakpoint.
The Trace candidates retain the approved Retrieval details disclosure; its natural 128px row
height and later phase offset are an intentional accessible-content adaptation to the source's
102px visual slot, not an unreported exact-parity claim. Operations retains its measured 1px
content-origin difference from the Figma outer border.

Fresh five Operator contexts were read directly through Figma MCP. Their complete structures,
uncropped whole-frame screenshots and measurements are cached under
`.verification/figma/q1/evidence/operator-prototypes-2026-10-07/`. Source frames are1440×960;
returned screenshots1024×683 have no annotation strip. Original51 sources remain preserved.
The missing caret was exported through MCP, then fetched using its explicit download instruction.
Local `bab86.svg` is331bytes, intrinsic11.4×6.4, SHA256
`864C1D2BB9B35ED4DD76DEE4346A2BF2BAE674A2B8E74EFBE6138A1651949911`.
Screenshots are visual targets and evidence, never UI implementation assets.

## Fresh regression evidence

Root commands ran in the integration worktree using the primary checkout's existing Python venv
and explicit integration `backend/src` PYTHONPATH. Results below qualify source at `827f9f2`;
later implementation changes require their own covering verification.

| Command | Actual result | Scope or limitation |
| --- | --- | --- |
| `python -m pytest` | Exit0;1556passed,16skipped,28warnings;279.62s | Entire collected1572 tests, dedicated isolated regression PostgreSQL |
| `ruff check .` | Exit0;All checks passed | Backend and repository lint at checked source |
| `python scripts/export_openapi.py --check` | Exit0;artifacts current | No generated contract drift |
| `docker compose config --quiet` | Exit0 | Optional Minio credential variables unset warnings; no services launched |
| `npm --prefix frontend run test` | Exit0;347passed across44files;78.57s | Complete Vitest suite |
| `npm --prefix frontend run build` | Exit0 | Production routes compiled; no native authentication claim |
| `npm --prefix frontend run format`, then `format:check`, then `typecheck` | Exit0 each | Geometry owner executed in that order before final focused checks |
| Focused five Operator browser cases |5passed;19.2s |1440×960 and390×844; API interception and no writes |
| `mvn clean verify` in pinned disposable Maven container | Exit1 |6unit and16FlowIT passed; real two-node prerequisite failed at missing proof header |

The full pytest run used only a newly created container `knora-figma-regression-postgres`:
loopback5544, database `knora_figma_regression`, ownership labels `figma-regression` and
`figma-ui-identity`, cached `pgvector/pgvector:pg16`. Alembic migrated it to4949b27855f4.
Tests that truncate tables or create/drop temporary databases were confined to this container;
retained Figma5543, daily5432 and Keycloak databases were not targeted. Proxy variables were
removed only from the test subprocess environment to avoid the previously diagnosed loopback
proxy failure. No lifecycle worker was started against retained data.

Maven first failed offline before tests because `maven-clean-plugin3.2.0` was absent from the
read-only proof cache. A disposable tmpfs copy with the normal Maven resolver cleared that
prerequisite, then exposed the missing real-probe header. The retained Figma stack was already
stopped approximately five hours before this run; no stack restart or recovery binding occurred.
The generated storage-proof classifier removed by `clean` was rebuilt with the existing
`storage-proof` profile, package with skipped tests, exit0. That artifact restoration is not a
passing full-Maven or native reset gate. No maintained dependency or cache change was made.

Detailed root logs and exit files are preserved at
`.verification/figma/q1/evidence/regression-preflight/`; owning task reports/reviews are retained
in the respective ignored SDD directories. Geometry task preserved239 unrelated artifact hashes
with zero drift; its five affected comparison captures were updated deliberately.

## October 8 frontend qualification

Fresh whole-frontend verification ran against source `81ff9e9`, including the independently
approved typography, Trace, Evaluation and Operations follow-ups.
Vitest passed 366 tests across 44 files in49.76s, exit0. Production build first failed after
compile/type checking/static generation at an ENOENT rename of generated `500.html`; the
destination file already existed after failure. A sequential build with no source changes or
cache cleanup passed, exit0. The precise cause of that intermittent generated-output failure
is unconfirmed. Existing Next image lint warnings remain visible; no source waiver was added.
Both build logs, diagnosis and exit records are retained in the excluded `regression-preflight`
directory. This fresh frontend evidence does not qualify native identity or replace the earlier
backend/Maven acceptance limits.

After frame source `58d7290`, with only subsequent plan documentation at `76ab6f2`, full Vitest
passed369 tests across44 files in20.09s, exit0. Production build passed its first run, exit0;
existing Next image lint warnings remain. Logs/exits are retained in the same excluded directory
with the `58d7290` suffix. No production source changed during these commands. Later Trace changes
require their own covering evidence.

## Trace flow and active reset presentation

The [Trace result/candidate plan](../superpowers/plans/2026-10-08-figma-trace-result-candidate-flow.md)
has passed independent review. Fresh complete direct MCP216:635 and its returned uncropped
render are saved under Q1 `evidence/trace-content-source-2026-10-08`. Source structure drives
result/citation/provenance positions and candidate text regions. Retained Retrieval details and
full observations remain in natural flow; source102px candidates cannot be enforced by clipping
those existing controls. Frame review remains pinned to28a6d3c→58d7290 and its263-entry artifact
audit; next-task source files were added afterward and their timing is disclosed in its report.

Trace result heading/answer/citations/provenance now follow source-relative0/34/82/126; first
candidate begins190, with source inner slots7/4/33/60 and retained disclosure88. Short candidate
rows naturally allocate128 rather than source102 to preserve that disclosure; the next starts326
rather than300. All266 evidence hashes were independently checked, four expected Trace outputs
changed and262 unchanged. The historical browser color-environment warning is a deferred minor
for the next authorized browser run; no optional rerun was made solely for that warning.

The [reset presentation plan](../superpowers/plans/2026-10-08-figma-reset-presentation.md) is active,
with original task BASE86679dc. Fresh complete MCP242:272/333/389 and246:311 structures and returned
renders are retained in its ignored SDD source directory. It changes existing template labels and
server-derived countdown display only, with privacy, native POST and no-JS semantics retained.
It cannot release the native reset binding/provider gate or prove a password transaction.

Reset presentation implementation is committed at `c9071f8`; independent review returned
Spec PASS / Quality Approved, no Critical or Important findings. Offline FlowIT18 tests passed;
two OTP JS/no-JS browser checks and the final source-copy
case passed. The final case covers four states at desktop/mobile, both password visibility toggles
and exact existing eye assets. Format, format:check and typecheck completed sequentially with exit0.
The offline renderer now extracts only the pinned698-byte parent visibility module and supplies
the native password page identity. No theme CSS, provider protocol or production asset changed.
Before/after Q1 inventory records261 unchanged of266 prior artifacts, four reset HTML changes and
one success HTML formatting drift from the earlier accepted source; exact historical success bytes
remain separately identified. Nineteen additions contain captures/geometry and the pinned module.
The reviewer independently verified285 artifact and12 source hashes. A proposed static-clock Minor
was later withdrawn: unchanged prepareFixture fixes Date before navigation, and an elapsed1500ms
diagnostic passed all eight static states without a new setter. No maintained test change was needed.

## Latest frontend qualification and archived Conversation bar

Source `070e4d2` includes reset presentation and the local archived Conversation bar correction.
Fresh full Vitest passed373 tests across44 files in46.69s, exit0. Production build passed its first
run, exit0; existing Next image lint warnings remain. Exact logs/exits are retained under
Q1 `evidence/regression-preflight/frontend-{test,build}-070e4d2.*`. No source changed during these
commands. These results qualify current frontend source, not native reset or whole-design acceptance.

Archived bar implementation uses authoritative existing restore availability for exact source copy,
and keeps generic server-rejected read-only copy. Desktop button151×34, inner748×48 and outer72
were verified; mobile grows naturally without clipping. Loaded Inter required7px rather than source
12px button padding; this measured adaptation and semantic color differences are disclosed.
Focused64 component checks and3 browser cases passed; format/check/typecheck exit0 in order.
All285 earlier artifacts remain unchanged, with10 A9 additions. Independent review identified
missing collapsed composition evidence. Test-only fix `cd3fb99` adds genuine desktop/mobile
collapsed captures using existing rail/evidence controls; both focused cases passed, with clean
color environment output. All295 pre-fix artifacts remain unchanged; four captures/JSONs were added.
Format/check/typecheck passed again in order. Scoped independent re-review returned Spec PASS /
Quality Approved, no new findings. No production source changed after the full frontend run.
The separate static-clock investigation preserved299 prior artifacts and added16 diagnostic
captures/JSONs; all experimental maintained edits were reverted. The original reviewer confirmed
the helper freeze boundary and withdrew the Minor. Both presentation tasks have no surviving findings.

## Remaining acceptance work

OTP input presentation `5583df8` received independent Spec compliance Approved / Task quality
Approved. Four focused browser cases passed, with format/check/typecheck exit0. The420px wrapper
centers six54px cells and10px gaps; narrower layouts shrink naturally. Empty marks remain decorative,
while the labelled native input stays truly empty. Leading-zero paste and clear were verified.
Of315 earlier Q1 artifacts,314 are unchanged and only copied native CSS changed; all nine native
HTML hashes are unchanged, with25 additions. The reviewer noted existing Java compiler notes in
the offline exporter; toolchain warning cleanup is deferred outside this bounded CSS task.
Native recovery/CSP and whole-design acceptance remain open. Documents local controls and the
detail action allocation are now independently approved, as recorded below.

- Operator label typography, Trace badges and relative Trace content measures are verified locally.
  Evaluation content measures and Operations accounting/bucket/Alerts measures are verified locally,
  with the direct-source value-slot correction above. Page coordinates, natural row growth, theme
  differences and supported extra controls remain explicitly measured. Comparison test success does
  not imply whole-page parity; the retained disclosure and 1px Operations origin are documented
  adaptations.
- [Visual coverage](figma-ui-visual-coverage.md) remains partial: original51 screen/panel/response
  mappings and89 prototype edge classifications retain per-edge unexercised paths and deviations.
  Source mobile/dark references are absent; responsive checks prove adaptation only.
- The isolated native OTP flow was exercised then restored. Desktop and mobile proved real
  email→OTP→password recovery, replay/generation handling, completion CTA and fresh native
  authorization; desktop also proved enrolled TOTP preservation and a required fresh TOTP login.
  The existing BFF application session is distinct from provider-browser SSO; raw provider cookie
  reuse is unverified. Restart/rotation, CSP/browser, upgrade/runbook and physical-outage evidence
  remain deferred deployment hardening in Issue #152. See [Keycloak theme](keycloak-theme.md).
- Live logout, expired-session journeys and remaining real-flow regression evidence are incomplete.
  Source/template/fixture tests cannot establish those service behaviors.
- Full Q2 and final whole-branch review remain outstanding. Main integration requires the Frontend
  formatting workflow's passing Prettier status; no integration action is authorized by this record.

Keep the goal active until the original requirements and their authoritative evidence are complete.

## Oct9 reset-success and identity navigation follow-up

The native reset-success path now keeps Keycloak's actual username/password form in the
Figma R4 composition. A successful password update stamps only a short-lived per-tab cosmetic
`sessionStorage` marker and replaces the page with the validated BFF
`/api/auth/login?prompt=login` URL. The fresh native login consumes the marker once and reveals
the green `Password updated` / `Sign in with your new password.` notice above the form. Pages marked
`isAppInitiatedAction` retain their native action link; storage failure leaves the server CTA usable.
No password, OTP, token, callback, or provider cookie is placed in the marker.

The identity E2E suite passed 9/9 after adding both reset-success secondary destinations
(Create account and Forgot Password). The native OTP runtime passed desktop and
mobile recovery again, and a new native secondary-navigation journey passed at both viewports:
Create account ↔ Sign in, registration validation → Sign in, reset request → Back to sign in,
verify/rejected OTP → Use a different email. The full frontend Vitest suite passed 400 tests across
45 files before the subsequent Conversation test additions; the reset-marker and callback-origin tests are included. A callback failure now
uses the validated configured public callback origin when running behind a proxy and fails closed
to the request origin for malformed or unsafe configuration. Fresh transition evidence is under
`.superpowers/sdd/2026-10-09-figma-reset-success-native-login/`.

These changes close the previously unproved identity secondary edges and replace the detached
completion behavior with the approved native form composition. Exact whole-page parity, provider
browser SSO-cookie reuse, natural expiry/account switching, and the remaining prototype/live
coverage gates remain open.

## Oct9 native OTP runtime evidence

Reviewed source checkpoint `92d1f8d` contains the dedicated native OTP journey and its bounded
non-reusable TOTP handling. The final desktop (`desktop1440x960`) and mobile (`mobile390x844`)
runs each passed one case after guarded isolated Bind. They exercised transitions 65, 72, 74,
76, 78, 79 and 81 in the visual ledger with real SMTP/native forms, including malformed and
wrong OTP rejection, cooldown/resend, generation fencing, password policy/confirmation,
completion and fresh login. A follow-up native identity run passed both viewports and verified
secondary transitions 67, 69, 71, 73, 75 and 77 (registration, sign-in, request-form return,
and change-email paths). The existing reset-success identity evidence covers transitions 80 and
82. The completion capture was inspected against direct MCP source; its notice and native login
composition differs from Figma node `250:841`, so completion parity remains open.

The current isolated native identity suite was rerun after the transition evidence update:
**12/12 tests passed** against the running Figma Compose harness. This covers native sign-in,
reset-success secondary destinations, invalid-credential and failed-outcome recovery, registration
validation/policy behavior, and active/archived registration outcomes. It is runtime evidence for
those identity transitions only; it does not bind the custom OTP provider or establish exact
whole-frame parity.

The consumed-replay oracle was verified against the native result: a second submission of the
prior verification action returns HTTP 400 HTML with the native `#kc-error-message` page-expired
marker, no redirect, and no OTP, login, or password form. Storage/service consume evidence
remains the authoritative challenge-consumption proof.

The native identity journey now also verifies transition 84 end to end. A newly registered account
is first rejected with a wrong password while the native form preserves the email and the BFF
session remains unauthenticated; replacing only the password reaches the same owned Workspace URL.
The focused Chromium case passed after the required frontend format, format check and typecheck
gates. Evidence is `edge-84-invalid.png` and `edge-84-corrected.png` under the native identity
evidence directory. This closes a previously fixture-only transition; exact source-frame parity
and natural session expiry remain separate gates.

The native Auth content origin is now aligned one pixel left with the direct Figma MCP source for
node `250:841`: the 420px rendered content begins at x=829 inside the source's x=819, 440px
container with 10px padding. The focused identity geometry assertions were updated with this
source-derived correction; semantic controls and backend authority are unchanged.

The Documents live journey now also covers transition 30. It submits a real deletion request from
the owned detail view, observes HTTP 202 with an idempotency key, renders the authoritative blocked
deletion projection when the policy is unavailable, and follows the detail back link to the same
Documents list with the source row retained. The focused application journey passed after the
frontend formatting and typecheck gates. This proves navigation and projection semantics only;
physical deletion remains deferred in Issue #150.

The CTA test transfers only the observed BFF application session and requires a fresh native
`prompt=login` transaction with new state, nonce and PKCE values. It records
`existingBffSessionFreshLogin=true` and `providerBrowserSsoVerified=false`; the latter is
explicit because no browser-visible Keycloak identity cookie was observed. Restore returned
the saved realm settings and unset client origins after each run, and the custom flow/key/data
were retained. Sanitized command logs and the transition evidence are under
`.superpowers/sdd/2026-10-08-figma-otp-native-runtime/`.

## Oct8 Documents completion and refreshed frontend qualification

Documents local interactions committed at `0528c72`; independent Spec compliance and Quality
review both approved with no findings. Two desktop/mobile browser cases and45 relevant component
checks passed. The owning menu wrapper now opens upward on mobile after a retained924.42px
overflow RED in an844px viewport. Filtering, search, keyboard menus, cancelled deletion dialogs,
selected-file reset and focus return are checked without API writes. Scoped href assertions do
not prove destination arrival. All340 earlier Q1 artifacts remain unchanged;12 task additions
bring the inventory to352. Upload trigger158.23×38 versus source154×38 remains a disclosed gap.

Document detail action allocation committed at `145c41c`; independent Spec compliance and
Quality review both approved with no findings. Actual42px deletion height failed against the
source40px expectation before correction. Local callsite classes now preserve42px Reprocess,
Archive and Restore, and40px Request deletion. Two final formatted browser cases cover both
Ready/Archived at desktop/mobile, Cancel/Escape/focus, exact existing assets and GET-only guards;
45 component checks passed. The first GREEN attempt's incorrect Workspace GET expectation was
diagnosed from actual fixture composition and corrected only in the test. All352 prior artifacts
remain unchanged;14 own-folder additions bring the inventory to366. Natural source/provenance
row growth and other page differences remain documented in the visual ledger.

Fresh complete frontend qualification on clean source `145c41cbfa6634de33e44d2233a0ff460ff24441`:
`npm --prefix frontend run test` passed373 tests across44 files (28.06s), exit0;
`npm --prefix frontend run build` passed, exit0. Existing Next image lint warnings remain.
Full logs and exit files are retained under Q1 `evidence/regression-preflight/` as
`frontend-{test,build}-145c41c.*`. HEAD and clean status were verified after both commands;
no maintained source changed during qualification. Format/check/typecheck passed sequentially
in the task. These results cover the current frontend source, including the mobile menu fix;
they do not qualify native OTP or complete Q1/Q2.

Current runtime check: Docker responds, but `docker ps` reports no running containers. Live
identity/logout/session evidence therefore needs the guarded retained harness resumed separately.
No recovery binding, password change, blocked outage retry, service mutation, merge, push or
worktree cleanup was performed in these Documents tasks. The full goal remains active.

## Oct8 live logout and forced sign-in

The guarded live identity task committed at `c03b799` and received independent Spec compliance
and Quality Approved review with no findings. The retained `knora-figma-e2e` services were started
through `prepare-figma-e2e.ps1 -CheckConfigurationOnly` plus owned Compose start; issuer discovery,
API health and Mailpit readiness returned200. No proof/proxy services or realm-configuration
mutation were used.

At1440×960 and390×844, the same browser context completed native login, then forced
`prompt=login` reauthentication. The fixed Keycloak callback remained in use, untrusted
`returnTo` was discarded, and state/nonce/PKCE values differed by boolean comparison only. The
username-hidden reauthentication field was readonly and password-empty before capture. Account
logout observed BFF303, native Keycloak logout confirmation, Signed out, scoped panel preference
removal, unrelated preference retention, null safe session, protected Workspace401 and a fresh
password-empty native sign-in form. No non-GET `/api/v1` writes occurred.

The first attempt exposed a test assumption: Keycloak's username-hidden form has no editable
username input. The test now asserts the readonly attempted username and reruns both cases green.
All366 prior Q1 artifacts retain their hashes; eight PNGs and two sanitized JSON journey files
were added under `live-logout-prompt-2026-10-08`. Mobile native forced sign-in reports horizontal
overflow while desktop does not; this is disclosed as an adaptation gap because no mobile Figma
identity reference exists. Natural expiry, reset completion, OTP/MFA, account switching and
whole-design parity remain unproved.

## Oct8 whole-branch acceptance audit

Independent review of `531f06e..809d914` returned **NOT READY / FAIL for the complete
approved objective**. The retained report is
`.superpowers/sdd/2026-10-05-figma-ui-workflow/final-whole-branch-review.md`.
Critical gaps are the unbound native OTP recovery flow, unresolved whole-design parity,
and unexercised prototype transitions. Selected live journeys and approved local slices
remain bounded evidence. The review does not authorize integration or close Q1/Q2.

This historical Oct8 audit is superseded for OTP runtime binding: the current isolated harness
uses `knora-figma-otp-runtime:26.3.3`, and the dedicated native OTP suite passed 4/4 across
desktop and mobile. The remaining gaps are provider browser SSO-cookie reuse, natural session
expiry, whole-design parity and the still-unexercised transitions listed in the current ledger.

On source `809d914`, four existing auth suites passed28 tests when run from `frontend`:
`npm exec vitest run tests/auth-session.test.ts tests/auth-logout-origin.test.ts
tests/auth-refresh.test.ts tests/auth-figma-integration.test.tsx` (exit0). The initial
repo-root invocation failed alias resolution before collecting tests; it is not a product
regression. This focused result does not prove natural session expiry or final-head global
qualification. Current OpenAPI and Ruff checks cannot run successfully in the host Python
environment: FastAPI and Ruff are absent. Compose configuration check returned exit0.

Actual native username-hidden reauthentication diagnosis ran twice at1440/390, both2
cases passing. At390px, document scrollWidth525 comes solely from the inherited hidden
restart-login tooltip: x394.80, width130, right524.80. Its48px button fits atx318/right366;
desktop has no overflow. The retained sanitized diagnosis is
`.superpowers/sdd/2026-10-05-figma-ui-workflow/native-reauth-overflow-diagnosis.md`.
Temporary diagnostic tests/config were removed. Commit `decaab7` applies the bounded
mobile-only tooltip placement and adds the no-overflow assertion; the live journeys passed
at390px, 800px, 801px and1440px after the fix, including the mobile hover arrow check. This resolves the recorded adaptation defect only and does
not change the still-open native OTP, parity or transition gates.
Fresh qualification after `decaab7`/`8279f8f`: frontend Vitest passed373 tests across44 files; the production build passed with only the existing Next `<img>` warnings. Format, format:check and typecheck passed before the four live viewport journeys (1440, 801, 800 and 390), including the mobile hover arrow check. These results qualify the current frontend source and mobile tooltip correction only; whole-design acceptance remains partial.

OTP binding and the rejected physical outage proof remain held; equivalent workarounds
are prohibited. Keep the goal active.

## Oct8 Conversation creation navigation

The retained Workspace restore journey now exercises New Conversation from an unsubmitted
draft and from an archived Conversation in an active Workspace (prototype edges34 and51).
It asserts POST201 with an idempotency key, waits for a different destination URL, then reads
GET200 to confirm the new ID, Workspace and active state; the destination composer is empty.
The source Conversation remains archived afterward. While the Workspace is archived, the
creation button is absent. The full scoped live journey passed (1 case,20.7s before formatting,
then 1 case,21.1s after formatting). Format, format:check, typecheck and diff checks passed.
Independent review approved this bounded three-file change with no Critical or Important findings.

Earlier attempts read a response body after document navigation, or inspected the old URL
before navigation completed. The final test waits for navigation and reads persisted state.
The original restore assertion also used superseded copy; it now expects the source-aligned
“Archived conversation · Read-only” status already rendered by ConversationComposer.
No production code changed. New evidence is in `conversation-creation-2026-10-08/`; future
runs of this journey use that folder. Earlier failed attempts had already overwritten some
legacy restore captures, so no unchanged-hash claim is made for those artifacts.
Other Conversation starting states, native expiry/OTP and whole-design parity remain open.

## Oct8 Operator tab navigation

The existing authorized live journey now exercises all eight previously unclicked tab directions
(54,55,56,58,60,61,63,64) and retains the trace-detail → Evaluation lookup direction59.
Each destination asserts its route, heading or lookup controls and selected Workspace. Empty
lookups have empty fields and disabled submit controls. The trace comes from real ingestion and
question processing; evaluation remains truthfully unavailable. Existing report refresh,
Workspace switching, cross-Workspace denial and missing-capability denial still pass.

The final scoped run passed2 cases in49.9s after format, format:check and typecheck (all exit0).
The earlier version passed2 in40.7s before the evidence path correction and retained edge59.
New captures use `.verification/figma/q1/evidence/operator-tab-journeys-2026-10-08/`;
the first run's scratch captures remain in this task's ignored SDD folder. Historical Operator
captures were not targeted. Representative real trace and empty-lookup captures were inspected.
Routine existing NO_COLOR/FORCE_COLOR warnings were emitted. This test-only change proves bounded
navigation and denial behavior; native OTP, full source parity and whole-head acceptance remain open.

Independent review found that edges 63 and 64 did not both prove the unavailable report source
before their tab clicks. The Operator journey now checks the requested
`operator-no-persisted-report` ID, `EVALUATION_REPORT_UNAVAILABLE` code and selected Workspace
immediately before each click. After this assertion-only correction, `npm --prefix frontend run
format`, `npm --prefix frontend run format:check` and `npm --prefix frontend run typecheck` each
exited 0. From `frontend`, `$env:FIGMA_TEST_MODE='application'; npm exec playwright test --
--config=playwright.figma-operator.config.ts` passed both cases (50.6s, exit 0). The run refreshed
the 14 captures in `.verification/figma/q1/evidence/operator-tab-journeys-2026-10-08/`.

### Oct8 Documents back-filter owner correction

Task 1 adds the live Documents row/menu/detail journey and focused component coverage. The local
archived filter reads `archived=true` through Next search params, while the archived detail owner
adds the query to its existing back link. No API scope or capability behavior changes. Evidence,
RED/GREEN commands, revisions and source projections are recorded in the task report and
`document-navigation-2026-10-08/`; processing-source, deletion, native OTP and full parity remain
unproven.

The isolated Documents journey completed after correcting the synchronous Markdown projection
oracle. Its fresh run passed1 case in19.9s. The exact source `q1-navigation-af9d18e4-b30b-480e-88a2-4b584f0cfa74.md`
was document `52efda78-cfc7-4c99-9376-83c899b39ddf` in Workspace
`17113675-7bdc-4487-8b79-d94b6575c639`. Current/served version
`67b99ee3-9a9a-4120-b14b-c2c56503812d` persisted through archive/restore. Revision advanced
1→2→3; availability changed available→unavailable→available. The archived back link preserved
`archived=true` and the checked local filter. Archive and restore returned200 using the observed
revisions in If-Match. Final restored list and four detail/menu images were inspected. The upload
created no ingestion job (`ingestion_job_id=null`, `ingestion_status=null`), while readiness is
`ready` and serving is `current`. This is the observed synchronous Markdown contract, not a
processing-row or asynchronous PDF claim. Synthetic data was retained.

### Oct9 Documents menu destinations

Archive and restore menu actions now navigate only after the scoped POST returns 200. The
canonical detail GET is authoritative: archived detail back preserves the checked
`?archived=true` list, while restored detail back returns to the bare list. Focused component
coverage records exact archive/unarchive paths and If-Match revisions, pending duplicate
suppression, unresolved responses, rejected requests, HTTP 409/403/401 outcomes and stale
Workspace scope. The live journey records destination states in
`document-menu-destinations-2026-10-09/`; source/version identity, revision transitions,
available→unavailable→available, null deletion and synchronous Markdown/null-job qualification
remain explicit. The native OTP reference is source checkpoint `92d1f8d`.

The reviewed correction at `b2b687f` requires exactly HTTP 200; 201/202/204 do not navigate.
Focused Vitest passed 59 tests and the final live journey passed one case in 20.7s, after format,
format:check and typecheck. Final captures use the separate `fix-http200-2026-10-09/` subfolder.
Independent Spec/Quality rereview approved the scoped correction with the historical-evidence
limitation retained: the initial Documents preflight was omitted. A historical manifest comparison
found 365/366 unchanged and no missing files, with one legacy Workspace capture changed before
this task. The fresh before/after audit proves all 436 prior Q1 files stayed unchanged during the
correction and final journey. This does not establish full Figma parity or global pytest acceptance.

### Oct9 Conversation creation from retained outcomes

The application journey now exercises the real New Conversation control while the retained
Conversation shows an answered Turn, a selected citation, an authoritative refusal, or an
unsubmitted draft. Each case observes POST201 with an idempotency key, waits for browser
navigation, verifies the new active Conversation through authenticated GETs, checks the new
composer is empty, and hashes the source history before and after to prove it was not changed.
The journey passed one Chromium case in 29.1s after the response-body assertion was corrected
to read the persisted destination after navigation. Evidence is in
`.verification/figma/q1/evidence/conversation-navigation-2026-10-09/`; the owning test is
`frontend/tests/e2e/figma-conversation-navigation.spec.ts`.

This closes the grounded-answer, selected-citation and refusal starting-state creation edges.
It does not manufacture an interrupted backend state, close natural expiry, or establish
whole-frame Figma parity or full 89-transition acceptance.

### Oct9 native recovery requalification

The owned OTP runtime was rebuilt from the isolated Keycloak image with the existing protected
Vault and the realm binding was verified as already present. The focused `EmailOtpResetFlowIT`
suite passed in the pinned Temurin 21 container. The complete native OTP browser file then passed
all four cases: identity secondary navigation at desktop/mobile and recovery/resend/consume/fresh
sign-in at desktop/mobile (2.6 minutes). The identity file passed all nine Chromium cases after
the same runtime restart, including both reset-success secondary destinations and the callback
failure-origin checks. Fresh captures are under
`.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/{native-otp,identity}/`.

This requalifies the current native runtime and reset-success implementation. Provider browser
SSO-cookie reuse, natural session expiry, deployment hardening Issue #152, whole-frame parity and
the remaining unexercised Figma transitions remain open as recorded in the visual ledger.

The identity follow-up also closes edges 83 and 86: invalid native credentials now enter the
real OTP request form through Forgot Password, and the failed callback outcome retry link starts
a fresh native Keycloak sign-in. Both focused Chromium cases passed (11.2s); captures are
`AU2-recovery-request-live.png` and `AU4-retry-sign-in-live.png` in the identity evidence folder.

Post-change qualification is green for the maintained frontend: Vitest `406/406`, fixture
Playwright `114 passed, 10 skipped` across all `124` selected cases, the live Documents journey
`1 passed`, the live Operator suite `2 passed`, and the live Conversation creation journey `1
passed`. The fixture run includes the Figma visual states, responsive states, dark/reduced-motion
states, OTP presentation and interaction regressions. The ten skips are guarded live journeys
in fixture mode. The dedicated live suites above do not cover every skipped case; the remaining
live cases retain their earlier evidence and were not requalified in this batch.

Evidence preservation limit: the broad fixture reruns wrote to their established capture paths
without a before-run hash inventory or copies. Those paths show the latest run, not immutable
historical captures. Earlier task-specific hash audits remain scoped to their recorded runs.

### Oct10 password completion discriminator

Native Keycloak completion now distinguishes successful password events from generic account
completion before enabling the Figma reset-success notice. A global event listener sets a
request-scoped forms attribute only for successful `UPDATE_PASSWORD` or password
`UPDATE_CREDENTIAL` events in the Knora realm; `UPDATE_PROFILE`, OTP credential changes,
errors, another realm/theme and missing details retain the generic trusted sign-in CTA.
The focused provider tests passed 22/22 plus 1/1 listener cases, and the live Identity suite
passed 12/12 including the generic profile action. This remains tied to the pinned Keycloak
26.3.3 synchronous event/provider behavior; deployment hardening remains Issue #152.

The subsequent application-mode Figma journey rerun passed 12 tests with 33 guarded skips when
controller proof was enabled.
It covers live account logout, workspace restore, archived Conversation/Workspace behavior,
document lifecycle, lost-response recovery, and PDF job observation. The controller-backed
answer/PDF/refusal journeys were preserved behind their explicit proof guard for the broad run;
all three were then requalified in the current runtime below. The PDF test is run after the host
worker processes the newly created job because the browser batch does not start a worker between
its upload and Ready assertions.

### Oct10 controller-backed transition requalification

With `FIGMA_CONTROLLER_PROOF=1` and the preserved owned artifacts, the grounded-answer and
unsupported-refusal journeys were run against the current isolated runtime and both passed. They
verified the authoritative answered citation projection and the refusal projection with no
citations. The earlier PDF artifact no longer resolves through the current API runtime, so the
Ready assertion failed before any document assertion. A fresh owned PDF upload was then accepted
and its authoritative queued job observation passed. The container worker could not install the
required Linux cgroup memory limit and returned `PDF_EXTRACTOR_UNAVAILABLE`; the same job was then
processed by the host Windows worker with the required Job Object limit and reached `succeeded`.
The guarded PDF Ready browser journey passed, proving the detail route's Ready projection and
source identity. No deletion was attempted.

## Oct10 guarded logout viewport requalification

The live account logout and forced sign-in journey was rerun against the retained runtime at
1440, 800, 801 and 390px viewports. All four Chromium cases passed (26.2s total), including
BFF logout, native Keycloak confirmation, null session/protected Workspace rejection, fresh
password-empty sign-in, scoped preference clearing and the mobile no-horizontal-overflow check.
The run adds fresh captures and sanitized journey records under
`.verification/figma/q1/evidence/live-logout-prompt-2026-10-08/`. This strengthens transitions
88/89 live evidence; it does not prove natural session expiry, provider SSO-cookie reuse or
whole-design parity.

The application-mode Figma suite was rerun with the host worker polling the retained runtime
for the duration of the browser run. It completed **11 passed, 33 skipped**: logout at four
viewports, Workspace/Conversation restore, document lifecycle and lost-response recovery,
queued PDF observation, grounded Turn reconciliation, PDF Ready projection, and refusal
projection. The worker was stopped after the run. This removes the earlier harness-ordering
failure where the newly uploaded PDF was still queued when the later Ready test read it.

## Oct10 Operator runtime requalification

The isolated Figma Operator suite was rerun with the retained runtime and direct backend-backed
fixtures. Both Chromium journeys passed (32.3s): the five-state authorized journey created a
real workspace, document and answered question, then verified Operations, Trace lookup/detail,
Evaluation unavailable, tab transitions 54–64, workspace switching and source provenance; the
denial journey verified cross-Workspace 403 and missing-operator capability denial with no trace
content. New captures are under `.verification/figma/q1/evidence/operator-tab-journeys-2026-10-08/`.
This confirms the Operator interactions remain live; exact Figma source parity differences stay
recorded in the coverage ledger.

The live Conversation navigation journey was rerun against the current runtime and passed
(1/1, 19.1s). It preserved retained answered and refused turns, citation inspection and an
unsubmitted draft while creating a distinct authorized Conversation four times. The source
history hash stayed unchanged and each destination was confirmed through the authenticated API.

## Oct10 auth regression after source-copy reconciliation

The complete native identity suite passed **13/13** in 32.6s. The dedicated native OTP suite
then passed **4/4** across desktop and mobile in 1.7 minutes, including recovery, resend,
generation fencing, consumed-code replay rejection, password update and fresh sign-in. A
parallel launch initially conflicted on the shared port; the suites were rerun sequentially and
these are the authoritative results.

## Oct10 frontend gate recheck

The maintained frontend was rechecked after the latest implementation record updates. `next
build` completed successfully, TypeScript completed with no diagnostics, Prettier formatting and
`format:check` both passed, and the full Vitest suite completed **406/406** tests across 45 files.
`docker compose config --quiet` also passed. The repository Python environment is absent in this
worktree, so the mandated `.venv` pytest and Ruff commands could not be executed here; this is an
environment gate limitation rather than a frontend test result. Whole-frame parity and the
explicitly deferred runtime/deployment gates remain open as recorded above.

A fresh fixture comparison for Operator Operations (`216:345`) passed 1/1 after rechecking the
source geometry. It confirms the rendered desktop signal band is 1200×108 and preserves the
existing backend-derived unavailable state and mobile fit. The remaining accounting, bucket,
Alerts and navigation-origin differences stay explicitly recorded in the visual ledger.

The complete fixture Figma suite was then rerun sequentially: **114 passed, 10 skipped** across
the 124 selected cases. The skips are the guarded application journeys, which require the live
runtime and are covered by the separate application-mode evidence; no fixture case failed.

Application-mode guarded journeys were rechecked against the retained runtime: **7 passed, 3
skipped** in the no-worker run, covering logout at four viewports, Workspace restore, document
lifecycle/lost-response recovery and queued PDF observation. With controller proof enabled, the
grounded-answer and refusal journeys passed; the PDF Ready journey correctly remained queued when
the isolated extractor worker was not running, so no false Ready claim was recorded.

The retained isolated PDF runtime was then advanced with the approved worker command using the
Figma PostgreSQL/MinIO endpoints. The previously queued owned PDF was reconciled and the focused
application journey `existing owned PDF reconciles to Ready after the controller isolated
extractor` passed **1/1**, observing `succeeded` and the Ready document projection. This closes the
remaining PDF Ready application evidence for the retained artifact.

With the worker kept polling for the duration of the run, the complete guarded application suite
then passed **10/10** with `FIGMA_CONTROLLER_PROOF=1`: all four logout viewports, Workspace
restore, document lifecycle/recovery, queued PDF observation, grounded answer, PDF Ready and
refusal. The worker was stopped after the run.

The initial light-theme `--text-muted` correction used the direct Figma Operator source value
`#657A74` (`rgb(101,122,116)`). A test-first token assertion caught the prior `#546B63` value;
that version passed the then-existing white-background contrast check, all 41 Operator component tests, all **406/406**
frontend tests, the three Operator source comparisons, typecheck, format gates and production
build. Dark-theme muted text remains unchanged because no corresponding dark Figma source exists.

Evaluation body explanation, context labels and observation code now use the source-specific
`--evaluation-muted` token (`#5E736B` in light; existing muted `#94B3A5` in explicit/system dark).
The source description and Workspace label used `#657A74` at this checkpoint; their shared
muted token is subsequently corrected for accessibility below. A failed component assertion preceded the change. Browser evidence for `216:755`
passed 1/1 and records explanation source/current color both `rgb(94,115,107)`. The full frontend
suite passed 406/406; format, typecheck, build and diff checks also passed. This closes only this
Evaluation color residual, not whole-frame parity.

## Oct10 Alerts surface and Trace timing follow-up

Operations Alerts now uses the direct light Figma value `#F4EAE6` through
`--operator-alert-surface`. Explicit/system dark retain the previous semantic mix. The focused
`216:345` browser comparison passed 1/1 at desktop/mobile after the new color assertion failed
on the old mix. Full Vitest passed 406/406, format/check, typecheck and build completed; build
retains the existing Next.js image lint warnings.

Trace Citation mapping was 1px below its source heading; Phase timing was 14px below. A new
relative browser assertion reproduced both before editing. Natural mapping-row spacing and
the timing list margin now match the direct cached MCP structure, retaining complete aliases,
Chunk IDs and filenames. The focused `216:573` browser comparison passed 1/1 at1440/390.
Fresh source/current global y values are Citation mapping738, Phase timing851, Retrieval875
and Validation927. The49 relevant component tests, format/check, typecheck and diff check
passed. Full evidence/provenance disclosures and natural wrapping remain; the retained128px
candidate rows versus source102px are still a documented adaptation, not independent parity
acceptance. No backend or native identity behavior changed in this follow-up.

Docker responded with server29.7.2 after the user's engine-ready confirmation. The primary
repository's Python environment exists and can be used for further worktree qualification;
the earlier statement about an absent environment applies only to the worktree-local path.

After the Trace change, full Vitest passed406/406 again and production build exited0. Ruff
passed against the worktree using the primary interpreter. Pytest collection succeeded with1656
tests; collection is not an execution claim. Compose configuration exited0 with unset optional
canonical/provider-test credential warnings. No retained runtime data was reset.

## Oct10 Documents menu alignment and live regression

The full Figma fixture suite passed114 cases with10 application-only skips after the Trace and
Alerts corrections. This is fixture composition/interaction evidence, not full parity acceptance.

Fresh Figma MCP `get_design_context` for `128:120` returned a complete structure and screenshot
without authentication failure. Its200px Ready menu has a5px inset from the1200px content's right
edge and2px item gaps. The production menu previously inset13px with0px item gaps. New browser
assertions reproduced both deviations before the local DocumentActionsMenu correction. Desktop
now records x1115,width200,height159; mobile retains the upward opening and viewport containment.
All4 Ready actions, Archived actions, keyboard focus, Escape/Cancel and zero-mutation fixture
contracts passed2/2. Shared Menu behavior and assets were not changed.

The live `Documents live navigation preserves owned source and menu lifecycle` journey then
passed1/1 using the isolated test identity/runtime, confirming real upload, Ready row/detail,
menu navigation, archive/restore and truthful blocked deletion projection. Relevant Documents
and Menu component tests passed70/70; format, format check, typecheck and diff check passed.
Fresh structure is cached at `.verification/figma/q1/evidence/documents-source-2026-10-10/128-120.md`.
No native/backend behavior was changed. Existing action foreground and status colors retain the
approved accessible semantic palette; example filenames/state copy do not override backend facts.

## Oct10 Inspector typography and muted contrast review correction

Fresh direct MCP structures for `128:109`, `128:107` and `183:176` confirm that the Inspector
content title uses Inter14/20 while its panel header uses Roboto Slab16. The content h3 now
explicitly uses `font-sans`. The browser test first failed on inherited Roboto Slab at1440/390,
then passed. Five focused browser cases cover empty suggestions, retained and archived evidence,
mobile sheet Escape and composer context;75 relevant component tests passed. The Inspector build
exited0 before the subsequent token correction. Cached complete source is under
`.verification/figma/q1/evidence/inspector-source-2026-10-10/`.

Independent review found one P2 contrast regression in shared muted text. The Figma sample
`#657A74` passes on white but falls below4.5:1 on page and subtle surfaces used by small Documents
headers, Inspector labels and Conversation trust cues. Six new theme/background cases reproduced
the two light failures (4.352 and4.261). The shared light token now uses `#60756F`, yielding
4.916 on white,4.676 on page and4.578 on subtle surface. This is an accessibility adaptation;
the original source measurement remains unchanged in comparison evidence. Dark values are unchanged.
The token guide records the rationale and current mapping.

After correction,69 scoped tests passed and the actual-browser contrast/reduced-motion case
passed1/1 with muted coverage on all three backgrounds in both themes. Format, format check,
TypeScript and diff checks passed. Existing environment color warnings were emitted by Playwright.
Whole-frame parity and integration acceptance remain open; these results do not claim completion
of the entire Figma scope or the deferred deployment gates.

The focused independent re-review recalculated both themes on all three backgrounds and resolved
the P2 finding: Spec compliant, Quality approved, no remaining finding from this correction.
Full Vitest subsequently passed412/412 across45 files, including the six new contrast cases.
Production build exited0 with the existing Next.js image warnings. Issue#152 was reread and
updated in place to replace the obsolete blanket native-runtime blocker with bounded evidence;
its essential security requirements, pending deployment work and open state were preserved.

The full Figma fixture suite then exited0:114 passed,10 application-only skips in1.5minutes.
This fresh run includes the Documents menu, Inspector typography and contrast corrections;
it checks51 source compositions and responsive/dark adaptations plus local interactions.
It is not live authorization evidence or independent whole-frame parity acceptance.

### Current work classification

| Category | Current status and next evidence |
| --- | --- |
| Implementation corrections | Inspector content typography and shared muted contrast are implemented. Documents menu, Operator Alerts and Trace timing corrections remain in the working diff. Their bounded source and test evidence is recorded above. |
| Implemented, incomplete verification/acceptance | Whole-frame comparison and final integrated review remain open. Some prototype edges still have component/fixture rather than live coverage; this does not establish missing product handlers. Provider browser SSO-cookie reuse and natural session expiry remain unverified. Native registration itself has runtime evidence; its ACTIVE destination follows the backend resolver rather than manufacturing the prototype NO_ACTIVE state. |
| Approved follow-up work | Physical deletion/retention#150, future supplied mobile/dark references#151 and deployment hardening#152 remain open. Documents live evidence#149 is locally resolved and awaiting integration. No additional scope was deferred. |

The next audit must identify an actual missing product action before adding behavior; reuse existing
evidence for equivalent handlers and record the specific origin/destination that remains unproved.
Prototype timeout/click simulations are not product actions. Figma completion still requires the
approved source coverage and final review, without importing deployment-only work into that path.

## Oct10 tinted notice foreground correction

Fresh full direct MCP128:118 confirms the interrupted heading, unavailable evidence and notice
copy; complete text is cached in `interrupted-source-2026-10-10/128-118.md`. Review then identified
additional actual background pairs outside the previous three-background token check: the small
Inspector refusal/interruption label and the DocumentDetail deletion-policy explanation use a
signature-tinted surface. The new actual-browser case computes foreground contrast against all
composited ancestor backgrounds. RED measured4.198:1 for the light refusal label.

Those two local foregrounds now use existing `text-secondary`; backgrounds and backend projections
remain unchanged. GREEN passed1/1 across refusal128:111, interruption128:118 and deletion128:131
in light/dark (six pairs). Format/check, TypeScript and diff check passed;84 related Conversation,
panel and token tests passed. This closes a concrete accessibility defect rather than asserting
full source-color parity or adding deployment hardening to the Figma critical path.

Documents/citation regression subsequently passed60/60. The independent review resolved the
additional tinted-notice finding in inspected source; the actual-browser GREEN is the controller's
execution evidence. The preceding114-case fixture/full build results predate this local foreground
change and must not be represented as a fresh whole-suite run of it.

## Oct10 Workspace popup source rows

Fresh direct MCP140:104 nodes140:233/236/238/241 define borderless40px rows,2px gaps and13px/16px
labels. Actual production options and Create inherited legacy main-button borders and margins.
A new browser assertion reproduced1px borders before the fix. WorkspaceSelector now resets these
locally, uses transparent ordinary backgrounds, medium ordinary labels, semibold current/Create
labels and a2px option gap. Search, archived navigation, semantic current highlight and handlers
remain. No global button CSS or static asset changed.

GREEN verifies three40px rows, zero margins/borders,16px line height,500/600 font weights,2px gap,
Create40px and ArrowDown/Escape focus return. Combined with tinted-notice verification it passed2/2.
Workspace/panel regression passed75/75; format/check, TypeScript and diff checks passed.
A fresh140:104 composition case passed1/1; the full rendered screenshot was inspected and confirms
borderless option/Create presentation while retaining supported search/archive controls. Complete
source is cached in `workspace-popup-source-2026-10-10/140-104.md`. Independent bounded Spec and
Quality re-review approved this correction with no remaining finding.

The fresh read-only completion audit found no additional missing functional action in its inspected
scope, but does not establish global visual parity or final integration acceptance. The remaining
source/implementation differences and verification gaps require evidence against the original
scope, rather than another claim based solely on passing focused tests.

## Oct10 Evaluation status and integrated regression

Fresh direct MCP216:810 defines the Unavailable badge foreground#784131, surface#F2E4DF,
12/16 semibold label and8px radius. The local unavailable badge now uses dedicated semantic
tokens rather than the generic warning mix. Desktop heading allocation365px and badge3px
top offset reproduce the source slot; the available branch is unchanged. The browser RED
caught the previous tone/position; GREEN passed2/2 with desktop/mobile Evaluation comparison.
Dark mode retains its existing warning palette as an adaptation without a supplied dark source.
Bounded independent review returned Spec compliant / Quality approved.

After all maintained frontend corrections in this working diff: format and format:check passed;
TypeScript passed; Vitest passed412/412 across45 files; the complete Figma fixture suite passed
117 cases with10 application-only skips. The sequential production build exited0. An earlier
build overlapped typecheck and failed on a generated Next type file; the sequential rerun is
the final build evidence. Existing Next image warnings remain. Ruff and OpenAPI check passed;
Compose validation exited0 with unset optional credential warnings.

The complete backend regression finished with1640 passed,16 skipped and28 warnings in271.76s,
exit0. It used the owned disposable regression PostgreSQL database on127.0.0.1:5544 and
deterministic-local provider, not retained Figma/daily databases. The16 skips remain explicit;
this run does not prove all live external-provider behavior. Docker Server29.7.2 was confirmed
available after the user's startup message.

## Oct10 current source comparison refresh

Created51 dated source/current pairs and seven overview sheets under
`.verification/figma/q1/evidence/source-review-2026-10-10/`, with original/current SHA256 values
and unchanged cached context hashes. Original comparisons, sources and manifest are preserved.
The refresh only crops the source's34px annotation strip for full screens; the10 compact
panel/response schematics retain their intrinsic geometry and do not define full-screen parity.

All seven overview sheets were inspected for composition. The AU1B246:404 generic info.ftl
capture was found to represent generic account completion rather than password-success login.
Its dated comparison now uses the existing Oct10 native password-updated login capture and
records that capture basis explicitly; the old generic fixture remains available. Individual
AU1B comparison inspection confirms the real sign-in form, green notice and secondary links;
native focus styling and typography/color differences remain visible. This corrects evidence
mapping, not product behavior. Detailed per-screen disposition and independent whole-frame
acceptance remain open; the dated manifest deliberately retains pending review status.

No scope was deferred, no code/test was removed, and no integration action was performed.
Provider-cookie SSO completion and natural browser-session expiry remain verification gaps.

## Oct10 registration same-form recovery — edge70

The existing native confirmation/password-policy rejection case now corrects and submits the
same rejected form. It verifies the browser's owned Workspace URL against the real resolver's
ACTIVE/My Workspace result and captures `edge-70-corrected-registration.png` in the existing
password-event identity evidence directory. The focused native Chromium case passed1/1 in12.4s
against the running isolated Figma graph. No product behavior or provider policy changed.
Format and format:check passed. This replaces the ledger's stale fixture-only/conditional
registration statements while preserving the approved backend-owned fresh-account destination.

Post-change TypeScript and diff checks passed. The resulting desktop capture was inspected:
it proves the existing WorkspaceHome landing, not the Conversation empty-state composition.
WorkspaceHome still renders its legacy management links/New Conversation presentation. The
remaining full-flow audit must reconcile this intermediate landing with the approved U1/U2
source mapping; this runtime capture does not accept that page as Figma visual parity.

## Oct10 Workspace landing presentation and session verification

The approved U1 WorkspaceHome intermediate route now uses shared heading/body tokens, spaced
semantic navigation links and the maintained Button. Restore, Conversation creation/idempotency,
capabilities, ToolLifecycleDisplay and destination routes are unchanged. It has no separate source
frame; this is a shared-system adaptation, not exact Figma-frame acceptance. Thirty relevant
Workspace/user-page/server-rendering tests passed, and the current native edge70 capture was
inspected after this presentation change.

### Provider-cookie completion

The new provider-sso variation of the existing native UPDATE_PASSWORD email-action journey proves
that the issued Keycloak cookies authenticate the same synthetic user in a separate context before
password update. They are transferred before completion, and an actual request-event observation
confirms KEYCLOAK_IDENTITY is sent on the fresh provider prompt=login request. The password form
is visible and empty, the Password updated notice is visible, BFF session remains null, and
state/nonce/PKCE differ from the previous transaction. Keycloak recognizes the username and hides
its editable field in this SSO case; that provider-owned form variant is retained.

The first diagnostic used route interception, which does not intercept the redirect destination;
request-event observation corrected that instrumentation. The next failure was an incorrect
always-visible username expectation. No production authentication logic was changed. The test
does not independently establish post-reset provider-cookie validity or OTP challenge coverage.
It provides the bounded I3 fresh-sign-in evidence for the native password-completion event.
Cookie values, tokens and complete action URLs are not written to diagnostic artifacts.

Evidence is `provider-sso-password-success.{png,json}` and safe boundary diagnostics in the
existing password-event-identity directory. The complete current native identity suite passed
14/14 in37.6s after the sanitizing review correction, including same-form edge70 recovery.

### Real-time bounded BFF session expiry

The new live Conversation case starts with real native authentication and retained answered/refused
history. It preserves the authenticated identity, capabilities and native tokens, while shortening
only the signed isolated BFF absolute deadline/JWE expiry to4s. The browser cookie retains its
longer lifetime; actual wall time is awaited with no clock mock or intercepted API response.
Submission then returns real401, disables further submission and preserves the draft. A new-tab
native SSO login restores the same identity; Reload history retains the draft, re-enables retry,
and returns HTTP200 history exactly equal to the pre-expiry HTTP200 answered-history response.
No retry submission or backend mutation is performed. Captures before/after recovery were inspected.

Final sanitized/assertion-strengthened case passed1/1 in19.2s. Evidence lives in
`.verification/figma/q1/evidence/session-expiry-2026-10-10/`. This covers browser interaction with
real elapsed BFF expiry under a shortened fixture lifetime. It does not measure default TTL,
provider refresh-token expiry, or successful retry submission; those are not implied by the result.

Independent bounded review returned Spec Pass / Quality Pass, resolving a P2 that native failure
logs could expose full action/callback URLs. Native completion, registration recovery and expiry
now clear owned page contexts and throw fixed errors without preserving the original failure/cause.
The review's history-response strengthening was applied and freshly verified.
Final format/check, TypeScript and diff checks passed. Sequential production build exited0 with
existing Next image warnings. Earlier backend,412-component and117-fixture evidence remains scoped
to its recorded checkpoint; these local changes are additionally supported by the results above.

### New observed composition defect to fix next

Inspection of the real expiry screenshots found that a populated Conversation rail can overflow
its list and overlap Load more/View archived/Collapse controls. Current ConversationList has a
min-height0 flex list with no bounded internal scrolling, allowing children to paint over footer
controls. This is an implementation defect under U3 panel/rail behavior, not deployment hardening
or a new deferral. Reproduce with a stable long-list browser fixture, correct scroll containment,
and verify footer/menu/keyboard usability while preserving short-list source geometry.

## Oct10 Conversation rail overflow resolution

The preceding observed U3 defect is now resolved locally. The rail-only list root has bounded
vertical scrolling and non-shrinking direct children. The mobile Conversation drawer uses explicit
flex header/body containment; generic Dialog and ordinary management-list presentation retain their
existing behavior. Desktop RED evidence records the previous visible overflow. The first mobile
check exposed an additional unbounded Dialog body, corrected by the drawer-specific rules.

Independent review identified a second concrete defect: the absolute 208px Actions menu could be
clipped horizontally at the approved 200px rail minimum, and below the last row. A browser left-edge
hit test reproduced the clipping. A CSS-only containment attempt failed collapsed sizing and lower
menu accessibility and was replaced. Menu now accepts an optional explicit ancestor boundary;
the rail opts in, and layout placement clamps width and chooses/clamps vertical position before
keyboard focus. Other Menu callers retain their existing placement. This is a required usability
correction within the approved scope, not deployment hardening or a new deferral.

The final browser regression uses contract-shaped 20+10 cursor pages, actually clicks Load more,
and covers default expanded, minimum 200px, collapsed and mobile390x844 rails. It checks bounded
scrolling, footer pointer accessibility, loaded last-row reachability/focus, both Rename/Archive
left-edge hit targets, Escape focus return, mobile outer containment/close focus return, no page
horizontal overflow and no unexpected fixture API writes. All four cases passed in15.2s.
Evidence, menu captures and retained RED artifacts are under
`.verification/figma/q1/evidence/rail-overflow-2026-10-10/`.

The final minimum-width and mobile open-menu captures were individually inspected. Five historical
short-list captures were preserved in `short-list-before/`; comparison differences are confined to
New/Search border rasterization, not layout. In128:110 only32 pixels changed, with bounding box
(16,148,235,227); the original/current whole capture and enlarged control crops were inspected.
The images are not byte-identical, and this bounded comparison is not whole-design acceptance.

The relevant Menu/primitives/Conversation tests passed97/97 across five files. Format followed by
format:check and TypeScript passed. Independent re-review returned Spec Pass / Quality Pass with
no remaining actionable finding in this scope. The Docker engine was confirmed29.7.2; isolated
services remained on their existing ports. The native real-time bounded session-expiry journey
was rerun after the correction and passed1/1 in22.3s, retaining the same shortened-lifetime,
history/draft and no-retry-submission qualifications recorded above. Its current expired-draft
capture was inspected and the footer no longer overlaps the long list.

The final post-review production build finished with exit0 at11:34:12+07; the complete fixture
suite finished with121 passed and10 application-only skips in1.7m, exit0 at11:35:25+07.
Durable logs/results use `build-reviewed*` and `full-fixture-reviewed*` in the rail evidence folder.
Existing Next image and environment color warnings remain; the10 skips are not application proofs.
Detailed51 source dispositions, remaining89-transition reconciliation and
integrated final acceptance remain open. Existing approved Issues#149–#152 remain the deferred-work
record; no additional scope was deferred, no valuable code/test was removed, and no branch was
pushed, merged, removed or deployed.

## Oct10 final composition corrections and owner-requested white actions

This later checkpoint supersedes the preceding blanket “51 source dispositions pending” statement.
It preserves the original41screens,10compact references and89classified transitions. No new scope
was deferred. Completion of the full goal remains subject to the final controller audit.

### Implemented corrections

- Workspace154:134 Archive popup was clipped by the outer rail column. Only the outer column now
  permits overflow; the inner Conversation list owns scrolling and the page boundary remains
  contained. Browser RED reproduced inaccessible menu edges at252/200px; both GREEN cases open
  the actual confirmation, cancel and return focus. The combined six rail/menu cases passed.
- Archived Workspace154:431/166:211/166:290 content origin now matches x120,y108,width1200.
  Empty/search-empty states use the source655px area. Workspace unavailable183:490 uses its
  centered640×330block atx400,y279. The236×40CTA keeps a complete single-line label; initial
  wrapping was caught and corrected. Desktop/mobile journeys and source captures passed.
- Compact4:35/4:67/4:99 fixtures now select actual citation1 before applying panel preferences,
  resolving the unintended unselected Inspector reference. Product selection logic is unchanged.
- Auth228:293/228:326 cue backgrounds used undefined action-soft/signature-soft tokens. Light
  now uses exact source#E6F5EB/#F4EAE6; explicit/system dark uses the retained native palette.
  Browser RED reproduced transparency; both states/theme pairs and their source captures passed.
  Foreground contrast for these three tinted cues remains4.5:1 or better.
- The owner then identified source-white controls rendered near-black. Direct Figma MCP183:540
  confirms white text on the green236×40CTA; cached complete source54:193/61:197 and Workspace,
  Conversation and identity button structures establish the same solid-action role. Shared
  action-foreground is white in light/explicit/system dark; generic native primary is white,
  matching existing native auth-specific controls. Upload, upload confirm, Create workspace,
  solid New Conversation, Send and auth retry/sign-in actions now inherit the correct foreground.
  The Workspace unavailable link also uses this common role. Secondary, outlined, tinted and
  text controls retain their own semantics. No handler, permission or credential rule changed.
  Source green backgrounds remain; the owner-requested primary foreground exception is explicitly
  documented without asserting4.5:1 small-text contrast. All other contrast gates remain.

### Verification additions and provenance

Six added Conversation component cases exercise the existing real Retry handler: still-interrupted
history restores the exact question/focus without aPOST; latest queued/processing/answered/refused
history preserves another draft; the actual refusal follow-up edits/focuses the composer without
submission. The file passed27/27. No production Retry behavior changed.

Seventeen prototype ledger rows were reconciled with current evidence:7,18,30,38,40,42,43,45,
47,48,49,50,51,81,85,87,88. Source/trigger/classification remain unchanged. Their qualifications
separate shared-handler component proofs from actual origin-specific live journeys; successful
creation is not claimed from intentional503 component cases. QueuedPDF→guarded worker→Ready,
authoritative Retry and refusal editing, native provider-cookie/fresh login and bounded real-clock
BFF expiry evidence are stated explicitly. Physical deletion remains#150. A read-only transition
review found no missing Conversation/Documents handler; this is not89independent live cases.

The pre-white-action checkpoint passed418/418Vitest,127fixture cases with10application-only skips,
and production build. Logs/results are under `workspace-state-origin-2026-10-10/`; those historical
results precede the subsequent soft-token/white-foreground corrections and are not represented as
verification of later source.

The actual-browser action-color RED reproduced near-black Upload document, Create workspace and
Try again. After the shared correction, the full fixture suite passed129 with10application-only
skips in2.1m. All51source cases audit visible solid action computed foregrounds and representative
presence. Five further dark/reduced-motion cases passed9.9s, checking enabled primary white text
in explicit/system dark, default and hover. Complete current Vitest passed418/418 across45files;
format→format:check and TypeScript passed. Durable fixture/dark/build logs use
`.verification/figma/q1/evidence/solid-action-colors-2026-10-10-*.log`.
The current production build then completed with exit0; existing Next image warnings remain.

### Independent review and current classification

The source reviewer individually inspected all51comparisons, then re-reviewed all four corrected
auth cue GREEN captures and refreshed183:490/128:120/148:116/228:293 white-action captures.
No remaining actionable finding was reported. Detailed per-node dispositions are maintained in
`figma-ui-visual-coverage.md`; source/current hashes and native246:404capture basis are retained
in the refreshed dated comparison manifest. “Retained” accepts stated composition/adaptations,
not exact pixel identity or backend operation proof.

The integrated read-only reviewer returned Spec Pass / Quality Pass for the implemented bounded
scope, finding no important product/security blocker. It relied on the separate individual source
review and required reconciliation of stale tracked acceptance statements. This appendix and the
current coverage checkpoint resolve that documentary inconsistency; the final controller audit
still owns whole-goal completion.

| Category | Current state |
| --- | --- |
| Not implemented | No additional missing Figma handler identified by current Conversation/Documents audit; approved physical deletion processing remains#150. |
| Implemented, verification or acceptance remaining | Controller requirement-by-requirement completion audit and final review of reconciled records remain. Component/shared-path evidence is qualified per transition instead of silently asserting live origin coverage. |
| Approved production/future work | #151supplied mobile/dark references and#152OTP deployment hardening remain;#149Documents live evidence is locally resolved, awaiting integration. Native default-TTL/provider-expiry and post-update SSO-cookie validity are outside the bounded evidence. |

GitHub Issues149–152 were checked again; all remain open, and no open PR exists. No duplicate
backlog item was created. Useful code/tests and retained evidence remain. No push, merge,
deployment, retained data reset or branch/worktree deletion was performed.

## Oct10 production runtime and final evidence reconciliation

Current working source retains every earlier implementation and useful test. This checkpoint
supersedes historical missing-path and fixture-only composer-focus statements; it does not yet
declare the full objective complete or authorize integration.

- Edge33 now clicks the actual Question input at1440/390, confirms focus, an empty draft and
  disabled Ask, with no unexpected request. The existing suggestion/archive test passed1 case
  covering both widths in9.0s. Initial failure used the wrong test accessible name; the corrected
  name is Ask. No product behavior was changed for this check.
- Production-build verification ran the compiled Next application on the guarded Figma endpoints.
  Documents navigation and AU3/AU4 outcomes passed2/2 in7.9s. The Documents journey created an
  owned Workspace, uploaded a source, verified Ready, archived/restored with revisions1→2→3,
  followed row-menu/detail/back-filter links, and verified deletion202 with the actual blocked
  projection. Source/document-version identity remained stable. Physical deletion remains#150.
- The first production run diagnosed APIRequestContext401 versus actual browser fetch200 with
  a Secure, HttpOnly, SameSite=Lax session cookie. Projection assertions now read through browser
  fetch with same-origin credentials; production cookie/auth settings are unchanged. Temporary
  diagnostic source was removed; diagnostic JSON and failed/green logs are retained.
- Fresh full pytest completed1640passed,16skipped,28warnings in336.00s, exit0, against only the
  owned disposable regression PostgreSQL5544. Durable log and result JSON are in
  `.verification/figma/q1/evidence/completion-audit-2026-10-10/`.
- The ledger now uses the approved owners U1Workspace/U2Documents/U3Conversation/O1Operator.
  Ten incomplete evidence paths were repaired. All51reference rows,89unique transition rows
  and159named artifacts exist; all16production asset entries are nonempty and match manifest
  SHA256. `coverage-artifact-audit.json` records the checks. Presence/checksum alone does not
  establish operation, geometry or authority; the qualified row evidence remains controlling.
- A fresh white-action visual run passed79/80 cases, including all dark/hover cases. One archived
  no-results fixture timed out before color evaluation; its focused rerun passed1/1 in9.2s.
  This is recorded as a first-run timeout followed by a passing rerun, not an80/80 clean run.
  Fresh token tests passed10/10 and formatting check passed.

Production evidence: `.verification/figma/q1/evidence/production-smoke-2026-10-10/`, including
`green-run.log`, `request-context-diagnostic.json`, `document-journey-green/journey.json` and native
outcome captures. Composer evidence: `composer-focus-2026-10-10/{1440,390}.png` and its green log.

The read-only reviewer returned Spec Pass / Quality Pass for the latest test-client, composer and
ledger corrections, with no important implementation or verification blocker. Its minor owner
legend inconsistency was corrected. The controller's requirement-by-requirement audit and final
integration choice remain distinct from this evidence checkpoint. No new work was deferred.

## Oct10 real interruption proof and distinct outcome correction

Final checklist review identified Q1's missing live authoritative interruption/Retry journey.
A fresh uniquely named owned Workspace/Conversation was created through the authenticated BFF,
and an actual queued Turn was submitted. The controller validated the exact isolated PostgreSQL
project/service/loopback5543, fresh admission UUIDs/name/age, then claimed only that Workspace's
new Turn. After the real60second PostgreSQL lease expired, the production fenced recovery seam
committed interrupted/EXECUTION_OUTCOME_UNKNOWN with null result. No direct SQL status override,
mocked API projection, daily service stop or retained historical Turn change occurred.

The first browser journey passed1/1, demonstrating real interruption, history reconciliation,
Retry restoring/focusing the exact draft without POST and explicit Ask202 admitting a distinct
queued Turn while retaining interrupted history. Visual inspection then found interrupted also
rendered System error: TurnCard treated every error_code as failed despite interrupted status.
A paired actual-error-code regression reproduced this defect (interrupted RED, failed control
passed). The minimal correction gives interrupted precedence; genuine failed retains System error.
The complete ConversationView file passed29/29 and full Vitest420/420 across45files. Fixtures now
carry the actual interruption failure stage/error code. Format/check/typecheck passed.

An overlapping broad Vitest run called Next build while the browser used Next dev, producing
missing routes-manifest errors and a browser timeout despite committed recovery. That failed
browser log and controller JSON remain; they are not a product pass. A subsequent sequential
production build passed, and the strengthened browser test is being rerun without overlapping
builds. The initial proof/captures are preserved in live-interruption-first-proof-2026-10-10.
The distinct-outcome fix received independent Spec Pass / Quality Pass, no important finding.
Final green live and affected source checks remain pending at this checkpoint.

## Oct10 follow-up evidence reconciliation

The preceding pending statement is superseded by the retained sequential run in
`.verification/figma/q1/evidence/live-interruption-2026-10-10/`:
`browser-after-build.log` reports **1 passed (2.1m)**; `controller-after-build.log`
confirms actual lease-expiry recovery. The matching Workspace and Turn IDs in
`controller.json` and `journey.json` establish an interrupted Turn, Retry without
a POST, a distinct explicitly submitted Turn returning 202, and retained history.
No additional live interruption run was needed for this documentation correction.

The owner-requested button foreground follow-up was checked with
`FIGMA_TEST_MODE=fixture npx playwright test tests/e2e/figma-ui-visual.spec.ts
--config=playwright.figma.config.ts` from `frontend`: **80 passed (59.5s)**,
including all 51 source fixtures, 24 responsive cases and 5 dark/reduced-motion
cases. Source fixtures assert computed white foreground on visible solid action
controls. Token tests passed **10/10**; format, format:check and diff check passed.
An earlier incorrectly invoked npm-exec command omitted the Playwright configuration
and failed all 80 cases before presentation checks with invalid relative URLs;
that invocation is not product evidence. A redundant CSS fallback and its structural
test introduced during this follow-up were removed; the existing shared token fix
and useful browser assertions remain the implementation.

The whole-goal audit and final source/integration disposition remain open. These
results establish the named journeys and presentation checks, not deployment.
