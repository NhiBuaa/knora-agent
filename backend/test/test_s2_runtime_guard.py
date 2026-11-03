"""Reject effective connection overrides before any database call."""

import hashlib
from pathlib import Path

import httpx
import pytest
import yaml
from backend.runtime_test import s2_runtime_guard


@pytest.mark.parametrize(
    "query",
    [
        "dbname=other",
        "host=other",
        "port=5432",
        "service=other",
        "options=-csearch_path=other",
        "connect_timeout=0",
    ],
)
def test_owned_database_guard_rejects_query_overrides(monkeypatch, query):
    monkeypatch.setenv("KNORA_S2_ISOLATED_TESTS", "1")
    with pytest.raises(ValueError):
        s2_runtime_guard.require_owned_s2_database(
            "postgresql+psycopg://knora_s2:isolated_s2@127.0.0.1:15433/knora_153_s2?" + query
        )


def test_owned_database_guard_accepts_only_the_approved_target(monkeypatch):
    monkeypatch.setenv("KNORA_S2_ISOLATED_TESTS", "1")
    s2_runtime_guard.require_owned_s2_database(
        "postgresql+psycopg://knora_s2:isolated_s2@127.0.0.1:15433/knora_153_s2?connect_timeout=3"
    )
    monkeypatch.delenv("KNORA_S2_ISOLATED_TESTS")
    with pytest.raises(ValueError):
        s2_runtime_guard.require_owned_s2_database(
            "postgresql+psycopg://knora_s2:isolated_s2@127.0.0.1:15433/knora_153_s2"
        )


def test_reference_file_is_checked_before_execution(tmp_path):
    path = tmp_path / "reference.cjs"
    path.write_bytes(b"original")
    pin = hashlib.sha256(b"original").hexdigest()
    s2_runtime_guard.require_reference_file(path, pin)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="reference file"):
        s2_runtime_guard.require_reference_file(path, pin)


@pytest.mark.parametrize("failure", [False, True])
def test_native_budget_reserves_before_send_even_when_transport_fails(failure):
    calls, sent = [], []

    def transport(request):
        sent.append(request)
        if failure:
            raise httpx.ReadTimeout("lost response", request=request)
        return httpx.Response(200, json={"status": "ok"})

    def reserve(request):
        s2_runtime_guard.reserve_native_request(request, calls, limit=2, collection="owned")

    with httpx.Client(
        transport=httpx.MockTransport(transport), event_hooks={"request": [reserve]}
    ) as client:
        for _ in range(2):
            if failure:
                with pytest.raises(httpx.ReadTimeout):
                    client.get("http://127.0.0.1:16433/collections/owned/exists")
            else:
                client.get("http://127.0.0.1:16433/collections/owned/exists")
        with pytest.raises(ValueError, match="budget"):
            client.get("http://127.0.0.1:16433/collections/owned/exists")
    assert len(sent) == len(calls) == 2
    assert all(record["method"] == "GET" for record in calls)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:16433/collections/owned",
        "http://foreign:16433/collections/owned",
        "http://127.0.0.1:6333/collections/owned",
        "http://127.0.0.1:16433/collections/owned-other",
    ],
)
def test_native_guard_rejects_foreign_target_before_transport(url):
    calls, sent = [], []
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda request: sent.append(request)),
            event_hooks={
                "request": [
                    lambda request: s2_runtime_guard.reserve_native_request(
                        request, calls, limit=2, collection="owned"
                    )
                ]
            },
        ) as client,
        pytest.raises(ValueError, match="target"),
    ):
        client.get(url)
    assert sent == calls == []


def test_native_query_limit_is_reserved_before_send():
    calls = []
    request = httpx.Request("POST", "http://127.0.0.1:16433/collections/owned/points/query")
    s2_runtime_guard.reserve_native_request(request, calls, limit=5, query_limit=1)
    with pytest.raises(ValueError, match="query budget"):
        s2_runtime_guard.reserve_native_request(request, calls, limit=5, query_limit=1)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("run_id", "project", "pg_vol", "qd_vol", "error_match"),
    [
        (None, None, None, None, "run ID|volume"),
        ("", None, None, None, "run ID|volume"),
        ("NOT-A-LOWERCASE-UUID-HEX", None, None, None, "run ID|volume"),
        ("c" * 31, None, None, None, "run ID|volume"),
        ("c" * 32, "knora-153-s2", None, None, "project|volume"),
        ("c" * 32, "foreign-project", None, None, "project|volume"),
        ("c" * 32, "knora-retrieval-test-" + "d" * 32, None, None, "project|volume"),
        ("c" * 32, "knora-retrieval-test-" + "c" * 32, "knora-153-s2-pgdata", None, "volume"),
        ("c" * 32, "knora-retrieval-test-" + "c" * 32, "foreign-pgdata", None, "volume"),
        ("c" * 32, "knora-retrieval-test-" + "c" * 32, None, "knora-153-s2-qdrantdata", "volume"),
        (
            "c" * 32,
            "knora-retrieval-test-" + "c" * 32,
            "knora-retrieval-test-" + "d" * 32 + "_verification-pgdata",
            None,
            "volume",
        ),
    ],
)
def test_storage_volume_selection_rejects_missing_historical_or_unscoped_names(
    monkeypatch, run_id, project, pg_vol, qd_vol, error_match
):
    if run_id is None:
        monkeypatch.delenv("KNORA_S2_RUN_ID", raising=False)
    else:
        monkeypatch.setenv("KNORA_S2_RUN_ID", run_id)

    if project is None:
        monkeypatch.delenv("KNORA_S2_PROJECT", raising=False)
    else:
        monkeypatch.setenv("KNORA_S2_PROJECT", project)

    if pg_vol is None:
        monkeypatch.delenv("KNORA_S2_POSTGRES_VOLUME", raising=False)
    else:
        monkeypatch.setenv("KNORA_S2_POSTGRES_VOLUME", pg_vol)

    if qd_vol is None:
        monkeypatch.delenv("KNORA_S2_QDRANT_VOLUME", raising=False)
    else:
        monkeypatch.setenv("KNORA_S2_QDRANT_VOLUME", qd_vol)

    with pytest.raises(ValueError, match=error_match):
        s2_runtime_guard.selected_s2_volumes()


def test_storage_volume_selection_accepts_exact_project_scoped_volumes(monkeypatch):
    run_id = "c" * 32
    project = f"knora-retrieval-test-{run_id}"
    expected_pg = f"{project}_verification-pgdata"
    expected_qd = f"{project}_verification-qdrantdata"

    monkeypatch.setenv("KNORA_S2_RUN_ID", run_id)
    monkeypatch.setenv("KNORA_S2_PROJECT", project)
    monkeypatch.setenv("KNORA_S2_POSTGRES_VOLUME", expected_pg)
    monkeypatch.setenv("KNORA_S2_QDRANT_VOLUME", expected_qd)

    volumes = s2_runtime_guard.selected_s2_volumes()
    assert volumes["postgres"] == expected_pg
    assert volumes["qdrant"] == expected_qd


def test_default_dev_compose_does_not_require_s2_environment_variables():
    dev_compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.dev.yml").read_text(encoding="utf-8")
    )
    volumes = dev_compose.get("volumes", {})
    assert "verification-pgdata" in volumes
    assert "verification-qdrantdata" in volumes
    for key in ("verification-pgdata", "verification-qdrantdata"):
        vol = volumes.get(key)
        if vol and isinstance(vol, dict) and "name" in vol:
            assert not str(vol["name"]).startswith("${KNORA_S2_")


def test_retrieval_topology_dev_compose_contract():
    dev_compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.dev.yml").read_text(encoding="utf-8")
    )
    services = dev_compose.get("services", {})

    # verification-postgres
    assert "verification-postgres" in services
    pg = services["verification-postgres"]
    assert "retrieval-test" in pg.get("profiles", [])
    assert (
        pg.get("image") == "pgvector/pgvector:pg16@sha256:"
        "ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b"
    )
    assert "127.0.0.1:15433:5432" in [str(p) for p in pg.get("ports", [])]
    assert any(
        "verification-pgdata:/var/lib/postgresql/data" in str(v) for v in pg.get("volumes", [])
    )

    # verification-qdrant
    assert "verification-qdrant" in services
    qd = services["verification-qdrant"]
    assert "retrieval-test" in qd.get("profiles", [])
    assert (
        qd.get("image") == "qdrant/qdrant:v1.19.2@sha256:"
        "b7b0444c4c351c970b98e90a6f89c2ee4287c65b44e52b4cb503fa5b2aa927ad"
    )
    assert "127.0.0.1:16433:6333" in [str(p) for p in qd.get("ports", [])]
    assert any("verification-qdrantdata:/qdrant/storage" in str(v) for v in qd.get("volumes", []))

    # verification-api
    assert "verification-api" in services
    api = services["verification-api"]
    assert "retrieval-http-test" in api.get("profiles", [])
    assert api.get("build", {}).get("context") == "."
    assert api.get("build", {}).get("dockerfile") == "backend/Dockerfile"
    assert "127.0.0.1:18053:8000" in [str(p) for p in api.get("ports", [])]


@pytest.mark.parametrize(
    ("target_service", "field", "value"),
    [
        ("verification-postgres", "working_dir", ""),
        ("verification-postgres", "working_dir", "   "),
        ("verification-postgres", "working_dir", None),
        ("verification-postgres", "config_files", ""),
        ("verification-postgres", "config_files", "   "),
        ("verification-postgres", "config_files", None),
        ("verification-qdrant", "working_dir", ""),
        ("verification-qdrant", "working_dir", "   "),
        ("verification-qdrant", "working_dir", None),
        ("verification-qdrant", "config_files", ""),
        ("verification-qdrant", "config_files", "   "),
        ("verification-qdrant", "config_files", None),
    ],
)
def test_require_owned_s2_storage_rejects_missing_or_blank_compose_labels(
    monkeypatch, target_service, field, value
):
    root = Path(__file__).resolve().parents[2]
    run_id = "c" * 32
    project = f"knora-retrieval-test-{run_id}"

    monkeypatch.setenv("KNORA_S2_RUN_ID", run_id)
    monkeypatch.setenv("KNORA_S2_PROJECT", project)
    expected_pg = f"{project}_verification-pgdata"
    expected_qd = f"{project}_verification-qdrantdata"
    monkeypatch.setenv("KNORA_S2_POSTGRES_VOLUME", expected_pg)
    monkeypatch.setenv("KNORA_S2_QDRANT_VOLUME", expected_qd)

    dev_yml = str(root / "docker-compose.dev.yml")
    rows = [
        {
            "Id": "1" * 64,
            "Image": "sha256:" + "a" * 64,
            "State": {"Running": True, "Restarting": False},
            "Config": {
                "Labels": {
                    "com.docker.compose.project": project,
                    "com.docker.compose.service": "verification-postgres",
                    "com.docker.compose.project.working_dir": str(root),
                    "com.docker.compose.project.config_files": dev_yml,
                }
            },
            "HostConfig": {"NanoCpus": 1_000_000_000, "Memory": 1024 * 1024 * 1024},
            "Mounts": [
                {
                    "Type": "volume",
                    "Name": expected_pg,
                    "Destination": "/var/lib/postgresql/data",
                    "RW": True,
                }
            ],
            "NetworkSettings": {
                "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15433"}]}
            },
        },
        {
            "Id": "2" * 64,
            "Image": "sha256:" + "b" * 64,
            "State": {"Running": True, "Restarting": False},
            "Config": {
                "Labels": {
                    "com.docker.compose.project": project,
                    "com.docker.compose.service": "verification-qdrant",
                    "com.docker.compose.project.working_dir": str(root),
                    "com.docker.compose.project.config_files": dev_yml,
                }
            },
            "HostConfig": {"NanoCpus": 2_000_000_000, "Memory": 2048 * 1024 * 1024},
            "Mounts": [
                {
                    "Type": "volume",
                    "Name": expected_qd,
                    "Destination": "/qdrant/storage",
                    "RW": True,
                }
            ],
            "NetworkSettings": {
                "Ports": {"6333/tcp": [{"HostIp": "127.0.0.1", "HostPort": "16433"}]}
            },
        },
    ]

    target_idx = 0 if target_service == "verification-postgres" else 1
    label_key = f"com.docker.compose.project.{field}"
    if value is None:
        rows[target_idx]["Config"]["Labels"].pop(label_key, None)
    else:
        rows[target_idx]["Config"]["Labels"][label_key] = value

    with pytest.raises(ValueError, match="admission|incomplete"):
        s2_runtime_guard.require_owned_s2_storage(rows, root)
