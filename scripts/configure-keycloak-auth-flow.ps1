param(
    [ValidateSet('Inspect', 'Diff', 'Apply', 'Rollback')][string]$Mode = 'Inspect',
    [string]$BaseUrl = 'http://127.0.0.1:8180',
    [string]$Realm = 'knora-dev',
    [ValidateSet('knora-dev', 'knora-figma-e2e')][string]$Project = 'knora-dev',
    [string]$AdminUsername = $env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME,
    [string]$AdminPassword = $env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD,
    [string]$SnapshotPath
)

$ErrorActionPreference = 'Stop'
foreach ($item in Get-ChildItem Env:) {
    if ($item.Name -match '^(DOCKER_|COMPOSE_)' -and $item.Value.Trim()) {
        throw "KEYCLOAK_AMBIENT_SELECTOR_REJECTED: $($item.Name)"
    }
}
$expectedPort = if ($Project -eq 'knora-dev') { 8180 } else { 8380 }
if ($BaseUrl -ne "http://127.0.0.1:$expectedPort" -or $Realm -ne 'knora-dev') { throw 'KEYCLOAK_EXACT_TARGET_REQUIRED' }
if (-not $AdminUsername -or -not $AdminPassword) { throw 'KEYCLOAK_ADMIN_CREDENTIALS_REQUIRED' }
if ($Mode -in 'Apply', 'Rollback') {
    $owned = $false
    $ids = @(& docker ps --filter "label=com.docker.compose.project=$Project" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'KEYCLOAK_PROJECT_INSPECTION_FAILED' }
    foreach ($id in $ids) {
        $container = (& docker inspect $id | ConvertFrom-Json)[0]
        foreach ($mapping in @($container.NetworkSettings.Ports.'8080/tcp')) {
            if ($mapping.HostIp -eq '127.0.0.1' -and $mapping.HostPort -eq "$expectedPort") { $owned = $true }
        }
    }
    if (-not $owned) { throw 'KEYCLOAK_PROJECT_OWNERSHIP_REQUIRED' }
}
# Do not print HTTP error bodies, tokens or credentials.
try {
    $token = Invoke-RestMethod -Method Post -Uri "$BaseUrl/realms/master/protocol/openid-connect/token" -ContentType 'application/x-www-form-urlencoded' -Body @{
        client_id = 'admin-cli'; grant_type = 'password'; username = $AdminUsername; password = $AdminPassword
    }
    $headers = @{ Authorization = "Bearer $($token.access_token)" }
    $realmUri = "$BaseUrl/admin/realms/$Realm"
    $currentRealm = Invoke-RestMethod -Uri $realmUri -Headers $headers
    $currentProfile = Invoke-RestMethod -Uri "$realmUri/users/profile" -Headers $headers
    if ($currentRealm.realm -ne $Realm) { throw 'target' }
} catch { throw 'KEYCLOAK_INSPECTION_FAILED' }
$settings = @{}
foreach ($name in 'loginTheme', 'registrationAllowed', 'resetPasswordAllowed', 'loginWithEmailAllowed', 'registrationEmailAsUsername', 'duplicateEmailsAllowed', 'verifyEmail') { $settings[$name] = $currentRealm.$name }
if ($Mode -eq 'Inspect') {
    @{ target = "$BaseUrl/realms/$Realm"; project = $Project; settings = $settings; profile = $currentProfile } | ConvertTo-Json -Depth 100
    return
}
$desired = @{ loginTheme = 'knora'; registrationAllowed = $true; resetPasswordAllowed = $true; loginWithEmailAllowed = $true; registrationEmailAsUsername = $false; duplicateEmailsAllowed = $false }
$profile = $currentProfile | ConvertTo-Json -Depth 100 | ConvertFrom-Json
$conflicts = @()
foreach ($attribute in $profile.attributes) {
    if ($attribute.name -in 'firstName', 'lastName') {
        if ($attribute.required.scopes.Count -gt 0) { $conflicts += $attribute.name; continue }
        if ($attribute.required) {
            $roles = @($attribute.required.roles | Where-Object { $_ -ne 'user' })
            if ($roles.Count -gt 0) { $attribute.required.roles = $roles }
            else { $attribute.PSObject.Properties.Remove('required') }
        }
    } elseif ($attribute.name -notin 'username', 'email' -and $attribute.required -and
        ('user' -in @($attribute.required.roles) -or $attribute.required.scopes.Count -gt 0)) { $conflicts += $attribute.name }
}
if ($conflicts.Count -gt 0 -and $Mode -ne 'Rollback') {
    Write-Output (@{ requiredAttributeConflicts = $conflicts } | ConvertTo-Json)
    throw 'KEYCLOAK_REQUIRED_CUSTOM_ATTRIBUTE_CONFLICT'
}
if ($Mode -eq 'Diff') {
    @{ settingsBefore = $settings; settingsAfter = $desired; profileBefore = $currentProfile; profileAfter = $profile; verifyEmailPreserved = $settings.verifyEmail } | ConvertTo-Json -Depth 100
    return
}
if ($Mode -eq 'Apply') {
    $settingsChanged = $false
    foreach ($name in $desired.Keys) {
        if ($currentRealm.$name -ne $desired[$name]) { $settingsChanged = $true }
    }
    $profileChanged = ($profile | ConvertTo-Json -Depth 100 -Compress) -ne ($currentProfile | ConvertTo-Json -Depth 100 -Compress)
    if (-not $settingsChanged -and -not $profileChanged) {
        Write-Output 'KEYCLOAK_AUTH_FLOW_ALREADY_SET'
        return
    }
}
if ($Mode -eq 'Rollback') {
    if (-not $SnapshotPath) { throw 'KEYCLOAK_SNAPSHOT_REQUIRED' }
    $saved = Get-Content -Raw -LiteralPath $SnapshotPath | ConvertFrom-Json
    if ($saved.baseUrl -ne $BaseUrl -or $saved.realm -ne $Realm -or $saved.project -ne $Project) { throw 'KEYCLOAK_SNAPSHOT_TARGET_REJECTED' }
    $desired = $saved.settings
    $profile = $saved.profile
} else {
    if (-not $SnapshotPath) {
        $folder = Join-Path (Split-Path $PSScriptRoot -Parent) '.superpowers/figma/keycloak-rollback'
        $null = New-Item -ItemType Directory -Force -Path $folder
        $SnapshotPath = Join-Path $folder "$Project-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')).json"
    }
    if (Test-Path -LiteralPath $SnapshotPath) { throw 'KEYCLOAK_SNAPSHOT_ALREADY_EXISTS' }
    @{ baseUrl = $BaseUrl; realm = $Realm; project = $Project; settings = $settings; profile = $currentProfile } |
        ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $SnapshotPath -Encoding utf8
    Write-Output "KEYCLOAK_ROLLBACK_SNAPSHOT=$SnapshotPath"
}
try {
    Invoke-RestMethod -Method Put -Uri "$realmUri/users/profile" -Headers $headers -ContentType 'application/json' -Body ($profile | ConvertTo-Json -Depth 100) | Out-Null
    Invoke-RestMethod -Method Put -Uri $realmUri -Headers $headers -ContentType 'application/json' -Body ($desired | ConvertTo-Json -Depth 100) | Out-Null
    $verified = Invoke-RestMethod -Uri $realmUri -Headers $headers
    $verifiedProfile = Invoke-RestMethod -Uri "$realmUri/users/profile" -Headers $headers
    foreach ($property in ($desired | ConvertTo-Json | ConvertFrom-Json).PSObject.Properties) {
        if ($verified.($property.Name) -ne $property.Value) { throw 'settings' }
    }
    if ($Mode -eq 'Apply' -and $verified.verifyEmail -ne $settings.verifyEmail) { throw 'verifyEmail' }
    if (($verifiedProfile | ConvertTo-Json -Depth 100 -Compress) -ne ($profile | ConvertTo-Json -Depth 100 -Compress)) { throw 'profile' }
} catch { throw 'KEYCLOAK_UPDATE_OR_VERIFICATION_FAILED; use the saved snapshot for rollback' }
Write-Output "KEYCLOAK_AUTH_FLOW_$($Mode.ToUpperInvariant())_VERIFIED"
