# Q1 review correction — round 1

2026-10-07. Review findings: `task-1-review.md`, two Important test-contract issues.
Fix base `3d91aa5`; controller amendment `d0b1c61` additionally approved the existing Figma
config selection and `figma-environment.test.ts` guard regression. Ready for independent
review of these corrections. **Full Q1 remains partial**; this round does not accept source
parity or native recovery gates.

## Corrections

1. The existing M5 persisted-refusal case now projects public `REFUSAL` and
   `INSUFFICIENT_EVIDENCE`, with null answer and empty citations. It verifies both current
   refusal headings, zero actual `Citation N:` buttons, and exactly one response paragraph
   containing the refusal reason. An erroneously rendered answer paragraph fails the assertion.
   The old region query was removed from this case because the current citation renderer is
   a labelled div with buttons, not a region. Other M5 cases were not changed.
2. The Q1 PDF observation uses generated `IngestionJobStatusResponse`. The shared test-only
   classifier accepts exactly queued, processing, retry_scheduled, succeeded, superseded and
   failed. The first three are pending; the last three terminal. Terminal classification does
   not equate superseded/failed to successful ingestion. A generated-shape fixture verifies
   all six statuses, specifically retry and superseded, and rejects runtime `retry_wait`.
   The live observation path uses the same classifier. No new PDF upload/worker run occurred.

## Guarded focused execution

The daily M5 runner and endpoints remain unchanged. Existing Figma config supports only explicit
`FIGMA_TEST_MODE=application` plus `FIGMA_TEST_CASE=m5-refusal` for this adjacent regression.
Selection is limited to `m5-user-flows.spec.ts` and the exact persisted-refusal title. Unknown
selection or incompatible/unknown mode throws. The anchored title handles Playwright's filename
prefix and cannot select another M5 case. Default identity/fixture/application selections remain
unchanged. Fixed Figma endpoint derivation and ambient override rejection remain active.

Only the selected refusal case uses existing `openFigmaLogin`, its read-only service ownership
check, and versioned owned test identity. Default `loginAs` remains unchanged. After the real
resolver reaches Workspace home, the case opens its actual Conversations link and New
Conversation control. The result itself is explicitly an intercepted projection, not a real
backend refusal outcome. Previously recorded actual refusal evidence is unchanged.

## RED/GREEN and final verification

| Command / selection | Observed result |
| --- | --- |
| Fixture Q1 Playwright, grep `PDF observation classifies` | RED rejected valid retry_scheduled against prior allowlist. GREEN: 1 passed in 3.9s; all six classifications plus invalid legacy rejection, no browser/data request. |
| `npm --prefix frontend run test -- tests/e2e/support/figma-environment.test.ts` | Selection RED: 1 failed/3 passed because explicit selector seam absent; implementation GREEN: 4 passed. |
| Application Figma config, exact M5 refusal selection | First diagnostic timed out on test navigation/name mismatch before refusal; it is a harness failure, not contract RED. After current route/name correction, old REFUSE double RED: missing Refused text, 1 failed in 14.2s. Canonical double GREEN: 1 passed in 20.3s. |
| Same exact M5 case after replacing the vacuous region check | Final 1 passed in 15.1s (handle 98430); current headings, actual citation-button absence and no answer paragraph verified. |
| `npm --prefix frontend run test -- tests/e2e/support/figma-environment.test.ts tests/e2e/support/environment.test.ts tests/e2e/support/playwright-config.test.ts` | 3 files/11 tests passed in 1.84s. Includes new selection guard and existing default M5 endpoint/override guards. |
| `npm --prefix frontend run format`, then `npm --prefix frontend run format:check` | Both exit 0; all matched files use Prettier style. |
| `npm --prefix frontend run typecheck` | Exit 0. |
| `git diff --check` | Exit 0. |

Focused commands:

```powershell
$env:FIGMA_TEST_MODE='fixture'
npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts figma-ui-interactions.spec.ts --grep 'PDF observation classifies'

$env:FIGMA_TEST_MODE='application'
$env:FIGMA_TEST_CASE='m5-refusal'
npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts m5-user-flows.spec.ts
```

NO_COLOR/FORCE_COLOR warnings were retained. No native credential/action URL/token/code log,
automatic trace/video/screenshot or source recapture was produced. Original 51 comparisons and
80 durable visual captures remain unchanged. No production/backend/generated contract files,
service/realm/worker configuration, passwords, deletion requests or new PDF writes changed.
Owned synthetic Conversations created by the focused regression remain retained.

Self-review confirmed four exact maintained test/config paths, canonical literals, shared PDF
classifier, narrow opt-in selector, default guards and current semantic assertions. Preview
processes exited; final 3300 listener check returned zero and the owner releases the lease.
Native reset/Vault/MFA/outage/CSP, missing five prototype references, citation toggle/archived
Workspace affordance and other previously documented parity gaps remain unresolved.
