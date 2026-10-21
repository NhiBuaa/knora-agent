"""Reject effective connection overrides before any database call."""

import hashlib

import httpx
import pytest
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
    "name", [None, "", "knora-153-s2-pgdata", "foreign", "knora-153-s2-pgdata-not-a-uuid"]
)
def test_storage_volume_selection_rejects_missing_historical_or_unscoped_names(monkeypatch, name):
    monkeypatch.setenv("KNORA_S2_QDRANT_VOLUME", "knora-153-s2-qdrantdata-" + "b" * 32)
    if name is None:
        monkeypatch.delenv("KNORA_S2_POSTGRES_VOLUME", raising=False)
    else:
        monkeypatch.setenv("KNORA_S2_POSTGRES_VOLUME", name)
    with pytest.raises(ValueError, match="volume"):
        s2_runtime_guard.selected_s2_volumes()


def test_compose_requires_explicit_fresh_volume_selection():
    from pathlib import Path

    import yaml

    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.s2.yml").read_text()
    )
    for key, variable in (
        ("pgdata", "KNORA_S2_POSTGRES_VOLUME"),
        ("qdrantdata", "KNORA_S2_QDRANT_VOLUME"),
    ):
        assert compose["volumes"][key]["name"].startswith("${" + variable + ":?")
