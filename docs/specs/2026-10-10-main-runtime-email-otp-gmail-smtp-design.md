# Knora Main Runtime Email OTP and Gmail SMTP Design

## Goal

Make the primary Knora Keycloak runtime on `127.0.0.1:8180` use the Figma-approved email → six-digit OTP → password reset flow while delivering mail through Gmail SMTP with a Google App Password supplied outside Git.

## Boundaries

The Keycloak provider remains the owner of OTP generation, persistence, expiry, attempt budgets, resend generation fencing, one-time consumption, anti-enumeration behavior, and password continuation. The browser and Knora backend never receive or store the OTP or Gmail secret. Mailpit remains available only for isolated/test profiles.

The primary runtime will use the existing `infra/keycloak/Dockerfile` and `knora-reset-email-otp` provider. Realm changes are applied by a guarded migration script with an ID-bound snapshot and rollback. Compose declares only SMTP variable names; values come from a local ignored env file or deployment secret store.

## Data and mail flow

1. User selects Forgot Password from the Knora sign-in page.
2. Keycloak invokes the Knora OTP authenticator.
3. Provider reserves the durable challenge and sends the code through Keycloak's email provider.
4. Gmail SMTP accepts the message using TLS and the App Password.
5. User submits the six-digit code; provider verifies expiry, generation, attempt budget and current account email.
6. Provider continues to native Keycloak password update.
7. A fresh sign-in confirms the updated credential.

## Configuration contract

Required runtime values are `KC_SMTP_HOST=smtp.gmail.com`, `KC_SMTP_PORT=587`, `KC_SMTP_FROM`, `KC_SMTP_USER`, `KC_SMTP_PASSWORD`, `KC_SMTP_STARTTLS=true`, and `KC_SMTP_AUTH=true` (exact variable names may be mapped by the launcher to Keycloak realm SMTP settings). `KC_SMTP_PASSWORD` is a Google App Password and must never be committed or logged.

## Safety and rollback

Before applying the realm migration, inspect the exact realm ID, current reset flow, email theme and SMTP metadata. Save a JSON snapshot outside tracked source. Apply only to `knora-dev` on the owned local endpoint, fail closed on mismatched realm or foreign OTP flow, and provide a restore command. SMTP connectivity is tested with a synthetic recipient only.

## Acceptance

- Main sign-in links to the Knora-styled email reset page.
- Email reset page uses the designed labels and sends a real Gmail message.
- OTP page accepts six digits, rejects malformed/wrong/expired/replayed codes, and preserves uniform errors.
- Valid OTP reaches the native password update page and a fresh sign-in succeeds.
- Registration and normal sign-in remain functional.
- No secret appears in repository files, logs, URLs, screenshots or test artifacts.
- Restart preserves provider installation and realm configuration.
- Rollback restores the pre-change realm flow and SMTP metadata.

## Deferred work

Production provider rotation, outage drills, CSP/deployment policy, Keycloak upgrade proof and production observability remain tracked by Issue #152. Gmail SMTP integration is tracked by Issue #157 and is intentionally combined with this implementation.
