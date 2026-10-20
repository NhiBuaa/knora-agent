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

# Check before provider calls, Compose changes, migrations, or truncating shared logs.
# PreflightOnly checks provider configuration without claiming application ports.
if (-not $PreflightOnly) {
    # Avoid NetTCPIP/CIM cold-start latency for this read-only safety check.
    $listeners = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    foreach ($binding in @(@('ApiPort', $ApiPort), @('FrontendPort', $FrontendPort))) {
        if ($binding[1] -in $listeners.Port) { Fail "PORT_IN_USE:$($binding[0]):$($binding[1])" }
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

if (-not $IsWindows -and $env:OS -ne 'Windows_NT') { Fail 'WINDOWS_RUNTIME_REQUIRED' }
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
            $processJob.Dispose()
            [Console]::WriteLine('DEV_STOPPED')
        } catch {
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
