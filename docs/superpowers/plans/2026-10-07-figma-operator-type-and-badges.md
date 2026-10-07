# Figma Operator typography and badges — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Correct remaining measured Operator label typography and Trace decision badge shapes.
**Architecture:** Extend only the owning presentation choices and local Trace badge callsites,
composing the existing selector and semantic badge. Preserve default consumers, domain outcomes,
dynamic provenance, disclosures and navigation. No shared primitive redesign.
**Tech Stack:** Next.js15.5.24, React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns authorization, Workspace archive/revision, outcomes, metrics and observations.
- Preserve all current actions, safe navigation, historical provenance and missing-data semantics.
- Never substitute illustrative Figma values for runtime data or invent report quality scores.
- Full MCP structures supply source geometry; PNG comparison verifies actual composition.
- Reuse exact local assets at intrinsic dimensions. No SVG editing, substitute icon or temporary URL.
- Use semantic tokens and preserve accessibility contrast, focus, responsive text fit and keyboard use.
- No generated API, backend/schema/client/dependency additions or production fixture routes.
- Run frontend format then format:check. No services/workers/realm/password/Vault/deletion/outage
  actions, installs, merge, push or branch/worktree removal.
- Native/full-regression and remaining source deviations are separate unresolved requirements.

## Exact directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/components/workspaces/WorkspaceSelector.tsx` | Operator label11px, default10px preserved |
| `frontend/components/operator/TraceView.tsx` | Source ANSWER and SELECTED badge dimensions/type/alignment |
| `frontend/tests/operator/operator-figma.test.tsx` | Actual owning presentation/default/state regressions |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Source geometry RED/GREEN, mobile preserved |
| `docs/development/figma-ui-visual-coverage.md` | Addressed typography/badges and truthful remaining gaps |

No shared StatusBadge/Menu or stylesheet edit. Fresh five-source cache remains authoritative at
`.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/`; original51 sources remain intact.

## Task 1: Match measured Operator typography and Trace badges

**Dependency:** Geometry correction task independently reviewed. Record clean exact BASE.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.

- [ ] Read five full MCP contexts and current affected measurementJSONs. Confirm source Workspace
  label11px versus current10px. Prior geometry task already corrected trace field13px; report14px stays.
- [ ] Inspect selector Operator presentation and Trace existing StatusBadge callsites. Reuse suitable
  components. Add meaningful actual-component/default-consumer tests and browser RED on named
  dimensions/font size/font weight/text alignment/icon absence, not assertions mirroring class strings.
- [ ] Set only Operator Workspace label11px; keep default selector and open/default consumers
  unchanged. Use existing presentation parameter, not route-based authorization or new domain state.
- [ ] Preserve and verify corrected trace lookup field13px/report14px and established34/36px field
  geometry, buttons, safe URL encoding, pending/error state and optional Workspace override.
- [ ] Source216:637 ANSWER is110×28 radius7px; text node216:638 isInter12px semibold600,
  source left padding10px, vertically centered16px text region. Source216:644 and216:651
  SELECTED are150×28 radius7px with same12px/600 and10px left padding. No icon appears in these
  source badge slots. Apply local presentation at those exact existing callsites, preserving semantic
  kind/accessibility and complete label. Do not edit the shared StatusBadge default or vector assets.
- [ ] Restrict named source geometry to corresponding ANSWER/SELECTED states. Other real outcomes,
  exclusion labels and unknown states must stay truthful and readable; allow natural growth for long
  dynamic labels instead of forcing arbitrary content into the supplied source rectangles.
- [ ] Preserve responsive row wrapping, full source names/excerpts/ranks/versions/Chunk Sets and
  embedding provenance. At390px whole SELECTED must fit without within-word wrapping or horizontal
  overflow. Keep actual disclosure and timing/validation content reachable through natural scroll.
- [ ] Run focused affected component tests GREEN and five Operator source cases1440/390 GREEN.
  Check effective label/badge geometry after fonts load, including source intrinsic assets from the
  preceding task. Captures remain comparison evidence, not backend/native/authorization proof.
- [ ] Update only affected five captures/JSON/HTML; preserve original51 and unrelated evidence hashes.
  Exclude only actively written root-owned regression-preflight logs from the invariant manifest.
- [ ] Record remaining source/current deviations honestly: page coordinates, margins, source candidate
  text measure, extra supported controls, natural dynamic growth and semantic-token contrast. No
  accepted-parity boolean or broad tolerance that waives a named mismatch.
- [ ] Run format→format:check→typecheck, focused regressions, self-review and report exact RED/GREEN,
  source/callsite/rendered geometry and command results. Commit only five owned maintained paths,
  release preview3300 and submit originalBASE→HEAD for independent spec/quality review.

**Finish condition:** Named typography and source badge geometry proven with complete dynamic state,
default-consumer behavior and readable mobile adaptation preserved; no Important review finding.
This task does not declare whole-page or full Figma/native acceptance.
