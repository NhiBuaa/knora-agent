param(
    [string]$BaseUrl = 'http://127.0.0.1:8180',
    [string]$Realm = 'knora-dev',
    [ValidateSet('knora-dev')][string]$Project = 'knora-dev',
    [string]$AdminUsername = $env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME,
    [string]$AdminPassword = $env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD,
    [Parameter(Mandatory = $true)][string]$Username
)

$ErrorActionPreference = 'Stop'

# This command is deliberately limited to the local development realm. It is a
# one-time repair for accounts created before the registration listener existed;
# normal registration is provisioned by the Keycloak event listener.
if ($BaseUrl -ne 'http://127.0.0.1:8180' -or $Realm -ne 'knora-dev' -or $Project -ne 'knora-dev') {
    throw 'KEYCLOAK_EXACT_LOCAL_TARGET_REQUIRED'
}
if (-not $AdminUsername -or -not $AdminPassword) { throw 'KEYCLOAK_ADMIN_CREDENTIALS_REQUIRED' }
if ($Username.Length -gt 128 -or $Username -notmatch '^[A-Za-z0-9._@+\-]+$') {
    throw 'KEYCLOAK_USERNAME_INVALID'
}

$ids = @(& docker ps --filter "label=com.docker.compose.project=$Project" --format '{{.ID}}')
if ($LASTEXITCODE -ne 0) { throw 'KEYCLOAK_PROJECT_INSPECTION_FAILED' }
$owned = $false
foreach ($id in $ids) {
    $container = (& docker inspect $id | ConvertFrom-Json)[0]
    foreach ($mapping in @($container.NetworkSettings.Ports.'8080/tcp')) {
        if ($mapping.HostIp -eq '127.0.0.1' -and $mapping.HostPort -eq '8180') { $owned = $true }
    }
}
if (-not $owned) { throw 'KEYCLOAK_PROJECT_OWNERSHIP_REQUIRED' }

try {
    $token = Invoke-RestMethod -Method Post -Uri "$BaseUrl/realms/master/protocol/openid-connect/token" `
        -ContentType 'application/x-www-form-urlencoded' -Body @{
            client_id = 'admin-cli'; grant_type = 'password'; username = $AdminUsername; password = $AdminPassword
        }
    $headers = @{ Authorization = "Bearer $($token.access_token)" }
    $realmUri = "$BaseUrl/admin/realms/$Realm"
    $profile = Invoke-RestMethod -Uri "$realmUri/users/profile" -Headers $headers
    if (-not (@($profile.attributes) | Where-Object { $_.name -eq 'capabilities' })) {
        $profile.attributes = @($profile.attributes) + @([pscustomobject]@{
                name = 'capabilities'; displayName = 'capabilities'; multivalued = $true
                permissions = @{ view = @('admin'); edit = @('admin') }; validations = @{}
            })
        Invoke-RestMethod -Method Put -Uri "$realmUri/users/profile" -Headers $headers `
            -ContentType 'application/json' -Body ($profile | ConvertTo-Json -Depth 20) | Out-Null
    }
    $encodedUsername = [Uri]::EscapeDataString($Username)
    $users = @(Invoke-RestMethod -Uri "$realmUri/users?username=$encodedUsername&exact=true" -Headers $headers)
} catch {
    throw 'KEYCLOAK_USER_LOOKUP_FAILED'
}

$matches = @($users | Where-Object { $_.username -eq $Username })
if ($matches.Count -ne 1) { throw 'KEYCLOAK_USER_UNIQUE_MATCH_REQUIRED' }
$user = $matches[0]

$attributes = @{}
if ($user.attributes) {
    foreach ($property in $user.attributes.PSObject.Properties) {
        $attributes[$property.Name] = @($property.Value)
    }
}
$attributes['capabilities'] = @('documents:read', 'documents:write', 'questions:ask')

try {
    $body = @{ attributes = $attributes } | ConvertTo-Json -Depth 10
    Invoke-RestMethod -Method Put -Uri "$realmUri/users/$($user.id)" -Headers $headers `
        -ContentType 'application/json' -Body $body | Out-Null
    $verified = Invoke-RestMethod -Uri "$realmUri/users/$($user.id)" -Headers $headers
    $actual = @($verified.attributes.capabilities)
    $expected = @('documents:read', 'documents:write', 'questions:ask')
    if (($actual -join '|') -ne ($expected -join '|')) { throw 'capabilities' }
} catch {
    throw 'KEYCLOAK_USER_PROVISIONING_FAILED'
}

Write-Output 'KEYCLOAK_USER_PROVISIONED'
