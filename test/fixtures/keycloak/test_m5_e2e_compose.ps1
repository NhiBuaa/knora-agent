$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$composeFiles = @(
    '-f', (Join-Path $repositoryRoot 'docker-compose.yml'),
    '-f', (Join-Path $repositoryRoot 'docker-compose.m5-e2e.yml')
)

& docker compose @composeFiles config --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'The production compose file and M5 E2E overlay must form a valid Compose configuration.'
}

$overlayPath = Join-Path $repositoryRoot 'docker-compose.m5-e2e.yml'
$realmPath = Join-Path $repositoryRoot 'test\fixtures\keycloak\m5-realm.json'
if (-not (Test-Path -LiteralPath $overlayPath -PathType Leaf)) {
    throw "Missing M5 E2E Compose overlay: $overlayPath"
}
if (-not (Test-Path -LiteralPath $realmPath -PathType Leaf)) {
    throw "Missing M5 E2E realm fixture: $realmPath"
}

$config = (& docker compose @composeFiles config --format json | ConvertFrom-Json)
if (-not $config.services.'keycloak-m5-e2e') {
    throw 'The Compose overlay must define the keycloak-m5-e2e service.'
}

$publishedPorts = @($config.services.'keycloak-m5-e2e'.ports)
$hasExpectedPort = $publishedPorts | Where-Object {
    $_.published -eq 8180 -and $_.target -eq 8080 -and $_.host_ip -eq '127.0.0.1'
}
if (-not $hasExpectedPort) {
    throw 'keycloak-m5-e2e must publish 127.0.0.1:8180 to container port 8080.'
}

$keycloakVolume = 'm5-e2e-verification_keycloak_m5_e2e_data'
& docker compose @composeFiles stop keycloak-m5-e2e
if ($LASTEXITCODE -ne 0) {
    throw 'The M5 E2E Keycloak service could not be stopped for realm reset.'
}
& docker compose @composeFiles rm -f keycloak-m5-e2e
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

& docker compose @composeFiles up -d --build postgres minio minio-init api keycloak-m5-e2e
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

$discovery = Wait-ForHttpSuccess 'http://127.0.0.1:8180/realms/m5-e2e/.well-known/openid-configuration' 'Keycloak discovery'
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

$tokenResponse = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-operator'
    password = 'm5-operator-password'
}
$payloadPart = $tokenResponse.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
switch ($payloadPart.Length % 4) {
    2 { $payloadPart += '==' }
    3 { $payloadPart += '=' }
}
$claims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payloadPart)) | ConvertFrom-Json
if ($claims.workspace_ids -isnot [Array] -or $claims.workspace_ids -notcontains 'm5-workspace') {
    throw 'The test token must include workspace_ids as an array containing m5-workspace.'
}
if ($claims.capabilities -isnot [Array] -or $claims.capabilities -notcontains 'documents:read' -or $claims.capabilities -notcontains 'operator:read') {
    throw 'The test token must include capabilities as an array with document and operator access.'
}

$deleteUserToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/token' -Body @{
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
if ($deleteUserClaims.workspace_id -ne 'm5-workspace' -or $deleteUserClaims.workspace_ids -isnot [Array] -or $deleteUserClaims.workspace_ids -notcontains 'm5-workspace' -or $deleteUserClaims.capabilities -isnot [Array] -or $deleteUserClaims.capabilities -notcontains 'documents:read' -or $deleteUserClaims.capabilities -notcontains 'documents:write' -or $deleteUserClaims.capabilities -notcontains 'documents:delete' -or $deleteUserClaims.capabilities -notcontains 'questions:ask') {
    throw 'The delete-user fixture token must include the m5-workspace document deletion capabilities.'
}

$otherWorkspaceToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/token' -Body @{
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
if ($otherClaims.workspace_id -ne 'm5-other-workspace' -or $otherClaims.capabilities -isnot [Array] -or $otherClaims.capabilities -notcontains 'operator:read') {
    throw 'The cross-workspace test identity must be an operator in m5-other-workspace.'
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

$noOperatorToken = Invoke-RestMethod -Method Post -ContentType 'application/x-www-form-urlencoded' -Uri 'http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/token' -Body @{
    grant_type = 'password'
    client_id = 'knora-web'
    username = 'm5-no-operator'
    password = 'm5-no-operator-password'
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
