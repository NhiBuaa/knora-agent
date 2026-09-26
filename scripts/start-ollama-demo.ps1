param(
    [switch]$PreflightOnly,
    [switch]$NoBrowser,
    [switch]$UseExistingStorage,
    [string]$OllamaBaseUrl = 'http://127.0.0.1:11434',
    [string]$PythonExe,
    [string]$DatabaseName = 'knora_issue103_demo',
    [string]$DatabaseUrl,
    [string]$ObjectStoreEndpoint,
    [string]$ObjectStoreBucket = 'knora',
    [int]$PostgresPort = 5432,
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Fail([string]$Code) {
    [Console]::Error.WriteLine($Code)
    exit 2
}

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
if ($OllamaBaseUrl -notmatch '^http://(127\.0\.0\.1|localhost):[0-9]{1,5}$') {
    Fail 'OLLAMA_LOCAL_ENDPOINT_REQUIRED'
}
$OllamaBaseUrl = $OllamaBaseUrl.TrimEnd('/')
$env:PYTHONPATH = "$repoRoot\backend\src;$repoRoot"
$env:KNORA_OLLAMA_BASE_URL = $OllamaBaseUrl
$env:KNORA_OLLAMA_EMBEDDING_MODEL = 'qwen3-embedding:0.6b'
$env:KNORA_EMBEDDING_PROVIDER = 'ollama'
$env:KNORA_GENERATION_PROVIDER = 'deterministic-local'
$env:KNORA_EMBEDDING_DIMENSION = '1024'
$env:KNORA_API_URL = "http://127.0.0.1:$ApiPort"
Remove-Item Env:KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID -ErrorAction SilentlyContinue

try {
    $tags = Invoke-RestMethod -Method Get -Uri "$OllamaBaseUrl/api/tags" -TimeoutSec 5
} catch {
    Fail 'OLLAMA_UNAVAILABLE'
}
$matching = @($tags.models | Where-Object { $_.name -eq 'qwen3-embedding:0.6b' })
if ($matching.Count -ne 1 -or $matching[0].digest -notmatch '^(sha256:)?[0-9a-fA-F]{64}$') {
    Fail 'MODEL_UNAVAILABLE'
}
try {
    $show = Invoke-RestMethod -Method Post -Uri "$OllamaBaseUrl/api/show" -ContentType 'application/json' -Body '{"model":"qwen3-embedding:0.6b"}' -TimeoutSec 10
    $embedded = Invoke-RestMethod -Method Post -Uri "$OllamaBaseUrl/api/embed" -ContentType 'application/json' -Body '{"model":"qwen3-embedding:0.6b","input":["Knora profile check"],"truncate":false}' -TimeoutSec 90
} catch {
    Fail 'OLLAMA_CONTRACT_UNAVAILABLE'
}
if (-not $show.details.family -or -not $show.details.quantization_level) {
    Fail 'MODEL_METADATA_UNAVAILABLE'
}
if ($embedded.model -ne 'qwen3-embedding:0.6b' -or @($embedded.embeddings).Count -ne 1 -or @($embedded.embeddings[0]).Count -ne 1024) {
    Fail 'DIMENSION_MISMATCH'
}

& $PythonExe -m knora.adapters.cli.worker --check-pdf-isolation 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'PDF_ISOLATION_UNAVAILABLE' }
$profileId = (& $PythonExe -m knora.adapters.cli.worker --profile-id 2>$null | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $profileId -notmatch '^embedding-ollama-qwen3-[0-9a-f]{24}$') {
    Fail 'PROFILE_RESOLUTION_FAILED'
}
$env:KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID = $profileId
$pinnedProfile = (& $PythonExe -m knora.adapters.cli.worker --profile-id 2>$null | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $pinnedProfile -ne $profileId) {
    Fail 'PROFILE_MISMATCH'
}
Write-Output "PRECHECK_OK $profileId"
Write-Output "API_URL=$env:KNORA_API_URL"
if ($UseExistingStorage -and (-not $DatabaseUrl -or -not $ObjectStoreEndpoint)) {
    Fail 'EXISTING_STORAGE_CONFIG_REQUIRED'
}
if ($PreflightOnly) { return }

if ($UseExistingStorage) {
    if (-not $env:KNORA_OBJECT_STORE_S3_ACCESS_KEY -or -not $env:KNORA_OBJECT_STORE_S3_SECRET_KEY) {
        Fail 'EXISTING_STORAGE_CREDENTIALS_REQUIRED'
    }
    $env:KNORA_DATABASE_URL = $DatabaseUrl
    $env:KNORA_OBJECT_STORE_S3_ENDPOINT = $ObjectStoreEndpoint
} else {
    if ($DatabaseName -notmatch '^[a-z][a-z0-9_]{0,62}$') { Fail 'INVALID_DATABASE_NAME' }
    if (-not $env:KNORA_CANONICAL_MINIO_ACCESS_KEY -or -not $env:KNORA_CANONICAL_MINIO_SECRET_KEY) {
        Fail 'MINIO_CREDENTIALS_REQUIRED'
    }
    $env:KNORA_EVAL_POSTGRES_HOST_PORT = [string]$PostgresPort
    $env:KNORA_DATABASE_URL = "postgresql+psycopg://knora:knora@127.0.0.1:$PostgresPort/$DatabaseName"
    $env:KNORA_OBJECT_STORE_S3_ENDPOINT = 'http://127.0.0.1:9000'
    $env:KNORA_OBJECT_STORE_S3_ACCESS_KEY = $env:KNORA_CANONICAL_MINIO_ACCESS_KEY
    $env:KNORA_OBJECT_STORE_S3_SECRET_KEY = $env:KNORA_CANONICAL_MINIO_SECRET_KEY
}
$env:KNORA_OBJECT_STORE_BACKEND = 's3_compatible'
$env:KNORA_OBJECT_STORE_S3_BUCKET = $ObjectStoreBucket
if (-not $env:KNORA_OBJECT_STORE_S3_REGION) { $env:KNORA_OBJECT_STORE_S3_REGION = 'us-east-1' }

Push-Location $repoRoot
try {
    if ($UseExistingStorage) {
        & $PythonExe -m alembic -c backend/alembic.ini current --check-heads | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail 'EXISTING_DATABASE_NOT_AT_HEAD' }
    } else {
        docker compose -p issue-103-ollama-reindex up -d postgres minio minio-init | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail 'STORAGE_START_FAILED' }
        $existing = docker compose -p issue-103-ollama-reindex exec -T postgres psql -U knora -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DatabaseName'"
        if ($LASTEXITCODE -ne 0) { Fail 'DATABASE_CHECK_FAILED' }
        if (($existing | Out-String).Trim() -ne '1') {
            docker compose -p issue-103-ollama-reindex exec -T postgres psql -U knora -d postgres -c "CREATE DATABASE $DatabaseName" | Out-Null
            if ($LASTEXITCODE -ne 0) { Fail 'DATABASE_CREATE_FAILED' }
        }
        & $PythonExe -m alembic -c backend/alembic.ini upgrade head | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail 'DATABASE_MIGRATION_FAILED' }
    }

    $logs = Join-Path $env:TEMP 'knora-issue103-runtime'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $started = @()
    try {
        $api = Start-Process -FilePath $PythonExe -ArgumentList @('-m','uvicorn','knora.main:app','--host','127.0.0.1','--port',[string]$ApiPort) -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'api.out.log') -RedirectStandardError (Join-Path $logs 'api.err.log')
        $started += $api
        $worker = Start-Process -FilePath $PythonExe -ArgumentList @('-m','knora.adapters.cli.worker') -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'worker.out.log') -RedirectStandardError (Join-Path $logs 'worker.err.log')
        $started += $worker
        $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
        $env:PORT = [string]$FrontendPort
        $frontend = Start-Process -FilePath $npm -ArgumentList @('--prefix','frontend','run','dev') -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'frontend.out.log') -RedirectStandardError (Join-Path $logs 'frontend.err.log')
        $started += $frontend
        $apiHealthy = $false
        $frontendHealthy = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
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
            if ($api.HasExited -or $worker.HasExited -or $frontend.HasExited) { break }
            if ($apiHealthy -and $frontendHealthy) { break }
        }
        if (-not $apiHealthy -or -not $frontendHealthy -or $worker.HasExited -or $frontend.HasExited) { throw 'RUNTIME_START_FAILED' }
        Write-Output "API_PID=$($api.Id) WORKER_PID=$($worker.Id) FRONTEND_PID=$($frontend.Id)"
        Write-Output "LOG_DIR=$logs"
        if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$FrontendPort" | Out-Null }
    } catch {
        foreach ($process in $started) {
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        }
        Fail 'RUNTIME_START_FAILED'
    }
} finally {
    Pop-Location
}
