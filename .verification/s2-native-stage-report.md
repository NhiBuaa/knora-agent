# S2.3 native staging wire report

## Scope and ownership

Implemented only the offline Qdrant wire builders and persisted-point acknowledgement validation in `backend/src/knora/adapters/qdrant/search_index.py`, with focused coverage in `backend/test/adapters/qdrant/test_search_index.py`. No transport, service, model, provider, schema, migration, dependency, runtime activation, collection startup, or production selector changes were made. Frozen corpus/evaluation artifacts are untouched.

## Implementation

- Builds a one-shard collection body with empty dense vectors and named `bm25` sparse vectors using the IDF modifier.
- Builds one bounded native staging batch (1–64 points) using the `qdrant/bm25` Document wire shape under named sparse vector `bm25`.
- Reuses the same NFKC/lowercase, `word`, k1/b/avg_len, lowercase, no ASCII folding, no stemmer and empty stopword profile for query and document bodies.
- Validates authoritative UTF-8 text keys, non-empty text and SHA-256 chunk checksums against the immutable generation manifest. Payload contains workspace, generation, chunk, profile identity/digest, per-chunk checksum and generation content digest; source/citation text is not persisted as payload authority.
- Builds an explicit persisted-point readback request and returns `StageReceipt` only after exact count, deterministic UUID identity, full payload identity and generation digest verification. Upsert/HTTP success responses are not accepted as receipts.

## TDD and verification

RED: focused staging tests initially failed with missing `stage_body`, `collection_body`, `persisted_points_body` and `parse_stage_response` methods (28 failures, 10 existing tests passing).

GREEN command (from this worktree):

```powershell
$env:PYTHONPATH='backend/src'; & ../issue-153-pdf-baseline/.venv/Scripts/python.exe -m pytest backend/test/adapters/qdrant/test_search_index.py backend/test/ingestion/test_search_indexing.py -q
```

Output:

```text
..........................................                               [100%]
43 passed in 0.07s
```

Formatting/lint with the available baseline interpreter:

```powershell
& ../issue-153-pdf-baseline/.venv/Scripts/python.exe -m ruff format --check backend/src/knora/adapters/qdrant/search_index.py backend/test/adapters/qdrant/test_search_index.py
& ../issue-153-pdf-baseline/.venv/Scripts/python.exe -m ruff check backend/src/knora/adapters/qdrant/search_index.py backend/test/adapters/qdrant/test_search_index.py
```

Both passed. `git diff --check` passed. The repository-root interpreter did not have Ruff installed; no dependency was installed.

## Exact boundaries and risks

This is an offline wire builder and validator only. It does not call Qdrant, prove qdrant-client/server compatibility, expose native token counts, create collections, upsert points, query, reconcile, activate, or integrate with PostgreSQL services. Qdrant `1.19.2` and qdrant-client `1.19.1` runtime compatibility, endpoint/configuration, and deployment evidence remain a separate gate. Native tokenizer semantics are represented by the pinned profile and shared request options; no whitespace token-count substitute or score threshold was added.
