import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from evals.runners.ragas_review import (
    KnoraRagasLLM,
    RagasDraftError,
    build_review_packet,
    generate_review_packet,
    load_approved_chunks,
    load_approved_pdf_chunks,
    noise_sensitivity_readiness,
    write_review_packet,
)
from pydantic import BaseModel

CORPUS = Path(__file__).resolve().parents[1] / "corpora/milestone_1/manifest.json"


class MockProvider:
    def __init__(self, output):
        self.output = output
        self.prompts = []

    def generate(self, prompt: str, schema: type[BaseModel]):
        self.prompts.append(prompt)
        return schema.model_validate(self.output)


def _candidate(chunks):
    first, second = chunks[:2]
    return {
        "language": "en",
        "question": "How do the two policies interact?",
        "reference_answer": "The first policy requires one step, and the second another.",
        "hops": [
            {
                "chunk_ref": first["chunk_ref"],
                "quote": first["content"].split(".")[0] + ".",
                "necessary_claim": "The first step comes from this policy.",
            },
            {
                "chunk_ref": second["chunk_ref"],
                "quote": second["content"].split(".")[0] + ".",
                "necessary_claim": "The second step comes from this policy.",
            },
        ],
    }


def test_approved_source_export_reuses_manifest_and_chunk_identity() -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    assert (
        identity["manifest_sha256"] == "sha256:" + hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    )
    assert identity["workspace_id"] == "evaluation-m1-r2"
    assert {chunk["chunk_ref"] for chunk in chunks} == {
        "support/account-security#0",
        "support/refund-policy#0",
    }
    assert all(
        chunk["content_sha256"] == hashlib.sha256(chunk["content"].encode()).hexdigest()
        for chunk in chunks
    )
    assert all(":L" in chunk["locator"] for chunk in chunks)


def test_source_export_rejects_unapproved_source_and_stale_chunk_mapping(tmp_path) -> None:
    with pytest.raises(RagasDraftError, match="SOURCE_NOT_APPROVED"):
        load_approved_chunks(CORPUS, approved_source_keys=("missing",))
    original = json.loads(CORPUS.read_text())
    original["documents"][0]["expected_chunk_references"] = ["wrong#0"]
    copied = tmp_path / "manifest.json"
    copied.write_text(json.dumps(original), encoding="utf-8")
    for document in json.loads(CORPUS.read_text())["documents"]:
        (tmp_path / document["path"]).write_bytes((CORPUS.parent / document["path"]).read_bytes())
    with pytest.raises(RagasDraftError, match="CHUNK_MAPPING_MISMATCH"):
        load_approved_chunks(copied, approved_source_keys=("support/account-security",))


def test_actual_ragas_prompt_uses_explicit_mock_provider_and_returns_pending_packet() -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    provider = MockProvider({"drafts": [_candidate(chunks)]})
    packet = asyncio.run(
        generate_review_packet(
            chunks,
            identity,
            provider=provider,
            approval={
                "ragas_generation_approved": True,
                "data_classification": "synthetic",
                "egress_approved": True,
                "manifest_sha256": identity["manifest_sha256"],
                "source_export_sha256": identity["source_export_sha256"],
                "approved_source_keys": identity["approved_source_keys"],
                "model": "mock-model",
            },
            model="mock-model",
            prompt_version="ragas-review-v1",
            language="en",
            count=1,
        )
    )
    assert packet["generator"] == {
        "origin": "ragas_pydantic_prompt",
        "library": "ragas",
        "version": "0.4.3",
        "ragas_llm": "KnoraRagasLLM",
        "model": "mock-model",
        "prompt_version": "ragas-review-v1",
    }
    assert packet["drafts"][0]["review_status"] == "pending_owner_review"
    assert (
        packet["drafts"][0]["proposed_necessary_hops"][0]["content_sha256"]
        == chunks[0]["content_sha256"]
    )
    assert packet["drafts"][0]["proposed_necessary_hops"][0]["locator"] == chunks[0]["locator"]
    assert packet["release_gate"] is False
    assert "support/account-security#0" in provider.prompts[0]
    assert "How do the two policies interact?" not in provider.prompts[0]


def test_generation_rejects_missing_or_mismatched_approval_before_provider_call() -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    provider = MockProvider({"drafts": [_candidate(chunks)]})
    with pytest.raises(RagasDraftError, match="GENERATION_NOT_APPROVED"):
        asyncio.run(
            generate_review_packet(
                chunks,
                identity,
                provider=provider,
                approval={"ragas_generation_approved": True, "data_classification": "private"},
                model="mock-model",
                prompt_version="v1",
                language="en",
                count=1,
            )
        )
    assert provider.prompts == []


def test_generation_approval_binds_selected_sources_before_provider_call() -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    provider = MockProvider({"drafts": [_candidate(chunks)]})
    with pytest.raises(RagasDraftError, match="GENERATION_NOT_APPROVED"):
        asyncio.run(
            generate_review_packet(
                chunks,
                identity,
                provider=provider,
                approval={
                    "ragas_generation_approved": True,
                    "data_classification": "synthetic",
                    "egress_approved": True,
                    "manifest_sha256": identity["manifest_sha256"],
                    "source_export_sha256": identity["source_export_sha256"],
                    "approved_source_keys": ["support/account-security"],
                    "model": "mock-model",
                },
                model="mock-model",
                prompt_version="v1",
                language="en",
                count=1,
            )
        )
    assert provider.prompts == []


def test_generation_rejects_tampered_source_export_before_provider_call() -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    provider = MockProvider({"drafts": [_candidate(chunks)]})
    chunks[0]["content"] = "private data"
    with pytest.raises(RagasDraftError, match="SOURCE_EXPORT_MISMATCH"):
        asyncio.run(
            generate_review_packet(
                chunks,
                identity,
                provider=provider,
                approval={
                    "ragas_generation_approved": True,
                    "data_classification": "synthetic",
                    "egress_approved": True,
                    "manifest_sha256": identity["manifest_sha256"],
                    "source_export_sha256": identity["source_export_sha256"],
                    "approved_source_keys": identity["approved_source_keys"],
                    "model": "mock-model",
                },
                model="mock-model",
                prompt_version="v1",
                language="en",
                count=1,
            )
        )
    assert provider.prompts == []


@pytest.mark.parametrize("mutation", ("unknown_ref", "wrong_quote", "single_hop", "same_ref"))
def test_review_packet_rejects_unmapped_or_unsupported_hops(mutation) -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    candidate = _candidate(chunks)
    if mutation == "unknown_ref":
        candidate["hops"][0]["chunk_ref"] = "unknown#0"
    elif mutation == "wrong_quote":
        candidate["hops"][0]["quote"] = "Invented evidence."
    elif mutation == "single_hop":
        candidate["hops"] = candidate["hops"][:1]
    else:
        candidate["hops"][1]["chunk_ref"] = candidate["hops"][0]["chunk_ref"]
    with pytest.raises(RagasDraftError, match="(EVIDENCE|MULTIHOP)"):
        build_review_packet([candidate], chunks, identity, model="mock", prompt_version="v1")


def test_packet_cap_language_and_immutable_local_output(tmp_path) -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    with pytest.raises(RagasDraftError, match="DRAFT_LIMIT"):
        build_review_packet(
            [_candidate(chunks)] * 13, chunks, identity, model="mock", prompt_version="v1"
        )
    candidate = _candidate(chunks)
    candidate["language"] = "fr"
    with pytest.raises(RagasDraftError, match="LANGUAGE"):
        build_review_packet([candidate], chunks, identity, model="mock", prompt_version="v1")
    packet = build_review_packet(
        [_candidate(chunks)], chunks, identity, model="mock", prompt_version="v1"
    )
    path = tmp_path / "review.json"
    write_review_packet(path, packet)
    assert (
        json.loads(path.read_text(encoding="utf-8"))["drafts"][0]["review_status"]
        == "pending_owner_review"
    )
    with pytest.raises(FileExistsError):
        write_review_packet(path, packet)


@pytest.mark.parametrize(
    "model,prompt_version", (("", "v1"), ("mock", " "), (" ", "v1"), ("mock", ""))
)
def test_packet_rejects_blank_declared_provenance(model, prompt_version) -> None:
    chunks, identity = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    with pytest.raises(RagasDraftError, match="GENERATOR_PROVENANCE_MISSING"):
        build_review_packet(
            [_candidate(chunks)], chunks, identity, model=model, prompt_version=prompt_version
        )


def test_noise_sensitivity_requires_full_retrieval_and_suitable_judge() -> None:
    capture = {
        "question": "What happened?",
        "reference_answer": "A happened.",
        "answer": "A happened.",
        "generation_evidence": [{"content": "A happened."}],
        "generation_evidence_status": "exact",
    }
    assert noise_sensitivity_readiness(capture, judge=None)["status"] == "unavailable"
    assert (
        noise_sensitivity_readiness(capture, judge=KnoraRagasLLM(MockProvider({})))["status"]
        == "unavailable"
    )
    capture["retrieved_contexts"] = ["A happened.", "Unrelated context."]
    capture["retrieved_contexts_status"] = "complete"
    assert noise_sensitivity_readiness(capture, judge=None)["status"] == "unavailable"
    assert (
        noise_sensitivity_readiness(capture, judge=KnoraRagasLLM(MockProvider({})))["status"]
        == "ready_experimental"
    )


def test_local_cli_builds_pending_packet_without_provider(tmp_path, monkeypatch) -> None:
    from evals.runners.ragas_review import main

    chunks, _ = load_approved_chunks(
        CORPUS, approved_source_keys=("support/account-security", "support/refund-policy")
    )
    candidate_path = tmp_path / "candidates.json"
    candidate_path.write_text(json.dumps([_candidate(chunks)]), encoding="utf-8")
    output = tmp_path / "packet.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ragas-review",
            "--manifest",
            str(CORPUS),
            "--source-key",
            "support/account-security",
            "--source-key",
            "support/refund-policy",
            "--candidates",
            str(candidate_path),
            "--output",
            str(output),
            "--model",
            "mock-model",
            "--prompt-version",
            "ragas-review-v1",
        ],
    )
    main()
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["release_gate"] is False
    assert packet["generator"] == {
        "origin": "imported_candidates",
        "declared_model": "mock-model",
        "declared_prompt_version": "ragas-review-v1",
    }


def test_approved_pdf_chunks_export_from_153() -> None:
    chunks_path = (
        Path(__file__).resolve().parents[1]
        / "reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime/chunks.json"
    )
    chunks, identity = load_approved_pdf_chunks(
        chunks_path, approved_source_keys=("academic-phonlp", "hierarchy-03")
    )
    assert len(chunks) == 13 + 2  # 13 phonlp + 2 hierarchy-03
    assert identity["approved_source_keys"] == ["academic-phonlp", "hierarchy-03"]
    assert all(":p" in c["locator"] for c in chunks)
    assert all(c["chunk_ref"].startswith(c["source_key"] + "#") for c in chunks)
    assert all(
        c["content_sha256"] == hashlib.sha256(c["content"].encode("utf-8")).hexdigest()
        for c in chunks
    )

    with pytest.raises(RagasDraftError, match="SOURCE_NOT_APPROVED"):
        load_approved_pdf_chunks(chunks_path, approved_source_keys=("missing-source",))
