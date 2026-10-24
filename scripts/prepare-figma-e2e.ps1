param(
    [switch]$CheckConfigurationOnly,
    [switch]$CheckFrontendOnly,
    [ValidatePattern('(?-i)^knora-figma-e2e(?:-[a-z0-9][a-z0-9-]{0,39})?$')]
    [string]$Project = 'knora-figma-e2e',
    [scriptblock]$Run
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path $PSScriptRoot -Parent
$frontendDir = Join-Path $repositoryRoot 'frontend'

if ($CheckFrontendOnly -and $CheckConfigurationOnly) {
    throw 'FIGMA_CHECK_MODE_CONFLICT: -CheckFrontendOnly and -CheckConfigurationOnly are mutually exclusive'
}
if ($CheckFrontendOnly -and $Run) {
    throw 'FIGMA_CHECK_MODE_CONFLICT: -CheckFrontendOnly cannot be combined with -Run'
}

function Test-FrontendDependencies {
    param([string]$Dir)
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw 'FIGMA_FRONTEND_UNAVAILABLE: node executable not found'
    }
    $nodeScript = @'
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

function isPhysicallyWithin(rootPath, candidatePath) {
  try {
    const root = fs.realpathSync(rootPath);
    const candidate = fs.realpathSync(candidatePath);
    const relative = path.relative(root, candidate);
    return relative === '' ||
      (!path.isAbsolute(relative) && relative !== '..' &&
       !relative.startsWith('..' + path.sep));
  } catch {
    return false;
  }
}

function isExact(spec) {
  return /^[0-9]+\.[0-9]+\.[0-9]+.*$/.test(spec);
}

function resolveLockNode(lockPackages, startKey, canonicalFrontend) {
  let currentKey = startKey;
  const visited = new Set();
  while (true) {
    if (visited.has(currentKey)) {
      return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'Lock link cycle detected: ' + currentKey };
    }
    visited.add(currentKey);
    const node = lockPackages[currentKey];
    if (!node || typeof node !== 'object') {
      return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'No lock node found for ' + currentKey };
    }
    if (node.link === true) {
      if (!node.resolved || typeof node.resolved !== 'string') {
        return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'Link node missing resolved target: ' + currentKey };
      }
      const targetRel = node.resolved.replace(/\\/g, '/');
      const targetAbs = path.resolve(canonicalFrontend, targetRel);
      if (!isPhysicallyWithin(canonicalFrontend, targetAbs)) {
        return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'Link target is outside frontend: ' + targetRel };
      }
      currentKey = targetRel;
      continue;
    }
    return { ok: true, node, key: currentKey };
  }
}

function validateFrontend(frontendDir, repoDir) {
  const rawRepo = repoDir || path.dirname(path.resolve(frontendDir));

  if (!isPhysicallyWithin(rawRepo, frontendDir)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'frontend directory is outside repository' };
  }

  let canonicalFrontend;
  try {
    canonicalFrontend = fs.realpathSync(frontendDir);
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: 'Cannot resolve frontend directory' };
  }

  const pkgJsonPath = path.join(canonicalFrontend, 'package.json');
  const lockJsonPath = path.join(canonicalFrontend, 'package-lock.json');
  const nmPath = path.join(canonicalFrontend, 'node_modules');

  if (!fs.existsSync(pkgJsonPath) || !fs.existsSync(lockJsonPath)) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: 'package.json or package-lock.json missing' };
  }
  if (!fs.existsSync(nmPath)) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: 'node_modules missing' };
  }

  if (!isPhysicallyWithin(canonicalFrontend, nmPath)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'node_modules is outside frontend' };
  }

  let pkgJson, lockJson;
  try {
    pkgJson = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf8'));
    lockJson = JSON.parse(fs.readFileSync(lockJsonPath, 'utf8'));
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: err.message };
  }

  if (!pkgJson || typeof pkgJson !== 'object' || Array.isArray(pkgJson) ||
      !lockJson || typeof lockJson !== 'object' || Array.isArray(lockJson) ||
      !lockJson.packages || typeof lockJson.packages !== 'object') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'package or lock JSON invalid structure' };
  }

  const lockPackages = lockJson.packages;

  const rootSpec = (pkgJson.devDependencies && pkgJson.devDependencies['@playwright/test']) ||
                   (pkgJson.dependencies && pkgJson.dependencies['@playwright/test']);
  if (!rootSpec || typeof rootSpec !== 'string') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'Root @playwright/test spec missing in package.json' };
  }

  const rootLock = lockPackages[''] || lockPackages['.'];
  if (!rootLock || typeof rootLock !== 'object') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'Root package missing in package-lock.json' };
  }

  const lockRootSpec = (rootLock.devDependencies && rootLock.devDependencies['@playwright/test']) ||
                       (rootLock.dependencies && rootLock.dependencies['@playwright/test']);
  if (rootSpec !== lockRootSpec) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'Root @playwright/test spec mismatch: package.json (' + rootSpec + ') != lock (' + lockRootSpec + ')' };
  }

  const rootReq = createRequire(pkgJsonPath);
  let pwTestPkgPath;
  try {
    pwTestPkgPath = rootReq.resolve('@playwright/test/package.json');
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: '@playwright/test not resolved from root' };
  }

  const pwTestDir = path.dirname(pwTestPkgPath);
  if (!isPhysicallyWithin(canonicalFrontend, pwTestDir)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: '@playwright/test is outside frontend' };
  }

  let pwTestPkg;
  try {
    pwTestPkg = JSON.parse(fs.readFileSync(pwTestPkgPath, 'utf8'));
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'Cannot parse @playwright/test package.json' };
  }

  if (pwTestPkg.name !== '@playwright/test') {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: '@playwright/test installed package name mismatch: ' + pwTestPkg.name };
  }

  const pwTestRelKey = path.relative(canonicalFrontend, pwTestDir).replace(/\\/g, '/');
  const pwTestLockRes = resolveLockNode(lockPackages, pwTestRelKey, canonicalFrontend);
  if (!pwTestLockRes.ok) {
    return pwTestLockRes;
  }
  const pwTestLockNode = pwTestLockRes.node;
  if (pwTestLockNode.name && pwTestLockNode.name !== pwTestPkg.name) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: '@playwright/test lock node name mismatch' };
  }
  if (pwTestPkg.version !== pwTestLockNode.version) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: '@playwright/test version mismatch: installed ' + pwTestPkg.version + ' != lock ' + pwTestLockNode.version };
  }

  let pwTestCliPath;
  try {
    pwTestCliPath = rootReq.resolve('@playwright/test/cli');
  } catch (err) {
    const binRel = typeof pwTestPkg.bin === 'string' ? pwTestPkg.bin : (pwTestPkg.bin && pwTestPkg.bin.playwright ? pwTestPkg.bin.playwright : 'cli.js');
    pwTestCliPath = path.resolve(pwTestDir, binRel);
  }

  if (!fs.existsSync(pwTestCliPath)) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: '@playwright/test CLI missing' };
  }
  if (!isPhysicallyWithin(canonicalFrontend, pwTestCliPath)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'CLI is outside frontend' };
  }
  if (!isPhysicallyWithin(pwTestDir, pwTestCliPath)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'CLI does not belong to @playwright/test package' };
  }
  try {
    if (!fs.statSync(pwTestCliPath).isFile()) {
      return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'CLI is not a file' };
    }
  } catch {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'Cannot stat CLI file' };
  }

  const pwTestDepSpec = pwTestPkg.dependencies && pwTestPkg.dependencies['playwright'];
  if (!pwTestDepSpec || typeof pwTestDepSpec !== 'string') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: '@playwright/test missing dependency playwright' };
  }
  const pwTestLockDepSpec = pwTestLockNode.dependencies && pwTestLockNode.dependencies['playwright'];
  if (!pwTestLockDepSpec || typeof pwTestLockDepSpec !== 'string') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: '@playwright/test lock node missing dependency playwright' };
  }
  if (pwTestDepSpec !== pwTestLockDepSpec) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright parent spec mismatch: ' + pwTestDepSpec + ' != ' + pwTestLockDepSpec };
  }

  const pwTestReq = createRequire(pwTestPkgPath);
  let pwPkgPath;
  try {
    pwPkgPath = pwTestReq.resolve('playwright/package.json');
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: 'playwright not resolved from @playwright/test' };
  }

  const pwDir = path.dirname(pwPkgPath);
  if (!isPhysicallyWithin(canonicalFrontend, pwDir)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'playwright is outside frontend' };
  }

  let pwPkg;
  try {
    pwPkg = JSON.parse(fs.readFileSync(pwPkgPath, 'utf8'));
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'Cannot parse playwright package.json' };
  }

  if (pwPkg.name !== 'playwright') {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright installed package name mismatch: ' + pwPkg.name };
  }

  const pwRelKey = path.relative(canonicalFrontend, pwDir).replace(/\\/g, '/');
  const pwLockRes = resolveLockNode(lockPackages, pwRelKey, canonicalFrontend);
  if (!pwLockRes.ok) {
    return pwLockRes;
  }
  const pwLockNode = pwLockRes.node;
  if (pwLockNode.name && pwLockNode.name !== pwPkg.name) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright lock node name mismatch' };
  }
  if (pwPkg.version !== pwLockNode.version) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright version mismatch: installed ' + pwPkg.version + ' != lock ' + pwLockNode.version };
  }
  if (isExact(pwTestLockDepSpec) && pwPkg.version !== pwTestLockDepSpec) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright version ' + pwPkg.version + ' != exact spec ' + pwTestLockDepSpec };
  }

  const pwDepSpec = pwPkg.dependencies && pwPkg.dependencies['playwright-core'];
  if (!pwDepSpec || typeof pwDepSpec !== 'string') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'playwright missing dependency playwright-core' };
  }
  const pwLockDepSpec = pwLockNode.dependencies && pwLockNode.dependencies['playwright-core'];
  if (!pwLockDepSpec || typeof pwLockDepSpec !== 'string') {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'playwright lock node missing dependency playwright-core' };
  }
  if (pwDepSpec !== pwLockDepSpec) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright-core parent spec mismatch: ' + pwDepSpec + ' != ' + pwLockDepSpec };
  }

  const pwReq = createRequire(pwPkgPath);
  let pwCorePkgPath;
  try {
    pwCorePkgPath = pwReq.resolve('playwright-core/package.json');
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_UNAVAILABLE', msg: 'playwright-core not resolved from playwright' };
  }

  const pwCoreDir = path.dirname(pwCorePkgPath);
  if (!isPhysicallyWithin(canonicalFrontend, pwCoreDir)) {
    return { ok: false, code: 'FIGMA_FRONTEND_OWNERSHIP_REJECTED', msg: 'playwright-core is outside frontend' };
  }

  let pwCorePkg;
  try {
    pwCorePkg = JSON.parse(fs.readFileSync(pwCorePkgPath, 'utf8'));
  } catch (err) {
    return { ok: false, code: 'FIGMA_FRONTEND_METADATA_INVALID', msg: 'Cannot parse playwright-core package.json' };
  }

  if (pwCorePkg.name !== 'playwright-core') {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright-core installed package name mismatch: ' + pwCorePkg.name };
  }

  const pwCoreRelKey = path.relative(canonicalFrontend, pwCoreDir).replace(/\\/g, '/');
  const pwCoreLockRes = resolveLockNode(lockPackages, pwCoreRelKey, canonicalFrontend);
  if (!pwCoreLockRes.ok) {
    return pwCoreLockRes;
  }
  const pwCoreLockNode = pwCoreLockRes.node;
  if (pwCoreLockNode.name && pwCoreLockNode.name !== pwCorePkg.name) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright-core lock node name mismatch' };
  }
  if (pwCorePkg.version !== pwCoreLockNode.version) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright-core version mismatch: installed ' + pwCorePkg.version + ' != lock ' + pwCoreLockNode.version };
  }
  if (isExact(pwLockDepSpec) && pwCorePkg.version !== pwLockDepSpec) {
    return { ok: false, code: 'FIGMA_FRONTEND_LOCK_MISMATCH', msg: 'playwright-core version ' + pwCorePkg.version + ' != exact spec ' + pwLockDepSpec };
  }

  return { ok: true, code: 'FIGMA_FRONTEND_OK', msg: 'All dependencies verified' };
}

const targetDir = process.argv[2] || process.argv[1];
const repoDir = process.argv[3];
const res = validateFrontend(targetDir, repoDir);
console.log(JSON.stringify(res));
process.exit(res.ok ? 0 : 1);
'@
    $resJson = $nodeScript | node - $Dir $repositoryRoot
    $parsed = $null
    try { $parsed = $resJson | ConvertFrom-Json } catch { }
    if ($LASTEXITCODE -ne 0 -or -not $parsed) {
        if ($parsed -and $parsed.code) {
            throw "$($parsed.code): $($parsed.msg)"
        }
        throw "FIGMA_FRONTEND_METADATA_INVALID: node validator returned exit code $LASTEXITCODE"
    }
    if (-not $parsed.ok) {
        throw "$($parsed.code): $($parsed.msg)"
    }
    return $parsed.code
}

if ($CheckFrontendOnly) {
    $null = Test-FrontendDependencies $frontendDir
    Write-Output 'FIGMA_FRONTEND_OK'
    return
}
$issuer = 'http://127.0.0.1:8380/realms/knora-dev'
# Reject ambient selectors before Docker, database, realm or user operations.
foreach ($item in Get-ChildItem Env:) {
    if ($item.Name -match '^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)' -and $item.Value.Trim()) {
        throw "FIGMA_AMBIENT_OVERRIDE_REJECTED: $($item.Name)"
    }
}
$fixture = Get-Content -Raw (Join-Path $repositoryRoot 'test/fixtures/keycloak/figma-realm.json') | ConvertFrom-Json
$client = @($fixture.clients | Where-Object clientId -eq 'knora-web')
if ($fixture.realm -ne 'knora-dev' -or $client.Count -ne 1 -or
    $client[0].rootUrl -ne 'http://127.0.0.1:3300' -or
    $client[0].baseUrl -ne 'http://127.0.0.1:3300' -or
    (@($client[0].redirectUris) -join '|') -ne 'http://127.0.0.1:3300/api/auth/callback' -or
    (@($client[0].webOrigins) -join '|') -ne 'http://127.0.0.1:3300' -or
    $client[0].attributes.'post.logout.redirect.uris' -ne 'http://127.0.0.1:3300/' -or
    $fixture.smtpServer.host -ne 'mail') { throw 'FIGMA_FIXTURE_REJECTED' }
$compose = @('--project-name', $project, '--project-directory', $repositoryRoot,
    '-f', (Join-Path $repositoryRoot 'docker-compose.dev.yml'), '--profile', 'figma')
$configJson = (& docker compose @compose config --format json) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'FIGMA_COMPOSE_CONFIG_FAILED' }
$config = $configJson | ConvertFrom-Json
if ($config.name -ne $project) { throw 'FIGMA_PROJECT_REJECTED' }
$bindings = @{
    'figma-postgres' = @('5543:5432'); 'figma-api' = @('8800:8000'); 'figma-keycloak' = @('8380:8080')
    'figma-minio' = @('9900:9000', '9901:9001'); 'figma-mail' = @('1025:1025', '8025:8025')
}
foreach ($service in $bindings.Keys) {
    $ports = @($config.services.$service.ports)
    if ($ports.Count -ne $bindings[$service].Count) { throw 'FIGMA_PORTS_REJECTED' }
    foreach ($binding in $bindings[$service]) {
        $published, $target = $binding.Split(':')
        if (-not ($ports | Where-Object { $_.host_ip -eq '127.0.0.1' -and $_.published -eq $published -and $_.target -eq $target })) { throw 'FIGMA_PORTS_REJECTED' }
    }
}
if ($config.services.'figma-api'.environment.KNORA_KEYCLOAK_ISSUER -ne $issuer -or
    $config.services.'figma-keycloak'.environment.KC_DB_URL -ne 'jdbc:postgresql://figma-keycloak-db:5432/keycloak') { throw 'FIGMA_REALM_OR_DATABASE_REJECTED' }
foreach ($volume in $config.volumes.PSObject.Properties) {
    if ($volume.Value.name -ne "${project}_$($volume.Name)") { throw 'FIGMA_VOLUME_REJECTED' }
}
if ($CheckConfigurationOnly) { Write-Output 'FIGMA_CONFIG_OK'; return }
if ($Project -ne 'knora-figma-e2e' -and -not $Run) { throw 'FIGMA_DISPOSABLE_RUN_REQUIRED: supply -Run for verification and owned cleanup' }
if ($Project -eq 'knora-figma-e2e' -and $Run) { throw 'FIGMA_DISPOSABLE_PROJECT_REQUIRED' }

$null = Test-FrontendDependencies $frontendDir
$reservation = $null
$reservationPath = Join-Path ([IO.Path]::GetTempPath()) "knora-figma-reservation-$Project.lock"
$startupAttempted = $false
$cleanupSucceeded = $false
try {
    if ($Run) {
        # CreateNew is atomic across worktrees; retain the claim if an orphaned Compose child could survive.
        try { $reservation = [IO.File]::Open($reservationPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None) }
        catch [IO.IOException] { throw "FIGMA_PROJECT_RESERVED: $reservationPath" }
        foreach ($resource in @(@('ps', '-a'), @('volume', 'ls'), @('network', 'ls'))) {
            $existing = @(& docker @resource --filter "label=com.docker.compose.project=$Project" --quiet)
            if ($LASTEXITCODE -ne 0) { throw 'FIGMA_RESOURCE_INSPECTION_FAILED' }
            if ($existing.Count -gt 0) { throw 'FIGMA_PROJECT_NOT_FRESH' }
        }
        foreach ($resource in 'volume', 'network') {
            $names = @(& docker $resource ls --format '{{.Name}}')
            if ($LASTEXITCODE -ne 0) { throw 'FIGMA_RESOURCE_INSPECTION_FAILED' }
            if ($names | Where-Object { $_.StartsWith("${Project}_") }) { throw 'FIGMA_PROJECT_NOT_FRESH' }
        }
    }

    $running = @(& docker ps --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'FIGMA_DOCKER_UNAVAILABLE' }
    $ownedPorts = @()
    foreach ($id in $running) {
        $container = (& docker inspect $id | ConvertFrom-Json)[0]
        foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($mapping in @($port.Value)) {
                if ($null -eq $mapping) { continue }
                if ([int]$mapping.HostPort -in 3300,8800,8380,5543,9900,9901,1025,8025) {
                    if ($container.Config.Labels.'com.docker.compose.project' -ne $project) { throw 'FIGMA_PORT_OWNERSHIP_REJECTED' }
                    $ownedPorts += [int]$mapping.HostPort
                }
            }
        }
    }
    foreach ($port in 3300,8800,8380,5543,9900,9901,1025,8025) {
        $listener = New-Object Net.Sockets.TcpClient
        try {
            $connected = $listener.ConnectAsync('127.0.0.1', $port).Wait(150)
            if ($connected -and $listener.Connected -and $port -notin $ownedPorts) { throw "FIGMA_PORT_IN_USE: $port" }
        } catch [AggregateException] {
            # Connection refused is an available port.
        } finally { $listener.Dispose() }
    }
    $startupAttempted = $true
    & docker compose @compose up -d --build figma-postgres figma-keycloak-db figma-keycloak figma-mail figma-minio figma-minio-init figma-api
    if ($LASTEXITCODE -ne 0) { throw 'FIGMA_START_FAILED' }
    foreach ($uri in "$issuer/.well-known/openid-configuration", 'http://127.0.0.1:8800/health', 'http://127.0.0.1:8025/api/v1/info') {
        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            try { $null = Invoke-RestMethod -Uri $uri -TimeoutSec 3; $ready = $true; break }
            catch { Start-Sleep -Seconds 2 }
        }
        if (-not $ready) { throw 'FIGMA_HTTP_READINESS_FAILED' }
    }
    & docker compose @compose exec -T figma-api alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'FIGMA_MIGRATIONS_FAILED' }
    & (Join-Path $PSScriptRoot 'configure-keycloak-auth-flow.ps1') -Mode Apply -BaseUrl 'http://127.0.0.1:8380' -Project $Project -AdminUsername 'figma-test-admin' -AdminPassword 'figma-test-admin-password'
    Write-Output 'FIGMA_PREPARED'
    if ($Run) { & $Run $Project $compose }
} finally {
    try {
        if ($reservation -and $startupAttempted) {
            & docker compose @compose down --volumes
            if ($LASTEXITCODE -ne 0) { throw "FIGMA_CLEANUP_FAILED: inspect project $Project; do not reuse it" }
            foreach ($resource in @(@('ps', '-a'), @('volume', 'ls'), @('network', 'ls'))) {
                $remaining = @(& docker @resource --filter "label=com.docker.compose.project=$Project" --quiet)
                if ($LASTEXITCODE -ne 0 -or $remaining.Count -gt 0) { throw "FIGMA_CLEANUP_FAILED: inspect project $Project; do not reuse it" }
            }
            $cleanupSucceeded = $true
            Write-Output "FIGMA_CLEANED=$Project"
        }
    } finally {
        if ($reservation) {
            $reservation.Dispose()
            if (-not $startupAttempted -or $cleanupSucceeded) { [IO.File]::Delete($reservationPath) }
        }
    }
}
