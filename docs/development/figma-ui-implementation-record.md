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
- Native OTP reset flow is unbound. Real email→OTP→password update, replay/concurrency in the native
  flow, stable Vault restart/rotation, enrolled MFA, CSP/browser behavior and completion/SSO gates
  remain unproved. Physical database outage was rejected by automatic tool approval review; an
  equivalent workaround is prohibited. See [Keycloak theme](keycloak-theme.md).
- Live logout, expired-session journeys and remaining real-flow regression evidence are incomplete.
  Source/template/fixture tests cannot establish those service behaviors.
- Full Q2 and final whole-branch review remain outstanding. Main integration requires the Frontend
  formatting workflow's passing Prettier status; no integration action is authorized by this record.

Keep the goal active until the original requirements and their authoritative evidence are complete.

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
at390px and1440px after the fix. This resolves the recorded adaptation defect only and does
not change the still-open native OTP, parity or transition gates.
OTP binding and the rejected physical outage proof remain held; equivalent workarounds
are prohibited. Keep the goal active.
