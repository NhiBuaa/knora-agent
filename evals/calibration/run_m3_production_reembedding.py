import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.reembedding_store import PostgresReembeddingStore
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    RetrievalV2CutoverTable,
    WorkspaceTable,
)
from knora.answering.reembedding_v2 import ReembedProductionCorpus
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.gemini.embedding import GeminiEmbeddingProvider

WORKSPACE_ID = "evaluation-m3-v1"


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def corpus(root: Path) -> list[dict[str, Any]]:
    base = root / "evals/corpora/milestone_3"
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    documents = []
    for record in manifest["documents"]:
        content = (base / record["path"]).read_bytes()
        canonical = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if sha256(canonical) != record["sha256"]:
            raise ValueError(f"corpus member checksum mismatch: {record['path']}")
        documents.append(
            {
                "source_key": record["chunk_references"][0].rsplit("#", 1)[0],
                "source_name": record["path"],
                "content": canonical,
            }
        )
    return sorted(documents, key=lambda item: item["source_key"])


def snapshot(source_keys: tuple[str, ...]) -> dict[str, Any]:
    with SessionFactory() as session:
        documents = session.scalars(
            select(DocumentTable)
            .where(
                DocumentTable.workspace_id == WORKSPACE_ID,
                DocumentTable.source_key.in_(source_keys),
            )
            .order_by(DocumentTable.source_key)
        ).all()
        members = []
        v1_digest = hashlib.sha256()
        for document in documents:
            active_set = session.get(EmbeddingSetTable, document.active_embedding_set_id)
            if active_set is None:
                raise ValueError("authority member has no active embedding set")
            chunks = session.scalars(
                select(ChunkTable)
                .where(ChunkTable.chunk_set_id == active_set.chunk_set_id)
                .order_by(ChunkTable.ordinal)
            ).all()
            chunk_digest = hashlib.sha256()
            for chunk in chunks:
                chunk_digest.update(str(chunk.ordinal).encode())
                chunk_digest.update(b"\0")
                chunk_digest.update(chunk.content_checksum.encode())
                chunk_digest.update(b"\n")
            v1_sets = session.scalars(
                select(EmbeddingSetTable)
                .where(
                    EmbeddingSetTable.chunk_set_id == active_set.chunk_set_id,
                    EmbeddingSetTable.embedding_configuration_id
                    == "embedding-local-m1-v2",
                )
                .order_by(EmbeddingSetTable.id)
            ).all()
            for embedding_set in v1_sets:
                embeddings = session.scalars(
                    select(ChunkEmbeddingTable)
                    .where(
                        ChunkEmbeddingTable.embedding_set_id == embedding_set.id
                    )
                    .order_by(ChunkEmbeddingTable.chunk_id)
                ).all()
                v1_digest.update(embedding_set.id.encode())
                for embedding in embeddings:
                    v1_digest.update(embedding.id.encode())
                    v1_digest.update(embedding.chunk_id.encode())
                    v1_digest.update(
                        canonical_json([format(value, ".17g") for value in embedding.embedding])
                    )
            members.append(
                {
                    "source_key": document.source_key,
                    "document_id": document.id,
                    "document_version_id": document.current_document_version_id,
                    "chunk_set_id": active_set.chunk_set_id,
                    "chunk_set_digest": chunk_digest.hexdigest(),
                    "chunk_count": len(chunks),
                    "active_embedding_set_id": active_set.id,
                    "active_embedding_configuration_id": (
                        document.active_embedding_configuration_id
                    ),
                    "v1_embedding_set_ids": [item.id for item in v1_sets],
                }
            )
        return {
            "member_count": len(members),
            "members": members,
            "v1_artifact_digest": v1_digest.hexdigest(),
        }


def execute(root: Path, output_path: Path) -> None:
    documents = corpus(root)
    source_keys = tuple(item["source_key"] for item in documents)
    if len(source_keys) != 4 or len(set(source_keys)) != 4:
        raise ValueError("authority-bound production corpus must contain exactly four sources")
    with SessionFactory.begin() as session:
        if session.get(WorkspaceTable, WORKSPACE_ID) is not None:
            raise ValueError("isolated authority workspace already exists")
        session.add(WorkspaceTable(id=WORKSPACE_ID, name="M3 production acceptance"))
    ingest = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=WORKSPACE_ID, key_id="issue-56-acceptance")
    for document in documents:
        ingest.execute(
            IngestDocumentCommand(
                workspace_id=WORKSPACE_ID,
                source_key=document["source_key"],
                source_name=document["source_name"],
                media_type="text/plain",
                raw_content=document["content"],
                chunking_configuration=ChunkingConfiguration.milestone_one(),
                embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
            ),
            principal,
        )
    before = snapshot(source_keys)
    if before["member_count"] != len(source_keys):
        raise ValueError("production corpus population is incomplete before re-embedding")
    api_key = os.environ.get("KNORA_GEMINI_API_KEY")
    if not api_key:
        raise ValueError("runtime Gemini credential is absent")
    provider = GeminiEmbeddingProvider(api_key=api_key)
    try:
        result = ReembedProductionCorpus(
            provider=provider,
            store=PostgresReembeddingStore(
                SessionFactory, authority_source_keys=source_keys
            ),
        ).execute(
            workspace_id=WORKSPACE_ID,
            configuration=EmbeddingConfiguration.gemini_m3(),
        )
    finally:
        provider.close()
        api_key = ""
    after = snapshot(source_keys)
    before_by_source = {item["source_key"]: item for item in before["members"]}
    after_by_source = {item["source_key"]: item for item in after["members"]}
    invariant_results = {}
    for source_key in source_keys:
        old = before_by_source[source_key]
        new = after_by_source[source_key]
        invariant_results[source_key] = {
            "document_unchanged": old["document_id"] == new["document_id"],
            "document_version_unchanged": (
                old["document_version_id"] == new["document_version_id"]
            ),
            "chunk_set_unchanged": old["chunk_set_id"] == new["chunk_set_id"],
            "chunk_set_digest_unchanged": (
                old["chunk_set_digest"] == new["chunk_set_digest"]
            ),
            "v1_embedding_sets_unchanged": (
                old["v1_embedding_set_ids"] == new["v1_embedding_set_ids"]
            ),
            "v2_active": (
                new["active_embedding_configuration_id"]
                == "embedding-gemini-m1-v1"
            ),
            "v2_embedding_set_is_new": (
                new["active_embedding_set_id"]
                not in old["v1_embedding_set_ids"]
            ),
        }
    with SessionFactory() as session:
        cutover = session.get(
            RetrievalV2CutoverTable,
            (WORKSPACE_ID, "embedding-gemini-m1-v1"),
        )
        v2_vector_count = session.scalar(
            select(func.count())
            .select_from(ChunkEmbeddingTable)
            .join(
                EmbeddingSetTable,
                EmbeddingSetTable.id == ChunkEmbeddingTable.embedding_set_id,
            )
            .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
            .join(
                DocumentTable,
                DocumentTable.active_embedding_set_id == EmbeddingSetTable.id,
            )
            .where(
                DocumentTable.workspace_id == WORKSPACE_ID,
                EmbeddingSetTable.embedding_configuration_id
                == "embedding-gemini-m1-v1",
            )
        )
        gemini_config = session.get(
            EmbeddingConfigurationTable, "embedding-gemini-m1-v1"
        )
    all_invariants_pass = all(
        all(values.values()) for values in invariant_results.values()
    )
    evidence = {
        "schema_version": 1,
        "workspace_id": WORKSPACE_ID,
        "authority_corpus_id": "m3-corpus-v1",
        "authority_source_keys": source_keys,
        "before": before,
        "after": after,
        "invariants": invariant_results,
        "v1_artifact_digest_unchanged": (
            before["v1_artifact_digest"] == after["v1_artifact_digest"]
        ),
        "v2_vector_count": v2_vector_count,
        "cutover": {
            "present": cutover is not None,
            "status": cutover.status if cutover is not None else None,
            "population_digest": (
                cutover.population_digest if cutover is not None else None
            ),
            "matches_execution": (
                cutover is not None
                and cutover.population_digest == result.population_digest
            ),
        },
        "embedding_configuration": {
            "present": gemini_config is not None,
            "id": gemini_config.id if gemini_config is not None else None,
            "provider": gemini_config.provider if gemini_config is not None else None,
            "model": gemini_config.model if gemini_config is not None else None,
            "dimensions": gemini_config.dimensions if gemini_config is not None else None,
            "input_policy_id": (
                gemini_config.input_policy_id if gemini_config is not None else None
            ),
        },
        "all_invariants_pass": all_invariants_pass,
        "credential_retained": False,
        "provider_vectors_retained_in_evidence": False,
    }
    if not (
        all_invariants_pass
        and evidence["v1_artifact_digest_unchanged"]
        and evidence["cutover"]["matches_execution"]
        and v2_vector_count == sum(item["chunk_count"] for item in after["members"])
    ):
        raise ValueError("production corpus cutover invariants failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_json(evidence))
    print(
        json.dumps(
            {
                "status": "PASSED",
                "member_count": len(source_keys),
                "v2_vector_count": v2_vector_count,
                "population_digest": result.population_digest,
                "evidence_sha256": sha256(output_path.read_bytes()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    execute(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
