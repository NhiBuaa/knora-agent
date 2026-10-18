# S2.3 native staging wire report

## Latest Q20 and retry evidence — 2026-10-18

Q20 source, fixture-isolation and route corrections are applied under exact #192 ACKs
6247908659,6248015911 and6248144459. The separate30minute runtime window retained the
fixed09:30:38UTC deadline and the owner's RAM-gate waiver. Actual private rollback fixture
passed1test: two real extractions,16native calls, C restaging/readback and revision5 CAS,
stale B activation denied, replay/conflict checked, all54 retained jobs unchanged. Across
three retained attempts22native calls were made (including six collection-setup calls before
the failed405 upload), with zero retrieval queries and zero generator/embedding/provider calls.
Owned PG/Qdrant were stopped at09:18:28UTC. Volumes, failed reports and collection evidence remain.
Evidence is in `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-q20-20261018/`.

Lexical reprocess retry packet115d80b9… is also applied under ACK6248144459: a failed child
no longer reuses a completed extraction, new internal job identities avoid fingerprint
collisions, and matching live work remains reusable. Independent scoped review has no blocker;
106maintained-worktree tests pass. No DB concurrency proof follows from those offline tests.
Full required CI on a new commit remains outstanding; HEAD remains4e0134d and S2 is incomplete.
Historical boundaries below are retained as chronology, superseded by this section.

## Current boundary — 2026-10-18

Latest superseding checkpoint: Q18 Windows-worker/private-bind packet received exact source
ACK6245501444. Retained HTTP retry resumed without object recreation or DB repair and passed
real loopback delivery through extraction/index/readiness/answer/citation/archive503. The three
Q8 lifecycle tests passed after their ACKed finite-population fixture correction. Q19 cleanup
round3 received exact ACK6245725578 and was applied after hash checks;52 offline tests passed.
Its separate structural native cleanup fixture passed1test with16nativecalls/3deletes/0queries,
in its own retained collection (ACK6245758425). Q10 round3 exact ACK6245848298 preceded both
trigger races passing;51pre-existing ingestion jobs hash identically before/after. Failed
fixture attempts and queued jobs remain unchanged. All owned services were stopped early
after tests (`early-stop-after-q10.json`). Q20 corrected real-reprocess rollback is approved
but remains a TEMP candidate pending finite source ACK/application and runtime proof.
Watchdog PID50048 was confirmed absent with stale heartbeat; all three owned services were
stopped early, retaining volumes. A replacement task keeps the original07:51:38UTC deadline.
No new all60 run, generator/provider call, developer DB repair or quality acceptance followed.
See the implementation checkpoint's latest section for the complete artifact paths and gates.

The additional window started2026-10-18T03:51:38Z and ends07:51:38Z; an independent watchdog
stops owned services three minutes early. Owner waived only the8GiB free-host-RAM gate.
Q17 preserved the old S2 DB via verified dump and rename; the fresh owned DB migrated to0155.
New finite frozen47 native parity passed. Fresh TestClient application upload→two jobs→native
question/citation→archive503 passed. Actual all60 attempt2 completed with exactly60native
queries,82total native API calls and one47-point PUT;206protected inputs unchanged.
Retrieval-only full group coverage: BM25Top8/selected34/35; Baseline B candidate/selected8/35.
All60 cases,47chunks,61mappings,25missing anchors and8controls remain; no generation or semantic
assessment was performed for all60. All8controls still selected BM25 evidence.

Historical pre-Q18-ACK attempt: real HTTP delivery was incomplete because container extraction
failed closed with cgroup2 read-only. The retry job/history is retained. Owner Q18 approved Windows worker plus a private
shared object-store bind; finite Compose/test ACK is pending. Three lifecycle tests also need
their stale fixture setup updated to the approved finite population. See the implementation
checkpoint for artifact paths, exact hashes, failed attempts and review boundaries.

## Historical runtime evidence — 2026-10-17

This section supersedes the historical offline-only statements below. Owned project
`knora-153-s2` runs PostgreSQL15433 and Qdrant16433 with separate retained volumes and
approved resource caps. Qdrant telemetry is disabled; the first empty startup had logged
the default enabled state and was immediately replaced before any corpus/query.

- Structural native scope/IDF/options/persisted-vector suite: **8 passed**, including an
  authorized N=2/n=1 score of ln(2), exclusion of foreign/revoked points, accents and numbers.
  One repeat command omitted the required evidence-root environment variable and errored
  before native requests; the corrected command passed8. Evidence remains under
  `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/structural/`.
- Frozen native vector parity: **1 passed**, covering every47 chunk and all7083 upstream
  tokens, exact sparse token-hash identities and TF weights (relative tolerance2e-6).
  Uses the verified retained upstream WASI tokenizer, existing imurmurhash0.1.4 over UTF-8
  bytes with seed0/absolute signed32-bit IDs, and independently calculated BM25 TF weights.
  This reference is a verification input, not an application/runtime dependency.
- Parity artifact:
  `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/frozen-parity-ec80d5cda5fa445d8ed848807d9d3f89.json`.
  It retains requests/responses, source/WASM/reference digests, per-chunk counts and the
  population/profile digest. Profile avg_len is7083/47, not a whitespace estimate.
- The first parity command selected BaselineB's capture copy and stopped at byte-SHA
  validation before native calls. Its47 identity/checksum pairs matched, but byte hash
  differed. Corrected input is the approved `binding-layout-v2-runtime/chunks.json`, SHA
  `146109370459186ef0d46e49e0165e1184ec719fe8a61a6b9cd55156e0b256f9`.
  Neither artifact was edited.
- Qdrant server1.19.2 image is now pinned in the opt-in Compose file to digest
  `b7b0444c4c351c970b98e90a6f89c2ee4287c65b44e52b4cb503fa5b2aa927ad`.
  SDK1.19.1 low-level REST successfully issued one native query with no inference;
  `sdk1191-native1192-query.json` retains evidence. The SDK remains a TEMP compatibility
  reference and has not been added to application dependencies.

No all60-case experiment or application serving/quality acceptance is claimed. Canonical
tie ordering at a full200-hit boundary awaits owner Q9. Runtime window is bounded to four
hours from approximately02:06UTC; preserve volumes/evidence when stopping owned services.

Additional structural integration: `test_s2_native_postgres_retrieval.py` passed2 tests with
real PG authority, native stage/receipt, PG activation, exactly one native query and PG text
hydration. Archiving the document immediately after the native query response rejects the
result before hydration. Retained evidence uses unique `pg-native-*.json` names in the same
runtime directory. This does not replace the pending shared facade or application E2E gate.

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

## Takeover follow-on: offline payload keyword indexes

`payload_index_bodies()` now builds three separate REST index request bodies:
`workspace_id` uses keyword with `is_tenant=true`; `generation_id` and
`profile_digest` use ordinary keyword indexes. These exactly cover the existing
query and authorized-IDF filter fields. Each call returns fresh bodies.
The shapes follow the official [tenant indexing](https://qdrant.tech/documentation/manage-data/indexing/)
and [payload filtering](https://qdrant.tech/documentation/search-patterns/vector-search-filtering/)
documentation fetched through Context7 during takeover.

TDD: the added contract test failed on the absent method, with the existing43
tests passing; after implementation the adapter/generation subset has **44 passed**.
The wider offline answering/retrieval/trace/PDF runner/dataset selection has
**166 passed**. Root Ruff format/check/lint and `git diff --check` pass.

These bodies are not sent anywhere. Index creation, actual tenant/stale isolation,
candidate-server compatibility and native IDF correctness remain unverified.

## Native transport implementation follow-on (offline)

The uncommitted `native_search_index.py` now sends native REST requests through the
existing HTTP dependency. It requires completed writes and complete persisted-point
readback before a receipt, disables redirects, makes sequential collection setup
replayable and validates the sparse BM25/IDF collection configuration. Projection
outages never become empty evidence. Transient transport/408/429/5xx and terminal
malformed response/configuration failures retain separate classifications, including
invalid compressed HTTP responses found by independent review.

The native transport suite has **41 passing offline tests**. The larger focused
S2/answering selection has **344 passed**; root Ruff format/check/lint passes.
No transport requests have reached a Qdrant server in this takeover. These tests
do not establish native tokenizer/count/vector parity, pinned client/server
compatibility, authorized-corpus IDF, actual isolation or serving readiness.
