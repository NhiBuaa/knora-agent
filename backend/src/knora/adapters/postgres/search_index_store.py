"""Transactional generation requests and activation; no projection I/O."""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.answering.stores import LexicalGeneration as RetrievedLexicalGeneration
from knora.domain.errors import KnoraError
from knora.ingestion.job_processing import IngestionWork
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalIndexInput,
    LexicalProfile,
    StageReceipt,
    StaleGenerationError,
)


class PostgresSearchIndexStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sessions = session_factory

    def read_active_generations(
        self, workspace_id: str, lexical_policy_id: str
    ) -> tuple[LexicalGeneration, ...]:
        with self._sessions.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable).where(WorkspaceTable.id == workspace_id).with_for_update()
            )
            if workspace is None or workspace.archived:
                raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")
            generations = self.read_active_generations_in_snapshot(
                session, workspace_id, lexical_policy_id
            )
            snapshots = tuple(
                RetrievedLexicalGeneration(
                    workspace_id,
                    g.document_id,
                    g.document_version_id,
                    g.chunk_set_id,
                    g.generation_id,
                    lexical_policy_id,
                )
                for g in generations
            )
            self.revalidate_lexical_snapshot_in_transaction(
                session, workspace_id, lexical_policy_id, snapshots
            )
            return generations

    def read_active_generations_in_snapshot(
        self, session: Session, workspace_id: str, lexical_policy_id: str
    ) -> tuple[LexicalGeneration, ...]:
        """Read the same corpus authority within a caller-owned consistent projection snapshot."""
        document_ids = session.scalars(
            select(DocumentTable.id)
            .join(LexicalHeadTable, LexicalHeadTable.document_id == DocumentTable.id)
            .where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.archived.is_(False),
                LexicalHeadTable.active_generation_id.is_not(None),
            )
            .order_by(DocumentTable.id)
        ).all()
        generations = tuple(
            self.read_active_generation_in_snapshot(
                session, workspace_id, document_id, lexical_policy_id
            )
            for document_id in document_ids
        )
        if not generations or len({g.lexical_profile.digest() for g in generations}) != 1:
            raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")
        return generations

    def revalidate_lexical_snapshot(
        self,
        workspace_id: str,
        lexical_policy_id: str,
        generations: tuple[RetrievedLexicalGeneration, ...],
    ) -> None:
        with self._sessions.begin() as session:
            self.revalidate_lexical_snapshot_in_transaction(
                session, workspace_id, lexical_policy_id, generations
            )

    def read_active_generation_in_snapshot(
        self, session: Session, workspace_id: str, document_id: str, lexical_policy_id: str
    ) -> LexicalGeneration:
        """Read authority in a caller-owned consistent snapshot; acquire no lifecycle locks."""
        try:
            workspace = session.get(WorkspaceTable, workspace_id)
            document = session.get(DocumentTable, document_id)
            head = session.get(LexicalHeadTable, document_id)
            row = (
                session.get(LexicalGenerationTable, head.active_generation_id)
                if head and head.active_generation_id
                else None
            )
            if (
                workspace is None
                or workspace.archived
                or document is None
                or document.archived
                or document.workspace_id != workspace_id
                or head is None
                or row is None
                or row.status != "active"
                or row.workspace_id != workspace_id
                or row.document_id != document_id
                or row.source_revision != document.revision
                or row.workspace_revision != workspace.revision
                or row.document_version_id != document.current_document_version_id
                or row.acknowledged_count != row.expected_count
            ):
                raise LexicalGenerationError("lexical snapshot is no longer active")
            generation = self._decode_generation(row)
            chunk_set = session.get(ChunkSetTable, row.chunk_set_id)
            version = session.get(DocumentVersionTable, row.document_version_id)
            if (
                generation.lexical_profile.id != lexical_policy_id
                or chunk_set is None
                or chunk_set.status != "completed"
                or chunk_set.document_version_id != row.document_version_id
                or version is None
                or version.document_id != document.id
            ):
                raise LexicalGenerationError("lexical source or profile is unavailable")
            return generation
        except LexicalGenerationError as exc:
            raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc

    def revalidate_lexical_snapshot_in_transaction(
        self,
        session: Session,
        workspace_id: str,
        lexical_policy_id: str,
        generations: tuple[RetrievedLexicalGeneration, ...],
    ) -> None:
        try:
            if not generations or len({g.document_id for g in generations}) != len(generations):
                raise LexicalGenerationError("lexical snapshot is incomplete")
            # Match lifecycle lock order; release these locks before any provider call.
            for snapshot in sorted(generations, key=lambda item: item.document_id):
                if (
                    snapshot.workspace_id != workspace_id
                    or snapshot.lexical_policy_id != lexical_policy_id
                ):
                    raise LexicalGenerationError("lexical snapshot is foreign")
                self._lock_document(session, workspace_id, snapshot.document_id)
                generation = self.read_active_generation_in_snapshot(
                    session, workspace_id, snapshot.document_id, lexical_policy_id
                )
                if (
                    generation.generation_id,
                    generation.document_version_id,
                    generation.chunk_set_id,
                ) != (
                    snapshot.index_generation_id,
                    snapshot.document_version_id,
                    snapshot.chunk_set_id,
                ):
                    raise LexicalGenerationError("lexical snapshot is no longer active")
        except LexicalGenerationError as exc:
            raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc

    @staticmethod
    def _lock_document(
        session: Session, workspace_id: str, document_id: str, *, allow_archived: bool = False
    ) -> tuple[WorkspaceTable, DocumentTable]:
        workspace = session.scalar(
            select(WorkspaceTable)
            .where(
                WorkspaceTable.id == workspace_id,
            )
            .with_for_update()
        )
        document = session.scalar(
            select(DocumentTable)
            .where(
                DocumentTable.id == document_id,
                DocumentTable.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        if (
            workspace is None
            or document is None
            or (not allow_archived and (workspace.archived or document.archived))
        ):
            raise StaleGenerationError("lexical source is unavailable")
        return workspace, document

    def request_generation(self, generation: LexicalGeneration, *, expected_revision: int) -> None:
        with self._sessions.begin() as session:
            self.request_generation_in_transaction(
                session, generation, expected_revision=expected_revision
            )

    def request_generation_in_transaction(
        self, session: Session, generation: LexicalGeneration, *, expected_revision: int
    ) -> None:
        workspace, document = self._lock_document(
            session, generation.workspace_id, generation.document_id
        )
        existing = session.get(LexicalGenerationTable, generation.generation_id)
        if existing is not None:
            if (
                existing.content_digest != generation.content_digest()
                or existing.status == "revoked"
            ):
                raise StaleGenerationError("generation identity cannot be reused")
            return
        if document.current_document_version_id != generation.document_version_id:
            raise StaleGenerationError("generation targets an obsolete source version")
        chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
        if (
            chunk_set is None
            or chunk_set.document_version_id != generation.document_version_id
            or chunk_set.status != "completed"
        ):
            raise StaleGenerationError("generation targets an incomplete chunk set")
        chunks = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == generation.chunk_set_id)
            .order_by(ChunkTable.ordinal)
        ).all()
        if [(c.id, c.ordinal, c.content_checksum) for c in chunks] != [
            (c.chunk_id, c.ordinal, c.content_checksum) for c in generation.chunks
        ]:
            raise StaleGenerationError("generation manifest differs from authoritative chunks")
        head = session.get(LexicalHeadTable, document.id)
        current_revision = head.revision if head is not None else 0
        if current_revision != expected_revision or generation.revision != expected_revision + 1:
            raise StaleGenerationError("desired generation compare-and-set failed")
        row = LexicalGenerationTable(
            id=generation.generation_id,
            workspace_id=generation.workspace_id,
            document_id=document.id,
            document_version_id=generation.document_version_id,
            chunk_set_id=generation.chunk_set_id,
            revision=generation.revision,
            source_revision=document.revision,
            workspace_revision=workspace.revision,
            profile_digest=generation.lexical_profile.digest(),
            content_digest=generation.content_digest(),
            expected_count=len(generation.chunks),
            manifest=asdict(generation),
            status="requested",
        )
        session.add(row)
        session.flush()
        if head is None:
            head = LexicalHeadTable(document_id=document.id, revision=0)
            session.add(head)
        active = (
            session.get(LexicalGenerationTable, head.active_generation_id)
            if head.active_generation_id
            else None
        )
        if active is not None and (
            active.document_version_id != generation.document_version_id
            or active.profile_digest != row.profile_digest
            or active.source_revision != document.revision
            or active.workspace_revision != workspace.revision
        ):
            head.active_generation_id = None
        head.revision = generation.revision
        head.desired_generation_id = generation.generation_id

    def activate_ready(self, generation: LexicalGeneration, receipt: StageReceipt) -> None:
        receipt.validate(generation)
        with self._sessions.begin() as session:
            self.activate_ready_in_transaction(session, generation, receipt)

    def activate_ready_in_transaction(
        self, session: Session, generation: LexicalGeneration, receipt: StageReceipt
    ) -> None:
        receipt.validate(generation)
        workspace, document = self._lock_document(
            session, generation.workspace_id, generation.document_id
        )
        head = session.get(LexicalHeadTable, document.id)
        row = session.get(LexicalGenerationTable, generation.generation_id)
        if (
            head is None
            or row is None
            or head.desired_generation_id != row.id
            or head.revision != generation.revision
            or row.revision != generation.revision
            or row.status == "revoked"
            or row.source_revision != document.revision
            or row.workspace_revision != workspace.revision
            or document.current_document_version_id != row.document_version_id
            or row.content_digest != receipt.content_digest
            or row.expected_count != receipt.point_count
        ):
            raise StaleGenerationError("activation compare-and-set failed")
        if row.acknowledged_count not in (None, receipt.point_count):
            raise StaleGenerationError("conflicting acknowledgement replay")
        row.acknowledged_count = receipt.point_count
        row.status = "active"
        head.active_generation_id = row.id

    def stage_corpus_transition(self, generations: Sequence[LexicalGeneration]) -> None:
        """Stage generations for a corpus snapshot transition without disrupting active serving."""
        with self._sessions.begin() as session:
            self.stage_corpus_transition_in_transaction(session, generations)

    def stage_corpus_transition_in_transaction(
        self, session: Session, generations: Sequence[LexicalGeneration]
    ) -> None:
        if not generations:
            raise StaleGenerationError("corpus transition batch cannot be empty")
        profile_digests = {g.lexical_profile.digest() for g in generations}
        if len(profile_digests) != 1:
            raise StaleGenerationError("corpus transition contains mixed profile digests")
        ordered = sorted(generations, key=lambda g: g.document_id)
        for generation in ordered:
            workspace, document = self._lock_document(
                session, generation.workspace_id, generation.document_id
            )
            existing = session.get(LexicalGenerationTable, generation.generation_id)
            if existing is not None:
                if (
                    existing.content_digest != generation.content_digest()
                    or existing.status == "revoked"
                ):
                    raise StaleGenerationError("generation identity cannot be reused")
                continue
            if document.current_document_version_id != generation.document_version_id:
                raise StaleGenerationError("generation targets an obsolete source version")
            chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
            if (
                chunk_set is None
                or chunk_set.document_version_id != generation.document_version_id
                or chunk_set.status != "completed"
            ):
                raise StaleGenerationError("generation targets an incomplete chunk set")
            chunks = session.scalars(
                select(ChunkTable)
                .where(ChunkTable.chunk_set_id == generation.chunk_set_id)
                .order_by(ChunkTable.ordinal)
            ).all()
            if [(c.id, c.ordinal, c.content_checksum) for c in chunks] != [
                (c.chunk_id, c.ordinal, c.content_checksum) for c in generation.chunks
            ]:
                raise StaleGenerationError("generation manifest differs from authoritative chunks")
            head = session.get(LexicalHeadTable, document.id)
            if head is None:
                head = LexicalHeadTable(document_id=document.id, revision=0)
                session.add(head)
            if generation.revision != head.revision + 1:
                raise StaleGenerationError("desired generation compare-and-set failed")
            row = LexicalGenerationTable(
                id=generation.generation_id,
                workspace_id=generation.workspace_id,
                document_id=document.id,
                document_version_id=generation.document_version_id,
                chunk_set_id=generation.chunk_set_id,
                revision=generation.revision,
                source_revision=document.revision,
                workspace_revision=workspace.revision,
                profile_digest=generation.lexical_profile.digest(),
                content_digest=generation.content_digest(),
                expected_count=len(generation.chunks),
                manifest=asdict(generation),
                status="requested",
            )
            session.add(row)
            session.flush()
            head.revision = generation.revision
            head.desired_generation_id = generation.generation_id

    def commit_corpus_transition(
        self, items: Sequence[tuple[LexicalGeneration, StageReceipt]]
    ) -> None:
        """Atomically transition serving generations to a new consistent corpus profile."""
        with self._sessions.begin() as session:
            self.commit_corpus_transition_in_transaction(session, items)

    def commit_corpus_transition_in_transaction(
        self, session: Session, items: Sequence[tuple[LexicalGeneration, StageReceipt]]
    ) -> None:
        if not items:
            raise StaleGenerationError("corpus transition batch cannot be empty")
        profile_digests = {g.lexical_profile.digest() for g, _ in items}
        if len(profile_digests) != 1:
            raise StaleGenerationError("corpus transition contains mixed profile digests")
        target_profile_digest = next(iter(profile_digests))
        workspace_ids = {g.workspace_id for g, _ in items}
        if len(workspace_ids) != 1:
            raise StaleGenerationError("corpus transition contains mixed workspaces")
        workspace_id = next(iter(workspace_ids))

        # Check full persisted membership: all active documents in this workspace
        # must transition together when switching to a new corpus profile digest
        active_doc_ids = set(
            session.scalars(
                select(DocumentTable.id)
                .join(LexicalHeadTable, LexicalHeadTable.document_id == DocumentTable.id)
                .where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.archived.is_(False),
                    LexicalHeadTable.active_generation_id.is_not(None),
                )
            ).all()
        )
        current_active_profile_digests = set()
        for doc_id in active_doc_ids:
            head = session.get(LexicalHeadTable, doc_id)
            if head and head.active_generation_id:
                active_row = session.get(LexicalGenerationTable, head.active_generation_id)
                if active_row:
                    current_active_profile_digests.add(active_row.profile_digest)

        is_profile_transition = bool(
            current_active_profile_digests
            and target_profile_digest not in current_active_profile_digests
        )
        submitted_doc_ids = {g.document_id for g, _ in items}
        if is_profile_transition and active_doc_ids and submitted_doc_ids != active_doc_ids:
            missing = active_doc_ids - submitted_doc_ids
            raise StaleGenerationError(
                "corpus transition requires receipts for all active documents in corpus; "
                f"missing: {missing}"
            )

        is_cold_activation = not active_doc_ids
        if is_cold_activation:
            staged_doc_ids = set(
                session.scalars(
                    select(DocumentTable.id)
                    .join(LexicalHeadTable, LexicalHeadTable.document_id == DocumentTable.id)
                    .join(
                        LexicalGenerationTable,
                        LexicalHeadTable.desired_generation_id == LexicalGenerationTable.id,
                    )
                    .where(
                        DocumentTable.workspace_id == workspace_id,
                        DocumentTable.archived.is_(False),
                        LexicalGenerationTable.profile_digest == target_profile_digest,
                    )
                ).all()
            )
            if staged_doc_ids and submitted_doc_ids != staged_doc_ids:
                missing = staged_doc_ids - submitted_doc_ids
                if missing:
                    raise StaleGenerationError(
                        "corpus transition requires receipts for all staged documents in corpus; "
                        f"missing: {missing}"
                    )
                extra = submitted_doc_ids - staged_doc_ids
                raise StaleGenerationError(
                    f"corpus transition contains unexpected unstaged documents; extra: {extra}"
                )

        for generation, receipt in items:
            receipt.validate(generation)
        ordered_items = sorted(items, key=lambda pair: pair[0].document_id)
        for generation, receipt in ordered_items:
            workspace, document = self._lock_document(
                session, generation.workspace_id, generation.document_id
            )
            head = session.get(LexicalHeadTable, document.id)
            row = session.get(LexicalGenerationTable, generation.generation_id)
            if (
                head is None
                or row is None
                or head.desired_generation_id != row.id
                or head.revision != generation.revision
                or row.revision != generation.revision
                or row.status == "revoked"
                or row.source_revision != document.revision
                or row.workspace_revision != workspace.revision
                or document.current_document_version_id != row.document_version_id
                or row.content_digest != receipt.content_digest
                or row.expected_count != receipt.point_count
            ):
                raise StaleGenerationError("transition compare-and-set failed")
            if row.acknowledged_count not in (None, receipt.point_count):
                raise StaleGenerationError("conflicting acknowledgement replay")
            row.acknowledged_count = receipt.point_count
            row.status = "active"
            head.active_generation_id = row.id

    def revoke(self, *, workspace_id: str, document_id: str) -> None:
        with self._sessions.begin() as session:
            self.revoke_in_transaction(session, workspace_id=workspace_id, document_id=document_id)

    def revoke_in_transaction(
        self, session: Session, *, workspace_id: str, document_id: str
    ) -> None:
        self._lock_document(session, workspace_id, document_id, allow_archived=True)
        head = session.get(LexicalHeadTable, document_id)
        if head is None:
            return
        if head.desired_generation_id is None and head.active_generation_id is None:
            return
        for row in session.scalars(
            select(LexicalGenerationTable).where(LexicalGenerationTable.document_id == document_id)
        ):
            row.status = "revoked"
        head.revision += 1
        head.desired_generation_id = None
        head.active_generation_id = None

    @staticmethod
    def _decode_generation(row: object) -> LexicalGeneration:
        manifest = getattr(row, "manifest", None)
        if not isinstance(manifest, Mapping):
            raise LexicalGenerationError("lexical generation manifest is not an object")
        try:
            profile_data = manifest["lexical_profile"]
            chunks_data = manifest["chunks"]
            if not isinstance(profile_data, Mapping) or not isinstance(chunks_data, (list, tuple)):
                raise TypeError
            generation = LexicalGeneration(
                generation_id=manifest["generation_id"],
                workspace_id=manifest["workspace_id"],
                document_id=manifest["document_id"],
                document_version_id=manifest["document_version_id"],
                chunk_set_id=manifest["chunk_set_id"],
                lexical_profile=LexicalProfile(**dict(profile_data)),
                revision=manifest["revision"],
                chunks=tuple(LexicalChunk(**dict(chunk)) for chunk in chunks_data),
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise LexicalGenerationError("lexical generation manifest is invalid") from exc
        if (
            generation.generation_id != getattr(row, "id", None)
            or generation.workspace_id != getattr(row, "workspace_id", None)
            or generation.document_id != getattr(row, "document_id", None)
            or generation.document_version_id != getattr(row, "document_version_id", None)
            or generation.chunk_set_id != getattr(row, "chunk_set_id", None)
            or generation.revision != getattr(row, "revision", None)
            or generation.lexical_profile.digest() != getattr(row, "profile_digest", None)
            or generation.content_digest() != getattr(row, "content_digest", None)
            or len(generation.chunks) != getattr(row, "expected_count", None)
        ):
            raise LexicalGenerationError("lexical generation manifest differs from authority")
        return generation

    def cleanup_generation_in_transaction(
        self,
        session: Session,
        generation_id: str,
        remove: Callable[[LexicalGeneration], None],
    ) -> str:
        """Remove one stale projection while holding its lifecycle lock."""
        row = session.get(LexicalGenerationTable, generation_id)
        if row is None:
            return "missing"
        identity = (row.workspace_id, row.document_id)
        self._lock_document(session, *identity, allow_archived=True)
        head = session.get(LexicalHeadTable, identity[1], with_for_update=True)
        row = session.get(
            LexicalGenerationTable, generation_id, with_for_update=True, populate_existing=True
        )
        if row is None or (row.workspace_id, row.document_id) != identity or head is None:
            raise StaleGenerationError("cleanup authority is unavailable")
        # The head pointers define current eligibility; row status can describe an older activation.
        if generation_id in (head.active_generation_id, head.desired_generation_id):
            return "retained"
        generation = self._decode_generation(row)
        remove(generation)
        return "removed"

    def load_generation(self, work: IngestionWork) -> LexicalIndexInput:
        with self._sessions.begin() as session:
            return self.load_generation_in_transaction(session, work)

    def load_generation_in_transaction(
        self, session: Session, work: IngestionWork
    ) -> LexicalIndexInput:
        if (
            work.derivation_kind != "lexical_index"
            or work.lexical_generation_id is None
            or not work.ingestion_job_id
        ):
            raise LexicalGenerationError("claimed work is not bound to a lexical index job")
        job = session.get(IngestionJobTable, work.ingestion_job_id)
        if (
            job is None
            or job.derivation_kind != "lexical_index"
            or job.workspace_id != work.workspace_id
            or job.document_id != work.document_id
            or job.target_document_version_id != work.document_version_id
            or job.source_object_id != work.source_object_id
            or job.lexical_generation_id != work.lexical_generation_id
            or job.parser_configuration_id != work.parser_configuration_id
            or job.normalizer_configuration_id != work.normalizer_configuration_id
            or job.chunking_configuration_id != work.chunking_configuration_id
            or job.embedding_configuration_id is not None
            or work.embedding_configuration_id is not None
            or job.lexical_profile is not None
            or job.source_revision != work.source_revision
            or job.workspace_revision != work.workspace_revision
        ):
            raise LexicalGenerationError("claimed work differs from its durable job")
        workspace, document = self._lock_document(session, work.workspace_id, work.document_id)
        row = session.get(LexicalGenerationTable, work.lexical_generation_id)
        head = session.get(LexicalHeadTable, work.document_id)
        if (
            document.current_document_version_id != job.target_document_version_id
            or document.revision != job.source_revision
            or workspace.revision != job.workspace_revision
            or (row is not None and row.status == "revoked")
            or (head is not None and head.desired_generation_id != job.lexical_generation_id)
        ):
            raise StaleGenerationError("lexical generation snapshot is stale")
        if row is None or head is None:
            raise LexicalGenerationError("lexical generation authority is missing")
        generation = self._decode_generation(row)
        if (
            row.status not in {"requested", "active"}
            or head.revision != row.revision
            or row.source_revision != job.source_revision
            or row.workspace_revision != job.workspace_revision
            or generation.workspace_id != work.workspace_id
            or generation.document_id != work.document_id
            or generation.document_version_id != work.document_version_id
            or (
                work.lexical_profile_digest is not None
                and work.lexical_profile_digest != row.profile_digest
            )
        ):
            raise LexicalGenerationError("generation differs from its durable job")
        version = session.get(DocumentVersionTable, work.document_version_id)
        source = session.get(OriginalSourceObjectTable, work.source_object_id)
        if version is None or source is None or source.deleted_at is not None:
            raise LexicalGenerationError("lexical source bytes are unavailable")
        if (
            version.document_id != document.id
            or source.workspace_id != workspace.id
            or source.document_version_id != version.id
            or source.raw_sha256
            != (
                version.raw_sha256
                if version.raw_sha256 is not None
                else version.normalized_content_checksum
            )
            or (version.media_type is not None and source.media_type != version.media_type)
            or source.object_key != work.source_object_key
            or source.media_type != work.source_media_type
            or source.raw_sha256 != work.source_sha256
            or source.byte_size != work.source_byte_size
            or source.byte_size <= 0
        ):
            raise LexicalGenerationError("lexical source provenance differs from claimed work")
        chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
        chunking = session.get(ChunkingConfigurationTable, work.chunking_configuration_id)
        if (
            chunk_set is None
            or chunking is None
            or chunk_set.document_version_id != version.id
            or (
                chunk_set.parser_configuration_id is not None
                and chunk_set.parser_configuration_id != job.parser_configuration_id
            )
            or (
                chunk_set.normalizer_configuration_id is not None
                and chunk_set.normalizer_configuration_id != job.normalizer_configuration_id
            )
            or chunk_set.chunking_configuration_id != job.chunking_configuration_id
        ):
            raise LexicalGenerationError("lexical chunk set provenance differs from its job")
        if chunk_set.status != "completed":
            raise LexicalGenerationError("lexical chunk set is incomplete")
        chunks = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == generation.chunk_set_id)
            .order_by(ChunkTable.ordinal)
        ).all()
        if [(chunk.id, chunk.ordinal, chunk.content_checksum) for chunk in chunks] != [
            (chunk.chunk_id, chunk.ordinal, chunk.content_checksum) for chunk in generation.chunks
        ]:
            raise LexicalGenerationError("authoritative chunks differ from generation")
        if any(
            not isinstance(chunk.content, str)
            or not chunk.content.strip()
            or hashlib.sha256(chunk.content.encode("utf-8")).hexdigest() != chunk.content_checksum
            for chunk in chunks
        ):
            raise LexicalGenerationError("authoritative chunk text checksum is invalid")
        chunk_vectors: tuple[tuple[str, tuple[float, ...]], ...] | None = None
        target_set_id = document.active_embedding_set_id
        target_config_id = (
            document.active_embedding_configuration_id or job.embedding_configuration_id
        )

        if target_set_id is not None or target_config_id is not None:
            emb_set_query = select(EmbeddingSetTable).where(
                EmbeddingSetTable.chunk_set_id == generation.chunk_set_id,
                EmbeddingSetTable.status == "completed",
            )
            if target_set_id is not None:
                emb_set_query = emb_set_query.where(EmbeddingSetTable.id == target_set_id)
            if target_config_id is not None:
                emb_set_query = emb_set_query.where(
                    EmbeddingSetTable.embedding_configuration_id == target_config_id
                )
            emb_set = session.scalar(emb_set_query)
            if emb_set is not None:
                if (
                    target_config_id is not None
                    and emb_set.embedding_configuration_id != target_config_id
                ):
                    raise LexicalGenerationError("active embedding configuration mismatch")
                chunk_embs = session.scalars(
                    select(ChunkEmbeddingTable)
                    .where(ChunkEmbeddingTable.embedding_set_id == emb_set.id)
                    .order_by(ChunkEmbeddingTable.chunk_id)
                ).all()
                if chunk_embs:
                    if len(chunk_embs) != len(chunks):
                        raise LexicalGenerationError("incomplete chunk embeddings")
                    emb_chunk_ids = {ce.chunk_id for ce in chunk_embs}
                    expected_chunk_ids = {chunk.id for chunk in chunks}
                    if emb_chunk_ids != expected_chunk_ids:
                        raise LexicalGenerationError("chunk embeddings mismatch generation chunks")
                    chunk_vectors = tuple(
                        (ce.chunk_id, tuple(float(x) for x in ce.embedding)) for ce in chunk_embs
                    )

        return LexicalIndexInput(
            generation,
            tuple((chunk.id, chunk.content) for chunk in chunks),
            chunk_vectors=chunk_vectors,
        )
