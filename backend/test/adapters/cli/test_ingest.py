import argparse
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.cli import ingest as cli_ingest
from knora.adapters.cli.ingest import media_type_for_path, run_ingestion
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import DocumentTable, WorkspaceTable
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestionResult
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.workspaces.ports import WorkspaceAdmission


@pytest.mark.parametrize("name", ["policy.md", "policy.markdown"])
def test_cli_accepts_markdown_paths(name: str) -> None:
    assert media_type_for_path(Path(name)) == "text/markdown"


@pytest.mark.parametrize("name", ["policy.txt", "policy.text", "policy"])
def test_cli_accepts_plain_text_paths(name: str) -> None:
    assert media_type_for_path(Path(name)) == "text/plain"


def test_cli_rejects_unsupported_path_extensions() -> None:
    with pytest.raises(KnoraError, match="UNSUPPORTED_DOCUMENT_TYPE"):
        media_type_for_path(Path("policy.json"))


def test_cli_rejects_an_archived_workspace_before_embedding_or_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing CLI admission wiring must permit embedding before this test fails."""

    class ArchivedAdmission:
        def admit(self, **_kwargs) -> WorkspaceAdmission:
            raise KnoraError("WORKSPACE_ARCHIVED")

    class ProviderMustNotRun:
        def embed_documents(self, *_args, **_kwargs):
            raise AssertionError("embedding ran after archived workspace rejection")

        embed = embed_documents

        def close(self) -> None:
            return None

    class StoreMustNotRun:
        def authorize_workspace(self, **_kwargs) -> None:
            raise AssertionError("persistence authorization ran after archived workspace rejection")

        def read_document_head(self, **_kwargs):
            raise AssertionError("persistence read ran after archived workspace rejection")

        def commit_derivation(self, **_kwargs):
            raise AssertionError("persistence write ran after archived workspace rejection")

    provider = ProviderMustNotRun()
    monkeypatch.setattr(
        cli_ingest,
        "build_provider_selection",
        lambda _settings: SimpleNamespace(
            embedding_provider=provider,
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
    )
    monkeypatch.setattr(
        cli_ingest,
        "PostgresIngestionStore",
        lambda _session_factory: StoreMustNotRun(),
    )
    monkeypatch.setattr(
        cli_ingest,
        "PostgresWorkspaceAdmissionStore",
        lambda _session_factory: ArchivedAdmission(),
        raising=False,
    )
    path = tmp_path / "archived.md"
    path.write_bytes(b"# Archived\n")

    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        run_ingestion(
            argparse.Namespace(
                path=path,
                workspace="workspace-archived",
                source_key="support/archived",
                source_name=None,
            )
        )


def test_cli_ingestion_preserves_active_workspace_processing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ActiveAdmission:
        def __init__(self) -> None:
            self.closed: list[str] = []

        def admit(self, *, principal, operation: str, operation_id: str) -> WorkspaceAdmission:
            return WorkspaceAdmission(
                id="admission-1",
                workspace_id=principal.workspace_id,
                operation=operation,
                operation_id=operation_id,
                admitted_at=datetime.now(UTC),
            )

        def close(self, *, admission_id: str) -> None:
            self.closed.append(admission_id)

    class RecordingProvider:
        def __init__(self) -> None:
            self.embedded: list[list[str]] = []

        def embed_documents(self, texts, configuration) -> EmbeddingBatch:
            self.embedded.append(texts)
            return EmbeddingBatch(
                vectors=tuple(
                    tuple(0.0 for _ in range(configuration.dimensions)) for _ in texts
                ),
                provider=configuration.provider,
                model=configuration.model,
            )

        embed = embed_documents

        def close(self) -> None:
            return None

    class RecordingStore:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def authorize_workspace(self, **_kwargs) -> None:
            self.calls.append("authorize")

        def read_document_head(self, **_kwargs):
            self.calls.append("read_document_head")
            return None

        def commit_derivation(self, **_kwargs) -> IngestionResult:
            self.calls.append("commit_derivation")
            return IngestionResult(
                outcome="created",
                activation_changed=True,
                document_id="document-1",
                document_version_id="version-1",
                chunk_set_id="chunk-set-1",
                embedding_set_id="embedding-set-1",
                chunking_configuration_id="chunking-1",
                embedding_configuration_id="embedding-1",
                chunk_count=1,
            )

    admission = ActiveAdmission()
    provider = RecordingProvider()
    store = RecordingStore()
    monkeypatch.setattr(
        cli_ingest,
        "build_provider_selection",
        lambda _settings: SimpleNamespace(
            embedding_provider=provider,
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
    )
    monkeypatch.setattr(cli_ingest, "PostgresIngestionStore", lambda _session_factory: store)
    monkeypatch.setattr(
        cli_ingest,
        "PostgresWorkspaceAdmissionStore",
        lambda _session_factory: admission,
    )
    path = tmp_path / "active.md"
    path.write_bytes(b"# Active\n\nActive content.\n")

    result = run_ingestion(
        argparse.Namespace(
            path=path,
            workspace="workspace-active",
            source_key="support/active",
            source_name=None,
        )
    )

    assert result["outcome"] == "created"
    assert store.calls == ["authorize", "read_document_head", "commit_derivation"]
    assert provider.embedded == [["Active content."]]
    assert admission.closed == ["admission-1"]


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
