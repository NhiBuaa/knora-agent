# Local development on Windows

Use this workflow for day-to-day development. It keeps the stable Ollama demo/acceptance launcher separate from source-watching development behavior.

## Runtime layout

```text
Windows host
├── Ollama
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

Install dependencies, pull the Ollama embedding model and create the gitignored local environment file:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\backend[dev]"
npm --prefix frontend ci
ollama pull qwen3-embedding:0.6b

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Set local-only MinIO credentials in `.env`:

```dotenv
KNORA_OBJECT_STORE_S3_ACCESS_KEY=<local secret>
KNORA_OBJECT_STORE_S3_SECRET_KEY=<local secret>
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

Keep Ollama and Docker Desktop running before starting Knora. Root `.env` is loaded once at launcher startup; restart the development launcher after changing `.env`.

## Start daily development

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
2. verifies `qwen3-embedding:0.6b`, exact 1024-dimensional embeddings, immutable profile resolution and the Windows PDF Job Object safety path;
3. starts PostgreSQL and MinIO through Docker Compose under the `knora-dev` project, plus bundled Keycloak when its default realm is selected, and waits for readiness;
4. creates/migrates the `knora_dev` database;
5. starts FastAPI with Uvicorn auto-reload for `backend/src/knora`;
6. starts the ingestion worker in `--dev-watch` mode and the Conversation Turn worker;
7. starts Next.js with its normal development server and Fast Refresh;
8. stays in the foreground as the supervisor for all four host processes.

Press `Ctrl+C` to stop API, both workers and frontend. PostgreSQL, MinIO and Keycloak intentionally remain running so the next development start is faster. Restart the launcher after changing Conversation worker source; only the PDF worker has safe source-watch restarts.

Before running the isolated M5 E2E workflow, stop the daily services. Both projects
use host ports 5432, 9000 and 8180; the E2E preparation script refuses to reset its
own fixtures while the daily project is running. The daily volumes remain intact:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -p knora-dev stop postgres minio keycloak-dev
```

Prepare the E2E project with the same base and dev Compose files:

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
docker compose -f docker-compose.yml -f docker-compose.dev.yml -p knora-m5-e2e stop postgres minio api keycloak-dev
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

Use `-ApiPort`, `-FrontendPort`, `-PostgresPort`, `-PythonExe`, `-OllamaBaseUrl`, `-EnvFile`, `-DatabaseName`, or `-NoBrowser` when a temporary local override is required. Process/command values take precedence over root `.env` where the launcher exposes an override.

An explicit `-FrontendPort` also sets the local `KEYCLOAK_REDIRECT_URI` and `NEXT_PUBLIC_APP_ORIGIN` to that port. The Keycloak client must allow the resulting exact callback URI (for example `http://127.0.0.1:3001/api/auth/callback`); changing the app port does not change Keycloak's redirect allowlist.
