# Issue #188 P2 — sanitized Dashboard observation envelope

Observation date: **2026-10-16 UTC** (approximately 03:20–03:27 UTC).

This is a minimal, sanitized record of the read-only Cloudflare Dashboard surfaces
used by the P2 capability investigation. It contains no account ID, email address,
IP/CIDR, payment detail, token value, token prefix/suffix/fingerprint, cookie,
authorization header, raw payload or screenshot. It is not a credential snapshot and
does not authorize an API request, configuration change or inference call.

## Surfaces and observations

- **Account selection and local metadata:** the selected Dashboard account matched
  the allowlisted `KNORA_CLOUDFLARE_ACCOUNT_ID` value read from the primary checkout's
  `.env` by key only. The selected worktree had no `.env`; its shell process had no
  account-ID value. No token setting was read.
- **Account API tokens:** the account-token page showed its first-token onboarding
  state and no account-owned token rows.
- **User API token summary:** the token displayed as `Workers AI` was Active, scoped
  to one account, had last-used date **2026-10-15**, no displayed expiry (`-`), and
  summary permissions `Workers AI:Edit` and `Workers AI:Read`. No AI Gateway or
  Billing permission was displayed. The policy form showed no selected client-IP
  filter and no selected TTL range; it was exited with Back and never submitted.
- **Plans and usage:** Workers plans showed **Free** as current; account
  Subscriptions showed **Workers Free — Active**; Workers AI showed **0/10k neurons
  used today** and a daily reset at 00:00 UTC.
- **AI Gateway landing:** the account view offered the default-Gateway onboarding
  text and a custom-Gateway link. No Gateway was created, changed, or exercised.

## Limits of this envelope

The historical two 403 requests are recorded only as “this checkout's configured
account/token” and are not bound to the displayed `Workers AI` token by name, type,
secret, fingerprint or policy history. The observations therefore make missing
AI Gateway/Billing permissions a sufficient **conditional** explanation, not a
proven historical root cause. Gateway configuration, first-Gateway date/log cohort,
native verdict shape, historical TTL/IP policy and combined P1 cost remain unknown.

This envelope records current Dashboard metadata only. It does not preserve raw
Cloudflare responses and must not be expanded by searching credentials, shell
history, arbitrary logs or latest traces.
