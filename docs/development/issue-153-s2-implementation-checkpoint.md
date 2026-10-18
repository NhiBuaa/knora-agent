# Issue153 S2 — implementation checkpoint (incomplete)

Date: 2026-10-16 (Asia/Saigon). Parent implementation gate: S2.1 `e78a3b5`,
[exact-head CI success](https://github.com/NhiBuaa/knora-agent/actions/runs/38748177861).
Whole-plan owner approval: PR203 `1346b7c`,
[execution record](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6199183792).

## Latest takeover state — uncommitted implementation

### CI correction — 2026-10-19

The implementation was committed/pushed as `71b25fe` after owner approval of the
108-file packet. Full hosted [CI39119161527](https://github.com/NhiBuaa/knora-agent/actions/runs/39119161527)
failed six Ubuntu cases and two Database cases; Frontend, Windows and Keycloak passed.
The owner approved the minimal correction and another commit/push/full exact-head CI:
strictly pin both the historical CRLF chunk bytes and the equivalent LF Git blob,
route the real PDF fixture and Windows worker-environment check to required Windows
CI, and add the persisted `derivation_kind` to the dense roundtrip test double.
No frozen file, historical hash, extraction hard limit or assertion was removed.
The new byte-pin regression rejects changed content, whitespace, mixed line endings
and BOM. Fresh hashing confirms all 206 protected inputs unchanged. Independent
review and the focused 88-case regression found no remaining defect. Local S2
runtime/database remain stopped; Database verification belongs to hosted CI.
Earlier uncommitted-state descriptions below are chronological records.

HEAD remains `4e0134d760def994197678da1aef148a179272a7` on the existing branch/worktree.
The changes below are local and uncommitted; historical CI does not cover them.
Earlier resource observations and implementation descriptions below are chronological records.

### Final verification checkpoint — 2026-10-18, after Q20

All S2 source below is still uncommitted on4e0134d; no remote update is implied.
The Q20 window was closed early at09:26UTC after all three owned containers were
verified stopped. Only its own watchdog task was removed; volumes and reports remain.
Restart requires new runtime authority (`runtime-q20-20261018/closed.json`).

Fresh verification on the maintained worktree, with explicit source pinning:

| Check | Evidence | Result |
| --- | --- | --- |
| Backend CI partition | `final-backend-fixture-20261018.xml` |1774passed/922deselected; existing evaluation Python3.13.15, optional dependencies already installed |
| Lexical retry/rollback/readiness selection | `retry-worktree-20261018.xml` |106passed, including16new retry cases |
| Full frontend unit selection | `final-frontend-complete-20261018.xml` |482passed/54files;234maintained/TEMPsource byte hashes match |
| Frontend lint/build/typecheck | retained TEMPsource, existing dependency junction |pass; three existing img-element lint warnings |
| Root Ruff format/check/lint |464Pythonfiles |pass |
| Default/S2 Compose config, generated OpenAPI | config-only/exporter check |pass; no service startup |
| Protected inputs | `final-protected-inputs-20261018.json`, fresh rehash |206unchanged, including frozen/BaselineB inputs |
| Windows CI partition | `final-windows-pinned-20261018.xml` |242passed/2454deselected in5m41s; worktree source pinned |

The first broad optional-dependency run had1773passes and one test-harness failure; the corrected full backend partition had1774passes.

The offline Database CI partition is intentionally non-accepting: without an active approved S2 PostgreSQL service, its guard recorded222 failures/74 errors/368 passes/12 skips. These are expected connection-denial outcomes, not a product regression; no developer DB or new runtime window was started.

The first broad optional-dependency run also had a harness failure because its global HTTP guard blocked the local lease-loss fixture's own GET127.0.0.1/blocked.
The TEMP runner now permits only that exact fixture method/host/path, keeps other real
HTTP and all non-memory DB connections denied, and the full1774case partition passes.
No product change or test suppression was used. Both attempts are retained. Earlier
missing-dependency collection failures are superseded for these partitions by the
existing evaluation interpreter; they are not erased from the record.

Acceptance map: S2.2 two jobs/parent linkage/revision fencing/recovery/public readiness,
S2.3 pinned native parity/isolation/finite profiles, and S2.4 saved all60 retrieval comparison
plus fresh HTTP application proof have implementation and scoped evidence recorded below.
Q19 cleanup and Q20 real-reprocess rollback now have native private-fixture proof. Final
whole-suite/new-head CI and the owner's integration choice remain gates; no merge/deploy,
semantic-quality acceptance or arbitrary-PDF profile support is claimed.

Owner chose to keep S2 local runtime and database tests stopped after Q20.
GitHub-hosted full CI, including Database, may run only after approval of the
proposed commit/push. Hosted CI does not establish new S2 runtime acceptance.

### Q20 runtime and retry correction — 2026-10-18, latest

Exact [ACK6248144459](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6248144459)
was read back for route packet `18af4e3fbda07d07418b4f6970f2032f41d19c8c976266ff5242730da4130201`
and retry round2 `115d80b99c3df88c3246a4a3b8e9ec09354268cb36cd6904da9de7ccde0c00db`.
Both exact candidates are applied. Git apply changed the route file's line endings;
the file was normalized to the ACKed candidate bytes and its raw SHA verified before runtime.
The runtime runner retained its original deadline; no new admission or extension was created.

Q20 application fixture passed1test in3.79s with two real PDF extractions,16native calls,
zero retrieval queries and zero generation/embedding/provider calls. Reprocess A creates a
new parent and exactly one child C; enqueue CAS reserves revision4 and activation publishes5.
B is rejected before and after C; same-key replay returns the original rollback; a stale
revision returns409. Only this fixture's obsolete A points were removed; C points were
restaged and read back after that cleanup. All54 pre-existing ingestion-job JSON projections
are unchanged (before/after SHA `44f8b19b0cabe6b322f74125d5e223967f714d3e1676d7afa0353d57988c4997`).
Evidence: `runtime-q20-20261018/rollback-native-attempt3.xml` and
`rollback-application-8651fe7635044b14ae85dab458affadd/report.json`.
Both owned runtime containers were stopped at09:18:28UTC, volumes/evidence retained.

Correction to the preceding continuation record: the405 upload attempt performed six native
collection-setup calls during app construction, before the failing upload; it performed no
extraction/query. Its report remains unchanged. Across all three Q20 attempts the retained
reports contain22native calls, below the40call limit. `attempts-summary.json` binds their hashes.

The retry packet above supersedes the unapproved round1 packet `0d5e7ade…`. Final independent
review found no blocking issue after16 new cases covered desired-B identity, reserved revision
and negative provenance. Exact source application was verified, then106tests passed on the
maintained worktree (`retry-worktree-20261018.xml`). This is offline proof; it is not database
concurrency acceptance. Root Ruff now checks464files successfully. No new commit/push or
exact-head CI is inferred. The optional-dependency collection gate is being rechecked using
an existing evaluation environment, pinned to this worktree, with real HTTP/DB connections denied.

### Q20 application and final review — 2026-10-18, continuation

Exact Q20 source ACK6247908659 was read back; all14 bases/candidates and patch
`ce1693343e38f4696e6eb4385d54e1727e988610b8340f1951a83d189e0f5755`
were verified before application. The source is now applied, superseding the pending-source
statements below. Worktree-source offline selection144passed; root Ruff463files, frontend
and shared formatting, TypeScript and OpenAPI exporter checks passed. The full backend
partition initially returned1195passed/9failed: seven ambient SOCKS/dependency failures,
one Windows multiprocessing launcher failure, and one collection-contract failure. The
144test rerun with a real script entry point, pinned worktree source and proxy-free
environment passed the bootstrap/extractor cases without production changes or real
HTTP/DB connections. Full collection remains blocked by missing `deepeval` and `ragas`;
the retained log is `offline-collection-20261018.log`. No dependency installation or
full-suite/CI success is inferred.

Final frontend unit execution used a byte-exact TEMP source copy and existing dependencies.
Its initial471passes/2failures/1collection error exposed missing external fixture files
in that copy. After copying the four unchanged repository fixture/script dependencies,
all20 tests in those three affected files passed; source and product behavior were unchanged.
Both JUnit attempts remain retained. No browser/visual acceptance follows from unit tests.

The previous runtime window expired07:51:38UTC. Owner explicitly authorized a separate
Q20-only30minute window and waived only its8GiB free-RAM gate. Fixed new admission deadline
is09:30:38.540761UTC; owned PG/Qdrant caps, volumes and loopback ports remain unchanged.
Migration0156 applied only to isolated S2 DB; retained ingestion-job projections are unchanged
apart from the new nullable column. Attempt1 aborted on retained processing work before
native calls. ACK6248015911 then isolated this fixture's worker from global expired recovery,
while preserving real claim/lease/extraction/finalization, retained queued/retry locks and
full old-job hashes. Attempt2 reached upload but the fixture's incorrect `/documents/pdf`
URL returned405 before native calls. A finite one-line correction to real `/documents`
is pending ACK (patch18af4e3fbda07d07418b4f6970f2032f41d19c8c976266ff5242730da4130201).
All services were stopped after each attempt; no retained job was repaired or processed.
Artifacts are under `runtime-q20-20261018/`, including both failed reports and migration receipt.

Independent final review found lexical reprocess could reuse a successful extraction with a
failed child, or collide with a prior job fingerprint on repeated retry. A three-file TEMP
fix preserves upload deduplication/dense behavior, follows the explicit desired child,
reuses viable in-flight extraction, and gives fresh lexical reprocess work its own persisted
identity while retaining external replay identity. Regression6RED followed by102PASS;
packet `0d5e7ade551f7c2079fbc01f25c33c5a0b28c66cea923bc2d0d4dfbb8a8d9da9`
awaits exact ACK before application. Remaining gates: runtime Q20 proof, retry fix/review,
full required test/CI evidence, and final integration choice. S2 remains incomplete.

### Latest continuation — Q19 source applied; closure still incomplete (2026-10-18)

This section supersedes the earlier pending HTTP/lifecycle-fixture statements below.
[ACK6245501444](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245501444)
was read back and the exact lifecycle and Windows HTTP packets were applied. The retained
HTTP extraction retry resumed using the original object bytes at the same key, with API in
its capped container and the existing Windows worker. Actual loopback HTTP upload → two jobs
→ lexical readiness → deterministic answer/citation → archive503 passed (1 test,10.35s).
Evidence: `runtime-20261018/http-resume.xml` and
`http-application-55402903456e4af394b8fe25851761cb/report.json` under the runtime20261018
artifact root. The separate failed `http-application-bac1f01f715445a6a3f44a7e77f486f8/report.json`
is retained unchanged, with its hash bound by the successful resume report.
The three Q8 lifecycle tests passed after their finite-population fixture correction.

Owner Q19 approved explicit generation cleanup, without a third ingestion job. Exact six-file
round3 patch `a3384de2b81aaa3c0f93279f8840cecff855125986bf0316103f50e4a9b7cf2e` received
[ACK6245725578](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245725578).
All bases and candidate hashes were verified before application. CLI:
`python -m knora.adapters.cli.cleanup_lexical GENERATION_ID`, using the explicit reviewed
lexical configuration, population manifest, Qdrant URL and collection. Workspace/Document
lifecycle locks precede head and refreshed generation row locks; either current head pointer
retains the generation. An old row status is not a current serving pointer. Missing/changed
authority fails closed. Only deterministic generation point IDs are removed, by native
`POST /collections/{name}/points/delete?wait=true`, requiring completed. Errors propagate out
of the transaction; a later explicit invocation may retry. Accepted runtime points/collections
are retained. Worktree verification:52 offline tests passed, Ruff format/check passed459files.
JUnit: `runtime-20261018/cleanup-offline.xml`. Round1/round2 cleanup packets were not ACKed;
round2's manifest encoding defect was detected before source application and is withdrawn.
The new private runtime fixture `backend/runtime_test/test_s2_cleanup.py` uses only its own
UUIDs/collection. Exact fixture ACK6245758425 preceded its native run:1passed in1.90s,
16reserved native calls/16responses/3delete calls/0queries. Evidence:
`runtime-20261018/cleanup-native.xml` and `cleanup-df7781215e8b426fbff54b34920d5532.json`.
No accepted application/frozen collection was deleted.

Other fresh checks:389 selected S2 offline tests and13 document/operator BM25 UI tests passed;
frontend/shared format checks, TypeScript typecheck and OpenAPI exporter check passed.
S2 Compose config passes with its required private object-root variable; omission correctly
fails interpolation. HEAD remains4e0134d; these results are not new exact-head CI evidence.

The parent-link race fixture initially omitted terminal lifecycle fields. After correcting
only the private fixture, its first race passed once. A queued row left by an earlier failed
fixture setup then prevented further queue-based runs. It was not deleted, terminalized or
claimed merely to make tests pass. Failed attempts and JUnit files `parent-link-rerun*.xml`
are retained; subsequent structural fixture rounds are retained separately. Exact round3
[ACK6245848298](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245848298)
pins SHA8452d3c7148af01c3a8eb838de3fcf45e90ee42de60988822ab4f79ec854a373.
Both actual trigger/lock races passed in0.58s. All51 pre-existing ingestion-job JSON projections
hash identically before/after (`340295b3f5caa25b4154300a2f48f55d409645e7c38a9af947c0d34de27e744d`);
only3new terminal structural rows were added. This proves trigger serialization, not worker
processing. Evidence: `parent-link-structural-round3.xml` and matching report JSON. Earlier
rounds failed setup (NULL ChunkSet parser/normalizer, then missing child started_at) and remain
retained; product constraints were unchanged. Existing recovery selection
had11passing tests; public readiness6passed independently.

Watchdog PID50048 was later confirmed absent, with its last heartbeat at04:11:39UTC. All three
owned containers were stopped early by verified IDs, retaining all volumes and evidence;
receipt `runtime-20261018/early-stop-watchdog-absent.json`. The original window deadline stays
07:51:38UTC. A replacement stop task uses that same fixed deadline, not another four hours;
its live handle must be checked before any further owned-runtime execution. No developer DB
repair, corpus/gold/Baseline B change, provider call, merge or deployment occurred.

At04:57UTC all three owned services were verified stopped after these tests, volumes retained
(`early-stop-after-q10.json`). Scheduled watchdog39332 retains the original deadline for any
admitted later execution; no additional window is inferred.

Owner Q20 now approved the corrected rollback: reprocess extractionA through same_as_job,
perform real extraction plus a new child to createC; CAS revision at enqueue and verify current
source/profile/lifecycle eligibility. The initial extra-child-under-A proposal is withdrawn:
each extraction must have exactly one index child. A TEMP candidate and17new offline tests
exist; source is not applied or ACKed yet. No frozen PDF reparsing is authorized for this proof.

Remaining: Q20 shared packet/ACK/application and runtime proof; final requirement audit/review,
commit and exact-subject CI/integration gates.

Artifact root: `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/`.

### Q16 applied; runtime source review and HTTP delivery preparation — 2026-10-18

**Latest runtime results (supersede preparation/failure status below):**
[ACK6245403965](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245403965)
was read back and applied with exact base/candidate hashes: lexical operational errors now map
to HTTP503; restore uses explicit Chunk→ChunkSet→DocumentVersion→Document identity joins.
The actual combined upload/all60/error-regression rerun passed3tests. All60 attempt2 completed
with exactly60 native queries,82total native API calls, one47-point PUT, zero operational
failures and all206 protected input hashes unchanged. Attempt1 remains retained with0native
calls. No further all60 rerun is needed.

Successful artifacts under `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261018/`:

- `frozen-parity-18357b4ff7df4dee8b93c336196fa591.json`:47chunks/7083upstream tokens,
  new finite profile, exact hash identities and TF tolerance2e-6.
- `upload-application-30345400afcb490a972593075cd6c978/report.json`: actual production
  composition through TestClient, Windows PDF extractor, native PG/Qdrant, two jobs, readiness,
  one deterministic generation/citation and archive503. This is not real network delivery.
- `all60-3b06ec7fc57a4c75b16e9c9d64dc2df1/report.json`: retrieval-only passed; SHA256
  `6a5c41bc3133342706c599fd67dab4366d90d9757c72733132992ad717631ebe`.
- Same directory `comparison.json`: SHA256
  `64a27004c18bb5faceb57f79d71b60824a7fd9bf9cacf4395d73eaa07bc56f56`.
  Full evidence-group coverage is BM25Top8=34/35, selected=34/35; B candidate=8/35,
  selected=8/35. Covered groups74/75 versus11/75. Case037 remains empty in both systems.
  All60 cases remain:35evaluable,17extraction/mapping missing,8controls;47chunks,61mappings,
  25missing anchors remain fixed. All8controls return BM25 candidates/selected evidence;
  generation was not run and no semantic/refusal quality improvement is claimed.

PG/native/readers selection:29passed,3failed. The three Q8 lifecycle fixtures omit the new
finite population, so the production read fence rejects before the intended lifecycle mutation.
TEMP one-file fixture correction is pending exact ACK; production fence remains unchanged.

Real loopback HTTP delivery attempt is retained incomplete in
`http-application-bac1f01f715445a6a3f44a7e77f486f8/report.json`. Upload202 succeeded; extraction
attempt1 safely scheduled retry with `PDF_EXTRACTOR_UNAVAILABLE`. Container cgroup2 is mounted
read-only, so the hard child-memory controller cannot be installed. Queue/job history remains
intact. Owner Q18 approved keeping API in its capped container and using the existing Windows
worker with a private shared object-store bind, without privileged access or weaker limits.
Compose/test candidates await finite ACK; resume must use the existing retry, not DB repair.

**Runtime resumed by explicit owner instruction:** the owner waived the8GiB free-RAM gate
for this run after its conservative basis was explained. Other caps/ownership/quota limits
remain. Start `2026-10-18T03:51:38Z`, hard deadline `07:51:38Z` (14:51ICT), watchdog cleanup
three minutes early. Initial available RAM6.43GiB. Independent hidden watchdog PID50048
records host memory; window/admission receipts are in the new runtime20261018 artifact folder.
Never restart/reset this deadline.

Read-only preflight found revision0154,27 legacy lexical-index jobs without parent lineage
and five processing jobs. Owner Q17 approved dumping and retaining the old database, then
creating an empty same-name S2 database. Dump `pre0155-pg-dump.custom`,513695bytes, SHA256
`911491955a84932930fe5dd8659f9d966e4fae7165b1fb133ce654292a0e06bb`; pg_restore TOC checked.
Old DB is retained as `knora_153_s2_pre0155_20261018`; fresh `knora_153_s2` migrated from empty
through0155 successfully. No parent backfill/deletion or developer database access occurred.

New finite frozen47 native vector parity **1 passed**. Fresh upload TestClient/native run
reached successful extraction/indexing, readiness, answer/citation and fixture vector parity,
then failed because archive rejection was HTTP400 instead of approved503 (same operational
error code). Failure retained. Root cause: main's KnoraError mapping lacks the lexical code;
finite one-line TEMP candidate has RED→GREEN regression plus13helper tests (14pass, DB/HTTP
denied), pending shared ACK. Actual main not yet changed for this fix.

All60 attempt1 failed during restore, **before any native API/query**: ambiguous implicit
DocumentVersion→Document join. Transaction rolled back; failed artifact retained. Private
restore helper now has three explicit identity joins; actual query compiles under PostgreSQL
without connection and existing13helper tests pass. Updated helper snapshot SHA256
`0707f41f872bba005073ab4fd91d137a197413c027cad62fa028d297d19d2381`, pending source review.
One initial plus two replacements remain the total limit; do not erase failed attempt dirs.

**Latest admission, 2026-10-18T03:39:52Z:** Workbench reports its separate window closed.
Fresh S2 preflight still fails the RAM gate: **4.64GiB free**, disk36.94GiB, all three ports
unused. Both exact stopped container IDs, pinned image digests, volume labels/mounts, caps,
checkout/config labels and disabled Qdrant telemetry verified using the explicit local daemon.
Evidence: `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261018/resource-preflight-b566757d8e1c4b7893c329cd1be7160e.json`.
No image build/start/migration/DB probe/native query/HTTP delivery occurred. Extra4h window
remains unused; owner was asked to free RAM to the existing8GiB gate. Root Ruff format/check/
lint now passes455files, OpenAPI artifacts current. All local implementation remains uncommitted.

Q16 is now applied under
[ACK6238368092](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6238368092),
with exact patch/base/candidate/result hashes verified. Actual selected offline checks:
**84 passed**, DB and real HTTP denied, attempts=[]; root Ruff format/check/lint passes
(453 files at that checkpoint). These are not new native/runtime results.

The nine-file runtime source round2 and application Compose snapshot have
[finite ACK6245182363](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245182363).
Manifest raw SHA256 `fefa628c8650119f810ce51424f208e2db206a771865990f4ddc01904cde776e`;
Compose LF SHA256 `5763fd33fee2978b7102c2013af8450464ae80dde66e3055484e727563344e8e`.
Actual/snapshot pins were reverified after readback. Four source findings were corrected:
connection query overrides, mutable archive-manifest trust, replay Chunk Set lineage and
unpinned JavaScript launcher/Murmur reference. Negative checks were observed RED then GREEN;
21 guard/restore tests also passed independent review without DB/HTTP. Round1 is superseded.

The prepared all60 test restores only the fourteen represented sources and all47 frozen
chunks; it retains the other two sources explicitly as lacking frozen chunks. It stages one
47-point PUT, verifies each generation's receipt before its activation and dispatches exactly
one production native Top200 for each frozen B query. No all60 query has run here.
Prepared native parity (two cases), upload application and all60 tests are collect-only.

Combined Workbench/S2 round2 has root finite
[ACK6245141363](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245141363):
patch SHA256 `f8b23154c6246d2800ce8271a7edd0a1bba6aeb82d89c7e9c00f5653cee5b421`,
101 selected independent offline tests pass, no DB/real HTTP. This is source review only;
the combined patch and merge revision0052 have not been applied to this S2 worktree.

`docker-compose.s2.yml` now contains the deterministic finite-upload application profile,
owned objects volume, loopback18053 and existing worker CLI invocation. Config validation
passes; no image was built. New `test_s2_http_application.py` prepares the real HTTP delivery
check outside TestClient: one fresh upload, exactly two worker CLI calls, parent/child polling,
lexical readiness, deterministic answer/citation provenance and archive rejection.
One test collected. Initial source `a9bb70f...` was rejected for inherited Docker routing.
The replacement pins the observed local Docker Desktop named pipe, removes Docker/Compose
ambient overrides, inspects the owned application identity/source labels/caps/loopback port
and finite deterministic settings before seeding, then executes the worker on that exact
container ID. Six missing-guard tests were RED; seven admission cases now pass. HTTP round2
manifest is in `knora-s2-runtime-source-review-20261018/http-round2/`; runtime source LF SHA256
`e027024729bee5c213d6d560f2528f6e7b95afd76539997f2d66294a12eac07b`, unit source
`fc691d5a9785ed246929c89c127351afa6af63257614f58c682a4d5c413ef5fd`, now approved under
[ACK6245247508](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245247508).
Readback and both actual/snapshot hashes verified. Independent seven mocked admission tests
pass with real subprocess/socket/DB/HTTP denied. Image ID format/recording does not establish
build provenance; the freshly built application source/image still needs admission evidence.

Broader offline backend partition: **1179 passed, 10 failed, 846 deselected**. One failure
was an in-memory SQLite connection denied by the TEMP guard; seven were ambient proxy
configuration in provider construction (no dispatch). Correcting only the TEMP harness
allowed SQLite `:memory:` and cleared proxy variables; targeted rerun **59 passed**, real
connection attempts=[]. The CI collection test remains blocked by locally absent optional
DeepEval/Ragas dependencies. No dependency was installed and no provider was called.
The last failure was the old exact two-file Compose inventory. Its finite patch
`5273e1afe8f66a2fcd6ea397b678a7530ea4e46f48f5788cea9034b974641fd7` is now applied under
[ACK6245227106](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6245227106),
with base/candidate/result hashes verified; production exclusions are unchanged. The actual
inventory/admission/guard/restore selection **29 passed**. Root Ruff (454 files at that
checkpoint), shared format/check and Compose application config pass; HTTP remains collect-only.

The extra four-hour S2 window has **not started**. Workbench has a separate short resource
window; S2 waits for its cleanup and a new full resource/ownership/port preflight. A prior RAM
observation reached8.12GiB, which does not authorize a later startup without rechecking.
Migration0155 is still unexecuted. Read-only legacy lexical-index counts must precede it;
do not fabricate parent lineage, remove retained rows or modify the developer database.
Current offline Alembic graph has one head0155 (no DB connection). Retained tokenizer WASM,
launcher and Murmur references match all expected byte pins. Both owned containers remain
stopped with exact pinned images, resource caps and loopback bindings; volumes retain the
expected project labels. Latest observed free RAM4.62GiB remains below the admission gate.
A separate TEMP deadline watchdog is prepared and ownership self-check passes without Docker;
it has not been launched and does not start or remove any service or volume.

### Historical Q15 applied; Q16 retrieval-only runner candidate — 2026-10-18

Q15 round2 below is now **applied** under
[ACK6238204819](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6238204819).
All18 base/candidate/result LF hashes verified. Actual selected backend checks **46 passed**,
two existing dependency warnings, DB connections denied. Root Ruff format (447 files unchanged),
format check/lint, frontend format/check and OpenAPI exporter check pass. These checks do not
establish runtime acceptance. New `test_s2_upload_application.py` is **one collected test only**:
production upload/two-job/native/citation/archive path prepared, not executed.

Owner Q16 approves frozen B retrieval queries, including saved follow-up context, for all60;
one native Top200, primary Top8 and existing selector, no generator/provider. Captured in
Hindsight before implementation and recorded in CONTEXT/ADR0019. Finite **TEMP-only** candidate:
`C:/Users/NhiBuaa/AppData/Local/Temp/knora-s2-all60-review/round1/q16-ACK.patch`, LF SHA
`ee47a63f98ac409ca02adee6c65c302b2f8a78f3e50bfe4a00e7a82865a2f016`.
Two files: existing PDF runner and new retrieval-only tests; sibling manifest pins both.
Seven tests RED for the missing function, then **63 passed** with existing PDF runner tests,
candidate import asserted and DB/real sync/async HTTP denied. Ruff format/check and actual
`git apply --check` pass. Request sent to replacement158 for finite #192 ACK; shared runner
unchanged for Q16. Saved identities/context are checked before dispatch, unresolved dispatch
stops before further queries and retained failures never auto-retry. JSON replay initially
differed on tuple/list representation; returning the persisted observation resolved this.
An initial TEMP Ruff command used defaults; rerun with repository configuration passes.

Latest resource observation: **7.12 GiB** free RAM, below8 GiB gate. The approved extra4h
window has **not started**; owned services remain stopped. No migration0155, new-profile
native verification, fresh upload application test or all60 native batch has run here.

### Owner Q15 and finite public polling/UI candidate — 2026-10-18

Q1–Q15 are approved. Q15 adds read-only derivation kind and preserves extraction retry profile:
`same_as_job` before a desired generation, otherwise `current` using desired B. Recorded in
CONTEXT/ADR0019 and Hindsight before implementation. No additional runtime acceptance follows.

Reader round1 below is now **applied** under
[ACK6237979052](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6237979052).
Verified patch/base/candidate/additional/result LF hashes; actual offline reader/snapshot
selection **13 passed**, database connections denied. A first selection accidentally used
`-k not postgres`, selecting only one test; the 13-test rerun removes that filter.

**Historical Q15 round2 candidate, now applied as recorded above**:
`C:/Users/NhiBuaa/AppData/Local/Temp/knora-s2-q15-review/round2/q15-ACK.patch`, LF SHA
`0b6e21365c69fdff552ac2f4a1a694193fc78ccf0cb7d18d433e93ca492a4215`.
Its manifest pins 18 bases/candidates and dependencies.
Besides kind, the response exposes `desired_lexical_generation_id` so UI does not infer its
absence from a new extraction having no child. Fixed a discovered integration gap in TEMP:
job status/payload previously left indexing/lexical fields at defaults. Candidate reuses the
document reader in a repeatable-read snapshot for BM25 serving, queries the requested job's
explicit child, keeps upload status/identity and continues polling while that child is active.
Population is injected into the job-store reader. No Qdrant/HTTP inside the snapshot.

Evidence: four new backend tests RED before implementation; combined TEMP selection **46 passed**,
two existing dependency warnings, all DB connections denied. UI three Q15 tests RED before,
then **72 passed** with existing document management/state tests. TEMP npm format, format:check,
typecheck, Ruff and exporter --check pass. One new owned-PG projection test **collect only**,
explicitly synthetic receipt, not native/application E2E. The first TEMP backend broad run lacked
the unchanged frozen chunks fixture (27 setup errors); copying that input unchanged resolved it.
Round1 patch container lacked new-file metadata and failed apply-check; retained it. Round2
only adds those headers, all 18 candidate contents unchanged; git apply --check passes.

The approved extra four-hour runtime window has **not started**. Latest free RAM observation
at 2026-10-17T17:55Z was **7.38 GiB**, below the 8 GiB gate; owned containers remain stopped.
Runtime/migration0155, native profile verification, fresh application E2E and all60 remain due.

### Owner Q14, integrated contracts and reader review — 2026-10-18

Owner Q1–Q14 are approved. Primary `retrieval-bm25-top8-v1` binds the frozen47 profile;
`retrieval-bm25-upload-fixture-top8-v1` binds the separately measured upload fixture profile.
The diagnostic ID/profile remain historical and immutable. Earlier pending Q12/Q13 entries
below are superseded. No approval establishes runtime or quality acceptance.

Read back [ACK6237470135](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6237470135)
and [ACK6237671687](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6237671687).
Verified all patch/base/candidate/additional pins, applied in order, and verified every result:

- Q9 round3, nine files: `63a103f2e8e7f90d135bd7bf62fa28ebedd880ea62a367b847345ca6bfb278c9`.
- Serving round2, eight files: `212c6980c6ab90d5b6d4de0b3b8acd99f877e5aeedf637fb0aa02a1a98a1a7e1`.
- Composition round1, five files: `d31d698a2e0342099f8019c0e78607734326f50e0904ea5c287b347dab8348d8`.

Q9 round2 and serving prior `cb1b39…` packages are withdrawn. Main now has opt-in finite
settings, native lifespan/client cleanup, HTTP extraction configuration and two-job worker
wiring. Dense remains the default. Before-generation and trace-commit checks, retrieval
boundaries and public availability call the complete population guard. A native write or
offline readback is not runtime readiness. The two scoped `.gitattributes` lines also have
finite ACK6237470135; JSON LF/PDF binary attributes preserve these new artifact pins.

Actual worktree Q9/serving selection: **181 passed** under SQLAlchemy connection denial.
The first integration run had179 pass/two failures: a private Q8 test caller still used the
old diagnostic profile, and Windows extraction could not spawn from a stdin harness.
Updated that caller to the approved Top8/profile; used a guarded file harness with repository
imports. No product behavior was changed to bypass the failures. The intermediate file
harness needed its repository root import path corrected; the final181 run passed.

Private manifest/config checks previously passed40 tests; real full-content serving checks
are separate from structural mocks. Frozen manifest LF SHA is
`5d9ddeec5aca02d0ceabaaebe7ae867ba895fc1e8cf67e13859fbd0923b7fe60` (creation CRLF
byte SHA `8e3f437eae9eba63de373d20214a520d44b644e9bc4051481cd87512b00a328f`).
It binds14 represented sources,47 chunks and7083 retained native token counts. Count bridge:
`C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/retained-population-counts-b527b99898794cfbb3e89a12722d2c43.json`,
raw SHA `dcb8efe51096fe82e8226918d239d6288e9b7eca153b81b00620f68844fff2c2`.
Its retained native evidence is `frozen-parity-ec80d5cda5fa445d8ed848807d9d3f89.json`.
No historical corpus/gold/Baseline B bytes were edited.

The new `evals/fixtures/pdf_retrieval_v3_s2/refund-policy.pdf` production extraction yields
one chunk. Its pinned upstream counter artifact records7 native tokens with
`native_server_verified=false`. Fixture manifest LF SHA
`e29bd9a22e6cabbf5e2ffd8580f006801470886859801469b3fe68ae422869a0`; counter SHA
`890dacd4662d65167237a700056964d9c81533ec6bfa8ae2f136eee55cac9017`; PDF SHA
`4ab63c9a21e8e2cb43e041df7ea02909df9726a521cd6acdea22f3483ed9c6ec`.
These are extraction/count evidence, not Qdrant population verification or application E2E.

**Pending finite reader round1**, TEMP only:
`C:/Users/NhiBuaa/AppData/Local/Temp/knora-s2-reader-review/round1/reader-ACK.patch`,
LF SHA `fbedb37762dec0d9b91b9f2de494205600e11ade80bd7117b80c6aab308dcf75`.
Six immutable candidates add PostgreSQL BM25 trace/PDF projection in a consistent authorized
snapshot, inject population into operator/main, and test the wiring. Dense default path is
preserved. TEMP combined offline selection **111 passed**, three known dependency warnings,
actual candidate imports asserted and all DB connections denied. Four new PG reader tests
**collect only**; they explicitly use a stub projection/synthetic receipt and cannot prove
native or upload E2E. Sent158 for independent review/ACK192. Shared reader/main delta is not
applied. Q10 race-source correction `d81b9f0e…` now has finite ACK6237470135; both actual
interleavings and0155 migration/replay/rollback remain unexecuted.

Fresh resource observation in this continuation: **6.962 GiB free RAM <8 GiB gate**;
disk41,160,593,408 bytes exceeds10 GiB. No startup or database query occurred. The renewed
four-hour window remains unused; runtime requires a fresh full ownership/ports/caps/resource
preflight. Remaining: reader ACK/integration, document UI/reprocess, bounded CLI/all60,
real migrations/concurrency/native population verification, fresh upload→citation E2E,
required checks/independent review/exact-head CI. HEAD remains4e0134d; all later work is dirty.

### Owner Q12–Q13 and primary contract review — 2026-10-17

Owner approved a separate immutable `retrieval-bm25-top8-v1` configuration, retaining the
diagnostic configuration at200, and a new stable source/checksum/native-count profile pin.
These approvals supersede earlier pending-decision entries. Hindsight initiative recaptured
before implementation. Neither approval establishes runtime acceptance.

Read back upload-readiness [ACK6235046377](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6235046377).
Verified LF patch `214e03e1d894634bf94df15abba21f42ad57d7db232ea983b729a906faf02ee8`,
both current bases, candidate snapshots and applied results. Actual worktree PDF suite:
**54 passed**. Lexical upload now waits for its explicit child and matching served version;
dense and unsuccessful extraction results retain their existing path. No fresh-upload E2E yet.

Q9/Q12 round2 remains TEMP only: nine-file patch
`.superpowers/sdd/s2-approved-resume-q9-q11/task-1-round2-ACK.patch`, LF SHA256
`3729de43267b4f86a8f3810642188e2650d38cf9982c03e85dc3b158d1f9f257`.
Manifest pins current bases and candidate snapshots.135 focused offline tests passed with
TEMP module identity asserted and SQLAlchemy connection attempts denied. Includes primary
Top8, requested adapter limit, contiguous ranks, complete/full-window tie metadata and pure
reader compatibility with historical diagnostic traces. Sent to158 for finite review/ACK192.
The full PostgreSQL BM25 reader and main/settings wiring remain outside this patch.

An earlier overly broad TEMP selection attempted five PostgreSQL reader tests against the
default developer port5432. Authentication failed before any database changes; no repair was
attempted. Subsequent offline selection excludes those tests and installs a connection guard.
This failed run is not runtime evidence. The renewed four-hour runtime window remains unused.
Q10 concurrent tests remain collect-only; fresh-session polling changed their LF source hash
to `d81b9f0ea12b86d6375c9331f173d4e7e1884a2dfa9f6b872e4b471b44cdb569`, sent for rereview.

### Runner and population guards applied — 2026-10-17,21:15 Asia/Saigon

Read back runner round1 [ACK6234801881](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234801881).
Full LF patch SHA256 `70befd4684f3fb7e8c9757dfa6381e4da4ab5c50b09c0e0700dc1c27f29a865c`,
both current bases and candidate snapshots matched before application; both resulting
files matched afterward. The actual worktree PDF suite passed **39 tests**. Saved native
rows now share rank validation/canonicalization with capture projection, preventing rank9
from becoming Top8 through JSON reordering. CLI/all60/application runtime remain incomplete.

Read back population guard [ACK6234899417](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234899417).
Applied exactly four files from
`C:/Users/NhiBuaa/AppData/Local/Temp/knora-s2-population-guard-review/population-guard-ACK.patch`,
LF SHA256 `21b56ce7cf01f1d4395c9c7603950a58899ee8911d8342823213c2f59248cbab`.
All three current bases, all candidate snapshots and all resulting hashes matched.
Extraction success and index staging require a known source SHA, exact ordered chunk
content and matching profile from the finite manifest. Missing or mismatched population
fails terminal configuration before staging. Index validation uses chunk ordinal order.
Dense behavior and loader stale/transport failure classification are preserved.
Private repeated-content fix hashes also match the independently reviewed snapshots.

TDD:11 signature failures, then8 behavioral failures/3 passes before guard implementation;
the corrected TEMP selection passed180 tests. An initial broad TEMP command imported
worktree source through conftest path changes and failed; only the corrected run, which
imports TEMP knora first and asserts its actual module path, is candidate evidence.
After application, the **actual worktree selection passed180 tests** across guard/S2 job,
dense PDF/job processing, private manifest and generation loader cases. New manifest test
counts are explicitly synthetic; no real native artifact or profile pin is approved by them.
Main still constructs the dense handler; future lexical wiring must inject the manifest.
Q12 config identity and Q13 statistics pin remain unanswered.

Added `backend/runtime_test/test_s2_parent_link_concurrency.py` with child-first and
parent-update-first schedules. Each asserts the competing backend actually waits on the
expected blocking PID before releasing the first transaction, then checks final identity
and child presence/absence. Fresh structural rows never enter the worker queue; no retained
lineage is inferred or data removed. **Two tests collect; neither has executed.** Source
review and real PostgreSQL evidence remain required. Root Ruff format/check/lint passed
for433 files before population application; final formatting follows later changes.

Fresh resource preflight at14:09:03UTC failed: **5.214 GiB free RAM <8 GiB minimum**;
disk39.123 GiB meets10 GiB minimum. Owned PG/Qdrant were observed stopped with expected
images/project/ports/caps/volumes; no target listener was reported. No startup, DB query,
DDL or provider call occurred; the renewed four-hour window remains unused. Evidence:
`C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/preflight-resume-140903.json`,
byte SHA256 `ac9f5e48b3b3e3cb05bf26ee900949528451528b26985c6139428ebaacc4a8ec`.
The actual legacy index-row count remains unknown. Preserve the RAM gate and migration
preflight; do not repair records to make tests pass. All changes remain uncommitted.

### Owner Q9–Q11 and review fixes — 2026-10-17,20:55 Asia/Saigon

Owner explicitly approved native complete/full-window tie rules, an explicit extraction parent
for each index job, finite verified population manifests, and one additional runtime window
of at most four hours starting at the next startup. That window has **not started**. Fresh
resource/ownership checks and exact shared ACKs remain required before startup/migration.

Three independent task reviews found defects; none is marked complete. Bounded fixes:

- Q9 TEMP now propagates the actual requested query limit into response parsing, preserves
  full-window ties and rejects sparse/oversized ranks. RED tests reproduced all three faults;
  the adapter/answering selection has **124 passed,3 deselected**. Those three reader tests
  remain red because the metadata companion is missing. Immutable Top8 config identity awaits
  owner Q12; the original diagnostic ID must not silently change meaning.
- Q10 TEMP adds the ORM check and parent identity-update guard, plus real PostgreSQL tests
  for exact parent replay, final-fence rollback and parent mutation. **57 offline tests pass**;
  trigger/transaction tests have not run. The current isolated DB's legacy-row count is
  **unknown**: older assertions were not supported by a saved live query. No lineage was
  guessed and no record removed. Finite eight-file patch SHA256(LF)
  `ef318832867fed6c64e9891fc25fae4bdffba90d43aad9791276d73b2eba82d0`
  was sent to authorized chat158 for review and specific ACK192; not applied.
- Q11 private manifest no longer rejects legitimate repeated text at distinct positions.
  New regression failed then passed; all **23 manifest tests pass**. Frozen-profile statistics
  compatibility remains open under owner Q13; no new native profile/evidence pin is claimed.
- S2.4 runner TEMP preserves native Top200 branch rows separately from post-revalidation
  candidates, primary Top8 and selected evidence. A saved-capture comparison keeps every case,
  failure, not-run, mapping-missing and control. **35 PDF runner tests pass**. Finite two-file
  patch SHA256(LF) `a3746638f86bdf2b78c6e10fdf228c1467ba989238f3ea87a3bedf10a6204d39`
  was sent to chat158 for review/ACK192; not applied or connected to an all60 runtime run.

Candidate artifacts and exact commands are in this plan's ignored SDD workspace and TEMP
directories recorded by its reports. Agent fix dispatches terminated at the usage limit;
controller made bounded fixes and requested peer re-review, which is still outstanding.
Q12–Q13 were asked through grilling and remain unanswered. No runtime/provider call,
developer-DB repair, commit, push or frozen/BaselineB/PR189 change was performed in this resume.

Follow-up: [finite Q10 ACK6234741170](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234741170)
was read back. Patch hash, all eight current bases and candidate snapshot hashes matched
immediately before application; all eight resulting files matched afterward. **Q10 is now
applied locally**, superseding the preceding pending/application note. The actual worktree
selection passed **57 tests**; root Ruff format/check/lint passed for432 files. The three
PostgreSQL test definitions collect successfully but were not executed. The ACK's source
review has no blocking finding; migration replay/rollback, actual legacy-row count and both
concurrent child-insert/parent-update schedules remain required evidence. No database migration
was executed. Runner ACK and Q12–Q13 remain pending.

### Four finite ACKs applied — 2026-10-17,14:10 Asia/Saigon

Read back [ACK6231034695](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6231034695)
before applying retrieval6c432af9, readiness97df47d1, OpenAPI266df2ca and operator
UI8799195e. All four full patch hashes and normalized base/candidate hashes matched
the existing manifests. Applied only the eight supplied files; their post-format
candidate hashes still match. This supersedes the pending-patch statements below.
The ACK excludes Q9 ties, Q10 linkage, later main/reader/schema/validator changes
and runtime authorization.

Fresh checks against the applied worktree:

- **448 backend offline tests passed** across answering, S2 job/authority/submission,
  Qdrant wire/native adapter and HTTP document/operator contracts; two dependency
  deprecation warnings. The database URL was scoped to isolated15433, but this
  selection uses no database fixtures and establishes no PostgreSQL runtime result.
- **78 operator UI tests passed** across all10 operator test files. Frontend format,
  format-check and full typecheck passed. Matching package/lock hashes were checked
  before reusing existing primary node_modules via missing-directory junctions;
  the worktree's existing `.cache` was preserved and no package was installed.
- Root Ruff format, format-check/lint, shared Prettier write/check, both default
  and S2 Compose config checks, exporter `OpenAPI --check` and diff whitespace checks
  passed. Default Compose emitted existing missing canonical MinIO credential warnings.

The formerly RED facade/public-readiness PostgreSQL tests are now pending rerun,
not claimed green. Owned containers remain stopped; the old runtime deadline is
expired. Q9–Q11 and runtime extension remain unanswered. Main/worker/config wiring,
all60, application citation proof, final review and exact-head CI remain incomplete.
All implementation is still uncommitted at4e0134d. Frozen inputs and PR189 are untouched.

### Latest continuation — 2026-10-17, Q8 and isolated runtime

Resumed at06:10UTC on2026-10-17. The existing branch/HEAD and all dirty/untracked
implementation remain intact. Live#192 has no comment after6228374786. All four
pending patches match their recorded patch, normalized base and candidate hashes;
`git apply --check` passes for each, but none is applied without its finite ACK.
Owned PostgreSQL and Qdrant containers remain stopped. The original06:06UTC runtime
deadline has now expired; startup requires a newly authorized window and fresh
resource/ownership checks. Q9–Q11 and runtime extension were presented to the owner
again; no answer is inferred from the instruction to continue. After three resumed
goal turns, the same gates remain: no owner answers or new#192 ACK; replacement
chat#158 is still reported active/inProgress at revision3 by bounded waits. The
resumed goal remains incomplete and is marked blocked pending those decisions or
external coordination changes. Do not restart the live chat merely for unchanged
observation, or restart runtime under the expired authorization.

Frozen input preflight (no services or retrieval) passed. The exact completed BaselineB
packet is `baseline-b-layout-v2-continuation`; the parent `baseline-b-layout-v2` remains
the historical stopped-at001 packet. Rechecked181 archived BaselineB byte hashes and206
unchanged input files, all60 selected saved observations, all47 frozen chunk identities/
checksums,61 approved mappings and25 missing anchors. Existing dataset loading validates
source bytes and PDF page metadata only; no text re-extraction or new chunks were produced.
Recomputed the existing saved coverage:35 evaluable,17 mapping-missing,8 controls; candidate
and selected full-group coverage both8/35. Original failed001 capture and its approved
same-attempt selection were checked separately and retained unchanged.

Evidence: `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/input-preflight-d401e152da4a4ea5b6d0beca793f6199.json`,
SHA256 `bf481acba46ebfc295d4b64ca00db03768a4c163edd1ad4e4d3fcb9ca366e125`.
The TEMP diagnostic script uses existing dataset/binding/coverage functions. Its output
contains source hashes and baseline candidate/selected identities for every60case. It is
input-readiness evidence, not a BM25 experiment, a new evaluation package or a quality pass.
Zero retrieval queries/provider calls; owned containers remain stopped; no frozen file diff.

Blocked audit after three consecutive continuation turns with the same remaining gates:
Q9 native tie/rank contract, Q10 parent/child job linkage and Q11 verified population/profile
binding need owner decisions; four finite shared patches need specific ACKs at#192. Those
decisions gate the remaining main/worker/reader/config/report integration and accepted runs.
Independent recovery proof, operator candidate and frozen-input preflight are now prepared.
Do not keep rerunning passing subsets while these gates remain unsettled. The full S2 goal
is incomplete and is being marked blocked pending owner decisions or new finite ACKs;
its objective is unchanged. Resumption must recheck live ACKs/hashes, preserve all dirty work,
and revalidate resources and the original06:06UTC runtime deadline before service startup.

Operator UI follow-on: a fourth finite patch is prepared in TEMP and sent to the authorized
replacement chat#158 for ACK at#192; it is **not applied** to this worktree. Patch
`operator-ui-ACK.patch` SHA256
`8799195eef6f1bc9951f7c5f6d08b28acbc1b8ddcd665ee7cee6013db38bd488`
changes only `frontend/lib/operator/api.ts`, `frontend/components/operator/TraceView.tsx`
and the new `frontend/tests/operator/operator-bm25.test.tsx`. It accepts explicit null embedding
configuration, retains rejection of missing/invalid types, shows BM25 raw score/contribution
and generation provenance, keeps zero distinct from malformed/missing scores, and displays
null embedding configuration as Not run. Existing dense score rendering is preserved.
The sibling manifest records normalized base/candidate hashes and dependency on pending
OpenAPI patch266df2ca. It does not include generated TS, document UI, backend operator/main,
Q9 ordering/metadata, Q10 job linkage or Q11 population binding.

The isolated TEMP frontend review tree first produced3 expected RED tests, then **56 operator
tests passed** (BM25/state/views/Figma). Prescribed `npm run format` and `format:check` passed.
Full typecheck initially failed because the copy lacked two external repository JSON fixtures;
copying those exact fixtures unchanged into the review tree and rerunning typecheck passed.
The review tree uses a junction to the existing primary node_modules; no dependency was
installed and the worktree's existing cache-only node_modules was left alone. Only selected
finite-patch files are candidates; formatting of other TEMP copies is outside the patch.
No browser/visual/runtime frontend acceptance is claimed. All four patches still require
finite ACK; Q9–Q11 and the full S2 application/all60/release gates remain open.

Final follow-on state: after root Ruff format/format-check/lint and diff-whitespace checks,
the combined recovery/native-recovery/two-job/concurrency selection passed **11 tests**.
Only the two new runtime test files were reformatted; no production code changed in this
continuation. Both owned containers are now stopped again, with all volumes/collections and
per-run evidence retained. Recheck resources and the original06:06UTC deadline before restart.

Latest follow-on at approximately02:40UTC: PostgreSQL was restarted for readiness checks,
then Qdrant restarted for one additional structural crash/replay check. The preflight had
12.28GiB free RAM and40.89GiB free disk, only the owned PostgreSQL15433 listener, verified
owned volume/caps and the pinned Qdrant image digest. The existing06:06UTC deadline remains;
restarts do not extend it. This supersedes the earlier stopped-container observation below.

New real PostgreSQL recovery suite: **6 passed**. It covers expired lexical lease/recovery
replay, a delayed old worker denied activation, source-version replacement and document or
workspace revision cycles superseding loaded work, lost commit-response reconciliation,
and final lease-guard rollback of tentative activation. Receipts in those six tests are
structural fixtures. The combined recovery/two-job/concurrent-CAS selection passed10.

A separate **real native crash/replay test passed**: verified Qdrant readback leaves PG
inactive, the expired attempt is recovered, the replacement reloads the same durable
generation and restages it, PG activates once, and native exact point count remains1.
The native plus PG recovery selection passed7. Sanitized request/response evidence:
`C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/native-recovery-6fcb77708a8c4b6e91edadc428319b63.json`.
This is a structural failure/recovery fixture, not the all60 experiment or application E2E.

The Q8 authority helper refactor passed41 selected offline/PG checks. Three finite patches
remain TEMP-only pending concrete #192 ACK from replacement chat#158:

- Retrieval facade: `6c432af91af6689a24d8a2d9fec6787e49c13de49fdf7f7678e98a46042d3cd5`.
- Public readiness reader: `97df47d173adf95c17a06efd044754a90e71ea3b349671bf43ce316f6785adcb`.
- Exporter-generated OpenAPI/manifest/TS: `266df2ca2d4ab2bc6d03f75e28ff0a690c6ddbb647f60434617d0667e62a0401`.

Each patch has base/candidate hashes in its sibling manifest under
`C:/Users/NhiBuaa/AppData/Local/Temp/knora-s2-takeover-4e0134d`.
Facade and activated-public-readiness tests remain intentionally RED against current shared
files; no candidate is applied or described as production verified. Dense reader8535130 and
7ee019d predicates remain preserved. Q10 awaits owner choice on explicit parent extraction
job linkage; no new column/migration has been added. Q11 awaits owner choice on explicit
verified population manifests versus automatic profile building. An opaque statistics digest
does not establish population binding; frozen47 parity does not authorize arbitrary upload
profiles. Q9 tie ordering also remains pending. Q1–Q8 approvals remain in force.

Follow-on: private active-corpus reader and text/citation hydration passed **9 new real
PostgreSQL tests**, after their missing-method RED runs. They preserve active A during desired
B rebuild and fail closed on archive/revision/profile/foreign authority, text checksum changes
and projection outage. No transaction spans projection I/O. Shared facade opt-in delegation
is still TEMP-only, patch SHA256 `6c432af91af6689a24d8a2d9fec6787e49c13de49fdf7f7678e98a46042d3cd5`,
sent to replacement chat#158 for a finite ACK at#192. Its integration test is intentionally
RED until that ACK permits application. This supersedes e1919e before review: orchestration
now lives in the private answering collaborator `adapters/postgres/lexical_retrieval.py`,
preserving the authority store's no-projection-I/O role. No shared facade hunk was applied.
Q9 asks the owner to settle tie ordering at a full200
native-hit boundary before shared validator/trace changes.

Native frozen vector parity now passed for all47 chunks/7083 upstream tokens, sparse hash
identities and TF weights; see `.verification/s2-native-stage-report.md` for exact retained
artifact and the corrected input-path failure. Qdrant image is pinned by digest. This verifies
the frozen native population only; full60-case evaluation and application E2E remain pending.

Further fresh verification: **97 dense/ingestion PostgreSQL regressions passed** (two existing
dependency deprecation warnings); **2 actual competing-transaction tests passed** for one CAS
winner and revoke versus activation. **2 PG/native integration tests passed**, each using one
real native query and PostgreSQL-authoritative text; archive after the HTTP response rejects
before hydration. These are structural integration, not upload-to-citation application E2E.
Sanitized `pg-native-*.json` evidence is retained in the runtime artifact directory; failed and
successful runs are never overwritten. Latest scoped integration invocation:6 passed,1 expected
facade RED pending ACK. Ruff formatting/check/lint, shared Prettier, Compose config and diff
whitespace checks pass. No commit/push/new CI, provider/judge/export call or frozen artifact edit.

Owned PostgreSQL/Qdrant containers were stopped after this verification batch while Q9 and
the finite facade ACK are pending. Volumes/collections/evidence are retained. Recheck host
resources, ownership/ports and the existing06:06UTC runtime deadline before any restart;
stopping does not silently grant a new four-hour window.

This section supersedes the chronological offline-only statements below. HEAD is still
`4e0134d`; all subsequent implementation remains uncommitted and has no new CI result.

- Owner Q8 approved revalidation immediately before generation and inside trace persistence.
  Exact shared patch SHA256 `f3d5ca3519f434c2fb304dd0394fa05d8543f9ea7c498eeb395af8c0893f8b17`
  received [finite ACK6228374786](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6228374786)
  from the replacement Workbench chat. Verified patch/base/candidate hashes before application.
  Snapshot parsing requires exact six-string generation objects. Lifecycle changes reject with
  `LEXICAL_RETRIEVAL_UNAVAILABLE`; no provider call holds a database transaction open.
- Public DTO/facade declarations and dense reader identities/predicates from8535130/7ee019d
  are applied under [ACK6219125148](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6219125148).
  These declarations do not yet supply public lexical readiness or BM25 reader wiring.
- Docker became available. Resource preflights passed (10.72GiB then9.33GiB free RAM,
  42.69GiB disk); owned project `knora-153-s2` started around02:06UTC on2026-10-17.
  PostgreSQL15433/`knora_153_s2` and Qdrant16433 have separate volumes and the approved caps.
  All migrations through0154 actually applied only to this new isolated database.
  Developer5432 was not altered. The four-hour runtime window ends around06:06UTC.
- PostgreSQL image digest is `ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`.
  Qdrant1.19.2 resolved digest is `b7b0444c4c351c970b98e90a6f89c2ee4287c65b44e52b4cb503fa5b2aa927ad`;
  full frozen-population compatibility is still pending. Its first empty startup logged default
  telemetry enabled; it was immediately stopped and recreated with telemetry disabled before
  any corpus/query. No claim is made that the initial process sent no telemetry packet.
- Fresh real PostgreSQL lifecycle/two-job tests: **16 passed** after formatting. Tests prove
  atomic extraction/one-child replay, rollback on final guard rejection, activation receipt
  checks and archive/revoke rejection between pre-provider validation and trace commit.
  They do not yet prove actual concurrent workers, crash recovery or reconciliation.
- Native structural Qdrant tests previously passed8, with retained sanitized request/response
  evidence at `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017/structural/`.
  The latest combined invocation passed16 PG tests but8 native fixture setups errored because
  the command omitted `KNORA_S2_EVIDENCE_ROOT`; no Qdrant request occurred in that invocation.
  A corrected native invocation is required. Prior structural proof is not the47-chunk/60-case run.
- Other prior fresh checks:55 Q8/BM25/two-job tests passed; dense PostgreSQL suite96 passed,
  one obsolete message-regex expectation failed, then its retained no-mutation assertion passed
  after removing the obsolete exact wording. Full97 rerun remains pending.

Remaining: production BM25 retrieval, public readiness/operator and composition wiring, finite
ACKs for those shared diffs, concurrent/recovery/reconciliation proof,47-chunk native tokenizer
parity/profile freeze, all60-case accepted experiment, deterministic upload-to-citation E2E,
review and exact-head CI. Corpus/gold/BaselineB and PR189 remain outside mutation scope.

### Earlier continuation — Q7 implemented offline

Previous goal turn classified as progress: live Git/PR/ACK checks and independent submission
review identified the next concrete fix. Owner Q7 now explicitly selects the valid **desired B**
profile for `current` reprocess, even while B is indexing and A remains active. Private submission
configuration now follows that rule, validates generation/head/source revisions and chunk-set
provenance, and never falls back to dense or active A. Its deployment injection remains pending
the shared facade/main ACK. `same_as_job` still reconstructs the explicitly selected extraction
job after revocation; an internal index job is not an external extraction command.

Independent submission review reproduced `OverflowError` from oversized persisted BM25 numbers.
Three numeric regressions failed before the decoder fix and now return
`CONFIGURATION_NOT_AVAILABLE`. The dispatcher now routes dense/extraction to the PDF handler
and lexical indexing to its dedicated handler, preserving the cancellation token and outcome.
It is not yet wired into `main.py`. A follow-up regression also prevents missing generation/head
authority from being treated as proof of a stale snapshot.

Fresh combined offline verification: **374 passed** across the S2 coordination, generation,
submission, native/wire adapter, job, answering and retrieval suites. Root Ruff format, format
check and lint pass; `git diff --check` passes. This supersedes the earlier intentionally red Q6
state below, but proves neither actual PostgreSQL transactions nor application/runtime behavior.

Public DTO/schema and facade injection candidates are still TEMP-only. Exact patch SHA256
`eaf7479722dd5ef0edfe3a140bd300991bf380641d4489de37ddd63b26601677` was sent to authorized
chat #158 for hunk ACK at #192; main/readers/OpenAPI/frontend require subsequent actual diffs.
Workbench reader correction `7ee019d4d755fe2adcd8e4a4949671782323d577` was inspected and changes
only the two agreed query predicates plus tests. Porting it together with the8535130 identity
additions was requested; the local S2 reader remains untouched.

Latest read-only preflight: **9.72 GiB RAM**, **39.44 GiB disk**, no listeners on15433/16433/18053.
Docker Desktop status could not be retrieved and its Linux-engine pipe is absent. No service or
migration was started. Recheck resources, daemon, ownership and ports immediately before startup.
Two delegated agents stopped with usage-limit errors; their incomplete dispatch/public proposal
work was inspected and continued directly. Hindsight capture/search for Q7 failed because its
local9077 service refused connection; this document retains the owner decision.

PR204 remains Draft/Open at4e0134d, base feature/issue-153-s2-contracts. PR189 remains Open/ready
at a67842e73959ecf4434ad027abd35983fc08017f. Frozen corpus/gold/BaselineB paths have no local
diff. All implementation edits remain uncommitted; historical CI does not cover them. Q8 asks
the owner to confirm the missing lexical revalidation seam before generation and at trace commit;
dependent application edits have not started. Full S2 acceptance remains incomplete.

- Owner Q1–Q5 approved two jobs, separate public lexical readiness/operator provenance,
  existing retry mapping, coordination with chat #158, and enqueue-time document/workspace
  revision fencing with `stale_derivation_snapshot`. Dense defaults and fingerprints remain
  compatible. Q6 now approves strategy-aware lexical `current` reprocess, preserving the
  explicit kind/profile for `same_as_job` and prohibiting implicit dense conversion.
- Specific two-job ACK: [#192 comment6207179255](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6207179255).
  Exact `tables.py`/migration0154 patch ACK:
  [comment6207569959](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6207569959),
  patch SHA256 `f14692e5126f1910d39456f888da8c3783a02574a5fd9f7e8f33f29062e61b0c`.
  Those exact schema hunks have been applied locally, without running a migration.
- New extraction finalization atomically prepares real chunks, a desired generation and one
  index job; index success revalidates the durable generation in the activation transaction,
  validates the receipt and retains the final database-time lease guard. Offline tests cover
  forged claim revisions, wrong job binding, final lease loss, full extraction fingerprint,
  stale supersession and cleanup. They do not establish PostgreSQL rollback/concurrency.
- Submission fingerprints/reuse bind lexical profile and enqueue revisions while external
  idempotency fingerprints and dense embedding matching remain intact. Strategy-aware
  `current` reprocess is still being implemented; Q7 asks whether its selected profile comes
  from desired or active generation. Internal index jobs are not external extraction commands.
- Generation loading validates durable job, source retention/provenance, completed chunk set,
  complete manifest and text checksums. Review distinguished actual stale snapshots from
  corrupt provenance (terminal configuration); malformed numeric profiles are wrapped.
- Native HTTP staging/query/setup now has explicit completion/readback validation and no
  automatic retry. Invalid compressed responses are terminal; classified transport/408/429/5xx
  failures are transient. Its collection/tokenizer/client/server wire behavior remains unverified.
- Independent reviews found a replay regression: transition IDs are scoped by operation kind,
  but the new success reader queried globally to find stale outcomes. Exact two-hunk ACK
  [comment6217554435](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6217554435)
  permits the migration0154 correction. Verified physical patch SHA256
  `41c7ea5c0b89aba9e5679e852bce5efdd09c5ac0afd7279f988b497e62f65adc` and full candidate
  `a49c11181703a6c73e3b8e079621d289165db49b6a5a4a2906d236094d16e099` were applied locally.
  The LF-normalized patch digest is
  `c525507f2427825173bef5ddd13737eb80ddfbeb21b98c1cf7a9c2ac023e6b25`.
  Superseded success outcomes now retain typed success kinds and replay lookup is again
  exact-kind. **50 offline coordination tests pass**, including same-ID/different-kind replay,
  stale extraction/index success and explicit superseded replay. DB audit rejection and
  rollback/concurrency remain unverified; no migration was executed.
- Fresh verification: **344 passed** across the six S2 offline adapter/job suites plus lexical
  generation, BM25 answering, answering module, retrieval-v2 and retrieval-configuration tests.
  Root `ruff format .`, `ruff format --check .`, and `ruff check .` pass.
  An earlier command with a nonexistent BM25 test filename ran no tests; it was corrected.
  Later Q6 tests are intentionally red (**2 failed, 41 passed** in their scoped submission
  suite), pending the Q7 profile-selection decision. The full current test gate is not green.
- Latest read-only host preflight: **10.96 GiB RAM**, **39.81 GiB disk** free, and no listeners
  on15433/16433/18053. Recheck immediately before startup. No S2 services or migrations were
  started during this takeover. Developer DB5432 has not been changed to satisfy tests.

Public readiness/operator/schema/OpenAPI and composition are still pending exact shared-hunk
ACK. Workbench `8535130` was inspected: its evaluation-reader additions expose raw source SHA,
embedding identity and chunk IDs; these additions are not yet on the diverged S2 branch.
The existing S2 reader blob is `cfbf6e5b66dae87ca45eb3a5d3fea08c3ac57a44`; Workbench
head98df284 has reader blob `393b9869ccf21d0b3bc1ad5ccdee61d13030cd41`. Review ACK was sent to
chat #158 for only its two `read_active_corpus` predicates (unarchived document/completed
EmbeddingSet) and focused tests, reserving that hunk for #158. Later S2 reader edits must
serialize with its verified commit and retain the8535130 identity projections. Runtime
concurrency/recovery, lifecycle integration, pinned native parity, the bounded all60 experiment,
application citation proof, final review and exact-head CI remain required for full S2 acceptance.
Corpus/gold/BaselineB and PR189 remain outside this work's mutation scope.

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
- Required CI for checkpoint head `4e0134d760def994197678da1aef148a179272a7`
  succeeded in [run `38789186498`](https://github.com/NhiBuaa/knora-agent/actions/runs/38789186498).
  Takeover verification checked all six jobs, including `CI required`, and the
  downloaded `ci-subject.json.checkout_sha` against that exact SHA. This supersedes
  the earlier in-progress staging-run observation; it does not cover later edits.
- No full local suite, migration execution, Qdrant query or application E2E claim.

## S2.3 offline native staging checkpoint

The Qdrant adapter now builds, offline only, a one-shard native BM25 collection body, a single 1–64 point staging batch, and an exact persisted-point readback request. It shares the approved `word` profile and NFKC/lowercase normalization with query construction. Readback returns a `StageReceipt` only after exact point count, deterministic UUID identity, profile/checksum/content-digest payload validation; HTTP/upsert acknowledgement alone is rejected. No transport, Qdrant service, collection, migration or runtime activation was performed. Details and tests: `.verification/s2-native-stage-report.md`.

The BM25 policy identifier is now `bm25-unicode-word-v1`; Baseline B's vector threshold and all historical artifacts are unchanged.

Prior-session offline verification: focused S2 tests **272 passed**. The broader evaluation-reader selection was not included in that count because its five tests attempted a developer PostgreSQL at `127.0.0.1:5432` and failed password authentication; no test failure was caused by the S2 code, and no database was modified. Ruff format/check and `git diff --check` pass.

## Takeover — verified state and pending boundaries

On 2026-10-16, the existing worktree and branch were verified at `4e0134d` with
no tracked or untracked changes. PR204 remains OPEN/Draft with base
`feature/issue-153-s2-contracts`; PR189 remains OPEN/Ready at `a67842e` and is
unchanged. The inherited verification counts above are historical evidence,
not a new local runtime result.

The owner explicitly approved the concrete **two-job design** during takeover:
`pdf_extraction` commits the real Chunk Set/Chunks, desired lexical generation
and exactly one queued `lexical_index` job atomically. Index work reuses existing
ingestion claim/lease/retry/history and succeeds only after verified receipt and
PostgreSQL CAS activation. `dense` remains the default and requires embedding
configuration; only the two explicit lexical kinds permit its absence.
Extraction success never means lexical-ready. This is an approved design,
not an implemented or runtime-verified capability.

The [earlier embedding-free ACK](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6199627446)
does **not** ACK that expanded handoff. The
[clarification](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6199682090)
and [explicit two-job ACK request](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6199726211)
have no subsequent concrete ACK at takeover. Shared ingestion/schema edits remain
blocked pending that ACK and verification of the exact follow-on migration parent.

Workbench reader commit `853513092979a16d8883e6ad78131255baecc8c6` was inspected.
It is not an ancestor of this S2 checkpoint. It adds defaulted `raw_sha256`,
`embedding_set_id` and ordered `chunk_ids` to `ActiveCorpusDocumentProjection`
and populates them through the existing dense query, with three test assertions.
It does not support lexical-only binding. Preserve these additions and dense
semantics when coordinating future reader edits. Document/job lexical readiness,
operator nullable dense provenance/BM25 fields, and HTTP/OpenAPI ownership require
a separate concrete contract ACK; no such reader or public schema edit was made.

The owner subsequently approved these follow-on directions during takeover:

- Preserve upload-job identity/status and expose indexing/lexical state separately.
  Resolve served version and answer availability by the selected retrieval strategy
  only after eligible activation. Without embeddings, embedding readiness remains
  `not_indexed`. Operator projections may carry nullable dense provenance and
  supplemental BM25 provenance. Exact public fields and shared ownership still need
  coordination before implementation.
- Reuse RetryPolicyV1: classified Qdrant connection/timeout/429/5xx failures map to
  existing `STORAGE_TRANSIENT`; invalid receipt/profile/provenance/configuration or
  request is terminal configuration failure. PostgreSQL coordination indeterminacy
  retains its existing semantics. Outages never become empty retrieval evidence.
- Contact chat #158 for concrete Workbench ACK at #192. The authorized request was
  sent, explicitly distinguishing the two-job boundary from the public-contract
  boundary. Sending a request is not an ACK; both remain pending until read back.

Fresh takeover preflight: approximately **4.0 GiB free RAM**, **40.12 GiB free disk**,
no listeners observed on 15433/16433/18053. The **8 GiB RAM gate fails**, so no
service startup, migration execution, developer database test or all-60 experiment
is permitted by this observation. Do not free memory by stopping unrelated apps.

Fresh offline baseline: **165 passed** across Qdrant wire, lexical generation,
BM25 answering, answering module/retrieval/trace, PDF runner and dataset contracts.
The S2.3 payload-index follow-on adds offline keyword request bodies for the exact
workspace/generation/profile-digest fields used by both query and IDF filters;
only the workspace field is tenant-marked. TDD observed a missing-method failure,
then **44 passed** in the adapter/generation subset. The same wider offline selection
now has **166 passed**. Root Ruff format/check/lint and `git diff --check` pass.
This is a narrower explicit selection than the historical 272; neither count
establishes PostgreSQL/Qdrant runtime, native tokenizer parity or application E2E.
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
