"""Tests for the bounded retrieval test harness and launcher."""

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
LAUNCHER = ROOT / "scripts/prepare-retrieval-test.ps1"


def make_inspect_payload(
    project: str,
    root: Path,
    service: str,
    cid: str,
    evidence_dir: Path | None = None,
) -> dict:
    if service == "verification-postgres":
        cpu, mem, internal, port = 1, 1024, "5432/tcp", "15433"
        mounts = [
            {
                "Type": "volume",
                "Name": f"{project}_verification-pgdata",
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            }
        ]
    elif service == "verification-qdrant":
        cpu, mem, internal, port = 2, 2048, "6333/tcp", "16433"
        mounts = [
            {
                "Type": "volume",
                "Name": f"{project}_verification-qdrantdata",
                "Destination": "/qdrant/storage",
                "RW": True,
            }
        ]
    else:  # verification-api
        cpu, mem, internal, port = 1, 768, "8000/tcp", "18053"
        if evidence_dir:
            obj_source = str(evidence_dir / "http-objects")
        else:
            obj_source = str(root / "evidence/http-objects")
        mounts = [
            {
                "Type": "bind",
                "Source": obj_source,
                "Destination": "/s2-objects",
                "RW": True,
            },
            {
                "Type": "bind",
                "Source": str(root / "evals/fixtures/pdf_retrieval_v3_s2"),
                "Destination": "/app/evals/fixtures/pdf_retrieval_v3_s2",
                "RW": False,
            },
        ]

    dev_compose = str(root / "docker-compose.dev.yml")
    return {
        "Id": cid,
        "Image": "sha256:" + "f" * 64,
        "State": {"Running": True, "Restarting": False},
        "Config": {
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.service": service,
                "com.docker.compose.project.working_dir": str(root),
                "com.docker.compose.project.config_files": dev_compose,
            },
            "Env": [
                "KNORA_PROVIDER_MODE=deterministic-local",
                "KNORA_EMBEDDING_PROVIDER=deterministic-local",
                "KNORA_GENERATION_PROVIDER=deterministic-local",
                (
                    "KNORA_DATABASE_URL="
                    "postgresql+psycopg://knora_s2:isolated_s2@postgres:5432/knora_153_s2"
                ),
                ("KNORA_RETRIEVAL_CONFIGURATION_ID=retrieval-bm25-upload-fixture-top8-v1"),
                "KNORA_LEXICAL_QDRANT_URL=http://qdrant:6333",
                (
                    "KNORA_LEXICAL_POPULATION_MANIFEST="
                    "/app/evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json"
                ),
                "KNORA_OBJECT_STORE_BACKEND=filesystem",
                "KNORA_OBJECT_STORE_ROOT=/s2-objects",
                "KNORA_LEXICAL_QDRANT_COLLECTION=s2_http_test",
                (
                    "KNORA_API_CREDENTIALS_JSON=[{"
                    '"key_id":"k-retrieval-test",'
                    '"key_hash":"sha256:' + ("0" * 64) + '",'
                    '"workspace_id":"00000000-0000-0000-0000-000000000001",'
                    '"enabled":true}]'
                ),
            ],
        },
        "HostConfig": {"NanoCpus": cpu * 1_000_000_000, "Memory": mem * 1024 * 1024},
        "Mounts": mounts,
        "NetworkSettings": {
            "Ports": {internal: [{"HostIp": "127.0.0.1", "HostPort": port}]},
            "Networks": {f"{project}_verification-isolated": {"NetworkID": "net-" + "a" * 16}},
        },
    }


@pytest.fixture
def retrieval_runner(tmp_path: Path):
    run_id = uuid.uuid4().hex
    project = f"knora-retrieval-test-{run_id}"
    evidence_dir = tmp_path / "evidence"
    events_file = tmp_path / "events.txt"
    events_file.write_text("")

    cid_pg = "1" * 64
    cid_qd = "2" * 64
    cid_api = "3" * 64
    cid_foreign = "9" * 64

    payload_pg = make_inspect_payload(project, ROOT, "verification-postgres", cid_pg, evidence_dir)
    payload_qd = make_inspect_payload(project, ROOT, "verification-qdrant", cid_qd, evidence_dir)
    payload_api = make_inspect_payload(project, ROOT, "verification-api", cid_api, evidence_dir)
    payload_foreign = {
        "Id": cid_foreign,
        "Image": "sha256:" + "8" * 64,
        "State": {"Running": True, "Restarting": False},
        "Config": {
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.service": "foreign-unowned",
                "com.docker.compose.project.working_dir": str(ROOT),
                "com.docker.compose.project.config_files": str(ROOT / "docker-compose.dev.yml"),
            }
        },
        "HostConfig": {"NanoCpus": 1_000_000_000, "Memory": 512 * 1024 * 1024},
        "Mounts": [],
        "NetworkSettings": {"Ports": {"9999/tcp": [{"HostIp": "127.0.0.1", "HostPort": "19999"}]}},
    }

    vol_pg_name = f"{project}_verification-pgdata"
    vol_qd_name = f"{project}_verification-qdrantdata"
    payload_vol_pg = {
        "Name": vol_pg_name,
        "CreatedAt": "2026-10-25T01:00:00Z",
        "Driver": "local",
        "Options": None,
        "Labels": {
            "com.docker.compose.project": project,
            "com.docker.compose.volume": "verification-pgdata",
        },
    }
    payload_vol_qd = {
        "Name": vol_qd_name,
        "CreatedAt": "2026-10-25T01:00:00Z",
        "Driver": "local",
        "Options": None,
        "Labels": {
            "com.docker.compose.project": project,
            "com.docker.compose.volume": "verification-qdrantdata",
        },
    }
    payload_vol_foreign = {
        "Name": f"{project}_foreign_vol",
        "Labels": {
            "com.docker.compose.project": project,
            "com.docker.compose.volume": "foreign_vol",
        },
    }

    net_id = "net-aaaaaaaaaaaaaaaa"
    payload_net = {
        "Id": net_id,
        "Name": f"{project}_verification-isolated",
        "Labels": {
            "com.docker.compose.project": project,
            "com.docker.compose.network": "verification-isolated",
        },
    }
    payload_net_foreign = {
        "Id": "net-foreign999999",
        "Name": f"{project}_foreign-net",
        "Labels": {
            "com.docker.compose.project": project,
            "com.docker.compose.network": "foreign-net",
        },
    }

    payloads = {
        cid_pg: payload_pg,
        cid_qd: payload_qd,
        cid_api: payload_api,
        cid_foreign: payload_foreign,
        f"{project}-verification-postgres-1": payload_pg,
        f"{project}-verification-qdrant-1": payload_qd,
        f"{project}-verification-api-1": payload_api,
        vol_pg_name: payload_vol_pg,
        vol_qd_name: payload_vol_qd,
        f"{project}_foreign_vol": payload_vol_foreign,
        net_id: payload_net,
        "net-foreign999999": payload_net_foreign,
    }
    payload_json = tmp_path / "inspect_payloads.json"
    payload_json.write_text(json.dumps(payloads), encoding="utf-8")

    def run_launcher(
        mode="Storage",
        extra_env=None,
        test_mode="success",
        custom_run=None,
        custom_evidence_dir=None,
        custom_run_id=None,
        after_script="",
        cancel_startup=False,
    ):
        target_run_id = custom_run_id or run_id
        target_evidence = str(custom_evidence_dir or evidence_dir)
        run_block = custom_run or '{ Write-Output "INNER_RUN_OK" }'

        mock_pwsh = f"""
$ErrorActionPreference = 'Stop'
$global:mock_containers = [System.Collections.Generic.List[string]]::new()
$global:mock_volumes = [System.Collections.Generic.List[string]]::new()
$global:mock_networks = [System.Collections.Generic.List[string]]::new()
$global:in_cleanup = $false
$global:started = $false

if ($env:TEST_MODE -eq 'retained-container') {{
    $global:mock_containers.Add('retained-c001')
}}
if ($env:TEST_MODE -eq 'retained-volume') {{
    $global:mock_volumes.Add("${{env:TEST_PROJECT}}_retained_vol")
}}
if ($env:TEST_MODE -eq 'retained-network') {{
    $global:mock_networks.Add("${{env:TEST_PROJECT}}_retained_net")
}}

function docker {{
    $global:LASTEXITCODE = 0
    $rawArgs = @($args)
    $cmd = $rawArgs -join ' '
    Add-Content -LiteralPath "$env:TEST_EVENTS" -Value "docker $cmd"

    if ($rawArgs -contains 'down') {{
        throw 'BROAD_DOWN_FORBIDDEN: exact ID cleanup required'
    }}

    $subArgs = @($rawArgs)
    if ($subArgs.Count -ge 2 -and $subArgs[0] -eq '--host') {{
        $subArgs = if ($subArgs.Count -gt 2) {{ $subArgs[2..($subArgs.Count - 1)] }} else {{ @() }}
    }}
    if ($subArgs.Count -eq 0) {{ return }}

    $verb = $subArgs[0]

    if ($env:TEST_MODE -eq 'fail-inspect-cleanup' -and $global:in_cleanup) {{
        $global:LASTEXITCODE = 1
        return
    }}

    if ($verb -eq 'ps') {{
        $volumeFilter = @($subArgs | Where-Object {{ $_ -like 'volume=*' }})
        if ($volumeFilter.Count) {{
            $volumeName = $volumeFilter[0].Substring(7)
            $map = Get-Content -Raw "$env:TEST_PAYLOADS" | ConvertFrom-Json
            return @($global:mock_containers | Where-Object {{
                @($map.$_.Mounts | Where-Object Name -eq $volumeName).Count -gt 0
            }})
        }}
        if ($subArgs -notcontains '--no-trunc') {{
            return @($global:mock_containers | ForEach-Object {{
                $_.Substring(0, [Math]::Min(12, $_.Length))
            }})
        }}
        return @($global:mock_containers)
    }}

    if ($verb -eq 'volume') {{
        $subVerb = if ($subArgs.Count -gt 1) {{ $subArgs[1] }} else {{ '' }}
        if ($subVerb -eq 'ls') {{
            return @($global:mock_volumes)
        }}
        if ($subVerb -eq 'inspect') {{
            $targetVol = $subArgs[-1]
            $map = Get-Content -Raw "$env:TEST_PAYLOADS" | ConvertFrom-Json
            if ($map.PSObject.Properties[$targetVol]) {{
                return @($map.$targetVol) | ConvertTo-Json -Depth 5
            }}
            return '[]'
        }}
        if ($subVerb -eq 'rm') {{
            $targetVol = $subArgs[-1]
            Add-Content -LiteralPath "$env:TEST_EVENTS" -Value "vol-rm-called $targetVol"
            if ($env:TEST_MODE -eq 'fail-vol-rm') {{
                $global:LASTEXITCODE = 1
                return
            }}
            $null = $global:mock_volumes.Remove($targetVol)
            return
        }}
        return
    }}

    if ($verb -eq 'network') {{
        $subVerb = if ($subArgs.Count -gt 1) {{ $subArgs[1] }} else {{ '' }}
        if ($subVerb -eq 'ls') {{
            if ($subArgs -notcontains '--no-trunc') {{
                return @($global:mock_networks | ForEach-Object {{
                    $_.Substring(0, [Math]::Min(12, $_.Length))
                }})
            }}
            return @($global:mock_networks)
        }}
        if ($subVerb -eq 'inspect') {{
            $targetNet = $subArgs[-1]
            $map = Get-Content -Raw "$env:TEST_PAYLOADS" | ConvertFrom-Json
            if ($map.PSObject.Properties[$targetNet]) {{
                $connections = @{{}}
                foreach ($container in $global:mock_containers) {{
                    $networks = $map.$container.NetworkSettings.Networks
                    if (@($networks.PSObject.Properties.Value.NetworkID) -contains $targetNet) {{
                        $connections[$container] = @{{ Name = $container }}
                    }}
                }}
                $map.$targetNet | Add-Member -NotePropertyName Containers `
                    -NotePropertyValue $connections -Force
                return @($map.$targetNet) | ConvertTo-Json -Depth 5
            }}
            return '[]'
        }}
        if ($subVerb -eq 'rm') {{
            $targetNet = $subArgs[-1]
            Add-Content -LiteralPath "$env:TEST_EVENTS" -Value "net-rm-called $targetNet"
            if ($env:TEST_MODE -eq 'fail-net-rm') {{
                $global:LASTEXITCODE = 1
                return
            }}
            $null = $global:mock_networks.Remove($targetNet)
            return
        }}
        return
    }}

    if ($verb -eq 'compose') {{
        if ($subArgs -contains 'up') {{
            if ($env:TEST_MODE -eq 'start-failure') {{
                $global:LASTEXITCODE = 1
                return
            }}
            if ($env:TEST_MODE -eq 'partial-startup-failure') {{
                $global:mock_containers.Add('{cid_pg}')
                $global:mock_volumes.Add('{vol_pg_name}')
                $global:mock_networks.Add('{net_id}')
                $global:started = $true
                $global:LASTEXITCODE = 1
                return
            }}
            if ($env:TEST_MODE -eq 'interruption-throw') {{
                $global:mock_containers.Add('{cid_pg}')
                $global:mock_volumes.Add('{vol_pg_name}')
                $global:mock_networks.Add('{net_id}')
                $global:started = $true
                throw "INTERRUPTED_AFTER_CREATION"
            }}

            $global:started = $true
            if ($env:TEST_MODE -like 'http*') {{
                $global:mock_containers.Add('{cid_api}')
                # Propagate credentials JSON to inspected API environment
                if ($env:KNORA_S2_API_CREDENTIALS_JSON) {{
                    $creds = $env:KNORA_S2_API_CREDENTIALS_JSON
                    if ($env:TEST_MODE -eq 'http-invalid-credentials') {{ $creds = '{{broken' }}
                    if ($env:TEST_MODE -eq 'http-missing-credentials') {{ $creds = '' }}
                    $pContent = Get-Content -Raw "$env:TEST_PAYLOADS" | ConvertFrom-Json
                    $apiObj = $pContent.'{cid_api}'
                    $envArr = @()
                    foreach ($line in $apiObj.Config.Env) {{
                        if ($line -like 'KNORA_API_CREDENTIALS_JSON=*') {{
                            $envArr += "KNORA_API_CREDENTIALS_JSON=$creds"
                        }} else {{
                            $envArr += $line
                        }}
                    }}
                    $apiObj.Config.Env = $envArr
                    $pContent.'{project}-verification-api-1'.Config.Env = $envArr
                    $jsonStr = $pContent | ConvertTo-Json -Depth 10
                    Set-Content -LiteralPath "$env:TEST_PAYLOADS" -Value $jsonStr -Encoding utf8
                }}
            }}
            $global:mock_containers.Add('{cid_pg}')
            $global:mock_containers.Add('{cid_qd}')
            $global:mock_volumes.Add('{vol_pg_name}')
            $global:mock_volumes.Add('{vol_qd_name}')
            $global:mock_networks.Add('{net_id}')

            if ($env:TEST_MODE -eq 'cancel-startup') {{
                Set-Content -LiteralPath "$env:TEST_EVENTS.ready" -Value 'ready'
                while ($true) {{ Start-Sleep -Milliseconds 20 }}
            }}

            if ($env:TEST_MODE -eq 'foreign-container-present') {{
                $global:mock_containers.Add('{cid_foreign}')
            }}
            return
        }}
        return
    }}

    if ($verb -eq 'inspect') {{
        $targets = $subArgs[1..($subArgs.Count - 1)]
        $map = Get-Content -Raw "$env:TEST_PAYLOADS" | ConvertFrom-Json
        $matched = @()
        foreach ($t in $targets) {{
            if ($map.PSObject.Properties[$t]) {{
                $matched += $map.$t
            }}
        }}
        if ($matched.Count -gt 0) {{
            return ($matched | ConvertTo-Json -Depth 10)
        }}
        return '[]'
    }}

    if ($verb -eq 'stop') {{
        $targetCid = $subArgs[-1]
        Add-Content -LiteralPath "$env:TEST_EVENTS" -Value "stop-called $targetCid"
        $global:in_cleanup = $true
        return
    }}

    if ($verb -eq 'rm') {{
        $targetCid = $subArgs[-1]
        Add-Content -LiteralPath "$env:TEST_EVENTS" -Value "rm-called $targetCid"
        $global:in_cleanup = $true
        $null = $global:mock_containers.Remove($targetCid)
        return
    }}
}}

try {{
    & "{LAUNCHER}" -Mode "{mode}" -RunId "{target_run_id}" `
        -EvidenceRoot "{target_evidence}" -Collection "s2_http_test" -Run {run_block}
}} finally {{
    {after_script}
}}
"""
        if cancel_startup:
            encoded = base64.b64encode(mock_pwsh.encode("utf-8")).decode()
            mock_pwsh = f"""
$ps = [powershell]::Create()
$null = $ps.AddScript([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')))
$pending = $ps.BeginInvoke()
try {{
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while (-not (Test-Path -LiteralPath "$env:TEST_EVENTS.ready")) {{
        if ($pending.IsCompleted -or [DateTime]::UtcNow -gt $deadline) {{
            throw 'CANCEL_SETUP_FAILED'
        }}
        Start-Sleep -Milliseconds 20
    }}
    $ps.Stop()
}} finally {{ $ps.Dispose() }}
"""
        env = {
            k: v
            for k, v in os.environ.items()
            if not re.match(r"^(DOCKER_|COMPOSE_|KNORA_S2_)", k, re.I)
        }
        env["TEST_EVENTS"] = str(events_file)
        env["TEST_PAYLOADS"] = str(payload_json)
        env["TEST_PROJECT"] = project
        env["TEST_MODE"] = test_mode
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", mock_pwsh],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    claim = Path(tempfile.gettempdir()) / f"knora-retrieval-reservation-{project}.lock"
    try:
        yield run_launcher, events_file, project, claim, evidence_dir, cid_foreign
    finally:
        claim.unlink(missing_ok=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_storage_mode_success(retrieval_runner) -> None:
    run_launcher, events_file, project, claim, _, _ = retrieval_runner
    proc = run_launcher(mode="Storage", test_mode="success")
    assert proc.returncode == 0, proc.stderr
    assert "RETRIEVAL_TEST_PREPARED" in proc.stdout
    assert "RETRIEVAL_TEST_CLEANED" in proc.stdout
    events = events_file.read_text(encoding="utf-8")
    assert "verification-postgres" in events
    assert "verification-qdrant" in events
    assert "verification-api" not in events
    assert "stop-called" in events
    assert "rm-called" in events
    assert "vol-rm-called" in events
    assert not claim.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_http_mode_success(retrieval_runner) -> None:
    run_launcher, events_file, project, claim, _, _ = retrieval_runner
    auth_probe = """
import json, os
from pathlib import Path
from uuid import UUID
from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json
payload = json.loads(Path(os.environ['TEST_PAYLOADS']).read_text('utf-8-sig'))
settings = dict(line.split('=', 1) for line in payload['3' * 64]['Config']['Env'])
raw_key = os.environ['KNORA_S2_HTTP_API_KEY']
credentials = credentials_from_json(settings['KNORA_API_CREDENTIALS_JSON'])
principal = ApiKeyAuthenticator(credentials).authenticate(raw_key)
assert principal.workspace_id == os.environ['KNORA_S2_HTTP_WORKSPACE_ID']
assert UUID(principal.workspace_id)
assert '127.0.0.1:15433' in os.environ['KNORA_DATABASE_URL']
assert raw_key not in Path(os.environ['TEST_EVENTS']).read_text()
print('HTTP_AUTH_OK')
"""
    probe_run = "{ $global:testRawKey = $env:KNORA_S2_HTTP_API_KEY; $probe = @'\n"
    probe_run += auth_probe + "\n'@\n & python -c $probe }"
    after = """
if ((Get-Content -Raw $env:TEST_EVENTS).Contains($global:testRawKey)) { throw 'KEY_IN_TRACE' }
$receipt = Join-Path (Split-Path $env:TEST_EVENTS) 'evidence/cleanup-receipt.json'
if ((Get-Content -Raw $receipt).Contains($global:testRawKey)) { throw 'KEY_IN_RECEIPT' }
"""
    proc = run_launcher(mode="Http", test_mode="http", custom_run=probe_run, after_script=after)
    assert proc.returncode == 0, proc.stderr
    assert "HTTP_AUTH_OK" in proc.stdout
    assert "API_KEY=" not in proc.stdout
    assert "RETRIEVAL_TEST_PREPARED" in proc.stdout
    assert "RETRIEVAL_TEST_CLEANED" in proc.stdout
    events = events_file.read_text(encoding="utf-8")
    assert "verification-postgres" in events
    assert "verification-qdrant" in events
    assert "verification-api" in events
    assert "stop-called" in events
    assert "rm-called" in events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_retained_container(retrieval_runner) -> None:
    run_launcher, _, _, _, _, _ = retrieval_runner
    proc = run_launcher(test_mode="retained-container")
    assert proc.returncode != 0
    output = proc.stderr + proc.stdout
    assert "RETRIEVAL_TEST_PROJECT_NOT_FRESH" in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_retained_volume(retrieval_runner) -> None:
    run_launcher, _, _, _, _, _ = retrieval_runner
    proc = run_launcher(test_mode="retained-volume")
    assert proc.returncode != 0
    output = proc.stderr + proc.stdout
    assert "RETRIEVAL_TEST_PROJECT_NOT_FRESH" in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_retained_network(retrieval_runner) -> None:
    run_launcher, _, _, _, _, _ = retrieval_runner
    proc = run_launcher(test_mode="retained-network")
    assert proc.returncode != 0
    output = proc.stderr + proc.stdout
    assert "RETRIEVAL_TEST_PROJECT_NOT_FRESH" in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_ambient_selector(retrieval_runner) -> None:
    run_launcher, _, _, _, _, _ = retrieval_runner
    secret = "secret-token-do-not-leak"
    proc = run_launcher(extra_env={"COMPOSE_PROJECT_NAME": secret})
    assert proc.returncode != 0
    output = proc.stderr + proc.stdout
    assert "RETRIEVAL_TEST_AMBIENT_OVERRIDE_REJECTED" in output
    assert secret not in proc.stdout and secret not in proc.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_cleans_up_on_inner_failure(retrieval_runner) -> None:
    run_launcher, events_file, project, claim, _, _ = retrieval_runner
    proc = run_launcher(custom_run='{ throw "INNER_FAILURE" }')
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    assert "stop-called" in events
    assert "rm-called" in events
    assert "RETRIEVAL_TEST_CLEANED" in proc.stdout
    assert not claim.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_cleans_up_on_startup_failure(retrieval_runner) -> None:
    run_launcher, _, _, claim, _, _ = retrieval_runner
    proc = run_launcher(test_mode="start-failure")
    assert proc.returncode != 0
    output = proc.stderr + proc.stdout
    assert "RETRIEVAL_TEST_START_FAILED" in output
    assert not claim.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_relative_evidence_root(retrieval_runner) -> None:
    run_launcher, events_file, _, _, _, _ = retrieval_runner
    proc = run_launcher(custom_evidence_dir="relative_evidence")
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    assert "compose" not in events or "up" not in events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_drive_relative_evidence_root(
    retrieval_runner,
) -> None:
    run_launcher, events_file, _, _, _, _ = retrieval_runner
    proc = run_launcher(custom_evidence_dir="C:drive_relative_evidence")
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    assert "compose" not in events or "up" not in events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_reused_nonfresh_object_root(
    retrieval_runner,
) -> None:
    run_launcher, events_file, _, _, evidence_dir, _ = retrieval_runner
    reused_objects = evidence_dir / "http-objects"
    reused_objects.mkdir(parents=True, exist_ok=True)
    (reused_objects / "stale-file.bin").write_text("reused")
    proc = run_launcher()
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    assert "compose" not in events or "up" not in events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_rejects_reused_empty_object_root(
    retrieval_runner,
) -> None:
    run_launcher, events_file, _, _, evidence_dir, _ = retrieval_runner
    reused_objects = evidence_dir / "http-objects"
    reused_objects.mkdir(parents=True, exist_ok=True)
    proc = run_launcher()
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    assert "compose" not in events or "up" not in events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_cleanup_never_adopts_or_deletes_foreign_container(
    retrieval_runner,
) -> None:
    run_launcher, events_file, _, claim, evidence, cid_foreign = retrieval_runner
    proc = run_launcher(test_mode="foreign-container-present")
    assert proc.returncode != 0
    assert claim.exists()
    receipt = json.loads((evidence / "cleanup-receipt.json").read_text("utf-8-sig"))
    assert cid_foreign in receipt["leftovers"]["containers"]
    events = events_file.read_text(encoding="utf-8")
    # Cleanup must never stop or rm foreign container row
    assert f"stop-called {cid_foreign}" not in events
    assert f"rm-called {cid_foreign}" not in events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_cleans_proved_owned_ids_on_partial_startup_failure(
    retrieval_runner,
) -> None:
    run_launcher, events_file, _, claim, _, _ = retrieval_runner
    proc = run_launcher(test_mode="partial-startup-failure")
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    # Proved-owned container created before failure is cleaned
    assert "stop-called" in events
    assert "rm-called" in events
    assert not claim.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_cleans_proved_owned_ids_on_interruption_throw(
    retrieval_runner,
) -> None:
    run_launcher, events_file, _, claim, _, _ = retrieval_runner
    proc = run_launcher(test_mode="interruption-throw")
    assert proc.returncode != 0
    events = events_file.read_text(encoding="utf-8")
    assert "stop-called" in events
    assert "rm-called" in events
    assert not claim.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_volume_rm_failure_retains_reservation(
    retrieval_runner,
) -> None:
    run_launcher, _, _, claim, evidence_dir, _ = retrieval_runner
    proc = run_launcher(test_mode="fail-vol-rm")
    assert proc.returncode != 0
    assert "RETRIEVAL_TEST_CLEANED" not in proc.stdout
    assert claim.exists()
    receipt_file = evidence_dir / "cleanup-receipt.json"
    assert receipt_file.exists()
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert not receipt["cleanup_succeeded"]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_network_rm_failure_retains_reservation(
    retrieval_runner,
) -> None:
    run_launcher, _, _, claim, evidence_dir, _ = retrieval_runner
    proc = run_launcher(test_mode="fail-net-rm")
    assert proc.returncode != 0
    assert "RETRIEVAL_TEST_CLEANED" not in proc.stdout
    assert claim.exists()
    receipt_file = evidence_dir / "cleanup-receipt.json"
    assert receipt_file.exists()
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert not receipt["cleanup_succeeded"]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_retrieval_launcher_inspect_failure_in_cleanup_retains_reservation(
    retrieval_runner,
) -> None:
    run_launcher, _, _, claim, evidence_dir, _ = retrieval_runner
    proc = run_launcher(test_mode="fail-inspect-cleanup")
    assert proc.returncode != 0
    assert "RETRIEVAL_TEST_CLEANED" not in proc.stdout
    assert claim.exists()
    receipt_file = evidence_dir / "cleanup-receipt.json"
    assert receipt_file.exists()
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert not receipt["cleanup_succeeded"]


def test_retrieval_launcher_rejects_missing_leaf_under_junction(retrieval_runner, tmp_path):
    run_launcher, events, _, _, _, _ = retrieval_runner
    target = tmp_path / "daily"
    target.mkdir()
    junction = tmp_path / "junction"
    made = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-Command",
            f"New-Item -ItemType Junction -Path '{junction}' -Target '{target}' | Out-Null",
        ],
        capture_output=True,
        text=True,
    )
    assert made.returncode == 0, made.stderr
    try:
        proc = run_launcher(custom_evidence_dir=junction / "new-run")
        assert proc.returncode != 0
        assert "RETRIEVAL_TEST_PATH_REJECTED" in proc.stderr
        assert not (target / "new-run").exists()
        assert not events.read_text()
    finally:
        junction.rmdir()


@pytest.mark.parametrize("test_mode", ["success", "retained-container"])
@pytest.mark.parametrize("mode", ["Storage", "Http"])
def test_retrieval_launcher_restores_ambient_environment(retrieval_runner, test_mode, mode):
    run_launcher, _, _, _, _, _ = retrieval_runner
    names = ("KNORA_DATABASE_URL", "KNORA_PROVIDER_MODE", "KNORA_OBJECT_STORE_ROOT")
    probe = '{ if ($env:KNORA_DATABASE_URL -like "*daily*") { throw "DAILY_DB" }; '
    probe += 'if ($env:KNORA_PROVIDER_MODE -ne "deterministic-local") { throw "LIVE_PROVIDER" } }'
    restore_probe = "\n".join(
        f'if ($env:{name} -ne "daily-sentinel") {{ throw "ENVIRONMENT_NOT_RESTORED" }}'
        for name in names
    )
    proc = run_launcher(
        mode=mode,
        test_mode="http" if mode == "Http" and test_mode == "success" else test_mode,
        extra_env=dict.fromkeys(names, "daily-sentinel"),
        custom_run=probe,
        after_script=restore_probe,
    )
    assert "ENVIRONMENT_NOT_RESTORED" not in proc.stderr
    if test_mode == "success":
        assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("mutation", ["volume", "mount", "network"])
def test_retrieval_launcher_preserves_replaced_resource(retrieval_runner, mutation):
    run_launcher, events, project, claim, evidence, _ = retrieval_runner
    changes = {
        "volume": f"$p.'{project}_verification-pgdata'.CreatedAt = 'replacement'",
        "mount": "$p.'" + "1" * 64 + "'.Mounts[0].Destination = '/foreign'",
        "network": "$p.'"
        + "1" * 64
        + "'.NetworkSettings.Networks = @{foreign=@{NetworkID='foreign'}}",
    }
    callback = "{ $p = Get-Content -Raw $env:TEST_PAYLOADS | ConvertFrom-Json; "
    callback += (
        changes[mutation] + "; $p | ConvertTo-Json -Depth 12 | Set-Content $env:TEST_PAYLOADS }"
    )
    proc = run_launcher(custom_run=callback)
    assert proc.returncode != 0
    log = events.read_text()
    if mutation == "volume":
        assert f"vol-rm-called {project}_verification-pgdata" not in log
    else:
        assert "rm-called " + "1" * 64 not in log
    assert claim.exists()
    assert not json.loads((evidence / "cleanup-receipt.json").read_text("utf-8-sig"))[
        "cleanup_succeeded"
    ]


@pytest.mark.parametrize("test_mode", ["http-invalid-credentials", "http-missing-credentials"])
def test_retrieval_launcher_rejects_invalid_actual_credentials(retrieval_runner, test_mode):
    run_launcher, _, _, _, _, _ = retrieval_runner
    proc = run_launcher(mode="Http", test_mode=test_mode)
    assert proc.returncode != 0
    assert "INNER_RUN_OK" not in proc.stdout


def test_retrieval_launcher_pipeline_stop_keeps_recovery_identity(retrieval_runner):
    run_launcher, events, project, claim, evidence, _ = retrieval_runner
    proc = run_launcher(test_mode="cancel-startup", cancel_startup=True)
    assert proc.returncode == 0, proc.stderr
    receipt = evidence / "cleanup-receipt.json"
    if receipt.exists() and json.loads(receipt.read_text("utf-8-sig"))["cleanup_succeeded"]:
        assert not claim.exists()
        assert "rm-called " + "1" * 64 in events.read_text()
    else:
        assert claim.exists()
        identity = json.loads(claim.read_text("utf-8-sig"))
        assert identity["project"] == project
        assert identity["compose_file"] == str(ROOT / "docker-compose.dev.yml")


def test_cleanup_failure_preserves_original_callback_error(retrieval_runner):
    run_launcher, _, _, claim, evidence, _ = retrieval_runner
    proc = run_launcher(test_mode="fail-vol-rm", custom_run='{ throw "ORIGINAL_CALLBACK_ERROR" }')
    assert proc.returncode != 0
    assert "ORIGINAL_CALLBACK_ERROR" in proc.stderr
    assert "RETRIEVAL_TEST_CLEANUP_INCOMPLETE" not in proc.stderr
    assert claim.exists()
    assert not json.loads((evidence / "cleanup-receipt.json").read_text("utf-8-sig"))[
        "cleanup_succeeded"
    ]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
@pytest.mark.parametrize("throw_inner", [False, True])
def test_retrieval_launcher_evidence_root_moved_fails_and_retains_claim(
    retrieval_runner, tmp_path, throw_inner
):
    run_launcher, events, project, claim, evidence_dir, _ = retrieval_runner
    moved_dir = tmp_path / "moved_evidence"
    callback = (
        f'{{ Move-Item -LiteralPath "{evidence_dir.as_posix()}" '
        f'-Destination "{moved_dir.as_posix()}"'
    )
    if throw_inner:
        callback += '; throw "INNER_FAIL"'
    callback += " }"

    proc = run_launcher(custom_run=callback)
    assert proc.returncode != 0
    assert "RETRIEVAL_TEST_CLEANED" not in proc.stdout
    assert claim.exists()
    assert (
        "RETRIEVAL_TEST_RECEIPT_FAILED" in proc.stderr
        or "cleanup-receipt.json" in proc.stderr
        or "receipt" in proc.stderr.lower()
    )
    if throw_inner:
        assert "INNER_FAIL" in proc.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
@pytest.mark.parametrize("mutation", ["reverse", "source", "rw"])
def test_retrieval_launcher_http_mount_mutations(retrieval_runner, mutation):
    run_launcher, events, project, claim, evidence, _ = retrieval_runner
    api_cid = "3" * 64
    changes = {
        "reverse": "$api.Mounts = @($api.Mounts[1], $api.Mounts[0])",
        "source": "$api.Mounts[0].Source = 'C:/foreign'",
        "rw": "$api.Mounts[1].RW = $true",
    }
    callback = (
        "{ $p = Get-Content -Raw $env:TEST_PAYLOADS | ConvertFrom-Json; "
        f"$api = $p.'{api_cid}'; "
        + changes[mutation]
        + '; $name = "$env:TEST_PROJECT-verification-api-1"; '
        + "if ($p.PSObject.Properties[$name]) { $p.$name.Mounts = $api.Mounts }; "
        + "$p | ConvertTo-Json -Depth 12 | "
        + "Set-Content -LiteralPath $env:TEST_PAYLOADS -Encoding utf8; "
        + "Write-Output 'INNER_RUN_OK' }"
    )
    proc = run_launcher(mode="Http", test_mode="http", custom_run=callback)
    log = events.read_text(encoding="utf-8")
    receipt_path = evidence / "cleanup-receipt.json"

    if mutation == "reverse":
        assert proc.returncode == 0, proc.stderr
        assert "INNER_RUN_OK" in proc.stdout
        assert "RETRIEVAL_TEST_CLEANED" in proc.stdout
        assert f"rm-called {api_cid}" in log
        assert not claim.exists()
        assert receipt_path.exists()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        assert receipt["cleanup_succeeded"]
    else:
        assert proc.returncode != 0
        assert f"rm-called {api_cid}" not in log
        assert claim.exists()
        assert receipt_path.exists()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        assert not receipt["cleanup_succeeded"]
