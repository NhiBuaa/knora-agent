"""The new finite pin preserves the frozen corpus and retained native counts."""

import json
from collections import defaultdict
from pathlib import Path

from backend.runtime_test.s2_frozen_restore import require_frozen_chunk_bytes

from knora.ingestion.lexical_population import VerifiedLexicalPopulation


def test_frozen_population_matches_all_retained_chunks_without_runtime_ids():
    path = Path("evals/fixtures/pdf_retrieval_v3_s2/frozen47-lexical-population-v1.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    manifest = VerifiedLexicalPopulation.from_mapping(raw)
    frozen = Path("evals/reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime/chunks.json")
    require_frozen_chunk_bytes(frozen.read_bytes())
    chunks = json.loads(frozen.read_text(encoding="utf-8"))["chunks"]
    by_source = defaultdict(list)
    for chunk in chunks:
        by_source[chunk["raw_sha256"]].append(chunk)
    observed = []
    for source, items in sorted(by_source.items()):
        items.sort(key=lambda c: (c["page_start"], c["start_offset"], c["end_offset"]))
        observed.append((source, tuple(c["content"] for c in items)))
    manifest.validate_corpus(observed, manifest.profile)
    assert manifest.profile.id == "bm25-word-frozen47-population-v1"
    assert manifest.native_evidence_sha256 == (
        "556f3733fdc3fa815c88f2b89f91bb632e6b17bbf1330ab25c0606dc23d2e303"
    )
    assert len(manifest.documents) == len(by_source) == 14
    counts = [c.native_token_count for d in manifest.documents for c in d.chunks]
    assert len(counts) == len(chunks) == 47
    assert sum(counts) == 7083
    assert manifest.profile.avg_len == 7083 / 47
    assert manifest.profile.statistics_digest != (
        "b3c146223df19b489786c9bb833df31ab57f24ccf8f6c54db5842a638b1f3336"
    )
