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

> [!NOTE]
> This browser verification harness does not load the shared local `.env` or invoke live AI providers. Do not evaluate AI provider behavior or generation quality using this deterministic smoke environment; for day-to-day development with Cloudflare or Ollama providers, see [local development](local-development.md) and [worktree environment sharing](local-development.md#referencing-a-shared-env-from-an-isolated-git-worktree).

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
./scripts/prepare-figma-e2e.ps1 -CheckFrontendOnly
```

### Frontend dependency containment pre-check (`-CheckFrontendOnly`)

Before running Playwright directly or starting browser verification, run `-CheckFrontendOnly` to verify that frontend dependencies and the Playwright CLI are physically contained inside the owned worktree and match the lockfile:

```powershell
./scripts/prepare-figma-e2e.ps1 -CheckFrontendOnly
```

Result codes:
- `FIGMA_FRONTEND_OK`: All required packages (`@playwright/test`, `playwright`, `playwright-core`) are physically contained inside `frontend/node_modules` of this worktree, the CLI belongs to `@playwright/test`, and installed versions match the lockfile nodes.
- `FIGMA_FRONTEND_UNAVAILABLE`: Node executable is missing, or `package.json`, `package-lock.json`, or required package installations are missing.
- `FIGMA_FRONTEND_OWNERSHIP_REJECTED`: `node_modules`, resolved packages, or the CLI path escape the owned frontend directory (e.g. symlinks/junctions pointing to sibling worktrees or outside directories).
- `FIGMA_FRONTEND_LOCK_MISMATCH`: Installed versions or dependency relationships do not agree with the lockfile nodes.
- `FIGMA_FRONTEND_METADATA_INVALID`: Package metadata or lockfile JSON is malformed.

> [!NOTE]
> `-CheckFrontendOnly` is a pre-check for harness execution; it does not protect raw `npm` commands executed outside the harness and does not prove runtime browser readiness. It is mutually exclusive with `-CheckConfigurationOnly` and `-Run`.

Missing prerequisites are blockers: report them; installation, model downloads and
credential/provider setup require separate authorization. Reusing already installed,
lockfile-matching dependencies in the isolated checkout is sufficient. Startup uses the
existing Dockerfiles to build application images; it can download declared application
dependencies, but does not install host tools. Stop if that network use is not authorized.

### Before launch: prerequisites and execution scope

Before a run with side effects, identify the target checkout/SHA (and dirty diff),
journey and installed build/dependencies, available tools/network permission, and a
browser harness that can exercise it. Installed Playwright is sufficient for the
journeys below; require the in-app browser only when the selected journey needs it.
Inspect port/project/stack ownership using read-only metadata. Check that authorized
configuration is available without printing secrets. For data or provider work, also
identify permitted sources, accounts/quota and the approved runtime scope; this
synthetic harness grants no provider authority.

Reuse existing authorization. When new approval is needed, present one concrete run
package: target and commands with side effects, dependencies/network use and permission
exceptions, data scope, time/request/cost limits where relevant, stop conditions,
ownership and cleanup. Once authorized, carry out the internal steps without asking
again for each one. Stop for missing new permission, unsafe/unknown ownership,
out-of-scope drift, startup/safety failure or an approved stop/budget limit. A failed
package does not renew its clock or revive a stopped historical package.

Pre-launch checks establish only what can be inspected then. Actual health,
migration/schema compatibility, authenticated sessions and running-build ownership
need checks **after startup**: use Doctor inside `-Run` before browser mutations.
`-CheckConfigurationOnly` does not perform those checks. Recheck ownership/readiness
at the point of use; an earlier preflight cannot guarantee resources stayed unchanged.

Choose a fresh project and result directory for **each** attempt. Keep these variables in
the same PowerShell session:

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
$project = 'knora-figma-e2e-agent-' + [guid]::NewGuid().ToString('N').Substring(0,12)
$runRoot = Join-Path $repoRoot "frontend/test-results/$project"
if (Test-Path -LiteralPath $runRoot) { throw 'Evidence directory already exists' }
$composeArgs = @('--project-name', $project, '--project-directory', $repoRoot,
    '-f', (Join-Path $repoRoot 'docker-compose.dev.yml'), '--profile', 'figma')
./scripts/prepare-figma-e2e.ps1 -Project $project -CheckConfigurationOnly
```

`FIGMA_CONFIG_OK` is configuration validation only. Launch using the `-Run` block below:
`FIGMA_PREPARED` means services ready, migrations applied, synthetic users imported and
native registration/login flow configured. The launcher atomically creates an exclusive
reservation file in the OS temp directory, shared by same-user sessions across worktrees,
and holds it through startup, the entire block and cleanup. A competing invocation
fails with `FIGMA_PROJECT_RESERVED`, without starting or cleaning anything. Suffixed projects
require `-Run` and refuse retained containers, volumes or networks before startup; never adopt
the legacy `knora-figma-e2e` project's data. Namespace selection changes storage identity, not ports.
Only one browser verification stack can use these loopback ports at a time:
frontend 3300, API 8800, Keycloak 8380, PostgreSQL 5543, MinIO 9900/9901,
SMTP 1025 and Mailpit 8025. A foreign listener is a blocker, not permission to stop it.
The frontend is started and owned by Playwright, not by the preparation script.

## Doctor (read-only)

Before a browser mutation, confirm both ownership and readiness **inside `-Run`**; HTTP 200
alone cannot identify the right build. Record the tested SHA/dirty diff and each container image ID:

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
OTP's separate launcher and `playwright.figma-otp.config.ts` support only the legacy
`knora-figma-e2e` project; the OTP config explicitly refuses suffixed selections.

## Drive and observe

Use installed Playwright directly; no MCP/browser plugin or extra CLI is required.
From the repository root, the following existing journeys cover UI login, Workspace
creation, synchronous Markdown ingestion, document archive/restore/deletion-request,
and Workspace/Conversation read-only boundaries. They do not call an AI provider:

Run the Doctor commands above at the beginning of this block, before Playwright:

```powershell
try {
    ./scripts/prepare-figma-e2e.ps1 -Project $project -Run {
        param($project, $composeArgs)
        # Run the read-only Doctor checks above here before browser mutations.
        $env:FIGMA_TEST_PROJECT = $project
        $env:FIGMA_TEST_MODE = 'application'
        $env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = Join-Path $runRoot 'smoke.xml'
        node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.figma.config.ts figma-document-navigation.spec.ts figma-ui-interactions.spec.ts --grep 'Documents live navigation|owned Workspace restores|live account logout and forced sign-in at 1440$' --reporter list,junit --output "$runRoot/results"
        if ($LASTEXITCODE -ne 0) { throw 'Agent smoke failed; preserve evidence' }
    }
} finally {
    Remove-Item Env:FIGMA_TEST_PROJECT,Env:FIGMA_TEST_MODE,Env:PLAYWRIGHT_JUNIT_OUTPUT_NAME -ErrorAction SilentlyContinue
}
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

The launcher's `finally` block runs project-scoped `down --volumes` **before releasing
the reservation**, and only if this invocation created it, passed freshness/port checks and
attempted startup. This includes partial startup and verification failures. Refused launches
never clean existing resources. The default legacy invocation (no `-Project`/`-Run`) keeps
its idempotent, non-cleaning behavior for the existing runtime/OTP harness.

After the launcher returns, require `FIGMA_CLEANED=<project>` if startup was attempted,
and check the fresh project name and resource queries:

```powershell
docker ps -a --filter "label=com.docker.compose.project=$project" --quiet
docker volume ls --filter "label=com.docker.compose.project=$project" --quiet
docker network ls --filter "label=com.docker.compose.project=$project" --quiet
```

All three resource queries must be empty; verify the run's listeners are gone and foreign
container IDs/statuses are unchanged. A namespace or stdout marker is not cleanup authority;
keep the lifecycle inside `-Run`, not a later unguarded `compose down`. This reservation is
for same-user agents sharing the OS temp directory and local Docker Desktop, not multi-user,
multi-host or remote-daemon orchestration. If the process is force-killed or cleanup fails,
the reservation remains even if Docker has not created resources yet: a surviving Compose
child may still be building. Report the project, reservation path and leftovers; use a new
project only after checking the old attempt is inactive. Never automatically steal/delete a
stale claim. Ordinary refusals before startup release only their own new reservation.
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
