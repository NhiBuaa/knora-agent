"""Characterize pinned native vectors against the retained upstream WASI tokenizer."""

import hashlib
import json
import os
import subprocess
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from unicodedata import normalize
from uuid import uuid4

import httpx
import pytest
from backend.runtime_test.s2_frozen_restore import require_frozen_chunk_bytes
from backend.runtime_test.s2_runtime_guard import require_reference_file

from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import QdrantSearchIndex
from knora.answering.stores import RetrievalConfiguration
from knora.infrastructure.lexical_configuration import load_lexical_population
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration, LexicalProfile


@pytest.mark.parametrize("profile_name", ["historical", "frozen47"])
def test_all_frozen_native_vectors_match_upstream_tokens_and_tf_weights(profile_name):
    assert os.environ.get("KNORA_S2_ISOLATED_TESTS") == "1", "owned S2 runtime required"
    spike = Path(os.environ["KNORA_S2_TOKENIZER_SPIKE"])
    murmur = Path(os.environ["KNORA_S2_MURMUR_REFERENCE"])
    frozen = Path("evals/reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime/chunks.json")
    frozen_sha = hashlib.sha256(frozen.read_bytes()).hexdigest()
    require_frozen_chunk_bytes(frozen.read_bytes())
    wasm_sha = hashlib.sha256((spike / "counter.wasm").read_bytes()).hexdigest()
    assert wasm_sha == "36f2b5cb8879b5b62a06c477c5de818b1b84795261b4785400714d2854d16269"
    require_reference_file(
        spike / "run-counter.cjs",
        "efd363a01df40b2fd08261b68070577600aa37579caccf6f7f2bbe2280436340",
    )
    require_reference_file(
        murmur, "45368bfe11080c4504b7804602015d93873303c5b13d5710af6c42e9abc35b4a"
    )
    chunks = json.loads(frozen.read_text(encoding="utf-8"))["chunks"]
    assert len(chunks) == 47
    counter = subprocess.run(
        ["node", str(spike / "run-counter.cjs"), str(spike / "counter.wasm")],
        input="\n".join(normalize("NFKC", c["content"]).lower().encode().hex() for c in chunks)
        + "\n",
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    tokens = []
    for line in counter.stdout.splitlines():
        count, encoded = line.split("\t")
        decoded = [bytes.fromhex(token).decode() for token in encoded.split()]
        assert len(decoded) == int(count)
        tokens.append(decoded)
    assert len(tokens) == 47 and sum(map(len, tokens)) == 7083
    reference_counts = json.loads((spike / "spike-result.json").read_text(encoding="utf-8"))[
        "chunk_counts"
    ]
    assert [(c["chunk_id"], len(t)) for c, t in zip(chunks, tokens, strict=True)] == [
        (c["chunk_id"], c["native_upstream_token_count"]) for c in reference_counts
    ]
    unique = sorted({token for document in tokens for token in document})
    hashes = subprocess.run(
        [
            "node",
            "-e",
            "const fs=require('node:fs');const hash=require(process.argv[1]);"
            "const tokens=JSON.parse(fs.readFileSync(0,'utf8'));"
            "process.stdout.write(JSON.stringify(tokens.map(t=>Math.abs("
            "hash(Buffer.from(t,'utf8').toString('latin1'),0).result()|0))));",
            str(murmur),
        ],
        input=json.dumps(unique),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    token_ids = dict(zip(unique, json.loads(hashes.stdout), strict=True))
    assert len(set(token_ids.values())) == len(token_ids), "reference hash collision"
    statistics = [
        {"chunk_id": c["chunk_id"], "checksum": c["content_checksum"], "native_token_count": len(t)}
        for c, t in zip(chunks, tokens, strict=True)
    ]
    statistics_digest = hashlib.sha256(json.dumps(statistics, sort_keys=True).encode()).hexdigest()
    profile = LexicalProfile.from_native_token_counts(
        id="bm25-unicode-word-v1",
        tokenizer="word",
        tokenizer_version="qdrant-1.19.2",
        k1=1.2,
        b=0.75,
        token_counts=tuple(map(len, tokens)),
        statistics_digest=statistics_digest,
    )
    if profile_name == "frozen47":
        population = load_lexical_population(
            RetrievalConfiguration.bm25_top8_v1(),
            "evals/fixtures/pdf_retrieval_v3_s2/frozen47-lexical-population-v1.json",
        )
        grouped = {}
        for chunk in chunks:
            grouped.setdefault(chunk["raw_sha256"], []).append(chunk)
        population.validate_corpus(
            tuple(
                (
                    source_sha,
                    tuple(
                        c["content"]
                        for c in sorted(rows, key=lambda c: (c["page_start"], c["start_offset"]))
                    ),
                )
                for source_sha, rows in grouped.items()
            ),
            population.profile,
        )
        assert population.profile.avg_len == profile.avg_len
        profile = population.profile
    run_id = uuid4().hex
    report = {
        "run_id": run_id,
        "scope": "47-chunk native vector parity, no quality/serving claim",
        "frozen_sha256": frozen_sha,
        "counter_wasm_sha256": wasm_sha,
        "counter_launcher_sha256": hashlib.sha256(
            (spike / "run-counter.cjs").read_bytes()
        ).hexdigest(),
        "murmur_reference_sha256": hashlib.sha256(murmur.read_bytes()).hexdigest(),
        "profile": asdict(profile),
        "profile_name": profile_name,
        "profile_digest": profile.digest(),
        "statistics": statistics,
        "calls": [],
        "status": "incomplete",
    }
    evidence = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / ("frozen-parity-" + run_id + ".json")
    evidence.parent.mkdir(parents=True, exist_ok=True)

    def capture(response):
        response.read()
        assert response.request.url.host == "127.0.0.1" and response.request.url.port == 16433
        assert len(report["calls"]) < 20
        report["calls"].append(
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

    try:
        with httpx.Client(
            base_url="http://127.0.0.1:16433",
            timeout=20,
            trust_env=False,
            event_hooks={"response": [capture]},
        ) as client:
            assert client.get("/").json()["version"] == "1.19.2"
            index = QdrantSearchIndex("s2_frozen_parity_" + run_id, profile)
            port = NativeQdrantSearchIndex(index=index, client=client)
            port.ensure_collection()
            generation = LexicalGeneration(
                run_id,
                "frozen-parity-only",
                "synthetic-parity-container",
                "parity-version",
                "parity-chunks",
                profile,
                1,
                tuple(
                    LexicalChunk(c["chunk_id"], i, c["content_checksum"])
                    for i, c in enumerate(chunks)
                ),
            )
            receipt = port.stage_generation(
                generation, {c["chunk_id"]: c["content"] for c in chunks}
            )
            receipt.validate(generation)
            response = client.post(
                f"/collections/{index.collection_name}/points",
                json={
                    "ids": list(generation.point_ids()),
                    "with_vector": True,
                    "with_payload": True,
                },
            )
            response.raise_for_status()
            vectors = {
                p["payload"]["chunk_id"]: p["vector"]["bm25"] for p in response.json()["result"]
            }
            assert set(vectors) == {c["chunk_id"] for c in chunks}
            for chunk, document in zip(chunks, tokens, strict=True):
                counts = Counter(document)
                expected = {
                    token_ids[token]: count
                    * 2.2
                    / (1.2 * (0.25 + 0.75 * len(document) / profile.avg_len) + count)
                    for token, count in counts.items()
                }
                vector = vectors[chunk["chunk_id"]]
                actual = dict(zip(vector["indices"], vector["values"], strict=True))
                assert actual == pytest.approx(expected, rel=2e-6)
            report["status"] = "passed"
    finally:
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
