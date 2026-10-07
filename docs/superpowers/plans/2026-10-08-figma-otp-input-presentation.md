# Figma OTP input presentation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development.

**Goal:** Match the source420px OTP allocation and empty-cell marks without changing native input authority.
**Architecture:** Correct existing OTP-specific CSS only, keeping one native text input and six
decorative mirrored cells. Responsive cells shrink within the available content width.
**Tech Stack:** Native Keycloak FreeMarker output, CSS, Playwright/TypeScript.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Keycloak owns code verification, cooldown, budgets and credentials; preserve POST/name/intents,
  leading zeros, single labelled input, expiry/error/privacy, no-JS and native action blocking.
- Complete cached direct MCP structures drive implementation; returned screenshots are visual
  targets, never assets. Preserve existing exact leaf/eye assets, semantic colors and focus.
- No template/script/provider/renderer/exporter/dependency/API or non-OTP CSS selector edits.
- No service/realm/Vault/SMTP/password/outage/data/worker/merge/push/cleanup actions.
- Mandatory frontend format then format:check, followed by typecheck.
- Static/fixture checks cannot establish native reset or whole-design acceptance.

## Directory ownership

| File | Responsibility |
| --- | --- |
| `themes/knora/login/resources/css/knora.css` | Existing OTP-specific wrapper/grid/empty-cell selectors |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Source allocation, empty/decorative cells and input preservation |
| `docs/development/figma-ui-visual-coverage.md` | Corrected OTP local region and retained residuals |

## Task 1: Correct OTP allocation and empty marks

**Skills:** figma-design-to-code, systematic-debugging, verification-before-completion,
requesting-code-review. Full source242-333.md/png and246-311.md/png are retained in
`.superpowers/sdd/2026-10-08-figma-reset-presentation/source/`; read all structures and view renders.

- [ ] Inventory current315 Q1 files excluding regression-preflight; preserve old captures.
  Source246:292/363 is420×56; six54×56 cells,10px gaps, centered inner374. Empty normal
  source marks are22px semibold “—” in muted color. Error sample digits remain input-derived,
  never hardcode234567. Existing input is text/numeric/pattern6, mirrors aria-hidden.
- [ ] Add focused browser case for normal/error at1440×960/390×844. RED expects wrapper420px
  desktop, cells54px/gap10/centered23px, empty pseudo marks, single labelled56px input;
  mobile wrapper available width/no overflow/cells natural shrink. Capture new evidence only
  `otp-input-presentation-2026-10-08`. Preserve unrelated source/private/native outcomes.
- [ ] Modify only existing selectors:
  ```css
  .knora-auth .knora-otp-entry { width: 420px; }
  .knora-otp-enhanced .knora-otp-cells {
    grid-template-columns: repeat(6, minmax(0, 54px));
    justify-content: center;
  }
  .knora-otp-cells span:empty::before {
    content: "—";
    color: var(--knora-muted);
  }
  ```
  Keep other existing properties (height56/max-width100%,10gap, semantic border/radius/font,
  pointer-events:none and true input focus) unchanged. Verify real computed minmax behavior on
  mobile; if it overflows, diagnose and rule before a different responsive solution.
- [ ] Offline existing exporter updates only native/resources/css/knora.css; no new parent/resource,
  no live flag. Existing9native HTML hashes must remain unchanged; report any unexpected drift
  before accepting it. Do not edit exporter/renderer. Run focused GREEN and two existing OTP
  JS/no-JS cases; native action remains blocked. Empty screenshot before paste, then000042 shows
  mirrored leading zeros and no empty pseudo content. Clear input restores six decorative marks.
  Native labelled input count1, required/pattern/min/max/autoComplete/aria fields retained.
- [ ] Verify no-JS shows native56px input and hidden mirror layer, no decorative mark overlay;
  enabled resend00:30 remains. Check existing source-copy test for password/request preservation
  after scoped CSS update; normalize color env for authorized runs. No all51 capture rerun.
- [ ] View all new empty-field captures and record source allocation versus actual origin, semantic
  color and privacy/error/expiry adaptations; no global parity claim. Verify exact static leaf18px
  load/slot unchanged and no new assets. Hash inventory permits only copied native CSS change plus
  new task evidence; all other prior files unchanged. Preserve prior screenshots as history.
- [ ] Format→format:check→typecheck sequentially; self-review/commit exact3paths, release3300,
  report RED/GREEN source map, native HTML/CSS hashes, artifacts and residuals. Root originalBASE→HEAD
  independent Spec/Quality review required.

**Finish condition:** Source OTP local allocation and empty-cell appearance verified without native
input/protocol/no-JS regression, independently approved. Full-design/native acceptance remains open.
