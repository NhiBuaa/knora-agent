# Figma reset static clock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development.

**Goal:** Make static reset presentation captures deterministic across elapsed browser time.
**Architecture:** Use existing Playwright clock only in the static source-copy test. Keep the
separate OTP countdown interaction test and native provider/template behavior unchanged.
**Tech Stack:** Playwright, TypeScript, existing Next fixture host.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Diagnostic ruling

The unchanged `prepareFixture` helper already calls `page.clock.setFixedTime` before navigation.
The planned elapsed1500ms diagnostic passed without the proposed local setter, disproving the
reviewer's live-Date premise. Treat this task as verification-only: retain diagnostic evidence,
revert only experimental test hunks, preserve prior artifacts, and request focused reviewer
confirmation. Do not duplicate clock setters or manufacture a failing test. No maintained test or
coverage edit is needed; the steps below preserve the original hypothesis for audit.

## Global Constraints

- Backend remains authority; no native submissions or provider/template/CSS/resource changes.
- Screenshots are evidence, never production assets; preserve all existing Q1 artifacts.
- No dependencies, service/realm/credential/data/worker/merge/push/cleanup actions.
- Run frontend format then format:check, followed by typecheck.
- Static fixture evidence cannot establish native reset or full-design acceptance.

## Directory ownership

| File | Responsibility |
| --- | --- |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Existing static reset clock and evidence path |
| `docs/development/figma-ui-visual-coverage.md` | Record deterministic static evidence and limits |

## Task 1: Freeze static reset capture time

**Skills:** receiving-code-review, systematic-debugging, verification-before-completion,
requesting-code-review. Reviewer Minor is in reset-presentation/task-1-review.md.

- [ ] Read existing static reset source-copy test and adjacent independently controlled timer test.
  Inventory all299 current Q1 artifacts, excluding only root regression-preflight.
- [ ] In the static test only install the existing clock at a fixed Date before navigation:
  ```ts
  const now = new Date("2026-10-05T12:00:00Z");
  await page.clock.install({ time: now });
  ```
  Add `await page.clock.runFor(1500)` after prepareFixture for OTP states only, before asserting
  `00:30`. Run that exact test and confirm RED from elapsed countdown, not infrastructure.
  Use separate evidence folder `reset-static-clock-2026-10-08`; preserve prior captures.
- [ ] Add `await page.clock.setFixedTime(now)` immediately after install, before any navigation.
  Keep runFor1500 so actual interval callbacks execute while Date remains fixed. Both normal/error
  OTP static states must still show00:30, preserving ready label/pending/disabled meaning. Do not
  change the adjacent timer test's install/pause/setFixedTime/runFor progression or no-JS test.
- [ ] Run only static test and existing native FTL OTP cases with normalized color environment:
  remove NO_COLOR, set FORCE_COLOR=0 in subprocess. Confirm three cases pass; observe timer test
  still proves00:30→00:01→ready and no-JS fallback. No native action submission.
- [ ] View new empty-field desktop/mobile captures. Record full copy/toggles/asset preservation,
  elapsed static interval proof and independent timer evidence. Do not broaden screenshot acceptance.
  Compare299 baseline hashes, preserve all existing files; enumerate additions separately.
- [ ] Run format→format:check→typecheck sequentially; commit exact two owned files, release3300,
  self-review/report with RED/GREEN and hash proof. Root originalBASE→HEAD independent review.

**Finish condition:** Static00:30 survives elapsed callback execution; the actual timer test still
advances; prior evidence preserved; independent Spec/Quality approval. Native gates remain open.
