# Task 1 — Archived Workspace evidence notice

2026-10-07. Ready for independent spec and quality review. Original BASE:
`f4ed4e33cd95da656951e64f2dd5ac43d5c4a98b`. The controller's later documentation
commit `f23fe9b` is included in the BASE→HEAD history but does not change this task's scope.
This implements the missing W5A notice only; full Q1/Q2 and native identity acceptance remain open.

## Source, scope and implementation

Read the owning plan's global constraints/directory interfaces, brief and progress. Used the
executing-plans, test-driven-development, Figma design-to-code, systematic-debugging and
verification-before-completion workflows. The full cached MCP structure at foundations
`.verification/figma/2026-10-05/workspaces/183-176.md`, node183:304, specifies:

- `READ-ONLY WORKSPACE`.
- `Workspace archived. Restore it to ask new questions or make changes.`
- Surface-subtle card with border, 340×82 desktop dimensions, horizontal14/vertical13 padding,
  8px radius/gap, 10px semibold muted heading and 13px body with 20px line height.

No static asset exists in this notice. Original MCP structures, source PNGs and source index
remain unchanged. Existing semantic surface/border/text tokens and actual local fonts are used.

The actual EvidenceInspector receives an optional `workspaceArchived=false`. Detail View and
list Hub pass their existing server-derived archive boolean; no browser preference, Turn outcome
or Conversation archive state authorizes the notice. The new card follows existing source context
and provenance. It does not replace evidence, disable Open document, change any citation label or
add a restore control. Default consumers retain their existing appearance. No route/backend,
API-client/generated contract, identity, service, worker or deletion change was made.

Existing W5A fixture already passes workspaceArchived to the actual View, so no fixture-support
edit or scope extension was necessary. Its unexpected-request guard remains unchanged.

## TDD and focused verification

All owner commands ran from `C:/Developer/Projects/knora-agent-worktree/figma-ui-identity`.

| Command/check | Actual result |
| --- | --- |
| Focused panel filter `Workspace notice` or `historical evidence without` (command below) | RED: 5 failed/41 skipped, each missing READ-ONLY WORKSPACE. After optional prop/card and View/Hub wiring: 5 passed/41 skipped. |
| `npm --prefix frontend run test -- tests/conversation-panels.test.tsx tests/conversation-view.test.tsx` | 2 files/62 passed in 2.64s (12:27:25), after required Hub test props were corrected. |
| Controller `npm --prefix frontend run test -- tests/conversation-panels.test.tsx`, handle82836 | Fresh current behavior assertions: 46/46 passed, exit0 in22.63s. Later change was notice responsive sizing only; final browser checks cover that sizing. |
| `npm --prefix frontend run format` → `npm --prefix frontend run format:check` → `npm --prefix frontend run typecheck` | Final sequential run exit0, all matched files use Prettier style. |
| Focused Playwright invocation below, handle9365 | Final 3/3 passed in30.6s, exit0: desktop/mobile notice interactions and W5A source capture only. |
| `npm --prefix frontend run build`, handle57255 | Final source build exit0; 18 static pages, existing no-img-element warnings retained. |
| Bundled Pillow W5A comparison refresh | W5A comparison/workspaces sheet refreshed; all51 current capture hashes match manifest. |
| `git diff --check` | Exit0. Exact staged scope reviewed before commit. |

```powershell
npm --prefix frontend run test -- tests/conversation-panels.test.tsx -t 'Workspace notice|historical evidence without'

$env:FIGMA_TEST_MODE='fixture'
Remove-Item Env:FIGMA_TEST_CASE -ErrorAction SilentlyContinue
npm --prefix frontend run test:e2e -- --config=playwright.figma.config.ts figma-ui-visual.spec.ts figma-ui-interactions.spec.ts --grep 'source fixture 183:176|archived Workspace evidence notice'

& C:/Users/NhiBuaa/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe .verification/figma/q1/refresh-refusal-comparisons.py
```

Unit assertions exercise actual inspector/View/Hub: selected historical excerpt, version, source
link and expanded evidence/source-key/checksum/offset provenance remain accessible. Active Workspace
and Conversation-only archive do not show the Workspace notice. Processing, interrupted and
canonical REFUSAL/INSUFFICIENT_EVIDENCE retain their own headings/content with no invented citation.
No new data mutation or live journey was needed for this presentation requirement.

## Diagnosed failures and responsive evidence

Initial typecheck caught missing required workspaceName/initialConversations in the new Hub test;
the fixture was corrected rather than changing the production interface. First browser run passed
mobile and W5A capture but found desktop width338 instead of source340. Existing inspector column
has a 1px border plus18px content padding, yielding338px automatic width. The notice alone now has
explicit340px width capped at available content+2px; existing inspector/layout code was not changed.

The subsequent run's desktop geometry passed but its new test incorrectly expected Escape to close
a non-modal desktop panel. Saved error-context proved only inactive citation focus. The test now
uses the existing desktop Close evidence control; mobile retains Escape/modal/focus return. These
test-harness failures are separate from the initial missing-notice production RED.

Final desktop assertions prove340×82, padding14/13, gap/radius8, surface-subtle RGB243/248/245,
exact notice copy, retained selected source and link. At390×844 the overlay fits without page
horizontal overflow, retains citation focus after Escape and allows natural card height above its
82px minimum. A positive doubled notice font/line-height check proves body remains within the card
and no card horizontal overflow. This is scoped enlarged-text evidence, not actual browser200% zoom
or full-page contrast acceptance. Desktop source height remains82; no mobile Figma reference exists.

## Captures, comparison and remaining differences

Ignored durable artifacts under `.verification/figma/q1/evidence/`:

- `archived-evidence-notice-1440.png`, `archived-evidence-notice-390.png`: selected historical source
  with the independent notice; explicit app captures only.
- `183-176-1440x960.png`, `183-176-comparison.png`: current W5A unselected source state.
- `workspaces-source-review.png`, `source-comparisons.json`: affected sheet/current hashes.

Viewed the current W5A side-by-side and mobile selected-source capture. Notice copy/card geometry
matches its requested slot. The preceding inspector context card remains taller than the source,
so notice vertical position differs; illustrated answer heading, citation labels and extra
accessible controls remain recorded differences. No illustrative content was fabricated. Updated
only W5A coverage and its stale missing-notice summary; prior task reports remain historical.
No completed80 repeat, live data mutation or screenshot baseline acceptance occurred.

## Self-review and handoff

Reviewed the three production diffs, archive scope/default consumers, actual provenance assertions,
responsive computed geometry, affected artifacts/hashes and coverage claims. The card is separate
from outcome/evidence and adds no action/state owner. Exact scope comprises the approved six maintained
files plus this report. The controller's next-plan documentation is not part of this source commit.

Fixture preview exited; final port3300 listener count0. The owner releases the lease; services and
retained data are unchanged. Independent review should compare original BASE through the scoped
commit and give separate spec/quality verdicts. This task awaits that review. Remaining native
recovery/Vault/MFA/CSP/outage, five unavailable Operator references, unexercised edges, browser zoom,
full contrast and unrelated visual differences remain requirements for the full Figma goal.
