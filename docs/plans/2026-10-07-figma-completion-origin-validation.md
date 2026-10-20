# Figma completion origin validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Fix the reviewed completion-link port and bracketed IPv6 validation defects.
**Architecture:** The maintained native info template continues to use configured client.baseUrl
only for successful account-update completion. Validate the existing authority before emitting
the fixed fresh-sign-in route, preserving unfinished native action links and fail-closed behavior.
**Tech Stack:** Keycloak26.3.3, FreeMarker2.3.32, Java21/Maven.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Keep credentials, OTP and passwords in Keycloak; no application-side recovery handling.
- Successful completion returns only to configured application origin and fixed
  `/api/auth/login?prompt=login`; strip configured path/query/fragment and native action parameters.
- Missing/invalid configured completion origin must not fall through to pageRedirectUri/actionUri.
- Preserve unfinished native required-action behavior and existing skipLink behavior.
- No provider/store/protocol/realm/Vault/service changes, native deploy or outage workaround.
- Use existing actual FTL offline renderer and pinned cached runtime; no dependency installation.
- No secrets/action URLs/tokens/codes in logs or committed fixtures; use synthetic test values.
- Source verification does not establish native password/MFA/Vault/CSP/outage acceptance.
- No merge, push, branch/worktree deletion or automatic integration action.

## Directory and exact scope

| File | Responsibility |
| --- | --- |
| `themes/knora/login/info.ftl` | Completion authority validation and existing fresh-sign-in CTA |
| `infra/keycloak/providers/email-otp-reset/src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java` | Actual native info template regressions |
| `docs/development/figma-ui-visual-coverage.md` | Correct the two reviewed origin defects' status and retain native gaps |

No additional helper, dependency, browser code or frontend production file. Retain the existing
ASCII hostname branch; this task fixes port and bracketed IPv6 acceptance, not a complete URL
parser, IDNA normalization, DNS existence or configured-host ownership verification.

## Task 1: Validate completion port and IPv6 authority

**Dependency:** OTP resend fallback independently reviewed. Record exact starting HEAD.
**Skills:** systematic-debugging, test-driven-development, verification-before-completion,
requesting-code-review.
**Consumes:** client.baseUrl and message.type/summary in the existing info.ftl context.
**Produces:** unchanged completion CTA for valid existing configuration; no completion link for
out-of-range ports or malformed bracketed IPv6.

- [ ] Read existing info.ftl and the first three actual renderer tests in EmailOtpResetFlowIT.
- [ ] Extend the actual fail-closed test with these synthetic configurations and assert no anchor:

```java
List.of("https://app.example:65536", "http://127.0.0.1:99999/",
        "https://[123]", "https://[1:2:3]", "https://[1::2::3]",
        "https://[1:2:3:4:5:6:7:8:9]", "https://[::1]:65536")
```

- [ ] Run the focused offline completed-info tests before editing production FTL; record actual
  RED from an incorrectly emitted link, not an environment/renderer failure.
- [ ] Replace permissive bracketed `[A-Fa-f0-9:]+` with an explicit ordinary IPv6 grammar.
  Use these alternatives, anchored within brackets in the existing authority match:

```text
([A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}
([A-Fa-f0-9]{1,4}:){1,7}:
([A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}
([A-Fa-f0-9]{1,4}:){1,5}(:[A-Fa-f0-9]{1,4}){1,2}
([A-Fa-f0-9]{1,4}:){1,4}(:[A-Fa-f0-9]{1,4}){1,3}
([A-Fa-f0-9]{1,4}:){1,3}(:[A-Fa-f0-9]{1,4}){1,4}
([A-Fa-f0-9]{1,4}:){1,2}(:[A-Fa-f0-9]{1,4}){1,5}
[A-Fa-f0-9]{1,4}:((:[A-Fa-f0-9]{1,4}){1,6})
:((:[A-Fa-f0-9]{1,4}){1,7}|:)
```

- [ ] Retain optional one-to-five-digit port syntax. Extract the port only from the matched
  authority (after closing bracket for IPv6, or host for the existing hostname branch), then
  require its numeric value <=65535 before rendering. Do not confuse IPv6 hextets with ports.
  Port0 remains syntactically accepted; configured service reachability is separate.
- [ ] Extend successful actual-template test with expected origins for hostname port65535,
  loopback `[::1]:3300`, expanded `[1:2:3:4:5:6:7:8]`, compressed `[2001:db8::1]`,
  `[1::]` and `[::]`, each with synthetic path/query/fragment. Assert exact fixed CTA and no
  copied native redirect/action or configured query/fragment. Preserve original cases.
- [ ] Keep the existing no-safe-origin and unfinished-info tests; add empty client.baseUrl and
  skipLink coverage only if not already exercised. Do not change non-completion authority rules.
- [ ] Run relevant offline info tests GREEN, then existing offline EmailOtpResetFlowIT excluding
  opt-in deployed storage/native scenarios. Record exact cached Maven/JDK commands and outputs.
- [ ] Update coverage lines for I3 configured-port/bracket-IPv6 correction; retain configured
  origin trust/reachability limits and native reset/provider/Vault/MFA/CSP/outage gaps. No new
  visual baseline or full capture rerun: valid configured-origin layout should remain unchanged.
- [ ] Self-review, git diff --check, commit exact three maintained paths, and write report in this
  plan's own SDD workspace. Independent originalBASE→HEAD review gives spec and quality verdicts.

**Finish condition:** Actual-template RED/GREEN demonstrates rejected malformed port/IPv6
and preserved valid fresh-sign-in links; no Important review finding. Full native goal remains
pending. DNS/IDNA and deployed configuration checks are not claimed by this bounded correction.
