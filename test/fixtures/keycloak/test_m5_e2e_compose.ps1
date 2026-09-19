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

& docker compose @composeFiles up -d postgres minio minio-init api keycloak-m5-e2e
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

Write-Output 'M5 E2E Keycloak token claims and API readiness validation passed.'
