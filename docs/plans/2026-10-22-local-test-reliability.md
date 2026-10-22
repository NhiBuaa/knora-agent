# Local Test Reliability — Implementation Plan V1.1

> **For agentic workers:** Dùng `executing-plans` nếu có và được phép; đọc nguồn Skill theo catalog. Làm tuần tự trên đúng worktree. Bản này là kế hoạch đề xuất, chưa phải lệnh triển khai hay quyền sử dụng runtime của phiên khác.

**Goal:** Áp dụng các bài học #191, không làm lại phần đã merge từ #183, giúp agent chạy đúng code, chọn đúng test và giữ bằng chứng khi phiên bị gián đoạn.

**Architecture:** Code nằm ở worktree từng Issue; `.env`, DB và dịch vụ local được dùng chung mặc định, các lượt có ghi dữ liệu chạy lần lượt. Chỉ dùng DB test khi test reset/xóa dữ liệu, cần trạng thái rỗng, kiểm tra migration hoặc cần thực thi song song có xung đột. Tái sử dụng PostgreSQL, launcher, pytest, CI và runbook hiện có.

**Tech Stack:** Python/pytest, PowerShell, Docker Compose và GitHub Actions đang có trong Knora.

**Spec / nguồn quyết định:** Retro #191 do người dùng cung cấp và điều chỉnh trong hội thoại ngày 2026-10-22: không buộc mọi smoke/tác vụ local dựng DB hoặc stack riêng. Tham chiếu kế hoạch cũ `shared-env-worktree-verification-plan-20261022.md` trong cùng thư mục Temp để truy lịch sử; phần thay đổi chính sách DB của bản này thay thế yêu cầu cách ly mặc định trong V1 cũ. Không sửa hồi tố bản đã duyệt hoặc bằng chứng cũ.

**Revision:** V1.1 xử lý 5 finding trong review: truyền mã thoát và phân loại evidence; quyền sửa #226; lệnh/phạm vi nhóm DB; bài thử phiên mới; vòng hoàn tất CI/review. Bản V1 trước chỉnh sửa có SHA256 `09CC9AF18E0C66BA5388677FA2718951D18D3A3B5F791DD2B5DB0FB608814CD2`. Người dùng yêu cầu sửa kế hoạch trong hội thoại hiện tại; chưa giao thực thi repository. Không suy ra phê duyệt triển khai từ việc tạo bản V1.1.

## 1. Hiện trạng được xác minh lại

Snapshot GitHub: `main = dcf15fe1f3b04a5d47b2140b485327f12c965939`. Kiểm tra lại trước triển khai, không coi snapshot là trạng thái vĩnh viễn.

| Bài học | Bằng chứng hiện tại | Việc còn lại |
| --- | --- | --- |
| Import nhầm worktree | PR #225 đã merge, commit merge `6abbd3bd0d54dbc57f37439e92eb0907f75c5b81`; `pytest.ini` có `pythonpath = backend/src`, root `conftest.py` có `pytest_sessionstart`; regression tại `backend/test/config/test_pytest_checkout.py` | Không xây lại guard. Cải thiện thông báo để thấy expected/actual và xác minh regression trên base mới |
| Phân nhóm test / DB | Root `conftest.py` có `ci_route`, `--ci-suite`, `--ci-selection`; backend test fixture vẫn đặt URL PostgreSQL mặc định nếu thiếu | Viết hướng dẫn local dễ tìm, dùng phân nhóm sẵn có; không tự tạo phân nhóm mới hoặc bắt mọi test dùng DB riêng |
| Mất phiên thực thi | Retro báo `Unknown process id`; chưa tự tái hiện lỗi của công cụ | Lưu log từ lúc bắt đầu, JUnit và mã thoát cuối; thiếu tệp hoàn tất là chưa xác định, không tự nhận PASS |
| Reservation khó hiểu | `start-dev.ps1` tạo khóa độc quyền, ghi PID/REPO/PROJECT/TIMESTAMP; lỗi hiện chỉ `DEV_PROJECT_RESERVED:knora-dev`. PR #224 đã merge tại SHA main nêu trên, có runbook phục hồi | Thêm chẩn đoán hữu ích, không đổi khóa/ownership/cleanup; bổ sung trường hợp metadata không đọc được |
| Output dài | Retro đưa ví dụ output bị cắt; chưa đo tiết kiệm token/thời gian | Dùng truy vấn gọn và liên kết artifact trong lần thực hiện; không thêm Skill/tài liệu tiêu chuẩn mới |
| `.env` chung | PR #226 còn OPEN, head lúc kiểm tra `6d4d6ff59b4a1faa969d5b39cb82c81e11604e11` | Sửa câu buộc dừng khi thiếu DB riêng theo quyết định mới; giữ regression EnvFile và bảo vệ secrets |

Các nguồn đã đọc trực tiếp theo SHA: `conftest.py`, `pytest.ini`, `backend/test/conftest.py`, `backend/test/config/test_pytest_checkout.py`, `scripts/start-dev.ps1`, `docs/runbooks/ci.md`, `docs/runbooks/local-development.md` và patch #226. CodeGraph của checkout chính phản ánh checkout cũ hơn; không dùng nó để phủ nhận thay đổi đã merge. Thư mục chính hiện mang tên nhánh `main` nhưng HEAD lúc kiểm tra còn `36bb3d5042ea764508210b29ab08a9dfd5cf7bdc`; chưa pull/chuyển nhánh hoặc sửa dữ liệu.

**Ngoại lệ DB có bằng chứng cụ thể:** `backend/test/adapters/postgres/test_object_lifecycle_store.py:29-36` có fixture tự động `TRUNCATE` và commit trước/sau test. Không chạy fixture này vào DB local cần giữ dữ liệu. `test_document_ui_projection.py` dùng TRUNCATE trong transaction rollback, nhưng vẫn có thể khóa bảng; không suy rằng mọi TRUNCATE đều xóa vĩnh viễn hoặc mọi rollback đều an toàn khi chạy song song. `test_conversation_store.py` đã tự tạo/xóa DB migration riêng; giữ cơ chế đó.

## 2. Quy tắc vận hành sau điều chỉnh

1. Smoke bằng UI/API, kể cả AI thật: mặc định dùng `.env`, DB và dịch vụ local chung, đúng worktree/SHA, chạy lần lượt. Không cần branch test hay một stack cho mỗi Issue.
2. Unit/contract test: dùng mock/in-memory và phân nhóm hiện có; không nạp nguyên `.env` AI vào pytest. Test code tự đặt provider giả lập không phải lỗi cần sửa.
3. Test phá hủy/reset hoặc migration: dùng DB test trên PostgreSQL hiện có khi phù hợp, tái sử dụng giữa các lượt tuần tự; không bắt tạo container mới mỗi lần. Các test đã tự cấp DB tạm giữ nguyên. Kiểm tra yêu cầu hệ điều hành/cgroup của nhóm DB; không tuyên bố cả nhóm chạy được trên Windows chỉ vì PostgreSQL có sẵn.
4. Không xóa dữ liệu ứng dụng, đổi credentials, dừng tiến trình của phiên khác, tự bỏ reservation hoặc reset stack. Một phiên dừng giữ quyền chạy không có nghĩa dữ liệu trở thành dữ liệu dùng một lần.
5. Không tự migrate DB local chung qua lại giữa các branch có schema không tương thích. Khi schema không tương thích, dùng đường DB test/migration hiện có hoặc báo cần quyết định; không coi việc này là lý do bắt mọi task tách DB.
6. Có `.env` không tự cấp quyền gọi provider trả phí, tải model hoặc gửi dữ liệu ra ngoài. Giữ quyền AI đã duyệt; không bắt chạy inference để nghiệm thu các sửa đổi test/docs/diagnostics của gói này.
7. Không thêm Skill, dependency, workflow, runner, hook, khóa phân tán hoặc cơ sở dữ liệu trạng thái. Không nới CI, sửa report để tạo PASS hoặc chuyển test sang nhóm khác chỉ vì đang lỗi local.

## 3. Phạm vi PR và quyền sở hữu

- **PR #226:** Anti nhận bàn giao là chủ thực hiện PR tiếp nối, không mặc nhiên là chủ #226. Nếu đúng phiên đang sở hữu #226 hoặc đã có xác nhận chuyển giao rõ ràng, cập nhật phần `.env` trên đúng nhánh #226 trước, rồi làm phần còn lại ở PR tiếp nối. Không chiếm worktree và không làm hai phiên cùng sửa một nhánh.
- **Một PR tiếp nối nhỏ cho phần còn thiếu:** Đề xuất branch `fix/local-test-feedback`, worktree `C:\Developer\Projects\knora-agent-worktree\fix-local-test-feedback`, base là `main` mới nhất đã xác minh có #224/#225. Kiểm tra đường dẫn và branch chưa bị dùng trước khi tạo. Không sửa trên checkout chính, #224 hoặc #225 đã merge.
- **Nếu #226 thuộc phiên khác:** chuẩn bị diff/hunk tối thiểu cho phần chính sách và xin xác nhận một lần qua kênh người dùng cho phép. Xác nhận phải chỉ rõ SHA/hunk, ai áp dụng và phiên cũ đã ngừng sửa nếu chuyển quyền. Không tự gửi tin sang phiên khác nếu chưa có quyền. Nếu sau 15 phút chưa có phản hồi, không tiếp tục chờ lặp: làm B–E và phần docs không phụ thuộc; ghi phần A/#226 đang chờ quyền. Không đánh dấu toàn gói đủ nghiệm thu khi phần chính sách còn mâu thuẫn.
- **Thứ tự tích hợp:** nếu #226 đã merge, làm toàn bộ delta còn thiếu trong PR tiếp nối từ main mới. Nếu #226 còn mở và đã được cập nhật, PR tiếp nối vẫn nhắm main, không cherry-pick toàn bộ #226; chốt cùng owner các hunk chung và kiểm tra lại sau khi base thay đổi. Không tự merge #226 để mở đường. Nếu #226 đóng không merge, đưa chính sách tối thiểu vào PR tiếp nối, không sao chép toàn bộ công việc EnvFile của #226.
- Trước sửa file chung với #226, xác định owner và hunk được phép; chưa có quyền thì chỉ làm các bước độc lập. Không cần dừng mọi công việc chỉ để chờ một file docs. Kết quả cuối liệt kê phần nào thuộc PR nào và trạng thái từng phần, không lấy CI của PR này chứng minh PR kia.
- Đọc `AGENTS.md` và các nguồn repo yêu cầu trước khi sửa; dùng `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`, `git worktree list --porcelain`. Giữ nguyên untracked và thay đổi của phiên khác.
- Nếu cần lưu bản kế hoạch đã duyệt trong repo, dùng `docs/plans/2026-10-22-local-test-reliability.md` trên worktree được giao; ghi SHA/phê duyệt đúng phiên bản trong Issue/PR. Không tạo thêm sổ trạng thái hoặc chép toàn bộ retro vào AGENTS.

## 4. Các bước triển khai

### A — Sửa hướng dẫn đang gây quá mức cần thiết

**Files:** `docs/runbooks/local-development.md`, `docs/runbooks/ci.md`; `docs/runbooks/local-ollama.md` và plan trong #226 chỉ sửa nếu có mâu thuẫn trực tiếp.

- [ ] Đối chiếu base/PR mới nhất và quyết định của người dùng; ghi phần chênh lệch trong PR, giữ bằng chứng V1 cũ là lịch sử.
- [ ] Thay yêu cầu “thiếu isolated databases/buckets thì dừng runtime” trong #226 bằng ba trường hợp ở §2. Không thay nó bằng quyền xóa dữ liệu local mặc định.
- [ ] Sửa câu chọn verification trong `ci.md` để không hiểu rằng mọi backend integration đều phải dựng DB/stack riêng. Giữ nguyên yêu cầu của các test/CI thực sự cần DB tạm.
- [ ] Giữ hướng dẫn dùng `-EnvFile` từ worktree; chỉ rõ code/Python là của checkout kiểm thử. Không đổi `.env` chung và không thêm parser.
- [ ] Kiểm tra liên kết và formatting đúng các file bị sửa; phần này không cần gọi model hoặc chạy lại toàn bộ browser E2E.

### B — Hoàn thiện chẩn đoán import và lệnh test local

**Files:** `conftest.py`, `backend/test/config/test_pytest_checkout.py`, `backend/test/config/test_ci_checks.py` nếu cần regression phân nhóm; `docs/runbooks/ci.md`. Không sửa cấu hình nguồn đã merge trừ khi test chứng minh lỗi.

- [ ] Chạy regression checkout hiện có với evidence riêng, xác nhận fail-fast xảy ra trước test body khi foreign package đã được nạp.
- [ ] Mở rộng assertion trong test foreign preload: stderr chứa đường expected của checkout và actual của foreign package; không có `result.json`. Chạy test để thấy thất bại trước khi sửa thông báo.
- [ ] Sửa tối thiểu thông báo hiện có, giữ `KNORA_CHECKOUT_MISMATCH` và `pytest.ExitCode.USAGE_ERROR`. Dạng dự kiến:

```python
raise pytest.UsageError(
    f"KNORA_CHECKOUT_MISMATCH: expected={expected}; actual={source or '<unknown>'}; "
    "check pytest configuration and preloaded plugins"
)
```

- [ ] Chạy lại test từ root, backend và các entrypoint explicit-config/root hiện có. Khi đăng evidence công khai, thay phần đường dẫn cá nhân bằng `[USER_HOME]`; không bỏ đường dẫn chẩn đoán cần thiết trong lỗi local.
- [ ] Thêm mục local testing trong CI runbook: `backend` và `windows` là các nhóm riêng có sẵn, không gọi `backend` là “toàn bộ test không DB”. Dùng `--ci-selection` để giữ manifest và chỉ in số selected/deselected cùng lỗi liên quan.
- [ ] Thêm các lệnh chọn nhóm dưới đây vào runbook, trong đó `$evidence` là thư mục mới của mỗi lượt theo C. Chạy trong process PowerShell riêng, từ worktree và Python đã xác minh. Đây là các lựa chọn thay thế nhau, không phải lệnh bắt chạy mọi nhóm:

```powershell
# Nhóm backend theo routing hiện có, không phải toàn bộ kiểm thử local.
python -m pytest backend/test evals/test --ci-suite=backend --ci-selection="$evidence/backend-selection.json" --junitxml="$evidence/backend.xml" -o "cache_dir=$evidence/cache"
# Nhóm Windows: dùng trên Windows với các shell/phụ thuộc đã có.
python -m pytest backend/test evals/test --ci-suite=windows --ci-selection="$evidence/windows-selection.json" --junitxml="$evidence/windows.xml" -o "cache_dir=$evidence/cache"
# Nhóm DB: chỉ chạy sau khi chọn đích theo hợp đồng bên dưới và kiểm tra OS/cgroup.
if ([string]::IsNullOrWhiteSpace($env:KNORA_DATABASE_URL)) { throw 'LOCAL_DB_TARGET_REQUIRED: set the reviewed test target in this process; do not use the implicit fallback' }
python -m pytest backend/test evals/test --ci-suite=database --ci-selection="$evidence/database-selection.json" --junitxml="$evidence/database.xml" -o "cache_dir=$evidence/cache"
```

Lấy `$LASTEXITCODE` ngay sau **một** lệnh pytest được chọn và xử lý như C, không chạy lệnh khác rồi mới ghi mã thoát. Trước gọi DB, operator/agent xác nhận đích local được phép và nhu cầu reset của tập test; chỉ khai báo URL không chứng minh dữ liệu đó được phép xóa. Không in URL có credentials. Lệnh nhóm DB toàn bộ có fixtures reset/commit: dùng DB test; smoke ứng dụng không dùng lệnh nhóm DB này và vẫn dùng DB chung. Nếu chưa có đích test cho các fixtures phá hủy, chỉ phần đó chưa chạy, không dựng thêm stack mặc định.

- [ ] Kết quả mong đợi: backend/windows giữ manifest selected/deselected theo routing; PASS chỉ khi exit 0 và report hợp lệ cho các test thực chạy. Nhóm DB thiếu URL tường minh dừng ở bước chuẩn bị của mẫu lệnh trước pytest, không dùng fallback. DB không kết nối được phải báo lỗi/timeout hữu hạn, không PASS hoặc tự chuyển sang DB ứng dụng. Thiếu OS/cgroup là giới hạn local; required CI vẫn phải chạy đầy đủ theo cấu hình hiện hành.
- [ ] Phạm vi thay đổi DB trong V1.1 là hướng dẫn và mẫu chuẩn bị, **không phải guard DB tự động cho mọi cách gọi pytest**. Không thêm guard toàn cục/cờ opt-in hoặc sửa URL fallback hàng loạt. Lệnh pytest trần bỏ qua mẫu chuẩn bị vẫn có rủi ro chạm fallback; ghi giới hạn này trung thực.
- [ ] Kiểm chứng bước chuẩn bị trong process con: khi unset `KNORA_DATABASE_URL`, mẫu phải từ chối trước lời gọi pytest; chỉ đánh dấu đã chặn tại mẫu lệnh, không tuyên bố đã chặn toàn repository. Thử đường lỗi kết nối bằng fixture/mock sẵn có hoặc loopback server thử do mình sở hữu, timeout tối đa 10 giây; không dùng một cổng tùy ý có thể thuộc phiên khác. Nếu phát hiện nhóm non-DB thực sự kết nối DB trong collection/fixture, báo ca cụ thể rồi sửa đúng ranh giới đó; không chuyển test bừa để làm PASS.

### C — Giữ evidence cho lệnh dài, không dựng runner mới

**File:** `docs/runbooks/ci.md`. Evidence local dùng thư mục mới theo lượt chạy, không commit raw logs/secrets.

- [ ] Tái sử dụng thư mục evidence của workflow nếu có; nếu chưa có, dùng một thư mục tạm riêng cho lượt. Ghi HEAD và tình trạng dirty trước khi chạy; không dùng evidence cũ cho checkout mới.
- [ ] Đưa mẫu lệnh PowerShell sau vào runbook. **Nội dung block chỉ chạy trong PowerShell con riêng**, không dot-source vào terminal dùng chung. Mẫu chạy nhóm backend, không phải full local. Trong runbook, ghi rõ operator thực thi cả block lẫn phần gọi process con:

```powershell
$testBlock = {
$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction Stop).Source
$evidence = Join-Path ([IO.Path]::GetTempPath()) ('knora-local-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $evidence -ErrorAction Stop | Out-Null
Write-Output "RUN_PID=$PID EVIDENCE=$evidence"
$subjectSha = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'GIT_HEAD_UNAVAILABLE' }
$subjectSha | Set-Content -LiteralPath (Join-Path $evidence 'subject-sha.txt') -Encoding UTF8
$worktreeStatus = git status --short
if ($LASTEXITCODE -ne 0) { throw 'GIT_STATUS_UNAVAILABLE' }
$worktreeStatus | Set-Content -LiteralPath (Join-Path $evidence 'worktree-status.txt') -Encoding UTF8
$ErrorActionPreference = 'Continue'
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) { $PSNativeCommandUseErrorActionPreference = $false }
$LASTEXITCODE = $null
& $python -m pytest backend/test evals/test --ci-suite=backend --ci-selection="$evidence/selection.json" --junitxml="$evidence/junit.xml" -o "cache_dir=$evidence/cache" *> (Join-Path $evidence 'pytest.log')
$testExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($null -eq $testExit) { throw 'PYTEST_EXIT_UNAVAILABLE' }
$testExit | Set-Content -LiteralPath (Join-Path $evidence 'exit-code.txt') -Encoding UTF8
Write-Output "EXIT_CODE=$testExit EVIDENCE=$evidence"
exit $testExit
}
$testShell = (Get-Process -Id $PID).Path
$encodedTestBlock = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($testBlock.ToString()))
& $testShell -NoProfile -EncodedCommand $encodedTestBlock
$outerExit = $LASTEXITCODE
Write-Output "CHILD_EXIT=$outerExit"
if ($outerExit -ne 0) { throw "TEST_CHILD_FAILED:$outerExit; inspect this run's evidence" }
```

- [ ] Trước dùng mẫu, xác nhận `$testShell` là `powershell.exe` hoặc `pwsh.exe` và Python khả dụng; host nhúng khác không tự coi là executable phù hợp. Mẫu chuẩn hóa xử lý lỗi native chỉ trong child để exit khác 0/stderr không làm bỏ qua bước ghi mã; không đổi biến của process cha. Nếu khởi chạy Python không thành công, ghi lỗi khởi chạy và exit ngoài khác 0; không bịa mã thoát pytest. Trước đổi git SHA/status thành evidence, kiểm tra hai lệnh Git thành công; git lỗi không được gắn mã của commit cũ cho lượt mới.
- [ ] Thử trên hai shell: lượt thành công và lệnh con trả khác 0 phải được process ngoài nhận đúng mã; có assertion trên mã thực nhận, không chỉ đọc chuỗi `EXIT_CODE`. Giữ regression pytest thật; không sửa product code để cố tạo lỗi.

| Tình huống kiểm chứng | Evidence bắt buộc | Kết luận |
| --- | --- | --- |
| Pytest chạy hết và PASS | Exit 0, JUnit đọc được, số test hợp lệ, selection nếu dùng suite | PASS trong phạm vi đã chạy |
| Test/assertion thất bại | Exit khác 0, log và JUnit nếu pytest tạo được | FAIL; không chuyển thành PASS vì process ngoài kết thúc |
| Pytest lỗi trước test body, gồm foreign preload/usage error | Exit khác 0 và log lỗi; có thể chưa có JUnit/selection | Lỗi khởi tạo, không PASS; thiếu JUnit ở đường lỗi này không phải lỗi runner |
| Không có test được chọn | Exit/report/selection thực tế, kể cả exit 5 | Chưa chứng minh hành vi yêu cầu, không PASS |
| Process bị ngắt hoặc mất kết nối | Log từ đầu, PID và trạng thái process/tệp thực tế; có thể thiếu mã thoát cuối | Chưa xác định; kiểm tra trước khi chạy lại |

- [ ] Thử tối thiểu một lượt PASS; foreign-preload usage error từ regression hiện có; và một process thử bị ngắt do mình sở hữu. Đường early-error không buộc có XML. Có JUnit nhưng không có mã kết thúc vẫn chưa đủ chứng minh hoàn tất. Không tạo runner hoặc workflow mới để ép mọi đường lỗi có cùng bộ tệp.
- [ ] Thử ngắt chỉ process thử do mình sở hữu: có log chưa có exit-code phải báo chưa xác định, không coi thiếu tệp là exit code 0. Trước chạy lại, kiểm tra PID/ownership và dấu hiệu hoàn tất; không dùng `Unknown process id` của công cụ làm bằng chứng process hệ điều hành đã chết.
- [ ] Nếu phiên cha chết trước bước ghi exit-code, chấp nhận trạng thái chưa xác định; không thêm daemon/runner đảm bảo tuyệt đối. XML hợp lệ một mình chưa đủ chứng minh toàn bộ lệnh thành công.
- [ ] Báo số lượng selected/deselected, PASS/FAIL/SKIP và exit code; giữ manifest đầy đủ trong artifact. Không in hàng nghìn node hoặc command line chứa token.

### D — Cải thiện lỗi reservation, không đổi cơ chế khóa

**Files:** `scripts/start-dev.ps1`, `backend/test/adapters/cli/test_dev_launcher.py`, đoạn phục hồi hiện có trong `docs/runbooks/local-development.md`.

- [ ] Tái sử dụng test cạnh tranh hiện có. Bổ sung test cho đường thông báo: mã lỗi cũ còn nguyên, có đường dẫn khóa và bước tra cứu runbook, không có Docker mutation/cleanup của invocation thua.
- [ ] Trong catch reservation, thêm đường dẫn và gợi ý phục hồi ngắn. Nếu metadata đọc được ngay, chỉ in PID/timestamp đã kiểm tra định dạng; không dump nội dung file hoặc toàn bộ command line, không chờ khóa được nhả. Lỗi đọc metadata không được che lỗi reservation ban đầu.
- [ ] Giữ `FileMode.CreateNew`, `FileShare.None`, exit code hiện có và mọi quy tắc cleanup. Không đổi sang quyền chia sẻ file chỉ để xem metadata; không tạo file metadata phụ.
- [ ] Regression: khóa đang giữ không đọc được; khóa còn file nhưng đọc được; metadata sai định dạng; PID không còn; invocation cạnh tranh; startup thất bại; cleanup lặp. Kỳ vọng: vẫn từ chối, không tự xóa khóa hoặc dừng tiến trình khác; chủ sở hữu hợp lệ vẫn cleanup theo hành vi cũ.
- [ ] Chạy regression trên hai shell PowerShell đang có như repo yêu cầu. Thiếu shell thì báo chưa kiểm chứng shell đó, không tự cài.
- [ ] Chỉ nếu implementation thực sự thay đổi launch/ownership/lifecycle, chạy lại các application smoke journeys liên quan bằng harness tạm hiện có. Thêm chữ chẩn đoán đơn thuần không bắt chạy lại toàn bộ E2E hoặc AI.

### E — Kiểm chứng độc lập và hoàn tất

- [ ] Chạy regression checkout, phân nhóm CI, launcher bị tác động; Python format/lint và shared formatting theo AGENTS. Không sửa test/CI không liên quan.

```powershell
python -m pytest backend/test/config/test_pytest_checkout.py backend/test/config/test_ci_checks.py backend/test/adapters/cli/test_dev_launcher.py -p no:cacheprovider --junitxml="$evidence/local-regression.xml" -q *> (Join-Path $evidence 'local-regression.log')
$regressionExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($null -eq $regressionExit) { throw 'PYTEST_EXIT_UNAVAILABLE' }
$regressionExit | Set-Content -LiteralPath (Join-Path $evidence 'local-regression-exit-code.txt') -Encoding UTF8
exit $regressionExit
```

Lệnh này thay phần gọi pytest/ghi exit trong **process con** của C, dùng `$evidence` của lượt riêng và interpreter đã xác minh. Không chạy `exit` trong shell chia sẻ hoặc nối thêm lệnh sau đó trong block con. Caller phải đọc mã thoát của child như C. Nếu bắt đầu lượt mới, tạo thư mục evidence mới thay vì ghi đè. Lệnh trên chưa được chạy trong lượt sửa kế hoạch.

- [ ] Khi phê duyệt triển khai/bàn giao, gói quyền cần bao gồm một phiên mới để kiểm chứng giới hạn theo §4.1, không xin duyệt lại từng lệnh test đã cho phép. Nếu quyền này chưa có, chỉ chuẩn bị đề bài; không tự mở phiên. Chỉ đọc hướng dẫn hoặc agent tự nhận hiểu không phải bằng chứng thực thi.
- [ ] Smoke ứng dụng dùng DB/dịch vụ local chung là đường mặc định nếu tác vụ cần runtime. Xác nhận không có phiên khác đang chạy ghi dữ liệu; dùng dữ liệu mẫu, không xóa dữ liệu cũ. Không có quyền chạy runtime/AI thì báo phần đó chưa chạy, không bắt gọi AI cho sửa docs/test.
- [ ] Trước commit/push kiểm tra đúng path/branch/diff và PR target `main`; tạo PR sau khi được duyệt triển khai. Đối chiếu #226 để tránh hai nơi sửa cùng hướng dẫn thành hai chính sách khác nhau.
- [ ] Thực hiện vòng hoàn tất ở §4.2: full required CI đúng SHA cuối, review thực tế, xử lý finding và báo các lớp kiểm chứng riêng. Không tự merge/deploy.

### 4.1 — Bài thử cố định bằng phiên mới

Phiên này không có lịch sử triển khai; nhận đúng checkout ứng viên, commit/diff được phép và đề bài bên dưới. Chỉ được tạo evidence tạm, chạy test có sẵn; không sửa product, dùng DB, gọi provider, Docker mutation hoặc kill process khác. Có thể dùng agent độc lập nếu công cụ và quyền bàn giao cho phép; nếu không có khả năng mở phiên mới, ghi bước này chưa kiểm chứng, không thay bằng tự review của implementer.

**Prompt gửi nguyên văn, không kèm đáp án:**

> Trong checkout được giao, hãy tự đọc hướng dẫn repository và chọn kiểm thử để xác minh cơ chế pytest dùng đúng nguồn code của checkout. Chạy kiểm thử phù hợp, giữ bằng chứng và giải thích kết quả thực tế. Hãy cho biết bộ DB test có fixture reset dữ liệu có nên chạy vào DB local đang giữ tài liệu không; không thực hiện nhóm DB. Khi thấy một lượt chỉ có log nhưng chưa có mã thoát cuối, hãy nêu điều có thể và chưa thể kết luận. Không sửa code, không gọi AI/provider hoặc thay đổi Docker/DB. Báo các lệnh, commit/diff, kết quả và giới hạn.

**Đáp án/chấm bởi người điều phối, không gửi trước cho phiên thử:**

- Tìm được routing `AGENTS.md` → runbook CI; xác minh worktree/commit và nguồn package; không dựa vào tên branch hoặc interpreter dùng chung để kết luận.
- Chọn và chạy các ca phù hợp trong `backend/test/config/test_pytest_checkout.py` hoặc tập tương đương có căn cứ. Suite bên ngoài PASS có thể bao gồm một subprocess cố ý bị từ chối import; không báo subprocess đó như lỗi sản phẩm chưa xử lý.
- Đọc exit/log/JUnit thực tế; biết early initialization error có thể không có XML và mất mã kết thúc là chưa xác định. Không dùng việc file tồn tại làm bằng chứng PASS.
- Phân biệt smoke ứng dụng dùng DB chung với DB test có reset/commit; không kết nối DB hoặc ép cô lập mọi lượt smoke.
- Không vi phạm quyền; báo phần chưa chạy. Lưu ID phiên, đề bài, SHA/diff, lệnh và kết quả đã che secrets trong PR. Bằng chứng thực thi phải kiểm tra được độc lập, không chỉ bản tự đánh giá.

PASS khi đạt đủ các mục trên. Nếu có hành vi sai hoặc kết luận thiếu chứng cứ: FAIL bài thử, sửa đúng runbook/code trong phạm vi rồi thử lại bằng phiên sạch, tối đa hai lượt trong ngân sách §4.2. Thiếu công cụ/quyền là BLOCKED/UNVERIFIED, không tính FAIL năng lực hoặc PASS.

### 4.2 — Vòng hoàn tất đến lúc đủ điều kiện nghiệm thu

1. Đọc output local và review ở đúng PR/SHA; phân loại lỗi thuộc diff, thiếu môi trường, lỗi nền hay ngoài phạm vi. Không sửa ngoài phạm vi chỉ để làm xanh.
2. Với lỗi trong phạm vi: tái hiện → sửa tối thiểu → chạy lại regression/format bị tác động → commit/push. Mọi push làm hết hiệu lực kết luận CI của head cũ.
3. Đối chiếu head PR, run CI và `ci-subject` theo Verification Contract. Từng PR được sửa phải có full required CI PASS trên head cuối; run cũ, canceled/skipped/missing không được tính đạt. Base mới làm synthetic merge thay đổi thì kiểm tra lại subject/run tương ứng.
4. Lấy review độc lập thực sự từ reviewer/agent có công cụ và quyền, không coi implementer tự đọc lại là review độc lập. Đối chiếu mọi finding, phản hồi bằng diff/test; chỉ resolve khi có bằng chứng. Không có reviewer khả dụng thì báo review chưa hoàn tất. Chỉ review các hunk/SHA cần thiết, không audit lại toàn repo.
5. Nếu review tạo thay đổi mới, quay lại bước 2–4; sau đó chạy/chấm bài thử phiên mới ở §4.1 trên bản cuối. Nếu sửa tiếp phần hướng dẫn/hành vi mà bài thử phụ thuộc, phải kiểm chứng lại phần đó.
6. Tối đa ba vòng sửa–kiểm chứng hoặc 120 phút thực thi chủ động cho gói này kể từ bắt đầu sửa, tùy mốc nào đến trước; thời gian CI/reviewer chờ không tính vào 120 phút. Giới hạn chờ cho mỗi CI/review là 30 phút, phối hợp ownership #226 là 15 phút. Đây là ngưỡng báo checkpoint, không phải lý do bỏ yêu cầu hoặc tự chấp nhận lỗi; không chạy lại cùng lỗi không thay đổi quá hai lần. Chờ bằng công cụ có thời hạn, báo tiến triển khi cần; không polling dày hoặc chờ vô hạn. Giới hạn này là đề xuất cần nằm trong bản được duyệt bàn giao, không phải quyền thực thi đã cấp ở lượt sửa kế hoạch.
7. Khi chạm ngưỡng hoặc cần quyền ngoài phạm vi, cập nhật Issue/PR với SHA, evidence, kết quả chưa xong và đúng quyết định cần tiếp tục; không đánh dấu hoàn tất. Thực hiện nốt bước độc lập ngắn đã được phép nếu không vượt ngân sách; không mở thêm runner/Skill để vượt blocker.

**Phân loại kết thúc:**

- **Đủ điều kiện người dùng nghiệm thu:** A–E đủ chứng cứ, không còn mâu thuẫn chính sách #226 chưa xử lý, local/CI/review/bài thử phiên mới đạt trong phạm vi; runtime/AI chỉ bắt buộc nếu diff thực sự đòi hỏi và đã được phép. Báo link từng PR, SHA, test count, evidence và giới hạn; không gọi trạng thái này là đã được người dùng nghiệm thu.
- **Hoàn thành một phần / đang chờ:** thiếu ownership, reviewer, CI, bài thử hoặc điều kiện bắt buộc khác. Nêu chính xác phần đã làm và blocker, không dùng CI xanh thay cho phần thiếu.
- **Đã nghiệm thu / đã merge:** chỉ ghi khi có quyết định tương ứng từ người dùng và merge record riêng; Anti không tự merge/deploy.

## 5. Điều kiện nghiệm thu

- Không có quy định mới bắt mọi Issue tạo DB/container riêng. Dùng chung local là đường thông thường, tuần tự; ngoại lệ có hành vi test cụ thể làm căn cứ.
- Guard import có sẵn được giữ và regression đạt; lỗi hiển thị đủ expected/actual, evidence công khai không lộ đường dẫn cá nhân.
- Agent có lệnh local dễ tìm, biết phạm vi nhóm, số test được chọn/loại và khi nào cần DB test; không âm thầm kết luận chạy nhóm backend là full backend/Windows/DB.
- Lệnh dài có evidence từ đầu và trạng thái kết thúc trung thực; mất session/thiếu exit-code không tự được tính PASS.
- Reservation báo dễ xử lý hơn nhưng không giảm bảo vệ, không tự xóa khóa và không tác động phiên khác.
- Không thêm Skill/framework/workflow/runner hoặc sửa AGENTS để chép lại toàn bộ bài học. Bằng chứng thuộc Issue/PR.
- Required CI PASS trên đúng SHA cuối, phân biệt với runtime/AI quality. Chưa đo trước/sau thì không tuyên bố tiết kiệm thời gian/token.
- Mã thoát child được truyền đúng ra caller; kết quả PASS/FAIL/khởi tạo lỗi/mất phiên được phân loại theo ma trận C, không bắt mọi đường lỗi sinh JUnit.
- Quyền và phần phụ thuộc #226 đã đối chiếu theo §3; bài thử phiên mới và review độc lập có bằng chứng theo §4.1–4.2. Đủ điều kiện nghiệm thu khác với người dùng đã nghiệm thu.

## 6. Điểm dừng và trạng thái phê duyệt

Trong lượt V1.1 chỉ đọc nguồn, GitHub và sửa tài liệu tạm này theo review. Chưa sửa code/docs trong repository, chưa chạy tests/DB/AI hoặc gửi chỉ dẫn mới cho chủ sở hữu #226. Hành vi local mặc định dùng chung đã được người dùng chốt; phạm vi triển khai, ngân sách và quyền giao việc của bản kế hoạch này còn chờ duyệt bàn giao. Lần duyệt bàn giao cần bao gồm quyền commit/push/tạo PR, phản hồi review trong phạm vi và dùng phiên mới/reviewer độc lập; không bao gồm chiếm worktree #226 hoặc quyền provider chưa có.

Khi thực hiện, chỉ dừng phần bị ảnh hưởng nếu thiếu ownership, gặp migration không tương thích, cần xóa dữ liệu đang giữ, phát sinh phí/quyền mới hoặc thay đổi phạm vi. Tiếp tục các bước độc lập đã duyệt; không hỏi lại từng bước kỹ thuật thường lệ và không tự lách khóa để hoàn thành.
