from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

from knora.adapters.postgres.tables import IngestionJobTable

MIGRATION = Path(__file__).parents[3] / "migrations/versions/20261016_0155_ingestion_parent_link.py"


def test_migration_rejects_unlinked_legacy_index_rows_before_schema_change():
    assert MIGRATION.is_file()
    migration = run_path(str(MIGRATION))
    calls = []
    op = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(scalar=lambda query: 2),
        add_column=lambda *args, **kwargs: calls.append("add_column"),
    )
    migration["upgrade"].__globals__["op"] = op
    with pytest.raises(RuntimeError, match="legacy lexical_index jobs have no parent"):
        migration["upgrade"]()
    assert calls == []


def test_index_job_model_exposes_indexed_self_parent_fk():
    column = IngestionJobTable.__table__.c.parent_ingestion_job_id
    assert column.nullable
    assert any(fk.column is IngestionJobTable.__table__.c.id for fk in column.foreign_keys)
    assert any(
        column.name in index.columns and index.unique
        for index in IngestionJobTable.__table__.indexes
    )


def test_model_declares_required_parent_only_for_index_jobs():
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in IngestionJobTable.__table__.constraints
        if hasattr(constraint, "sqltext")
    }
    assert checks["ck_ingestion_jobs_index_parent"] == (
        "(derivation_kind = 'lexical_index' AND parent_ingestion_job_id IS NOT NULL) "
        "OR (derivation_kind <> 'lexical_index' AND parent_ingestion_job_id IS NULL)"
    )
