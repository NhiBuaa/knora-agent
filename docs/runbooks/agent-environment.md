# Agent environment: isolated browser verification

Use this when a coding agent needs to launch, drive, observe or clean up Knora without
using a developer's data or an AI provider. For product navigation, read the
[Feature Map](../development/feature-map.md). Daily Cloudflare development stays in
[local development](local-development.md); release acceptance stays in
[CI and Runtime Verification](ci.md). A targeted smoke run is not release acceptance.

This is the existing Figma **application** Playwright harness, not fixture-mode UI or a
second launcher. It runs the real Next.js BFF, FastAPI, PostgreSQL/pgvector, MinIO,
Keycloak and synthetic Mailpit realm. No worker is started: Markdown ingestion is
synchronous; PDF jobs and submitted Turns do not reach terminal results on their own.
Deterministic providers prove structure, not answer quality or real email delivery.

## Launch

Run PowerShell from an isolated checkout of the intended commit. Required tools are
Docker Desktop/Compose, Node/npm, installed `frontend/node_modules` matching the lockfile,
and the Chromium revision required by that installed Playwright. Check these first:

```powershell
git status --short
git rev-parse HEAD
docker version --format '{{.Server.Version}}'
node --version
npm --version
Test-Path frontend/node_modules/@playwright/test/cli.js
```

Missing prerequisites are blockers: report them; installation, model downloads and
credential/provider setup require separate authorization. Reusing already installed,
lockfile-matching dependencies in the isolated checkout is sufficient. Startup uses the
existing Dockerfiles to build application images; it can download declared application
dependencies, but does not install host tools. Stop if that network use is not authorized.

Choose a fresh project and result directory for **each** attempt. Keep these variables in
the same PowerShell session, including cleanup after a failed launch:

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
$project = 'knora-figma-e2e-agent-' + [guid]::NewGuid().ToString('N').Substring(0,12)
$runRoot = Join-Path $repoRoot "frontend/test-results/$project"
if (Test-Path -LiteralPath $runRoot) { throw 'Evidence directory already exists' }
$composeArgs = @('--project-name', $project, '--project-directory', $repoRoot,
    '-f', (Join-Path $repoRoot 'docker-compose.dev.yml'), '--profile', 'figma')
$ownedAttempt = $false
./scripts/prepare-figma-e2e.ps1 -Project $project -CheckConfigurationOnly
./scripts/prepare-figma-e2e.ps1 -Project $project | ForEach-Object {
    if ($_ -ceq "FIGMA_PROJECT_FRESH=$project") { $ownedAttempt = $true }
    $_
}
```

Success is `FIGMA_CONFIG_OK`, `FIGMA_PROJECT_FRESH=<project>`, then `FIGMA_PREPARED`: services ready, migrations applied,
synthetic users imported and native registration/login flow configured. Suffixed projects
refuse retained containers, volumes or networks before startup; never adopt the legacy
`knora-figma-e2e` project's data. Namespace selection changes storage identity, not ports.
Only one browser verification stack can use these loopback ports at a time:
frontend 3300, API 8800, Keycloak 8380, PostgreSQL 5543, MinIO 9900/9901,
SMTP 1025 and Mailpit 8025. A foreign listener is a blocker, not permission to stop it.
The frontend is started and owned by Playwright, not by the preparation script.

## Doctor (read-only)

Before a browser mutation, confirm both ownership and readiness; HTTP 200 alone cannot
identify the right build. Record the tested SHA/dirty diff and each container image ID:

```powershell
docker compose @composeArgs ps -a
$ids = @(docker ps -a --filter "label=com.docker.compose.project=$project" --quiet)
foreach ($id in $ids) {
    docker inspect --format '{{.Name}} {{.Image}} {{index .Config.Labels "com.docker.compose.project"}}' $id
}
Invoke-RestMethod http://127.0.0.1:8800/health
$discovery = Invoke-RestMethod http://127.0.0.1:8380/realms/knora-dev/.well-known/openid-configuration
if ($discovery.issuer -cne 'http://127.0.0.1:8380/realms/knora-dev') { throw 'Wrong issuer' }
Invoke-RestMethod http://127.0.0.1:8025/api/v1/info
docker compose @composeArgs exec -T figma-api alembic current
docker compose @composeArgs exec -T figma-api python -c 'from knora.infrastructure.settings import Settings; s=Settings(); print(s.provider_mode, s.embedding_provider, s.generation_provider)'
```

Require migration `head` and `deterministic-local None None` before ingestion. The browser
helper `assertFigmaServiceOwnership()` additionally validates the selected project and
exact loopback API/issuer/mail bindings before login. The frontend's readiness probe is
`/api/auth/session`; unauthenticated `{session:null}` is healthy, not a logged-in proof.
Ambient Compose, Docker, Knora, Keycloak, session and legacy E2E overrides are rejected.
Inspect conflicting variable **names**, not secret values; do not silently clear someone's
settings to target a different environment. `FIGMA_TEST_PROJECT` is the explicit browser
ownership selector and must equal the launcher project.

## Drive and observe

Use installed Playwright directly; no MCP/browser plugin or extra CLI is required.
From the repository root, the following existing journeys cover UI login, Workspace
creation, synchronous Markdown ingestion, document archive/restore/deletion-request,
and Workspace/Conversation read-only boundaries. They do not call an AI provider:

```powershell
$env:FIGMA_TEST_PROJECT = $project
$env:FIGMA_TEST_MODE = 'application'
$env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = Join-Path $runRoot 'smoke.xml'
node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.figma.config.ts figma-document-navigation.spec.ts figma-ui-interactions.spec.ts --grep 'Documents live navigation|owned Workspace restores|live account logout and forced sign-in at 1440$' --reporter list,junit --output "$runRoot/results"
if ($LASTEXITCODE -ne 0) { throw 'Agent smoke failed; preserve evidence and clean up' }
```

Use accessible roles/labels from the Feature Map, not visual coordinates or guessed
selectors. Playwright starts the real frontend on 3300 and refuses to reuse an existing
server. Its webServer teardown owns that frontend; preserve the command's process handle
if running asynchronously. After it exits, 3300 must no longer accept connections.

Evidence lives under the unique `$runRoot`: `smoke.xml`, per-test `evidence/journey.json`
and explicit masked screenshots. A successful click is insufficient: inspect the asserted
HTTP response and later authoritative projection as well as the visible state. Keep failed
attempts too. Playwright clears its output directory at startup, so use a new directory for
every invocation, even if repeating the same test on the same stack.

For diagnosis, use `docker compose @composeArgs logs --tail 80 figma-api` locally and the
Playwright frontend output; Docker logs belong to this project only. Read bounded logs
instead of dumping all services. Auth URLs, tokens, cookies, passwords, OTP/mail bodies,
realm snapshots and broad logs must not enter PRs or retained evidence. Native traces,
video and automatic screenshots remain disabled by the harness. Other historical specs
still write to fixed `.verification/figma/q1` paths or require controller artifacts: do not
run a broad glob as this smoke workflow. Keep their historical evidence untouched.

## Isolation and cleanup

Keep the fresh project name and the container IDs observed during Launch/Doctor. In a
`finally` block (also after startup/test failure), recheck that this is the disposable
namespace created by **this invocation**, then use the exact Compose arguments above:

```powershell
if ($project -cnotmatch '^knora-figma-e2e-agent-[a-f0-9]{12}$') { throw 'Not an owned smoke project' }
if (-not $ownedAttempt) { throw 'No fresh-project marker acquired; leave existing resources untouched' }
docker compose @composeArgs down --volumes
if ($LASTEXITCODE -ne 0) { throw 'Cleanup failed' }
docker ps -a --filter "label=com.docker.compose.project=$project" --quiet
docker volume ls --filter "label=com.docker.compose.project=$project" --quiet
docker network ls --filter "label=com.docker.compose.project=$project" --quiet
Remove-Item Env:FIGMA_TEST_PROJECT,Env:FIGMA_TEST_MODE,Env:PLAYWRIGHT_JUNIT_OUTPUT_NAME -ErrorAction SilentlyContinue
```

All three resource queries must be empty; verify the run's listeners are gone and foreign
container IDs/statuses are unchanged. A namespace string alone is not ownership: the marker
is emitted only after freshness and port checks, immediately before startup, so it also
permits cleanup of a partially failed startup. A launch refused because resources already
existed emits no marker; leave those resources untouched. Keep the marker in this
invocation's session only.
Use process handles/owned Job Objects for a stuck frontend, never `taskkill` by image name
or a generic port-kill. Do not run Docker prune, delete other worktrees, remove historical
volumes, or remove evidence. Images/build cache are intentionally retained; Docker's
explicit Keycloak image tag is shared by the existing harness, while stopped containers
retain their original image IDs. Image-cache maintenance is separate from data cleanup.

## Updating this contract

Keep startup facts in the launcher/config, navigation in the Feature Map and observations
in the related PR. Promote only repeatable gotchas, following
[selective closeout](../agents/issue-tracker.md#selective-closeout). Safe, small corrections
within the approved work may be made directly; architecture/policy/authority changes outside
that scope remain proposals. No new Skill or duplicate knowledge store is needed for this path.
