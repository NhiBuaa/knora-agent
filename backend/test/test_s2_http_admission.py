"""The HTTP proof cannot run a worker on an ambient Docker target."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.runtime_test import test_s2_http_application as runtime


def application_row(root):
    return {
        "Id": "a" * 64,
        "Image": "sha256:" + "b" * 64,
        "State": {"Running": True, "Restarting": False},
        "Config": {
            "Labels": {
                "com.docker.compose.project": "knora-153-s2",
                "com.docker.compose.service": "application",
                "com.docker.compose.project.working_dir": str(root),
                "com.docker.compose.project.config_files": str(root / "docker-compose.s2.yml"),
            },
            "Env": [
                "KNORA_PROVIDER_MODE=deterministic-local",
                "KNORA_EMBEDDING_PROVIDER=deterministic-local",
                "KNORA_GENERATION_PROVIDER=deterministic-local",
                "KNORA_DATABASE_URL=postgresql+psycopg://knora_s2:isolated_s2@postgres:5432/knora_153_s2",
                "KNORA_RETRIEVAL_CONFIGURATION_ID=retrieval-bm25-upload-fixture-top8-v1",
                "KNORA_LEXICAL_QDRANT_URL=http://qdrant:6333",
                "KNORA_LEXICAL_POPULATION_MANIFEST=/app/evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json",
                "KNORA_OBJECT_STORE_BACKEND=filesystem",
                "KNORA_OBJECT_STORE_ROOT=/s2-objects",
                "KNORA_LEXICAL_QDRANT_COLLECTION=s2_http_test",
            ],
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": str(root / "evidence/http-objects"),
                "Destination": "/s2-objects",
                "RW": True,
            }
        ],
        "HostConfig": {"NanoCpus": 1_000_000_000, "Memory": 768 * 1024 * 1024},
        "NetworkSettings": {"Ports": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18053"}]}},
    }


@pytest.mark.parametrize(
    "change", [None, "project", "source", "port", "memory", "provider", "native", "objects"]
)
def test_application_admission_pins_local_daemon_and_owned_container(monkeypatch, change):
    root = Path(__file__).resolve().parents[2]
    row = deepcopy(application_row(root))
    if change == "project":
        row["Config"]["Labels"]["com.docker.compose.project"] = "other-project"
    elif change == "source":
        row["Config"]["Labels"]["com.docker.compose.project.working_dir"] = str(root / "other")
    elif change == "port":
        row["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostIp"] = "0.0.0.0"
    elif change == "memory":
        row["HostConfig"]["Memory"] = 0
    elif change == "provider":
        row["Config"]["Env"][0] = "KNORA_PROVIDER_MODE=openai-compatible"
    elif change == "native":
        row["Config"]["Env"][5] = "KNORA_LEXICAL_QDRANT_URL=https://foreign.example"
    elif change == "objects":
        row["Mounts"][0]["Source"] = str(root / "other-objects")
    monkeypatch.setenv("KNORA_S2_EVIDENCE_ROOT", str(root / "evidence"))
    monkeypatch.setenv("KNORA_S2_OBJECT_STORE_ROOT", str(root / "evidence/http-objects"))
    monkeypatch.setenv("KNORA_S2_APPLICATION_COLLECTION", "s2_http_test")
    monkeypatch.setenv("DOCKER_CONTEXT", "foreign-context")
    monkeypatch.setenv("DOCKER_HOST", "tcp://foreign:2375")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "foreign-project")
    calls = []

    def inspect(command, **kwargs):
        calls.append(command)
        assert command[:3] == ["docker", "--host", "npipe:////./pipe/dockerDesktopLinuxEngine"]
        assert not any(key.startswith(("DOCKER_", "COMPOSE_")) for key in kwargs["env"])
        return SimpleNamespace(stdout=json.dumps([row]))

    monkeypatch.setattr(runtime.subprocess, "run", inspect)
    if change:
        with pytest.raises(AssertionError):
            runtime._owned_application(root)
    else:
        command, environment, container_id, image_id = runtime._owned_application(root)
        assert command[:3] == calls[0][:3]
        assert container_id == row["Id"] and image_id == row["Image"]
        assert "DOCKER_CONTEXT" not in environment
    assert len(calls) == 1


def test_windows_worker_environment_uses_owned_endpoints_and_discards_ambient_settings(monkeypatch):
    from sqlalchemy.engine import make_url

    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("KNORA_S2_APPLICATION_COLLECTION", "s2_http_test")
    monkeypatch.setenv("KNORA_S2_OBJECT_STORE_ROOT", str(root / "evidence/http-objects"))
    monkeypatch.setattr(
        runtime,
        "SessionFactory",
        SimpleNamespace(
            kw={
                "bind": SimpleNamespace(
                    url=make_url(
                        "postgresql+psycopg://knora_s2:isolated_s2@127.0.0.1:15433/knora_153_s2?connect_timeout=3"
                    )
                )
            }
        ),
    )
    environment = runtime._windows_worker_environment(
        root,
        {
            "PATH": "kept",
            "KNORA_GENERATION_PROVIDER": "paid-ambient-provider",
            "KNORA_OBJECT_STORE_ROOT": "foreign",
            "KNORA_OPENAI_API_KEY": "must-not-reach-worker",
        },
    )
    assert environment["PATH"] == "kept"
    assert "KNORA_OPENAI_API_KEY" not in environment
    assert environment["KNORA_GENERATION_PROVIDER"] == "deterministic-local"
    assert environment["KNORA_LEXICAL_QDRANT_URL"] == "http://127.0.0.1:16433"
    assert environment["KNORA_OBJECT_STORE_ROOT"] == str(root / "evidence/http-objects")
    assert environment["PYTHONPATH"].split(runtime.os.pathsep) == [
        str(root / "backend/src"),
        str(root),
    ]
