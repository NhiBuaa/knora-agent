"""Restore metadata from retained chunks without extracting or changing their identities."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from backend.runtime_test import s2_frozen_restore


def test_frozen47_metadata_is_complete_and_preserves_every_saved_field():
    path = Path("evals/reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime/chunks.json")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "146109370459186ef0d46e49e0165e1184ec719fe8a61a6b9cd55156e0b256f9"
    )
    chunks = json.loads(path.read_text(encoding="utf-8"))["chunks"]
    restored = s2_frozen_restore.frozen_chunk_metadata(chunks)
    assert len(restored) == 47
    assert {row["chunk_id"] for row in restored} == {row["chunk_id"] for row in chunks}
    for original in chunks:
        row = next(row for row in restored if row["chunk_id"] == original["chunk_id"])
        assert all(row[key] == value for key, value in original.items())
        assert row["token_count"] > 0
        assert 1 <= row["start_line"] <= row["end_line"]
    for chunk_set in {row["chunk_set_id"] for row in restored}:
        ordinals = [row["ordinal"] for row in restored if row["chunk_set_id"] == chunk_set]
        assert ordinals == list(range(len(ordinals)))


def test_all60_input_packet_preserves_approved_selection_and_missing_anchors():
    dataset, chunks, bindings, baseline, protected = s2_frozen_restore.load_frozen_inputs()
    assert len(dataset.cases) == len(baseline) == 60
    assert len(chunks) == 47
    assert sum(bool(ids) for ids in bindings.values()) == 61
    assert sum(not ids for ids in bindings.values()) == 25
    assert len(protected) == 206
    assert all(row["failure_code"] is None for row in baseline)


def test_real_all60_frozen_queries_validate_before_unresolved_last_dispatch(tmp_path):
    from evals.runners.pdf_retrieval_v3 import collect_bm25_cases

    from knora.answering.stores import RetrievalConfiguration

    dataset, _, _, baseline, _ = s2_frozen_restore.load_frozen_inputs()
    last = dataset.cases[-1]
    (tmp_path / f"dispatch-{last.id}-attempt-1.json").write_text("{}", encoding="utf-8")
    store = Mock()
    with pytest.raises(ValueError, match="unresolved dispatch"):
        collect_bm25_cases(
            dataset,
            store,
            baseline,
            tmp_path,
            run_id="offline-input-validation",
            workspace_id="offline",
            configuration=RetrievalConfiguration.bm25_top8_v1(),
            derivation_sha256="fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2",
        )
    store.retrieve_candidates.assert_not_called()
    assert len(list(tmp_path.iterdir())) == 1


def test_changed_archive_cannot_authorize_changed_follow_up_context(monkeypatch):
    root = Path("evals/reports/pdf_retrieval_v3_v1/baseline-b-layout-v2-continuation")
    case_path = root / "captures/case-pdf-v3-029-attempt-1.json"
    archive_path = root / "archive-manifest.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["provider_metadata"]["conversation_context"]["retrieval_query"] = (
        "Foreign context\nCurrent question: "
        + case["provider_metadata"]["conversation_context"]["retrieval_query"].split(
            "Current question: "
        )[-1]
    )
    altered_case = (json.dumps(case, ensure_ascii=False, indent=2) + "\n").encode()
    archive = json.loads(archive_path.read_text(encoding="utf-8"))
    for entry in archive["files"]:
        if entry["path"] == "captures/case-pdf-v3-029-attempt-1.json":
            entry["sha256"] = hashlib.sha256(altered_case).hexdigest()
    altered = {
        case_path.resolve(): altered_case,
        archive_path.resolve(): (json.dumps(archive, indent=2) + "\n").encode(),
    }
    read_bytes, read_text = Path.read_bytes, Path.read_text
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: altered.get(path.resolve()) if path.resolve() in altered else read_bytes(path),
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, **kwargs: (
            altered[path.resolve()].decode()
            if path.resolve() in altered
            else read_text(path, **kwargs)
        ),
    )
    with pytest.raises(ValueError, match="frozen Baseline B archive"):
        s2_frozen_restore.load_frozen_inputs()


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "document_version_id",
        "parser_configuration_id",
        "normalizer_configuration_id",
        "chunking_configuration_id",
        "status",
    ],
)
def test_changed_restore_chunk_set_lineage_is_rejected(field):
    frozen = {
        "chunk_set_id": "set",
        "document_version_id": "version",
        "parser_configuration_id": "parser",
        "normalizer_configuration_id": "normalizer",
        "chunking_configuration_id": "config",
    }
    row = SimpleNamespace(
        id="set",
        document_version_id="version",
        parser_configuration_id="parser",
        normalizer_configuration_id="normalizer",
        chunking_configuration_id="config",
        status="completed",
    )
    setattr(row, field, "changed")
    with pytest.raises(ValueError, match="chunk set lineage"):
        s2_frozen_restore.require_frozen_chunk_set(row, frozen)


@pytest.mark.parametrize("fault", ["checksum", "prefix", "overlap"])
def test_restore_rejects_unprovable_page_prefix_or_changed_content(fault):
    row = {
        "chunk_id": "one",
        "chunk_set_id": "set",
        "page_start": 1,
        "page_end": 1,
        "start_offset": 0,
        "end_offset": 3,
        "content": "abc",
        "content_checksum": hashlib.sha256(b"abc").hexdigest(),
    }
    chunks = [row]
    if fault == "checksum":
        row["content"] = "def"
    elif fault == "prefix":
        row.update(start_offset=1, end_offset=4)
    else:
        chunks.append(
            {
                **row,
                "chunk_id": "two",
                "content": "def",
                "content_checksum": hashlib.sha256(b"def").hexdigest(),
            }
        )
    with pytest.raises(ValueError):
        s2_frozen_restore.frozen_chunk_metadata(chunks)
