"""Runtime contract and performance validation for Sequential Dependence Model (SDM).

Tests runtime constraints, latency bounds (p50/p95 < 10ms on 100 candidates),
preservation of dense-only candidates, determinism, and error guards under
authorized post-DBSF conditions.
Refs #153.
"""

from __future__ import annotations

import hashlib
import math
import time

import pytest

from knora.answering.sequential_dependence import (
    CorpusStatistics,
    SequentialDependenceConfig,
    SequentialDependenceScorer,
)
from knora.answering.stores import RetrievalCandidate
from knora.ingestion.lexical_positions import (
    ChunkPositionalDerivation,
    build_corpus_statistics_from_chunks,
    extract_chunk_positions,
)


def _generate_synthetic_corpus_and_candidates(
    num_candidates: int = 100, words_per_chunk: int = 200
) -> tuple[list[RetrievalCandidate], CorpusStatistics, str, dict[str, ChunkPositionalDerivation]]:
    """Generate realistic synthetic candidates for runtime latency & contract tests."""
    vocabulary = [
        "hợp",
        "đồng",
        "lao",
        "động",
        "tiền",
        "lương",
        "bảo",
        "hiểm",
        "xã",
        "hội",
        "người",
        "sử",
        "dụng",
        "thời",
        "hạn",
        "chấm",
        "dứt",
        "trách",
        "nhiệm",
        "bồi",
        "thường",
        "quy",
        "định",
        "pháp",
        "luật",
        "điều",
        "khoản",
        "thỏa",
        "thuận",
        "doanh",
        "nghiệp",
        "chi",
        "trả",
        "chế",
        "độ",
        "thử",
        "việc",
        "nghỉ",
        "phép",
        "năm",
    ]

    query_tokens = ["hợp", "đồng", "lao", "động", "tiền", "lương"]
    query = " ".join(query_tokens)

    derivations: list[ChunkPositionalDerivation] = []
    candidates: list[RetrievalCandidate] = []

    for i in range(num_candidates):
        chunk_id = f"chunk-{i:04d}"
        words = []
        for w in range(words_per_chunk):
            idx = (i * 17 + w * 31) % len(vocabulary)
            words.append(vocabulary[idx])

        # Top 10 candidates have exact query phrase matches
        if i < 10:
            words[10:16] = query_tokens

        text = " ".join(words)
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()

        deriv = extract_chunk_positions(chunk_id, text, checksum)
        derivations.append(deriv)

        candidates.append(
            RetrievalCandidate(
                document_id=f"doc-{i // 10}",
                document_version_id=f"ver-{i // 10}",
                source_key="handbook",
                source_name="handbook.pdf",
                chunk_set_id="cset-1",
                embedding_set_id="eset-1",
                embedding_configuration_id="econf-1",
                chunk_id=chunk_id,
                chunk_ordinal=i,
                heading_path=("Chương I",),
                start_line=1,
                end_line=20,
                content=text,
                content_checksum=checksum,
                token_count=len(words),
                cosine_distance=0.15 + (i * 0.005),
                similarity=0.85 - (i * 0.005),
                bm25_score=15.0 - (i * 0.1),
                fusion_score=1.0 - (i * 0.008),
                index_generation_id="gen-1",
            )
        )

    corpus_stats = build_corpus_statistics_from_chunks(
        derivations, statistics_digest="runtime-digest-001"
    )
    positions_map = {d.chunk_id: d for d in derivations}

    return candidates, corpus_stats, query, positions_map


def test_sdm_latency_p50_p95_on_100_candidates() -> None:
    """SDM scoring on 100 DBSF candidates must have p50 < 10ms and p95 < 20ms."""
    candidates, corpus_stats, query, positions_map = _generate_synthetic_corpus_and_candidates(
        num_candidates=100, words_per_chunk=200
    )
    scorer = SequentialDependenceScorer(
        config=SequentialDependenceConfig(
            lambda_t=0.80,
            lambda_o=0.10,
            lambda_u=0.10,
            mu=2500.0,
            window_size=8,
            blend_alpha=0.30,
        ),
        corpus_stats=corpus_stats,
    )

    # 1. Warm-up run with pre-extracted positions
    _ = scorer.score_candidates(query, candidates, positions_by_chunk=positions_map)

    latencies_pos_ms: list[float] = []
    for _ in range(60):
        t0 = time.perf_counter()
        results = scorer.score_candidates(query, candidates, positions_by_chunk=positions_map)
        t1 = time.perf_counter()
        latencies_pos_ms.append((t1 - t0) * 1000.0)
        assert len(results) == 100

    latencies_pos_ms.sort()
    pos_p50 = latencies_pos_ms[int(len(latencies_pos_ms) * 0.50)]
    pos_p95 = latencies_pos_ms[int(len(latencies_pos_ms) * 0.95)]

    # Contract with positional cache: p50 < 10.0ms, p95 < 20.0ms
    assert pos_p50 < 10.0, f"Positional p50 latency {pos_p50:.2f}ms exceeded 10ms limit"
    assert pos_p95 < 20.0, f"Positional p95 latency {pos_p95:.2f}ms exceeded 20ms limit"

    # 2. Raw content tokenization fallback
    latencies_raw_ms: list[float] = []
    for _ in range(60):
        t0 = time.perf_counter()
        results = scorer.score_candidates(query, candidates)
        t1 = time.perf_counter()
        latencies_raw_ms.append((t1 - t0) * 1000.0)
        assert len(results) == 100

    latencies_raw_ms.sort()
    raw_p50 = latencies_raw_ms[int(len(latencies_raw_ms) * 0.50)]
    raw_p95 = latencies_raw_ms[int(len(latencies_raw_ms) * 0.95)]

    # Contract with raw fallback: p50 < 15.0ms, p95 < 25.0ms
    assert raw_p50 < 15.0, f"Raw p50 latency {raw_p50:.2f}ms exceeded 15ms limit"
    assert raw_p95 < 25.0, f"Raw p95 latency {raw_p95:.2f}ms exceeded 25ms limit"


def test_sdm_dense_only_candidates_preserved_and_scored() -> None:
    """Dense candidates with zero lexical matches receive valid Dirichlet smoothed scores."""
    _, corpus_stats, query, _ = _generate_synthetic_corpus_and_candidates(
        num_candidates=10, words_per_chunk=100
    )

    # Dense candidate with entirely disjoint vocabulary
    dense_text = "hoàn toàn không chứa bất kỳ từ khóa nào từ câu hỏi truy vấn"
    dense_checksum = hashlib.sha256(dense_text.encode("utf-8")).hexdigest()
    dense_candidate = RetrievalCandidate(
        document_id="doc-dense",
        document_version_id="ver-dense",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-dense",
        embedding_set_id="eset-dense",
        embedding_configuration_id="econf-dense",
        chunk_id="chunk-dense-only-999",
        chunk_ordinal=0,
        heading_path=(),
        start_line=1,
        end_line=10,
        content=dense_text,
        content_checksum=dense_checksum,
        token_count=len(dense_text.split()),
        cosine_distance=0.08,
        similarity=0.92,
        bm25_score=None,
        fusion_score=0.92,
        index_generation_id="gen-1",
    )

    # Normal lexical candidate
    lexical_text = "hợp đồng lao động tiền lương và chế độ"
    lex_checksum = hashlib.sha256(lexical_text.encode("utf-8")).hexdigest()
    lexical_candidate = RetrievalCandidate(
        document_id="doc-lex",
        document_version_id="ver-lex",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-lex",
        embedding_set_id="eset-lex",
        embedding_configuration_id="econf-lex",
        chunk_id="chunk-lexical-001",
        chunk_ordinal=1,
        heading_path=(),
        start_line=11,
        end_line=20,
        content=lexical_text,
        content_checksum=lex_checksum,
        token_count=len(lexical_text.split()),
        cosine_distance=0.25,
        similarity=0.75,
        bm25_score=12.5,
        fusion_score=0.75,
        index_generation_id="gen-1",
    )

    scorer = SequentialDependenceScorer(corpus_stats=corpus_stats)
    results = scorer.score_candidates(query, [dense_candidate, lexical_candidate])

    # Assert both candidates are present in output
    assert len(results) == 2
    scored_dense = next(r for r in results if r.candidate.chunk_id == "chunk-dense-only-999")
    scored_lex = next(r for r in results if r.candidate.chunk_id == "chunk-lexical-001")

    # Dense candidate must have finite, valid scores
    assert math.isfinite(scored_dense.raw_sdm_score)
    assert scored_dense.raw_sdm_score < 0.0  # Log probabilities are negative
    assert scored_dense.unigram_score < 0.0
    assert scored_dense.ordered_score < 0.0
    assert scored_dense.unordered_score < 0.0
    assert 0.0 <= scored_dense.normalized_sdm_score <= 1.0
    assert 0.0 <= scored_dense.combined_score <= 1.0
    assert scored_dense.unigram_matches == 0
    assert scored_dense.ordered_matches == 0
    assert scored_dense.unordered_matches == 0

    # Lexical candidate has matches
    assert scored_lex.unigram_matches > 0


def test_sdm_deterministic_ranking_and_permutation_invariance() -> None:
    """Input candidate order permutation must produce identical ranking and scores."""
    candidates, corpus_stats, query, _ = _generate_synthetic_corpus_and_candidates(
        num_candidates=25, words_per_chunk=150
    )
    scorer = SequentialDependenceScorer(corpus_stats=corpus_stats)

    res1 = scorer.score_candidates(query, candidates)
    res2 = scorer.score_candidates(query, list(reversed(candidates)))

    order1 = [r.candidate.chunk_id for r in res1]
    order2 = [r.candidate.chunk_id for r in res2]

    assert order1 == order2
    for r1, r2 in zip(res1, res2, strict=True):
        assert r1.candidate.chunk_id == r2.candidate.chunk_id
        assert abs(r1.raw_sdm_score - r2.raw_sdm_score) < 1e-9
        assert abs(r1.combined_score - r2.combined_score) < 1e-9


def test_sdm_positional_extraction_throughput_and_checksum_verification() -> None:
    """Positional extraction from 100 chunks must be fast (< 50ms) and enforce checksums."""
    raw_chunks = []
    for i in range(100):
        text = f"Nội dung chunk {i} về điều khoản thanh lý hợp đồng và nghiệm thu số {i * 10}."
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        raw_chunks.append((f"chunk-{i}", text, checksum))

    t0 = time.perf_counter()
    derivations = [extract_chunk_positions(cid, txt, chk) for cid, txt, chk in raw_chunks]
    duration_ms = (time.perf_counter() - t0) * 1000.0

    assert len(derivations) == 100
    assert duration_ms < 50.0, f"Extraction took {duration_ms:.2f}ms, expected < 50ms"

    # Corrupt one checksum and verify rejection
    bad_cid, bad_txt, _ = raw_chunks[0]
    corrupt_checksum = "bad-checksum" + "0" * 52

    with pytest.raises(ValueError, match="content checksum mismatch"):
        extract_chunk_positions(bad_cid, bad_txt, corrupt_checksum)
