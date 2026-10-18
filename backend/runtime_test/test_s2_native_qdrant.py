"""Bounded structural checks against the owned, pinned Qdrant service."""

import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import AuthorizedLexicalSnapshot, QdrantSearchIndex
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration, LexicalProfile


@pytest.fixture(scope="module")
def native(request):
    assert os.environ.get("KNORA_S2_ISOLATED_TESTS") == "1", "owned S2 runtime required"
    run_id = uuid4().hex
    artifact_root = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"])
    artifact_root.mkdir(parents=True, exist_ok=True)
    calls = []

    def retain():
        (artifact_root / (run_id + ".json")).write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "scope": "structural fixtures only, not the 60-case evaluation",
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "calls": calls,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    request.addfinalizer(retain)

    def capture(response):
        response.read()
        assert response.request.url.host == "127.0.0.1"
        assert response.request.url.port == 16433
        assert len(calls) < 100, "structural run call budget exceeded"
        calls.append(
            {
                "method": response.request.method,
                "url": str(response.request.url),
                "request": json.loads(response.request.content)
                if response.request.content
                else None,
                "status": response.status_code,
                "response": response.json(),
            }
        )

    profile = LexicalProfile(
        "structural-word-v1", "word", "qdrant-1.19.2", 1.2, 0.75, 3, "three-token-fixtures"
    )
    index = QdrantSearchIndex("s2_structural_" + run_id, profile)
    with httpx.Client(
        base_url="http://127.0.0.1:16433",
        timeout=10,
        trust_env=False,
        event_hooks={"response": [capture]},
    ) as client:
        assert client.get("/").json()["version"] == "1.19.2"
        port = NativeQdrantSearchIndex(index=index, client=client)
        port.ensure_collection()
        generations = []
        for label, workspace, text in (
            ("current", "owner", "HẠN MỨC 42"),
            ("other", "owner", "ＰＤＦ bản_001"),
            ("foreign", "foreign", "HẠN MỨC 42"),
            ("revoked", "owner", "HẠN MỨC 42"),
        ):
            checksum = hashlib.sha256(text.encode()).hexdigest()
            generation = LexicalGeneration(
                run_id + label,
                workspace,
                label,
                label + "-version",
                label + "-chunks",
                profile,
                1,
                (LexicalChunk(label, 0, checksum),),
            )
            receipt = port.stage_generation(generation, {label: text})
            receipt.validate(generation)
            generations.append(generation)
        snapshot = AuthorizedLexicalSnapshot(
            "owner", tuple(g.generation_id for g in generations[:2]), profile.id, profile.digest()
        )
        # Retain collections and failed setup responses for review; never overwrite a run.
        yield port, snapshot, client, generations


def test_native_keyword_scope_excludes_foreign_and_revoked_points(native):
    port, snapshot, _, _ = native
    hits = port.query(snapshot, "HẠN MỨC 42")
    assert [hit["chunk_id"] for hit in hits] == ["current"]
    assert all(hit["score_policy_digest"] == port.index.profile.digest() for hit in hits)


def test_idf_uses_only_authorized_population(native):
    port, snapshot, _, _ = native
    hits = port.query(snapshot, "42")
    assert [hit["chunk_id"] for hit in hits] == ["current"]
    # N=2, n=1, tf=1, document length=avg_len=3: weight=1 and IDF=ln(2).
    assert hits[0]["score"] == pytest.approx(math.log(2), rel=1e-5)


@pytest.mark.parametrize(
    "query,expected",
    [("hạn", ["current"]), ("han", []), ("001", ["other"]), ("PDF", ["other"]), ("...", [])],
)
def test_native_word_options_preserve_accents_digits_and_normalization(native, query, expected):
    port, snapshot, _, _ = native
    assert [hit["chunk_id"] for hit in port.query(snapshot, query)] == expected


def test_native_vectors_match_three_retained_tokens(native):
    port, _, client, generations = native
    response = client.post(
        f"/collections/{port.index.collection_name}/points",
        json={
            "ids": list(generations[0].point_ids()),
            "with_vector": True,
            "with_payload": False,
        },
    )
    response.raise_for_status()
    vector = response.json()["result"][0]["vector"]["bm25"]
    assert len(vector["indices"]) == 3
    assert len(set(vector["indices"])) == 3
    assert vector["values"] == pytest.approx([1, 1, 1], rel=1e-5)
