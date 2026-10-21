# An toàn dữ liệu và khởi động launcher — kế hoạch xử lý review

> **For agentic workers:** Use `executing-plans` if available and authorized in the actual
> skill catalog; otherwise follow these steps directly. This work is handed to Antigravity,
> not to additional Codex sessions. Do not install skills or delegate further by default.

**Goal:** Hoàn thiện PR #214 để launcher không nhận nhầm dữ liệu, không tranh quyền sử dụng
project giữa các phiên và không chờ vô hạn khi đọc metadata Docker.

**Architecture:** Giữ launcher và harness hiện tại. Tái sử dụng cách tạo file giữ chỗ nguyên tử
trong `scripts/prepare-figma-e2e.ps1`, nhưng không sao chép cleanup xóa dữ liệu của harness đó.
Kiểm tra container lẫn volume dưới cùng quyền giữ chỗ; chỉ dùng API/thư viện hệ thống đã có.

**Tech Stack:** Windows PowerShell 5.1, PowerShell 7, Docker Desktop/Compose, Python/pytest,
Windows Job Object và GitHub Actions hiện có.

**Spec:** Review được người dùng duyệt cho
[PR #214](https://github.com/NhiBuaa/knora-agent/pull/214), các review thread ở mục 6,
`AGENTS.md`, `docs/runbooks/ci.md#verification-contract`,
`docs/runbooks/local-development.md` và `docs/runbooks/agent-environment.md`.

## 1. Điểm xuất phát và phạm vi

- PR đang mở, nhắm `main`; nhánh `fix/launcher-preflight-test-isolation`.
- Head được kiểm tra ngày 2026-10-21: `ae017923728a0453d0b74b32ee2a70fbf30a37d1`.
- Base lúc kiểm tra: `de7f97dac40823cc5b9da3e626522a05caa8b732`.
- [CI 39558339040](https://github.com/NhiBuaa/knora-agent/actions/runs/39558339040)
  đạt trên head trên. Đây không phải bằng chứng cho commit sửa tiếp theo.
- Lượt review đã chạy 49 test đạt, 50 deselected: 48 ca quyền sở hữu và regression proxy.
  Mô phỏng hai phép kiểm tra đồng thời cho kết quả cả hai được chấp nhận; không chạy Compose.
- Đã đọc metadata Docker thật: volume PostgreSQL/MinIO có nhãn project nhưng không có
  đường dẫn checkout; container PostgreSQL đã dừng có `NetworkSettings.Ports = {}`.
  Không khởi động, xóa hoặc thay đổi các tài nguyên đó.

### Global Constraints

- Sửa trên chính nhánh PR #214; không tự merge, không force-push, không tạo PR thay thế.
- Đọc lại head, diff, review threads và trạng thái worktree trước khi sửa. Nếu head đã đổi,
  đối chiếu delta, giữ thay đổi của người khác; không reset hoặc ghi đè file untracked.
- Không sửa sản phẩm, schema, provider, giao diện, Figma/OTP harness hay kiến trúc ứng dụng.
- Không thêm Skill, dependency, hook, workflow, dịch vụ khóa hoặc kho trạng thái mới.
  File giữ chỗ có vòng đời hữu hạn là cơ chế loại trừ thao tác, không phải sổ tiến độ.
- Giữ nguyên các sửa proxy và tài liệu lịch sử của PR. Không mở lại Issue #153/S2 đã nghiệm thu.
- Không chạy launcher thật vào project `knora-dev` đang có trên máy để thử lỗi.
  Không `prune`, `down --volumes`, tự đổi nhãn nhận quyền, hoặc tự dừng phiên khác.
- Giữ dữ liệu Docker khi dừng daily launcher như hiện tại. Chỉ dọn process/file thực sự thuộc
  lần chạy; không sao chép chính sách xóa volume của disposable Figma harness.
- Tự xử lý các bước sửa, test, commit/push, phản hồi review và theo dõi CI trong phạm vi này.
  Chỉ hỏi khi cần quyền/cài đặt/chi phí mới, có sửa chồng không thể hòa giải an toàn,
  hoặc muốn thay đổi chính sách/kiến trúc ngoài phạm vi.
- Không công bố token/password, `.env`, log rộng hoặc đường dẫn user-local. Dùng `[REDACTED]`
  cho giá trị nhạy cảm và `<owned-temp>` cho thư mục cá nhân; giữ cấu trúc lệnh để tái hiện.

### File được tác động

| File | Trách nhiệm |
| --- | --- |
| `scripts/start-dev.ps1` | Giữ chỗ, kiểm tra chủ sở hữu container/volume, giới hạn đọc Docker, xử lý kết thúc |
| `backend/test/adapters/cli/test_dev_launcher.py` | Regression và fixture hiện có; kiểm tra cả hai shell |
| `docs/runbooks/local-development.md` | Bổ sung ngắn hành vi từ chối, giới hạn và cách xử lý an toàn |
| Tài liệu kế hoạch này | Kế hoạch tĩnh; kết quả thực thi và tiến độ vẫn thuộc PR |

Chỉ đọc `scripts/prepare-figma-e2e.ps1`, `scripts/dev-process-job.cs`,
`docker-compose.dev.yml`, `test_ollama_launcher.py` và các hợp đồng CI liên quan.
Giữ nguyên cơ chế Job Object trong file C#; không tạo bộ quản lý process thay thế.

## 2. Tác vụ A — giữ chỗ trước kiểm tra và khởi động

**Files:** sửa launcher và `test_dev_launcher.py`; tái sử dụng mẫu tại
`prepare-figma-e2e.ps1:53-61,114-132`, không sửa harness Figma.

**Interface giữ nguyên:** tham số public của `start-dev.ps1`,
`Test-DevStorageOwnership([bool]$PostgresPortInUse)` và đường `-PreflightOnly`.
Không thêm cờ bỏ qua kiểm tra hoặc cờ tự nhận quyền sở hữu.

- [ ] Thêm test hai tiến trình PowerShell riêng, hai checkout giả, chung TEMP/TMP do test sở hữu.
  Dùng tín hiệu file/event để dừng A trong cửa sổ kiểm tra; khởi động B khi A vẫn giữ chỗ.
  Không dùng `sleep` làm bằng chứng duy nhất; mỗi lần đợi phải có deadline và thu log khi lỗi.
- [ ] Chạy test trước sửa: phải chứng minh B chưa bị ngăn đúng lúc, không phải lỗi fixture.
- [ ] Tạo file giữ chỗ duy nhất cho project, cùng đường dẫn qua các worktree của cùng user.
  Dùng đúng cơ chế nguyên tử có sẵn, không dùng `Test-Path` rồi mới tạo:

  ```powershell
  $reservationPath = Join-Path ([IO.Path]::GetTempPath()) 'knora-dev-reservation-knora-dev.lock'
  $reservation = [IO.File]::Open($reservationPath, [IO.FileMode]::CreateNew,
      [IO.FileAccess]::Write, [IO.FileShare]::None)
  ```

  Chuyển lỗi tồn tại/không truy cập được thành từ chối rõ, ví dụ
  `DEV_PROJECT_RESERVED:knora-dev`; không in toàn bộ đường dẫn cá nhân ra PR.
- [ ] Lấy quyền trước đọc quyền sở hữu và trước provider/Compose/migration/log ghi đè;
  kiểm tra lại cổng và metadata sau khi lấy quyền. Giữ quyền suốt khởi động, runtime và
  cleanup process hiện có. Chỉ chèn một vòng `try/finally` bao vòng đời cần bảo vệ.
- [ ] B bị từ chối phải không gọi Compose, không cắt log, không xóa claim của A,
  không đụng process hay dữ liệu của A. Kiểm tra cả hai invocation cùng checkout.
- [ ] Thoát bình thường, lỗi validation, lỗi startup đã kết thúc rõ ràng và cleanup thành công:
  đóng handle, xóa đúng file claim mình vừa tạo; lần chạy sau phải lấy quyền được.
- [ ] Force-kill hoặc kết quả cleanup/tiến trình mutating còn không xác định: không tự xóa
  claim để cho phép invocation mới. Không suy từ PID gốc đã chết rằng mọi child đã chết.
  Dùng cách giữ claim bảo thủ như harness hiện có; báo cần kiểm tra thủ công, không tự phá khóa.
- [ ] Test `Ctrl+C`, startup thất bại một phần, lỗi trong cleanup, claim có sẵn và phiên bị
  force-kill; chỉ giết process do fixture vừa tạo. Chứng minh outsider vẫn sống.
- [ ] `-PreflightOnly` vẫn không giữ chỗ, không gọi Docker, không khởi động hay cleanup stack.
- [ ] Chạy test sau sửa trên PowerShell 5.1 và 7; nếu thiếu shell thì ghi giới hạn,
  không xem test bị skip là bằng chứng đủ để chốt tương thích.

Giới hạn được chấp nhận: các launcher cùng user, chung thư mục temp, dùng Docker Desktop local.
Không tuyên bố khóa này bảo vệ trước người khác chạy Compose trực tiếp, user khác, remote daemon
hoặc binary launcher cũ không hợp tác. Không thêm distributed locking.

## 3. Tác vụ B — kiểm tra cả dữ liệu còn lại, không tự nhận quyền

**Files:** `start-dev.ps1`, test quyền sở hữu hiện có trong `test_dev_launcher.py`.
Tiêu thụ claim từ A; vẫn trả boolean từ `Test-DevStorageOwnership` cho các lỗi ownership.

- [ ] Mở rộng Docker double hiện có với các trường hợp: không container nhưng còn volume;
  container đúng checkout nhưng volume không xác minh được; volume trùng tên dự kiến nhưng
  nhãn thiếu/sai; volume PostgreSQL, MinIO và các volume của bundled Keycloak được dùng khi launch.
- [ ] Chạy regression mới trước sửa; với cổng trống, case volume mồ côi phải hiện đang đi
  tới `INVALID_EMBEDDING_PROVIDER`, thay vì bị từ chối ownership.
- [ ] Kiểm tra volume thực sự Compose có thể gắn, kể cả khi bộ lọc nhãn không thấy nó.
  Đối chiếu tên dự kiến từ compose hiện có, nhãn project/volume và mount của container đáng tin.
  Không chỉ lọc `label=com.docker.compose.project=knora-dev` rồi coi không thấy là an toàn.
- [ ] Volume chỉ có project/name không chứng minh checkout. Khi chỉ còn volume, không có
  bằng chứng chủ sở hữu đáng tin: từ chối trước Compose và migration. Không tự viết nhãn,
  chuyển dữ liệu, tạo database thay thế, đổi project name hoặc xóa volume để test xanh.
- [ ] Nếu chấp nhận reuse qua container hiện hữu, phải khớp checkout, project, service và
  mount/source của từng volume cần dùng; không lấy một container đúng làm bằng chứng cho mọi volume.
  Thiếu JSON/trường dữ liệu, inspect lỗi hoặc Docker unavailable đều phải từ chối an toàn.
- [ ] Giữ hai đường hợp lệ: project hoàn toàn mới không có tài nguyên còn lại; và tài nguyên
  đã xác minh cùng checkout. Khi cổng PostgreSQL bận vẫn cần đúng loopback binding như hiện tại.
- [ ] Các test refusal phải chứng minh không Compose/provider/migration/log mutation và listener
  ban đầu vẫn hoạt động. Ví dụ assertion mở rộng trực tiếp từ test hiện có:

  ```python
  assert result.returncode == 2, result.stderr
  assert "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev" in result.stderr
  assert "COMPOSE_MUTATION_ATTEMPTED" not in result.stderr
  ```

  Đồng thời đọc danh sách lệnh double thực nhận, chỉ cho phép metadata chỉ đọc;
  không dùng riêng chuỗi stdout làm bằng chứng không có tác động.
- [ ] Test dữ liệu tổng hợp đại diện JSON thật; không đưa credentials, `.Config.Env` hoặc
  dữ liệu thật vào fixture. Giữ nguyên lịch sử 48 ca cũ, cập nhật kỳ vọng theo hợp đồng mới.

Đánh đổi chủ ý: sau khi container bị xóa, một số volume cũ không còn chứng minh được chủ sở hữu
sẽ bị từ chối. Tài liệu phải giải thích đây là bảo vệ dữ liệu, không hướng dẫn tự xóa volume.
Không thêm kho lưu ownership lâu dài chỉ để tránh việc từ chối này.

## 4. Tác vụ C — chặn thời gian đọc Docker và giữ test đáng tin

**Files:** launcher và các fixture/test đang sở hữu hành vi, không thêm framework/script mới.

- [ ] Thêm fake CLI thực sự chạy process cho tình huống metadata bị treo. Test phải đi qua
  đường timeout thật, không mock luôn timeout/helper rồi tự khẳng định cơ chế hoạt động.
- [ ] Giới hạn metadata: tối đa 10 giây mỗi lệnh và 30 giây cho một lượt ownership scan,
  theo đồng hồ đo thời gian trôi qua. Giữ các mức này thành hằng private, không thêm cấu hình public.
- [ ] Trên PS5.1 và PS7, đọc stdout/stderr bất đồng bộ đồng thời, chờ process có hạn;
  không gọi `ReadToEnd()`/`.Result` vô hạn trước hoặc sau `WaitForExit(timeout)`.
  Dùng process handle của chính lệnh vừa tạo; không kill theo tên `docker` hay theo cổng.
- [ ] Khi hết hạn: dừng/thu hồi đúng child metadata, trả lỗi rõ như
  `DOCKER_METADATA_TIMEOUT:knora-dev`, không tiếp tục provider/Compose/migration.
  Không giết daemon hay CLI của phiên khác. Không mở rộng timeout này sang toàn bộ workflow sản phẩm.
- [ ] Kiểm tra lỗi exit code, JSON hỏng, output rỗng và stdout/stderr nhiều hơn bộ đệm pipe;
  test cả đường thực thi có khoảng trắng. Không dùng API chỉ có ở .NET mới mà PS5.1 không hỗ trợ.
- [ ] Deadline của test treo phải lớn hơn deadline launcher một khoảng hữu hạn; test xác minh
  lỗi do launcher trả về và process đã kết thúc, không phải chỉ `subprocess.TimeoutExpired` từ pytest.
- [ ] Cập nhật Docker double/fixture khi boundary gọi Docker thay đổi; không bỏ test cũ hoặc
  cho phép chúng gọi Docker thật ngoài ý muốn. TEMP/TMP phải thuộc từng test;
  chỉ hai invocation trong một test cạnh tranh mới dùng chung thư mục đó.
- [ ] Nếu phải sửa fixture cleanup, giữ cổng PostgreSQL giả bằng socket đã bind nhưng không
  listen suốt thời gian cần thiết, vì Docker double không cần bind cổng PostgreSQL. Tái sử dụng mẫu
  socket đang có trong test guard; không retry mọi lỗi startup để che lỗi thật.
  Chỉ thay cách giữ cổng giả của fixture, không đổi kiểm tra cổng sản phẩm.
- [ ] Chạy lại toàn bộ hai file test launcher, gồm proxy và cleanup, không chỉ các test mới.

## 5. Kiểm chứng và hướng dẫn vận hành

- [ ] Cập nhật ngắn `docs/runbooks/local-development.md` tại hướng dẫn startup/cleanup:
  claim dùng chung, volume chưa xác minh bị từ chối, timeout đọc Docker, giữ nguyên storage
  sau Ctrl+C, và giới hạn cùng user/local Docker. Không tạo thêm runbook hoặc hướng dẫn reset dữ liệu.
- [ ] Dùng môi trường Python đã cài pytest; tại máy bàn giao, Python mặc định không có pytest,
  còn `.venv/Scripts/python.exe` trong primary checkout đã chạy được bộ test ở lượt review.
  Kiểm tra lại trước dùng, không tự cài dependency. Tắt bytecode/cache; giữ proxy cleanup trong
  riêng môi trường test, không sửa proxy user/system.
- [ ] Từ gốc đúng worktree, với `$pythonExe` trỏ Python đã xác minh, chạy:

  ```powershell
  $pythonExe = 'C:\Developer\Projects\knora-agent\.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Existing test Python is unavailable' }
  & $pythonExe -c 'import pytest; print(pytest.__version__)'
  if ($LASTEXITCODE -ne 0) { throw 'Existing test Python cannot import pytest' }
  $env:PYTHONDONTWRITEBYTECODE = '1'
  $env:PYTHONPATH = (Join-Path (Get-Location) 'backend/src') + ';' + (Get-Location).Path
  & $pythonExe -m pytest -p no:cacheprovider backend/test/adapters/cli/test_dev_launcher.py backend/test/adapters/cli/test_ollama_launcher.py -q
  & $pythonExe -m ruff format .
  & $pythonExe -m ruff format --check .
  & $pythonExe -m ruff check .
  git diff --check
  ```

  Kiểm tra exit code từng lệnh; nếu format đổi mã sau test thì chạy lại phần bị tác động.
  Dùng JUnit ở thư mục kết quả mới do mình sở hữu khi ghi evidence; giữ cả các lần chưa đạt.
- [ ] Nếu đọc Docker thật, chỉ đọc IDs/state/mounts/nhãn liên quan; không dump inspect toàn bộ.
  Không cần ứng dụng/browser/provider thật để chứng minh ba sửa lỗi orchestration này.
  Các runtime fixture dùng process/socket thật nhưng Docker giả phải được báo đúng như vậy.
  Browser smoke trên Figma không thay thế kiểm chứng daily launcher; không sửa harness để trình diễn.
- [ ] Tự review diff cuối theo ba ranh giới an toàn; kiểm tra trạng thái/docs cũ của PR không
  bị mất. Mỗi claim trong báo cáo phải có assertion hoặc kết quả thực thi tương ứng.

## 6. Xử lý review, push và điều kiện bàn giao kết quả

Đọc lại thread trước phản hồi; tên/line có thể dịch chuyển sau sửa:

| Thread | Xử lý |
| --- | --- |
| [4333903533 — retained volumes](https://github.com/NhiBuaa/knora-agent/pull/214#discussion_r4333903533) | Tác vụ B, regression trước/sau và chứng minh từ chối không thay dữ liệu |
| [4333903545 — concurrent launchers](https://github.com/NhiBuaa/knora-agent/pull/214#discussion_r4333903545) | Tác vụ A, hai process có đồng bộ, lifecycle/claim và outsider survival |
| [4333903568 — Docker hang](https://github.com/NhiBuaa/knora-agent/pull/214#discussion_r4333903568) | Tác vụ C, timeout thực sự và thu hồi đúng child |
| [4333903553 — stopped container](https://github.com/NhiBuaa/knora-agent/pull/214#discussion_r4333903553) | Không gọi là lỗi đã tái hiện. Nêu metadata thực tế rỗng và phạm vi chứng minh; nếu thêm kiểm tra running nhỏ ở cùng boundary, phải có regression và nói rõ đây là phòng vệ |
| [4333903558 — overlapping ports](https://github.com/NhiBuaa/knora-agent/pull/214#discussion_r4333903558) | Lỗi có trước PR, review đã phân biệt. Báo rõ chưa sửa trong gói ba vấn đề; không âm thầm mở rộng sản phẩm chỉ để đóng hết thread |
| [4333903579 — fixture port race](https://github.com/NhiBuaa/knora-agent/pull/214#discussion_r4333903579) | Không khẳng định đã quan sát test chập chờn. Nếu giữ socket như C, chứng minh fixture không chia sẻ cổng; nếu chưa sửa, ghi giới hạn thật |

- [ ] Sau test và self-review đạt, commit/push bình thường vào đúng nhánh PR #214.
  Stage từng file có chủ đích; kế hoạch này do Codex tạo mới, không phải untracked của người khác.
  Không stage thay đổi ngoài phạm vi hoặc toàn bộ thư mục chỉ vì tiện.
- [ ] Phản hồi từng review thread bằng commit/file/test/count và kết quả thật. Chỉ resolve
  khi lỗi đã sửa và kiểm chứng hoặc có căn cứ kỹ thuật đủ bác bỏ; chưa chắc thì để mở và báo rõ.
  Không dùng việc CI xanh làm lý do tự đóng một vấn đề an toàn chưa xử lý.
- [ ] Cập nhật body PR: evidence trước/sau, giới hạn claim/volume, trạng thái thực thi và
  những nhận xét chưa sửa. Không ghi đè bằng chứng thất bại cũ hoặc tự xóa historical evidence.
- [ ] Đợi full required CI trên SHA cuối: Frontend, Backend Ubuntu/Windows, Database, Keycloak
  và `CI required`. Đối chiếu head PR với `head_sha` của run và artifact `ci-subject`:
  `pr_head_sha` là head PR, `checkout_sha` có thể là synthetic merge; không đồng nhất hai SHA.
  Có push mới thì kết quả SHA trước không còn đủ. Không skip/nới CI; không lặp rerun vô hạn.
- [ ] Nếu CI fail, đọc đúng job lỗi, sửa trong phạm vi rồi chạy lại test liên quan và CI.
  Nếu là sự cố hạ tầng/quyền/công cụ chưa được cấp, báo blocker kèm bằng chứng; không tự cài hoặc đổi quyền.
- [ ] Kết quả cuối bằng tiếng Việt ngắn: ba finding xử lý thế nào; file đã sửa; lệnh/test/count
  thực chạy; head SHA và link CI; thread nào còn mở; giới hạn runtime; kết luận đủ/chưa đủ merge.
  Phân biệt đã sửa, local đạt, CI đạt, runtime ứng dụng đã chạy, review, merge và deploy.
  Không tự merge hoặc deploy.

## 7. Điều kiện kết thúc, không bàn giao qua lại vì việc thông thường

Hoàn thành khi A/B/C có regression trước/sau, các đường startup/refusal/cleanup liên quan đạt
trên hai shell, dữ liệu/outsider không bị tác động, diff trong phạm vi, PR đã push và required CI
đạt trên SHA cuối. Nhận xét chưa được sửa/bác bỏ phải còn được nêu, không đổi thành PASS cho đẹp.

Không dừng sau mỗi test đỏ hay sau việc viết kế hoạch. Tự phân tích, sửa, chạy lại và theo dõi CI
trong phạm vi đã giao. Chỉ dừng khi hoàn thành hoặc có blocker cần quyết định/quyền thật sự;
khi đó nêu chính xác phần đã xong, bằng chứng, lý do không thể tiếp tục an toàn và một câu hỏi cần trả lời.
## 8. Kết quả khắc phục và hoàn thiện (Remediation & Final Safety Completion)

Theo các gói bàn giao `dev-launcher-storage-safety-remediation-antigravity-20261021.md` và `dev-launcher-safety-completion-antigravity-20261021.md`, các điểm kỹ thuật còn thiếu và 4 review findings đã được hoàn thiện triệt để:

1. **Volume bắt buộc nhãn hợp lệ và kiểm chứng inspect thực tế (Finding 1 / P1 - Thread 4333903533)**:
   - `Test-DevStorageOwnership` siết chặt xác thực nhãn: nhãn volume không được null, rỗng, thiếu project hoặc thiếu role; mọi trường hợp nhãn không hợp lệ đều bị từ chối với `COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev`.
   - Sửa `test_launcher_refuses_when_volume_inspect_fails_on_existing_volume` để có container gắn volume và dùng marker file xác nhận lệnh volume inspect thực sự được gọi trước khi bị từ chối.
   - Mở rộng `test_launcher_verifies_volume_destination_and_role_label` kiểm thử toàn diện 10 trường hợp nhãn (null-labels, empty-labels, missing-project, missing-role, empty-project, empty-role, wrong-project, wrong-role) và mount destination (wrong-destination, valid).

2. **Dọn sạch sau lỗi khởi động và giải phóng reservation (Finding 2 / P2 - Thread 4333903545)**:
   - Phân biệt rõ ràng giữa mutating startup bất định / dọn dẹp lỗi (giữ lại lock file kèm PID, repo, timestamp và cảnh báo `DEV_RESERVATION_RETAINED:knora-dev`) với lỗi khởi động đã xác định kết thúc và dọn sạch (`startupConfirmed = $true`, `cleanupFailed = $false`): tự động giải phóng khóa để cho phép lần khởi chạy tiếp theo thành công bình thường.
   - Kiểm chứng bằng nhánh `startup-failure` trong `test_launcher_cleans_owned_descendants` và `test_launcher_retains_reservation_on_mutating_startup_uncertainty`.

3. **Thu hồi toàn bộ cây tiến trình metadata bằng Windows Job Object (Finding 3 / P2 - Thread 4333903568)**:
   - Nạp sớm `scripts/dev-process-job.cs` trong `scripts/start-dev.ps1`; mở rộng hỗ trợ file batch `.bat` và bổ sung phương thức `WaitForProcesses` kiểm tra `ActiveProcesses == 0` qua `QueryInformationJobObject`.
   - `Invoke-DockerMetadata` tạo và quản lý tiến trình query trực tiếp trong Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, cấm breakaway), chuyển hướng stdout/stderr ra file tạm trong `%TEMP%` để tránh deadlock anonymous pipe trên Windows.
   - Khi timeout (10s command, 30s scan), Job Object đóng lại và bảo đảm hạt nhân Windows hủy toàn bộ cây tiến trình (gồm cả con, cháu holding pipe).
   - Kiểm chứng bằng regression test `test_launcher_docker_metadata_terminates_child_holding_pipe_within_deadline` với cây tiến trình 3 cấp (root -> middle -> leaf).

4. **Loại bỏ tranh chấp cổng trong fixture và kiểm chứng ổn định (Finding 4 / P2 - Thread 4333903579)**:
   - Trong nhánh `startup-failure` của `test_launcher_cleans_owned_descendants`, dùng socket PostgreSQL đã bind (không listen) giữ cổng độc quyền suốt vòng đời test, loại bỏ hoàn toàn vòng lặp retry cấp cao.
   - Trạng thái review threads:
     - Thread 4333903533: RESOLVED (volume label enforcement & genuine inspect call verification).
     - Thread 4333903545: RESOLVED (clean startup failure releases reservation; uncertainty retains).
     - Thread 4333903568: RESOLVED (job-owned metadata process tree cleanup & WaitForProcesses probe).
     - Thread 4333903579: RESOLVED (bound socket port reservation; high-level retry removed).
     - Thread 4333903558: UNRESOLVED (để mở — lỗi trùng cổng đầu vào là finding có từ trước, ngoài phạm vi PR).
