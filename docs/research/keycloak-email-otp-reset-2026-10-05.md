# Keycloak email OTP reset — primary-source findings

Date: 2026-10-05. Target: Keycloak 26.3.3. Planning research; no provider implemented or tested.

## Native behavior and chosen boundary

The native reset flow sends a signed email link. Its Reset OTP action concerns an enrolled
authenticator credential, not a six-digit email recovery code. The Knora flow needs a custom
authenticator, while keeping native password policy and update handling.
[Reset documentation](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_admin/topics/login-settings/forgot-password.adoc),
[ResetCredentialEmail](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/authenticators/resetcred/ResetCredentialEmail.java).

Recommended flow:

1. Custom Knora Email OTP Reset, REQUIRED: email request, verify and resend.
2. Native Reset Password, REQUIRED: schedules UPDATE_PASSWORD.
3. Native UPDATE_PASSWORD: confirmation, password policy and credential update.

Replace native Choose User and Send Reset Email. Choose User checks username and conditionally
email and has an existing-SSO path; a custom first execution can enforce the exact email request
UX without relying on loginWithEmailAllowed. Disable the Reset – Conditional OTP subflow for
this password-only recovery flow so enrolled authenticator credentials remain intact.
[Choose User](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/authenticators/resetcred/ResetCredentialChooseUser.java),
[Reset Password](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/authenticators/resetcred/ResetPassword.java),
[Update Password](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/requiredactions/UpdatePassword.java),
[credential provider](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/credential/PasswordCredentialProvider.java).

## SPI and templates

Implement Authenticator and AuthenticatorFactory with provider ID knora-reset-email-otp.
authenticate renders the current phase; action handles submitted intent. requiresUser returns
false to permit uniform decoy challenges for unknown/disabled accounts. configuredFor returns
true; setRequiredActions is empty because the recovery code is transient. Factory supports
REQUIRED only, no user setup, and configurable policy fields.
[Authenticator](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/authentication/Authenticator.java),
[Factory](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/authentication/AuthenticatorFactory.java),
[configuration interface](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/authentication/ConfigurableAuthenticatorFactory.java).

Register the fully qualified factory in
META-INF/services/org.keycloak.authentication.AuthenticatorFactory.
Use context.form().setAttribute(...).createForm(...), submit to the theme loginAction URL,
and read decoded form parameters through the flow context. Never put request state in a singleton.
[Pinned authentication SPI guide](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_development/topics/auth-spi.adoc).

Theme templates include login.ftl, register.ftl, knora-reset-email.ftl, knora-reset-otp.ftl,
login-update-password.ftl and reset-specific completion in info.ftl. Preserve the native form
action, hidden state and field error behavior when overriding templates.

Add email theme HTML/text knora-reset-otp.ftl and localized subject/body messages. Use
EmailTemplateProvider with realm, user and authentication session; it uses realm SMTP and renders
both text and HTML templates.
[Email API](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/email/EmailTemplateProvider.java),
[FreeMarker implementation](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/email/freemarker/FreeMarkerEmailTemplateProvider.java).

## Reset completion and an existing SSO session

On successful verification set AuthenticationManager.END_AFTER_REQUIRED_ACTIONS. Native completion
ends the reset authentication session and renders detached info.ftl. This alone does not guarantee
that a prior browser SSO cookie will require credentials on the next normal login.
[Completion source](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/services/managers/AuthenticationManager.java#L926-L961).

Preferred application integration: a fixed trusted CTA to /api/auth/login?prompt=login.
Allowlist only that prompt value in the existing BFF login route, creating a fresh transaction
with the existing state, nonce and S256 PKCE behavior. Keycloak treats prompt=login as requiring
reauthentication even with an SSO cookie.
[OIDC prompt handling](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/protocol/oidc/OIDCLoginProtocol.java#L452-L459).

A reset-scoped custom RequiredActionProvider that clears cookies after UPDATE_PASSWORD is an
alternative if BFF edits are prohibited; it adds action-ordering/configuration obligations.
It is not selected for this plan.
[Required action API](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi-private/src/main/java/org/keycloak/authentication/RequiredActionProvider.java).

## Packaging and realm migration

Use the repository's existing infra/keycloak/Dockerfile. New provider source belongs under
infra/keycloak/providers/email-otp-reset, not a second top-level Keycloak deployment.
Pin keycloak-core, keycloak-server-spi, keycloak-server-spi-private and keycloak-services to
26.3.3 with provided scope, using Java 21. Copy the built JAR to /opt/keycloak/providers before
kc.sh build; copy the theme into /opt/keycloak/themes/knora.
[Provider dependencies](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_development/topics/providers.adoc),
[container build](https://github.com/keycloak/keycloak/blob/26.3.3/docs/guides/server/containers.adoc#L55-L69),
[pinned Java runtime](https://github.com/keycloak/keycloak/blob/26.3.3/quarkus/container/Dockerfile#L17-L18).

Configure resetPasswordAllowed, resetCredentialsFlow, UPDATE_PASSWORD, login/email themes,
registrationAllowed and SMTP. Email sign-in requires loginWithEmailAllowed. Keep duplicate email
addresses disabled. Email-as-username and registration verification are explicit product choices.
[Realm fields](https://github.com/keycloak/keycloak/blob/26.3.3/core/src/main/java/org/keycloak/representations/idm/RealmRepresentation.java),
[registration](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_admin/topics/users/proc-enabling-user-registration.adoc),
[SMTP](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_admin/topics/realms/email.adoc).

Updating dev-realm.json does not migrate an existing realm: startup import skips existing realms.
Provide an idempotent targeted settings migration, avoiding destructive reimport.
[Import behavior](https://github.com/keycloak/keycloak/blob/26.3.3/docs/guides/server/importExport.adoc#L107-L118).

## Knora policy proposals — not Keycloak defaults

- Six decimal digits, including leading zeroes, generated with SecureRandom.
- Code TTL five minutes; recovery window 15 minutes.
- Resend cooldown 30 seconds to match the supplied Figma. The research initially considered
  60 seconds; the workflow selects 30 seconds with server-side limits.
- Five verification submissions per account recovery window; resend/new session does not reset it.
- Three sends per account/email per 15-minute window and 20 sends per IP per window.
- Resend invalidates previous generation; successful verification consumes the code once.
- Store a keyed digest bound to realm, account, current email, client, auth session/tab and generation.
- Uniform public challenge for unknown/disabled accounts and delivery errors; no OTP/password logs.

Storage is an implementation decision and release gate. Authentication session notes have no
atomic counter contract. SingleUseObjectProvider.remove promises single-use consumption across
nodes, and putIfAbsent can reserve keys; replace is not compare-and-swap. A candidate adapter must
prove atomic rotation/consume and account-wide budgets, including concurrent sessions and nodes.
Use explicit expiry checks; cache eviction alone is not code expiration.
[Authentication session](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi/src/main/java/org/keycloak/sessions/AuthenticationSessionModel.java),
[single-use storage contract](https://github.com/keycloak/keycloak/blob/26.3.3/server-spi/src/main/java/org/keycloak/models/SingleUseObjectProvider.java).

## Verification required before release

Inject clock, code generator, digest, sender and store. Test policy transitions independently,
then use the pinned real container and test SMTP for the complete journey. Official reset tests
show mailbox capture, clock advancement, policy errors, disabled users and SMTP failures.
[Pinned reset tests](https://github.com/keycloak/keycloak/blob/26.3.3/testsuite/integration-arquillian/tests/base/src/test/java/org/keycloak/testsuite/forms/ResetPasswordTest.java).

Required cases: valid/leading-zero/paste; malformed/wrong/expired code; resend cooldown and rotation;
replay and parallel consume; account-wide budget across sessions; changed email/disabled account;
SMTP/store failure; expired auth session; password policy/confirmation; enrolled MFA preserved;
existing SSO still prompts; fresh state/nonce/PKCE and tampered callback rejection.

Build with Maven verify, then the existing Keycloak Dockerfile and repository verification commands.
The verify gate must include real-container and multi-node storage tests. Private SPI and overridden
templates require rebuilding/retesting on Keycloak upgrades.
[Theme upgrade guidance](https://github.com/keycloak/keycloak/blob/26.3.3/docs/documentation/server_development/topics/themes.adoc#L54-L57).
