param([switch]$CheckConfigurationOnly)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path $PSScriptRoot -Parent
$project = 'knora-figma-e2e'
# Reuse all existing ambient/configuration guards before any Docker mutation.
& (Join-Path $PSScriptRoot 'prepare-figma-e2e.ps1') -CheckConfigurationOnly
if ($LASTEXITCODE -ne 0) { throw 'OTP_BASE_CONFIGURATION_FAILED' }
$jar = Join-Path $repositoryRoot 'infra/keycloak/providers/email-otp-reset/target/email-otp-reset-0.1.0-SNAPSHOT-storage-probe.jar'
if (-not (Test-Path -LiteralPath $jar -PathType Leaf)) { throw 'OTP_PROBE_JAR_REQUIRED' }
$compose = @('--project-name', $project, '--project-directory', $repositoryRoot,
    '-f', (Join-Path $repositoryRoot 'docker-compose.figma-e2e.yml'),
    '-f', (Join-Path $repositoryRoot 'docker-compose.figma-otp-proof.yml'))
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
$secretBytes = New-Object byte[] 32
$random.GetBytes($secretBytes)
$random.Dispose()
# This ephemeral test header stays in process/container environment, never an artifact or output.
$env:KNORA_STORAGE_PROOF_SECRET = [Convert]::ToBase64String($secretBytes)
try {
    $configText = (& docker compose @compose config --format json) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'OTP_COMPOSE_CONFIG_FAILED' }
    $config = $configText | ConvertFrom-Json
    if ($config.name -ne $project) { throw 'OTP_PROJECT_REJECTED' }
    foreach ($node in 'keycloak', 'keycloak-proof') {
        $service = $config.services.$node
        if ($service.image -ne 'quay.io/keycloak/keycloak:26.3.3' -or
            $service.environment.KC_DB_URL -ne 'jdbc:postgresql://keycloak-db:5432/keycloak' -or
            $service.environment.KC_HOSTNAME -ne 'http://127.0.0.1:8380' -or
            $service.environment.KC_CACHE -ne 'ispn' -or
            $service.environment.KC_CACHE_STACK -ne 'jdbc-ping' -or
            $service.environment.KNORA_STORAGE_PROOF -ne 'enabled') { throw 'OTP_NODE_TARGET_REJECTED' }
        $mount = @($service.volumes | Where-Object target -eq '/opt/keycloak/providers/knora-storage-probe.jar')
        if ($mount.Count -ne 1 -or -not $mount[0].read_only -or
            [IO.Path]::GetFullPath($mount[0].source) -ne [IO.Path]::GetFullPath($jar)) { throw 'OTP_PROBE_MOUNT_REJECTED' }
        $ports = @($service.ports)
        $expectedPort = if ($node -eq 'keycloak') { '8380' } else { '8381' }
        if ($ports.Count -ne 1 -or $ports[0].host_ip -ne '127.0.0.1' -or
            $ports[0].published -ne $expectedPort -or $ports[0].target -ne 8080) { throw 'OTP_PORT_REJECTED' }
    }
    foreach ($volume in $config.volumes.PSObject.Properties) {
        if ($volume.Value.name -ne "${project}_$($volume.Name)") { throw 'OTP_VOLUME_REJECTED' }
    }
    if ($CheckConfigurationOnly) { Write-Output 'OTP_PROOF_CONFIG_OK'; return }
    $running = @(& docker ps -a --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'OTP_DOCKER_UNAVAILABLE' }
    $ownedPorts = @()
    foreach ($id in $running) {
        $container = (& docker inspect $id | ConvertFrom-Json)[0]
        $labels = $container.Config.Labels
        if ($container.Name -in "/${project}-keycloak-1", "/${project}-keycloak-proof-1", "/${project}-keycloak-db-1") {
            if ($labels.'com.docker.compose.project' -ne $project -or
                [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne [IO.Path]::GetFullPath($repositoryRoot)) { throw 'OTP_RESOURCE_OWNERSHIP_REJECTED' }
        }
        foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($mapping in @($port.Value)) {
                if ($null -ne $mapping -and [int]$mapping.HostPort -in 8380,8381) {
                    if ($labels.'com.docker.compose.project' -ne $project -or
                        $labels.'com.docker.compose.service' -notin 'keycloak', 'keycloak-proof') { throw 'OTP_PORT_OWNERSHIP_REJECTED' }
                    $ownedPorts += [int]$mapping.HostPort
                }
            }
        }
    }
    foreach ($port in 8380,8381) {
        $listener = New-Object Net.Sockets.TcpClient
        try {
            $connected = $listener.ConnectAsync('127.0.0.1', $port).Wait(150)
            if ($connected -and $listener.Connected -and $port -notin $ownedPorts) { throw "OTP_PORT_IN_USE: $port" }
        } catch [AggregateException] {
            # Refused connection means the port is available.
        } finally { $listener.Dispose() }
    }
    # Existing DB and volumes remain intact. Only these owned test nodes are recreated/started.
    & docker compose @compose up -d --no-deps keycloak keycloak-proof
    if ($LASTEXITCODE -ne 0) { throw 'OTP_NODES_START_FAILED' }
    foreach ($port in 8380,8381) {
        $ready = $false
        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            try {
                $null = Invoke-RestMethod -Uri "http://127.0.0.1:$port/realms/knora-dev/.well-known/openid-configuration" -TimeoutSec 2
                $ready = $true; break
            } catch { Start-Sleep -Seconds 1 }
        }
        if (-not $ready) { throw 'OTP_NODE_READINESS_FAILED' }
    }
    Write-Output 'OTP_PROOF_NODES_READY'
} finally {
    Remove-Item Env:KNORA_STORAGE_PROOF_SECRET -ErrorAction SilentlyContinue
}
