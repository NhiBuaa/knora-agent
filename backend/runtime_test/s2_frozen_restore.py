"""Owned S2 frozen restore helpers; importing this module performs no I/O."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import tiktoken

from knora.adapters.pdf._pypdf_chunking import _encode
from knora.ingestion.pdf import PdfExtractionConfiguration


def require_frozen_chunk_bytes(raw: bytes) -> None:
    # Pin both the historical CRLF artifact and its exact LF Git blob, without normalizing input.
    if hashlib.sha256(raw).hexdigest() not in {
        "146109370459186ef0d46e49e0165e1184ec719fe8a61a6b9cd55156e0b256f9",
        "46093ced1a44ce05c7b7b67c95d5dde487bec11529d57ff3e01b7bd7627ff918",
    }:
        raise ValueError("frozen chunk bytes changed")


def frozen_chunk_metadata(chunks):
    """Recover production ordinals, token counts and line numbers from complete page prefixes."""
    if len({row["chunk_id"] for row in chunks}) != len(chunks):
        raise ValueError("duplicate frozen chunk identity")
    ordered = sorted(
        chunks,
        key=lambda row: (
            row["chunk_set_id"],
            row["page_start"],
            row["start_offset"],
            row["end_offset"],
        ),
    )
    pages = {}
    ordinals = defaultdict(int)
    tokenizer = tiktoken.get_encoding(PdfExtractionConfiguration.layout_preserving().tokenizer_name)
    restored = []
    for row in ordered:
        start, end, content = row["start_offset"], row["end_offset"], row["content"]
        if (
            row["page_start"] != row["page_end"]
            or not 0 <= start < end
            or len(content) != end - start
            or hashlib.sha256(content.encode()).hexdigest() != row["content_checksum"]
        ):
            raise ValueError("invalid frozen page range or checksum")
        key = (row["chunk_set_id"], row["page_start"])
        prefix = pages.get(key, "")
        if start > len(prefix):
            raise ValueError("unobserved page prefix; line numbers cannot be proved")
        overlap = min(len(prefix), end) - start
        if prefix[start : start + overlap] != content[:overlap]:
            raise ValueError("inconsistent overlapping frozen text")
        page = prefix + content[overlap:]
        pages[key] = page
        restored.append(
            {
                **row,
                "ordinal": ordinals[row["chunk_set_id"]],
                "token_count": len(_encode(tokenizer, content)),
                "start_line": page.count("\n", 0, start) + 1,
                "end_line": page.count("\n", 0, end) + 1,
            }
        )
        ordinals[row["chunk_set_id"]] += 1
    return restored


def load_frozen_inputs():
    """Read the approved packet and every protected byte before any runtime mutation."""
    from evals.datasets.pdf_retrieval_v3_v1 import load_dataset, validate_approval
    from evals.runners.pdf_source_binding import digest, propose_bindings, validate_binding_review

    binding = Path("evals/reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime")
    baseline = binding.with_name("baseline-b-layout-v2-continuation")
    manifest = Path("evals/datasets/pdf_retrieval_v3_v1.manifest.json")
    gold = manifest.with_name("pdf_retrieval_v3_v1.jsonl")
    approval = manifest.with_name("pdf_retrieval_v3_v1.approval.json")

    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(baseline / "archive-manifest.json") != (
        "f30a7125d7c7acb7a65af50c18c2c375fbabfee5828114ffadb8860b869629f6"
    ):
        raise ValueError("frozen Baseline B archive manifest changed")
    archive = read(baseline / "archive-manifest.json")["files"]
    paths = [
        manifest,
        gold,
        approval,
        binding / "chunks.json",
        binding / "proposals.json",
        binding / "binding-review.json",
        baseline / "archive-manifest.json",
        baseline / "candidate-vs-selected-coverage.json",
        baseline / "report.json",
        baseline / "revalidation-selection.json",
    ]
    paths.extend(baseline / entry["path"] for entry in archive)
    protected = {str(path): sha(path) for path in paths}
    for entry in archive:
        if sha(baseline / entry["path"]) != entry["sha256"]:
            raise ValueError("frozen Baseline B archive changed")
    dataset = load_dataset(manifest, gold)
    validate_approval(dataset, read(approval))
    protected.update({str(source.path): sha(source.path) for source in dataset.sources})
    if (dataset.corpus_sha256, dataset.dataset_sha256) != (
        "c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0",
        "2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae",
    ):
        raise ValueError("frozen dataset identity changed")
    require_frozen_chunk_bytes((binding / "chunks.json").read_bytes())
    chunks = read(binding / "chunks.json")["chunks"]
    proposal = propose_bindings(dataset, [SimpleNamespace(**row) for row in chunks])
    review = read(binding / "binding-review.json")
    if proposal != read(binding / "proposals.json") or digest(review) != (
        "7d7efbb47e548392eca3846a576552d238eb850f862bda7f9e16f7dc7bfb3288"
    ):
        raise ValueError("approved source bindings changed")
    bindings = validate_binding_review(proposal, review)
    selection = read(baseline / "revalidation-selection.json")
    if (
        digest(selection) != ("c11b02c68114e5c1d65678c5d25cb35af9eaff4069d8841969d0c8fe02d6c799")
        or digest(selection["observation"]) != selection["observation_sha256"]
    ):
        raise ValueError("approved B attempt selection changed")
    original = baseline / "captures/case-pdf-v3-001-attempt-1.json"
    if sha(original) != selection["original_capture_sha256"]:
        raise ValueError("original failed B attempt changed")
    observations = [read(path) for path in sorted((baseline / "captures").glob("case-*.json"))]
    observations = [
        selection["observation"] if row["case_id"] == "pdf-v3-001" else row for row in observations
    ]
    if (
        len(observations) != 60
        or {row["case_id"] for row in observations} != {case.id for case in dataset.cases}
        or any(
            row["failure_code"] or digest(row["public_response"]) != row["response_sha256"]
            for row in observations
        )
    ):
        raise ValueError("selected frozen B observations are incomplete")
    return dataset, frozen_chunk_metadata(chunks), bindings, observations, protected


def require_frozen_chunk_set(row, frozen):
    expected = {
        "id": frozen["chunk_set_id"],
        "document_version_id": frozen["document_version_id"],
        "chunking_configuration_id": frozen["chunking_configuration_id"],
        "parser_configuration_id": frozen["parser_configuration_id"],
        "normalizer_configuration_id": frozen["normalizer_configuration_id"],
        "status": "completed",
    }
    if row is None or any(getattr(row, key) != value for key, value in expected.items()):
        raise ValueError("restored chunk set lineage changed")


def restore_frozen_population(session_factory, dataset, chunks, object_root):
    """Restore retained identities only into the owned DB; never repair an existing mismatch."""
    from backend.runtime_test.s2_runtime_guard import require_owned_s2_database
    from sqlalchemy import select

    from knora.adapters.postgres.tables import (
        ChunkingConfigurationTable,
        ChunkSetTable,
        ChunkTable,
        DocumentTable,
        DocumentVersionTable,
        OriginalSourceObjectTable,
        WorkspaceTable,
    )

    require_owned_s2_database(session_factory.kw["bind"].url)
    workspace_ids = {row["workspace_id"] for row in chunks}
    assert len(workspace_ids) == 1
    workspace_id = next(iter(workspace_ids))
    config = PdfExtractionConfiguration.layout_preserving()
    config_id = "chunking-m2-pdf-pypdf-6-14-2-layout-v2"
    expected_config = {
        "id": config_id,
        "parser_version": config.parser_version,
        "chunker_version": config.chunking_policy_version,
        "tokenizer_name": config.tokenizer_name,
        "tokenizer_version": config.tokenizer_version,
        "target_tokens": config.target_tokens,
        "overlap_tokens": config.overlap_tokens,
        "max_tokens": config.max_tokens,
    }
    by_source = defaultdict(list)
    for chunk in chunks:
        by_source[chunk["source_key"]].append(chunk)
    # Source bytes are retained separately; neither PDF extraction nor embedding runs here.
    for source in dataset.sources:
        data = source.path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == source.sha256
        target = object_root / "s2-frozen" / source.sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == data
        else:
            with target.open("xb") as stream:
                stream.write(data)
    with session_factory.begin() as session:
        workspace = session.get(WorkspaceTable, workspace_id)
        fresh = workspace is None
        if fresh:
            workspace = WorkspaceTable(id=workspace_id, name="S2 frozen47 identity restore")
            session.add(workspace)
            session.flush()
        assert workspace.name == "S2 frozen47 identity restore" and not workspace.archived
        assert workspace.revision == 0
        stored_config = session.get(ChunkingConfigurationTable, config_id)
        if stored_config is None:
            assert fresh, "existing restore configuration is missing; never repair it"
            session.add(ChunkingConfigurationTable(**expected_config))
            session.flush()
        else:
            assert all(
                getattr(stored_config, key) == value for key, value in expected_config.items()
            )
        documents = {}
        for source in dataset.sources:
            rows = by_source[source.id]
            # The approved serving manifest contains14 represented sources, not empty derivations.
            if not rows:
                continue
            document = session.scalar(
                select(DocumentTable).where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.source_key == source.id,
                )
            )
            if fresh:
                assert document is None
                document = DocumentTable(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    source_key=source.id,
                    source_name=source.path.name,
                )
                session.add(document)
                session.flush()
                version_id = rows[0]["document_version_id"]
                assert session.get(DocumentVersionTable, version_id) is None
                session.add(
                    DocumentVersionTable(
                        id=version_id,
                        document_id=document.id,
                        raw_sha256=source.sha256,
                        media_type="application/pdf",
                        version_number=1,
                    )
                )
                session.flush()
                document.current_document_version_id = version_id
                session.add(
                    OriginalSourceObjectTable(
                        id=str(uuid4()),
                        workspace_id=workspace_id,
                        document_version_id=version_id,
                        object_key="s2-frozen/" + source.sha256,
                        raw_sha256=source.sha256,
                        byte_size=source.path.stat().st_size,
                        media_type="application/pdf",
                    )
                )
                if rows:
                    session.add(
                        ChunkSetTable(
                            id=rows[0]["chunk_set_id"],
                            document_version_id=version_id,
                            chunking_configuration_id=config_id,
                            parser_configuration_id=rows[0]["parser_configuration_id"],
                            normalizer_configuration_id=rows[0]["normalizer_configuration_id"],
                            status="completed",
                        )
                    )
                    session.flush()
                    for row in rows:
                        session.add(
                            ChunkTable(
                                id=row["chunk_id"],
                                chunk_set_id=row["chunk_set_id"],
                                heading_path=[],
                                **{
                                    key: row[key]
                                    for key in (
                                        "ordinal",
                                        "start_line",
                                        "end_line",
                                        "content",
                                        "content_checksum",
                                        "token_count",
                                        "page_start",
                                        "page_end",
                                        "start_offset",
                                        "end_offset",
                                    )
                                },
                            )
                        )
            assert document is not None and not document.archived and document.revision == 0
            version = session.get(DocumentVersionTable, document.current_document_version_id)
            assert version.raw_sha256 == source.sha256 and version.document_id == document.id
            source_object = session.scalar(
                select(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.document_version_id == version.id
                )
            )
            assert source_object is not None and source_object.deleted_at is None
            assert source_object.object_key == "s2-frozen/" + source.sha256
            assert (
                source_object.workspace_id,
                source_object.raw_sha256,
                source_object.byte_size,
            ) == (workspace_id, source.sha256, source.path.stat().st_size)
            if rows:
                assert version.id == rows[0]["document_version_id"]
                chunk_set = session.get(ChunkSetTable, rows[0]["chunk_set_id"])
                require_frozen_chunk_set(chunk_set, rows[0])
            documents[source.id] = document.id
        session.flush()
        assert (
            len(
                session.scalars(
                    select(DocumentTable.id).where(DocumentTable.workspace_id == workspace_id)
                ).all()
            )
            == len(documents)
            == 14
        )
        actual = session.scalars(
            select(ChunkTable)
            .join(ChunkSetTable, ChunkTable.chunk_set_id == ChunkSetTable.id)
            .join(
                DocumentVersionTable, ChunkSetTable.document_version_id == DocumentVersionTable.id
            )
            .join(DocumentTable, DocumentVersionTable.document_id == DocumentTable.id)
            .where(DocumentTable.workspace_id == workspace_id)
        ).all()
        assert len(actual) == len(chunks) == 47
        expected = {row["chunk_id"]: row for row in chunks}
        for row in actual:
            assert row.id in expected
            pin = expected[row.id]
            assert row.heading_path == []
            assert all(
                getattr(row, key) == pin[key]
                for key in (
                    "chunk_set_id",
                    "ordinal",
                    "start_line",
                    "end_line",
                    "content",
                    "content_checksum",
                    "token_count",
                    "page_start",
                    "page_end",
                    "start_offset",
                    "end_offset",
                )
            )
    return workspace_id, documents
