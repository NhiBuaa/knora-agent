# Local Ollama PDF re-index on Windows

This runbook runs the Knora API, PDF worker, frontend and Ollama on Windows. PostgreSQL and MinIO run in Docker. The PDF extractor uses the existing Windows Job Object limit for its child process. The launcher checks that limit before starting the API or worker.

## Prerequisites

- Windows with the repository's Python virtual environment and frontend dependencies installed.
- Docker Desktop running Linux containers. Ports 5432, 9000, 8000 and 3000 must be available, or pass alternate PostgreSQL, API and frontend ports to the launcher. MinIO uses port 9000.
- Ollama installed on Windows with `qwen3-embedding:0.6b` pulled. The download can be large. Keep Ollama bound to localhost.
- Existing Keycloak configuration for browser sign-in. The launcher does not create or change a realm.

From PowerShell, start Ollama if it is not already running, then pull and inspect the model:

```powershell
ollama serve
ollama pull qwen3-embedding:0.6b
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Use a second PowerShell session if `ollama serve` stays in the foreground. The launcher verifies `/api/tags`, `/api/show`, and a 1024-value `/api/embed` response. It resolves the exact model digest into one immutable Knora profile. API and worker startup are pinned to that profile ID, and embedding calls recheck the digest before work.

If a GPU runner fails, start a separate CPU-only Ollama endpoint in another PowerShell session instead of changing the default service:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11435'
$env:OLLAMA_LLM_LIBRARY = 'cpu'
$env:CUDA_VISIBLE_DEVICES = '-1'
ollama serve
```

Set `KNORA_OLLAMA_BASE_URL=http://127.0.0.1:11435` in `.env`, or pass `-OllamaBaseUrl http://127.0.0.1:11435` as a temporary override. The digest remains the model identity; the different endpoint is only a local runtime choice.

## One-time local configuration

Create the persistent local environment file once from the tracked template:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

`.env` is gitignored. Edit it with local-only values instead of re-entering `$env:...` assignments every time a new PowerShell session starts. For the default local MinIO path, set at least:

```dotenv
KNORA_OBJECT_STORE_S3_ACCESS_KEY=<local secret>
KNORA_OBJECT_STORE_S3_SECRET_KEY=<local secret>
```

The launcher also accepts the older `KNORA_CANONICAL_MINIO_ACCESS_KEY` / `KNORA_CANONICAL_MINIO_SECRET_KEY` names for compatibility, but the application-facing S3 variables above are sufficient for the normal fresh local stack. Keep all real credentials out of `.env.example`, Git, logs and issue comments.

If browser sign-in is needed, fill the backend `KNORA_KEYCLOAK_*` values and the frontend `KEYCLOAK_*` / `SESSION_SECRET` values in the same local `.env`. The launcher loads the root file before starting child processes, so FastAPI, worker and Next.js inherit the same local configuration.

Configuration precedence for launcher-owned local values is:

```text
explicit command / process environment
        >
root .env
        >
application defaults
```

The launcher still owns runtime-derived values such as the resolved Ollama profile ID. Do not pin `KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID` manually for the normal local flow.

## Start

From the repository root:

```powershell
.\scripts\start-ollama-demo.ps1 -PreflightOnly
.\scripts\start-ollama-demo.ps1
```

The preflight starts no database or service. It fails if Ollama, the model contract, exact vector size, profile pin or Windows PDF child memory limit is unavailable. The full launcher starts only PostgreSQL and MinIO through the existing Compose file, creates and migrates the separate `knora_issue103_demo` database, and starts API, worker and frontend as hidden host processes. It prints their PIDs and a log directory under the system temporary directory. It opens the frontend URL unless `-NoBrowser` is supplied.

For a nondefault PostgreSQL/API/frontend port, use `-PostgresPort`, `-ApiPort` and `-FrontendPort`. The MinIO host port remains 9000. The Python interpreter can be selected with `-PythonExe`; the launcher otherwise checks the worktree and primary checkout virtual environments. `-EnvFile` can point to an alternate dotenv file for an isolated local run; the default is the repository-root `.env`.

### Use an existing retained Workspace

The default launcher database is intentionally new and contains no previously retained Documents. To re-index an existing Workspace, first bring its PostgreSQL and ObjectStore services online, and confirm its database has been reviewed and migrated to the current Alembic head.

Put the reviewed connection values in the local `.env`:

```dotenv
KNORA_DATABASE_URL=<existing database URL>
KNORA_OBJECT_STORE_S3_ENDPOINT=http://127.0.0.1:9000
KNORA_OBJECT_STORE_S3_BUCKET=knora
KNORA_OBJECT_STORE_S3_ACCESS_KEY=<local secret>
KNORA_OBJECT_STORE_S3_SECRET_KEY=<local secret>
```

Then run:

```powershell
.\scripts\start-ollama-demo.ps1 -PreflightOnly -UseExistingStorage
.\scripts\start-ollama-demo.ps1 -UseExistingStorage
```

This mode **does not start Compose, create a database, or run migrations**; it checks Alembic heads and fails if the schema is behind. Command-line flags remain available as temporary overrides, but credential-bearing URLs and secrets should stay in the gitignored `.env` or another local secret source rather than shell history.

Check the selected Workspace and document identities before submitting re-index. Do not point the launcher at the default `knora` database used by another checkout without reviewing its schema, source-object store and backup first. The `Teacher Manh - Guidelines 2024.pdf` gate needs this existing-data mode or a separately prepared retained-source fixture; a fresh launcher database cannot prove preservation of the earlier source/version identity.

## Re-index and verify

Open the authenticated Documents surface. A retained PDF with an active embedding profile different from the deployed profile shows **Re-index required**. The action appears only when the backend confirms a retained PDF source and a writable Workspace. It submits `config_mode=deployed` with a stable idempotency key and follows the authoritative job status. A network failure retains the key for an explicit retry. A failed job remains visible; it does not replace the old active Embedding Set.

For the issue acceptance fixture, re-index every non-archived test Document in the chosen local Workspace. Verify that `Teacher Manh - Guidelines 2024.pdf` reaches `succeeded`, the new active Embedding Set has 1024 dimensions, and the existing Document Version and Original Source Object identities remain unchanged. Record job/profile IDs and gate results only; do not attach the PDF or raw provider responses.

## Stop or recover

Stop only the API, worker and frontend PIDs printed by this launch. If no other test is using the issue's Compose project, stop its services with `docker compose -p issue-103-ollama-reindex stop postgres minio`. Do not remove volumes, source objects or the worktree as part of routine shutdown.

If the model digest changes, stop API and worker, rerun preflight, and restart with the new pinned profile. Existing vectors remain under their old immutable profile and require explicit re-index. If PDF isolation preflight fails, do not start the worker or weaken the extractor limit.
