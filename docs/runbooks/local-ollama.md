# Local Ollama PDF re-index on Windows

This runbook runs the Knora API, PDF worker, frontend and Ollama on Windows. PostgreSQL and MinIO run in Docker. The PDF extractor uses the existing Windows Job Object limit for its child process. The launcher checks that limit before starting the API or worker.

## Prerequisites

- Windows with the repository's Python virtual environment and frontend dependencies installed.
- Docker Desktop running Linux containers. Ports 5432, 9000, 8000 and 3000 must be available, or pass alternate PostgreSQL, API and frontend ports to the launcher. MinIO uses port 9000.
- Ollama installed on Windows with `qwen3-embedding:0.6b` pulled. The download can be large. Keep Ollama bound to localhost.
- Runtime MinIO credentials in the PowerShell session. Do not put credentials, raw PDFs or Ollama responses in Git or issue comments.
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

Pass `-OllamaBaseUrl http://127.0.0.1:11435` to both launcher commands below. The digest remains the model identity; the different endpoint is a local runtime choice.

## Start

Set the MinIO credentials through your local secret source. The following variable names are required; do not paste values into a tracked file:

```powershell
$env:KNORA_CANONICAL_MINIO_ACCESS_KEY = '<local secret>'
$env:KNORA_CANONICAL_MINIO_SECRET_KEY = '<local secret>'
```

Configure the existing Keycloak issuer, audience and JWKS settings in the same shell if browser sign-in is needed. Then, from the repository root:

```powershell
.\scripts\start-ollama-demo.ps1 -PreflightOnly
.\scripts\start-ollama-demo.ps1
```

The preflight starts no database or service. It fails if Ollama, the model contract, exact vector size, profile pin or Windows PDF child memory limit is unavailable. The full launcher starts only PostgreSQL and MinIO through the existing Compose file, creates and migrates the separate `knora_issue103_demo` database, and starts API, worker and frontend as hidden host processes. It prints their PIDs and a log directory under the system temporary directory. It opens the frontend URL unless `-NoBrowser` is supplied.

For a nondefault PostgreSQL/API/frontend port, use `-PostgresPort`, `-ApiPort` and `-FrontendPort`. The MinIO host port remains 9000. The Python interpreter can be selected with `-PythonExe`; the launcher otherwise checks the worktree and primary checkout virtual environments.

### Use an existing retained Workspace

The default launcher database is intentionally new and contains no previously retained Documents. To re-index an existing Workspace, first bring its PostgreSQL and ObjectStore services online, and confirm its database has been reviewed and migrated to the current Alembic head. Supply their host-reachable endpoints and existing ObjectStore credentials in the environment. Then run with `-UseExistingStorage`, `-DatabaseUrl`, `-ObjectStoreEndpoint`, and the correct `-ObjectStoreBucket`. This mode **does not start Compose, create a database, or run migrations**; it checks Alembic heads and fails if the schema is behind. Use the same options for preflight and full launch.

```powershell
$env:KNORA_OBJECT_STORE_S3_ACCESS_KEY = '<existing local secret>'
$env:KNORA_OBJECT_STORE_S3_SECRET_KEY = '<existing local secret>'
.\scripts\start-ollama-demo.ps1 -PreflightOnly -UseExistingStorage -DatabaseUrl '<existing database URL>' -ObjectStoreEndpoint 'http://127.0.0.1:9000'
.\scripts\start-ollama-demo.ps1 -UseExistingStorage -DatabaseUrl '<existing database URL>' -ObjectStoreEndpoint 'http://127.0.0.1:9000'
```

Check the selected Workspace and document identities before submitting re-index. Do not point the launcher at the default `knora` database used by another checkout without reviewing its schema, source-object store and backup first. The `Teacher Manh - Guidelines 2024.pdf` gate needs this existing-data mode or a separately prepared retained-source fixture; a fresh launcher database cannot prove preservation of the earlier source/version identity.

## Re-index and verify

Open the authenticated Documents surface. A retained PDF with an active embedding profile different from the deployed profile shows **Re-index required**. The action appears only when the backend confirms a retained PDF source and a writable Workspace. It submits `config_mode=deployed` with a stable idempotency key and follows the authoritative job status. A network failure retains the key for an explicit retry. A failed job remains visible; it does not replace the old active Embedding Set.

For the issue acceptance fixture, re-index every non-archived test Document in the chosen local Workspace. Verify that `Teacher Manh - Guidelines 2024.pdf` reaches `succeeded`, the new active Embedding Set has 1024 dimensions, and the existing Document Version and Original Source Object identities remain unchanged. Record job/profile IDs and gate results only; do not attach the PDF or raw provider responses.

## Stop or recover

Stop only the API, worker and frontend PIDs printed by this launch. If no other test is using the issue's Compose project, stop its services with `docker compose -p issue-103-ollama-reindex stop postgres minio`. Do not remove volumes, source objects or the worktree as part of routine shutdown.

If the model digest changes, stop API and worker, rerun preflight, and restart with the new pinned profile. Existing vectors remain under their old immutable profile and require explicit re-index. If PDF isolation preflight fails, do not start the worker or weaken the extractor limit.
