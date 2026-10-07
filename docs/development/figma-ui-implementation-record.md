# Figma UI implementation record — partial

Updated October 8, 2026. The approved objective remains implementation of the complete Figma
design. This is a continuity and evidence record, not Q1/Q2 or full-product acceptance.

## Current integration

Worktree: `C:/Developer/Projects/knora-agent-worktree/figma-ui-identity`.
Branch: `codex/figma-ui-identity`. Latest independently reviewed source slice: Evaluation `6ff260d`.
Operations content measures are executing from original BASE `6ff260d` after Evaluation review.
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

## Remaining acceptance work

### October 8 frontend qualification

Fresh whole-frontend verification ran against source `81ff9e9`, including the independently
approved typography, Trace and Evaluation follow-ups and the Operations task awaiting review.
Vitest passed 366 tests across 44 files in49.76s, exit0. Production build first failed after
compile/type checking/static generation at an ENOENT rename of generated `500.html`; the
destination file already existed after failure. A sequential build with no source changes or
cache cleanup passed, exit0. The precise cause of that intermittent generated-output failure
is unconfirmed. Existing Next image lint warnings remain visible; no source waiver was added.
Both build logs, diagnosis and exit records are retained in the excluded `regression-preflight`
directory. This fresh frontend evidence does not qualify native identity or replace the earlier
backend/Maven acceptance limits.

- Operator label typography, Trace badges and relative Trace content measures are independently
  approved. Evaluation content measures are independently approved; Operations accounting/bucket/Alerts
  measures are executing. Page coordinates, natural row growth, theme differences and supported extra
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
