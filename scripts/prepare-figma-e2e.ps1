param([switch]$CheckConfigurationOnly)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path $PSScriptRoot -Parent
$project = 'knora-figma-e2e'
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
$compose = @('--project-name', $project, '--project-directory', $repositoryRoot, '-f', (Join-Path $repositoryRoot 'docker-compose.figma-e2e.yml'))
$configJson = (& docker compose @compose config --format json) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'FIGMA_COMPOSE_CONFIG_FAILED' }
$config = $configJson | ConvertFrom-Json
if ($config.name -ne $project) { throw 'FIGMA_PROJECT_REJECTED' }
$bindings = @{
    postgres = @('5543:5432'); api = @('8800:8000'); keycloak = @('8380:8080')
    minio = @('9900:9000', '9901:9001'); mail = @('1025:1025', '8025:8025')
}
foreach ($service in $bindings.Keys) {
    $ports = @($config.services.$service.ports)
    if ($ports.Count -ne $bindings[$service].Count) { throw 'FIGMA_PORTS_REJECTED' }
    foreach ($binding in $bindings[$service]) {
        $published, $target = $binding.Split(':')
        if (-not ($ports | Where-Object { $_.host_ip -eq '127.0.0.1' -and $_.published -eq $published -and $_.target -eq $target })) { throw 'FIGMA_PORTS_REJECTED' }
    }
}
if ($config.services.api.environment.KNORA_KEYCLOAK_ISSUER -ne $issuer -or
    $config.services.keycloak.environment.KC_DB_URL -ne 'jdbc:postgresql://keycloak-db:5432/keycloak') { throw 'FIGMA_REALM_OR_DATABASE_REJECTED' }
foreach ($volume in $config.volumes.PSObject.Properties) {
    if ($volume.Value.name -ne "${project}_$($volume.Name)") { throw 'FIGMA_VOLUME_REJECTED' }
}
if ($CheckConfigurationOnly) { Write-Output 'FIGMA_CONFIG_OK'; return }

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
& docker compose @compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'FIGMA_START_FAILED' }
foreach ($uri in "$issuer/.well-known/openid-configuration", 'http://127.0.0.1:8800/health', 'http://127.0.0.1:8025/api/v1/info') {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try { $null = Invoke-RestMethod -Uri $uri -TimeoutSec 3; $ready = $true; break }
        catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw 'FIGMA_HTTP_READINESS_FAILED' }
}
& docker compose @compose exec -T api alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'FIGMA_MIGRATIONS_FAILED' }
& (Join-Path $PSScriptRoot 'configure-keycloak-auth-flow.ps1') -Mode Apply -BaseUrl 'http://127.0.0.1:8380' -Project $project -AdminUsername 'figma-test-admin' -AdminPassword 'figma-test-admin-password'
Write-Output 'FIGMA_PREPARED'
