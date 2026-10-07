# Figma archived inspector context geometry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Match the retained W5A unselected-answer guidance card geometry without clipping evidence.
**Architecture:** EvidenceInspector already receives authoritative Workspace archive state. Apply
the source96px context minimum only to archived Workspace + completed ANSWER + no citation.
All selected historical excerpts and other outcome states keep their existing evidence layout.
**Tech Stack:** React18.3.1, TypeScript, Tailwind CSS v4, Vitest, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Backend owns Workspace archive and Turn outcome; no inferred archive/outcome authority.
- Preserve historical citation version, excerpt, source link and provenance; never fabricate content.
- Use existing semantic tokens and production components; no API/schema/dependency changes.
- Figma full MCP structure is geometry authority; screenshots are visual comparison targets.
- Run frontend format then format:check for maintained frontend changes.
- Preserve mobile readability, keyboard/focus and selected-source access; never hide overflow to fit.
- No service/worker/realm/password/deletion actions, merge, push or branch/worktree removal.
- Native identity/outage/full-regression and other source differences remain separate open gates.

## Exact directory ownership

| Path | Responsibility |
| --- | --- |
| `frontend/components/citations/EvidenceInspector.tsx` | Conditional retained-answer context card geometry |
| `frontend/tests/conversation-panels.test.tsx` | Actual component state distinctions and historical evidence preservation |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | W5A unselected context desktop/mobile geometry and content-fit checks |
| `docs/development/figma-ui-visual-coverage.md` | Correct W5A context-height status and retain other differences |

Source: foundations cache `.superpowers/figma/2026-10-05/workspaces/183-176.md`, nodes187:218
and183:304. Inspector376wide; content padding18, gap14; context340×96, padding14/13, gap8,
radius8; following archived notice340×82. Ordinary conversation sources retain146px contexts.

## Task 1: Correct only retained unselected-answer context

**Dependency:** Current OTP/origin and Operator guidance tasks reviewed; record exact starting HEAD.
**Skills:** figma-design-to-code, test-driven-development, verification-before-completion,
requesting-code-review.

- [ ] Read full cached source, actual inspector and current archived notice browser tests.
- [ ] Add a component regression distinguishing archived/no-selection/ANSWER from selected
  citation, active Workspace, refusal, pending and interrupted states. Require the96px minimum
  only on the source's retained-answer guidance, preserving existing historical excerpt/link checks.
- [ ] Run the affected component test RED against current146px universal context minimum.
- [ ] Compute the presentation condition from existing props; keep outcome/citation precedence:

```tsx
const retainedAnswerContext =
  workspaceArchived && !citation && turn?.result?.decision === "ANSWER";
```

- [ ] Use source96px minimum and340px width, bounded to available mobile width, for this condition.
  Preserve146px minimum elsewhere; no fixed maximum height or clipped real text. Do not change
  heading/body, provenance, source-selection behavior, archived notice or restore composer.
- [ ] Run actual component GREEN and focused related panel tests.
- [ ] Add W5A unselected source fixture at1440 and390: actual context height96desktop/width340,
  padding14/13,gap8,radius8, following notice gap14, full text fit and no viewport overflow. Then
  select a real fixture citation and confirm preserved historical excerpt/document navigation;
  source fixture requests remain intercepted, no API mutation or backend authorization claim.
- [ ] Recapture only W5A, rebuild only its comparison/workspace sheet with existing scripts,
  preserve all other source/capture hashes and full cached MCP structure. Record remaining
  answer/citation/extra-control differences; no automatic baseline acceptance.
- [ ] Update coverage, run format→format:check→typecheck and focused browser cases, self-review
  and report exact RED/GREEN/geometry/limitations. Commit exact four maintained paths and release
  preview3300. Independent originalBASE→HEAD review gives spec and quality verdicts.

**Finish condition:** W5A retained-answer card and notice spacing match cached geometry at desktop,
mobile text remains readable and selected historical evidence is preserved; no Important finding.
Other inspector states and full native/Figma acceptance are not accepted by this bounded task.
