# Figma OTP resend progressive enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Preserve a usable native resend form action when JavaScript is blocked.
**Architecture:** Server cooldown/budget remains authoritative. The native form keeps its existing
POST intent; JavaScript alone enhances it with disabled countdown behavior. This fixes the
reviewed theme defect without changing storage, provider protocol or deploying recovery.
**Tech Stack:** Keycloak26.3.3, FreeMarker2.3.32, Java21/Maven, Playwright.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Keep credentials, OTP and passwords in Keycloak; no browser/server application OTP handling.
- Preserve server-enforced cooldown, account/IP send windows, generation fencing and six-digit
  verification semantics. UI disabled state is not the rate-limit authority.
- No recovery flow apply, provider reload, realm/password/service change or blocked outage retry.
- Use existing actual FTL offline renderer and pinned cached runtime; no dependency installation.
- No secrets/action URLs/tokens/codes in logs or committed fixtures. No production data.
- Frontend maintained changes require format then format:check.
- Source checks cannot establish native OTP/Vault/MFA/CSP/password/outage acceptance.
- No merge, push, branch/worktree deletion or automatic integration action.

## Directory and exact scope

| File | Responsibility |
| --- | --- |
| `themes/knora/login/knora-reset-otp.ftl` | Native resend button and existing countdown enhancement |
| `infra/keycloak/providers/email-otp-reset/src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java` | Actual FTL offline regression |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Existing JS/no-JS actual FTL input/resend checks |
| `docs/development/figma-ui-visual-coverage.md` | Record corrected fallback and remaining native gates |

Consume existing retryAfterSeconds attribute and native intent=resend. Do not alter Java provider,
store, service, CSS, POM, source exporter or generated contracts. Diagnose/amend scope if needed.

## Task 1: Native resend fallback

**Dependency:** archived evidence notice reviewed. Record exact starting HEAD.
**Skills:** test-driven-development, systematic-debugging, verification-before-completion,
requesting-code-review.

- [ ] Read actual FTL and native action/store service. Current server-rendered disabled attribute
  persists indefinitely without JavaScript; existing no-JS browser test codifies this defect.
- [ ] Add actual FTL RED requiring enabled native resend form action with retryAfterSeconds30
  and0, preserved formnovalidate/name=intent/value=resend and visible cooldown information.
- [ ] Run focused offline FTL test and confirm disabled-markup failure before production edit.
- [ ] Remove permanent server-rendered disabled behavior from native resend. In the existing JS
  enhancement set disabled immediately for a positive valid cooldown, then enable at zero.
  Preserve the original accessible code field, mirror cells, paste/leading zeroes and native POST.
- [ ] JS-blocked user may submit native resend; server still rejects/limits early requests under
  unchanged protocol. Do not claim this offline action proves deployed server cooldown behavior.
- [ ] Update offline test expectations and run focused actual FTL rendering GREEN. Preserve
  unknown-account masking, no OTP leakage and all existing intent fields.
- [ ] Update existing JS/no-JS browser checks: JS positive cooldown disabled then enabled after
  controlled browser clock passage; no-JS resend enabled, code visible/labelled/leading zeroes.
  Source fixture submissions remain blocked; no actual SMTP/code/password action is authorized.
- [ ] Re-export actual source FTL with existing offline exporter. Run only affected OTP
  interactions; JS-rendered visual layout should stay unchanged. Recapture only if rendering
  changes; preserve existing source comparison hashes and full MCP structures.
- [ ] Update coverage fallback wording; retain native and configured-origin regex gate gaps.
- [ ] Run format/format:check and typecheck for maintained frontend test edits. Run relevant
  actual offline FTL tests with existing disposable pinned Maven cache, excluding opt-in deployed
  storage/native scenarios. No worker/data/service changes or broad80 capture rerun.
- [ ] Self-review/report exact RED/GREEN/commands/limitations; commit exact paths and release
  preview3300lease. Independent review originalBASE→HEAD gives separate spec/quality verdicts.

**Finish condition:** native form remains usable without JS, JS countdown behavior is verified,
server protocol unchanged and no Important review finding. Full native OTP goal remains pending.
