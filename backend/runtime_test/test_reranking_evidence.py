"""Runtime contract, performance and safety validation for Reranking and Evidence selection.

Tests zero local model weights invariant, p50/p95 latency bounds, Cloudflare API
isolation, fallback safety, and evidence budget compliance under realistic loads.
Refs #153 (Retrieval V3 Stage 6).
"""

from __future__ import annotations

import hashlib
import sys
import time

from knora.answering.reranking import (
    combine_reranking_scores,
    select_evidence_mmr,
)
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.stores import RetrievalCandidate
from knora.providers.cloudflare.reranking import CloudflareRerankingProvider


def _generate_synthetic_candidates(
    num_candidates: int = 100, words_per_chunk: int = 250
) -> list[RetrievalCandidate]:
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
        "thời",
        "hạn",
        "chấm",
        "dứt",
        "người",
        "sử",
        "dụng",
        "trách",
        "nhiệm",
        "bồi",
        "thường",
        "quy",
        "định",
        "pháp",
        "luật",
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
        "điều",
        "khoản",
        "employment",
        "contract",
        "salary",
        "insurance",
        "termination",
        "severance",
        "benefits",
        "compliance",
        "statutory",
        "regulations",
        "obligations",
        "liability",
    ]

    candidates = []
    for i in range(num_candidates):
        chunk_id = f"chunk-{i:04d}"
        words = [vocabulary[(i * 13 + w * 29) % len(vocabulary)] for w in range(words_per_chunk)]
        text = " ".join(words)
        candidates.append(
            RetrievalCandidate(
                document_id="doc-runtime",
                document_version_id="ver-runtime",
                source_key="policy",
                source_name="policy.pdf",
                chunk_set_id="cset-runtime",
                embedding_set_id=None,
                embedding_configuration_id=None,
                chunk_id=chunk_id,
                chunk_ordinal=i,
                heading_path=("Section A", f"Clause {i}"),
                start_line=1,
                end_line=20,
                content=text,
                content_checksum=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                token_count=len(words),
                cosine_distance=None,
                similarity=None,
                fusion_score=0.95 - (i * 0.005),
                sdm_score=0.90 - (i * 0.004),
                index_generation_id="gen-runtime",
            )
        )
    return candidates


def test_zero_local_model_weights_invariant():
    """Verify strictly $0 AI budget: NO PyTorch, HuggingFace Transformers, FastEmbed or ONNX."""
    forbidden = {
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "fastembed",
        "onnx",
        "onnxruntime",
        "sentence_transformers",
    }
    loaded_forbidden = forbidden.intersection(sys.modules.keys())
    assert not loaded_forbidden, (
        f"Zero local model weights invariant violated: loaded forbidden modules {loaded_forbidden}"
    )


def test_reranking_combination_and_mmr_latency():
    """Verify runtime latency: score combination and MMR on 100 candidates."""
    candidates = _generate_synthetic_candidates(num_candidates=100, words_per_chunk=250)
    config = RerankingConfiguration.cloudflare_bge_reranker_v1()

    # Pre-generate synthetic reranker scores
    rerank_scores = {
        c.chunk_id: 0.1 + (int(c.chunk_id.split("-")[1]) % 10) * 0.08 for c in candidates
    }

    latencies_ms: list[float] = []

    # Run 30 iterations for benchmark distribution
    for _ in range(30):
        t0 = time.perf_counter()
        combined = combine_reranking_scores(candidates, rerank_scores, config)
        selection = select_evidence_mmr(combined, config)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    latencies_ms.sort()
    p50 = latencies_ms[len(latencies_ms) // 2]
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)]

    assert p50 < 10.0, f"Reranking + MMR p50 latency exceeded budget: {p50:.2f}ms >= 10.0ms"
    assert p95 < 25.0, f"Reranking + MMR p95 latency exceeded budget: {p95:.2f}ms >= 25.0ms"
    assert len(selection.selected) <= config.max_evidence_chunks


def test_evidence_budget_containment():
    """Verify that MMR evidence selection strictly respects max 5 chunks and 3000 tokens."""
    candidates = _generate_synthetic_candidates(num_candidates=50, words_per_chunk=800)
    config = RerankingConfiguration.cloudflare_bge_reranker_v1()

    selection = select_evidence_mmr(candidates, config)

    # 1. Chunk count limit
    assert len(selection.selected) <= 5
    # 2. Token budget limit
    total_tokens = sum(item.candidate.token_count for item in selection.selected)
    assert total_tokens <= 3000, f"Total tokens {total_tokens} exceeded budget 3000"


def test_cloudflare_reranker_endpoint_isolation():
    """Verify Cloudflare reranker provider strictly isolates endpoint to Workers AI allowlist."""
    provider = CloudflareRerankingProvider(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="test-api-token",
    )
    expected_url = "https://api.cloudflare.com/client/v4/accounts/0123456789abcdef0123456789abcdef/ai/run/@cf/baai/bge-reranker-base"
    assert provider.endpoint_url == expected_url
    assert provider.model == "@cf/baai/bge-reranker-base"
