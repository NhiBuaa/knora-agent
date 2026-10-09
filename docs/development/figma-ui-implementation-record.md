# Figma UI implementation record — partial

Updated October 8, 2026. The approved objective remains implementation of the complete Figma
design. This is a continuity and evidence record, not Q1/Q2 or full-product acceptance.

## Current integration

Worktree: `C:/Developer/Projects/knora-agent-worktree/figma-ui-identity`.
Branch: `codex/figma-ui-identity`. Latest independently reviewed source slice: OTP presentation `5583df8`.
Evaluation, Operations, shared Operator frame and Trace flow are independently approved.
No merge, push, deployment, branch disposition or worktree removal has occurred.

The stack includes Next.js15.5.24, React18.3.1, TypeScript and Tailwind CSS v4, with local fonts,
semantic tokens, Vitest and Playwright. Canonical backend and Keycloak ownership remain binding.
The approved workflow's folder responsibilities are in
[the directory analysis](../superpowers/plans/2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).

## Recent completed source slices

Each source slice below received separate independent spec and quality approval. This records
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

Fresh five Operator contexts were read directly through Figma MCP. Their complete structures,
uncropped whole-frame screenshots and measurements are cached under
`.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/`. Source frames are1440×960;
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
`.superpowers/figma/q1/evidence/regression-preflight/`; owning task reports/reviews are retained
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

- Operator label typography, Trace badges and relative Trace content measures are independently
  approved. Evaluation content measures and Operations accounting/bucket/Alerts measures are also
  independently approved. Page coordinates, natural row growth, theme differences and supported extra
  controls remain explicitly measured. Comparison test success does not imply whole-page parity.
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
completion and fresh login. Transitions 73, 75, 77, 80 and 82 remain unproved and are not
marked complete. The completion capture was inspected against direct MCP source; its notice and
native login composition differs from Figma node `250:841`, so completion parity remains open.

The consumed-replay oracle was verified against the native result: a second submission of the
prior verification action returns HTTP 400 HTML with the native `#kc-error-message` page-expired
marker, no redirect, and no OTP, login, or password form. Storage/service consume evidence
remains the authoritative challenge-consumption proof.

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
New captures use `.superpowers/figma/q1/evidence/operator-tab-journeys-2026-10-08/`;
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
the 14 captures in `.superpowers/figma/q1/evidence/operator-tab-journeys-2026-10-08/`.

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
`.superpowers/figma/q1/evidence/conversation-navigation-2026-10-09/`; the owning test is
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
