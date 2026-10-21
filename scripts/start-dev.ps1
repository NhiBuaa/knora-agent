param(
    [switch]$PreflightOnly,
    [switch]$NoBrowser,
    [string]$EnvFile,
    [string]$OllamaBaseUrl,
    [string]$EmbeddingProvider,
    [string]$GenerationProvider,
    [string]$GenerationModel,
    [string]$PythonExe,
    [string]$DatabaseName = 'knora_dev',
    [string]$ObjectStoreBucket,
    [int]$PostgresPort = 5432,
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendWatchRoot = 'backend\src\knora'
$workerRestartExitCode = 75
$composeProject = 'knora-dev'
$composeFiles = @(
    '-f', (Join-Path $repoRoot 'docker-compose.dev.yml')
)

function Fail([string]$Code) {
    [Console]::Error.WriteLine($Code)
    exit 2
}

$dockerCommandTimeoutMs = 10000
$dockerScanTimeoutMs = 30000

if (-not ('Knora.Dev.ProcessJob' -as [type])) {
    Add-Type -Path (Join-Path $PSScriptRoot 'dev-process-job.cs')
}

function Invoke-DockerMetadata([string[]]$CommandArgs, [System.Diagnostics.Stopwatch]$ScanWatch) {
    if ($ScanWatch -and $ScanWatch.ElapsedMilliseconds -ge $dockerScanTimeoutMs) {
        Fail "DOCKER_METADATA_TIMEOUT:$composeProject"
    }
    $remainingScanMs = if ($ScanWatch) { $dockerScanTimeoutMs - $ScanWatch.ElapsedMilliseconds } else { $dockerCommandTimeoutMs }
    $timeoutMs = [Math]::Min($dockerCommandTimeoutMs, [Math]::Max(100, [int]$remainingScanMs))

    $dockerFunc = Get-Command -Name 'docker' -CommandType Function -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($dockerFunc) {
        $output = & $dockerFunc @CommandArgs
        $cmdExit = $LASTEXITCODE
        if ($ScanWatch -and $ScanWatch.ElapsedMilliseconds -ge $dockerScanTimeoutMs) {
            Fail "DOCKER_METADATA_TIMEOUT:$composeProject"
        }
        $global:LASTEXITCODE = $cmdExit
        return $output
    }

    $dockerApp = Get-Command -Name 'docker' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $dockerApp) {
        $global:LASTEXITCODE = 1
        return $null
    }

    $metaJob = New-Object Knora.Dev.ProcessJob
    $tempDir = [System.IO.Path]::GetTempPath()
    $outPath = Join-Path $tempDir ([System.IO.Path]::GetRandomFileName())
    $errPath = Join-Path $tempDir ([System.IO.Path]::GetRandomFileName())
    try {
        $cmdArgsArray = [string[]]@($CommandArgs)
        $proc = $metaJob.Start($dockerApp.Source, $cmdArgsArray, $repoRoot, $outPath, $errPath)
        $completed = $metaJob.WaitForProcesses($timeoutMs)
        if (-not $completed) {
            $metaJob.Dispose()
            Fail "DOCKER_METADATA_TIMEOUT:$composeProject"
        }
        if ($ScanWatch -and $ScanWatch.ElapsedMilliseconds -ge $dockerScanTimeoutMs) {
            $metaJob.Dispose()
            Fail "DOCKER_METADATA_TIMEOUT:$composeProject"
        }
        $global:LASTEXITCODE = $proc.ExitCode
        if ($proc.ExitCode -ne 0) {
            return $null
        }
        $rawOut = if (Test-Path -LiteralPath $outPath) { [System.IO.File]::ReadAllText($outPath) } else { '' }
        if (-not $rawOut) { return @() }
        $lines = @($rawOut -split '\r?\n' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        return $lines
    } finally {
        if ($metaJob) { $metaJob.Dispose() }
        if (Test-Path -LiteralPath $outPath) { try { [System.IO.File]::Delete($outPath) } catch { } }
        if (Test-Path -LiteralPath $errPath) { try { [System.IO.File]::Delete($errPath) } catch { } }
    }
}

function Test-DevStorageOwnership([bool]$PostgresPortInUse) {
    try {
        $scanWatch = [System.Diagnostics.Stopwatch]::StartNew()
        $ids = @(Invoke-DockerMetadata @('ps', '-a', '--filter', "label=com.docker.compose.project=$composeProject", '--format', '{{.ID}}') $scanWatch)
        if ($LASTEXITCODE -ne 0) { return $false }

        $expectedVolumeConfig = @{
            "${composeProject}_knora_postgres_data" = @{
                Service = 'postgres'
                Destination = '/var/lib/postgresql/data'
                Role = 'knora_postgres_data'
            }
            "${composeProject}_knora_minio_data" = @{
                Service = 'minio'
                Destination = '/data'
                Role = 'knora_minio_data'
            }
            "${composeProject}_keycloak_dev_data" = @{
                Service = 'keycloak-dev'
                Destination = '/opt/keycloak/data'
                Role = 'keycloak_dev_data'
            }
            "${composeProject}_keycloak_dev_database" = @{
                Service = 'keycloak-dev-db'
                Destination = '/var/lib/postgresql/data'
                Role = 'keycloak_dev_database'
            }
        }

        $mountedVolumes = @{}
        $ownedPostgres = 0

        foreach ($id in $ids) {
            $rawLabels = Invoke-DockerMetadata @('inspect', $id, '--format', '{{json .Config.Labels}}') $scanWatch
            $labelJson = if ($rawLabels -is [array]) { $rawLabels -join '' } else { $rawLabels }
            $labels = if ($labelJson) { $labelJson | ConvertFrom-Json } else { $null }
            if ($LASTEXITCODE -ne 0 -or
                -not $labels -or
                -not $labels.PSObject.Properties['com.docker.compose.project'] -or
                $labels.'com.docker.compose.project' -ne $composeProject -or
                -not $labels.PSObject.Properties['com.docker.compose.project.working_dir'] -or
                -not $labels.'com.docker.compose.project.working_dir' -or
                [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repoRoot) {
                return $false
            }
            $service = if ($labels.PSObject.Properties['com.docker.compose.service']) { $labels.'com.docker.compose.service' } else { $null }
            if ($PostgresPortInUse -and $service -eq 'postgres') {
                $rawState = Invoke-DockerMetadata @('inspect', $id, '--format', '{{json .State}}') $scanWatch
                $stateJson = if ($rawState -is [array]) { $rawState -join '' } else { $rawState }
                $state = if ($stateJson) { $stateJson | ConvertFrom-Json } else { $null }
                if ($LASTEXITCODE -ne 0 -or -not $state -or -not $state.PSObject.Properties['Running'] -or -not $state.Running) {
                    return $false
                }
                $rawPorts = Invoke-DockerMetadata @('inspect', $id, '--format', '{{json .NetworkSettings.Ports}}') $scanWatch
                $portsJson = if ($rawPorts -is [array]) { $rawPorts -join '' } else { $rawPorts }
                $ports = if ($portsJson) { $portsJson | ConvertFrom-Json } else { $null }
                if ($LASTEXITCODE -ne 0 -or -not $ports -or -not $ports.PSObject.Properties['5432/tcp']) { return $false }
                $bindings = @($ports.'5432/tcp')
                if ($bindings.Count -eq 1 -and $bindings[0].HostIp -eq '127.0.0.1' -and
                    $bindings[0].HostPort -eq [string]$PostgresPort) { $ownedPostgres++ }
            }
            $rawMounts = Invoke-DockerMetadata @('inspect', $id, '--format', '{{json .Mounts}}') $scanWatch
            $mountsJson = if ($rawMounts -is [array]) { $rawMounts -join '' } else { $rawMounts }
            $mounts = if ($mountsJson) { $mountsJson | ConvertFrom-Json } else { $null }
            if ($LASTEXITCODE -ne 0) { return $false }
            foreach ($m in @($mounts)) {
                if ($m -and $m.PSObject.Properties['Type'] -and $m.Type -eq 'volume' -and
                    $m.PSObject.Properties['Name'] -and $m.Name) {
                    $mountedVolumes[$m.Name] = @{
                        Service = $service
                        Destination = if ($m.PSObject.Properties['Destination']) { [string]$m.Destination } else { $null }
                    }
                }
            }
        }

        # List all volume names from Docker daemon
        $allVolumeNames = @(Invoke-DockerMetadata @('volume', 'ls', '--format', '{{.Name}}') $scanWatch)
        if ($LASTEXITCODE -ne 0) { return $false }

        # List project-filtered volume names
        $filtered = @(Invoke-DockerMetadata @('volume', 'ls', '--filter', "label=com.docker.compose.project=$composeProject", '--format', '{{.Name}}') $scanWatch)
        if ($LASTEXITCODE -ne 0) { return $false }

        $existingVolumes = @()
        foreach ($v in $filtered) {
            if ($v -and $v -notin $existingVolumes) { $existingVolumes += $v }
        }
        foreach ($vol in $expectedVolumeConfig.Keys) {
            if ($vol -in $allVolumeNames -and $vol -notin $existingVolumes) {
                $existingVolumes += $vol
            }
        }

        # Path 1: Fresh project with no containers and no retained volumes
        if ($ids.Count -eq 0 -and $existingVolumes.Count -eq 0) {
            return (-not $PostgresPortInUse)
        }

        # If volumes remain but no verified containers exist, refuse
        if ($ids.Count -eq 0 -and $existingVolumes.Count -gt 0) {
            return $false
        }

        # Path 2: All existing volumes must belong to this checkout and match mounted containers
        foreach ($v in $existingVolumes) {
            $rawVolLabels = Invoke-DockerMetadata @('volume', 'inspect', $v, '--format', '{{json .Labels}}') $scanWatch
            if ($LASTEXITCODE -ne 0 -or $null -eq $rawVolLabels) {
                return $false
            }
            $volLabelsJson = if ($rawVolLabels -is [array]) { $rawVolLabels -join '' } else { $rawVolLabels }
            $volLabels = if ($volLabelsJson -and $volLabelsJson.Trim() -ne '') { $volLabelsJson | ConvertFrom-Json } else { $null }

            if (-not $volLabels -or
                -not $volLabels.PSObject.Properties['com.docker.compose.project'] -or
                -not $volLabels.'com.docker.compose.project' -or
                $volLabels.'com.docker.compose.project' -ne $composeProject) {
                return $false
            }
            if ($expectedVolumeConfig.ContainsKey($v)) {
                $expectedRole = $expectedVolumeConfig[$v].Role
                if (-not $volLabels.PSObject.Properties['com.docker.compose.volume'] -or
                    -not $volLabels.'com.docker.compose.volume' -or
                    $volLabels.'com.docker.compose.volume' -ne $expectedRole) {
                    return $false
                }
            }

            if (-not $mountedVolumes.ContainsKey($v)) {
                return $false
            }

            $mountInfo = $mountedVolumes[$v]
            if ($expectedVolumeConfig.ContainsKey($v)) {
                $expectedCfg = $expectedVolumeConfig[$v]
                if ($mountInfo.Service -ne $expectedCfg.Service) {
                    return $false
                }
                $destNorm = if ($mountInfo.Destination) { $mountInfo.Destination.TrimEnd('/').Replace('\', '/') } else { '' }
                $expectedDestNorm = $expectedCfg.Destination.TrimEnd('/').Replace('\', '/')
                if ($destNorm -ne $expectedDestNorm) {
                    return $false
                }
            }
        }

        return (-not $PostgresPortInUse -or $ownedPostgres -eq 1)
    } catch {
        if ($_.Exception.Message -like "*DOCKER_METADATA_TIMEOUT*") {
            Fail "DOCKER_METADATA_TIMEOUT:$composeProject"
        }
        return $false
    }
}

function Import-DotEnv([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $lineNumber = 0
    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $lineNumber++
        $trimmed = $rawLine.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $separator = $rawLine.IndexOf('=')
        if ($separator -le 0) { Fail "INVALID_DOTENV_ENTRY:$lineNumber" }
        $name = $rawLine.Substring(0, $separator).Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            Fail "INVALID_DOTENV_ENTRY:$lineNumber"
        }
        $value = $rawLine.Substring($separator + 1)
        $existing = [Environment]::GetEnvironmentVariable(
            $name,
            [EnvironmentVariableTarget]::Process
        )
        if ($null -eq $existing) {
            [Environment]::SetEnvironmentVariable(
                $name,
                $value,
                [EnvironmentVariableTarget]::Process
            )
        }
    }
}

if ($EnvFile) {
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { Fail 'ENV_FILE_UNAVAILABLE' }
    $dotenvPath = (Resolve-Path -LiteralPath $EnvFile).Path
} else {
    $dotenvPath = Join-Path $repoRoot '.env'
}
Import-DotEnv $dotenvPath

$reservation = $null
$reservationPath = Join-Path ([IO.Path]::GetTempPath()) "knora-dev-reservation-$composeProject.lock"
$cleanupFailed = $false
$mutatingStarted = $false
$startupConfirmed = $false

if (-not $PreflightOnly) {
    try {
        $reservation = [IO.File]::Open(
            $reservationPath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )
        $writer = [System.IO.StreamWriter]::new($reservation, [System.Text.Encoding]::UTF8)
        $writer.WriteLine("PID=$PID")
        $writer.WriteLine("REPO=$repoRoot")
        $writer.WriteLine("PROJECT=$composeProject")
        $writer.WriteLine("TIMESTAMP=$([DateTime]::UtcNow.ToString('o'))")
        $writer.Flush()
    } catch {
        Fail "DEV_PROJECT_RESERVED:$composeProject"
    }
}

try {
# Check before provider calls, Compose changes, migrations, or truncating shared logs.
# PreflightOnly checks provider configuration without claiming application ports.
if (-not $PreflightOnly) {
    # Avoid NetTCPIP/CIM cold-start latency for this read-only safety check.
    $listeners = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    foreach ($binding in @(@('ApiPort', $ApiPort), @('FrontendPort', $FrontendPort))) {
        if ($binding[1] -in $listeners.Port) { Fail "PORT_IN_USE:$($binding[0]):$($binding[1])" }
    }
    $postgresPortInUse = $PostgresPort -in $listeners.Port
    if (-not (Test-DevStorageOwnership $postgresPortInUse)) {
        if (-not $postgresPortInUse) { Fail "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:$composeProject. Existing services were not changed." }
        $owner = 'unverified'
        try {
            $ownerIds = @(Get-NetTCPConnection -State Listen -LocalPort $PostgresPort -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique)
            $owner = ($ownerIds | ForEach-Object {
                $process = Get-Process -Id $_ -ErrorAction Stop
                "$($process.Id)/$($process.ProcessName)"
            }) -join ','
        } catch { }
        Fail "PORT_IN_USE:PostgresPort:$PostgresPort owner=$owner; choose a free port with -PostgresPort. Existing services were not changed."
    }
}

if (-not $EmbeddingProvider) {
    $EmbeddingProvider = if ($env:KNORA_EMBEDDING_PROVIDER) { $env:KNORA_EMBEDDING_PROVIDER } else { 'cloudflare-workers-ai' }
}
if ($EmbeddingProvider -notin @('cloudflare-workers-ai', 'ollama', 'deterministic-local')) { Fail 'INVALID_EMBEDDING_PROVIDER' }
if (-not $GenerationProvider) {
    $GenerationProvider = if ($env:KNORA_GENERATION_PROVIDER) { $env:KNORA_GENERATION_PROVIDER } else { 'cloudflare-workers-ai' }
}
if ($GenerationProvider -notin @('cloudflare-workers-ai', 'ollama', 'deterministic-local')) { Fail 'INVALID_GENERATION_PROVIDER' }
if (-not $GenerationModel) {
    $GenerationModel = if ($env:KNORA_OLLAMA_GENERATION_MODEL) { $env:KNORA_OLLAMA_GENERATION_MODEL } else { 'qwen3:8b' }
}
if ($GenerationProvider -eq 'ollama' -and $GenerationModel -notin @('qwen3:8b', 'qwen3:4b', 'gpt-oss:20b')) {
    Fail 'INVALID_GENERATION_MODEL'
}
if ($GenerationProvider -ne 'ollama' -and $PSBoundParameters.ContainsKey('GenerationModel')) { Fail 'INVALID_GENERATION_MODEL' }

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { Fail 'WINDOWS_RUNTIME_REQUIRED' }
if (-not $PythonExe) {
    $candidates = @(
        (Join-Path $repoRoot '.venv\Scripts\python.exe'),
        (Join-Path $repoRoot '..\..\knora-agent\.venv\Scripts\python.exe')
    )
    $PythonExe = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Fail 'PYTHON_RUNTIME_UNAVAILABLE'
}
if ($EmbeddingProvider -eq 'ollama' -or $GenerationProvider -eq 'ollama') {
    if (-not $OllamaBaseUrl) {
        $OllamaBaseUrl = if ($env:KNORA_OLLAMA_BASE_URL) {
            $env:KNORA_OLLAMA_BASE_URL
        } else {
            'http://127.0.0.1:11434'
        }
    }
    if ($OllamaBaseUrl -notmatch '^http://(127\.0\.0\.1|localhost):[0-9]{1,5}$') {
        Fail 'OLLAMA_LOCAL_ENDPOINT_REQUIRED'
    }
    $OllamaBaseUrl = $OllamaBaseUrl.TrimEnd('/')
}
if (-not $ObjectStoreBucket) {
    $ObjectStoreBucket = if ($env:KNORA_OBJECT_STORE_S3_BUCKET) {
        $env:KNORA_OBJECT_STORE_S3_BUCKET
    } else {
        'knora'
    }
}
if ($DatabaseName -notmatch '^[a-z][a-z0-9_]{0,62}$') { Fail 'INVALID_DATABASE_NAME' }

$env:PYTHONPATH = "$repoRoot\backend\src;$repoRoot"
if ($OllamaBaseUrl) { $env:KNORA_OLLAMA_BASE_URL = $OllamaBaseUrl }
if ($EmbeddingProvider -eq 'ollama') { $env:KNORA_OLLAMA_EMBEDDING_MODEL = 'qwen3-embedding:0.6b' }
$env:KNORA_EMBEDDING_PROVIDER = $EmbeddingProvider
$env:KNORA_GENERATION_PROVIDER = $GenerationProvider
$env:KNORA_OLLAMA_GENERATION_MODEL = $GenerationModel
Remove-Item Env:KNORA_EXPECTED_GENERATION_MODEL_DIGEST -ErrorAction SilentlyContinue
$env:KNORA_EMBEDDING_DIMENSION = if ($EmbeddingProvider -eq 'deterministic-local') { '1536' } else { '1024' }
$env:KNORA_M5_E2E_FAULTS_ENABLED = 'false'
$env:KNORA_API_URL = "http://127.0.0.1:$ApiPort"
$env:KNORA_BACKEND_URL = $env:KNORA_API_URL
$devIssuer = 'http://127.0.0.1:8180/realms/knora-dev'
if ($env:KEYCLOAK_ISSUER -and $env:KNORA_KEYCLOAK_ISSUER -and
    $env:KEYCLOAK_ISSUER -ne $env:KNORA_KEYCLOAK_ISSUER) {
    Fail 'OIDC_ISSUER_MISMATCH'
}
$oidcIssuer = if ($env:KEYCLOAK_ISSUER) {
    $env:KEYCLOAK_ISSUER
} elseif ($env:KNORA_KEYCLOAK_ISSUER) {
    $env:KNORA_KEYCLOAK_ISSUER
} else {
    $devIssuer
}
$oidcBase = "$oidcIssuer/protocol/openid-connect"
if (-not $env:KEYCLOAK_ISSUER) { $env:KEYCLOAK_ISSUER = $oidcIssuer }
if (-not $env:KNORA_KEYCLOAK_ISSUER) { $env:KNORA_KEYCLOAK_ISSUER = $oidcIssuer }
if (-not $env:KEYCLOAK_AUTHORIZATION_URL) { $env:KEYCLOAK_AUTHORIZATION_URL = "$oidcBase/auth" }
if (-not $env:KEYCLOAK_TOKEN_URL) { $env:KEYCLOAK_TOKEN_URL = "$oidcBase/token" }
if (-not $env:KEYCLOAK_JWKS_URL) { $env:KEYCLOAK_JWKS_URL = "$oidcBase/certs" }
if (-not $env:KNORA_KEYCLOAK_JWKS_URL) { $env:KNORA_KEYCLOAK_JWKS_URL = $env:KEYCLOAK_JWKS_URL }
if (-not $env:KEYCLOAK_CLIENT_ID) { $env:KEYCLOAK_CLIENT_ID = 'knora-web' }
if (-not $env:KEYCLOAK_AUDIENCE) { $env:KEYCLOAK_AUDIENCE = $env:KEYCLOAK_CLIENT_ID }
if (-not $env:KNORA_KEYCLOAK_AUDIENCE) { $env:KNORA_KEYCLOAK_AUDIENCE = $env:KEYCLOAK_AUDIENCE }
$useBundledKeycloak = $oidcIssuer -eq $devIssuer
$appOrigin = "http://127.0.0.1:$FrontendPort"
if ($PSBoundParameters.ContainsKey('FrontendPort') -or -not $env:KEYCLOAK_REDIRECT_URI) {
    $env:KEYCLOAK_REDIRECT_URI = "$appOrigin/api/auth/callback"
}
if ($PSBoundParameters.ContainsKey('FrontendPort') -or -not $env:KEYCLOAK_POST_LOGOUT_REDIRECT_URI) {
    $env:KEYCLOAK_POST_LOGOUT_REDIRECT_URI = "$appOrigin/"
}
if ($PSBoundParameters.ContainsKey('FrontendPort') -or -not $env:NEXT_PUBLIC_APP_ORIGIN) {
    $env:NEXT_PUBLIC_APP_ORIGIN = $appOrigin
}
$env:KNORA_DATABASE_URL = "postgresql+psycopg://knora:knora@127.0.0.1:$PostgresPort/$DatabaseName"
Remove-Item Env:KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID -ErrorAction SilentlyContinue

if ($EmbeddingProvider -eq 'ollama' -or $GenerationProvider -eq 'ollama') {
    try {
        $tags = Invoke-RestMethod -Method Get -Uri "$OllamaBaseUrl/api/tags" -TimeoutSec 5
    } catch {
        Fail 'OLLAMA_UNAVAILABLE'
    }
}
if ($EmbeddingProvider -eq 'ollama') {
    $matching = @($tags.models | Where-Object { $_.name -eq 'qwen3-embedding:0.6b' })
    if ($matching.Count -ne 1 -or $matching[0].digest -notmatch '^(sha256:)?[0-9a-fA-F]{64}$') {
        Fail 'MODEL_UNAVAILABLE'
    }
    try {
        $show = Invoke-RestMethod -Method Post -Uri "$OllamaBaseUrl/api/show" -ContentType 'application/json' -Body '{"model":"qwen3-embedding:0.6b"}' -TimeoutSec 10
        $embedded = Invoke-RestMethod -Method Post -Uri "$OllamaBaseUrl/api/embed" -ContentType 'application/json' -Body '{"model":"qwen3-embedding:0.6b","input":["Knora dev profile check"],"truncate":false}' -TimeoutSec 90
    } catch {
        Fail 'OLLAMA_CONTRACT_UNAVAILABLE'
    }
    if (-not $show.details.family -or -not $show.details.quantization_level) {
        Fail 'MODEL_METADATA_UNAVAILABLE'
    }
    if ($embedded.model -ne 'qwen3-embedding:0.6b' -or @($embedded.embeddings).Count -ne 1 -or @($embedded.embeddings[0]).Count -ne 1024) {
        Fail 'DIMENSION_MISMATCH'
    }
}
if ($GenerationProvider -eq 'ollama') {
    $generationModels = @($tags.models | Where-Object { $_.name -eq $GenerationModel })
    if ($generationModels.Count -ne 1 -or $generationModels[0].digest -notmatch '^(sha256:)?[0-9a-fA-F]{64}$') {
        Fail 'GENERATION_MODEL_UNAVAILABLE'
    }
    $env:KNORA_EXPECTED_GENERATION_MODEL_DIGEST = 'sha256:' + (($generationModels[0].digest -replace '^sha256:', '').ToLowerInvariant())
}
$profileCheck = 'from knora.infrastructure.settings import Settings; from knora.bootstrap import build_provider_selection; print(build_provider_selection(Settings(_env_file=None)).embedding_configuration.id)'
$ErrorActionPreference = 'Continue'
$profileId = (& $PythonExe -c $profileCheck 2>$null | Select-Object -Last 1)
$profileExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($profileExit -ne 0 -or -not $profileId -or
    ($EmbeddingProvider -eq 'ollama' -and $profileId -notmatch '^embedding-ollama-qwen3-[0-9a-f]{24}$') -or
    ($EmbeddingProvider -eq 'cloudflare-workers-ai' -and $profileId -ne 'embedding-cloudflare-qwen3-06b-v1') -or
    ($EmbeddingProvider -eq 'deterministic-local' -and $profileId -ne 'embedding-local-m1-v2')) {
    Fail 'PROFILE_RESOLUTION_FAILED'
}
$env:KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID = $profileId
$ErrorActionPreference = 'Continue'
$pinnedProfile = (& $PythonExe -c $profileCheck 2>$null | Select-Object -Last 1)
$profileExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($profileExit -ne 0 -or $pinnedProfile -ne $profileId) {
    Fail 'PROFILE_MISMATCH'
}
& $PythonExe -m knora.adapters.cli.worker --check-pdf-isolation 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'PDF_ISOLATION_UNAVAILABLE' }
Write-Output "PRECHECK_OK $profileId"
Write-Output "EMBEDDING_PROVIDER=$EmbeddingProvider"
Write-Output "GENERATION_PROVIDER=$GenerationProvider"
if ($GenerationProvider -eq 'ollama') {
    Write-Output "GENERATION_MODEL=$GenerationModel"
    Write-Output "GENERATION_DIGEST=$env:KNORA_EXPECTED_GENERATION_MODEL_DIGEST"
}
if ($GenerationProvider -eq 'cloudflare-workers-ai') {
    Write-Output 'GENERATION_MODEL=@cf/openai/gpt-oss-20b'
}
Write-Output "API_URL=$env:KNORA_API_URL"
Write-Output "OIDC_REDIRECT_URI=$env:KEYCLOAK_REDIRECT_URI"
Write-Output "OIDC_ISSUER=$oidcIssuer"
if ($PreflightOnly) { return }

if (-not $env:SESSION_SECRET) { Fail 'SESSION_SECRET_REQUIRED' }

$minioAccessKey = $env:KNORA_CANONICAL_MINIO_ACCESS_KEY
$minioSecretKey = $env:KNORA_CANONICAL_MINIO_SECRET_KEY
if (-not $minioAccessKey) { $minioAccessKey = $env:KNORA_OBJECT_STORE_S3_ACCESS_KEY }
if (-not $minioSecretKey) { $minioSecretKey = $env:KNORA_OBJECT_STORE_S3_SECRET_KEY }
if (-not $minioAccessKey -or -not $minioSecretKey) { Fail 'MINIO_CREDENTIALS_REQUIRED' }

$env:KNORA_CANONICAL_MINIO_ACCESS_KEY = $minioAccessKey
$env:KNORA_CANONICAL_MINIO_SECRET_KEY = $minioSecretKey
$env:KNORA_EVAL_POSTGRES_HOST_PORT = [string]$PostgresPort
$env:KNORA_OBJECT_STORE_BACKEND = 's3_compatible'
$env:KNORA_OBJECT_STORE_S3_ENDPOINT = 'http://127.0.0.1:9000'
$env:KNORA_OBJECT_STORE_S3_BUCKET = $ObjectStoreBucket
$env:KNORA_OBJECT_STORE_S3_ACCESS_KEY = $minioAccessKey
$env:KNORA_OBJECT_STORE_S3_SECRET_KEY = $minioSecretKey
if (-not $env:KNORA_OBJECT_STORE_S3_REGION) { $env:KNORA_OBJECT_STORE_S3_REGION = 'us-east-1' }

Push-Location $repoRoot
$mutatingStarted = $true
try {
    $storageServices = @('postgres', 'minio')
    if ($useBundledKeycloak) { $storageServices += 'keycloak-dev' }
    docker compose @composeFiles -p $composeProject up -d --wait @storageServices | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail 'STORAGE_START_FAILED' }
    docker compose @composeFiles -p $composeProject run --rm --no-deps minio-init | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail 'OBJECT_STORE_INIT_FAILED' }

    $existing = docker compose @composeFiles -p $composeProject exec -T postgres psql -U knora -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DatabaseName'"
    if ($LASTEXITCODE -ne 0) { Fail 'DATABASE_CHECK_FAILED' }
    if (($existing | Out-String).Trim() -ne '1') {
        docker compose @composeFiles -p $composeProject exec -T postgres psql -U knora -d postgres -c "CREATE DATABASE $DatabaseName" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail 'DATABASE_CREATE_FAILED' }
    }
    & $PythonExe -m alembic -c backend/alembic.ini upgrade head | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail 'DATABASE_MIGRATION_FAILED' }

    $logs = Join-Path $env:TEMP 'knora-dev-runtime'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $env:PORT = [string]$FrontendPort
    $workerGeneration = 0
    if (-not ('Knora.Dev.ProcessJob' -as [type])) {
        Add-Type -Path (Join-Path $PSScriptRoot 'dev-process-job.cs')
    }
    $processJob = [Knora.Dev.ProcessJob]::new()

    function Start-DevProcess([string]$FilePath, [string[]]$ArgumentList,
        [string]$RedirectStandardOutput, [string]$RedirectStandardError) {
        return $processJob.Start($FilePath, $ArgumentList, $repoRoot,
            $RedirectStandardOutput, $RedirectStandardError)
    }

    function Start-DevWorker {
        $script:workerGeneration++
        $stdout = Join-Path $logs "worker-$script:workerGeneration.out.log"
        $stderr = Join-Path $logs "worker-$script:workerGeneration.err.log"
        Write-Host "[worker] starting generation $script:workerGeneration"
        return Start-DevProcess -FilePath $PythonExe -ArgumentList @(
            '-m','knora.adapters.cli.worker',
            '--dev-watch',
            '--watch-root',$backendWatchRoot
        ) -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    }

    $api = $null
    $worker = $null
    $conversationWorker = $null
    $frontend = $null
    try {
        $api = Start-DevProcess -FilePath $PythonExe -ArgumentList @(
            '-m','uvicorn','knora.main:app',
            '--host','127.0.0.1',
            '--port',[string]$ApiPort,
            '--reload',
            '--reload-dir',$backendWatchRoot
        ) -RedirectStandardOutput (Join-Path $logs 'api.out.log') -RedirectStandardError (Join-Path $logs 'api.err.log')
        $worker = Start-DevWorker
        $conversationWorker = Start-DevProcess -FilePath $PythonExe -ArgumentList @(
            'scripts/run_conversation_worker.py'
        ) -RedirectStandardOutput (Join-Path $logs 'conversation-worker.out.log') -RedirectStandardError (Join-Path $logs 'conversation-worker.err.log')
        $frontend = Start-DevProcess -FilePath $npm -ArgumentList @('--prefix','frontend','run','dev') -RedirectStandardOutput (Join-Path $logs 'frontend.out.log') -RedirectStandardError (Join-Path $logs 'frontend.err.log')
        $startupConfirmed = $true

        $apiHealthy = $false
        $frontendHealthy = $false
        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            Start-Sleep -Seconds 1
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2
                if ($health.status -eq 'ok') { $apiHealthy = $true }
            } catch { }
            try {
                $frontendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -MaximumRedirection 0 -UseBasicParsing -TimeoutSec 2
                if ([int]$frontendResponse.StatusCode -ge 200 -and [int]$frontendResponse.StatusCode -lt 400) { $frontendHealthy = $true }
            } catch {
                if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -ge 300 -and [int]$_.Exception.Response.StatusCode -lt 400) { $frontendHealthy = $true }
            }
            if ($api.HasExited -or $worker.HasExited -or $conversationWorker.HasExited -or $frontend.HasExited) { break }
            if ($apiHealthy -and $frontendHealthy) { break }
        }
        if (-not $apiHealthy -or -not $frontendHealthy -or $api.HasExited -or $worker.HasExited -or $conversationWorker.HasExited -or $frontend.HasExited) {
            throw 'RUNTIME_START_FAILED'
        }

        Write-Output "DEV_READY API_PID=$($api.Id) WORKER_PID=$($worker.Id) CONVERSATION_WORKER_PID=$($conversationWorker.Id) FRONTEND_PID=$($frontend.Id)"
        Write-Output "LOG_DIR=$logs"
        Write-Output "[api] auto-reload enabled for backend/src/knora"
        Write-Output "[worker] restart-on-change enabled; current job drains before restart"
        Write-Output "[conversation-worker] durable Turns enabled"
        Write-Output "[frontend] Next.js Fast Refresh enabled"
        Write-Output "Press Ctrl+C to stop API, both workers and frontend. PostgreSQL/MinIO stay running."
        if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$FrontendPort" | Out-Null }

                while ($true) {
            Start-Sleep -Milliseconds 500
            if ($api.HasExited) {
                throw "API_EXITED:$($api.ExitCode)"
            }
            if ($frontend.HasExited) {
                throw "FRONTEND_EXITED:$($frontend.ExitCode)"
            }
            if ($conversationWorker.HasExited) {
                throw "CONVERSATION_WORKER_EXITED:$($conversationWorker.ExitCode)"
            }
            if ($worker.HasExited) {
                $exitCode = $worker.ExitCode
                if ($exitCode -ne $workerRestartExitCode) {
                    throw "WORKER_EXITED:$exitCode"
                }
                Write-Output '[worker] source changed; drained current job and exited cleanly'
                $worker = Start-DevWorker
                Start-Sleep -Milliseconds 300
                if ($worker.HasExited) {
                    throw "WORKER_RESTART_FAILED:$($worker.ExitCode)"
                }
                Write-Output "[worker] ready generation $workerGeneration"
            }
        }
    } finally {
        try {
            if ($processJob) { $processJob.Dispose() }
            [Console]::WriteLine('DEV_STOPPED')
        } catch {
            $cleanupFailed = $true
            [Console]::Error.WriteLine("DEV_CLEANUP_FAILED:$($_.Exception.Message)")
            $global:LASTEXITCODE = 2
            throw
        }
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    Fail 'DEV_RUNTIME_FAILED'
} finally {
    Pop-Location
}
} finally {
    if ($reservation) {
        try {
            $reservation.Dispose()
        } catch { }
        if (-not $cleanupFailed -and (-not $mutatingStarted -or $startupConfirmed)) {
            try { [IO.File]::Delete($reservationPath) } catch { }
        } else {
            [Console]::Error.WriteLine("DEV_RESERVATION_RETAINED:$reservationPath - Mutating startup or cleanup did not complete cleanly. Inspect and remove lock file manually after verifying container and process state.")
        }
    }
}
