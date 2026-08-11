from datetime import UTC, datetime

import pytest

from knora.adapters.object_store.inventory import JsonlObjectInventory


def test_jsonl_inventory_is_workspace_scoped_and_validates_records(tmp_path) -> None:
    path = tmp_path / "inventory.jsonl"
    path.write_text(
        '{"workspace_id":"w1","object_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        '"created_at":"2026-01-01T00:00:00+00:00"}\n'
        '{"workspace_id":"w2","object_key":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",'
        '"created_at":"2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )

    records = JsonlObjectInventory(path).objects(workspace_id="w1")

    assert records == [("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", datetime(2026, 1, 1, tzinfo=UTC))]


def test_jsonl_inventory_rejects_invalid_record(tmp_path) -> None:
    path = tmp_path / "inventory.jsonl"
    path.write_text(
        '{"workspace_id":"w1","object_key":"",'
        '"created_at":"2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid object inventory identity"):
        JsonlObjectInventory(path).objects(workspace_id="w1")


def test_jsonl_inventory_accepts_provider_opaque_key_without_format_assumption(tmp_path) -> None:
    path = tmp_path / "inventory.jsonl"
    path.write_text(
        '{"workspace_id":"w1","object_key":"provider/object-opaque-1",'
        '"created_at":"2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )

    assert JsonlObjectInventory(path).objects(workspace_id="w1") == [
        ("provider/object-opaque-1", datetime(2026, 1, 1, tzinfo=UTC))
    ]
