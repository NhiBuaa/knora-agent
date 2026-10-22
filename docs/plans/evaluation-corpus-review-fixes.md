# Evaluation corpus review fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: dùng `executing-plans` nếu có trong catalog thật của phiên Agy; thực hiện tuần tự theo các checkbox. Không mặc định tạo sub-agent. Skill thiếu thì ghi UNVERIFIED và theo verification contract của repository, không tự cài.

**Goal:** Khép hai findings của review #192 / PR #202 bằng test có khả năng bắt lỗi thật, giữ nguyên dữ liệu và evidence đã chạy, rồi chuẩn bị PR cho review và nghiệm thu riêng của owner.

**Architecture:** Giữ transaction và cơ chế source pins hiện hữu. Bổ sung regression có khóa ngoại thực thi, mở rộng tập file được ghim trong `reviewed_build_pins()`; không thêm harness, workflow hay state store.

**Tech Stack:** Python, pytest, SQLAlchemy, SQLite offline, PostgreSQL integration CI hiện hữu; Ruff; GitHub PR #202.

**Spec:** `docs/adr/0018-knora-evaluation-tool-authority.md`; `docs/development/issue-192-workbench-verification.md`; `docs/development/issue-158-evaluation-verification.md`. Findings và evidence chi tiết ở `<REVIEW_OUTPUT>/review.md`, theo handoff đi kèm.

## Global Constraints

- Knora giữ authority cho dataset/Gold/run/report/gate. Giữ Gold/history/FAILED source; không sửa historical manifest/journal để hợp thức hóa code mới.
- Phạm vi sửa: hai findings, docs kiểm chứng, caller/test trực tiếp bị ảnh hưởng. Không thay model/provider/dependency, retry, quota hay luật admission.
- Gói cũ đã ghi 26 attempts, 3 startups, 7/7 slots COMPLETED. **Không startup thứ tư, replay, reset hoặc chuyển phần 33-26 thành retry budget.** Lượt lập kế hoạch không gia hạn phê duyệt live.
- Ngân sách thực thi kế hoạch này: **0 external inference calls, 0 live jobs, 0 runtime startups, paid USD 0**. Offline SQLite fixture dùng DB riêng trong pytest tmp_path.
- Không mở Docker Desktop, dùng retained L1, đổi permission môi trường, mở UI hoặc sửa tài nguyên phiên khác. CI disposable database theo workflow hiện hữu là evidence khác với live L1.
- Không tự merge PR/main, deploy, close #158, xóa branch/worktree. Tích hợp main bằng merge/rebase chỉ khi có quyền hiện hành rõ ràng; nếu chưa có, hoàn thành độc lập hai fixes trước rồi báo quyết định còn thiếu.
- Progress/receipt nằm trong #192 / PR #202; plan này là implementation plan, không phải sổ trạng thái cạnh tranh.

## Intake và snapshot cần đối chiếu

Ngày lập kế hoạch: 22/10/2026. `<WORKTREE>` là đường dẫn trong handoff; `<PYTHON_ENV>=<WORKTREE>/.venv-eval`.

Snapshot review trước đó, không phải khẳng định trạng thái GitHub mới nhất:
- branch `codex/issue-192-workbench-contract`, HEAD `ad6ec58c90e028967897ad9515d6d8afd0a46ad6`;
- dirty adapter SHA256 `5e6a99f93ef1bfa777fb49f9d6faae9ff64c766a0e80b74a657543e8ac2dd394`;
- origin/main `42dc0ba08c126037e6c9db06942f96198db7e0c3`, merge-base `b2465f540a3c7a9e9b8014850a0100eefd621170`;
- PR202 OPEN/Ready, conflict với main; diff đúng 127 files, không dùng local main cũ gồm 741 files;
- CI required run39402241081 chỉ phủ committed HEAD trên, không phủ dirty adapter.

Lượt lập kế hoạch đọc được HEAD/ref/hash file như trên; `git status` gặp lỗi quyền sandbox. Agy phải lấy status mới thành công trước khi sửa, không suy từ lỗi status thành worktree sạch.

- [ ] Đọc global/worktree AGENTS, CONTEXT, domain routing, Architecture Standard, M1/M2 seams, ADR0018, hai verification docs.
- [ ] Đọc guidance pinned `1429d18001b4be17dab9dc108740482ed6efbb65`: AGENTS, issue-tracker, ci, agent-environment, feature-map, skill-evals; nếu branch thiếu thì `git show <sha>:<path>` chỉ đọc. Không integrate branch chỉ để lấy docs.
- [ ] Chạy từ đúng worktree, lưu stdout/stderr và exit riêng cho từng lệnh:
```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git diff -- backend/src/knora/adapters/postgres/corpus_preparation.py
Get-FileHash -Algorithm SHA256 backend/src/knora/adapters/postgres/corpus_preparation.py
gh issue view 192 --repo NhiBuaa/knora-agent --comments
gh issue view 158 --repo NhiBuaa/knora-agent --comments
gh pr view 202 --repo NhiBuaa/knora-agent --json headRefOid,baseRefName,isDraft,mergeable,mergeStateStatus,statusCheckRollup
```
- [ ] Nếu SHA/hash/dirty khác snapshot, đọc delta và xác định owner trước khi đụng hunk. Không reset/stash/ghi đè thay đổi không thuộc mình. Permission lỗi thì checkpoint, không tự sửa quyền.
- [ ] Mỗi lần pytest có output root riêng dưới temp, không chạy đồng thời lên cùng DB/cache. Không load developer .env cho suite offline.

## File map

| File | Vai trò và thay đổi dự kiến |
| --- | --- |
| `backend/src/knora/adapters/postgres/corpus_preparation.py` | Giữ dirty fix tách kiểm tra IDs và flush job trước attempt; không commit giữa hai nguồn |
| `backend/test/evaluation/test_corpus_store.py` | Regression hai nguồn với FK ON và rollback khi insert attempt thứ hai lỗi |
| `backend/src/knora/evaluation/live_admission.py` | Mở rộng source pins, giữ schema/API/hash canonical hiện hữu |
| `backend/test/evaluation/test_live_admission.py` | Test coverage pin + content drift thật qua read interception và chặn trước startup |
| `docs/development/issue-192-workbench-verification.md` | Append checkpoint mới: SHA/checks/findings/evidence limits |
| `docs/development/issue-158-evaluation-verification.md` | Chỉ cập nhật khi có acceptance evidence mới đã đối chiếu; không viết lại lịch sử |

Không dự kiến thay UI/schema/migration. Nếu dependency closure chỉ ra file thực thi khác cần pin, ghi lý do trong diff/review; không tạo danh sách cấu hình hoặc framework mới.

## Task 1 — Regression thứ tự flush và rollback (P2)

**Consumes:** `corpus_db -> (plan, factory)`, `adapter(factory)`, `admitted(tmp_path, plan)` trong test hiện hữu; `store.begin(plan, gate)`.
**Produces:** Hai regression kiểm tra transaction thật bằng fixture offline, và dirty fix được giữ trong commit có test.

**Outcome công bố trước:** Hai claims, hai jobs, hai attempts liên kết đúng khi FK bật; lỗi ghi nguồn thứ hai rollback toàn bộ writes của begin. Failure: FK không bật, exception sai lý do, orphan/partial row, pointer/revision/Gold thay đổi sau rollback. Ngân sách: offline, 0 provider/job live.

- [ ] Thêm helper fixture có scope test (tái sử dụng corpus_db); bật FK sau khi seed đã commit để không che lỗi setup bằng việc đổi toàn bộ fixture:
```python
@pytest.fixture
def constrained_corpus_db(corpus_db):
    plan, factory = corpus_db
    with factory.kw["bind"].connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    return plan, factory
```
Nếu foreign_key_check phát hiện fixture seed sai, sửa seed theo thứ tự dependency và kiểm tra lại; không bỏ assert hoặc tắt constraints.

- [ ] Thêm test thành công; giữ assertions Gold/document versions hiện có:
```python
def test_begin_with_enforced_foreign_keys(constrained_corpus_db, tmp_path):
    plan, factory = constrained_corpus_db
    store, gate = adapter(factory), admitted(tmp_path, plan)
    with gate.corpus_operation(plan.scope(), plan.payload()):
        claims = store.begin(plan, gate)
    expected = {p.job_id for p in plan.sources}
    assert {c.token.job_id for c in claims} == expected
    with factory() as session:
        assert {j.id for j in session.scalars(select(IngestionJobTable))} == expected
        attempts = session.scalars(select(IngestionJobAttemptTable)).all()
        assert len(attempts) == 2
        assert {a.ingestion_job_id for a in attempts} == expected
        assert session.get(EvaluationGoldVersionTable, "gold").frozen_json == plan.frozen_json
        assert len(session.scalars(select(DocumentVersionTable)).all()) == 2
```

- [ ] Thêm rollback test: snapshot các document pointer/revision, source status, frozen Gold trước begin; gây lỗi ở mapper insert attempt nguồn2 bằng event và luôn tháo listener:
```python
from sqlalchemy import event

def reject_second_attempt(mapper, connection, target):
    if target.ingestion_job_id == plan.sources[1].job_id:
        raise RuntimeError("second-source-insert-failure")

event.listen(IngestionJobAttemptTable, "before_insert", reject_second_attempt)
try:
    with pytest.raises(RuntimeError, match="second-source-insert-failure"):
        with gate.corpus_operation(plan.scope(), plan.payload()):
            store.begin(plan, gate)
finally:
    event.remove(IngestionJobAttemptTable, "before_insert", reject_second_attempt)
```
Đoạn trên đặt trong test riêng có plan/factory/store/gate từ constrained fixture. Sau exception, mở session mới và assert jobs==[], attempts==[], pointer/revision/source status/Gold bằng snapshot trước begin. Không assert journal của authority rollback cùng transaction DB: đó là hai miền persistence khác nhau.

- [ ] Chứng minh test thành công bắt lỗi HEAD cũ: dùng compile-in-memory kỹ thuật đã có trong `<REVIEW_OUTPUT>/reproduce_flush_order.py`, chạy đúng scenario regression trên adapter source lấy từ `git show HEAD:<adapter>` trong DB/journal temp riêng. Không checkout/reset source thật. Bản cũ phải lỗi IntegrityError tại thứ tự FK; không chấp nhận lỗi import/setup làm RED. Ghi test ID + exception. Không commit probe dùng đường dẫn máy cá nhân.
- [ ] Giữ fix hiện hữu: preflight cả hai job IDs trước pending insert, flush parent trước child, một `_sessions.begin()` cho cả hai. Không thêm commit trung gian.
- [ ] Chạy:
```powershell
& '<PYTHON_ENV>/Scripts/python.exe' -B -m pytest backend/test/evaluation/test_corpus_store.py -q -p no:cacheprovider -p no:deepeval --basetemp '<OUTPUT>/corpus-tmp' --junitxml '<OUTPUT>/corpus.xml'
```
Expected exit0; test mới thành công và rollback đạt. SQLite PASS chỉ chứng minh scope offline này.
- [ ] Format/lint theo Task3; review diff rồi commit riêng adapter + tests:
```powershell
git add backend/src/knora/adapters/postgres/corpus_preparation.py backend/test/evaluation/test_corpus_store.py
git commit -m "fix(evaluation): flush corpus jobs before attempts"
```

## Task 2 — Ghim mã runtime và chặn content drift (P1)

**Consumes/produces:** Giữ nguyên signature và shape dictionary của `reviewed_build_pins()`, được `LivePackage._validate_manifest` và `_check` so sánh. Không cấp thêm authority.

**Outcome công bố trước:** Thay bytes của adapter/collaborator mà HEAD không đổi sẽ đổi source pins và bị `LIVE_PACKAGE_BUILD` trước tạo journal mới hoặc gọi startup. Failure: adapter không có trong pins, đổi nội dung không bị phát hiện, startup callback được gọi, test phải dùng real package/journal cũ. Ngân sách: offline temp package, 0 external calls.

- [ ] Chạy CodeGraph status đúng worktree; query MCP nếu có cho `prepare_corpus -> PostgresCorpusPreparationStore.begin/finalize -> ingestion_jobs activation`; nếu không có MCP dùng CLI explore. Không dùng index checkout khác. Đối chiếu source hiện tại bằng rg cho imports/callers của reviewed_build_pins, init/check, corpus handler, activation, tables, object/PDF processing và runtime entry. Nếu map lỗi, báo giới hạn rồi dùng read/rg; không xóa/recreate DB có sẵn.
- [ ] Chọn source set đơn giản, bao phủ mã Knora runtime thay vì duy trì whitelist thiếu từng collaborator. Thay ba nhóm evaluation/answering/providers bằng toàn bộ package first-party `backend/src/knora/**/*.py`, giữ hai eval entry scripts hiện hữu:
```python
paths = sorted(
    {
        *root.joinpath("backend/src/knora").rglob("*.py"),
        root / "evals/runners/ragas_review.py",
        root / "evals/scorers/deepeval_cloudflare.py",
    }
)
```
Giữ `relative_to(root).as_posix()`, UTF-8 text normalization/hash, code_sha và response dependency version checks. Query closure nếu chỉ ra runtime helper ngoài package thì thêm chính file đó vào set; không pin .env, credentials, generated evidence, tests hoặc cache.

**Đánh đổi:** Pin toàn package thêm I/O đọc/hash và sẽ vô hiệu gói khi file runtime không liên quan thay đổi; đổi lại không bỏ sót collaborator mới trong package. Không tuyên bố nhanh hơn. Nếu đo thấy ảnh hưởng thực tế tới deadline thì checkpoint và đề xuất tập dependency có bằng chứng; không cache hash bỏ qua dirty content.

- [ ] Thêm test parameterized cho ít nhất các file thực sự tồn tại:
```python
@pytest.mark.parametrize("relative", [
    "backend/src/knora/adapters/postgres/corpus_preparation.py",
    "backend/src/knora/adapters/postgres/ingestion_jobs/coordination.py",
    "backend/src/knora/ingestion/job_processing.py",
])
def test_reviewed_build_tracks_runtime_content(monkeypatch, relative):
    from pathlib import Path
    import knora.evaluation.live_admission as live

    root = Path(live.__file__).resolve().parents[4]
    before = live.reviewed_build_pins()
    assert relative in before["sources"]
    original_read = Path.read_text
    target = (root / relative).resolve()

    def drifted_read(path, *args, **kwargs):
        text = original_read(path, *args, **kwargs)
        return text + "\n# synthetic source drift\n" if path.resolve() == target else text

    monkeypatch.setattr(Path, "read_text", drifted_read)
    after = live.reviewed_build_pins()
    assert after["code_sha"] == before["code_sha"]
    assert after["sources"][relative] != before["sources"][relative]
```
Monkeypatch scoped theo test, không ghi source thật; test này RED trên source set cũ.

- [ ] Thêm test init và window cùng cơ chế drifted_read. Tạo manifest/package **trước** patch bằng package_manifest/LivePackage.initialize hiện hữu. Sau patch:
  1. `LivePackage.initialize` với manifest đã pin + temp path chưa tồn tại phải raise `LIVE_PACKAGE_BUILD` và không tạo journal.
  2. `package.window` dùng cleanup hợp lệ như `test_package_startup_gates_run_before_side_effect_and_never_reset` phải raise cùng mã; effects=[] và startup counter không tăng. Reuse assertion/callback structure hiện hữu, không stub `_check` hoặc return pins bằng dict giả.
  3. Đổi file bị pin thành lỗi đọc bằng monkeypatch phải fail closed trước callback; không silently skip missing files.
- [ ] Chạy test mới trước sửa source set để thấy RED do missing pin/drift, rồi áp dụng source set và chạy cả admission/corpus scope:
```powershell
& '<PYTHON_ENV>/Scripts/python.exe' -B -m pytest backend/test/evaluation/test_live_admission.py backend/test/evaluation/test_corpus_store.py backend/test/evaluation/test_corpus_preparation.py backend/test/evaluation/test_corpus_plan.py -q -p no:cacheprovider -p no:deepeval --basetemp '<OUTPUT>/admission-tmp' --junitxml '<OUTPUT>/admission.xml'
```
- [ ] Format/lint, review diff rồi commit riêng live_admission + tests:
```powershell
git add backend/src/knora/evaluation/live_admission.py backend/test/evaluation/test_live_admission.py
git commit -m "fix(evaluation): pin corpus runtime sources in reviewed builds"
```
Không chạy probe khởi tạo lại manifest/journal lịch sử. Old build mismatch sau fix là kết quả đúng.

## Task 3 — Kiểm chứng tổng hợp, docs và PR cùng nhánh

- [ ] Chạy từng lệnh, kiểm tra exit ngay; không để exit của lệnh cuối che failure trước:
```powershell
& '<PYTHON_ENV>/Scripts/python.exe' -m ruff format .
& '<PYTHON_ENV>/Scripts/python.exe' -m ruff format --check .
& '<PYTHON_ENV>/Scripts/python.exe' -m ruff check .
git diff --check
& '<PYTHON_ENV>/Scripts/python.exe' -B -m pytest backend/test/evaluation backend/test/adapters/http/test_http_evaluation_datasets.py backend/test/adapters/http/test_http_evaluation_runs.py backend/test/adapters/http/test_http_evaluation_scoring.py evals/test/test_deepeval_capture.py evals/test/test_ragas_review.py -q -p no:cacheprovider -p no:deepeval --basetemp '<OUTPUT>/suite-tmp' --junitxml '<OUTPUT>/suite.xml'
```
Trước chạy formatter toàn repo đọc dirty inventory; nếu formatter sửa ngoài phạm vi thì xem diff, không tự stage hoặc revert hunk owner khác.
- [ ] Ghi counts thực tế, không hardcode404 (test mới sẽ đổi count), failure/error/skip, duration, command, exit và commit SHA. Review trước có404Python +57frontend PASS là evidence cũ, không evidence cho code mới.
- [ ] Nếu chỉ backend tests/pins/flush thay đổi, không ép UI journey. Nếu giải conflict đụng BFF/UI/runtime composition thì chạy check/browser journey tương ứng Feature Map với quyền/ownership phù hợp; CI synthetic frontend không chứng minh browser thật. Không mở lại L1 để lấy browser evidence.
- [ ] Append checkpoint trong verification doc #192, giữ lịch sử: finding nào khép, test IDs, hashes/build thực tế, CI SHA, runtime artifact nào chỉ đọc. Publish receipt đã redacted lên #192/PR202 theo hướng dẫn pinned, dùng --body-file UTF8; đọc lại sau publish, không duplicate comment khi lỗi một phần.
- [ ] Rà soát tiếp theo bởi reviewer theo `requesting-code-review` nếu skill thực có. Không coi tự đánh giá của Agy là review độc lập.
- [ ] Stage đúng docs cần đổi, commit mô tả evidence; push nhánh PR202 hiện hữu bằng push thường theo quyền đã giao. Không force-push, mở PR thay thế hoặc rename branch lịch sử.
- [ ] Đọc CI required cho **SHA cuối** sau mọi commit/docs/integration. Missing/pending/failing là chưa CI Verified. Old run39402241081 không phủ fixes.

## Task 4 — Quyết định tích hợp và xử lý conflict

Đây là bước có điều kiện, không ngăn làm Task1–3 offline. Snapshot preview chỉ đọc trước có8files:
- `backend/src/knora/adapters/postgres/document_reader.py`
- `backend/src/knora/main.py`
- `backend/test/adapters/cli/test_dev_launcher.py`
- `backend/test/adapters/postgres/test_evaluation_reader.py`
- `backend/test/config/test_ci_checks.py`
- `conftest.py`
- `docs/evaluation.md`
- `docs/openapi-manifest.json`

- [ ] Refresh PR/base đúng refs bằng read-only fetch khi được phép; không merge/rebase để lấy guidance. Xác định có approval chọn cách integrate main vào branch hay chưa. Nếu chưa, gửi owner lựa chọn cụ thể và giữ PR pending integration; không tự suy phê duyệt từ "sửa findings".
- [ ] Khi có quyền tích hợp: bảo toàn owner/source-key semantics của reader và thay đổi main về launcher ownership/storage/test isolation (#214); đối chiếu shared-reader #153 theo pins/ACK mới nếu thay contract. Không lấy ours/theirs toàn file.
- [ ] Giải main composition bằng ghép dependencies, không mở default live registry. Giữ test partition/conftest và CI gate của cả hai phía; docs giữ provenance/history, không gộp quality claims.
- [ ] Nếu schema/export thay đổi, regenerate qua exporter hiện hữu; không sửa generated TS bằng tay. Chạy `python scripts/export_openapi.py --check`; chạy format:shared/check cho maintained shared files bị tác động; format/format:check frontend nếu sửa frontend.
- [ ] Chạy đúng test vùng conflict (reader/launcher/config/root) và suite Task3, CI DB disposable theo workflow; lấy CI mới đúng integrated SHA. Không suy SQLite PASS thành Postgres runtime PASS.
- [ ] PR202 đã Ready ở snapshot; không cần thao tác Draft→Ready nếu live read vẫn đúng. Giữ OPEN cho owner review/merge.

## Task 5 — Audit evidence và bàn giao nghiệm thu #158

Không inference hoặc startup bổ sung để lấp thiếu evidence.

- [ ] Đọc artifact hiện hữu ở paths trong handoff, hashes và journal theo mode=ro/query_only. Counters26/3/7slots chỉ chứng minh journal, không chứng minh raw payload, zero billing hoặc cleanup.
- [ ] Đối chiếu execution IDs, jobs/attempts, chunks/vectors/provenance, active pointers, Gold v1/v2/source statuses từ captures/DB dump đã thu; FAILED/history không đổi. Nếu không có read-only artifact thì ghi UNVERIFIED, không khởi động retained Postgres.
- [ ] Audit independent owner judgments có trước judge run; đối chiếu rubric **correctness, answer_relevancy, faithfulness**. Handoff cũ dùng "Precision" cần làm rõ mapping/evidence, không tự đổi tên rồi tuyên bố agreement. Giữ disagreements/missing evidence.
- [ ] Audit paid-cost/quota proof và owned cleanup receipts đúng execution; không tự dùng lời handoff làm xác minh độc lập. Hai sample không chứng minh calibration, benchmark-wide quality hay baseline improvement.
- [ ] Giữ run lịch sử `faacf17180f24a2bb5ab6c9e36917c6a`: COMPLETED / SEMANTIC_PENDING, expected ANSWER nhận REFUSAL. New results không sửa semantic state lịch sử.
- [ ] Nộp acceptance packet cho owner: Implemented / Local Verified / CI Verified / Runtime Verified / AI quality / Reviewed / Merged / Deployed tách riêng. #158 chỉ nghiệm thu khi owner chấp thuận phạm vi và quality còn lại; PR có thể được review code trước.
- [ ] Nếu cần chạy mới, trả về yêu cầu **envelope mới** có exact build/inputs/resource ownership/quota/cost/deadline/startup/call caps; không dùng gói cũ.
- [ ] Selective closeout theo pinned issue-tracker: ghi ngắn evidence bốn mặt (kích hoạt hướng dẫn, kết quả task, tuân thủ/bằng chứng, hiệu quả thực thi); dẫn records độc lập, không tự kết luận baseline tốt hơn. Không thêm skill/framework/store.

## Điều kiện dừng và kết quả bàn giao

Dừng đúng hành động phụ thuộc khi permission/ownership/SHA conflict không giải thích được, test fail sai nguyên nhân, FK không enforce, build drift không chặn side effect, thiếu approval tích hợp/live. Tiếp tục phần độc lập còn làm được; không dừng để xin lại từng thao tác offline thông thường.

Mỗi checkpoint: actual calls/jobs/startups của lần xử lý này (mong đợi0/0/0), SHA, diff, command/exit/counts, artifact digest; redact account/token/private URL/path bằng [REDACTED], <USER_HOME>, <WORKTREE>, <PYTHON_ENV>. Không ghi secrets từ .env.

Hoàn tất fixes khi hai findings có regression đạt và review đọc được diff; hoàn tất CI khi đúng SHA cuối xanh; sẵn sàng nghiệm thu khi có packet nêu rõ runtime/quality gaps. Không tự tuyên bố merge, deploy hay owner acceptance.
