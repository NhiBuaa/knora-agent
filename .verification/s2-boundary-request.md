## #153 S2.2–S2.4 boundary request — preparing one execution approval

Owner conditionally accepts S2.1 `e78a3b5` / Draft PR #201 and permits offline S2.2 code/tests after exact-head CI required succeeds. CI is running at https://github.com/NhiBuaa/knora-agent/actions/runs/38748177861 (`workflow_dispatch`, exact subject `e78a3b5f0d507916fcf6acce0adada6d037532cd`). Whole remaining S2/runtime plan is being prepared for one owner approval; checkpoints will then be internal evidence, not repeated owner gates. No runtime/migration/model permission is inferred here.

Please confirm the proposed shared-file/schema boundary before S2.2–S2.4 edits:

- #153 owns independent lexical readiness and PostgreSQL authoritative search-generation/work/CAS state, additive migration, ingestion finalization/lifecycle invalidation and focused `ingestion/search_indexing.py` + `adapters/postgres/search_index_store.py`. Existing public ingestion facade and dense behavior remain compatible.
- #153 continues owning the S2 answering/trace seams, trusted lexical projection in `adapters/postgres/evaluation_reader.py`, PDF capture supplements and native Qdrant adapter. Nullable embedding provenance is valid only in explicit lexical mode. No new dataset/run/report authority or evaluation framework.
- Application composition/configuration and an optional dependency/isolated verification Compose file are needed later. Please flag concurrent changes to `main.py`, runtime settings, `backend/pyproject.toml`, `adapters/postgres/tables.py`, Alembic revision chain, trace persistence or evaluation reader before either side edits them. We will agree precise shared diffs and migration parent before editing; silence is not ACK.
- #158/#192 keep ownership of `knora/evaluation/`, DeepEval/Ragas/Langfuse integration, Workbench/Runs API/UI/OpenAPI and their metrics. No change proposed to their canonical facade or historical metric semantics. New retrieval diagnostics remain versioned supplements.
- Proposed runtime is a separate `knora-153-s2` Compose project, own PostgreSQL/Qdrant/objects, loopback ports 15433/16433/18053, no existing session DB/volumes/production defaults. Exact limits are in the forthcoming plan; this comment does not reserve or start these resources.

Frozen Baseline B, 16 PDF/60 gold cases, 25 missing anchors and PR #189 remain unchanged. PR #201 stays Draft; no merge/deploy/close. Please respond with ACK or concrete file/schema conflicts; we can finish the plan and CI independently while waiting.
