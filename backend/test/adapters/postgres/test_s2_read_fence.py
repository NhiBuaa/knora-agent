"""Lexical eligibility checks against retained ORM records, without a live database."""

from contextlib import nullcontext
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
import test_s2_generation_loading as generation_loading

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.answering.stores import LexicalGeneration, QuestionTraceRecord
from knora.domain.errors import KnoraError

snapshot = generation_loading.snapshot


def _active(snapshot):
    rows = snapshot.rows
    rows.generation.status = "active"
    rows.generation.acknowledged_count = 1
    rows.head.active_generation_id = "generation"
    return LexicalGeneration("workspace", "document", "version", "chunks", "generation", "profile")


def test_consistent_projection_snapshot_reads_the_same_active_authority(snapshot):
    _active(snapshot)
    generation = snapshot.store.read_active_generation_in_snapshot(
        snapshot.session, "workspace", "document", "profile"
    )
    assert (generation.generation_id, generation.document_version_id, generation.chunk_set_id) == (
        "generation",
        "version",
        "chunks",
    )


def test_consistent_projection_snapshot_cannot_claim_ready_after_archive(snapshot):
    _active(snapshot)
    snapshot.rows.document.archived = True
    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        snapshot.store.read_active_generation_in_snapshot(
            snapshot.session, "workspace", "document", "profile"
        )


@pytest.mark.parametrize(
    "drift",
    [
        "workspace_archive",
        "document_archive",
        "workspace_revision",
        "source_revision",
        "source_version",
        "revoked",
        "active_pointer",
        "receipt",
        "profile",
        "foreign",
        "chunk_set",
        "manifest",
        "missing_generation",
    ],
)
def test_snapshot_revalidation_denies_invalidated_authority(snapshot, drift):
    generation = _active(snapshot)
    rows = snapshot.rows
    if drift == "workspace_archive":
        rows.workspace.archived = True
    elif drift == "document_archive":
        rows.document.archived = True
    elif drift == "workspace_revision":
        rows.workspace.revision += 1
    elif drift == "source_revision":
        rows.document.revision += 1
    elif drift == "source_version":
        rows.document.current_document_version_id = "new-version"
    elif drift == "revoked":
        rows.generation.status = "revoked"
    elif drift == "active_pointer":
        rows.head.active_generation_id = "replacement"
    elif drift == "receipt":
        rows.generation.acknowledged_count = 0
    elif drift == "profile":
        rows.generation.profile_digest = "changed"
    elif drift == "foreign":
        generation = replace(generation, workspace_id="foreign")
    elif drift == "chunk_set":
        rows.chunk_set.status = "processing"
    elif drift == "manifest":
        rows.generation.manifest["lexical_profile"]["b"] = 0.5
    else:
        snapshot.session.rows.pop((type(rows.generation), rows.generation.id))
    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        snapshot.store.revalidate_lexical_snapshot_in_transaction(
            snapshot.session, "workspace", "profile", (generation,)
        )


def test_same_version_profile_rebuild_keeps_still_active_snapshot_eligible(snapshot):
    generation = _active(snapshot)
    snapshot.rows.head.revision += 1
    snapshot.rows.head.desired_generation_id = "new-desired-generation"
    snapshot.store.revalidate_lexical_snapshot_in_transaction(
        snapshot.session, "workspace", "profile", (generation,)
    )


def _trace(generation):
    return QuestionTraceRecord(
        workspace_id="workspace",
        question="Fact?",
        retrieval_configuration_id="bm25",
        embedding_configuration_id=None,
        candidate_decisions=(),
        retrieved_chunk_ids=(),
        embedding_set_ids=(),
        chunk_set_ids=("chunks",),
        decision="REFUSAL",
        answer=None,
        refusal_reason="INSUFFICIENT_EVIDENCE",
        generation_status="not_called",
        trace_schema_version=3,
        provider_metadata={
            "retrieval": {
                "mode": "bm25-only",
                "lexical_generations": [asdict(generation)],
            }
        },
    )


@pytest.mark.parametrize("drift", ["archive", "missing", "mode", "shape", "scalar", "non_string"])
def test_trace_transaction_rejects_invalid_snapshot_before_writing(snapshot, drift):
    generation = _active(snapshot)
    trace = _trace(generation)
    retrieval = trace.provider_metadata["retrieval"]
    if drift == "archive":
        snapshot.rows.document.archived = True
    elif drift == "missing":
        retrieval.pop("lexical_generations")
    elif drift == "mode":
        retrieval["mode"] = "dense"
    elif drift == "shape":
        retrieval["lexical_generations"][0]["unexpected"] = "field"
    elif drift == "scalar":
        retrieval["lexical_generations"] = ["not-an-object"]
    else:
        retrieval["lexical_generations"][0]["document_id"] = 42
    written = []
    snapshot.session.add = written.append
    store = PostgresAnsweringStore(SimpleNamespace(begin=lambda: nullcontext(snapshot.session)))
    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        store.persist_trace(trace)
    assert written == []
