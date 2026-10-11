# Task 1 — Conversation parity follow-up

2026-10-07. **Ready for independent spec and quality review.** Original BASE
`788ab0cd9c6a26362c0adffdcc1f3abeee5d7d45`
includes the approved plan; controller amendments `dfa7911` and `b2b2fc6` extended exact route,
Hub and existing consumer-test scope. This implements the two requested behaviors, not full
Q1/Q2 or full Figma acceptance. Prior native gates and unrelated visual deviations remain open.

## Source and implementation

Read the owning brief, plan constraints/interfaces, progress, approved integration spec and
the cached high-fidelity structures for 183:176 and the edge44 selected/default states
(128:115/128:110). The foundations source index and original MCP/PNG files were not changed.
The Workspace source specifies a 72px bottom bar, exact archived/helper wording and a 184×40
desktop Restore workspace action; no new static image/icon asset is required in this slot.

- Citation selection uses a functional update comparing **Turn ID and citation index**. The
  same selection clears pressed state and the selected inspector; another Turn/index selects
  that Turn's original citation array. Missing citations clear after history reload. Panel
  preferences, unrelated panels and historical source/version/provenance remain unchanged.
- The existing Composer file exports a shared `WorkspaceReadOnlyComposer`, consumed by the
  detail View and list Hub. This avoids duplicated restore authority and circular View/Hub
  imports or a new general API/state module. Both server routes pass `workspace.revision`
  from their already-authorized backend projection. Optional props preserve other callers.
- Missing, negative or non-integer revision disables restore. A validated **zero** revision is
  valid, matching the existing HTTP `required_revision` contract; no invented positive-only
  rule is imposed. The UI cannot create revision authority from browser preferences.
- The bottom control sends public Workspace restore with encoded ID and `If-Match`, validates
  returned Workspace ID/archive state/new revision, then consumes unchanged
  `resolveWorkspaceAfterMutation(workspaceId)` for backend resolution and signed preference.
  Navigation occurs only after that flow succeeds. The UI never locally unarchives the Workspace.
- Pending duplicate clicks are blocked. 401 invokes the detail View's existing session-expiry
  path and disables mutation; Hub also retains its own authentication-required state. 403,
  conflicts and invalid returned projections stay read-only with an error. Resolver failure
  after validated success says **Workspace restored. Reload to select an active Workspace.**
  It does not misreport that successful mutation as failed or enable the composer locally.
- Shared restore state is keyed by Workspace ID and validated revision. Unmount/session checks
  prevent late old-scope responses from navigating the current surface. Tests cover old Workspace
  and changed revision while a restore is pending.
- Workspace archive takes priority over Conversation archive in the bottom bar. Following an
  authoritative Workspace reload, a separately archived Conversation still has its distinct
  Restore conversation action and no Question composer until that restore succeeds.

The original prescribed auth integration test has no Conversation route composition. The
controller approved `conversation-page-workspace.test.tsx`, based on the existing document
route pattern, plus the actual list Hub seam in `ConversationPanels.tsx`. A later existing
ConversationView test needed only its Workspace-specific expectation and Next router mock;
the Conversation-only expectation remains intact. All changes stay within those exact scopes.

## RED/GREEN and final commands

Commands below ran from the identity worktree repository root. Focused failures were inspected;
no source baseline was accepted to make them pass.

| Verification | Observed result |
| --- | --- |
| `npm --prefix frontend run test -- tests/conversation-panels.test.tsx -t 'toggles the same'` | RED: 1 failed/20 skipped; repeated selection remained aria-pressed=true. Functional update GREEN. Existing narrow dismissal test initially expected the old repeat-to-reopen behavior; updated it to deselect first, then select again, retaining Escape focus return. |
| Same panel file, `-t 'restores the archived Workspace'` | RED: missing Archived workspace bar. Shared authoritative restore implementation GREEN, pending duplicate-click and revision/selection checks included. |
| `npm --prefix frontend run test -- tests/conversation-page-workspace.test.tsx` | RED: both routes rendered revision undefined (2 failed/4 passed); after server prop wiring, all 6 passed, including missing session/backend denial. |
| Three affected Conversation suites | Intermediate 58 passed after the narrowly approved existing consumer/router correction. Initial missing Next router context and obsolete Workspace read-only wording were test-harness failures, not backend failures. |
| `npm --prefix frontend run test -- tests/conversation-panels.test.tsx tests/conversation-page-workspace.test.tsx tests/conversation-view.test.tsx tests/e2e/support/figma-source-inventory.test.ts` | Final 4 files/68 tests passed in 3.36s. Covers mouse/Enter/Space, another Turn and another citation, stale history reset, missing/zero/invalid revision, pending, 401/403/409/412, invalid scope/state/revision, resolver recovery, both archived states, old scope/revision and default consumers. |
| Fixture Playwright focused new interactions | Initial 4 passed in 11.0s: toggle, narrow modal/focus and bottom restore at 1440/390. |
| Fixture Playwright affected interaction + visual selection | Final 6 passed in 16.2s (handle 77691). Two A7/W5A source captures and four affected interactions only; no full80 repeat. |
| Guarded application Playwright, grep `owned Workspace restores` | 1 passed in 17.4s (handle 45240). Actual Workspace archive/restore and separately archived Conversation retention. |
| `npm --prefix frontend run format` → `npm --prefix frontend run format:check` → `npm --prefix frontend run typecheck` | All exit 0; final matched files use Prettier style. |
| `npm --prefix frontend run build` | Final exit 0 (handle 65731); 18 static pages, existing no-img-element warnings retained. An earlier build passed before nonnegative-revision self-review correction; final build includes it. |
| Bundled Pillow affected comparison refresh | Two pairs/two sheets refreshed; all 51 actual capture hashes match the current manifest. |
| `git diff --check` and `git diff --cached --check` | Both exit 0; staged scope contains exactly the 13 approved source/test/coverage/report files. |

Focused Playwright invocations:

```powershell
$env:FIGMA_TEST_MODE='fixture'
npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts figma-ui-visual.spec.ts figma-ui-interactions.spec.ts --grep 'source fixture (128:115|183:176)|citation selection toggles|archived Workspace bottom|narrow evidence'

$env:FIGMA_TEST_MODE='application'
npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts figma-ui-interactions.spec.ts --grep 'owned Workspace restores'
```

Existing guarded fixed endpoints and read-only service ownership checks were used. No ambient
endpoint override, production fixture route, service/realm/schema/provider/generated contract,
worker, deletion, password or recovery change occurred. The live journey submitted no Document
or Question. The test-only restore interception applies only to the W5A state and its exact
Workspace restore/resolver/preference POST paths; unknown fixture requests still fail closed.
Fixture status is never described as backend authorization or a native restore outcome.

## Actual live outcome and retained data

One new owned synthetic Workspace and two Conversations were created through their public
backend APIs. One Conversation was archived with its returned revision. The Workspace was
archived through the actual Conversation rail UI and restored by keyboard from the bottom
Workspace CTA while viewing the separately archived Conversation.

The actual Workspace archive projection had revision **1**; restore returned **200**, archived
false and revision **2**, using `If-Match: 1`. Signed preference returned 200; the resolver-selected
destination was that Workspace's home. Subsequent actual UI and GET confirmed the second
Conversation was still archived/read-only, while the active Conversation showed its Question
composer. No second Conversation restore was submitted in the live journey. Unit evidence
separately proves its distinct restore sequencing. All synthetic data remains retained.

Safe IDs/revisions are in ignored `parity-live-restore.json`; no account details, credentials,
authentication code/token/action URLs were printed or stored in the report. Automatic
trace/video/native snapshots remain off; explicit app screenshots use the existing capture helper.
NO_COLOR/FORCE_COLOR and existing build image warnings are reported without suppressing gates.

## Captures and source comparison

All artifacts below are under ignored `.verification/figma/q1/evidence/`:

- Current A7: `128-115-1440x960.png`, `128-115-comparison.png`.
- Toggle destination: `parity-citation-deselected.png`.
- Current W5A: `183-176-1440x960.png`, `183-176-comparison.png`.
- Desktop/mobile bottom control: `parity-workspace-1440.png`, `parity-workspace-390.png`.
- Actual live: `parity-live-workspace-archived.png`,
  `parity-live-conversation-still-archived.png`, `parity-live-workspace-restored.png`,
  `parity-live-restore.json`.
- Refreshed `conversations-source-review.png`, `workspaces-source-review.png` and
  `source-comparisons.json`; all other source captures and comparisons retained.

Desktop computed bounds prove **72px bar, 184×40 button** and exact source wording. The mobile
390×844 adaptation wraps its message/button into a 112px bar without page overflow or clipped
critical action. There is no mobile Figma geometry reference, so this is responsive usability
evidence. Mouse/keyboard toggle and focus return are asserted through actual components.
Viewed the current W5A side-by-side and mobile capture: the requested bottom slot now matches,
while the illustrative answer heading, second citation label, extra controls and missing inspector
read-only notice remain recorded differences. No new image asset was introduced or source static
asset changed. Original Figma PNG annotation is cropped only for comparison, never used as UI.

Coverage ledger updates only A7, W5A, edge44 and their stale remaining-gap/historical diagnosis
wording. Previous Q1 report stays historical. Full-screen/source parity is not inferred from
these two successful behavior corrections; descriptive RGB metrics are not acceptance thresholds.

## Self-review and handoff

Reviewed exact production component/route diffs, optional prop consumers, test-only fixture paths,
the new route regression, current coverage claims and durable artifact hashes. The server revision
is separate from Conversation revision; no local archive-state reset or substitute Conversation
POST exists in Workspace restoration. Shared state is scoped, duplicate submissions are blocked,
and recovery after a completed mutation remains explicit.

Preview processes exited after serial fixture/live runs. Final port 3300 listener check returned
none; the owner releases the lease. Existing owned services and retained data remain untouched.
Independent review should use original BASE `788ab0c` through this scoped commit and provide
separate spec/quality verdicts. This task awaits that review; no integration action is performed.
Native recovery/Vault/MFA/CSP/outage, five unavailable Operator prototype references, unexercised
edges, real browser zoom/full contrast and unrelated visual differences remain required work.
