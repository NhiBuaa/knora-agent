param(
    [Parameter(Mandatory = $false)]
    [string]$RunId,

    [Parameter(Mandatory = $false)]
    [string]$EvidenceRoot,

    [Parameter(Mandatory = $false)]
    [scriptblock]$Run
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$project = 'knora-issue162'
$compose = Join-Path $repositoryRoot 'docker-compose.dev.yml'
$profile = 'password-reset-test'
$dockerHostArgs = @('--host', 'npipe:////./pipe/dockerDesktopLinuxEngine')
$targetServices = @('reset-api','reset-keycloak','reset-keycloak-db','reset-mail','reset-postgres')
$expectedNetwork = "${project}_reset-isolated"

if (-not $IsWindows) { throw 'RESET_TEST_WINDOWS_REQUIRED' }
if ($EvidenceRoot -and -not [IO.Path]::IsPathFullyQualified($EvidenceRoot)) { throw 'RESET_TEST_EVIDENCE_ROOT_INVALID' }

# 1. Parameter Validation
if ($Run) {
    if (-not $RunId) {
        throw 'RESET_TEST_RUN_ID_REQUIRED'
    }
    try {
        $null = [guid]::Parse($RunId)
    } catch {
        throw "RESET_TEST_RUN_ID_INVALID: RunId must be a valid Guid ($RunId)"
    }
    if (-not $EvidenceRoot) {
        throw 'RESET_TEST_EVIDENCE_ROOT_REQUIRED'
    }
    if (-not [System.IO.Path]::IsPathRooted($EvidenceRoot) -or (-not [System.IO.Path]::IsPathFullyQualified($EvidenceRoot))) {
        throw "RESET_TEST_EVIDENCE_ROOT_INVALID: EvidenceRoot must be an absolute path ($EvidenceRoot)"
    }
}

# 2. Block ambient DOCKER_/COMPOSE_ overrides
foreach ($item in Get-ChildItem Env:) {
    if ($item.Name -match '^(DOCKER_|COMPOSE_)' -and $item.Value.Trim()) {
        throw 'RESET_TEST_AMBIENT_SELECTOR_REJECTED'
    }
}

# 3. Path Preflight and Ancestor Reparse Point Validation
function Assert-NoReparsePoint($pathToCheck) {
    $curr = [System.IO.Path]::GetFullPath($pathToCheck)
    while ($curr) {
        if (Test-Path -LiteralPath $curr -ErrorAction SilentlyContinue) {
            $item = Get-Item -LiteralPath $curr -Force -ErrorAction SilentlyContinue
            if ($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                throw 'RESET_TEST_PATH_REJECTED'
            }
        }
        $parent = [System.IO.Path]::GetDirectoryName($curr)
        if (-not $parent -or $parent -eq $curr) { break }
        $curr = $parent
    }
}

Assert-NoReparsePoint $repositoryRoot
Assert-NoReparsePoint $compose

$runtime = if ($EvidenceRoot) {
    [System.IO.Path]::GetFullPath($EvidenceRoot)
} else {
    Join-Path $repositoryRoot '.verification/password-reset'
}

$vault = Join-Path $runtime 'vault'
$realmFile = Join-Path $runtime 'realm.json'
$digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes('knora-reset-regression'))).ToLowerInvariant()
$entry = Join-Path $vault "knora-dev_knora-email-otp-hmac-$digest"

foreach ($path in @((Join-Path $repositoryRoot '.verification'), $runtime, $vault, $realmFile, $entry)) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'RESET_TEST_PATH_REJECTED'
    }
}
Assert-NoReparsePoint $runtime

if (Test-Path -LiteralPath $vault) {
    foreach ($item in Get-ChildItem -LiteralPath $vault -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'RESET_TEST_PATH_REJECTED'
        }
    }
}

# 4. Inspect the whole daemon; short IDs are never ownership evidence.
function Get-ResetInventory {
    $result = @{ containers=@(); volumes=@(); networks=@() }
    foreach ($kind in @('containers','volumes','networks')) {
        $listArgs = switch ($kind) {
            containers { @('ps','-a','--no-trunc','--format','{{.ID}}') }
            volumes { @('volume','ls','--format','{{.Name}}') }
            networks { @('network','ls','--no-trunc','--format','{{.ID}}') }
        }
        $result[$kind] = @(& docker @dockerHostArgs @listArgs)
        if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_INSPECTION_FAILED' }
    }
    return $result
}
function Read-ResetResource($kind, $id) {
    $inspectArgs = if ($kind -eq 'container') { @('inspect',$id) } else { @($kind,'inspect',$id) }
    $raw = & docker @dockerHostArgs @inspectArgs | Out-String
    if ($LASTEXITCODE -ne 0 -or -not $raw.Trim()) { throw 'RESET_TEST_INSPECTION_FAILED' }
    $resource = ($raw | ConvertFrom-Json)[0]
    $actual = if ($kind -eq 'volume') { $resource.Name } else { $resource.Id }
    if ($actual -cne $id) { throw 'RESET_TEST_INSPECTION_IDENTITY_MISMATCH' }
    return $resource
}
function Assert-ResetFreshness {
    param($baseline)
    $ids = $baseline.containers
    $ownedPorts = @()
    foreach ($id in $ids) {
        $container = Read-ResetResource container $id
        $belongs = $container.Config.Labels.'com.docker.compose.project' -eq $project
        if ($belongs) {
            if ($Run) { throw 'RESET_TEST_PROJECT_NOT_FRESH' }
            if (-not $container.Config.Labels.'com.docker.compose.project.working_dir' -or
                -not $container.Config.Labels.'com.docker.compose.project.config_files' -or
                [IO.Path]::GetFullPath($container.Config.Labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot -or
                [IO.Path]::GetFullPath($container.Config.Labels.'com.docker.compose.project.config_files') -ne $compose) { throw 'RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED' }
        }
        if ($container.State.Running) {
            foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
                foreach ($mapping in @($port.Value)) {
                    if ($null -eq $mapping) { continue }
                    if ($mapping.HostPort -in '8480','8900','8125','3400') {
                        if (-not $belongs) { throw 'RESET_TEST_PORT_OWNERSHIP_REQUIRED' }
                        $ownedPorts += [int]$mapping.HostPort
                    }
                }
            }
        }
    }
    foreach ($id in $baseline.networks) {
        $n = Read-ResetResource network $id
        if ($Run -and ($n.Name -eq $expectedNetwork -or $n.Labels.'com.docker.compose.project' -eq $project)) { throw 'RESET_TEST_PROJECT_NOT_FRESH' }
    }
    foreach ($id in $baseline.volumes) {
        $v = Read-ResetResource volume $id
        if ($Run -and ($v.Labels.'com.docker.compose.project' -eq $project -or $v.Name.StartsWith("${project}_"))) { throw 'RESET_TEST_PROJECT_NOT_FRESH' }
    }
    foreach ($port in 8480,8900,8125,3400) {
        $client = [Net.Sockets.TcpClient]::new()
        try {
            $connected = $client.ConnectAsync('127.0.0.1',$port).Wait(150)
            if ($connected -and $client.Connected -and $port -notin $ownedPorts) { throw "RESET_TEST_PORT_IN_USE: $port" }
        } catch [AggregateException] {} finally { $client.Dispose() }
    }
}

# 5. Atomic Reservation Lock and State Tracking
$reservationPath = Join-Path ([IO.Path]::GetTempPath()) "knora-reset-reservation-$project.lock"
$reservation = $null
$startupAttempted = $false
$startupFailed = $false
$innerRunFailed = $false
$capturedNativeExit = $null
$cleanupSucceeded = $false
$cleanupErrors = [System.Collections.Generic.List[string]]::new()
$primaryFailure = $null
$baseline = $null
$containerIdentity = @{}
$volumeIdentity = @{}
$networkIdentity = @{}
$claim = $null

$ledger = [PSCustomObject]@{
    containers = [System.Collections.Generic.List[string]]::new()
    volumes = [System.Collections.Generic.List[string]]::new()
    networks = [System.Collections.Generic.List[string]]::new()
}

$savedEnvironment = @{}
foreach ($name in @('KNORA_RESET_REALM_FILE', 'KNORA_RESET_VAULT_DIR', 'DOCKER_HOST')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}


function Get-Identity($value) { return ($value | ConvertTo-Json -Depth 25 -Compress) }
function Get-ContainerIdentity($c) {
    $networks = @($c.NetworkSettings.Networks.PSObject.Properties | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value.NetworkID)" })
    return Get-Identity ([ordered]@{ Id=$c.Id; Image=$c.Image; Created=$c.Created; Labels=$c.Config.Labels; Mounts=@($c.Mounts | Sort-Object Destination); Networks=$networks; PortBindings=$c.HostConfig.PortBindings })
}
function Assert-ResetContainer($c) {
    $l = $c.Config.Labels
    $service = $l.'com.docker.compose.service'
    if ($c.Id -notmatch '^[a-f0-9]{64}$' -or $c.Image -notmatch '^sha256:[a-f0-9]{64}$' -or
        $c.Id -in $baseline.containers -or $l.'com.docker.compose.project' -ne $project -or $service -notin $targetServices -or
        $l.'com.docker.compose.container-number' -ne '1' -or $l.'com.docker.compose.oneoff' -ne 'False' -or
        -not $l.'com.docker.compose.project.working_dir' -or -not $l.'com.docker.compose.project.config_files' -or
        [IO.Path]::GetFullPath($l.'com.docker.compose.project.working_dir') -ne $repositoryRoot -or
        [IO.Path]::GetFullPath($l.'com.docker.compose.project.config_files') -ne $compose) { throw 'RESET_TEST_CONTAINER_OWNERSHIP_REQUIRED' }
    $nets = @($c.NetworkSettings.Networks.PSObject.Properties)
    if ($nets.Count -ne 1 -or $nets[0].Name -ne $expectedNetwork -or $nets[0].Value.NetworkID -notmatch '^[a-f0-9]{64}$') { throw 'RESET_TEST_NETWORK_OWNERSHIP_REQUIRED' }
    $mounts = @($c.Mounts)
    if ($service -in 'reset-keycloak-db','reset-postgres') {
        if ($mounts.Count -ne 1 -or $mounts[0].Type -ne 'volume' -or -not $mounts[0].Name -or $mounts[0].Destination -ne '/var/lib/postgresql/data' -or $mounts[0].RW -ne $true) { throw 'RESET_TEST_MOUNT_OWNERSHIP_REQUIRED' }
    } elseif ($service -eq 'reset-keycloak') {
        $realmMount = @($mounts | Where-Object Destination -eq '/opt/keycloak/data/import/realm.json')
        $vaultMount = @($mounts | Where-Object Destination -eq '/opt/keycloak/vault')
        if ($mounts.Count -ne 2 -or $realmMount.Count -ne 1 -or $vaultMount.Count -ne 1 -or $realmMount[0].Type -ne 'bind' -or $vaultMount[0].Type -ne 'bind' -or
            [IO.Path]::GetFullPath($realmMount[0].Source) -ne $realmFile -or [IO.Path]::GetFullPath($vaultMount[0].Source) -ne $vault -or $realmMount[0].RW -ne $false -or $vaultMount[0].RW -ne $false) { throw 'RESET_TEST_MOUNT_OWNERSHIP_REQUIRED' }
    } elseif ($mounts.Count -ne 0) { throw 'RESET_TEST_MOUNT_OWNERSHIP_REQUIRED' }
    $expectedPort = switch ($service) { reset-api { '8000/tcp=8900' }; reset-keycloak { '8080/tcp=8480' }; reset-mail { '8025/tcp=8125' }; default { '' } }
    $published = @()
    foreach ($p in $c.NetworkSettings.Ports.PSObject.Properties) {
        foreach ($binding in @($p.Value)) {
            if ($null -eq $binding) { continue }
            if ($binding.HostIp -ne '127.0.0.1') { throw 'RESET_TEST_PORT_OWNERSHIP_REQUIRED' }
            $published += "$($p.Name)=$($binding.HostPort)"
        }
    }
    if ($c.State.Running -and ($published -join ',') -ne $expectedPort) { throw 'RESET_TEST_PORT_OWNERSHIP_REQUIRED' }
}
function Assert-ResetNetwork($n, $allowedContainers) {
    if ($n.Id -notmatch '^[a-f0-9]{64}$' -or $n.Id -in $baseline.networks -or $n.Name -ne $expectedNetwork -or $n.Driver -ne 'bridge' -or
        $n.Labels.'com.docker.compose.project' -ne $project -or $n.Labels.'com.docker.compose.network' -ne 'reset-isolated' -or -not $n.Created) { throw 'RESET_TEST_NETWORK_OWNERSHIP_REQUIRED' }
    foreach ($p in $n.Containers.PSObject.Properties) { if ($p.Name -notin $allowedContainers) { throw 'RESET_TEST_FOREIGN_NETWORK_ATTACHMENT' } }
}
function Get-NetworkIdentity($n) { return Get-Identity ([ordered]@{Id=$n.Id;Name=$n.Name;Created=$n.Created;Driver=$n.Driver;Labels=$n.Labels}) }
function Assert-ResetVolume($v, $allowedContainers) {
    if ($v.Name -in $baseline.volumes -or -not $v.Name -or -not $v.CreatedAt -or $v.Driver -ne 'local' -or
        ($v.Labels.'com.docker.compose.project' -and $v.Labels.'com.docker.compose.project' -ne $project) -or
        ($null -ne $v.Options -and @($v.Options.PSObject.Properties).Count -gt 0)) { throw 'RESET_TEST_VOLUME_OWNERSHIP_REQUIRED' }
    $attached = @(& docker @dockerHostArgs ps -a --no-trunc --filter "volume=$($v.Name)" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_INSPECTION_FAILED' }
    foreach ($id in $attached) { if ($id -notin $allowedContainers) { throw 'RESET_TEST_FOREIGN_VOLUME_ATTACHMENT' } }
}
function Save-ResetClaim {
    $claim.inventory = $ledger
    $claim.identities = @{ containers=$containerIdentity; volumes=$volumeIdentity; networks=$networkIdentity }
    # Append snapshots so cancellation during an update cannot erase the durable pre-start identity.
    $bytes = [Text.Encoding]::UTF8.GetBytes(($claim | ConvertTo-Json -Depth 35 -Compress) + "`n")
    $reservation.Position = $reservation.Length
    $reservation.Write($bytes,0,$bytes.Length)
    $reservation.Flush($true)
}
function Update-ResetLedger {
    $current = Get-ResetInventory
    $candidates = @()
    foreach ($id in $current.containers) {
        $c = Read-ResetResource container $id
        if ($c.Config.Labels.'com.docker.compose.project' -ne $project) { continue }
        Assert-ResetContainer $c
        $candidates += $c
    }
    $candidateIds = @($candidates | ForEach-Object Id)
    foreach ($c in $candidates) {
        $fingerprint = Get-ContainerIdentity $c
        if ($containerIdentity.ContainsKey($c.Id) -and $containerIdentity[$c.Id] -cne $fingerprint) { throw 'RESET_TEST_CONTAINER_IDENTITY_CHANGED' }
        foreach ($net in $c.NetworkSettings.Networks.PSObject.Properties) {
            $n = Read-ResetResource network $net.Value.NetworkID
            Assert-ResetNetwork $n $candidateIds
            $ni = Get-NetworkIdentity $n
            if ($networkIdentity.ContainsKey($n.Id) -and $networkIdentity[$n.Id] -cne $ni) { throw 'RESET_TEST_NETWORK_IDENTITY_CHANGED' }
            $networkIdentity[$n.Id] = $ni
            if (-not $ledger.networks.Contains($n.Id)) { $ledger.networks.Add($n.Id) }
        }
        foreach ($m in @($c.Mounts | Where-Object Type -eq 'volume')) {
            $v = Read-ResetResource volume $m.Name
            Assert-ResetVolume $v $candidateIds
            if ($v.Mountpoint -cne $m.Source) { throw 'RESET_TEST_VOLUME_MOUNT_IDENTITY_CHANGED' }
            $vi = Get-Identity $v
            if ($volumeIdentity.ContainsKey($v.Name) -and $volumeIdentity[$v.Name] -cne $vi) { throw 'RESET_TEST_VOLUME_IDENTITY_CHANGED' }
            $volumeIdentity[$v.Name] = $vi
            if (-not $ledger.volumes.Contains($v.Name)) { $ledger.volumes.Add($v.Name) }
        }
        $containerIdentity[$c.Id] = $fingerprint
        if (-not $ledger.containers.Contains($c.Id)) { $ledger.containers.Add($c.Id) }
    }
    Save-ResetClaim
    return $candidates
}
try {
    try {
        $reservation = [IO.File]::Open($reservationPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    } catch [IO.IOException] {
        throw "RESET_TEST_PROJECT_RESERVED: $reservationPath"
    }
    $baseline = Get-ResetInventory
    Assert-ResetFreshness $baseline
    if ($Run -and (Test-Path -LiteralPath $runtime)) { throw 'RESET_TEST_EVIDENCE_NOT_FRESH' }
    $sourceFiles = @{}
    foreach ($path in @($compose,$PSCommandPath)) { $sourceFiles[[IO.Path]::GetFileName($path)] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
    $sourceHead = $null
    $diffHash = $null
    if (Test-Path -LiteralPath (Join-Path $repositoryRoot '.git')) {
        $sourceHead = (& git -C $repositoryRoot rev-parse HEAD | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_SOURCE_IDENTITY_FAILED' }
        $diff = (& git -C $repositoryRoot diff --binary HEAD | Out-String)
        if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_SOURCE_IDENTITY_FAILED' }
        $diffHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($diff)))
    }
    $claim = [ordered]@{ run_id=$RunId; project=$project; checkout=$repositoryRoot; compose=$compose; evidence=$runtime; planned_services=$targetServices; planned_network=$expectedNetwork; docker_endpoint=$dockerHostArgs[1]; source_head=$sourceHead; source_diff_sha256=$diffHash; source_files=$sourceFiles; started_utc=[DateTime]::UtcNow.ToString('o'); baseline=$baseline; inventory=$ledger; identities=@{}; phase='reserved'; cleanup_receipt=$null }
    Save-ResetClaim

    $null = New-Item -ItemType Directory -Force $vault
    $ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls $vault /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_VAULT_REJECTED' }
    $allowed = @($ownerSid, 'S-1-5-18', 'S-1-5-32-544')
    foreach ($path in @($vault) + @(Get-ChildItem -LiteralPath $vault -Force | ForEach-Object FullName)) {
        $acl = Get-Acl -LiteralPath $path
        foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
            if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $allowed) {
                throw 'RESET_TEST_VAULT_REJECTED'
            }
        }
    }

    $fixture = Get-Content -Raw (Join-Path $repositoryRoot 'test/fixtures/keycloak/figma-realm.json') | ConvertFrom-Json
    $fixture | Add-Member -NotePropertyName id -NotePropertyValue 'knora-reset-regression' -Force
    $client = @($fixture.clients | Where-Object clientId -eq 'knora-web')[0]
    $client.rootUrl = 'http://127.0.0.1:3400'
    $client.baseUrl = 'http://127.0.0.1:3400'
    $client.redirectUris = @('http://127.0.0.1:3400/api/auth/callback')
    $client.webOrigins = @('http://127.0.0.1:3400')
    $client.attributes.'post.logout.redirect.uris' = 'http://127.0.0.1:3400/'
    $fixture.smtpServer.host = 'reset-mail'
    $fixture | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $realmFile -Encoding utf8

    $keyValid = $false
    if (Test-Path -LiteralPath $entry) {
        $decoded = $null
        try {
            if ((Get-Item -LiteralPath $entry).Length -gt 4096) { throw 'size' }
            $encoded = [IO.File]::ReadAllText($entry).Trim()
            if ($encoded -cnotmatch '^[A-Za-z0-9+/]+={0,2}$') { throw 'format' }
            $decoded = [Convert]::FromBase64String($encoded)
            $keyValid = $decoded.Length -ge 32 -and [Convert]::ToBase64String($decoded) -ceq $encoded
        } catch {} finally {
            if ($null -ne $decoded) { [Array]::Clear($decoded, 0, $decoded.Length) }
            $encoded = $null
        }
    }
    if (-not $keyValid) {
        $bytes = New-Object byte[] 32
        [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $temporary = Join-Path $vault "key-$([guid]::NewGuid()).tmp"
        try {
            [IO.File]::WriteAllText($temporary, [Convert]::ToBase64String($bytes))
            [IO.File]::Move($temporary, $entry, $true)
        } finally { [Array]::Clear($bytes, 0, $bytes.Length) }
    }

    $env:KNORA_RESET_REALM_FILE = $realmFile
    $env:KNORA_RESET_VAULT_DIR = $vault

    $composeArgs = @(
        '--project-name', $project,
        '--project-directory', $repositoryRoot,
        '-f', $compose,
        '--profile', $profile
    )
    $targetServices = @(
        'reset-api',
        'reset-keycloak',
        'reset-keycloak-db',
        'reset-mail',
        'reset-postgres'
    )

    $startupAttempted = $true
    $claim.phase = 'startup-attempted'
    Save-ResetClaim
    & docker @dockerHostArgs compose @composeArgs up -d --build @targetServices
    if ($LASTEXITCODE -ne 0) {
        $startupFailed = $true
        throw 'RESET_TEST_START_FAILED'
    }

    if ($Run) {
        $admitted = @(Update-ResetLedger)
        $services = @($admitted | ForEach-Object { $_.Config.Labels.'com.docker.compose.service' })
        if ($admitted.Count -ne 5 -or @($services | Select-Object -Unique).Count -ne 5 -or @($admitted | Where-Object { -not $_.State.Running }).Count -gt 0 -or $ledger.volumes.Count -ne 2) { throw 'RESET_TEST_TOPOLOGY_NOT_READY' }
    }

    $stage = 'ADMIN_LOGIN'
    $token = $null
    for ($attempt = 0; $attempt -lt 60 -and $null -eq $token; $attempt++) {
        try {
            $token = Invoke-RestMethod -TimeoutSec 5 -Method Post 'http://127.0.0.1:8480/realms/master/protocol/openid-connect/token' -ContentType 'application/x-www-form-urlencoded' -Body @{
                client_id = 'admin-cli'; grant_type = 'password'; username = 'figma-test-admin'; password = 'figma-test-admin-password'
            }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($null -eq $token) { throw 'unavailable' }
    $headers = @{ Authorization = "Bearer $($token.access_token)" }
    $uri = 'http://127.0.0.1:8480/admin/realms/knora-dev'
    $stage = 'REALM_IDENTITY'
    $realm = Invoke-RestMethod $uri -Headers $headers -TimeoutSec 10
    if ($realm.id -ne $fixture.id) { throw 'realm' }
    $stage = 'INSTALL_FLOW'
    $flows = Invoke-RestMethod "$uri/authentication/flows" -Headers $headers -TimeoutSec 10
    if (-not @($flows | Where-Object alias -eq 'issue162-reset')) {
        $stage = 'CREATE_FLOW'
        Invoke-RestMethod -Method Post "$uri/authentication/flows" -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body '{"alias":"issue162-reset","providerId":"basic-flow","topLevel":true,"builtIn":false}' | Out-Null
    }
    $stage = 'REQUIRE_EXECUTIONS'
    $executions = Invoke-RestMethod "$uri/authentication/flows/issue162-reset/executions" -Headers $headers -TimeoutSec 10
    $executions = @($executions | Where-Object { $null -ne $_ })
    $providers = @('knora-reset-email-otp', 'reset-password')
    if ($executions.Count -gt 2) { throw 'flow' }
    for ($index = 0; $index -lt $executions.Count; $index++) {
        if ($executions[$index].providerId -ne $providers[$index]) { throw 'flow' }
    }
    for ($index = $executions.Count; $index -lt 2; $index++) {
        $stage = "ADD_EXECUTION_$($providers[$index])"
        Invoke-RestMethod -Method Post "$uri/authentication/flows/issue162-reset/executions/execution" -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body (@{provider=$providers[$index]} | ConvertTo-Json) | Out-Null
    }
    $stage = 'REQUIRE_EXECUTIONS'
    $executions = Invoke-RestMethod "$uri/authentication/flows/issue162-reset/executions" -Headers $headers -TimeoutSec 10
    if ($executions.Count -ne 2 -or $executions[0].providerId -ne 'knora-reset-email-otp' -or $executions[1].providerId -ne 'reset-password') { throw 'flow' }
    foreach ($execution in $executions) {
        $execution.requirement = 'REQUIRED'
        Invoke-RestMethod -Method Put "$uri/authentication/flows/issue162-reset/executions" -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body ($execution | ConvertTo-Json -Depth 10) | Out-Null
    }
    $stage = 'BIND_FLOW'
    Invoke-RestMethod -Method Put $uri -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body '{"resetCredentialsFlow":"issue162-reset","emailTheme":"knora"}' | Out-Null
    $stage = 'API_HEALTH'
    $healthy = $false
    for ($attempt = 0; $attempt -lt 60 -and -not $healthy; $attempt++) {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8900/health' -TimeoutSec 5
            $healthy = $health.status -eq 'ok' -and $health.service -eq 'knora-agent'
        } catch {}
        if (-not $healthy) { Start-Sleep -Seconds 2 }
    }
    if (-not $healthy) { throw 'unavailable' }

    if ($Run) {
        Write-Output 'RESET_TEST_PREPARED'
        $capturedNativeExit = $null
        $global:LASTEXITCODE = 0
        try {
            $env:DOCKER_HOST = $dockerHostArgs[1]
            & $Run
            $capturedNativeExit = $LASTEXITCODE
            if ($capturedNativeExit -ne 0) {
                $innerRunFailed = $true
                throw "RESET_TEST_RUN_FAILED: callback native process exited with code $capturedNativeExit"
            }
        } catch {
            $innerRunFailed = $true
            throw
        }
    } else {
        Write-Output 'RESET_TEST_READY'
    }
} catch {
    $primaryFailure = $_
    if ($startupFailed) {
        throw 'RESET_TEST_START_FAILED'
    }
    if ($innerRunFailed) {
        throw
    }
    if ($_.Exception.Message -match '^(RESET_TEST_|INNER_FAIL)') {
        throw
    }
    throw "RESET_TEST_PREPARATION_FAILED_${stage}_$([int]$_.Exception.Response.StatusCode)"
} finally {
    try {
        if ($Run -and $reservation -and $startupAttempted) {
            try { $null = Update-ResetLedger } catch { $cleanupErrors.Add($_.Exception.Message) }

            foreach ($cId in $ledger.containers) {
                try {
                    $c = Read-ResetResource container $cId
                    Assert-ResetContainer $c
                    if ((Get-ContainerIdentity $c) -cne $containerIdentity[$cId]) { throw 'RESET_TEST_CONTAINER_IDENTITY_CHANGED' }
                    foreach ($m in @($c.Mounts | Where-Object Type -eq 'volume')) {
                        $v = Read-ResetResource volume $m.Name
                        Assert-ResetVolume $v $ledger.containers
                        if ($v.Mountpoint -cne $m.Source) { throw 'RESET_TEST_VOLUME_MOUNT_IDENTITY_CHANGED' }
                        if ((Get-Identity $v) -cne $volumeIdentity[$v.Name]) { throw 'RESET_TEST_VOLUME_IDENTITY_CHANGED' }
                    }
                    foreach ($net in $c.NetworkSettings.Networks.PSObject.Properties) {
                        $n = Read-ResetResource network $net.Value.NetworkID
                        Assert-ResetNetwork $n $ledger.containers
                        if ((Get-NetworkIdentity $n) -cne $networkIdentity[$n.Id]) { throw 'RESET_TEST_NETWORK_IDENTITY_CHANGED' }
                    }
                    & docker @dockerHostArgs stop $cId | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_STOP_FAILED' }
                    $c = Read-ResetResource container $cId
                    if ((Get-ContainerIdentity $c) -cne $containerIdentity[$cId]) { throw 'RESET_TEST_CONTAINER_IDENTITY_CHANGED' }
                    foreach ($m in @($c.Mounts | Where-Object Type -eq 'volume')) {
                        $v = Read-ResetResource volume $m.Name
                        Assert-ResetVolume $v $ledger.containers
                        if ($v.Mountpoint -cne $m.Source) { throw 'RESET_TEST_VOLUME_MOUNT_IDENTITY_CHANGED' }
                        if ((Get-Identity $v) -cne $volumeIdentity[$v.Name]) { throw 'RESET_TEST_VOLUME_IDENTITY_CHANGED' }
                    }
                    foreach ($net in $c.NetworkSettings.Networks.PSObject.Properties) {
                        $n = Read-ResetResource network $net.Value.NetworkID
                        Assert-ResetNetwork $n $ledger.containers
                        if ((Get-NetworkIdentity $n) -cne $networkIdentity[$n.Id]) { throw 'RESET_TEST_NETWORK_IDENTITY_CHANGED' }
                    }
                    & docker @dockerHostArgs rm $cId | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_RM_FAILED' }
                } catch { $cleanupErrors.Add("CONTAINER ${cId}: $($_.Exception.Message)") }
            }

            foreach ($vName in $ledger.volumes) {
                try {
                    $v = Read-ResetResource volume $vName
                    Assert-ResetVolume $v @()
                    if ((Get-Identity $v) -cne $volumeIdentity[$vName]) { throw 'RESET_TEST_VOLUME_IDENTITY_CHANGED' }
                    & docker @dockerHostArgs volume rm $vName | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_VOLUME_RM_FAILED' }
                } catch { $cleanupErrors.Add("VOLUME ${vName}: $($_.Exception.Message)") }
            }

            foreach ($nId in $ledger.networks) {
                try {
                    $n = Read-ResetResource network $nId
                    Assert-ResetNetwork $n @()
                    if ((Get-NetworkIdentity $n) -cne $networkIdentity[$nId]) { throw 'RESET_TEST_NETWORK_IDENTITY_CHANGED' }
                    & docker @dockerHostArgs network rm $nId | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_NETWORK_RM_FAILED' }
                } catch { $cleanupErrors.Add("NETWORK ${nId}: $($_.Exception.Message)") }
            }

            $remContainers = @($ledger.containers)
            $remVolumes = @($ledger.volumes)
            $remNetworks = @($ledger.networks)
            $inventoryComplete = $false
            try {
                $remaining = Get-ResetInventory
                $remContainers = @($ledger.containers | Where-Object { $_ -in $remaining.containers })
                $remVolumes = @($ledger.volumes | Where-Object { $_ -in $remaining.volumes })
                $remNetworks = @($ledger.networks | Where-Object { $_ -in $remaining.networks })
                foreach ($kind in @('containers','volumes','networks')) {
                    foreach ($id in $remaining[$kind]) {
                        if ($id -in $baseline[$kind]) { continue }
                        $singular = switch ($kind) { containers { 'container' }; volumes { 'volume' }; networks { 'network' } }
                        $resource = Read-ResetResource $singular $id
                        $labels = if ($kind -eq 'containers') { $resource.Config.Labels } else { $resource.Labels }
                        if ($labels.'com.docker.compose.project' -eq $project -or $id -in $ledger.$kind) {
                            $cleanupErrors.Add("REMAINING_${kind}: $id")
                            switch ($kind) {
                                containers {
                                    if ($id -notin $remContainers) { $remContainers += $id }
                                    foreach ($m in @($resource.Mounts | Where-Object Type -eq 'volume')) {
                                        if ($m.Name -in $remaining.volumes -and $m.Name -notin $remVolumes) { $remVolumes += $m.Name }
                                    }
                                }
                                volumes { if ($id -notin $remVolumes) { $remVolumes += $id } }
                                networks { if ($id -notin $remNetworks) { $remNetworks += $id } }
                            }
                        }
                    }
                }
                foreach ($cId in $ledger.containers) {
                    $exact = @(& docker @dockerHostArgs ps -a --no-trunc --filter "id=$cId" --format '{{.ID}}')
                    if ($LASTEXITCODE -ne 0 -or $exact.Count -gt 0) { $cleanupErrors.Add("REMAINING_CONTAINER: $cId") }
                }
                foreach ($vName in $ledger.volumes) {
                    $exact = @(& docker @dockerHostArgs volume ls --filter "name=$vName" --format '{{.Name}}')
                    if ($LASTEXITCODE -ne 0 -or $vName -in $exact) { $cleanupErrors.Add("REMAINING_VOLUME: $vName") }
                }
                foreach ($nId in $ledger.networks) {
                    $exact = @(& docker @dockerHostArgs network ls --no-trunc --filter "id=$nId" --format '{{.ID}}')
                    if ($LASTEXITCODE -ne 0 -or $nId -in $exact) { $cleanupErrors.Add("REMAINING_NETWORK: $nId") }
                }
                $inventoryComplete = $true
            } catch { $cleanupErrors.Add('RESET_TEST_CLEANUP_INVENTORY_FAILED') }

            $isClean = ($cleanupErrors.Count -eq 0)

            if ($EvidenceRoot) {
                $receiptPath = Join-Path $EvidenceRoot 'cleanup-receipt.json'
                $receipt = [PSCustomObject]@{
                    project = $project
                    run = $claim
                    primary_failure = if ($capturedNativeExit -ne $null -and $capturedNativeExit -ne 0) {
                        "CALLBACK_NATIVE_EXIT_$capturedNativeExit"
                    } elseif ($innerRunFailed) {
                        'CALLBACK_FAILED'
                    } elseif ($primaryFailure) {
                        'PREPARATION_FAILED'
                    } else {
                        $null
                    }
                    cleanup_succeeded = $isClean
                    inventory_complete = $inventoryComplete
                    inventory = $ledger
                    errors = $cleanupErrors
                    remaining = [PSCustomObject]@{
                        containers = $remContainers
                        volumes = $remVolumes
                        networks = $remNetworks
                    }
                }
                try {
                    $receipt | ConvertTo-Json -Depth 35 | Set-Content -LiteralPath $receiptPath -Encoding utf8
                    $claim.phase = if ($isClean) { 'cleaned' } else { 'cleanup-incomplete' }
                    $claim.cleanup_receipt = @{ path=$receiptPath; cleanup_succeeded=$isClean; remaining=$receipt.remaining; errors=$cleanupErrors }
                    Save-ResetClaim
                } catch {
                    $isClean = $false
                    $cleanupErrors.Add('RESET_TEST_CLEANUP_PERSISTENCE_FAILED')
                    $receipt.cleanup_succeeded = $false
                    $claim.phase = 'cleanup-incomplete'
                    $claim.cleanup_receipt = @{ path=$receiptPath; cleanup_succeeded=$false; remaining=$receipt.remaining; errors=$cleanupErrors }
                    # Neither persistence failure may replace the original run error or erase a durable claim.
                    try { $receipt | ConvertTo-Json -Depth 35 | Set-Content -LiteralPath $receiptPath -Encoding utf8 } catch {}
                    try { Save-ResetClaim } catch { $cleanupErrors.Add('RESET_TEST_RESERVATION_PERSISTENCE_FAILED') }
                }
            }

            if ($isClean) {
                $cleanupSucceeded = $true
                Write-Output "RESET_TEST_CLEANED=$project"
            } elseif (-not $primaryFailure -and -not $innerRunFailed) {
                throw "RESET_TEST_CLEANUP_FAILED: $($cleanupErrors -join '; ')"
            }
        }
    } finally {
        foreach ($name in $savedEnvironment.Keys) {
            if ($null -eq $savedEnvironment[$name]) {
                Remove-Item "Env:$name" -ErrorAction SilentlyContinue
            } else {
                [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
            }
        }

        if ($reservation) {
            $reservation.Dispose()
            $reservation = $null
            if (-not $startupAttempted -or -not $Run -or $cleanupSucceeded) {
                [IO.File]::Delete($reservationPath)
            }
        }
    }
}
