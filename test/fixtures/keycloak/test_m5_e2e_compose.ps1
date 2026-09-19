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

Write-Output 'M5 E2E Keycloak Compose validation passed.'
