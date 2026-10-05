param(
    [string]$BaseUrl = 'http://127.0.0.1:8180',
    [string]$Realm = 'knora-dev',
    [string]$AdminUsername = $env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME,
    [string]$AdminPassword = $env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD
)

$ErrorActionPreference = 'Stop'
if (-not $AdminUsername -or -not $AdminPassword) {
    throw 'KEYCLOAK_ADMIN_CREDENTIALS_REQUIRED'
}
if ($BaseUrl -notmatch '^https?://[^/]+$') {
    throw 'KEYCLOAK_BASE_URL_INVALID'
}
if ($Realm -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'KEYCLOAK_REALM_INVALID'
}

$token = Invoke-RestMethod -Method Post -Uri "$BaseUrl/realms/master/protocol/openid-connect/token" -ContentType 'application/x-www-form-urlencoded' -Body @{
    client_id = 'admin-cli'
    grant_type = 'password'
    username = $AdminUsername
    password = $AdminPassword
}
$headers = @{ Authorization = "Bearer $($token.access_token)" }
$realmUri = "$BaseUrl/admin/realms/$Realm"
$current = Invoke-RestMethod -Method Get -Uri $realmUri -Headers $headers
if ($current.loginTheme -eq 'knora') {
    Write-Output 'KEYCLOAK_THEME_ALREADY_SET'
    return
}

# Keycloak's realm update accepts the presentation property without a destructive re-import.
$body = @{ loginTheme = 'knora' } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Put -Uri $realmUri -Headers $headers -ContentType 'application/json' -Body $body | Out-Null
$updated = Invoke-RestMethod -Method Get -Uri $realmUri -Headers $headers
if ($updated.loginTheme -ne 'knora') {
    throw 'KEYCLOAK_THEME_UPDATE_FAILED'
}
Write-Output 'KEYCLOAK_THEME_SET'
