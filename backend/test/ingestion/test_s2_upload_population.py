"""The finite upload fixture must match actual production PDF extraction."""

import hashlib
import json
from pathlib import Path

from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.pdf import PdfExtractionConfiguration


def test_upload_manifest_matches_the_real_pdf_and_measured_counter_evidence():
    root = Path("evals/fixtures/pdf_retrieval_v3_s2")
    manifest = VerifiedLexicalPopulation.from_mapping(
        json.loads((root / "upload-lexical-population-v1.json").read_text(encoding="utf-8"))
    )
    pdf = root / "refund-policy.pdf"
    with pdf.open("rb") as stream:
        extraction = PypdfTextExtractor().extract(
            stream, PdfExtractionConfiguration.layout_preserving()
        )
    assert len(extraction.chunks) == 1
    assert extraction.chunks[0].content == "Refund requests are accepted within 30 days."
    counts = manifest.validate_document(
        hashlib.sha256(pdf.read_bytes()).hexdigest(),
        tuple(chunk.content for chunk in extraction.chunks),
        manifest.profile,
    )
    assert counts == (7,)
    assert manifest.profile.id == "bm25-word-upload-fixture-population-v1"
    evidence_path = root / "upload-native-counter-v1.json"
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == manifest.native_evidence_sha256
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["counter_wasm_sha256"] == (
        "36f2b5cb8879b5b62a06c477c5de818b1b84795261b4785400714d2854d16269"
    )
    assert evidence["native_server_verified"] is False
    assert evidence["chunks"][0]["native_token_count"] == len(evidence["chunks"][0]["tokens"]) == 7
