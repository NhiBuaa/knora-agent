param(
    [string]$ProjectSuffix = ''
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path $PSScriptRoot -Parent

# Preflight: Detect and reject conflicting ambient variables per runbook (no silent wiping)
$conflicts = @()
foreach ($item in Get-ChildItem Env:) {
    if ($item.Name -match '^(COMPOSE_PROJECT_NAME|FIGMA_E2E_|M5_E2E_|KEYCLOAK_PORT)' -and $item.Value.Trim()) {
        $conflicts += $item.Name
    }
}
if ($conflicts.Count -gt 0) {
    throw "AMBIENT_CONFLICT_DETECTED: Conflicting environment variables set: $($conflicts -join ', '). Clean environment before launch."
}

$suffix = if ($ProjectSuffix) { $ProjectSuffix } else { (Get-Random -Minimum 100000 -Maximum 999999).ToString() }
$project = "knora-figma-e2e-copy-$suffix"

# Distinct per-run evidence directory: reject collisions, never overwrite
$evidenceRoot = Join-Path $repositoryRoot 'frontend/test-results/copy-runtime'
$runEvidenceDir = Join-Path $evidenceRoot "run-$suffix"
if (Test-Path -LiteralPath $runEvidenceDir) {
    throw "EVIDENCE_COLLISION_DETECTED: Directory $runEvidenceDir already exists. Use a distinct project suffix."
}
New-Item -ItemType Directory -Path $runEvidenceDir | Out-Null

$runBlock = {
    param($proj, $composeArgs)
    Write-Host "[runtime] Starting Playwright live copy test under project $proj..."
    $env:FIGMA_TEST_PROJECT = $proj
    $env:FIGMA_TEST_MODE = 'application'
    $env:FIGMA_TEST_MATCH = 'figma-conversation-copy.spec.ts'
    $env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = Join-Path $runEvidenceDir 'copy-smoke.xml'

    Push-Location (Join-Path $repositoryRoot 'frontend')
    try {
        node node_modules/@playwright/test/cli.js test --config playwright.figma.config.ts figma-conversation-copy.spec.ts --reporter list,junit --output "$runEvidenceDir/results"
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            throw "PLAYWRIGHT_COPY_FAILED: exit $exitCode"
        }
        Write-Host "[runtime] Playwright live copy test PASSED!"
    } finally {
        Pop-Location
        Remove-Item Env:FIGMA_TEST_PROJECT,Env:FIGMA_TEST_MODE,Env:FIGMA_TEST_MATCH,Env:PLAYWRIGHT_JUNIT_OUTPUT_NAME -ErrorAction SilentlyContinue
    }
}

Write-Host "[runtime] Launching prepare-figma-e2e.ps1 with project $project..."
& (Join-Path $PSScriptRoot 'prepare-figma-e2e.ps1') -Project $project -Run $runBlock
Write-Host "[runtime] Completed execution with status: $LASTEXITCODE"
