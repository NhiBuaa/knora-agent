# Local development on Windows

Use this workflow for day-to-day development with Cloudflare Workers AI. The stable offline Ollama demo/acceptance launcher remains separate from source-watching development behavior.

For provider-free, disposable coding-agent browser verification, use the
[agent environment](agent-environment.md) and its Feature Map instead of this daily runtime.

## Runtime layout

```text
Windows host
├── Cloudflare Workers AI (backend HTTPS)
├── FastAPI                auto-reload
├── PDF ingestion worker   graceful restart-on-change
├── Conversation worker    processes durable Turns
└── Next.js                Fast Refresh / HMR

Docker Desktop
├── PostgreSQL / pgvector
├── MinIO
└── Keycloak (knora-dev realm)
```

The development launcher uses the dedicated `knora_dev` database by default. It does not reuse the `knora_issue103_demo` database from the stable #103 demo launcher.

## One-time setup

Install dependencies and create the gitignored local environment file:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\backend[dev]"
npm --prefix frontend ci
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Set local-only MinIO credentials and Cloudflare Workers AI account/token in `.env`:

```dotenv
KNORA_OBJECT_STORE_S3_ACCESS_KEY=<local secret>
KNORA_OBJECT_STORE_S3_SECRET_KEY=<local secret>
KNORA_CLOUDFLARE_ACCOUNT_ID=<32-character account ID>
KNORA_CLOUDFLARE_API_TOKEN=<Workers AI token>
```

Generate a random session secret and put it in `.env` as `SESSION_SECRET=<generated value>`:

```powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
[Convert]::ToBase64String($bytes)
```

When OIDC settings are blank, the daily launcher starts the bundled `knora-dev` Keycloak
realm and fills frontend/backend OIDC endpoints. Explicit `.env` or process values are
preserved; when the issuer points to another realm, that Keycloak must already be running.
Set the client ID and both audience values for a custom client. The Compose `api` service
remains tied to the bundled realm for isolated E2E; daily development runs the API on Windows.
The bundled realm's public `knora-web` client allows
`http://127.0.0.1:3000/api/auth/callback`. The local login is `m5-user` /
`m5-user-password`. These are development credentials; do not use this realm for production.

Confirm the account's Workers AI data permission and available free allowance before real use. The launcher does not check billing or make a paid model call during preflight. Keep the token in backend process secrets, never in `NEXT_PUBLIC_` variables or committed files. Keep Docker Desktop running before starting Knora. Root `.env` is loaded once at launcher startup; restart after changing it.

## Configuration reference

Daily development includes registration, sign-in, sign-out and Forgot Password
through real email OTP. Fill the blank values in the root
[`.env.example`](../../.env.example), then save it as the ignored `.env`:

| Group                   | Values to supply                                                          |
| ----------------------- | ------------------------------------------------------------------------- |
| AI, storage and session | Cloudflare account/token, local MinIO access/secret, and `SESSION_SECRET` |
| Email OTP               | `KNORA_OTP_HMAC_KEY`, `KC_SMTP_FROM`, `KC_SMTP_USER`, `KC_SMTP_PASSWORD`  |

The template already sets the local OTP switch to true and supplies Gmail
host/port/TLS/auth settings. The sender and SMTP user usually use the same Gmail
address, but both fields must be filled. Use a Google App Password, not the account
password. Preserve existing MinIO credentials, HMAC key, SMTP settings and session
secret when reusing a configured environment; do not overwrite its `.env`.
Complete [Daily auth setup](#daily-auth-setup-one-time) once to configure the
Keycloak reset flow and SMTP. After setup, daily use needs only `start-dev.ps1`.
Backend/Compose defaults remain unchanged when the template's explicit local OTP
setting is absent; production must keep the local switch off.

Add overrides to `.env` or the process environment only for the mode you use.
Launcher parameters take precedence over the process environment, which takes
precedence over `.env`. Leave optional numeric variables unset instead of assigning
empty strings. Updating the template must not change another session's `.env` or
restart its runtime.

### Defaults and values supplied by the launcher

| Variable                                                                                                           | Usage / default                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `KNORA_EMBEDDING_PROVIDER`, `KNORA_GENERATION_PROVIDER`                                                            | The daily launcher defaults both to `cloudflare-workers-ai`; select both as `ollama` for offline use or `deterministic-local` for simulation. Direct backend invocation requires both selectors to be set or both unset.                                                                                                                                        |
| `KNORA_PROVIDER_MODE`                                                                                              | Direct backend/CI defaults to `deterministic-local` when the selector pair is absent; compatibility modes remain available for evaluation. The daily launcher selects the pair independently, so this variable does not select its provider.                                                                                                                    |
| `KNORA_DATABASE_URL`                                                                                               | Settings defaults to `postgresql+psycopg://knora:knora@localhost:5432/knora`; the daily launcher derives it from `-DatabaseName` (default `knora_dev`) and `-PostgresPort` (5432). Set an explicit URL only for direct backend invocation or `start-ollama-demo.ps1 -UseExistingStorage` with a verified target.                                                |
| `KNORA_EMBEDDING_DIMENSION`, `KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID`, `KNORA_EXPECTED_GENERATION_MODEL_DIGEST` | The launcher resolves and pins these values; do not enter them manually when using it. Direct backend invocation defaults to dimension 1536; Cloudflare/Ollama require 1024 and the matching profile; Ollama generation requires a verified real digest.                                                                                                        |
| `KNORA_API_URL`, `KNORA_BACKEND_URL`, `NEXT_PUBLIC_APP_ORIGIN`                                                     | The daily launcher derives these from the API/frontend ports, defaulting to 8000/3000. Never put provider secrets in `NEXT_PUBLIC_` variables.                                                                                                                                                                                                                  |
| `KEYCLOAK_AUTHORIZATION_URL`, `KEYCLOAK_TOKEN_URL`, `KEYCLOAK_JWKS_URL`, `KEYCLOAK_ISSUER`                         | The daily launcher supplies endpoints for `http://127.0.0.1:8180/realms/knora-dev` when unset. An external issuer requires a running realm; endpoints follow that issuer unless explicitly overridden.                                                                                                                                                          |
| `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_AUDIENCE`, `KNORA_KEYCLOAK_AUDIENCE`                                               | The bundled client is `knora-web`; the backend audience defaults to the frontend audience. For an external client, configure the client ID and both audiences to match the realm.                                                                                                                                                                               |
| `KNORA_KEYCLOAK_ISSUER`, `KNORA_KEYCLOAK_JWKS_URL`                                                                 | The daily launcher takes these from frontend OIDC settings when unset. Frontend/backend issuers must match; direct backend invocation does not enable bearer validation automatically when configuration is missing.                                                                                                                                            |
| `KEYCLOAK_CLIENT_SECRET`                                                                                           | Required only for an external confidential client; the bundled public client does not need it.                                                                                                                                                                                                                                                                  |
| `KEYCLOAK_REDIRECT_URI`, `KEYCLOAK_POST_LOGOUT_REDIRECT_URI`                                                       | Daily launcher defaults are `http://127.0.0.1:3000/api/auth/callback` and `http://127.0.0.1:3000/`; `-FrontendPort` updates both. They must match the client's allowlist.                                                                                                                                                                                       |
| `KNORA_KEYCLOAK_JWKS_CACHE_TTL_SECONDS`                                                                            | Backend default: 300 seconds; override only when needed.                                                                                                                                                                                                                                                                                                        |
| `KNORA_API_CREDENTIALS_JSON`                                                                                       | Backend default: `[]`; used only for API-key CLI/integration, not required for the browser bearer flow. Contains `key_id`, hash, Workspace and enabled fields as defined in [architecture](../standards/architecture.md#authentication-and-workspace-authorization); never store raw API keys in this JSON.                                                     |
| `KNORA_RETRIEVAL_CONFIGURATION_ID`, `KNORA_VECTOR_MIN_SIMILARITY`                                                  | Default: `retrieval-m1-v1`, without a threshold override. Opt-in containment uses `retrieval-evidence-containment-v1`; rollback uses `retrieval-m1-v1`. See the [acceptance runbook](evidence-containment-acceptance.md). V2 accepts only its calibrated threshold/profile; do not use it for Cloudflare merely because dimensions or scores appear compatible. |

### Optional providers

Cloudflare retains fixed native Qwen3 embedding and GPT-OSS generation; daily use
does not require model/profile input. `KNORA_CLOUDFLARE_TIMEOUT_SECONDS` defaults to
60 seconds. Overrides for `KNORA_CLOUDFLARE_EMBEDDING_MODEL`,
`KNORA_CLOUDFLARE_EMBEDDING_CONFIGURATION_ID` and `KNORA_CLOUDFLARE_GENERATION_MODEL`
are accepted only when they match the current fixed profile. Changing the model or
embedding space requires an approved new configuration and controlled re-indexing.

For offline Ollama, use [Provider selection](#provider-selection-and-explicit-simulation)
and the [stable offline runbook](local-ollama.md). Supported overrides:

| Variable                                                                  | Default                                                                                                                       |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `KNORA_OLLAMA_BASE_URL`                                                   | Launcher: `http://127.0.0.1:11434`; direct Settings: `http://localhost:11434`. The launcher accepts only loopback endpoints.  |
| `KNORA_OLLAMA_EMBEDDING_MODEL`                                            | `qwen3-embedding:0.6b`, fixed profile; the launcher resolves its digest/metadata.                                             |
| `KNORA_OLLAMA_GENERATION_MODEL`                                           | `qwen3:8b`; an already pulled `qwen3:4b` or `gpt-oss:20b` can also be selected. Template cleanup does not change the default. |
| `KNORA_OLLAMA_TIMEOUT_SECONDS`, `KNORA_OLLAMA_GENERATION_TIMEOUT_SECONDS` | 60 and 120 seconds; overrides must be positive numbers.                                                                       |

Gemini, OpenAI-compatible and the semantic scorer retain compatibility/evaluation
callers; see [provider/scorer variables](../evaluation.md#provider-and-scorer-configuration).
The application provider and judge are separate roles; selecting Cloudflare for
daily use does not select a judge or change the model-backed evaluation contract.

### Storage, Compose, operations and OTP

| Variable                                                                                                               | Usage / default                                                                                                                                                                                                                                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `KNORA_OBJECT_STORE_BACKEND`, `KNORA_OBJECT_STORE_ROOT`                                                                | Direct backend defaults: `filesystem`, root `.knora-objects`. The daily launcher selects `s3_compatible` with local MinIO.                                                                                                                                                                                                                                   |
| `KNORA_OBJECT_STORE_S3_ENDPOINT`, `KNORA_OBJECT_STORE_S3_BUCKET`, `KNORA_OBJECT_STORE_S3_REGION`                       | No direct backend defaults; S3 requires a bucket, credentials and the service endpoint. The daily launcher uses `http://127.0.0.1:9000`, bucket `knora` (or `-ObjectStoreBucket`/environment), and region `us-east-1` when unset. The stable launcher supports `-ObjectStoreEndpoint` and `-UseExistingStorage`; see the [offline runbook](local-ollama.md). |
| `KNORA_CANONICAL_MINIO_ACCESS_KEY`, `KNORA_CANONICAL_MINIO_SECRET_KEY`                                                 | Compose credential names; the launcher prefers this pair, then falls back to `KNORA_OBJECT_STORE_S3_ACCESS_KEY`/`KNORA_OBJECT_STORE_S3_SECRET_KEY` from the template. Do not fill both pairs. Direct Compose invocation requires the canonical pair in the process environment or `.env`; preserve credentials for existing volumes.                         |
| `KNORA_PROVIDER_TEST_ACCESS_KEY`, `KNORA_PROVIDER_TEST_SECRET_KEY`                                                     | Only for the `provider-test` profile in `docker-compose.dev.yml`, with credentials separate from daily use. Not required for normal startup.                                                                                                                                                                                                                 |
| `KNORA_OBJECT_INVENTORY_MANIFEST`, `KNORA_OBJECT_INVENTORY_MINIMUM_AGE_SECONDS`                                        | Operations: optional JSONL inventory path; minimum age defaults to 86400 seconds. An inventory scanner is not supplied automatically when the manifest is unset.                                                                                                                                                                                             |
| `KNORA_OPERATIONAL_ALERT_CONFIGURATION_JSON`, `KNORA_OPERATIONAL_METRICS_RETRY_WINDOW_SECONDS`                         | Optional versioned alert configuration; retry metric window defaults to 300 seconds. See [operational observability](../standards/architecture.md#asynchronous-pdf-ingestion).                                                                                                                                                                               |
| `KNORA_OTP_LOCAL_DEV_ENABLED`, `KNORA_OTP_HMAC_KEY`                                                                    | The daily template explicitly sets the local switch to true; Compose still defaults to false when it is unset. The key must be canonical Base64 containing at least 32 decoded bytes and must persist across restarts. Production uses Vault/secret manager when the switch is off.                                                                          |
| `KC_SMTP_HOST`, `KC_SMTP_PORT`, `KC_SMTP_FROM`, `KC_SMTP_USER`, `KC_SMTP_PASSWORD`, `KC_SMTP_STARTTLS`, `KC_SMTP_AUTH` | Required for daily Forgot Password; apply once through guarded SMTP setup. Gmail host `smtp.gmail.com`, port 587, STARTTLS/auth true, and sender/user/password from an authorized development account. Leaving them unset does not configure SMTP automatically. Mailpit is only for isolated tests/CI.                                                      |

OTP/SMTP requires the procedure in [Daily auth setup](#daily-auth-setup-one-time)
and the [guarded migration](../development/keycloak-theme.md#primary-email-otp-migration).
Updating the template must not generate keys, change key sources, enable flows or
restart an active realm. Existing profiles/datasets/evidence retain their identity
and content.

## Start daily development

### Daily auth setup (one-time)

For an already configured daily environment, keep its `.env`, HMAC key and SMTP
settings and skip setup. Registration, sign-in, sign-out and Forgot Password are
all part of daily use; OTP is not a separate optional feature.

For a fresh environment:

1. Copy `.env.example` to `.env` only if `.env` does not exist, and fill both groups
   in the configuration reference above. The four Gmail defaults and local OTP
   switch are already set. Enable Google 2-Step Verification and use a Google App
   Password for `KC_SMTP_PASSWORD`; `KC_SMTP_FROM` must be an authorized sender.
2. Generate a session secret and an OTP HMAC key separately, only for a new
   environment. Use the session-secret command under [One-time setup](#one-time-setup).
   For `KNORA_OTP_HMAC_KEY`, generate canonical padded Base64:

   ```powershell
   .\.venv\Scripts\python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
   ```

   Put the result in the HMAC field. Never generate replacement values for an
   existing configured environment.

3. Open Docker Desktop, then run `.\scripts\start-dev.ps1` from the repository root.
   Keep that terminal open. Once startup finishes, Keycloak is running, but entering
   SMTP values in `.env` alone has not configured the realm's reset flow or SMTP.
4. Open a second PowerShell terminal at the same repository root. For a fresh
   bundled realm with unchanged bootstrap credentials, run:

   ```powershell
   $otpAdmin = @{
       BaseUrl = 'http://127.0.0.1:8180'
       Project = 'knora-dev'
       AdminUsername = 'knora-dev-admin'
       AdminPassword = 'knora-dev-admin-password'
   }
   .\scripts\configure-keycloak-email-otp.ps1 -Mode Prepare -EnablePrimaryOtp @otpAdmin
   .\scripts\configure-keycloak-email-otp.ps1 -Mode Bind -EnablePrimaryOtp -ConfigurePrimarySmtp @otpAdmin
   ```

   Use the existing admin credentials for a custom/existing realm instead; never
   reset them to match this example. The guarded script loads SMTP values from the
   ignored root `.env`, prepares the reset flow and binds it with a rollback
   snapshot. Expect `OTP_FLOW_PREPARED_UNBOUND` (or `OTP_FLOW_ALREADY_PREPARED`) and
   `OTP_BIND_VERIFIED` (or `OTP_BIND_ALREADY_SET`). Stop if either command fails.
   Existing SMTP changes may require the previous password for rollback; follow
   the [guarded migration](../development/keycloak-theme.md#primary-email-otp-migration)
   rather than bypassing its checks.

5. Open `http://127.0.0.1:3000`, register a dedicated development account using an
   inbox you control, sign out, then use Forgot Password. Receive the OTP, set a new
   disposable password and sign in with it. Only observed delivery and successful
   recovery confirm the complete flow. The fixture `m5-user@example.test` cannot
   receive real mail.

After this one-time setup, start daily development with
`.\scripts\start-dev.ps1`. Do not repeat realm binding or key generation each day.
The launcher does not configure SMTP automatically or verify real mail delivery;
`-PreflightOnly` is only a provider/PDF configuration check.

#### Existing runtime and key safety

Local Keycloak does not enable or mount file-vault. The daily template explicitly sets
`KNORA_OTP_LOCAL_DEV_ENABLED=true` and requires `KNORA_OTP_HMAC_KEY` only in the ignored root `.env`.
Use canonical padded Base64 encoding of at least 32 random bytes. Preserve the same key across
restarts; missing or invalid keys fail closed without Vault/random fallback. The old
`KNORA_PRIMARY_OTP_VAULT_PATH` setting is unused and can be removed.

For an existing Vault-backed runtime, preserve its current key or schedule an approved rotation
before changing the source. After upgrading the local image/configuration, rebuild and recreate
Keycloak in your own dev project to remove the old mount; `docker compose restart` alone does not
apply a changed environment or service configuration. Follow the
[Email OTP configuration guide](../development/keycloak-theme.md) for the guarded realm migration.
SMTP/App Passwords are unchanged. Production keeps its Vault/secret-manager source with the local
switch off; provider selection and hardening remain in Issue #152.

#### Manual Email OTP smoke with Gmail SMTP

Daily development and manual acceptance use the configured Gmail SMTP service. Mailpit remains
only in isolated automated tests/CI; the daily launcher does not start it. A green Mailpit test
does not prove delivery to a real mailbox.

Use a dedicated development account with a mailbox you control and a disposable password.
The bundled `m5-user@example.test` fixture cannot receive real Gmail delivery. The primary realm
must already have the custom Email OTP reset flow and Gmail SMTP configured through the
[guarded migration](../development/keycloak-theme.md#primary-email-otp-migration). Preserve the
existing SMTP/App Password and HMAC key; do not generate a replacement key for this smoke.

1. In ignored root `.env`, set `KNORA_OTP_LOCAL_DEV_ENABLED=true` and retain the valid
   `KNORA_OTP_HMAC_KEY`. Remove the unused `KNORA_PRIMARY_OTP_VAULT_PATH` setting if present.
   Use a PowerShell session without OTP environment overrides, because process values take
   precedence over `.env`. Confirm the file is ignored with `git check-ignore .env`.
2. In your own dev runtime maintenance window, with `keycloak-dev-db` already running, rebuild
   and recreate only Keycloak to apply the updated image, environment and removed Vault mount:

   ```powershell
   Set-Location C:\Developer\Projects\knora-agent
   $compose = @('-p', 'knora-dev', '-f', 'docker-compose.dev.yml')
   docker compose @compose config --quiet
   docker compose @compose up -d --build --force-recreate --no-deps --wait keycloak-dev
   ```

   Check mount destinations only; the output must not contain `/opt/keycloak/vault`:

   ```powershell
   $containerId = docker compose @compose ps -q keycloak-dev
   docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' $containerId
   ```

   Resolved Compose configuration and full container inspection contain secrets; do not print
   or retain them. Coordinate this restart with anyone sharing the runtime; it interrupts active
   authentication sessions. No other project's containers or volumes need changing.

3. Open `http://127.0.0.1:3000`, choose sign in, then **Forgot password**. Submit the dedicated
   account's email and confirm an OTP arrives in its real inbox (also check spam).
4. Enter one incorrect code and confirm rejection. Then enter the received code before expiry,
   set a new disposable password, and confirm a fresh sign-in succeeds with it and rejects the
   previous password. Record only pass/fail, time and tested commit; never the OTP, passwords,
   keys, mailbox content or authentication URL.
5. Leave `.env` unchanged and restart only `keycloak-dev`:

   ```powershell
   docker compose @compose restart keycloak-dev
   ```

   Wait for Keycloak to become ready, open a new reset transaction, and repeat delivery/verification.
   Full restart of single-node `start-dev` loses the previous native authentication session.
   Verification of an OTP issued before a rolling restart has separate
   [recorded isolated evidence](https://github.com/NhiBuaa/knora-agent/issues/159#issuecomment-6145207522).
   Invalid/missing keys and production source separation are covered by the automated provider
   tests; do not corrupt the shared runtime's key to exercise those negative cases manually.

### Launch

From the repository root:

```powershell
.\scripts\start-dev.ps1
```

Optional preflight without starting storage or application processes:

```powershell
.\scripts\start-dev.ps1 -PreflightOnly
```

The development launcher:

1. loads root `.env` without overwriting explicit process environment values;
2. validates the selected backend provider pair, native Cloudflare model/profile and credential settings, immutable profile pin and the Windows PDF Job Object safety path; Ollama selections additionally check local model metadata and a 1024-value embedding response;
3. starts PostgreSQL and MinIO through Docker Compose under the `knora-dev` project, plus bundled Keycloak when its default realm is selected, and waits for readiness;
4. creates/migrates the `knora_dev` database;
5. starts FastAPI with Uvicorn auto-reload for `backend/src/knora`;
6. starts the ingestion worker in `--dev-watch` mode and the Conversation Turn worker;
7. starts Next.js with its normal development server and Fast Refresh;
8. stays in the foreground as the supervisor for all four host processes.

Press `Ctrl+C` to stop API, both workers and frontend. PostgreSQL, MinIO and Keycloak intentionally remain running so the next development start is faster. Restart the launcher after changing Conversation worker source; only the PDF worker has safe source-watch restarts.

### Provider selection and explicit simulation

If startup reports `PORT_IN_USE:ApiPort:8000` or `PORT_IN_USE:FrontendPort:3000`,
stop the previous daily supervisor with Ctrl+C before starting another one. The launcher
checks occupied ports before modifying services or logs and leaves existing processes alone.
If the old supervisor has already exited, inspect the listening process and its parent before
stopping it; do not stop every Node/Python process on the machine.

Daily development selects `cloudflare-workers-ai` for both roles: native
`@cf/qwen/qwen3-embedding-0.6b` under `embedding-cloudflare-qwen3-06b-v1` (1024
dimensions) and `@cf/openai/gpt-oss-20b` generation. The preflight prints the
selected pair/profile without sending text to Cloudflare. Missing credentials,
unsupported model or profile, and PDF isolation failure stop before services change.
The API and workers inherit the pinned selection. Process environment overrides
`.env`, and command parameters override both; clear stale process selectors before
restarting if the preflight shows an unexpected pair.

Use the stable [offline Ollama runbook](local-ollama.md) for its digest-pinned demo.
To choose Ollama in the daily launcher, select both roles explicitly, for example
with a local CPU endpoint:

```powershell
.\scripts\start-dev.ps1 -EmbeddingProvider ollama -GenerationProvider ollama -OllamaBaseUrl http://127.0.0.1:11435
```

For Ollama, first pull `qwen3-embedding:0.6b` and a supported generation model
(`qwen3:8b`, `qwen3:4b` or `gpt-oss:20b`). `-GenerationModel` selects the Ollama
generation model; missing models or invalid digests stop preflight, and the
resolved generation digest is pinned. Selecting only `-GenerationProvider ollama`
keeps Cloudflare embedding, so select both for fully offline use.

For UI simulation or CI, select both deterministic roles explicitly:

```powershell
.\scripts\start-dev.ps1 -EmbeddingProvider deterministic-local -GenerationProvider deterministic-local
```

Deterministic output copies evidence and cannot establish model answer quality.
Restart the full launcher after provider/model changes; auto-reload does not refresh
the parent environment. Submit a new Turn and verify its server trace records the
selected provider/model/profile, then inspect facts, citations and refusal. Old
Turns remain unchanged. Successful preflight does not certify answer quality.

The conversation-approved 120B trial has not qualified a model replacement. Application
bootstrap retains `@cf/openai/gpt-oss-20b`; low-level 120B transport tests are diagnostic only.
Malformed output remains rejected. Owner-approved Retrieval V3 recovery can correct generation
or verifier format, or regenerate an unsupported answer from the same source snapshot with
specific feedback. Unsupported extra statements can be removed, followed by fresh verification
of the entire remaining answer and all required question parts. It stops on repeated failed
content, provider unavailability or deadline;
there is no provider fallback and no unverified final answer. Per-call safe observations are in
`QuestionTrace.provider_metadata.generation_recovery`; malformed generation also retains a trace.
Verification selects exact supporting quotes, then independently checks whether they
establish each complete claim. Each call is capped at 60 seconds within the same
90-second question pipeline; the second call does not reset that deadline.
Provider/model changes require restarting the full launcher and checking fresh trace
model/prompt identities. Paid AI use requires its own authorization; the Issue #153
owner granted reasonable paid use and conditional 120B integration in the Codex
conversation on 2026-10-29. This is not release acceptance or deployment approval.

### Re-index a retained corpus for Cloudflare

Only the operator of an isolated, quiesced target corpus should run this workflow.
Stop writers to that target, review the selected Workspaces and source data permission,
and keep a recoverable backup. Set `KNORA_DATABASE_URL` explicitly in the operator
process; the CLI refuses an implicit database target. Inventory is read-only by
default and includes archived Documents:

```powershell
$env:KNORA_DATABASE_URL = '<reviewed target database URL>'
.\.venv\Scripts\python scripts/reindex-cloudflare.py --workspace-id <workspace UUID>
```

Resolve every blocker before applying. A current PDF with retained source and a
terminal `PDF_TEXT_INSUFFICIENT` outcome can be excluded only by its reviewed Document
ID with `--approve-unindexable-id <Document UUID>`. Carry the same Workspace and
approved exclusion arguments through inventory, apply and cleanup. After checking
the data permission and free allowance, add `--apply --acknowledge-data-permission
--acknowledge-free-quota` to stage Cloudflare vectors and atomically activate full
eligible coverage. The apply step makes live embedding calls and has no automatic
budget or paid-tier upgrade. Verify authorized answers, citations, refusals and
source/version provenance end to end before a separate fresh inventory and
`--cleanup --e2e-confirmed`. Cleanup removes obsolete vector rows for the selected
eligible Documents; it retains sources, versions, Chunk Sets, Embedding Sets and
traces. Do not run apply/cleanup while writers can change the target population.

Before running the isolated M5 E2E workflow, stop the daily services. Both projects
use host ports 5432, 9000 and 8180; the E2E preparation script refuses to reset its
own fixtures while the daily project is running. The daily volumes remain intact:

```powershell
docker compose -f docker-compose.dev.yml -p knora-dev stop postgres minio keycloak-dev
```

Prepare the E2E project with the standalone dev Compose file:

```powershell
.\scripts\prepare-local-e2e.ps1 -CheckConfigurationOnly
.\scripts\prepare-local-e2e.ps1
```

The first command checks configuration without starting services. The second temporarily
sets test-only credentials and enables the E2E fault seam, starts the separate
`knora-m5-e2e` Compose project, then checks real Keycloak tokens and API authorization.
It restores the caller's environment when it returns and does not edit root `.env` or
start Playwright. Run the browser suite
after its readiness check using the M5 E2E environment values required by
`frontend/playwright.config.ts`.

When finished, stop the E2E services before restarting daily development:

```powershell
docker compose -f docker-compose.dev.yml -p knora-m5-e2e stop postgres minio api keycloak-dev
.\scripts\start-dev.ps1
```

Routine shutdown does not remove the development volumes.

## Reload behavior

### Frontend

Next.js owns frontend refresh behavior:

```text
edit .tsx / .ts / CSS
→ Fast Refresh / HMR
→ browser updates
```

A frontend edit does not restart the API or ingestion worker.

### FastAPI

Uvicorn watches `backend/src/knora`:

```text
edit backend Python
→ Uvicorn reloads the API process
→ API becomes healthy again with the new code
```

The Uvicorn reloader stays separate from the ingestion-worker lifecycle.

### Ingestion worker

The worker watches Python source but never treats a source change as permission to kill an admitted job.

If idle:

```text
source change
→ restart requested
→ worker exits with the dedicated dev-restart code
→ supervisor starts a fresh worker
```

If processing a job:

```text
PDF A running
→ source change
→ restart requested
→ PDF A finishes through the normal durable/fenced path
→ worker does not claim PDF B
→ worker exits cleanly
→ supervisor starts a fresh worker using the new code
```

Multiple source changes while draining collapse into one pending restart. Unexpected worker crashes are surfaced as development-runtime failures instead of being hidden behind an infinite restart loop.

The lease/fencing/recovery mechanisms remain failure safeguards; normal development reload does not intentionally exercise those crash paths.

## Stable demo / acceptance remains separate

Use:

```powershell
.\scripts\start-ollama-demo.ps1
```

for the stable Ollama PDF re-index demo and acceptance path. That launcher does not enable API auto-reload or worker source watching. This keeps #103 verification reproducible while `start-dev.ps1` optimizes the daily edit-run loop.

## Logs and ports

### Browser session renewal

After upgrading from the old access-token-only session, sign in once through
`/api/auth/login` to obtain a renewable session. Existing cookies remain readable,
but cannot acquire a refresh token retroactively.

The Next.js server retains access and refresh tokens in an encrypted HttpOnly,
SameSite=Lax cookie (Secure in production). Before forwarding a protected API
request, it renews an access token with 30 seconds or less remaining. Protected
page middleware renews and persists the cookie before server rendering; rendering
itself never consumes a refresh token. Refresh verifies the Keycloak issuer,
audience and original subject, and re-reads capabilities from the validated ID token.
Tokens never appear in the session JSON or browser JavaScript storage, and the
session cookie is not forwarded to FastAPI.

Keycloak controls idle expiry and revocation; Knora additionally caps one browser
session at eight hours. Temporary refresh failures return a retryable 503 without
forwarding or replaying a Turn POST. A rejected refresh requires sign-in again;
the Conversation recovery controls preserve its mounted draft and idempotency key.
Logout invalidates the local session before starting Keycloak browser logout.

The current coordinator deduplicates refreshes within one Next.js server process,
keeps results for 30 seconds for concurrent requests, and bounds that cache to 256
entries. Daily dev runs this topology. Multiple frontend replicas require shared
refresh coordination and shared logout revocation before rotated refresh tokens
are enabled; process-local coordination is not evidence for that release gate.
Do not extend Keycloak timeouts or disable refresh-token rotation to hide failures.

Protocol reference: [Keycloak OpenID Connect endpoints](https://www.keycloak.org/securing-apps/oidc-layers).

Defaults:

```text
Frontend  http://127.0.0.1:3000
API       http://127.0.0.1:8000
Postgres  127.0.0.1:5432
MinIO     http://127.0.0.1:9000
```

Development logs are written beneath:

```text
%TEMP%\knora-dev-runtime
```

Each worker restart gets generation-specific log files so the previous generation is not silently overwritten.

On Windows, each launcher invocation owns one Job Object containing the API,
frontend, both workers and their child processes. Processes join before their
first instruction runs, so cleanup still owns descendants after a shell or worker
has exited. Ctrl+C and startup failures force-stop this group and wait up to ten
seconds for it to empty. `DEV_STOPPED` confirms cleanup; `DEV_CLEANUP_FAILED`
reports a termination, accounting or timeout failure. PostgreSQL, MinIO and
bundled Keycloak remain running, and processes from other invocations stay outside
the group. A port occupied by another session still fails the preflight check.

### Multi-launcher safety and storage protection

To prevent concurrent development sessions from colliding or corrupting persistent
data, the daily launcher enforces three preflight safety guards:

- **Project reservation lock**: Before verifying storage or starting services, the
  launcher acquires an exclusive file lock at
  `%TEMP%\knora-dev-reservation-knora-dev.lock`. A concurrent second launcher on
  the same machine and user immediately aborts with `DEV_PROJECT_RESERVED:knora-dev`
  before inspecting or altering shared Docker resources. The refusal diagnostics print
  `DEV_RESERVATION_PATH` and the recovery runbook reference; if the lock file is readable
  on disk, the recorded owner PID (`DEV_RESERVATION_OWNER_PID`) and timestamp
  (`DEV_RESERVATION_TIMESTAMP`) are output without dumping arbitrary content or secrets.
  Normal shutdown (Ctrl+C) and clean preflight aborts release the lock automatically.
  If startup fails after mutating operations begin or cleanup cannot be verified cleanly,
  the lock file is intentionally retained on disk with process and timestamp metadata,
  printing `DEV_RESERVATION_RETAINED:knora-dev`. Subsequent invocations are blocked until
  an operator inspects for orphaned processes/containers and manually removes the file.
- **Storage ownership verification**: The launcher queries the Docker daemon volume
  catalog (`docker volume ls`) and reconciles expected storage volumes
  (`knora-dev_knora_postgres_data`, `knora-dev_knora_minio_data`,
  `knora-dev_keycloak_dev_data`, `knora-dev_keycloak_dev_database`). If a volume is
  present on the daemon but `docker volume inspect` fails or returns empty metadata,
  the launcher refuses to proceed with `COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev`.
  Furthermore, container mounts are checked against an exact specification: mount type
  must be `volume`, `Destination` must match the canonical container mount path (e.g.
  `/var/lib/postgresql/data` for Postgres and Keycloak DB, `/data` for MinIO,
  `/opt/keycloak/data` for Keycloak), and each volume must possess its matching
  `com.docker.compose.volume` role label. Existing storage is never modified or reset;
  `down --volumes` is never invoked by the daily launcher, preserving development
  PostgreSQL and MinIO data across restarts.
- **Docker metadata read timeout**: Preflight Docker metadata queries are bounded to
  10 seconds per command and 30 seconds for the entire ownership scan using a continuous
  stopwatch deadline covering both process execution and file-buffered output consumption.
  Each metadata process is launched directly inside a Windows Job Object (`Knora.Dev.ProcessJob`)
  with breakaway disallowed (`JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0`). If the Docker daemon hangs
  or child processes spawn long-lived descendants holding pipes or handles, closing the Job Object
  upon timeout forcefully terminates the entire process tree without blocking on streams,
  hanging the shell, freezing CI runners, or leaving orphaned descendant processes.

#### Recovery triage (preserve retained data)

These steps describe the current `scripts/start-dev.ps1` guards. Read-only diagnosis
and mocked launcher tests do not prove a live recovery. Commands with side effects
below require an owned maintenance window, a recoverable backup and rechecking the
observed state immediately before acting. Stop on unavailable metadata or ambiguous
ownership; a matching project name alone does not establish ownership.

From the checkout that originally created the daily project, inspect only relevant
metadata (full `docker inspect`/resolved Compose output can expose secrets):

```powershell
$devCompose = @('-p', 'knora-dev', '-f', 'docker-compose.dev.yml')
$devIds = @(docker ps -a --filter label=com.docker.compose.project=knora-dev --quiet)
foreach ($id in $devIds) {
    docker inspect --format '{{.Id}} {{.State.Running}} {{index .Config.Labels "com.docker.compose.service"}} {{index .Config.Labels "com.docker.compose.project.working_dir"}}' $id
    docker inspect --format '{{json .Mounts}}' $id
    docker inspect --format '{{json .NetworkSettings.Ports}}' $id
}
docker volume ls --filter label=com.docker.compose.project=knora-dev --format '{{.Name}}'
docker volume inspect knora-dev_knora_postgres_data --format '{{.Name}} {{index .Labels "com.docker.compose.project"}} {{index .Labels "com.docker.compose.volume"}}'
```

Require successful command exits and compare the creating checkout, service, labels,
mount type/name/destination and bindings with the guard above. The PostgreSQL role is
`knora_postgres_data`, mounted at `/var/lib/postgresql/data`; its internal port stays 5432. Inspect the other expected volumes too if implicated. Do not publish user-local
paths or secret output in evidence.

**Retained reservation file.** Inspect the recorded owner locally:

When a launcher is refused with `DEV_PROJECT_RESERVED:knora-dev`, diagnostics report:

- `DEV_RESERVATION_PATH:<path>`: filesystem path to the reservation lock file.
- `DEV_RESERVATION_RUNBOOK:docs/runbooks/local-development.md#recovery-triage-preserve-retained-data`: reference to this recovery procedure.
- If readable on disk (orphaned or retained lock from an exited process), `DEV_RESERVATION_OWNER_PID:<pid>` and `DEV_RESERVATION_TIMESTAMP:<timestamp>` report the recorded holder.
- If the file is currently held exclusively by an active launcher process, owner metadata is omitted so unverified or concurrent writes are not read.

```powershell
$devLock = Join-Path ([IO.Path]::GetTempPath()) 'knora-dev-reservation-knora-dev.lock'
Get-Content -LiteralPath $devLock
# Substitute the recorded PID; inspect ancestry locally, without publishing arguments.
Get-CimInstance Win32_Process -Filter 'ProcessId = <recorded PID>' |
    Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath
Get-NetTCPConnection -State Listen -LocalPort 8000,3000 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Include any originally selected custom ports. Correlate reservation REPO/PROJECT,
PID start time (PIDs can be reused), parent/descendant processes, owned logs and the
container inventory. Age or an absent PID alone is insufficient: retained containers
or surviving children may still be in use. An unreadable file may still be held by a
live launcher. Coordinate with the recorded owner and quiesce its runtime. Only after
proving no valid launcher or orphaned host process remains, understanding any retained
storage state and excluding concurrent starts, remove that exact file in the owned
maintenance window: `Remove-Item -LiteralPath $devLock`. Retry the authorized launcher
once; `DEV_PROJECT_RESERVED:knora-dev` still means stop and investigate. Never clear an
active lock or delete storage to make the reservation pass.

**PostgreSQL port occupied.** Inspect the selected port and its owner:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5432 |
    Select-Object LocalAddress, LocalPort, OwningProcess
# For the owned PostgreSQL container identified above:
$devPostgres = docker compose @devCompose ps -a -q postgres
docker inspect --format '{{.State.Running}} {{json .NetworkSettings.Ports}}' $devPostgres
```

The guard permits reuse only when the running PostgreSQL container belongs to this
checkout/project, every storage check succeeds and its sole binding is
`127.0.0.1:<selected port>` to `5432/tcp`. A stopped container or another stack/process
is not reuse authority. `PORT_IN_USE:PostgresPort:<port>` can also mask failed ownership
checks when that port is occupied; inspect both, and leave foreign processes alone.

For an owned project whose existing PostgreSQL container needs a different host port,
stop its launcher and coordinate all database clients first. Check the new port is free,
preserve the volume identity/backup, image and original checkout/Compose configuration.
Use the proposed port only to inspect the resolved Compose configuration and image:

```powershell
# Example only: confirm 5433 is free before choosing it.
$env:KNORA_EVAL_POSTGRES_HOST_PORT = '5433'
$devPostgresImage = docker inspect --format '{{.Image}}' $devPostgres
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify the existing PostgreSQL image' }
$devConfig = docker compose @devCompose config --format json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Invalid Compose configuration' }
$devConfiguredImage = docker image inspect --format '{{.Id}}' $devConfig.services.postgres.image
if ($LASTEXITCODE -ne 0 -or $devConfiguredImage -ne $devPostgresImage) {
    throw 'PostgreSQL image changed or is unavailable; stop for an approved image-preserving plan'
}
```

Keep the original authorized environment/secret inputs; do not invent missing values.
Restore any previous process override after inspection. **Stop here for the daily
launcher:** this is diagnosis, not a verified recovery procedure for `knora-dev`.
Request a data-owner-approved recovery plan before changing its container or clients.
That plan must preserve the exact image ID and volume name/destination, prohibit concurrent
pull/retag/start, recreate only the owned PostgreSQL service without dependencies or image
pulls, and verify the retained mount, image, data/schema, readiness and sole loopback binding
afterward. A failed check keeps clients stopped. `restart` alone does not apply a changed
port mapping ([Compose up reference](https://docs.docker.com/reference/cli/docker/compose/up/)).

The plan must also align the Compose host-port override, subsequent launcher
`-PostgresPort` and authorized host database clients; the launcher sets
`KNORA_DATABASE_URL` for its API/workers itself. Container-to-container clients keep
service port 5432. A disposable Compose trial can demonstrate port recreation with a
retained volume and synthetic data; it does not prove daily-launcher, retained-lock or
orphan-volume recovery. Those live recovery paths remain unverified. Missing container
or unknown mount ownership follows the next case.

**Volume remains but its container is missing.** List all containers mounting the
specific retained volume, including containers outside the daily project:

```powershell
docker ps -a --filter volume=knora-dev_knora_postgres_data --format '{{.ID}} {{.Names}}'
docker volume inspect knora-dev_knora_postgres_data --format '{{.Name}} {{index .Labels "com.docker.compose.project"}} {{index .Labels "com.docker.compose.volume"}}'
```

A retained volume without its verified service mount fails the guard even when its
labels look right (`COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev` when the selected
PostgreSQL port is free). Do not run the port-recreation recipe, automatically adopt
that volume, reset the database or use `down --volumes`. The launcher has no verified
automatic recovery for this case. Stop and request an explicit recovery plan from the
data owner: provenance/backup, quiesced clients, exact original image/configuration,
service-to-volume mapping, approved recreation and post-recovery mount/data/schema checks.
If provenance is missing, keep the volume intact and report the blocker. Do not bypass
the guard or describe container recreation as verified data recovery.

The helper uses the Windows [Job Object API](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
and loads through PowerShell's `Add-Type`; it requires no additional dependency.

Use `-ApiPort`, `-FrontendPort`, `-PostgresPort`, `-PythonExe`, `-OllamaBaseUrl`, `-EnvFile`, `-DatabaseName`, or `-NoBrowser` when a temporary local override is required. Process/command values take precedence over root `.env` where the launcher exposes an override.

An explicit `-FrontendPort` also sets the local `KEYCLOAK_REDIRECT_URI` and `NEXT_PUBLIC_APP_ORIGIN` to that port. The Keycloak client must allow the resulting exact callback URI (for example `http://127.0.0.1:3001/api/auth/callback`); changing the app port does not change Keycloak's redirect allowlist.

## Referencing a shared `.env` from an isolated Git worktree

When developing or verifying an Issue branch in an isolated Git worktree (e.g., `C:\Developer\Projects\knora-agent-worktree\<issue-slug>`), developers and autonomous agents can share the local `.env` located at the primary checkout (`C:\Developer\Projects\knora-agent\.env`) without merging code into temporary testing branches or copying secrets across directories.

### Worktree and environment boundaries

1. **`.env` is a local filesystem path, not a Git branch property**:
   The primary checkout `.env` resides at an uncommitted, gitignored filesystem location. Loading it from a worktree does not execute code from the primary checkout or require the primary checkout to be on `main` or any specific commit.
2. **Execute code and dependencies from the active worktree**:
   Always invoke the launcher script directly from the active worktree root (e.g. `.\scripts\start-dev.ps1`). The launcher automatically binds `$env:PYTHONPATH` to the active worktree (`$repoRoot\backend\src;$repoRoot`) and uses dependencies matching the worktree's lockfiles. The virtual environment interpreter is discovered from the worktree `.venv` or the primary checkout `.venv`.
3. **Verification of ownership and resource safety before invocation**:
   Passing `-EnvFile` or setting configuration variables does **not** grant execution permissions or create isolated backend services. The daily development launcher targets the shared `knora-dev` Docker Compose project and `knora_dev` database. Before launching:
   - Verify that ports 5432, 8180, 8000, 3000, and 9000 are not occupied by foreign or active developer sessions.
   - Never override ownership guards, remove reservation locks (`%TEMP%\knora-dev-reservation-knora-dev.lock`), or run mutating commands (`docker compose down -v`) against an active or unverified stack.
   - Shared local databases and services are used sequentially by default for local development and deterministic smoke testing.
   - Use an isolated test database only when tests execute destructive fixtures (such as table truncations or resets), run schema migrations, or require an empty initial state.
   - Unit and contract tests must use mocks, fakes, or in-memory stores instead of live databases.
4. **Configuration precedence and issue overrides**:
   Configuration values resolve in strict hierarchical order:
   ```text
   explicit launcher CLI parameters (-EnvFile, -FrontendPort, etc.)
           >
   caller process environment variables ($env:KEY)
           >
   loaded .env file (-EnvFile or root .env)
           >
   application defaults
   ```
   Never modify the shared primary `.env` to tune or test an individual Issue. Any issue-specific temporary settings must be passed as explicit launcher CLI arguments or set in the isolated caller process.
5. **AI credentials and simulation separation**:
   Having API tokens or account IDs in `.env` does not grant authorization to execute real or paid AI inference. Synthetic smoke harnesses (such as the [agent environment](agent-environment.md)) use deterministic providers to prove wiring and layout, which must never be cited as evidence of real AI generation quality. Real AI runs require explicit provider authorization, approved model targets, request budgets, and clean teardown procedures.

### Invocation example

Run the launcher from the active worktree root in a dedicated PowerShell process, supplying the absolute path to the shared `.env`:

```powershell
# From the worktree root: C:\Developer\Projects\knora-agent-worktree\<issue-slug>
.\scripts\start-dev.ps1 -EnvFile C:\Developer\Projects\knora-agent\.env -PreflightOnly
```

Use `-PreflightOnly` to validate configuration, profile compatibility, and PDF memory limits safely without launching Docker services or modifying persistent data.
