param([switch]$IsolatedChild)
$ErrorActionPreference = 'Stop'
if (-not $IsolatedChild) {
    $sharedLock = Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
    $before = if (Test-Path -LiteralPath $sharedLock) { (Get-FileHash -LiteralPath $sharedLock).Hash } else { $null }
    $namespace = Join-Path ([IO.Path]::GetTempPath()) "knora-reset-selfcheck-$([guid]::NewGuid())"
    $null = New-Item -ItemType Directory -Path $namespace
    $start = [Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
    foreach ($argument in @('-NoProfile','-File',$PSCommandPath,'-IsolatedChild')) { $start.ArgumentList.Add($argument) }
    $start.Environment['TEMP'] = $namespace
    $start.Environment['TMP'] = $namespace
    $start.Environment['KNORA_SELFCHECK_TEMP'] = $namespace
    $child = [Diagnostics.Process]::Start($start)
    $child.WaitForExit()
    $after = if (Test-Path -LiteralPath $sharedLock) { (Get-FileHash -LiteralPath $sharedLock).Hash } else { $null }
    if ($before -cne $after) { throw 'SELFCHECK_CHANGED_SHARED_RESERVATION' }
    if (-not [IO.Path]::GetFullPath($namespace).StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) -or [IO.Path]::GetFullPath($namespace) -eq [IO.Path]::GetFullPath([IO.Path]::GetTempPath())) { throw 'SELFCHECK_TEMP_ESCAPE' }
    Remove-Item -LiteralPath $namespace -Recurse -Force
    if ($child.ExitCode -ne 0) { throw "SELFCHECK_CHILD_FAILED_$($child.ExitCode)" }
    return
}
if ([IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\','/') -ne [IO.Path]::GetFullPath($env:KNORA_SELFCHECK_TEMP).TrimEnd('\','/')) { throw 'SELFCHECK_TEMP_NOT_ISOLATED' }
# Run the real preparation script in disposable fixture copies with service boundaries mocked.
$env:KNORA_RESET_REALM_FILE = 'preexisting-synthetic-realm'
$env:KNORA_RESET_VAULT_DIR = 'preexisting-synthetic-vault'
$root = Split-Path $PSScriptRoot -Parent
$scratch = Join-Path $root ".verification/password-reset/selfchecks/$([guid]::NewGuid())"

function New-ResetMockResources {
    $s = $global:resetPrepState
    $services = @('reset-api','reset-keycloak','reset-keycloak-db','reset-mail','reset-postgres')
    $s.netId = 'a' * 64
    $s.mockNetworks.Add($s.netId)
    foreach ($i in 0..4) {
        if ($s.failStartup -and $i -ne 2) { continue }
        $service = $services[$i]
        $id = ($i + 1).ToString('x').PadLeft(64,'0')
        $mounts = @()
        if ($service -in 'reset-keycloak-db','reset-postgres') {
            $v = ($i + 10).ToString('x').PadLeft(64,'b')
            $s.mockVolumes.Add($v)
            $s.volumeData[$v] = @{Name=$v; CreatedAt='2026-10-25T10:00:00Z'; Driver='local'; Options=$null; Labels=$null; Mountpoint="/var/lib/docker/volumes/$v/_data"}
            $mounts = @(@{Type='volume';Name=$v;Source="/var/lib/docker/volumes/$v/_data";Destination='/var/lib/postgresql/data';RW=$true})
        }
        if ($service -eq 'reset-keycloak') {
            $mounts = @(
                @{Type='bind';Source=$env:KNORA_RESET_REALM_FILE;Destination='/opt/keycloak/data/import/realm.json';RW=$false},
                @{Type='bind';Source=$env:KNORA_RESET_VAULT_DIR;Destination='/opt/keycloak/vault';RW=$false}
            )
        }
        $ports = @{}
        switch ($service) {
            reset-api { $ports['8000/tcp'] = @(@{HostIp='127.0.0.1';HostPort='8900'}) }
            reset-keycloak { $ports['8080/tcp'] = @(@{HostIp='127.0.0.1';HostPort='8480'}) }
            reset-mail { $ports['8025/tcp'] = @(@{HostIp='127.0.0.1';HostPort='8125'}) }
        }
        $s.containerData[$id] = @{
            Id=$id; Image=('sha256:' + ('c' * 64)); Created='2026-10-25T10:00:01Z'
            Config=@{Labels=@{
                'com.docker.compose.project'='knora-issue162';'com.docker.compose.service'=$service
                'com.docker.compose.project.working_dir'=$s.expectedWorkingDir
                'com.docker.compose.project.config_files'=$s.expectedConfigFile
                'com.docker.compose.container-number'='1';'com.docker.compose.oneoff'='False'
            }}
            State=@{Running=$true}; Mounts=$mounts; HostConfig=@{PortBindings=$ports}
            NetworkSettings=@{Ports=$ports;Networks=@{'knora-issue162_reset-isolated'=@{NetworkID=$s.netId;IPAddress='172.31.0.5';EndpointID=('d'*64)}}}
        }
        $s.mockContainers.Add($id)
    }
}
function docker {
    $global:LASTEXITCODE = 0
    $s = $global:resetPrepState
    $s.dockerCalls += ,@($args)
    $a = @($args)
    if ($a[0] -ne '--host' -or $a[1] -ne 'npipe:////./pipe/dockerDesktopLinuxEngine') { throw 'UNPINNED_DOCKER_ENDPOINT' }
    $a = @($a[2..($a.Count-1)])
    $verb = $a[0]
    $target = $a[-1]
    if ($verb -in 'inspect','stop','rm' -and $a.Count -ne 2) { throw 'UNEXPECTED_DOCKER_ARGUMENTS' }
    if ($verb -in 'volume','network' -and $a[1] -in 'inspect','rm' -and $a.Count -ne 3) { throw 'UNEXPECTED_DOCKER_ARGUMENTS' }
    if ($verb -eq 'ps' -and ($a -join '|') -notmatch '^ps\|-a\|--no-trunc\|(?:(?:--filter\|(?:volume|id)=[a-f0-9]{64})\|)?--format\|\{\{\.ID\}\}$') { throw 'UNEXPECTED_PS_ARGUMENTS' }
    if ($verb -eq 'volume' -and $a[1] -eq 'ls' -and ($a -join '|') -notmatch '^volume\|ls\|(?:--filter\|name=[a-f0-9]{64}\|)?--format\|\{\{\.Name\}\}$') { throw 'UNEXPECTED_VOLUME_LS_ARGUMENTS' }
    if ($verb -eq 'network' -and $a[1] -eq 'ls' -and ($a -join '|') -notmatch '^network\|ls\|--no-trunc\|(?:--filter\|id=[a-f0-9]{64}\|)?--format\|\{\{\.ID\}\}$') { throw 'UNEXPECTED_NETWORK_LS_ARGUMENTS' }
    if ($verb -eq 'ps') {
        if ($s.retainedContainer) { return ('f' * 64) }
        $found = @($s.mockContainers)
        if ($a -contains '--filter') {
            $f=$a[[array]::IndexOf($a,'--filter')+1]
            if ($f -like 'volume=*') { $found=@($found | Where-Object { @($s.containerData[$_].Mounts | Where-Object Name -eq $f.Substring(7)).Count -gt 0 }) }
            if ($f -like 'id=*') { $found=@($found | Where-Object { $_ -eq $f.Substring(3) }) }
        }
        if ($a -notcontains '--no-trunc') { return @($found | ForEach-Object { $_.Substring(0,12) }) }
        return $found
    }
    if ($verb -eq 'inspect') {
        if ($s.inspectFail) { $global:LASTEXITCODE=1; return }
        if ($s.retainedContainer) {
            return (@{Id=('f'*64);Config=@{Labels=@{'com.docker.compose.project'='knora-issue162';'com.docker.compose.project.working_dir'=$s.expectedWorkingDir;'com.docker.compose.project.config_files'=$s.expectedConfigFile}};State=@{Running=$false}} | ConvertTo-Json -Depth 10)
        }
        if (-not $s.containerData.ContainsKey($target) -or -not $s.mockContainers.Contains($target)) { $global:LASTEXITCODE=1; return }
        return ($s.containerData[$target] | ConvertTo-Json -Depth 12)
    }
    if ($verb -eq 'volume') {
        switch ($a[1]) {
            ls { if ($s.retainedVolume) { return 'knora-issue162_retained' }; return @($s.mockVolumes) }
            inspect {
                if ($s.retainedVolume) { return (@{Name='knora-issue162_retained';Labels=@{'com.docker.compose.project'='knora-issue162'}} | ConvertTo-Json) }
                if (-not $s.mockVolumes.Contains($target)) { $global:LASTEXITCODE=1; return }
                return ($s.volumeData[$target] | ConvertTo-Json -Depth 5)
            }
            rm {
                if ($s.failVolumeRm) { $global:LASTEXITCODE=1; return }
                if (-not $s.mockVolumes.Contains($target)) { throw 'UNEXPECTED_VOLUME_RM' }
                $s.mockVolumes.Remove($target) | Out-Null; $s.volumesRemoved++; return
            }
        }
    }
    if ($verb -eq 'network') {
        switch ($a[1]) {
            ls {
                $found = if ($s.retainedNetwork) { @('e'*64) } else { @($s.mockNetworks) }
                if ($a -notcontains '--no-trunc') { return @($found | ForEach-Object { $_.Substring(0,12) }) }
                return $found
            }
            inspect {
                if ($s.retainedNetwork) { return (@{Id=('e'*64);Name='knora-issue162_reset-isolated';Labels=@{'com.docker.compose.project'='knora-issue162'}} | ConvertTo-Json) }
                if (-not $s.mockNetworks.Contains($target)) { $global:LASTEXITCODE=1; return }
                $attached=@{}; foreach ($id in $s.mockContainers) { $attached[$id]=@{Name=$id} }
                if ($s.foreignNetwork) { $attached[('f'*64)]=@{Name='another-checkout'} }
                return (@{Id=$s.netId;Name='knora-issue162_reset-isolated';Created='2026-10-25T10:00:00Z';Driver='bridge';Labels=@{'com.docker.compose.project'='knora-issue162';'com.docker.compose.network'='reset-isolated'};Containers=$attached} | ConvertTo-Json -Depth 6)
            }
            rm {
                if ($s.mockContainers.Count -or -not $s.mockNetworks.Contains($target)) { throw 'UNEXPECTED_NETWORK_RM' }
                $s.mockNetworks.Remove($target) | Out-Null; $s.networksRemoved++; return
            }
        }
    }
    if ($verb -eq 'compose' -and $a -contains 'up') {
        $expected=@('compose','--project-name','knora-issue162','--project-directory',$s.expectedWorkingDir,'-f',$s.expectedConfigFile,'--profile','password-reset-test','up','-d','--build','reset-api','reset-keycloak','reset-keycloak-db','reset-mail','reset-postgres')
        if (($a -join '|') -ne ($expected -join '|')) { throw 'WRONG_COMPOSE_STARTUP_ARGV' }
        $s.correctUp=$true; $s.starts++
        New-ResetMockResources
        if ($s.wrongPort) { $s.containerData[('1'.PadLeft(64,'0'))].NetworkSettings.Ports['8000/tcp'][0].HostIp='0.0.0.0' }
        if ($s.failStartup) { $global:LASTEXITCODE=1 }
        return
    }
    if ($verb -eq 'stop') {
        if (-not $s.mockContainers.Contains($target)) { throw 'UNEXPECTED_STOP' }
        $s.containerData[$target].State.Running=$false
        $s.containerData[$target].NetworkSettings.Ports=@{}
        $s.containerData[$target].NetworkSettings.Networks['knora-issue162_reset-isolated'].IPAddress=''
        $s.containerData[$target].NetworkSettings.Networks['knora-issue162_reset-isolated'].EndpointID=''
        $s.containersStopped++; return
    }
    if ($verb -eq 'rm') {
        if ($a -contains '-v' -or -not $s.mockContainers.Contains($target)) { throw 'UNEXPECTED_RM' }
        $s.mockContainers.Remove($target) | Out-Null; $s.containersRemoved++; return
    }
    throw "UNEXPECTED_DOCKER_CALL: $($a -join ' ')"
}

function Start-Sleep {}

function Set-Content {
    [CmdletBinding()]
    param([Parameter(ValueFromPipeline=$true)]$Value, [string]$LiteralPath, [string]$Encoding)
    process {
        if ($global:resetPrepState.failReceipt -and [IO.Path]::GetFileName($LiteralPath) -eq 'cleanup-receipt.json') {
            throw [IO.IOException]::new('synthetic cleanup receipt write failure')
        }
        Microsoft.PowerShell.Management\Set-Content @PSBoundParameters
    }
}

function Get-Item {
    param($LiteralPath, [switch]$Force)
    if ($global:resetPrepState.fileLink -and [IO.Path]::GetFullPath($LiteralPath) -eq [IO.Path]::GetFullPath($global:resetPrepState.fileLink)) {
        return @{Attributes=[IO.FileAttributes]::ReparsePoint}
    }
    Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
}

function Invoke-RestMethod {
    param($Uri, $Method = 'Get', $Headers, $TimeoutSec, $ContentType, $Body)
    if ($Uri -like '*:8900/health') {
        $global:resetPrepState.healthCalls++
        if ($global:resetPrepState.healthUnavailable) { return @{status='ok'; service='unexpected'} }
        if ($global:resetPrepState.healthCalls -lt 3) { throw 'synthetic startup delay' }
        return @{status='ok'; service='knora-agent'}
    }
    if ($Uri -like '*/token') { return @{access_token='synthetic'} }
    if ($Uri -like '*/executions/execution') {
        $provider = ($Body | ConvertFrom-Json).provider
        $global:resetPrepState.executions += [pscustomobject]@{id=$provider; providerId=$provider; requirement='DISABLED'}
        return
    }
    if ($Uri -like '*/executions') {
        if ($Method -eq 'Put') {
            if (($Body | ConvertFrom-Json).requirement -ne 'REQUIRED') { throw 'requirement' }
            $global:resetPrepState.required++
            return
        }
        return ,$global:resetPrepState.executions
    }
    if ($Uri -like '*/authentication/flows') { return ,@([pscustomobject]@{alias='issue162-reset'}) }
    if ($Method -eq 'Put') { $global:resetPrepState.bound = $true; return }
    return @{id='knora-reset-regression'}
}

$prepCases = @(
    'parent-link', 'runtime-link', 'vault-link', 'realm-link', 'key-link',
    'health', 'health-unavailable', 'partial-empty', 'partial-otp',
    'invalid-key', 'empty-key', 'short-key', 'whitespace-key', 'valid-key',
    'long-valid-key', 'unexpected-flow'
)
$runCases = @(
    'run-success', 'run-retained-refusal', 'run-port-3400-busy',
    'run-relative-evidence', 'run-partial-startup-failure',
    'run-callback-failure', 'run-cleanup-failure', 'run-lock-contention',
    'run-volume-only', 'run-network-only', 'run-inspect-failure', 'run-replaced-volume', 'run-foreign-mount',
    'default-startup-failure', 'run-existing-evidence', 'run-wrong-port', 'run-foreign-network', 'run-recovery-inspect-failure', 'run-callback-cleanup-failure',
    'run-callback-receipt-failure', 'run-success-receipt-failure',
    'run-callback-evidence-missing', 'run-success-evidence-missing', 'run-native-callback-failure', 'run-native-callback-cleanup-failure', 'run-stale-lastexitcode-success'
)
$allCases = $prepCases + $runCases

$failed = @()
try {
    foreach ($case in $allCases) {
        $copy = Join-Path $scratch $case
        $null = New-Item -ItemType Directory -Force "$copy/scripts", "$copy/test/fixtures/keycloak", "$copy/test/fixtures/password-reset"
        Copy-Item -LiteralPath "$PSScriptRoot/prepare-password-reset-regression.ps1" -Destination "$copy/scripts/prepare-password-reset-regression.ps1"
        Copy-Item -LiteralPath "$root/docker-compose.dev.yml" -Destination "$copy/docker-compose.dev.yml"
        Copy-Item -LiteralPath "$root/test/fixtures/keycloak/figma-realm.json" -Destination "$copy/test/fixtures/keycloak/figma-realm.json"
        $runtime = "$copy/.verification/password-reset"
        $outside = "$copy/outside"
        $null = New-Item -ItemType Directory -Force $outside
        Set-Content -LiteralPath "$outside/realm.json" -Value 'sentinel'

        $global:resetPrepState = @{
            starts = 0
            healthCalls = 0
            required = 0
            bound = $false
            executions = @()
            dockerCalls = @()
            mockContainers = [System.Collections.Generic.List[string]]::new()
            mockVolumes = [System.Collections.Generic.List[string]]::new()
            mockNetworks = [System.Collections.Generic.List[string]]::new()
            containersStopped = 0
            containersRemoved = 0
            volumesRemoved = 0
            networksRemoved = 0
            correctUp = $false
            callbackRan = $false
            containerData = @{}
            volumeData = @{}
            expectedWorkingDir = $copy
            expectedConfigFile = (Join-Path $copy 'docker-compose.dev.yml')
        }
        $global:resetPrepState.healthUnavailable = ($case -eq 'health-unavailable')
        if ($case -eq 'run-retained-refusal') { $global:resetPrepState.retainedContainer = $true }
        if ($case -eq 'run-partial-startup-failure') { $global:resetPrepState.failStartup = $true }
        if ($case -eq 'run-cleanup-failure') { $global:resetPrepState.failVolumeRm = $true }
        if ($case -eq 'run-volume-only') { $global:resetPrepState.retainedVolume = $true }
        if ($case -eq 'run-network-only') { $global:resetPrepState.retainedNetwork = $true }
        if ($case -eq 'run-inspect-failure') { $global:resetPrepState.inspectFail = $true; $global:resetPrepState.retainedContainer = $true }
        if ($case -eq 'default-startup-failure') { $global:resetPrepState.failStartup = $true }
        if ($case -eq 'run-wrong-port') { $global:resetPrepState.wrongPort = $true }
        if ($case -eq 'run-callback-cleanup-failure' -or $case -eq 'run-native-callback-cleanup-failure') { $global:resetPrepState.failVolumeRm = $true }

        if ($case -notin 'partial-empty', 'partial-otp') {
            $global:resetPrepState.executions = @(
                [pscustomobject]@{id='otp'; providerId='knora-reset-email-otp'; requirement='DISABLED'},
                [pscustomobject]@{id='password'; providerId='reset-password'; requirement='DISABLED'}
            )
        } elseif ($case -eq 'partial-otp') {
            $global:resetPrepState.executions = @([pscustomobject]@{id='otp'; providerId='knora-reset-email-otp'; requirement='DISABLED'})
        }
        if ($case -eq 'unexpected-flow') { $global:resetPrepState.executions[0].providerId = 'unexpected' }

        switch ($case) {
            parent-link { $null = New-Item -ItemType Junction -Path "$copy/.verification" -Target $outside }
            runtime-link {
                $null = New-Item -ItemType Directory "$copy/.verification"
                $null = New-Item -ItemType Junction -Path $runtime -Target $outside
            }
            vault-link {
                $null = New-Item -ItemType Directory -Force $runtime
                $null = New-Item -ItemType Junction -Path "$runtime/vault" -Target $outside
            }
            default { $null = New-Item -ItemType Directory -Force "$runtime/vault" }
        }

        $digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes('knora-reset-regression'))).ToLowerInvariant()
        $entry = "$runtime/vault/knora-dev_knora-email-otp-hmac-$digest"
        $validKey = [Convert]::ToBase64String([byte[]](1..32))
        if ($case -eq 'long-valid-key') { $validKey = [Convert]::ToBase64String([byte[]](1..64)) }
        if ($case -in 'realm-link', 'key-link') {
            $global:resetPrepState.fileLink = $(if ($case -eq 'realm-link') { "$runtime/realm.json" } else { $entry })
            Set-Content -LiteralPath $global:resetPrepState.fileLink -Value 'sentinel'
        }
        if ($case -eq 'invalid-key') { [IO.File]::WriteAllText($entry, 'truncated') }
        if ($case -eq 'empty-key') { [IO.File]::WriteAllText($entry, '') }
        if ($case -eq 'short-key') { [IO.File]::WriteAllText($entry, [Convert]::ToBase64String([byte[]](1..16))) }
        if ($case -eq 'whitespace-key') { [IO.File]::WriteAllText($entry, $validKey.Insert(8, ' ')) }
        if ($case -in 'valid-key', 'long-valid-key') { [IO.File]::WriteAllText($entry, $validKey) }

        $caught = ''
        $runGuid = [guid]::NewGuid().ToString()
        $evidenceDir = Join-Path $copy 'evidence'
        $runOutput = [System.Collections.Generic.List[string]]::new()

        try {
            if ($case -in 'run-callback-evidence-missing','run-success-evidence-missing') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run {
                    $global:resetPrepState.callbackRan=$true
                    $movedEvidence = "$evidenceDir-unavailable"
                    foreach ($path in @($evidenceDir,$movedEvidence)) {
                        if (-not [IO.Path]::GetFullPath($path).StartsWith([IO.Path]::GetFullPath($scratch) + [IO.Path]::DirectorySeparatorChar)) { throw 'SELFCHECK_EVIDENCE_ESCAPE' }
                    }
                    [IO.Directory]::Move($evidenceDir,$movedEvidence)
                    if ($case -eq 'run-callback-evidence-missing') { throw 'INNER_FAIL' }
                } | ForEach-Object { $runOutput.Add([string]$_) }
            } elseif ($case -in 'run-callback-receipt-failure','run-success-receipt-failure') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run {
                    $global:resetPrepState.callbackRan=$true
                    $global:resetPrepState.failReceipt=$true
                    if ($case -eq 'run-callback-receipt-failure') { throw 'INNER_FAIL' }
                } | ForEach-Object { $runOutput.Add([string]$_) }
            } elseif ($case -eq 'run-existing-evidence') {
                $null=New-Item -ItemType Directory -Path $evidenceDir
                [IO.File]::WriteAllText((Join-Path $evidenceDir 'cleanup-receipt.json'),'previous-owner-sentinel')
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { throw 'CALLBACK_MUST_NOT_RUN' } | Out-Null
            } elseif ($case -in 'run-wrong-port','run-foreign-network','run-recovery-inspect-failure','run-callback-cleanup-failure') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run {
                    if ($case -eq 'run-foreign-network') { $global:resetPrepState.foreignNetwork=$true }
                    if ($case -eq 'run-recovery-inspect-failure') { $global:resetPrepState.inspectFail=$true }
                    if ($case -eq 'run-callback-cleanup-failure') { throw 'INNER_FAIL' }
                } | Out-Null
            } elseif ($case -eq 'run-lock-contention') {
                $lockPath = Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
                [IO.File]::WriteAllText($lockPath, 'another-owner-sentinel')
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { throw 'CALLBACK_MUST_NOT_RUN' } | Out-Null
            } elseif ($case -in 'run-volume-only','run-network-only','run-inspect-failure','run-replaced-volume','run-foreign-mount') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run {
                    if ($case -eq 'run-replaced-volume') { $v=@($global:resetPrepState.mockVolumes)[0]; $global:resetPrepState.volumeData[$v].CreatedAt='2026-10-25T11:00:00Z' }
                    if ($case -eq 'run-foreign-mount') { $id=@($global:resetPrepState.mockContainers)[0]; $global:resetPrepState.containerData[$id].Mounts=@(@{Type='bind';Source='C:/foreign';Destination='/foreign';RW=$true}) }
                } | Out-Null
            } elseif ($case -eq 'run-success') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { $global:resetPrepState.callbackRan=$true; if ($env:DOCKER_HOST -ne 'npipe:////./pipe/dockerDesktopLinuxEngine') { throw 'CALLBACK_ENDPOINT_WRONG' }; Write-Output 'INNER_OK' } | Out-Null
            } elseif ($case -eq 'run-retained-refusal') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { $global:resetPrepState.callbackRan=$true; Write-Output 'INNER_OK' } | Out-Null
            } elseif ($case -eq 'run-port-3400-busy') {
                $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 3400)
                try {
                    $listener.Start()
                    & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { $global:resetPrepState.callbackRan=$true; Write-Output 'INNER_OK' } | Out-Null
                } finally {
                    $listener.Stop()
                }
            } elseif ($case -eq 'run-relative-evidence') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot 'relative/evidence' -Run { $global:resetPrepState.callbackRan=$true; Write-Output 'INNER_OK' } | Out-Null
            } elseif ($case -eq 'run-partial-startup-failure') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { $global:resetPrepState.callbackRan=$true; Write-Output 'INNER_OK' } | Out-Null
            } elseif ($case -in 'run-native-callback-failure', 'run-native-callback-cleanup-failure') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run {
                    $global:resetPrepState.callbackRan = $true
                    & cmd.exe /d /c exit 7
                } | ForEach-Object { $runOutput.Add([string]$_) }
            } elseif ($case -eq 'run-stale-lastexitcode-success') {
                & cmd.exe /d /c exit 7
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run {
                    $global:resetPrepState.callbackRan = $true
                    Write-Output 'INNER_OK'
                } | ForEach-Object { $runOutput.Add([string]$_) }
        } elseif ($case -eq 'run-callback-failure') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { throw 'INNER_FAIL' } | Out-Null
            } elseif ($case -eq 'run-cleanup-failure') {
                & "$copy/scripts/prepare-password-reset-regression.ps1" -RunId $runGuid -EvidenceRoot $evidenceDir -Run { $global:resetPrepState.callbackRan=$true; Write-Output 'INNER_OK' } | Out-Null
            } else {
                & "$copy/scripts/prepare-password-reset-regression.ps1" | Out-Null
            }
        } catch {
            $caught = $_.Exception.Message
        }

        $ok = if ($case -like '*-link') {
            $caught -eq 'RESET_TEST_PATH_REJECTED' -and $global:resetPrepState.starts -eq 0 -and (Get-Content -Raw "$outside/realm.json").Trim() -eq 'sentinel'
        } elseif ($case -eq 'unexpected-flow') {
            $caught -like 'RESET_TEST_PREPARATION_FAILED_REQUIRE_EXECUTIONS_*' -and -not $global:resetPrepState.bound
        } elseif ($case -eq 'health-unavailable') {
            $caught -like 'RESET_TEST_PREPARATION_FAILED_API_HEALTH_*' -and $global:resetPrepState.healthCalls -eq 60
        } elseif ($case -eq 'run-success') {
            $receipt = Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json
            -not $caught -and $global:resetPrepState.callbackRan -and $global:resetPrepState.correctUp -and $global:resetPrepState.containersRemoved -eq 5 -and $global:resetPrepState.volumesRemoved -eq 2 -and $global:resetPrepState.mockContainers.Count -eq 0 -and $global:resetPrepState.mockVolumes.Count -eq 0 -and $receipt.cleanup_succeeded -and -not (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'))
        } elseif ($case -eq 'run-retained-refusal') {
            ($caught -like '*RESET_TEST_PROJECT_NOT_FRESH*' -or $caught -like '*RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED*') -and $global:resetPrepState.starts -eq 0 -and $global:resetPrepState.containersRemoved -eq 0 -and -not (Test-Path -LiteralPath $evidenceDir)
        } elseif ($case -eq 'run-port-3400-busy') {
            ($caught -like '*RESET_TEST_PORT_OWNERSHIP_REQUIRED*' -or $caught -like '*RESET_TEST_PORT_IN_USE*') -and $global:resetPrepState.starts -eq 0
        } elseif ($case -eq 'run-relative-evidence') {
            $caught -like '*RESET_TEST_EVIDENCE_ROOT_INVALID*'
        } elseif ($case -eq 'run-partial-startup-failure') {
            $caught -like '*RESET_TEST_START_FAILED*' -and ($global:resetPrepState.containersRemoved -ge 1)
        } elseif ($case -eq 'run-native-callback-failure') {
            $receipt = if (Test-Path -LiteralPath "$evidenceDir/cleanup-receipt.json") {
                Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json
            } else { $null }
            $caught -like '*7*' -and $receipt -ne $null -and ($receipt.primary_failure -like '*7*') -and $global:resetPrepState.containersRemoved -ge 5 -and $global:resetPrepState.volumesRemoved -ge 2 -and -not (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'))
        } elseif ($case -eq 'run-native-callback-cleanup-failure') {
            $receipt = if (Test-Path -LiteralPath "$evidenceDir/cleanup-receipt.json") {
                Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json
            } else { $null }
            $lockPath = Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
            $caught -like '*7*' -and $receipt -ne $null -and ($receipt.primary_failure -like '*7*') -and (Test-Path -LiteralPath $lockPath)
        } elseif ($case -eq 'run-stale-lastexitcode-success') {
            $receipt = if (Test-Path -LiteralPath "$evidenceDir/cleanup-receipt.json") {
                Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json
            } else { $null }
            -not $caught -and $global:resetPrepState.callbackRan -and $receipt -ne $null -and $receipt.cleanup_succeeded -and -not (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'))
        } elseif ($case -eq 'run-callback-failure') {
            $caught -like '*INNER_FAIL*' -and ($global:resetPrepState.containersRemoved -ge 5)
        } elseif ($case -in 'run-callback-receipt-failure','run-success-receipt-failure','run-callback-evidence-missing','run-success-evidence-missing') {
            $lockPath=Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
            $snapshots=@(if (Test-Path -LiteralPath $lockPath) { Get-Content -LiteralPath $lockPath | ForEach-Object { $_ | ConvertFrom-Json } })
            $expectedError=if ($case -like 'run-callback-*') { 'INNER_FAIL' } else { 'RESET_TEST_CLEANUP_FAILED*' }
            $caught -like $expectedError -and $global:resetPrepState.callbackRan -and -not @($runOutput | Where-Object { $_ -like 'RESET_TEST_CLEANED=*' }).Count -and $snapshots.Count -gt 0 -and $snapshots[0].run_id -eq $runGuid -and $snapshots[-1].phase -eq 'cleanup-incomplete' -and $global:resetPrepState.containersRemoved -eq 5 -and $global:resetPrepState.volumesRemoved -eq 2
        } elseif ($case -eq 'default-startup-failure') {
            $caught -eq 'RESET_TEST_START_FAILED' -and $global:resetPrepState.mockContainers.Count -eq 1 -and $global:resetPrepState.containersStopped -eq 0 -and $global:resetPrepState.containersRemoved -eq 0 -and -not (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'))
        } elseif ($case -eq 'run-existing-evidence') {
            $caught -eq 'RESET_TEST_EVIDENCE_NOT_FRESH' -and $global:resetPrepState.starts -eq 0 -and [IO.File]::ReadAllText((Join-Path $evidenceDir 'cleanup-receipt.json')) -eq 'previous-owner-sentinel'
        } elseif ($case -in 'run-wrong-port','run-foreign-network','run-recovery-inspect-failure','run-callback-cleanup-failure') {
            $receipt=Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json
            $lockPath=Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
            $snapshots=@(Get-Content -LiteralPath $lockPath | ForEach-Object { $_ | ConvertFrom-Json })
            $expectedError = switch ($case) { run-wrong-port { '*RESET_TEST_PORT_OWNERSHIP_REQUIRED*' }; run-callback-cleanup-failure { '*INNER_FAIL*' }; default { '*RESET_TEST_CLEANUP_FAILED*' } }
            $caught -like $expectedError -and -not $receipt.cleanup_succeeded -and $snapshots.Count -ge 2 -and $snapshots[0].run_id -eq $runGuid -and $snapshots[0].source_files.'docker-compose.dev.yml' -and $snapshots[-1].phase -eq 'cleanup-incomplete' -and $snapshots[-1].cleanup_receipt.cleanup_succeeded -eq $false -and $receipt.run.docker_endpoint -eq 'npipe:////./pipe/dockerDesktopLinuxEngine'
        } elseif ($case -in 'run-volume-only','run-network-only','run-inspect-failure') {
            $caught -like 'RESET_TEST_*' -and $global:resetPrepState.starts -eq 0 -and $global:resetPrepState.containersRemoved -eq 0 -and -not (Test-Path -LiteralPath $evidenceDir)
        } elseif ($case -in 'run-replaced-volume','run-foreign-mount') {
            $receipt=Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json
            $caught -like '*RESET_TEST_CLEANUP_FAILED*' -and -not $receipt.cleanup_succeeded -and $global:resetPrepState.mockContainers.Count -gt 0 -and (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'))
        } elseif ($case -eq 'run-lock-contention') {
            $lockPath = Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
            $unchanged = [IO.File]::ReadAllText($lockPath) -eq 'another-owner-sentinel'
            $noCalls = $global:resetPrepState.dockerCalls.Count -eq 0
            [IO.File]::Delete($lockPath)
            $caught -like '*RESET_TEST_PROJECT_RESERVED*' -and $unchanged -and $noCalls -and -not (Test-Path -LiteralPath $evidenceDir)
        } elseif ($case -eq 'run-cleanup-failure') {
            $lockPath = Join-Path ([IO.Path]::GetTempPath()) "knora-reset-reservation-knora-issue162.lock"
            $lockRetained = Test-Path -LiteralPath $lockPath
            $receiptOk = Test-Path -LiteralPath "$evidenceDir/cleanup-receipt.json"
            $caughtOk = $caught -like '*RESET_TEST_CLEANUP_FAILED*'
            $receipt = if ($receiptOk) { Get-Content -Raw "$evidenceDir/cleanup-receipt.json" | ConvertFrom-Json }
            $matchOk = $caughtOk -and $receiptOk -and -not $receipt.cleanup_succeeded -and @($receipt.remaining.volumes).Count -gt 0 -and $lockRetained
            if ($lockRetained) {
                [IO.File]::Delete($lockPath)
            }
            $matchOk
        } else {
            $key = [IO.File]::ReadAllText($entry)
            $keyValid = $false
            try { $keyValid = $key -cnotmatch '\s' -and [Convert]::FromBase64String($key).Length -ge 32 } catch {}
            -not $caught -and $global:resetPrepState.correctUp -and $global:resetPrepState.healthCalls -ge 3 -and $global:resetPrepState.required -eq 2 -and $global:resetPrepState.bound -and
                $keyValid -and ($case -notin 'valid-key', 'long-valid-key' -or $key -eq $validKey)
        }

        $envRestored = $env:KNORA_RESET_REALM_FILE -eq 'preexisting-synthetic-realm' -and $env:KNORA_RESET_VAULT_DIR -eq 'preexisting-synthetic-vault' -and -not $env:DOCKER_HOST
        $ok = $ok -and $envRestored
        Write-Output "CASE=$case OK=$ok ENV_RESTORED=$envRestored ERROR=$caught"
        if (-not $ok) { $failed += $case }
        $ownedLock=Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
        if (Test-Path -LiteralPath $ownedLock) { [IO.File]::Delete($ownedLock) }

        # Safely remove junctions before directory deletion
        foreach ($jPath in @("$runtime/vault", $runtime, "$copy/.verification")) {
            if (Test-Path -LiteralPath $jPath) {
                $jItem = Get-Item -LiteralPath $jPath -Force -ErrorAction SilentlyContinue
                if ($jItem -and ($jItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                    [IO.Directory]::Delete($jPath)
                }
            }
        }
    }
} finally {
    if (-not [IO.Path]::GetFullPath($scratch).StartsWith([IO.Path]::GetFullPath((Join-Path $root '.verification/password-reset/selfchecks/')))) { throw 'SELFCHECK_SCRATCH_ESCAPE' }
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failed) { throw "RESET_TEST_PREPARATION_SELFCHECK_FAILED_$($failed -join ',')" }
Write-Output "RESET_TEST_PREPARATION_SELFCHECK_PASSED_$($allCases.Count)"
