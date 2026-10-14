"""Local owner-review packets from approved, versioned Knora source chunks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from evals.runners.evaluation import load_corpus_manifest, write_report_atomic
from pydantic import BaseModel, Field

from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor

os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from ragas.llms.base import InstructorBaseRagasLLM  # noqa: E402
from ragas.prompt import PydanticPrompt  # noqa: E402


class RagasDraftError(ValueError):
    pass


class SourceChunk(BaseModel):
    source_key: str
    chunk_ref: str
    content: str
    content_sha256: str
    locator: str


class DraftInput(BaseModel):
    language: Literal["en", "vi"]
    count: int = Field(ge=1, le=12)
    chunks: list[SourceChunk]


class ProposedHop(BaseModel):
    chunk_ref: str
    quote: str
    necessary_claim: str


class DraftCandidate(BaseModel):
    language: Literal["en", "vi"]
    question: str
    reference_answer: str
    hops: list[ProposedHop]


class DraftOutput(BaseModel):
    drafts: list[DraftCandidate]


class KnoraReviewPrompt(PydanticPrompt[DraftInput, DraftOutput]):
    input_model = DraftInput
    output_model = DraftOutput
    instruction = (
        "Draft document-grounded questions in the requested language. Use only supplied chunks. "
        "For each answer, propose two distinct necessary evidence steps, each with an exact "
        "quote and chunk_ref. Do not claim that a question is proven multi-hop. "
        "Return no more drafts than requested."
    )


class KnoraRagasLLM(InstructorBaseRagasLLM):
    """Adapt an explicitly supplied Knora schema-aware provider to Ragas prompts."""

    is_async = False

    def __init__(self, provider):
        self.provider = provider

    def generate(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        return self.provider.generate(prompt, schema=response_model)

    async def agenerate(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        if hasattr(self.provider, "a_generate"):
            return await self.provider.a_generate(prompt, schema=response_model)
        return await asyncio.to_thread(self.generate, prompt, response_model)


def _source_export_sha256(chunks: list[dict]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(chunks, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
    )


def _validate_source_export(chunks: list[dict], identity: dict) -> None:
    approved = identity.get("approved_source_keys", [])
    refs = [chunk.get("chunk_ref") for chunk in chunks]
    if (
        not chunks
        or len(refs) != len(set(refs))
        or any(
            chunk.get("source_key") not in approved
            or not isinstance(chunk.get("content"), str)
            or chunk.get("content_sha256")
            != hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
            or not str(chunk.get("chunk_ref", "")).startswith(chunk["source_key"] + "#")
            for chunk in chunks
        )
        or identity.get("source_export_sha256") != _source_export_sha256(chunks)
    ):
        raise RagasDraftError("SOURCE_EXPORT_MISMATCH")


def load_approved_chunks(
    manifest_path: Path, *, approved_source_keys: tuple[str, ...]
) -> tuple[list[dict], dict]:
    """Export existing M1 chunks while retaining their source identity and checksums."""
    if not approved_source_keys or len(set(approved_source_keys)) != len(approved_source_keys):
        raise RagasDraftError("SOURCE_NOT_APPROVED")
    manifest = load_corpus_manifest(manifest_path)
    configuration = ChunkingConfiguration.milestone_one()
    if manifest.chunking_configuration_id != configuration.id:
        raise RagasDraftError("CHUNKING_CONFIGURATION_UNSUPPORTED")
    selected = {
        item.source_key: item
        for item in manifest.documents
        if item.source_key in approved_source_keys
    }
    if set(selected) != set(approved_source_keys):
        raise RagasDraftError("SOURCE_NOT_APPROVED")
    processor = DocumentProcessor()
    chunks = []
    for source_key in approved_source_keys:
        document = selected[source_key]
        processed = processor.process(
            raw_content=document.path.read_bytes(),
            media_type="text/plain" if document.path.suffix == ".txt" else "text/markdown",
            configuration=configuration,
        )
        if processed.normalized_content_checksum != document.normalized_content_sha256:
            raise RagasDraftError("SOURCE_CHECKSUM_MISMATCH")
        refs = tuple(f"{source_key}#{chunk.ordinal}" for chunk in processed.chunks)
        if refs != document.expected_chunk_references:
            raise RagasDraftError("CHUNK_MAPPING_MISMATCH")
        chunks.extend(
            {
                "source_key": source_key,
                "chunk_ref": ref,
                "content": chunk.content,
                "content_sha256": chunk.content_checksum,
                "locator": f"{source_key}:L{chunk.start_line}-L{chunk.end_line}",
            }
            for ref, chunk in zip(refs, processed.chunks, strict=True)
        )
    identity = {
        "manifest_sha256": "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "corpus_version": manifest.version,
        "workspace_id": manifest.workspace_id,
        "chunking_configuration_id": manifest.chunking_configuration_id,
        "embedding_configuration_id": manifest.embedding_configuration_id,
        "approved_source_keys": list(approved_source_keys),
        "source_export_sha256": _source_export_sha256(chunks),
    }
    return chunks, identity


def build_review_packet(
    candidates: list[dict],
    chunks: list[dict],
    identity: dict,
    *,
    model: str,
    prompt_version: str,
) -> dict:
    _validate_source_export(chunks, identity)
    if not 1 <= len(candidates) <= 12:
        raise RagasDraftError("DRAFT_LIMIT")
    by_ref = {chunk["chunk_ref"]: chunk for chunk in chunks}
    drafts = []
    for index, raw in enumerate(candidates, start=1):
        try:
            candidate = DraftCandidate.model_validate(raw)
        except ValueError as error:
            raise RagasDraftError("DRAFT_LANGUAGE_OR_SCHEMA_INVALID") from error
        if not candidate.question.strip() or not candidate.reference_answer.strip():
            raise RagasDraftError("DRAFT_CONTENT_MISSING")
        if len(candidate.hops) < 2 or len({hop.chunk_ref for hop in candidate.hops}) < 2:
            raise RagasDraftError("MULTIHOP_EVIDENCE_INSUFFICIENT")
        hops = []
        for hop in candidate.hops:
            chunk = by_ref.get(hop.chunk_ref)
            if (
                chunk is None
                or not hop.quote.strip()
                or hop.quote not in chunk["content"]
                or not hop.necessary_claim.strip()
            ):
                raise RagasDraftError("EVIDENCE_UNSUPPORTED")
            hops.append(
                {
                    "chunk_ref": hop.chunk_ref,
                    "source_key": chunk["source_key"],
                    "quote": hop.quote,
                    "necessary_claim": hop.necessary_claim,
                    "content_sha256": chunk["content_sha256"],
                    "locator": chunk["locator"],
                }
            )
        drafts.append(
            {
                "draft_id": f"draft-{index:02d}",
                "language": candidate.language,
                "question": candidate.question,
                "reference_answer": candidate.reference_answer,
                "proposed_necessary_hops": hops,
                "review_status": "pending_owner_review",
            }
        )
    return {
        "schema_version": 1,
        "source": identity,
        "generator": {
            "library": "ragas",
            "version": "0.4.3",
            "model": model,
            "prompt_version": prompt_version,
            "ragas_llm": "KnoraRagasLLM",
        },
        "drafts": drafts,
        "release_gate": False,
    }


async def generate_review_packet(
    chunks: list[dict],
    identity: dict,
    *,
    provider,
    approval: dict,
    model: str,
    prompt_version: str,
    language: Literal["en", "vi"],
    count: int,
) -> dict:
    if (
        approval.get("ragas_generation_approved") is not True
        or approval.get("data_classification") not in {"public", "synthetic"}
        or approval.get("egress_approved") is not True
        or approval.get("manifest_sha256") != identity.get("manifest_sha256")
        or approval.get("source_export_sha256") != identity.get("source_export_sha256")
        or approval.get("approved_source_keys") != identity.get("approved_source_keys")
        or approval.get("model") != model
    ):
        raise RagasDraftError("GENERATION_NOT_APPROVED")
    if not 1 <= count <= 12:
        raise RagasDraftError("DRAFT_LIMIT")
    if not chunks or not model or not prompt_version:
        raise RagasDraftError("GENERATOR_INPUT_INVALID")
    _validate_source_export(chunks, identity)
    output = await KnoraReviewPrompt().generate(
        llm=KnoraRagasLLM(provider),
        data=DraftInput(
            language=language, count=count, chunks=[SourceChunk.model_validate(c) for c in chunks]
        ),
        retries_left=0,
    )
    if len(output.drafts) > count or any(draft.language != language for draft in output.drafts):
        raise RagasDraftError("DRAFT_LIMIT_OR_LANGUAGE_MISMATCH")
    return build_review_packet(
        [draft.model_dump() for draft in output.drafts],
        chunks,
        identity,
        model=model,
        prompt_version=prompt_version,
    )


def write_review_packet(path: Path, packet: dict) -> None:
    write_report_atomic(path, packet)


def noise_sensitivity_readiness(capture: dict, *, judge) -> dict:
    """Gate the experimental diagnostic on full retrieval, not selected evidence."""
    required = ("question", "reference_answer", "answer")
    if (
        any(not isinstance(capture.get(key), str) or not capture[key].strip() for key in required)
        or capture.get("retrieved_contexts_status") != "complete"
        or not isinstance(capture.get("retrieved_contexts"), list)
        or not capture["retrieved_contexts"]
        or any(
            not isinstance(item, str) or not item.strip() for item in capture["retrieved_contexts"]
        )
        or not isinstance(judge, InstructorBaseRagasLLM)
    ):
        return {"status": "unavailable", "score": None}
    return {"status": "ready_experimental", "score": None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local Ragas owner-review packet")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-key", action="append", required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-version", required=True)
    args = parser.parse_args()
    chunks, identity = load_approved_chunks(
        args.manifest, approved_source_keys=tuple(args.source_key)
    )
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    if not isinstance(candidates, list):
        raise RagasDraftError("CANDIDATES_INVALID")
    packet = build_review_packet(
        candidates, chunks, identity, model=args.model, prompt_version=args.prompt_version
    )
    write_review_packet(args.output, packet)


if __name__ == "__main__":
    main()
