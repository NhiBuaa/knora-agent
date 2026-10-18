"""Reject effective connection overrides before any database call."""

import hashlib

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
