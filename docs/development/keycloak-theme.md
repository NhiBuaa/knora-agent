# Knora Keycloak login theme

The theme changes presentation. Keycloak owns credentials, native form actions, validation,
password policy, registration, and the OIDC protocol. Knora's BFF retains state, nonce and S256
PKCE validation. There is no Knora password or profile store.

## Verified Keycloak base

The local image is `quay.io/keycloak/keycloak:26.3.3`, digest `sha256:6a7217a100bd3e5de4063a27a538ef999a3c5a88c4b4ec0ffc0a642aee7b2597`. The inspection used:

```powershell
docker image inspect quay.io/keycloak/keycloak:26.3.3 --format '{{json .RepoDigests}}'
docker create quay.io/keycloak/keycloak:26.3.3
docker cp <container-id>:/opt/keycloak/lib/lib/main/org.keycloak.keycloak-themes-26.3.3.jar <temporary-path>
```

The JAR contains the actual v2 overrides for login, registration, update password and the layout
wrapper, plus the field, profile and password-policy helpers. Knora inherits `keycloak.v2`, its
wrapper, scripts, escaping and native helpers, and appends `css/knora.css`. Four child templates
adapt login, registration, update password and information pages to the approved identity design.
The registration template renders the real native username and email attributes and native
password/confirmation fields. It retains locale, terms and recaptcha contracts, native profile
annotations, read-only behavior, errors and policy helpers. A required custom field that appears
after configuration drift remains visible; configuration preflight rejects that scope conflict.

The layout uses bundled Inter and Roboto Slab and original Figma exports at their intrinsic
18×18 size. `resources/images/figma-assets.json` records original hashes and owning nodes; SVG
bytes remain unmodified. Identity resources use Keycloak resource URLs. The native password
visibility script owns type and accessible-label changes. The AU12 eye asset has its own callsite.

## Local development and deployment

`docker-compose.dev.yml` mounts `themes/knora` read-only. A new `knora-dev` realm imports `loginTheme=knora` from `test/fixtures/keycloak/dev-realm.json`. The persistent `keycloak_dev_data` volume may already contain the realm; import does not update it. For that case, set admin credentials in the current PowerShell process, then run:

```powershell
$env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME = '<admin username>'
$env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD = '<admin password>'
.\scripts\configure-keycloak-theme.ps1
```

The script reads the realm, changes only `loginTheme`, and verifies the setting. It does not delete/re-import users or clients. For another Keycloak host, supply `-BaseUrl` and `-Realm` explicitly. Do not commit credentials.

Build the same theme into a deployment image from the repository root:

```powershell
docker build -f infra/keycloak/Dockerfile -t knora-keycloak:26.3.3 .
```

Inter and Roboto Slab are bundled from `frontend/public/fonts`; their OFL license files are included alongside the theme assets. Theme colors match `frontend/styles/tokens.css`. Keycloak follows the browser's system light/dark setting; the app's preference cookie is not shared with the identity provider.

## Registration and existing realm configuration

Fresh development imports enable registration, password reset, username or email sign-in, and
unique email addresses, with `registrationEmailAsUsername=false` to keep the native username
field. `verifyEmail=false` is retained from the development fixture. Existing
realms retain their current `verifyEmail` setting when configured; no mandatory verification
screen is added. Development callback and logout allowlists remain on port 3000.

The [pinned native default profile](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/resources/org/keycloak/userprofile/config/keycloak-default-user-profile.json)
requires first and last names in the user context. AU8/AU9 collect four fields only, so this
development/test profile removes the user-required rule from those two attributes. Existing
values, validators, permissions, admin-required rules, unrelated attributes and groups remain
untouched. No hidden name values are generated. Conditional name requirements or additional
required custom attributes are reported as conflicts before applying.

For an existing daily realm, set admin credentials in the current process and inspect the exact
`knora-dev` target before changing it:

```powershell
.\scripts\configure-keycloak-auth-flow.ps1 -Mode Inspect
.\scripts\configure-keycloak-auth-flow.ps1 -Mode Diff
.\scripts\configure-keycloak-auth-flow.ps1 -Mode Apply
```

Only loopback port 8180 with Compose project `knora-dev`, or port 8380 with project
`knora-figma-e2e`, is accepted. Apply and rollback verify container ownership before mutation.
The script updates only the approved realm flags and copied native profile. It saves previous
settings and the full previous profile before a change, prints the snapshot path without
credentials, verifies the result, and makes a repeated identical apply a no-op. Restore with:

```powershell
.\scripts\configure-keycloak-auth-flow.ps1 -Mode Rollback -SnapshotPath '<saved snapshot>'
```

Snapshot files belong to local `.superpowers/figma/keycloak-rollback` continuity evidence and
must be retained until the realm change has an explicit disposition. They contain profile
configuration and realm flags, not credentials, user records, tokens or password values.
Daily SMTP remains operator configuration; enabling reset alone does not prove mail delivery.

## Isolated Figma identity harness

`docker-compose.figma-e2e.yml` is standalone. It uses project `knora-figma-e2e`, project-namespaced
volumes, separate application and Keycloak PostgreSQL databases, and test SMTP only. All exposed
ports bind `127.0.0.1`: frontend 3300, API 8800, Keycloak 8380, PostgreSQL 5543, Minio 9900/9901,
SMTP 1025 and mailbox 8025. The derived test realm has only the port-3300 client callback,
logout and origin URLs; its reset SMTP host is the isolated `mail` service. The test-only native
password policy is a minimum length of 12; development password policy is unchanged.

In a shell without ambient `COMPOSE_*`, `DOCKER_*`, `FIGMA_E2E_*`, `M5_E2E_*`, `KEYCLOAK_*`, `KNORA_*` or
`SESSION_SECRET` overrides:

```powershell
.\scripts\prepare-figma-e2e.ps1 -CheckConfigurationOnly
.\scripts\prepare-figma-e2e.ps1
Set-Location frontend
.\node_modules\.bin\playwright.ps1 test --config=playwright.figma.config.ts
```

Preparation validates project, bindings, volume names, database and realm/client targets before
starting resources, and checks running-container ownership and other listeners before mutation.
Startup, migrations, bucket creation and profile application are idempotent; preparation never
deletes or resets a realm, volume or daily resource. Do not use `prepare-local-e2e.ps1` for these
tests. Existing M5 configuration and endpoint guards are independent and unchanged.

The browser helper verifies exact Compose ownership before browser identity operations. Its
test-created users remain in the test realm; reruns use unique identities. Traces, video and
automatic failure screenshots are disabled because native action URLs contain authentication
state and reset codes. Explicit AU1/AU2/AU8/AU9 screenshots mask password inputs by stable ID.
Native failure page snapshots are also disabled with Playwright's installed
`PLAYWRIGHT_NO_COPY_PROMPT` setting, since accessibility snapshots include native action URLs.
Empty password fields are shown in explicit full-page captures; populated passwords are masked.
The harness checks Next readiness through `/api/auth/session`, which returns 200 without
following a sign-in redirect to Keycloak. The product base URL remains port 3300.

## Acceptance boundary

Source/fixture checks cover native action retention, assets, registration profile rules, harness
guards and profile inspect/diff/apply/no-op/rollback using test HTTP fixtures. They do not execute
FreeMarker, prove native registration, deliver reset mail, or establish rendered visual parity.
`figma-identity.spec.ts` contains real-provider cases for default/invalid sign-in, four-field
registration, real empty-field validation, password confirmation/policy errors and email sign-in.
Fresh registration follows the preserved backend resolver: it atomically creates `My Workspace`
and returns `ACTIVE`. A separate owner archive through the real API then proves
`NO_ACTIVE_WORKSPACE` and the workspace-management landing. The test never silently archives
an account to make fresh registration appear empty.

I1's isolated Keycloak 26.3.3 browser checks now execute all four native template overrides.
The real test SMTP reset link renders update-password and completes authentication; a separate
native execute-actions email for the test-created user renders information/proceed/completion.
This native email-link check verifies the templates and SMTP only. The approved I2 OTP journey
and I3 application CTAs remain separate work.

Actual AU1/AU2/AU8/AU9 captures were compared with cached structural contexts and PNG targets.
Checks cover 420×40 input containers, the 420×42 action at x830, right-aligned reset link,
single-line registration title, local font loading and all three original 18×18 assets.
Native autofocus, error summaries and per-field errors remain visible; real AU9 errors can
increase page height and scroll, with the sign-in footer verified accessible. Those adaptations
preserve native behavior instead of clipping actual validation. Controller review and broader
callback-negative, protected API, logout/account-switch and full-suite gates remain independent.

The earlier Docker Desktop `sailor-ingest.sock` failure was resolved by the user before live
startup. Initial frontend readiness independently timed out because it followed the root's
307 redirect; `/api/auth/session` readiness resolved it. Neither earlier failure is counted as
a native form behavior RED. No daily resource reset was used during recovery or testing.

Historical Issue #115 evidence used the earlier inherited-form theme on disposable port 8183.
It proved stylesheet delivery, invalid credentials, a provider callback, and non-destructive theme
selection. It does not verify the new I1 native templates or the current registration journey.

## Email OTP provider source and operator provisioning

The image packages `knora-reset-email-otp` before Keycloak augmentation and enables the pinned
file Vault provider. The execution is currently **unbound**: this source build does not replace
the realm's reset flow. Offline Java translation tests and pinned parent FreeMarker rendering
are separate from deployed recovery acceptance. Native password, replay, MFA preservation,
shared Vault restart/rotation and visual browser checks remain required. The physical database
outage proof remains blocked by automatic tool review; a lock timeout or reply-loss proof is not
a substitute for it. This outstanding deployment-hardening proof is separate from the approved
isolated native-runtime path below, which requires its own essential-safety preflight and review.

### Guarded isolated native runtime source

`docker-compose.figma-otp-runtime.yml` is an explicit override for the Figma harness. It builds
the existing production Dockerfile, mounts operator-supplied file Vault read-only at
`/opt/keycloak/vault`, and retains the base ports, databases, volumes and theme mounts. It contains
no storage probe or proof secret. The ordinary Figma, daily and production Compose files remain
independent. This runtime requires an existing owned Figma realm; it does not import a realm.

Supply admin credentials through process-local `-AdminUsername` and `-AdminPassword` parameters
on the following commands (omitted here), without logging them. Select an existing Vault directory;
the preparer never generates or rotates its key. Within a Git repository, both the directory and
the actual realm-ID-derived entry must be ignored and the entry must be untracked. An external
directory must be outside Git. Neither directories nor entries may be links/junctions. The
directory and entry must have protected Windows ACLs granting access only to the current operator,
SYSTEM and Administrators; the operator must have read access. The preparer checks these boundaries
before reading Base64 key material, and never prints the key or exports it into the environment.

```powershell
.\scripts\prepare-figma-otp-runtime.ps1 -CheckConfigurationOnly -VaultPath '<existing operator Vault directory>'
# Runtime start requires the controller's separate essential-safety preflight and review.
.\scripts\prepare-figma-otp-runtime.ps1 -VaultPath '<existing operator Vault directory>'
.\scripts\configure-keycloak-email-otp.ps1 -Mode Inspect
.\scripts\configure-keycloak-email-otp.ps1 -Mode Diff
.\scripts\configure-keycloak-email-otp.ps1 -Mode Prepare
# Binding is a separate explicit operation after essential-safety acceptance.
.\scripts\configure-keycloak-email-otp.ps1 -Mode Bind -EnableIsolatedOtp
.\scripts\configure-keycloak-email-otp.ps1 -Mode Restore -SnapshotPath '<saved snapshot>'
```

The exact target is realm name `knora-dev` at `http://127.0.0.1:8380`, Compose project
`knora-figma-e2e`, with container ownership labels matching this script's resolved checkout.
Both scripts reject ambient target selectors. Runtime check-only validates the actual existing
realm ID, Vault filename/key, owned loopback exposure and rendered Compose graph without mutation.
Actual runtime preparation builds/starts only owned Keycloak with `--no-deps`, checks discovery
and provider availability, and verifies that the realm ID and reset binding remain unchanged.
Active proof/proxy containers are rejected; stopped containers from the exact owned checkout are
retained as historical evidence. No container or volume cleanup is performed.

The flow script defaults to read-only Inspect. Prepare creates the custom basic flow
`knora-email-otp-reset` with ownership description `Knora isolated email OTP recovery v1` and
ordered REQUIRED executions `knora-reset-email-otp`, then native `reset-password`. An existing
conflicting alias/order/requirement fails closed. Repeat Prepare is a no-op, and Prepare never
changes the reset binding. Bind requires explicit opt-in, registered providers and enabled native
UPDATE_PASSWORD. Standalone Bind also checks the main container's native image tag, exact command
and entrypoint, base/runtime Compose-file provenance, absence of proof environment, and only the
three reviewed read-only fixture/theme/Vault bind mounts. It rejects active proof/proxy siblings
before creating a snapshot and rechecks native activation immediately before the realm update.
Stopped siblings must have the exact project/checkout ownership. Restore remains available even
if proof exposure has returned, without requiring cleanup. Bind saves the prior reset binding,
email theme, reset-enabled flag and actual
realm ID before changing only those three settings to the custom flow, `knora`, and true.
Restore checks the exact target, checkout and actual realm ID, restores only the saved settings,
and retains the custom unbound flow. Partial errors retain snapshots and report redacted codes;
keep the snapshot until the change has an explicit disposition.

These source commands and executable fake HTTP/Docker checks establish guarded configuration
behavior only. Task 1 does not start/reload a provider, prepare/bind a live flow or update a password.
Native recovery acceptance remains a separate controller-reviewed operation with essential-safety
preflight; deferred deployment hardening, including the blocked outage proof, is not claimed by
this source verification. The existing storage and offline source approvals remain scoped.

Provision a cryptographically generated Base64 key containing at least 32 decoded bytes in
Keycloak Vault. The application lookup entry is `knora-email-otp-hmac-` followed by lowercase
SHA-256 hex of the **actual realm ID**, obtained from the existing realm representation. All nodes
and restarts must resolve the same stable key. No environment, random or plaintext fallback is
supported; missing/malformed/unavailable entries prevent store admission and SMTP.

The [Keycloak 26.3.3 file Vault](https://github.com/keycloak/keycloak/blob/26.3.3/docs/guides/server/vault.adoc)
uses the **realm name** as its physical filename prefix. With the default REALM_UNDERSCORE_KEY
resolver, escape each underscore in the realm name and lookup entry by doubling it, then join
them with one underscore. The ID-qualified application entry adds ID isolation; the native file
provider itself does not supply realm-ID isolation. Realm rename requires coordinating the
physical mapping while retaining the same key. Mount the operator-owned Vault directory read
only and configure `--vault-dir` on every node. Do not bake secrets into the image, theme, realm
export, source tree or logs. This change documents provisioning only; no production or daily
Compose secret/mount is changed. Vault values close after each request; decoded bytes are
cleared after MAC initialization, without claiming complete JVM zeroization.

**Hot rotation is unsupported.** The key also identifies account and IP budgets, so changing it
mid-window creates different identities. Disable recovery on all nodes, drain all in-flight
HTTP and SMTP work, wait a full 15-minute recovery window plus transaction drain, coordinate
replacement and readability across all nodes, then re-enable recovery. SMTP drain is not bounded
by the five-second independent transaction timeout. Mixed-key rolling intervals and fallback
key rings are unsupported. A changed key invalidates older codes; successful node restart alone
must preserve the existing key and budget identities.

The private relational adapter stores keyed digests, stable user IDs and fenced generations in
Keycloak's own database. Five-minute challenges and fixed 15-minute account/IP windows retain
expired rows for a further 24-hour inactivity grace. Admission performs indexed cleanup in
separate batches of at most 100 with locked-row skipping and reference checks. This grace trades
short-term retention for safe stale-operation fencing; opportunistic cleanup does not impose a
hard total-row capacity limit. Custom JPA is an unsupported Keycloak extension API, so schema,
transaction and multi-node proofs must be repeated when upgrading the pinned runtime.

### Isolated native completion client origins (Task 2 source amendment)

The retained isolated `knora-web` client had no base URL, so the native completed `info.ftl`
rendered no trusted Sign in link. The guarded Bind helper now snapshots the actual client ID
and nullable `baseUrl`/`rootUrl`, sets only those two fields to `http://127.0.0.1:3300`, and
verifies the same client ID plus unchanged `redirectUris` and `webOrigins` before binding
recovery. An already-bound no-op requires both origins to match. Restore unbinds the realm
first, then restores the saved client fields. The snapshot retains original null/string values;
pinned Keycloak ignores JSON null URL updates, so restoring null sends an explicit empty string.
Readback treats only null and empty string as equivalent unset values. Whitespace or a nonempty
value is never accepted as unset; nonempty prior values must match exactly. Earlier realm-only
snapshots remain compatible and leave the client untouched. Partial failures retain the snapshot.
This amendment is source verified; a successful native completion CTA and subsequent fresh
credential/MFA login still require the separately bounded runtime journey and review.
