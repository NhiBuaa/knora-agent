"""Unit evidence for finite population guards; counts here are synthetic."""

import hashlib
import json
from dataclasses import asdict, replace
from io import BytesIO

import pytest
from backend.test.fixtures.issue_18_acceptance import pdf_extraction
from backend.test.ingestion.test_s2_job_contracts import (
    IndexStore,
    Projection,
    extraction_work,
    index_input,
    lexical_profile,
)

from knora.ingestion.job_processing import (
    Cancellation,
    HandlerFailureKindV1,
    PdfDerivationHandler,
    PdfExtractionProfile,
    WorkFailed,
    WorkSucceeded,
)
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import PdfExtractionConfiguration
from knora.ingestion.search_indexing import LexicalChunk, LexicalIndexHandler, StageReceipt


def population_for(texts):
    documents = [
        {
            "source_sha256": extraction_work().source_sha256,
            "chunks": [
                {
                    "content_checksum": hashlib.sha256(t.encode()).hexdigest(),
                    "native_token_count": 1,
                }
                for t in texts
            ],
        }
    ]
    profile = replace(lexical_profile(), avg_len=1.0)
    statistics = {
        "documents": documents,
        "tokenizer": profile.tokenizer,
        "tokenizer_version": profile.tokenizer_version,
    }
    profile = replace(
        profile,
        statistics_digest=hashlib.sha256(
            json.dumps(statistics, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    return VerifiedLexicalPopulation.from_mapping(
        {
            "schema_version": "lexical-population-v1",
            "id": "synthetic-unit-population",
            "native_evidence_sha256": "f" * 64,
            "profile": asdict(profile),
            "profile_digest": profile.digest(),
            "documents": documents,
        }
    )


@pytest.mark.parametrize("fault", [None, "missing", "source", "text", "profile"])
def test_extraction_requires_known_source_ordered_content_and_profile(fault):
    extraction = pdf_extraction()
    population = population_for(tuple(c.content for c in extraction.chunks))
    profile = population.profile
    work = replace(extraction_work(), lexical_profile_digest=profile.digest())
    if fault == "source":
        work = replace(work, source_sha256="a" * 64)
    if fault == "text":
        extraction = pdf_extraction(page_texts=("Changed source text.",))
    if fault == "profile":
        profile = replace(profile, id="another-profile")
        work = replace(work, lexical_profile_digest=profile.digest())

    class Source:
        def head(self, **kwargs):
            return ObjectMetadata(
                work.workspace_id, work.source_object_key, work.source_sha256, 3, "application/pdf"
            )

        def open_read(self, **kwargs):
            return BytesIO(b"pdf")

    class Extractor:
        def extract(self, stream, configuration):
            return extraction

    handler = PdfDerivationHandler(
        object_store=Source(),
        extractor=Extractor(),
        profile=PdfExtractionProfile(
            "parser-1",
            "pdf-normalizer-m2-v1",
            "chunks-1",
            PdfExtractionConfiguration.milestone_two(),
            profile,
        ),
        lexical_population=None if fault == "missing" else population,
    )
    outcome = handler.execute(work, Cancellation())
    if fault is None:
        assert isinstance(outcome, WorkSucceeded)
        assert outcome.payload.extraction == extraction
    else:
        assert outcome == WorkFailed(
            HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
        )


@pytest.mark.parametrize("fault", [None, "missing", "source", "text", "profile", "order"])
def test_index_checks_authoritative_source_and_ordinal_content_before_projection(fault):
    population = population_for(("first", "second"))
    profile = population.profile
    if fault == "profile":
        profile = replace(profile, id="another-profile")
    texts = ("second", "first") if fault == "order" else ("first", "second")
    if fault == "text":
        texts = ("changed", "second")
    chunks = tuple(
        LexicalChunk(f"chunk-{i}", i, hashlib.sha256(text.encode()).hexdigest())
        for i, text in enumerate(texts)
    )
    generation = replace(
        index_input().generation, lexical_profile=profile, chunks=tuple(reversed(chunks))
    )
    loaded = replace(
        index_input(),
        generation=generation,
        chunk_texts=tuple((c.chunk_id, texts[c.ordinal]) for c in reversed(chunks)),
    )
    work = replace(
        extraction_work(),
        derivation_kind="lexical_index",
        lexical_generation_id=generation.generation_id,
        lexical_profile_digest=profile.digest(),
    )
    if fault == "source":
        work = replace(work, source_sha256="a" * 64)
    projection = Projection(StageReceipt(generation.generation_id, 2, generation.content_digest()))
    handler = LexicalIndexHandler(
        store=IndexStore(loaded),
        index=projection,
        lexical_population=None if fault == "missing" else population,
    )
    outcome = handler.execute(work, Cancellation())
    if fault is None:
        assert isinstance(outcome, WorkSucceeded)
        assert len(projection.calls) == 1
    else:
        assert outcome == WorkFailed(
            HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
        )
        assert projection.calls == []
