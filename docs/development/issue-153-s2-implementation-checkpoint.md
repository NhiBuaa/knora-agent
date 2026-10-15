# Issue153 S2 — implementation checkpoint (incomplete)

Date: 2026-10-16 (Asia/Saigon). Parent implementation gate: S2.1 `e78a3b5`,
[exact-head CI success](https://github.com/NhiBuaa/knora-agent/actions/runs/38748177861).
Whole-plan owner approval: PR203 `1346b7c`,
[execution record](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6199183792).

## Boundary and scope

Work is isolated in `issue-153-s2-implementation`, Draft PR204, stacked on PR201.
Concrete shared boundary ACKs: [#158](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6199062129)
and [#192](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6199062853).
[Exact migration-chain ACK](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6199213191):
local revision `20261016_0153` follows `4949b27855f4`. Workbench0051 remains a separate,
unmerged chain; ancestry/integration order must be reconciled before integration.

This checkpoint delivers immutable requests, wire validation and provisional
PostgreSQL request/activation/revoke transactions. **S2.2 is not complete**: durable
lease/retry/reconciliation, extraction without embedding, lifecycle hooks and serving
integration are outstanding. No constructor or test-only store establishes production
readiness. No second in-memory lifecycle authority remains.

## Independent review and corrections

The initial six tests missed real faults: colon point IDs invalid in Qdrant, missing
named sparse `using`, partial receipt acceptance, stale revision activation and absent
profile provenance. An independent reproduction activated revision1 after revision2
and accepted one point for a two-chunk request.

Corrections:

- Deterministic UUID5 point IDs bind generation/chunk; response validates that identity.
- `using=bm25`, NFKC/lowercase, raw scores without numeric cutoff, workspace/generation/
  profile-digest scope for both retrieval and IDF, and fail-closed malformed/stale,
  duplicate, nonfinite and out-of-order rows. Server tie-boundary behavior is unproven.
- One profile value object, receipt equality against full expected count and digest.
- Delete unused `GenerationLedger`. PostgreSQL locks workspace before document,
  validates authoritative chunk manifests and desired revision, and records complete
  receipts atomically with activation. Workspace/document revisions fence delayed work.
- Archive permits explicit revoke; revoked identities cannot activate or request-replay.
- Follow-up independent PostgreSQL review found the missing workspace lock/revision
  fence and archived-source revoke bug; code and dedicated runtime tests address them.
  Global fixture-ID collision was corrected to UUIDs. Runtime concurrency is unproven.

## Verification so far

- Focused existing answering/PDF/evaluation contracts plus new pure contracts: **244 passed**.
- Ruff root format, format check, lint and `git diff --check`: passed.
- Alembic graph has one **local** head0153. Offline SQL rendering for
  `4949b27855f4:20261016_0153` creates lexical tables only, no database connection.
- Five PostgreSQL lifecycle tests were collected, **not executed**. They live in
  `backend/runtime_test/test_s2_search_index_store.py`, outside cheap required-CI
  collection as approved by the plan. A manual run requires `KNORA_S2_ISOLATED_TESTS=1`
  and asserts loopback port15433/database `knora_153_s2` before any DB access.
  Do not count these tests as passing or silently skip them within CI reports.
- Required CI for this implementation head is pending, not inherited from S2.1.
- No full local suite, migration execution, Qdrant query or application E2E claim.

## S2.3 offline native staging checkpoint

The Qdrant adapter now builds, offline only, a one-shard native BM25 collection body, a single 1–64 point staging batch, and an exact persisted-point readback request. It shares the approved `word` profile and NFKC/lowercase normalization with query construction. Readback returns a `StageReceipt` only after exact point count, deterministic UUID identity, profile/checksum/content-digest payload validation; HTTP/upsert acknowledgement alone is rejected. No transport, Qdrant service, collection, migration or runtime activation was performed. Details and tests: `.verification/s2-native-stage-report.md`.

The BM25 policy identifier is now `bm25-unicode-word-v1`; Baseline B's vector threshold and all historical artifacts are unchanged.

Offline verification on this head: focused S2 tests **272 passed**. The broader evaluation-reader selection was not included in that count because its five tests attempted a developer PostgreSQL at `127.0.0.1:5432` and failed password authentication; no test failure was caused by the S2 code, and no database was modified. Ruff format/check and `git diff --check` pass.
## Tokenizer spike

Owner approved changing to native `word` under a new profile and a <=2h offline spike.
[Primary sources, experiment and limitations](../research/2026-10-16-s2-native-word-tokenizer.md)
record five exact-token fixtures and the frozen47-chunk population:7,083 tokens,
proposed `avg_len=150.70212765957447`. Pinned server parity and profile activation
remain pending. No default256 or approximate tokenizer was used.

## Runtime and preservation

Host RAM preflight remains below8GiB; no service or local migration has started.
Disk has more than10GiB; proposed15433/16433/18053 ports have no listeners.
Do not stop main apps/services or relax the resource gate. The approved runtime project,
limits, independent volumes/database, retained logs and cleanup rules remain in PR203.

PR189 was verified OPEN/Ready (`isDraft=false`), contrary to older Draft descriptions.
Its state/content was not changed. New raw artifacts live outside Git. Frozen corpus,
gold, 47 chunks, binding, 25 missing anchors, all60 cases, BaselineB and historical
metrics remain unchanged. No provider/model/judge/export, paid cost, production-default
change, merge, deploy or Issue close was performed.

## Remaining acceptance evidence

1. Finish S2.2 worker/extraction/lifecycle integration and recovery with existing lease
   and retry contracts; execute owned PostgreSQL concurrency/rollback tests.
2. Verify exact native server/client, tokenizer/count/vector parity, authorized-corpus
   IDF and tenant/stale isolation before activating any profile.
3. Run one bounded all60 retrieval experiment, save Top200 once, derive native Top8
   without refill, and replay selected evidence separately. Preserve every failure and
   missing/not-run outcome. BM25 raw scores are not vector0.65 or semantic correctness.
4. Prove the application/evidence/citation path using deterministic generation fixtures.
5. Required exact-head CI and independent final review; report combined S2 acceptance
   only after these checks. Resource/profile compatibility failures remain explicit blockers.
