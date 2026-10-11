# Figma Documents local interactions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development.

**Goal:** Exercise the remaining local Documents filter/menu/dialog prototype actions through actual modules.
**Architecture:** Extend the existing guarded fixture browser suite for reversible local interactions.
Do not substitute fixture navigation for real product destination or backend lifecycle proof.
**Tech Stack:** Next/React, Playwright/TypeScript, existing scoped API fixture.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend remains source of truth; fixtures establish presentation and local UI behavior only.
- Preserve capabilities, native menus/dialog focus, API fields and all current production modules.
- Production ownership is limited to the diagnosed mobile DocumentActionsMenu placement amendment below;
  no helper/fixture response/exporter/renderer/dependency changes.
- No live upload/archive/restore/reprocess/delete, service/realm/password/Vault/SMTP/outage/worker,
  merge/push/cleanup actions. Unexpected API requests must remain rejected.
- Source structure drives interaction mapping; screenshots are evidence, never assets.
- Frontend format then format:check and typecheck mandatory.
- Every prior Q1 artifact must remain unchanged; add a separate task evidence directory.

## Directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Existing module local control journeys |
| `docs/development/figma-ui-visual-coverage.md` | Precisely mapped edges and remaining live limitations |
| `frontend/components/documents/DocumentActionsMenu.tsx` | Diagnosed mobile archived menu placement only |

## Task 1: Exercise Documents local control journeys

**Dependency:** OTP input presentation independently approved. Read fresh complete MCP128:120
structure/render saved at `.superpowers/sdd/2026-10-08-figma-documents-header/source/`.
Read coverage ledger edges3/5/6/8/9/11/13/14/17/23/24/26/28 for exact meanings before mapping.
**Skills:** figma-design-to-code, verification-before-completion, requesting-code-review,
systematic-debugging if a failure occurs. This is verification-only, no fabricated RED.

- [ ] Record clean original BASE and full Q1 before hashes (exclude root regression-preflight only).
  Read existing prepareFixture, DocumentList, DocumentActionsMenu, UploadDocumentDialog and
  DeletionRequestDialog. Fixture host is state-driven; clicking a link proves its target URL only,
  not arrival at real production page. Do not alter host/helper to manufacture transitions.
- [ ] Add one desktop/mobile local journey at1440×960/390×844:
  `prepareFixture(page,"128:120")` starts five rows, archived checked, ready menu open. Close menu
  using Escape and assert focus returns to ready trigger. Uncheck Show archived→four rows and
  archived row absent, count4. Check→five rows/count5, archived row present. Search exact filename,
  assert expected row only/count1; unmatched query→empty state, then clear→five/count5.
  Locate list rows by real names, not global repeated text. No status reinterpretation.
- [ ] Reopen Ready menu with keyboard and assert View details/Reprocess/Archive/Request deletion;
  use Arrow keys and Escape to verify focus return. Verify href for View details and row link
  agrees with scoped document ID without navigating state-driven fixture host. Capture ready menu
  only after fonts/assets ready. Record URL check separately, not a completed destination edge.
- [ ] Open deletion confirmation from ready menu, assert document name/dialog/Cancel/Confirm,
  then Cancel and reopen/Escape with focus return to existing actual trigger. Do not confirm.
  Open archived row menu and assert Restore document/no Reprocess, then Request deletion and
  cancel; this is local dialog only, not accepted deletion. Capture archived menu and dialog
  empty/non-sensitive states in `documents-local-interactions-2026-10-08` only.
- [ ] Open Upload document, choose test-only in-memory Reporting policy.pdf (no submission),
  assert selected filename and Upload action enabled, Cancel; reopen and verify selection cleared.
  Escape closes dialog and returns existing trigger focus. These checks map local selected-file
  and cancel transitions, not parsing/READY/upload acceptance. Capture selected file state only.
- [ ] Assert no unexpected API request and no POST/DELETE/PATCH invocation in these journeys;
  all native/backend mutation actions remain uninvoked. If existing focus/selection behavior
  contradicts required controls, report concrete failure before any production fix/ownership change.
- [ ] Run only new2cases; normalize NO_COLOR/FORCE_COLOR environment. View captures and report
  readable mobile/menu/dialog fit/no horizontal overflow, existing asset slots and source residuals.
  Update only accurately exercised ledger rows; preserve every unexercised/live limitation.
- [ ] Inventory after: all prior hashes unchanged, additions solely own evidence folder. Run
  format→format:check→typecheck sequentially. Self-review, exact2path commit, release3300; report
  commands/results, per-edge evidence mapping and guards. Root originalBASE→HEAD Spec/Quality review.

**Finish condition:** Named local filter/menu/dialog actions verified and accurately mapped,
independently reviewed. Real lifecycle/navigation/authorization and whole-design acceptance remain open.

## Diagnosed mobile placement amendment

Desktop local journey passed. Mobile Archived trigger reaches document end; even actual scrolling
cannot center it because remaining scroll range is exhausted. Existing downward absolute menu
extends to924.421875 in844px viewport. Ready mobile menu already fits; this failure is menu placement,
not focus or API behavior. Preserve failing log and diagnostic geometry/PNG before correction.

Ruling: Add only mobile upward placement to the owning DocumentActionsMenu wrapper using a static
Tailwind descendant rule `max-md:[&_.kn-menu\_\_panel]:bottom-full` (same established escaped selector
syntax as existing rules). Desktop downward source composition is retained. Documents list actions
are below the heading/toolbar, providing room above on the tested mobile composition. There is no
mobile Figma reference; this is disclosed responsive adaptation. No shared Menu props/positioning,
handlers, source copy, API or fixture changes. Cost if wrong: local responsive rule rework.

This amendment converts the task's diagnosed presentation correction to RED→GREEN: retain concrete
overflow RED, apply the one-rule fix, run both original journeys GREEN and verify all menuitems fit,
Escape/arrow/deletion cancel/file reset remain functional. Exactly three maintained paths now belong
to implementer; record the expanded ownership in report. Controller plan commit is disclosed in
originalBASE→HEAD review range. If another actual failure appears, diagnose it before another edit.
