param([switch]$CheckConfigurationOnly)

$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFiles = @(
    '-p', 'knora-m5-e2e',
    '-f', (Join-Path $repositoryRoot 'docker-compose.yml'),
    '-f', (Join-Path $repositoryRoot 'docker-compose.dev.yml')
)

# Restore the caller's environment even if E2E preparation fails.
$e2eValues = @{
    KNORA_CANONICAL_MINIO_ACCESS_KEY = 'm5-e2e-minio-access'
    KNORA_CANONICAL_MINIO_SECRET_KEY = 'm5-e2e-minio-secret'
    KNORA_M5_E2E_FAULTS_ENABLED = 'true'
    KNORA_KEYCLOAK_JWKS_CACHE_TTL_SECONDS = '1'
}
$previousValues = @{}
foreach ($name in $e2eValues.Keys) {
    $previousValues[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    foreach ($name in $e2eValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $e2eValues[$name], 'Process')
    }

& docker compose @composeFiles config --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'The base and dev Compose files must form a valid configuration.'
}

$realmPath = Join-Path $repositoryRoot 'test\fixtures\keycloak\dev-realm.json'
if (-not (Test-Path -LiteralPath $realmPath -PathType Leaf)) {
    throw "Missing local development realm fixture: $realmPath"
}

$config = (& docker compose @composeFiles config --format json | ConvertFrom-Json)
if (-not $config.services.'keycloak-dev') {
    throw 'The dev Compose overlay must define the keycloak-dev service.'
}

$publishedPorts = @($config.services.'keycloak-dev'.ports)
$hasExpectedPort = $publishedPorts | Where-Object {
    $_.published -eq 8180 -and $_.target -eq 8080 -and $_.host_ip -eq '127.0.0.1'
}
if (-not $hasExpectedPort) {
    throw 'keycloak-dev must publish 127.0.0.1:8180 to container port 8080.'
}
if ($CheckConfigurationOnly) {
    Write-Output 'E2E_CONFIG_OK'
    return
}

$devServices = @(& docker ps --filter 'label=com.docker.compose.project=knora-dev' --filter 'status=running' --format '{{.ID}}')
if ($LASTEXITCODE -ne 0) {
    throw 'Could not inspect the daily development Compose project.'
}
if ($devServices.Count -gt 0) {
    throw 'Stop daily development services before M5 E2E: docker compose -f docker-compose.yml -f docker-compose.dev.yml -p knora-dev stop postgres minio keycloak-dev'
}

$keycloakVolume = 'knora-m5-e2e_keycloak_dev_data'
& docker compose @composeFiles stop keycloak-dev
if ($LASTEXITCODE -ne 0) {
    throw 'The M5 E2E Keycloak service could not be stopped for realm reset.'
}
& docker compose @composeFiles rm -f keycloak-dev
if ($LASTEXITCODE -ne 0) {
    throw 'The M5 E2E Keycloak service could not be removed for realm reset.'
}
$volumeName = (& docker volume ls --filter "name=^$keycloakVolume$" --format '{{.Name}}')
if ($volumeName) {
    if ($volumeName -ne $keycloakVolume) {
        throw "Refusing to remove unexpected Keycloak volume: $volumeName"
    }
    & docker volume rm $keycloakVolume
    if ($LASTEXITCODE -ne 0) {
        throw "The exact M5 E2E Keycloak volume could not be removed: $keycloakVolume"
    }
}

& docker compose @composeFiles up -d --build postgres minio minio-init api keycloak-dev
if ($LASTEXITCODE -ne 0) {
    throw 'The M5 E2E Compose services did not start.'
}

function Wait-ForHttpSuccess([string]$uri, [string]$description) {
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $uri
            if ($response.StatusCode -eq 200) {
                return $response
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "$description did not return HTTP 200."
}

$discovery = Wait-ForHttpSuccess 'http://127.0.0.1:8180/realms/knora-dev/.well-known/openid-configuration' 'Keycloak discovery'
$apiHealth = Wait-ForHttpSuccess 'http://127.0.0.1:8000/health' 'API health endpoint'

$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $migrationOutput = @(& docker compose @composeFiles exec -T api alembic upgrade head 2>&1)
    $migrationExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($migrationExitCode -ne 0) {
    throw 'The M5 E2E API migration command failed.'
}

$bootstrapOutput = (@(& docker compose @composeFiles exec -T api python -m knora.adapters.cli.m5_e2e_bootstrap) -join "`n").Trim()
if ($LASTEXITCODE -ne 0) {
    throw 'The M5 E2E workspace bootstrap command failed.'
}
if ($bootstrapOutput -ne '{"outcome": "provisioned", "workspaces": ["m5-other-workspace", "m5-workspace"]}') {
    throw 'The M5 E2E workspace bootstrap command returned an unexpected sanitized result.'
}

$tokenResponse = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/knora-dev/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-operator'
    password = 'm5-operator-password'
}
$userToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/knora-dev/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-user'
    password = 'm5-user-password'
}
$userPayloadPart = $userToken.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
switch ($userPayloadPart.Length % 4) {
    2 { $userPayloadPart += '==' }
    3 { $userPayloadPart += '=' }
}
$userClaims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($userPayloadPart)) | ConvertFrom-Json
if ($userClaims.workspace_id -ne 'm5-workspace' -or $userClaims.workspace_ids -isnot [Array] -or (@($userClaims.workspace_ids) -join '|') -ne 'm5-workspace' -or $userClaims.capabilities -isnot [Array] -or ((@($userClaims.capabilities) | Sort-Object) -join '|') -ne 'documents:read|documents:write|questions:ask') {
    throw 'The user fixture token must contain exactly its approved identity and capabilities.'
}
$payloadPart = $tokenResponse.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
switch ($payloadPart.Length % 4) {
    2 { $payloadPart += '==' }
    3 { $payloadPart += '=' }
}
$claims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payloadPart)) | ConvertFrom-Json
if ($claims.workspace_id -ne 'm5-workspace' -or $claims.workspace_ids -isnot [Array] -or (@($claims.workspace_ids) -join '|') -ne 'm5-workspace') {
    throw 'The test token must contain exactly the m5-workspace identity.'
}
if ($claims.capabilities -isnot [Array] -or ((@($claims.capabilities) | Sort-Object) -join '|') -ne 'documents:read|documents:write|operator:read|questions:ask') {
    throw 'The operator fixture token must contain exactly its approved capabilities.'
}

$deleteUserToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/knora-dev/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-delete-user'
    password = 'm5-delete-user-password'
}
$deleteUserPayloadPart = $deleteUserToken.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
switch ($deleteUserPayloadPart.Length % 4) {
    2 { $deleteUserPayloadPart += '==' }
    3 { $deleteUserPayloadPart += '=' }
}
$deleteUserClaims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($deleteUserPayloadPart)) | ConvertFrom-Json
if ($deleteUserClaims.workspace_id -ne 'm5-workspace' -or $deleteUserClaims.workspace_ids -isnot [Array] -or (@($deleteUserClaims.workspace_ids) -join '|') -ne 'm5-workspace' -or $deleteUserClaims.capabilities -isnot [Array] -or ((@($deleteUserClaims.capabilities) | Sort-Object) -join '|') -ne 'documents:delete|documents:read|documents:write|questions:ask') {
    throw 'The delete-user fixture token must contain exactly its approved capabilities.'
}

$otherWorkspaceToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/knora-dev/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-other-workspace'
    password = 'm5-other-workspace-password'
}
$otherPayloadPart = $otherWorkspaceToken.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
switch ($otherPayloadPart.Length % 4) {
    2 { $otherPayloadPart += '==' }
    3 { $otherPayloadPart += '=' }
}
$otherClaims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($otherPayloadPart)) | ConvertFrom-Json
if ($otherClaims.workspace_id -ne 'm5-other-workspace' -or $otherClaims.workspace_ids -isnot [Array] -or (@($otherClaims.workspace_ids) -join '|') -ne 'm5-other-workspace' -or $otherClaims.capabilities -isnot [Array] -or ((@($otherClaims.capabilities) | Sort-Object) -join '|') -ne 'documents:read|documents:write|operator:read|questions:ask') {
    throw 'The cross-workspace fixture token must contain exactly its approved identity and capabilities.'
}
try {
    $crossWorkspaceResponse = Invoke-WebRequest -UseBasicParsing -Headers @{ Authorization = "Bearer $($otherWorkspaceToken.access_token)" } 'http://127.0.0.1:8000/v1/workspaces/m5-workspace/operator/operations'
    $crossWorkspaceStatus = $crossWorkspaceResponse.StatusCode
} catch {
    $crossWorkspaceStatus = [int]$_.Exception.Response.StatusCode
}
if ($crossWorkspaceStatus -ne 403) {
    throw "The other-workspace operator bearer request must return HTTP 403, got $crossWorkspaceStatus."
}

$noOperatorToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/knora-dev/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-no-operator'
    password = 'm5-no-operator-password'
}
$noOperatorPayloadPart = $noOperatorToken.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
switch ($noOperatorPayloadPart.Length % 4) {
    2 { $noOperatorPayloadPart += '==' }
    3 { $noOperatorPayloadPart += '=' }
}
$noOperatorClaims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($noOperatorPayloadPart)) | ConvertFrom-Json
if ($noOperatorClaims.workspace_id -ne 'm5-workspace' -or $noOperatorClaims.workspace_ids -isnot [Array] -or (@($noOperatorClaims.workspace_ids) -join '|') -ne 'm5-workspace' -or $noOperatorClaims.capabilities -isnot [Array] -or ((@($noOperatorClaims.capabilities) | Sort-Object) -join '|') -ne 'documents:read|documents:write|questions:ask') {
    throw 'The no-operator fixture token must contain exactly its approved identity and capabilities.'
}
try {
    $noOperatorResponse = Invoke-WebRequest -UseBasicParsing -Headers @{ Authorization = "Bearer $($noOperatorToken.access_token)" } 'http://127.0.0.1:8000/v1/workspaces/m5-workspace/operator/operations'
    $noOperatorStatus = $noOperatorResponse.StatusCode
} catch {
    $noOperatorStatus = [int]$_.Exception.Response.StatusCode
}
if ($noOperatorStatus -ne 403) {
    throw "The same-workspace no-operator bearer request must return HTTP 403, got $noOperatorStatus."
}

Write-Output 'M5 E2E Keycloak token claims, API readiness, and authorization-denial validation passed.'
} finally {
    foreach ($name in $e2eValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process')
    }
}
