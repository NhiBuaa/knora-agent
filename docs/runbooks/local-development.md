# Local development on Windows

Use this workflow for day-to-day development. It keeps the stable Ollama demo/acceptance launcher separate from source-watching development behavior.

## Runtime layout

```text
Windows host
├── Ollama
├── FastAPI                auto-reload
├── PDF ingestion worker   graceful restart-on-change
└── Next.js                Fast Refresh / HMR

Docker Desktop
├── PostgreSQL / pgvector
└── MinIO
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
3. starts PostgreSQL and MinIO through Docker Compose under the `knora-dev` Compose project and waits for storage readiness;
4. creates/migrates the `knora_dev` database;
5. starts FastAPI with Uvicorn auto-reload for `backend/src/knora`;
6. starts the ingestion worker in `--dev-watch` mode;
7. starts Next.js with its normal development server and Fast Refresh;
8. stays in the foreground as the supervisor for those three host processes.

Press `Ctrl+C` to stop API, worker and frontend. PostgreSQL and MinIO intentionally remain running so the next development start is faster.

If you need to free ports 5432/9000 before switching to another local topology, stop the development storage services explicitly:

```powershell
docker compose -p knora-dev stop postgres minio
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
