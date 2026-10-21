"""Offline identity/content checks; actual PostgreSQL snapshots need runtime evidence."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from knora.adapters.postgres.lexical_retrieval import validate_population_in_transaction
from knora.adapters.postgres.tables import ChunkTable, DocumentVersionTable
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration


@pytest.fixture
def population_snapshot():
    manifest = VerifiedLexicalPopulation.from_mapping(
        json.loads(
            Path(
                "evals/fixtures/pdf_retrieval_v3_s2/frozen47-lexical-population-v1.json"
            ).read_text(encoding="utf-8")
        )
    )
    frozen = json.loads(
        Path("evals/reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime/chunks.json").read_text(
            encoding="utf-8"
        )
    )["chunks"]
    objects = {}
    generations = []
    for i, document in enumerate(manifest.documents):
        chunks = sorted(
            (c for c in frozen if c["raw_sha256"] == document.source_sha256),
            key=lambda c: (c["page_start"], c["start_offset"], c["end_offset"]),
        )
        version_id, document_id, chunk_set_id = f"v{i}", f"d{i}", f"s{i}"
        objects[DocumentVersionTable, version_id] = SimpleNamespace(
            document_id=document_id, raw_sha256=document.source_sha256
        )
        for ordinal, chunk in enumerate(chunks):
            objects[ChunkTable, chunk["chunk_id"]] = SimpleNamespace(
                id=chunk["chunk_id"],
                chunk_set_id=chunk_set_id,
                ordinal=ordinal,
                content=chunk["content"],
                content_checksum=chunk["content_checksum"],
            )
        generations.append(
            LexicalGeneration(
                f"g{i}",
                "workspace",
                document_id,
                version_id,
                chunk_set_id,
                manifest.profile,
                1,
                tuple(
                    LexicalChunk(c["chunk_id"], j, c["content_checksum"])
                    for j, c in enumerate(chunks)
                ),
            )
        )
    ids = [g.document_id for g in generations]

    class Session:
        def get(self, model, identity):
            return objects.get((model, identity))

        def scalars(self, statement):
            return SimpleNamespace(all=lambda: ids)

    return Session(), tuple(generations), manifest, objects, ids


def test_complete_manifest_matches_authoritative_content(population_snapshot):
    session, generations, manifest, _, _ = population_snapshot
    validate_population_in_transaction(session, "workspace", generations, manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_manifest",
        "extra_document",
        "missing_document",
        "missing_chunk",
        "changed_text",
        "changed_checksum",
        "changed_ordinal",
        "foreign_chunk_set",
        "changed_source",
        "foreign_version",
        "changed_profile",
    ],
)
def test_unknown_or_changed_population_is_operationally_unavailable(population_snapshot, mutation):
    session, generations, manifest, objects, ids = population_snapshot
    generation = generations[0]
    chunk_key = (ChunkTable, generation.chunks[0].chunk_id)
    if mutation == "missing_manifest":
        manifest = None
    elif mutation == "extra_document":
        ids.append("new-document")
    elif mutation == "missing_document":
        ids.pop()
    elif mutation == "missing_chunk":
        objects.pop(chunk_key)
    elif mutation == "changed_text":
        objects[chunk_key].content += " changed"
    elif mutation == "changed_checksum":
        objects[chunk_key].content_checksum = "0" * 64
    elif mutation == "changed_ordinal":
        objects[chunk_key].ordinal += 1
    elif mutation == "foreign_chunk_set":
        objects[chunk_key].chunk_set_id = "foreign"
    elif mutation == "changed_source":
        objects[DocumentVersionTable, generation.document_version_id].raw_sha256 = "0" * 64
    elif mutation == "foreign_version":
        objects[DocumentVersionTable, generation.document_version_id].document_id = "foreign"
    elif mutation == "changed_profile":
        generations = (
            replace(generation, lexical_profile=replace(manifest.profile, avg_len=1)),
            *generations[1:],
        )
    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        validate_population_in_transaction(session, "workspace", generations, manifest)
