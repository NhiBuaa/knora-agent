import argparse
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.cli.ingest import media_type_for_path, run_ingestion
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import DocumentTable, WorkspaceTable
from knora.domain.errors import KnoraError


@pytest.mark.parametrize("name", ["policy.md", "policy.markdown"])
def test_cli_accepts_markdown_paths(name: str) -> None:
    assert media_type_for_path(Path(name)) == "text/markdown"


@pytest.mark.parametrize("name", ["policy.txt", "policy.text", "policy"])
def test_cli_accepts_plain_text_paths(name: str) -> None:
    assert media_type_for_path(Path(name)) == "text/plain"


def test_cli_rejects_unsupported_path_extensions() -> None:
    with pytest.raises(KnoraError, match="UNSUPPORTED_DOCUMENT_TYPE"):
        media_type_for_path(Path("policy.json"))


def test_cli_ingestion_writes_only_its_explicit_workspace(tmp_path: Path) -> None:
    workspace_id = f"cli-{uuid4()}"
    other_workspace_id = f"cli-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=workspace_id, name="CLI Workspace"),
                WorkspaceTable(id=other_workspace_id, name="Other CLI Workspace"),
            ]
        )
    path = tmp_path / "refunds.md"
    path.write_bytes(b"# Refunds\n\nRefunds are available for thirty days.\n")

    result = run_ingestion(
        argparse.Namespace(
            path=path,
            workspace=workspace_id,
            source_key="support/refunds",
            source_name=None,
        )
    )

    assert result["outcome"] == "created"
    with SessionFactory() as session:
        documents = session.scalars(
            select(DocumentTable).where(
                DocumentTable.workspace_id.in_([workspace_id, other_workspace_id])
            )
        ).all()
        assert [(document.workspace_id, document.source_key) for document in documents] == [
            (workspace_id, "support/refunds")
        ]
