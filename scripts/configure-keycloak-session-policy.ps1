param(
    [ValidateSet('Inspect', 'Diff', 'Apply', 'Rollback')][string]$Mode = 'Inspect',
    [string]$BaseUrl = 'http://127.0.0.1:8180',
    [string]$Realm = 'knora-dev',
    [ValidatePattern('(?-i)^(knora-dev|knora-figma-e2e(?:-[a-z0-9][a-z0-9-]{0,39})?)$')][string]$Project = 'knora-dev',
    [string]$AdminUsername = $env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME,
    [string]$AdminPassword = $env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD,
    [string]$SnapshotPath
)

$ErrorActionPreference = 'Stop'

function Unwrap-Items($items) {
    if ($null -eq $items) { return }
    if ($items -is [System.Collections.IEnumerable] -and $items -isnot [string] -and $items -isnot [System.Collections.IDictionary] -and $items -isnot [System.Management.Automation.PSCustomObject]) {
        foreach ($sub in $items) {
            if ($sub -is [System.Collections.IEnumerable] -and $sub -isnot [string] -and $sub -isnot [System.Collections.IDictionary] -and $sub -isnot [System.Management.Automation.PSCustomObject]) {
                foreach ($subsub in $sub) {
                    $subsub
                }
            } else {
                $sub
            }
        }
    } else {
        $items
    }
}

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
        grant_type = 'password'
        client_id = 'admin-cli'
        username = $AdminUsername
        password = $AdminPassword
    }
    $headers = @{ Authorization = "Bearer $($token.access_token)" }
} catch {
    throw 'KEYCLOAK_INSPECTION_FAILED'
}

# Provider check via /admin/serverinfo
try {
    $serverInfo = Invoke-RestMethod -Uri "$BaseUrl/admin/serverinfo" -Headers $headers
    $hasProvider = $false
    $oidcMappers = @(Unwrap-Items $serverInfo.protocolMapperTypes.'openid-connect')
    foreach ($mapperType in $oidcMappers) {
        if ($mapperType.id -eq 'knora-session-policy') { $hasProvider = $true }
    }
    if (-not $hasProvider) { throw 'missing' }
} catch {
    throw 'KEYCLOAK_SESSION_POLICY_PROVIDER_REQUIRED'
}

# Client lookup
try {
    $clients = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients?clientId=knora-web" -Headers $headers))
    if ($clients.Count -ne 1) { throw 'client' }
    $client = $clients[0]
    $clientUuid = $client.id
} catch {
    throw 'KEYCLOAK_INSPECTION_FAILED'
}

# Managed claim names
$managedClaims = @('knora_remember_me', 'knora_session_started_at')

# Mapper and client scopes conflict scan
$existingMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers))
$existingPolicyMapper = $null
foreach ($m in $existingMappers) {
    $claimName = if ($m.config) { $m.config.'claim.name' } else { $null }
    if ($claimName -in $managedClaims) {
        if ($m.name -ne 'knora-session-policy' -or $m.protocolMapper -ne 'knora-session-policy') {
            throw 'KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT'
        }
    }
    if ($m.name -eq 'knora-session-policy' -or $m.protocolMapper -eq 'knora-session-policy') {
        if ($existingPolicyMapper -ne $null) {
            # Duplicate canonical mapper
            throw 'KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT'
        }
        $isConsent = if ($m.PSObject.Properties['consentRequired']) { [bool]$m.consentRequired } else { $false }
        $hasConflictingClaim = ($claimName -and $claimName -notin $managedClaims)
        if ($m.name -eq 'knora-session-policy' -and
            $m.protocol -eq 'openid-connect' -and
            $m.protocolMapper -eq 'knora-session-policy' -and
            (-not $isConsent) -and
            (-not $hasConflictingClaim)) {
            $existingPolicyMapper = $m
        } else {
            throw 'KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT'
        }
    }
}

$scopes = @()
try {
    $scopes += @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/default-client-scopes" -Headers $headers))
    $scopes += @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/optional-client-scopes" -Headers $headers))
} catch {
    throw 'KEYCLOAK_INSPECTION_FAILED'
}

foreach ($s in $scopes) {
    if ($s.id) {
        $scopeMappers = @()
        try {
            $scopeMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/client-scopes/$($s.id)/protocol-mappers/models" -Headers $headers))
        } catch {
            throw 'KEYCLOAK_INSPECTION_FAILED'
        }
        foreach ($sm in $scopeMappers) {
            $claimName = if ($sm.config) { $sm.config.'claim.name' } else { $null }
            if ($claimName -in $managedClaims) {
                throw 'KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT'
            }
            if ($sm.name -eq 'knora-session-policy' -or $sm.protocolMapper -eq 'knora-session-policy') {
                throw 'KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT'
            }
        }
    }
}

# Current projections
$currentRealm = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers
$realmBefore = [ordered]@{
    rememberMe = [bool]$currentRealm.rememberMe
    ssoSessionIdleTimeout = [int]$currentRealm.ssoSessionIdleTimeout
    ssoSessionMaxLifespan = [int]$currentRealm.ssoSessionMaxLifespan
    ssoSessionIdleTimeoutRememberMe = [int]$currentRealm.ssoSessionIdleTimeoutRememberMe
    ssoSessionMaxLifespanRememberMe = [int]$currentRealm.ssoSessionMaxLifespanRememberMe
    clientSessionIdleTimeout = [int]$currentRealm.clientSessionIdleTimeout
    clientSessionMaxLifespan = [int]$currentRealm.clientSessionMaxLifespan
    accessTokenLifespan = [int]$currentRealm.accessTokenLifespan
}

$desiredRealm = [ordered]@{
    rememberMe = $true
    ssoSessionIdleTimeout = 1800
    ssoSessionMaxLifespan = 28800
    ssoSessionIdleTimeoutRememberMe = 604800
    ssoSessionMaxLifespanRememberMe = 2592000
    clientSessionIdleTimeout = 0
    clientSessionMaxLifespan = 0
    accessTokenLifespan = 300
}

$clientAttrs = $client.attributes
$attributesBefore = [ordered]@{
    'access.token.lifespan' = [ordered]@{
        present = ($clientAttrs -ne $null -and $clientAttrs.PSObject.Properties['access.token.lifespan'] -ne $null)
        value = if ($clientAttrs) { $clientAttrs.'access.token.lifespan' } else { $null }
    }
    'client.session.idle.timeout' = [ordered]@{
        present = ($clientAttrs -ne $null -and $clientAttrs.PSObject.Properties['client.session.idle.timeout'] -ne $null)
        value = if ($clientAttrs) { $clientAttrs.'client.session.idle.timeout' } else { $null }
    }
    'client.session.max.lifespan' = [ordered]@{
        present = ($clientAttrs -ne $null -and $clientAttrs.PSObject.Properties['client.session.max.lifespan'] -ne $null)
        value = if ($clientAttrs) { $clientAttrs.'client.session.max.lifespan' } else { $null }
    }
}

$attributesAfter = [ordered]@{
    'access.token.lifespan' = [ordered]@{ present = $true; value = '300' }
    'client.session.idle.timeout' = [ordered]@{ present = $false; value = $null }
    'client.session.max.lifespan' = [ordered]@{ present = $false; value = $null }
}

$mapperBefore = [ordered]@{
    present = ($existingPolicyMapper -ne $null)
    model = $existingPolicyMapper
}

if ($Mode -eq 'Inspect') {
    @{
        target = "$BaseUrl/realms/$Realm"
        project = $Project
        realmBefore = $realmBefore
        attributesBefore = $attributesBefore
        mapperBefore = $mapperBefore
    } | ConvertTo-Json -Depth 10
    Write-Output 'KEYCLOAK_SESSION_POLICY_INSPECTED'
    return
}

if ($Mode -eq 'Diff') {
    @{
        realmBefore = $realmBefore
        realmAfter = $desiredRealm
        attributesBefore = $attributesBefore
        attributesAfter = $attributesAfter
        mapperBefore = $mapperBefore
        mapperAfter = @{
            present = $true
            model = @{
                name = 'knora-session-policy'
                protocol = 'openid-connect'
                protocolMapper = 'knora-session-policy'
                consentRequired = $false
                config = @{}
            }
        }
    } | ConvertTo-Json -Depth 10
    Write-Output 'KEYCLOAK_SESSION_POLICY_DIFF'
    return
}

if ($Mode -eq 'Apply') {
    # Check if already applied
    $realmMatches = $true
    foreach ($k in $desiredRealm.Keys) {
        if ($realmBefore[$k] -ne $desiredRealm[$k]) { $realmMatches = $false }
    }
    $attrsMatch = ($attributesBefore['access.token.lifespan'].present -eq $true -and $attributesBefore['access.token.lifespan'].value -eq '300' -and
                   $attributesBefore['client.session.idle.timeout'].present -eq $false -and
                   $attributesBefore['client.session.max.lifespan'].present -eq $false)
    $mapperMatches = ($existingPolicyMapper -ne $null)

    if ($realmMatches -and $attrsMatch -and $mapperMatches) {
        Write-Output 'KEYCLOAK_SESSION_POLICY_ALREADY_SET'
        return
    }

    if (-not $SnapshotPath) {
        $folder = Join-Path (Split-Path $PSScriptRoot -Parent) '.verification/figma/keycloak-rollback'
        $null = New-Item -ItemType Directory -Force -Path $folder
        $SnapshotPath = Join-Path $folder "$Project-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')).json"
    }

    if (Test-Path -LiteralPath $SnapshotPath) {
        throw 'KEYCLOAK_SNAPSHOT_ALREADY_EXISTS'
    }

    $mapperId = if ($existingPolicyMapper) { $existingPolicyMapper.id } else { [guid]::NewGuid().ToString() }
    $desiredMapper = [ordered]@{
        id = $mapperId
        name = 'knora-session-policy'
        protocol = 'openid-connect'
        protocolMapper = 'knora-session-policy'
        consentRequired = $false
        config = @{}
    }

    $snapshot = [ordered]@{
        schema = 'knora-session-policy-snapshot-v1'
        target = "$BaseUrl/realms/$Realm"
        baseUrl = $BaseUrl
        realm = $Realm
        project = $Project
        clientUuid = $clientUuid
        realmBefore = $realmBefore
        realmAfter = $desiredRealm
        attributesBefore = $attributesBefore
        attributesAfter = $attributesAfter
        mapperBefore = $mapperBefore
        mapperAfter = [ordered]@{
            present = $true
            id = $mapperId
            model = $desiredMapper
        }
        completedSteps = @()
    }

    # Write snapshot atomically using CreateNew
    $snapJson = $snapshot | ConvertTo-Json -Depth 10
    $stream = [System.IO.File]::Open($SnapshotPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    try {
        $writer = New-Object System.IO.StreamWriter($stream, [System.Text.Encoding]::UTF8)
        $writer.Write($snapJson)
        $writer.Flush()
    } finally {
        $stream.Dispose()
    }

    function Update-Journal([string]$step) {
        $snapshot.completedSteps += $step
        $journal = [ordered]@{
            step = $step
            completedSteps = $snapshot.completedSteps
            timestampUtc = [DateTime]::UtcNow.ToString('o')
        }
        $journal | ConvertTo-Json | Set-Content -LiteralPath "$SnapshotPath.progress.json" -Encoding utf8
    }

    # Step 1: Mapper mutation
    if (-not $existingPolicyMapper) {
        $mBody = $desiredMapper | ConvertTo-Json
        Invoke-RestMethod -Method Post -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers -ContentType 'application/json' -Body $mBody | Out-Null
        Update-Journal 'mapper'

        # Exact readback
        $readbackMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers))
        $foundMappers = @($readbackMappers | Where-Object { $_ -and $_.name -eq 'knora-session-policy' })
        if ($foundMappers.Count -ne 1) {
            throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
        }
        $foundMapper = $foundMappers[0]
        if (-not $foundMapper -or
            $foundMapper.id -ne $mapperId -or
            $foundMapper.protocolMapper -ne 'knora-session-policy' -or
            $foundMapper.protocol -ne 'openid-connect' -or
            $foundMapper.consentRequired -ne $false) {
            throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
        }
        if ($foundMapper.config -ne $null -and $foundMapper.config.PSObject.Properties.Count -gt 0) {
            foreach ($cp in $foundMapper.config.PSObject.Properties) {
                if ($cp.Value -ne $null -and $cp.Value -ne '') {
                    throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
                }
            }
        }
    }

    # Step 2: Client attributes mutation
    $clientFresh = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers
    foreach ($propName in @('access.token.lifespan', 'client.session.idle.timeout', 'client.session.max.lifespan')) {
        $curPres = ($clientFresh.attributes -ne $null -and $clientFresh.attributes.PSObject.Properties[$propName] -ne $null)
        $curVal = if ($curPres) { $clientFresh.attributes.($propName) } else { $null }
        $expPres = $attributesBefore[$propName].present
        $expVal = $attributesBefore[$propName].value
        if ($curPres -ne $expPres -or $curVal -ne $expVal) {
            throw 'KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE'
        }
    }

    $freshAttrs = [ordered]@{}
    if ($clientFresh.attributes) {
        foreach ($prop in $clientFresh.attributes.PSObject.Properties) {
            if ($prop.Name -notin @('access.token.lifespan', 'client.session.idle.timeout', 'client.session.max.lifespan')) {
                $freshAttrs[$prop.Name] = $prop.Value
            }
        }
    }
    $freshAttrs['access.token.lifespan'] = '300'
    $clientPayload = [ordered]@{
        id = $clientUuid
        clientId = $clientFresh.clientId
        attributes = $freshAttrs
    }
    $cBody = $clientPayload | ConvertTo-Json -Depth 10
    Invoke-RestMethod -Method Put -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers -ContentType 'application/json' -Body $cBody | Out-Null
    Update-Journal 'client'

    # Exact readback
    $clientVerify = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers
    $vAttrs = $clientVerify.attributes
    $lifespanVal = if ($vAttrs -and $vAttrs.PSObject.Properties['access.token.lifespan']) { $vAttrs.'access.token.lifespan' } else { $null }
    $idlePres = ($vAttrs -ne $null -and $vAttrs.PSObject.Properties['client.session.idle.timeout'] -ne $null)
    $maxPres = ($vAttrs -ne $null -and $vAttrs.PSObject.Properties['client.session.max.lifespan'] -ne $null)
    if ($lifespanVal -ne '300' -or $idlePres -or $maxPres) {
        throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
    }

    # Step 3: Realm mutation
    $realmFresh = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers
    foreach ($k in $desiredRealm.Keys) {
        if ($realmFresh.$k -ne $realmBefore[$k]) {
            throw 'KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE'
        }
    }

    $rBody = $desiredRealm | ConvertTo-Json
    Invoke-RestMethod -Method Put -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers -ContentType 'application/json' -Body $rBody | Out-Null
    Update-Journal 'realm'

    # Exact readback
    $realmVerify = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers
    foreach ($k in $desiredRealm.Keys) {
        if ($realmVerify.$k -ne $desiredRealm[$k]) {
            throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
        }
    }

    Write-Output 'KEYCLOAK_SESSION_POLICY_APPLY_VERIFIED'
    Write-Output "Snapshot: $SnapshotPath"
    return
}

if ($Mode -eq 'Rollback') {
    if (-not $SnapshotPath -or -not (Test-Path -LiteralPath $SnapshotPath)) {
        throw 'KEYCLOAK_SNAPSHOT_REQUIRED'
    }

    $saved = Get-Content -Raw -LiteralPath $SnapshotPath | ConvertFrom-Json
    if ($saved.baseUrl -ne $BaseUrl -or $saved.realm -ne $Realm -or $saved.project -ne $Project -or $saved.clientUuid -ne $clientUuid) {
        throw 'KEYCLOAK_SESSION_POLICY_SNAPSHOT_TARGET_REJECTED'
    }

    # Read journal if present
    $journalPath = "$SnapshotPath.progress.json"
    $completedSteps = if (Test-Path -LiteralPath $journalPath) {
        @( (Get-Content -Raw -LiteralPath $journalPath | ConvertFrom-Json).completedSteps )
    } else {
        @()
    }

    # Read current state
    $currentRealm = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers
    $clientFresh = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers
    $cAttrs = $clientFresh.attributes
    $currentMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers))

    # Evaluate Realm state: must be either at Before or After
    $realmIsBefore = $true
    foreach ($p in $saved.realmBefore.PSObject.Properties) {
        if ($currentRealm.($p.Name) -ne $p.Value) { $realmIsBefore = $false }
    }
    $realmIsAfter = $true
    foreach ($p in $saved.realmAfter.PSObject.Properties) {
        if ($currentRealm.($p.Name) -ne $p.Value) { $realmIsAfter = $false }
    }
    if (-not $realmIsBefore -and -not $realmIsAfter) {
        throw 'KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE'
    }

    # Evaluate Client state: must be either at Before or After
    $clientIsBefore = $true
    foreach ($p in $saved.attributesBefore.PSObject.Properties) {
        $curPres = ($cAttrs -ne $null -and $cAttrs.PSObject.Properties[$p.Name] -ne $null)
        $curVal = if ($curPres) { $cAttrs.($p.Name) } else { $null }
        if ($p.Value.present -ne $curPres -or $p.Value.value -ne $curVal) { $clientIsBefore = $false }
    }
    $clientIsAfter = $true
    foreach ($p in $saved.attributesAfter.PSObject.Properties) {
        $curPres = ($cAttrs -ne $null -and $cAttrs.PSObject.Properties[$p.Name] -ne $null)
        $curVal = if ($curPres) { $cAttrs.($p.Name) } else { $null }
        if ($p.Value.present -ne $curPres -or $p.Value.value -ne $curVal) { $clientIsAfter = $false }
    }
    if (-not $clientIsBefore -and -not $clientIsAfter) {
        throw 'KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE'
    }

    # Evaluate Mapper state: must be either at Before or After
    $mapperIsBefore = $true
    $mapperIsAfter = $true
    if ($saved.mapperBefore.present) {
        $mBeforeFound = $null
        $mAfterFound = $null
        foreach ($m in $currentMappers) {
            if ($m.id -eq $saved.mapperBefore.model.id) { $mBeforeFound = $m }
            if ($m.id -eq $saved.mapperAfter.id) { $mAfterFound = $m }
        }
        if (-not $mBeforeFound) { $mapperIsBefore = $false }
        if (-not $mAfterFound) { $mapperIsAfter = $false }
    } else {
        $targetFound = $null
        foreach ($m in $currentMappers) {
            if ($m.id -eq $saved.mapperAfter.id -or $m.name -eq 'knora-session-policy') { $targetFound = $m }
        }
        if ($targetFound -ne $null) {
            $mapperIsBefore = $false
            if ($targetFound.id -ne $saved.mapperAfter.id -or $targetFound.protocolMapper -ne 'knora-session-policy') {
                $mapperIsAfter = $false
            }
        } else {
            $mapperIsAfter = $false
        }
    }
    if (-not $mapperIsBefore -and -not $mapperIsAfter) {
        throw 'KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE'
    }

    # Check if already fully rolled back (NO-OP)
    if ($realmIsBefore -and $clientIsBefore -and $mapperIsBefore) {
        Write-Output 'KEYCLOAK_SESSION_POLICY_ROLLBACK_VERIFIED'
        return
    }

    # Step 1: Restore Realm if in 'after' state or recorded in journal
    if ($realmIsAfter -or ('realm' -in $completedSteps -and -not $realmIsBefore)) {
        $realmRestored = @{}
        foreach ($p in $saved.realmBefore.PSObject.Properties) {
            $realmRestored[$p.Name] = $p.Value
        }
        $rBody = $realmRestored | ConvertTo-Json
        Invoke-RestMethod -Method Put -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers -ContentType 'application/json' -Body $rBody | Out-Null
        # Readback realm
        $realmVerify = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers
        foreach ($p in $saved.realmBefore.PSObject.Properties) {
            if ($realmVerify.($p.Name) -ne $p.Value) {
                throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
            }
        }
    }

    # Step 2: Restore Client Attributes if in 'after' state or recorded in journal
    if ($clientIsAfter -or ('client' -in $completedSteps -and -not $clientIsBefore)) {
        $freshClientForRestore = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers
        $restoredAttrs = [ordered]@{}
        if ($freshClientForRestore.attributes) {
            foreach ($prop in $freshClientForRestore.attributes.PSObject.Properties) {
                if ($prop.Name -notin @('access.token.lifespan', 'client.session.idle.timeout', 'client.session.max.lifespan')) {
                    $restoredAttrs[$prop.Name] = $prop.Value
                }
            }
        }
        foreach ($prop in $saved.attributesBefore.PSObject.Properties) {
            if ($prop.Value.present) {
                $restoredAttrs[$prop.Name] = $prop.Value.value
            }
        }
        $clientPayload = [ordered]@{
            id = $clientUuid
            clientId = $freshClientForRestore.clientId
            attributes = $restoredAttrs
        }
        $cBody = $clientPayload | ConvertTo-Json -Depth 10
        Invoke-RestMethod -Method Put -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers -ContentType 'application/json' -Body $cBody | Out-Null
        # Readback client attributes
        $clientVerify = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers
        $vAttrs = $clientVerify.attributes
        foreach ($p in $saved.attributesBefore.PSObject.Properties) {
            $curPres = ($vAttrs -ne $null -and $vAttrs.PSObject.Properties[$p.Name] -ne $null)
            $curVal = if ($curPres) { $vAttrs.($p.Name) } else { $null }
            if ($p.Value.present -ne $curPres -or $p.Value.value -ne $curVal) {
                throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
            }
        }
    }

    # Step 3: Restore / Remove Mapper if in 'after' state or recorded in journal
    if ($mapperIsAfter -or ('mapper' -in $completedSteps -and -not $mapperIsBefore)) {
        if (-not $saved.mapperBefore.present) {
            $mId = $saved.mapperAfter.id
            Invoke-RestMethod -Method Delete -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models/$mId" -Headers $headers | Out-Null
            # Readback mapper deleted
            $readbackMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers))
            foreach ($rm in $readbackMappers) {
                if ($rm.id -eq $mId -or $rm.name -eq 'knora-session-policy') {
                    throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
                }
            }
        } else {
            $origModel = $saved.mapperBefore.model
            $origBody = $origModel | ConvertTo-Json
            Invoke-RestMethod -Method Put -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models/$($origModel.id)" -Headers $headers -ContentType 'application/json' -Body $origBody | Out-Null
            $readbackMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers))
            $rmFound = $null
            foreach ($rm in $readbackMappers) { if ($rm.id -eq $origModel.id) { $rmFound = $rm } }
            if (-not $rmFound -or $rmFound.name -ne $origModel.name -or $rmFound.protocolMapper -ne $origModel.protocolMapper) {
                throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
            }
        }
    }

    # Final Readback of entire projection
    $finalRealm = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm" -Headers $headers
    foreach ($p in $saved.realmBefore.PSObject.Properties) {
        if ($finalRealm.($p.Name) -ne $p.Value) {
            throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
        }
    }
    $finalClient = Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid" -Headers $headers
    $fAttrs = $finalClient.attributes
    foreach ($p in $saved.attributesBefore.PSObject.Properties) {
        $curPres = ($fAttrs -ne $null -and $fAttrs.PSObject.Properties[$p.Name] -ne $null)
        $curVal = if ($curPres) { $fAttrs.($p.Name) } else { $null }
        if ($p.Value.present -ne $curPres -or $p.Value.value -ne $curVal) {
            throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
        }
    }
    $finalMappers = @(Unwrap-Items (Invoke-RestMethod -Uri "$BaseUrl/admin/realms/$Realm/clients/$clientUuid/protocol-mappers/models" -Headers $headers))
    if (-not $saved.mapperBefore.present) {
        foreach ($fm in $finalMappers) {
            if ($fm.name -eq 'knora-session-policy' -or $fm.id -eq $saved.mapperAfter.id) {
                throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
            }
        }
    } else {
        $fmFound = $null
        foreach ($fm in $finalMappers) { if ($fm.id -eq $saved.mapperBefore.model.id) { $fmFound = $fm } }
        if (-not $fmFound) {
            throw 'KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED'
        }
    }

    Write-Output 'KEYCLOAK_SESSION_POLICY_ROLLBACK_VERIFIED'
    return
}
