param(
    [string]$OllamaBaseUrl = 'http://127.0.0.1:11434',
    [string]$GenerationModel = 'qwen3:8b'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($OllamaBaseUrl -notmatch '^http://(127\.0\.0\.1|localhost):[0-9]{1,5}$') {
    throw 'OLLAMA_LOCAL_ENDPOINT_REQUIRED'
}
if ($GenerationModel -notin @('qwen3:8b', 'qwen3:4b', 'gpt-oss:20b')) {
    throw 'GENERATION_MODEL_UNSUPPORTED'
}

try {
    $tags = Invoke-RestMethod -Uri "$OllamaBaseUrl/api/tags" -TimeoutSec 5
} catch {
    throw 'OLLAMA_UNAVAILABLE'
}
$matching = @($tags.models | Where-Object { $_.name -eq $GenerationModel })
if ($matching.Count -ne 1 -or $matching[0].digest -notmatch '^(sha256:)?[0-9a-fA-F]{64}$') {
    throw 'GENERATION_MODEL_UNAVAILABLE'
}

$env:KNORA_GENERATION_PROVIDER = 'ollama'
$env:KNORA_OLLAMA_GENERATION_MODEL = $GenerationModel
$env:KNORA_OLLAMA_BASE_URL = $OllamaBaseUrl
$gateStartedAt = [DateTimeOffset]::UtcNow.ToString('o')
Push-Location $repoRoot
try {
    npm --prefix frontend run test:e2e -- --config playwright.ollama.config.ts
    if ($LASTEXITCODE -ne 0) { throw 'OLLAMA_BROWSER_GATE_FAILED' }
    $pythonCandidates = @(
        (Join-Path $repoRoot '.venv\Scripts\python.exe'),
        (Join-Path $repoRoot '..\..\knora-agent\.venv\Scripts\python.exe')
    )
    $python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $python) { throw 'PYTHON_RUNTIME_UNAVAILABLE' }
    & $python scripts/verify_ollama_conversation.py --since $gateStartedAt
    if ($LASTEXITCODE -ne 0) { throw 'OLLAMA_TRACE_GATE_FAILED' }
} finally {
    Pop-Location
}
