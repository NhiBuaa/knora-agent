# Knora verification-environment remediation — kế hoạch và bàn giao V1

> **For agentic workers:** Dùng Skill `executing-plans` nếu có trong catalog được phép, thực hiện từng nhiệm vụ và tự review giữa các bước. Nếu không có Skill/công cụ tương ứng, theo quy trình repo và báo giới hạn; không cài Skill, không bịa tên công cụ. Không dừng để xin xác nhận sau mỗi nhiệm vụ thường lệ. Checkbox là danh sách công việc dự kiến; bằng chứng và tiến độ thực tế thuộc Issue/PR.

**Goal:** Xử lý đủ năm bài học #212/PR #227: đóng gói Docker, phụ thuộc frontend giữa worktree, khoảng trống test UI, đầu ra công cụ và routing hướng dẫn; không thay đổi kiến trúc ứng dụng.

**Architecture:** Sửa Dockerfile/Compose và launcher/test/runbook hiện có. Global AGENTS giữ nguyên tắc dùng công cụ; repo AGENTS giữ ranh giới và liên kết đến nguồn sở hữu chi tiết. Không xây hệ thống kiểm chứng hay kho trạng thái mới.

**Tech Stack:** PowerShell, Python/pytest, Docker Compose, Node/npm, Vitest, Playwright và GitHub Actions đang có. Không thêm dependency hoặc workflow.

**Spec / nghiên cứu đầu vào:** `<USER_HOME>\Documents\Codex\2026-10-19\h-y-audit-h-th-ng\verification-environment-research-20261024.md`, SHA256 `A77751B51909A99A5C66C6FB8E745582ECCDB897FFA2059175255D3697162EA4`. Đọc phần tương ứng khi thực hiện, không chép toàn báo cáo vào Issue/PR.

## 0. Phiên bản, nguồn và hiệu lực phê duyệt

- Tạo ngày 2026-10-24, giờ Việt Nam. Đối tượng nghiên cứu: `NhiBuaa/knora-agent`, main `798bdbef4fbe2298cd12af5d2034a361d5d328c9`; PR #227 final head `a10fe329acf5f40046670fb7bac2a5c2bbfaaec2` đã merge.
- Người dùng yêu cầu kế hoạch trọn gói để giao Antigravity tự làm tới nghiệm thu. Lượt soạn này chỉ viết kế hoạch, chưa triển khai. Quyền thực thi dưới đây có hiệu lực khi người dùng gửi prompt duyệt đúng V1/hash của file này hoặc phê duyệt tương đương trong hội thoại. Không tự tạo URL/SHA phê duyệt trên GitHub.
- Tệp Temp là gói bàn giao. Khi bắt đầu triển khai, đưa kế hoạch tại `docs/plans/2026-10-24-verification-environment-remediation.md` trong worktree nhiệm vụ, commit và liên kết full SHA cùng nguồn duyệt hội thoại tại PR. Trước khi commit, thay tiền tố đường dẫn user-local bằng `<USER_HOME>` và ghi đây là bản ẩn danh từ V1/hash đã duyệt; giữ nguyên ý nghĩa, ghi hash riêng của bản trong repo, không giả hai file có cùng hash. Liên kết nguồn mã cố định trong báo cáo nghiên cứu; không công khai username hay ép người đọc PR truy cập file local riêng. Không tạo thêm bản tóm tắt/sổ trạng thái; bản Temp chỉ là bản bàn giao lịch sử. Nếu có thay đổi an toàn không đổi phạm vi, giữ tham chiếu V1 và nêu delta; chỉ đổi ranh giới/phạm vi mới cần duyệt lại.
- Ghi `git hash-object` hoặc SHA256 của kế hoạch trước khi làm; phiên bản mới nhất không tự động kế thừa duyệt. Nếu main tiến lên, so diff các file liên quan: tiếp tục khi tương thích, giữ thay đổi mới; nếu ai đã sửa một mục thì xác minh và tái sử dụng, không làm lại để khớp kế hoạch.
- Không cần duyệt lại thiết kế đã chốt trong tài liệu này. Chỉ dừng khi đúng điều kiện tại §9; không hỏi người dùng lựa chọn lại framework, thư mục, cách chạy hay công cụ vốn đã được quyết định.

## 1. Gói quyền thực thi đề nghị duyệt một lần

### Được tự thực hiện sau khi nhận duyệt

- Đọc repository/GitHub, tạo nhánh `fix/verification-environment-reliability` và worktree mới `C:\Developer\Projects\knora-agent-worktree\fix-verification-environment-reliability` từ main remote mới nhất sau kiểm tra delta. Nếu tên đã được nhiệm vụ khác dùng, thêm hậu tố ngắn mô tả không chứa tên agent; không chiếm hoặc đổi tên tài nguyên cũ.
- Chỉnh đúng các nguồn §3–7; thêm một ignore-file Docker chuyên biệt vì cần bảo vệ context, không thêm chương trình chạy mới. Commit/push nhánh, tạo một PR review trực tiếp vào main, cập nhật bằng chứng và phản hồi review thuộc phạm vi. Không merge.
- Cài phụ thuộc ứng dụng/test đã khai báo và khóa bằng `npm ci` trong frontend thuộc worktree mới này; dùng npm cache hiện có. Cho phép tải đúng Chromium mà Playwright đã khóa yêu cầu, chỉ khi thiếu. Cho phép build image từ dependencies/base image khai báo sẵn. Không nâng phiên bản, sửa lockfile để chữa môi trường, cài Node/Python/Docker/Maven/công cụ toàn máy, Skill, hook hoặc dịch vụ mới.
- Chạy test phù hợp, lint/typecheck/format, full required CI và workflow runtime `application`; được tự sửa nguyên nhân trong phạm vi rồi chạy lại đến khi đủ bằng chứng, không cần xin duyệt mỗi lượt. Chuẩn bị/test local và CI trước dispatch. Dùng quota GitHub hiện có; nếu cần mua/thêm quota hoặc phát sinh dịch vụ trả phí mới thì dừng. Workflow hiện có timeout 90 phút/lần; không tăng timeout hay retry test để che lỗi/treo. Không chạy provider AI trả phí hoặc model inference.
- Cập nhật nhỏ `<USER_HOME>/.codex/AGENTS.md` đúng §6–7, giữ nguyên nội dung khác. Cho phép bản sao lưu cục bộ và diff đã ẩn danh; không công khai toàn bộ cấu hình cá nhân. Chỉ đọc `<USER_HOME>/.gemini/GEMINI.md` để xác nhận tham chiếu, không tạo bản sao quy tắc.
- Tự xử lý lỗi logic, test, formatting, CI/review do thay đổi này gây ra trong phạm vi. Tự đọc báo cáo, sửa rồi chạy lại kiểm tra bị tác động, không hỏi lại từng lệnh.

### Ranh giới không được vượt

- Giữ nguyên main checkout, worktree/stack/bộ cài của phiên khác và file untracked. Không stash/reset, prune, tháo junction cũ, cài đè shared node_modules, kill theo tên/port chung hoặc tự xóa lock.
- Không sửa dữ liệu dev thật, không chạy DB suite có fixture TRUNCATE trên DB đang giữ dữ liệu. Chạy backend/windows partitions hoặc test config đã xác minh không truy cập DB; DB CI dùng môi trường workflow hiện có.
- Runtime application ưu tiên GitHub runner sạch. Local chỉ được dùng harness sẵn có với project hậu tố mới và `-Run`, sau xác minh port/quyền sở hữu. Không chạy `run-runtime-verification.ps1` đầy đủ trên máy chia sẻ: mã đang dùng project cố định `knora-figma-e2e` và cuối cùng `down --volumes`; freshness đọc trước không thay ownership nguyên tử. Không mở rộng lần này sang thiết kế lại runner ownership.
- Không tải `.env` shared vào smoke deterministic, không sửa Keycloak/realm/dữ liệu của stack đang dùng; không chạy OTP/PDF/terminal Turns/citations/deployment như phần mở rộng.
- Không ghi đè image tag dùng chung ở local nếu có thể ảnh hưởng phiên khác; dùng tag image backend riêng cho build kiểm tra, hoặc dùng hosted runtime. Không chạy local launcher build Keycloak tag chung nếu chưa chứng minh an toàn.
- Không đổi rule bảo vệ branch, nới CI, bỏ test, thay assertion/fixture chỉ để PASS; không tự gán Reviewed/Accepted/Merged/Deployed từ test xanh.

## 2. Khởi động và nhận đúng nơi làm

**Đọc:** AGENTS tại đích, `docs/agents/issue-tracker.md`, phần Verification Contract trong `docs/runbooks/ci.md`, `docs/runbooks/agent-environment.md`; đọc thiết kế UI và module seams khi tác vụ thực sự chạm nguồn đó. Chọn Skills theo catalog thực tế, không đoán thư mục.

- [ ] Kiểm tra Git tại checkout chính chỉ đọc: top-level, nhánh, status, worktree list. Chỉ in block của đích cần dùng; không tải toàn bộ danh sách dài vào context. Checkout đã quan sát ở main cũ `36bb3d5…` với untracked reports, phải giữ nguyên.
- [ ] Kiểm tra remote main và diff file liên quan với base nghiên cứu. Tạo worktree mới theo quy tắc repo; nếu app áp đặt đường dẫn trái quy định thì báo giới hạn, không sửa main thay thế.
- [ ] Tại worktree đích chạy và đọc bốn kiểm tra dưới; báo ngắn task/path/branch trước lần sửa đầu tiên. Xác nhận không thuộc phiên khác.

```powershell
git -C $target rev-parse --show-toplevel
git -C $target branch --show-current
git -C $target status --short
git -C $target worktree list --porcelain
```

`$target` là đường dẫn worktree vừa tạo và được kiểm tra, không phải đường dẫn suy từ cwd. Lọc output worktree theo block sau khi thu nhận, không bỏ trường cần xác minh ownership.

- [ ] Lưu bản kế hoạch theo §0, xác định PR/Issue sở hữu tiến độ. Không bắt buộc tạo Issue mới nếu PR có đủ phạm vi/AC và liên kết #212/PR #227; không sửa trạng thái Issue đã hoàn tất.
- [ ] Chọn các check tương ứng trước sửa. CodeGraph chỉ dùng cho truy vết mã cần thiết: status đúng worktree, init/sync theo hướng dẫn hiện hành; nếu lỗi không tự xóa DB/lock. Không đưa map của worktree khác làm bằng chứng.
- [ ] Xác định Python import từ đúng checkout; dùng cơ chế pytest guard hiện có, không chữa thủ công môi trường shared. Trước npm ci, kiểm tra đường dẫn vật lý frontend và node_modules thuộc worktree này, không phải junction ra ngoài; đích đã bị người khác đặt file thì giữ nguyên và báo mâu thuẫn.

**Đạt bước 2:** branch/worktree/source approval xác định được; không thay main/untracked; nguồn kiểm chứng đúng checkout; prerequisites thiếu được phân biệt với lỗi sản phẩm.

## 3. Nhiệm vụ A — Docker đóng gói đủ tài nguyên

**Modify:** `backend/Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.s2.yml`.
**Create:** `backend/Dockerfile.dockerignore`.
**Tests:** `backend/test/config/test_figma_e2e_harness.py`, `backend/test/config/test_runtime_evidence.py`; dùng image build hiện có làm chứng minh đóng gói, không thêm workflow.
**Observe:** `scripts/run-runtime-verification.ps1` bổ sung assertion tài nguyên trong image ở nhánh application để hosted run cũng cung cấp bằng chứng đọc resource, không chỉ container health.
**Docs:** cập nhật ghi chú command build trong runbook chỉ khi lệnh/context thay đổi; không sửa lịch sử bằng chứng.

**Hợp đồng đã chốt:** cả `api` chính, `api` dev, `figma-api` dev và `application` S2 dùng root context `.` cùng `dockerfile: backend/Dockerfile`. Giữ WORKDIR `/app`, CMD hiện có, vị trí migrations/alembic; stage resource sibling theo `../evals`, `../docs`. Không xóa 16 force-include khỏi pyproject, không chuyển nguồn policy/dataset, không sửa loaders.

```dockerfile
# Bố trí đường dẫn cần đạt; giữ các COPY backend và CMD hiện hành.
WORKDIR /app
COPY backend/pyproject.toml backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/src ./src
# COPY từng nhóm file được liệt kê trong force-include vào /evals/...
# COPY policy được liệt kê vào /docs/design/...
RUN pip install --no-cache-dir .
```

Danh sách nguồn lấy trực tiếp từ `[tool.hatch.build.targets.wheel.force-include]` trong `backend/pyproject.toml:43–59` của base; dùng nhóm COPY rõ ràng cho 3 dataset, 5 corpus, 6 runner, 1 scorer, 1 policy. Chỉ chép các file đó, không toàn `evals` hoặc toàn `docs`. Nếu upstream thêm resource thì bảo toàn hợp đồng mới, cập nhật allowlist/test theo nguồn hiện hành.

- [ ] Thêm regression trước sửa: cả bốn service dùng đúng context/Dockerfile; 16 nguồn có trong checkout và được phép vào context; đầu vào được copy đến đường dẫn Hatch thực sự đọc. Dùng parsing/fixture hiện có; không chỉ assert chuỗi `context: .` ở một service.
- [ ] Chạy test mới, xác nhận lỗi phản ánh cấu hình cũ; ghi lại output/mã thoát trong PR. Không tạo production bug giả.
- [ ] Sửa Dockerfile/Compose. Ignore-file chuyên biệt bắt đầu loại tất cả, chỉ mở parent directories và exact input cần thiết, cộng Dockerfile/ignore-file cho builder; không mở toàn `backend/**` rồi vô tình cho secrets/artifacts vào. Kiểm tra cú pháp exception có mở đủ ancestor directories.
- [ ] Thêm kiểm tra bảo vệ context bằng fixture tên giả `.env`, nested `.env`, token/credential giả, `.git`, `node_modules`, report và file mới không thuộc allowlist. Không dùng secret thật để test. Không cài parser dockerignore mới; có thể dùng context build kiểm tra với builder hiện có hoặc test cấu trúc đơn giản cộng build thật. Đừng tuyên bố test parser tự viết chứng minh toàn ngữ nghĩa Docker.
- [ ] Chạy lại test graph/service-profile/launcher. Kiểm tra context Keycloak không đổi; ignore-file backend không làm thay root context của Keycloak.
- [ ] Build image backend tag riêng khi an toàn hoặc lấy build trong hosted application workflow. Không cần chạy S2 app/migration. Trong image kiểm tra installed distribution chứa đủ đích force-include, so nội dung resource với SHA/hash nguồn; import application, đọc catalog manifest/corpus và JSON policy ở đường dẫn loader thực tế, không chạy evaluation/model. Import đơn thuần không đủ chứng minh policy đã đọc.
- [ ] Để có bằng chứng ngay cả khi local Docker không dùng được, thêm check offline tại runner runtime hiện có sau `Add-ImageIdentity`, chỉ nhánh application: đọc danh sách force-include từ checkout, tính hash nguồn, rồi `docker compose exec -T figma-api python -c ...` dùng standard library/importlib để kiểm tra đích installed distribution và hash/resource JSON/corpus. Không đọc `.env`, không chạy scorer/provider/claim acceptance, không tự nhận quyền quyết định M3 từ việc JSON đọc được. Check lỗi phải làm application profile fail; check đạt chỉ in số resource và identity/hash không nhạy cảm. Test runner giả lập xác nhận check diễn ra, nonzero không bị bỏ qua, và OTP không bị gắn thêm luồng này. Không thêm script hay định dạng evidence mới: giữ log/report hiện có và marker ngắn `RUNTIME_PACKAGE_RESOURCES_OK=<count>`; marker đơn độc không thay validator/runtime journeys.
- [ ] Kiểm tra `alembic.ini`, migrations và entrypoint vẫn tìm đúng đường dẫn; migration thật chỉ trong synthetic runtime do harness sở hữu.
- [ ] Commit phạm vi A với test + cấu hình. Không stage bằng `git add .` khi có file ngoài phạm vi.

**Đạt A:** graph regression và image build/resource-read cùng đạt, không dựa Compose config đơn thuần. Nếu wheel tồn tại nhưng loader không đọc được thì chưa đạt.

## 4. Nhiệm vụ B — Dependency thuộc đúng worktree, dừng sớm khi sai

**Modify:** `scripts/prepare-figma-e2e.ps1`, `scripts/run-runtime-verification.ps1`, `docs/runbooks/agent-environment.md`.
**Tests:** `backend/test/config/test_figma_e2e_harness.py`, `backend/test/config/test_runtime_evidence.py`.
**Không sửa:** phiên bản package/lockfile, launcher OTP hoặc config chọn project OTP; không thay cách dev của mọi worktree cũ.

**Giao diện chốt:** thêm một switch `-CheckFrontendOnly` vào launcher hiện có. Switch này chỉ đọc frontend dependency, không gọi Docker, không reservation, realm, migration, npm install hay cleanup. Kết hợp nó với `-CheckConfigurationOnly` hoặc `-Run` phải bị từ chối rõ trước side effect. `-CheckConfigurationOnly` tiếp tục chỉ chứng minh Compose; không bị buộc có node_modules và không được đổi nhãn thành runtime/dependency PASS. Normal startup kể cả legacy project chạy cùng validator trước reservation/startup. Runtime runner gọi `-CheckFrontendOnly` trước khi vào khối try/finally có cleanup; prerequisite thất bại không được rơi vào `down --volumes`.

**Implementation seam:** một function validator trong launcher, gọi Node standard library bằng `node -e`/stdin để đọc JSON/resolve/realpath; không require thực thi mã gói ứng dụng. Không thêm JS script, framework hay runtime TypeScript. PowerShell gọi validator trực tiếp khi normal startup và khi switch chỉ đọc; runtime runner gọi switch để tái sử dụng, không chép validator lần hai.

**Mã kết quả dự kiến:** `FIGMA_FRONTEND_OK`; lỗi bắt đầu `FIGMA_FRONTEND_UNAVAILABLE`, `FIGMA_FRONTEND_OWNERSHIP_REJECTED`, `FIGMA_FRONTEND_LOCK_MISMATCH` hoặc `FIGMA_FRONTEND_METADATA_INVALID`, giữ phần chẩn đoán ngắn. Không in environment, token hoặc username-local lên PR. Mã lỗi mới được ghi runbook; không sửa mã ownership/cleanup đang có.

**Logic bắt buộc:**

```text
frontend = canonical realpath(<repository>/frontend)
read package.json + package-lock.json as JSON
resolve node_modules root, @playwright/test package and CLI from frontend
resolve playwright from @playwright/test; resolve playwright-core from playwright
for each resolved path:
    require physical containment inside owned frontend (separator-aware, correct OS casing)
    locate correct lockfile node for the resolved package path
    require installed name/version and parent dependency resolution agree with that lock node
require CLI belongs to the selected @playwright/test installation
return summary only; never install/repair automatically
```

Không so `package.json` range `^1.63.0` với version bằng phép bằng chuỗi. Không ép package tree luôn phẳng/cùng version; so node thực sự resolve với lockfile tương ứng. Metadata hidden installed lock không thay thế lockfile của checkout. Ba version khớp chưa chứng minh toàn cây hoặc Chromium sẵn sàng. Trước browser test, chạy collection `--list` và launch browser bằng test phù hợp; browser thiếu là prerequisite riêng.

- [ ] Viết regression bằng cây metadata tổng hợp trong temp: hợp lệ; thiếu Node; thiếu package/lock; JSON lỗi; direct mismatch; nested mismatch; CLI khác cây; path có khoảng trắng; đường dẫn cùng prefix nhưng là thư mục anh em; junction/symlink ra ngoài dù cùng version; link nội bộ hợp lệ. Kiểm tra Unix trên CI và Windows trên shell hỗ trợ, theo fixture hiện có; không đổi bộ cài thật thành lỗi.
- [ ] Test từ chối chứng minh fake Docker không nhận startup/down, không tạo reservation hoặc thay realm. Test `-CheckFrontendOnly` không gọi Docker kể cả thành công. Test config-only không đòi dependency và marker cũ không đổi. Test startup-failure/owned cleanup/concurrency trước đây vẫn chạy.
- [ ] Sửa validator, tích hợp runner trước cleanup-capable try; giữ semantics `-CheckConfigurationOnly`. Nếu validator làm test giả lập cũ thiếu metadata thì bổ sung metadata tối thiểu trong fixture, không tắt guard production và không xóa assertion an toàn.
- [ ] Cài dependency chỉ trong worktree nhiệm vụ đã được duyệt bằng `npm ci`; không xóa junction cũ. Kiểm tra realpath trước và sau, lockfile diff phải rỗng. Dùng chung cache tải được phép, không shared mutable installation.
- [ ] Ghi vào runbook: chạy CheckFrontendOnly trước lệnh Playwright trực tiếp; lệnh đó là tiền kiểm, không chứng minh runtime. Không quảng cáo guard bảo vệ mọi lệnh npm bên ngoài harness.
- [ ] Chạy collection test đã chọn bằng local CLI đúng worktree, không `npx` có thể tải package thiếu ngầm. Xác minh revision Chromium qua lần launch test thực, không chỉ kiểm tra tồn tại executable.
- [ ] Chạy regressions mới/cũ và commit B. Hợp đồng OTP fixed project/suffixed refusal giữ nguyên bằng test/config inspection; không cần chạy OTP thật.

**Đạt B:** dependency đúng được chạy; cây sai/ngoài worktree dừng trước startup/cleanup; đường chạy cũ hợp lệ vẫn dùng được; thiếu công cụ không bị gán lỗi sản phẩm hoặc tự sửa shared tree.

## 5. Nhiệm vụ C — Vá đúng lỗ hổng test UI

**Modify/Test:** `frontend/tests/e2e/figma-ui-interactions.spec.ts`, `frontend/tests/ui-primitives.test.tsx`; `frontend/tests/dialog-menu.test.tsx` chỉ khi assertion keyboard/reopen cần đặt ở chủ sở hữu này.
**Production files:** chỉ sửa control/CSS hiện có nếu test mới tái hiện một lỗi thật trong phạm vi #212; không sửa giao diện vì sở thích. Nguồn thiết kế: `docs/design/knora-visual-tokens.md` và spec/plan đã duyệt của #212 được liên kết từ PR #227.

**Matrix hữu hạn, không toàn bộ tích Descartes:**

| Ca cần chứng minh | Điều kiện | Điều kiện đạt |
| --- | --- | --- |
| Control drawer/sheet/menu bị bỏ sót | Mở đúng surface, 320×568 và 390×844; bổ sung 768×1024 nếu đổi layout | Control bắt buộc visible; control độc lập thuộc hợp đồng touch đo width và height ≥44px, tolerance hiện có; không đo state ẩn |
| Close với tiêu đề dài | 320×568, dialog hiện có, title dài đại diện nội dung thực | Close không bị co, đạt hợp đồng 44×44; không bị title che/chồng; không overflow ngang toàn trang |
| User thường và Operator | 1024×768, xác nhận `matchMedia('(pointer: coarse)').matches`; fixture đúng vai trò | User controls thuộc hợp đồng ≥44×44; chỉ hai control Operator được thiết kế cho phép giữ hợp đồng 26px theo nguồn đã duyệt; không tự áp ngoại lệ lên nơi khác |
| Không bỏ qua nhánh quan trọng | Fixture/breakpoint có control bắt buộc | `expect(...).toBeVisible()` trước đo; không dùng `if(isVisible())` để âm thầm bỏ assertion. Nếu có control thay thế hợp lệ, assert nhánh thay thế đúng |
| Enabled/disabled có hành vi | Nút liên quan trong upload/composer/Button hiện có | Disabled không gọi callback riêng qua click/keyboard; khi đủ đầu vào thì enabled và thao tác được. Không kiểm tra callback không gắn với nút đang xét |

Operator 26px không mặc định là width lẫn height: đọc đúng hợp đồng control hiện có; giữ exception đã duyệt, không sáng tạo tiêu chuẩn mới. Nếu tài liệu thẩm quyền mâu thuẫn thật thì nêu chính xác xung đột, không ép test theo giả định.

- [ ] Lập bảng rất ngắn trong PR: lỗi retro → test cũ nào đã bao phủ → assertion thiếu → test bổ sung. Ca đã bao phủ đủ thì giữ và chạy lại, không thêm test trùng.
- [ ] Bổ sung assertion/test trước sửa UI, chạy chứng minh assertion mới hoạt động; nếu mã hiện tại đã đạt thì ghi rõ test bảo vệ khoảng trống, không bịa red-green của product bug.
- [ ] Dùng helper animation settle/double RAF và tolerance đang có. Đo cả width/height khi đúng hợp đồng, overlap rectangle ở cặp control/title bị tác động. Không thêm sleep dài, force click để vượt visibility hay tăng retry.
- [ ] Với coarse pointer, xác minh media query thực ở browser; không suy từ `hasTouch` hoặc tên test. Kiểm tra cả user và Operator cùng điều kiện.
- [ ] Chạy owning Vitest, typecheck/lint/format và fixture Playwright đã chọn; lưu counts/exit/JUnit. Chụp ảnh có chủ đích đã mask ở các viewport liên quan, không bật trace/video/raw auth screenshot.
- [ ] Nếu test phát hiện lỗi hiện hữu cùng phạm vi thì sửa component/CSS nhỏ nhất và chạy lại. Nếu lỗ hổng chỉ là test, giữ production code nguyên vẹn. Không thêm animation/reduced-motion matrix mới trừ khi code vừa sửa thực sự chạm hành vi đó.
- [ ] Commit C và ghi rõ fixture PASS không chứng minh backend/auth/application đã chạy. Không nhận đã thử cảm ứng vật lý; emulation là kết luận riêng.

**Đạt C:** từng lỗi thực trong retro có test/đối chiếu cụ thể, control ở trạng thái mở và exception đúng; không cần mọi control×viewport×pointer, không tạo suite song song.

## 6. Nhiệm vụ D — Đầu ra công cụ vừa đủ, không mất nội dung cần review

**Modify:** `<USER_HOME>/.codex/AGENTS.md` đúng một mục ngắn về sử dụng công cụ; `docs/agents/issue-tracker.md` sửa ví dụ đọc Issue/lịch sử. Chỉ bổ sung `ci.md`/Agent environment nếu thiếu liên kết đến cơ chế report đang có, không chép lại toàn lệnh.

**Nội dung chung chốt để thêm hoặc hợp nhất nếu đã có:**

> Trước khi lấy dữ liệu lớn, xác định đối tượng và trường cần đọc; lấy trạng thái/SHA/tên file hoặc số lượng trước, rồi đọc patch, bình luận hay log liên quan theo phần. Với tác vụ review, phải đọc đủ phạm vi cần đánh giá; không dùng việc giới hạn đầu ra để bỏ qua bằng chứng.
>
> Nếu công cụ báo đầu ra bị cắt, coi phần đó là chưa đọc đủ: thu hẹp truy vấn hoặc chia đoạn trước khi kết luận. Giữ report cần thiết theo quy trình dự án, loại dữ liệu nhạy cảm trước khi lưu/công bố; không in toàn environment, command line tiến trình hoặc log xác thực để chẩn đoán mặc định.

Ví dụ command pattern được phép điều chỉnh quoting theo shell nhưng không đổi mục đích:

```powershell
gh pr view $pr --repo NhiBuaa/knora-agent --json number,state,headRefOid,baseRefName,url
gh pr checks $pr --repo NhiBuaa/knora-agent --required
git -C $target diff --name-status $base HEAD
# Sau đó lấy patch đúng file và log đúng job lỗi; không mở tất cả comment bot mặc định.
```

- [ ] Trước sửa global, lưu backup vào thư mục evidence local mới và hash đầu vào; đọc lại ngay trước apply patch để giữ thay đổi đồng thời. Nếu có delta không chồng phần sửa thì hợp nhất giữ nguyên; chồng policy đang được phiên khác sửa thì dừng riêng hạng mục đó, tiếp tục việc repo độc lập.
- [ ] Thêm/hợp nhất hai đoạn trên đúng nghĩa, giữ toàn bộ quyền và chính sách khác. Không thêm lệnh Knora vào global. Lưu diff trước/sau đã ẩn danh, hash và đường dẫn backup local; không post toàn AGENTS cá nhân lên PR.
- [ ] Trong issue-tracker, thay ví dụ lấy mọi comments mặc định bằng tóm tắt/metadata trước, lấy đúng comment/page lịch sử khi cần phê duyệt/quyết định. Đọc đúng API/CLI hiện có trước khi viết command; không tạo lệnh/field giả.
- [ ] Kiểm tra output test dài đi theo JUnit/selection manifest và mã thoát hiện có. Không giảm số test chỉ để log nhỏ hơn. Không thêm wrapper/hook/tool mới.

**Đạt D:** hướng dẫn được lưu đúng nguồn, không trùng toàn đoạn ở repo/global; trial §8 chứng minh truy vấn đúng mà không mất phần cần đọc. Không tuyên bố tiết kiệm token theo phần trăm khi chưa có baseline hợp lệ.

## 7. Nhiệm vụ E — Tinh gọn routing, giữ nguyên ranh giới

**Modify:** repo `AGENTS.md`, `docs/runbooks/ci.md` chỉ để giữ chi tiết formatting nguồn sở hữu; `<USER_HOME>/.codex/AGENTS.md` chỉ thay đổi D và khử lặp nguyên văn ngay trong phần bị tác động nếu an toàn. Không viết lại global toàn file.
**Read-only:** `<USER_HOME>/.gemini/GEMINI.md`, hiện tham chiếu nguồn chung thay vì sao chép.

- [ ] Lập mapping trong PR cho từng đoạn bỏ/rút: điều kiện kích hoạt → nguồn đích → quy tắc giữ lại. Không cần tài liệu inventory mới.
- [ ] Repo AGENTS giữ yêu cầu format rồi check khi sửa frontend/Python/shared, cấm hand-compress, cấm sửa generated OpenAPI bằng tay và required CI. Lệnh/phạm vi chi tiết ở `docs/runbooks/ci.md#formatting-scope`, scripts package và CI hiện có. Nếu bảng runbook thiếu một yêu cầu đang có thì bổ sung tại đó trước khi rút AGENTS.
- [ ] Hai module seam links chuyển thành conditional pointer rõ: đọc trước khi chạm interface, phụ thuộc hoặc ownership module tương ứng. Giữ các nguồn nền tảng/architecture và an toàn hiện hành; không viện dẫn kế hoạch này để bỏ hướng dẫn chưa sửa.
- [ ] Giữ routing Skill theo catalog, không tạo allowlist. Không xóa authority, quyền dữ liệu, ownership worktree, verification, exact SHA, Issue/PR ownership hoặc lịch sử milestone chỉ để đạt chỉ tiêu số dòng. Không bắt repo phụ thuộc global cá nhân để hoạt động.
- [ ] Kiểm tra Antigravity vẫn tham chiếu nguồn chung; không sao chép global sang GEMINI. Dòng tham chiếu tồn tại chỉ là kiểm tra tệp, không đủ nhận agent đã nạp; thử session mới ở §8.
- [ ] Chạy link/heading check và formatting hiện có; ghi bytes/lines trước/sau, không quy thành mức giảm token hoặc tăng chất lượng khi chưa đo.
- [ ] Commit D/E trong repo; global changes báo riêng với hash/diff local. Không stage cấu hình cá nhân hoặc đường dẫn user-home vào repo.

**Đạt E:** nội dung rút có nguồn đích xác định; không mất nghĩa/ràng buộc; agent mới tìm được nguồn đúng cho tác vụ khác nhau. Nếu chỉ rút chữ mà agent bỏ hướng dẫn bắt buộc thì chưa đạt.

## 8. Kiểm chứng cuối và nghiệm thu bằng chứng

### 8.1 Test phù hợp, không đụng DB có dữ liệu

Chạy theo đúng checkout và runner hiện có. Các lệnh dưới là điểm vào đã xác định; bổ sung regression owning test nếu phạm vi thực đổi. Mỗi lệnh dài dùng log/JUnit/selection/exit theo CI runbook, thư mục mới cho mỗi lần chạy; không dùng report cũ hoặc report dở dang làm PASS.

```powershell
python -m pytest backend/test/config/test_figma_e2e_harness.py backend/test/config/test_runtime_evidence.py -q -p no:cacheprovider --junitxml=$report
npm --prefix frontend run test -- tests/ui-primitives.test.tsx tests/dialog-menu.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run format:shared
npm --prefix frontend run format:shared:check
python -m ruff format .
python -m ruff format --check .
python -m ruff check .
```

`$report` phải được đặt thành đường dẫn JUnit mới trong thư mục evidence thuộc task trước lệnh pytest; `$target/$base/$pr` lấy từ bằng chứng nhận việc, không chạy placeholder literal. Nếu formatter repo-wide chạm file ngoài phạm vi thì xem diff và không stage phần không liên quan; không chạy formatter tại main. Chọn additional backend/windows suite bằng partition hiện có khi cần; không gọi bare full pytest không xác minh targets. Test cache dùng `-p no:cacheprovider` hoặc cache riêng cho mọi trial dùng chung checkout; không chia sẻ test-state giữa agent sessions.

Fixture browser dùng local CLI:

```powershell
# Trong frontend worktree; chỉ biến môi trường của process con, khôi phục trong finally.
$env:FIGMA_TEST_MODE = 'fixture'
node node_modules/@playwright/test/cli.js test --config=playwright.figma.config.ts figma-ui-interactions.spec.ts --grep 'independent controls meet minimum|touch|coarse' --list
```

Đọc tên ca thực sau thay đổi và chọn grep chính xác bao gồm mọi ca mới; `--list` chỉ chứng minh collection. Sau đó chạy cùng selector không có `--list`, thêm reporter JUnit/outputDir mới qua cơ chế harness. Nếu cần grep broader để bao ca renamed thì xác nhận selected count và danh sách ca trước chạy; không tính 0 tests/skipped là PASS. Không dùng broad glob application/evidence historical tests. Port 3300 có chủ khác thì không kill, có thể tiếp tục hosted/CI và báo local browser pending.

### 8.2 Runtime thật trên SHA cuối

- [ ] Sửa và commit hoàn tất trước runtime nghiệm thu; ghi full head SHA, dirty status, node/npm/Playwright versions và image IDs theo evidence runner. Nếu chạy dirty local thì chỉ là evidence local đúng diff, không thay bằng SHA commit sạch.
- [ ] Ưu tiên dispatch `.github/workflows/runtime-verification.yml` với `profile=application`, `subject_sha=<full-final-head>`; workflow source ref phải chứa thay đổi và hỗ trợ input hiện hành. Ghi riêng workflow SHA, subject SHA, checkout SHA. Không dùng workflow source main cũ rồi giả là runner code mới.
- [ ] Workflow có sẵn chạy identity, documents, conversations, workspace và operator; build backend và migration synthetic thuộc workflow. Không tự chọn bỏ journeys để gắn nhãn full application PASS. Đọc JUnit, evidence JSON và validator hiện có; workflow xanh thiếu artifact hoặc thiếu expected cases chưa đạt.
- [ ] Kiểm tra cleanup bằng chứng đúng project và tài nguyên được sở hữu. GitHub runner hết vòng đời không tự chứng minh mọi assertion cleanup trong test đã chạy; đọc kết quả. Local smoke nếu được chọn chỉ dùng disposable suffix `-Run`, verify resource IDs trước/sau; không động legacy project của người khác.
- [ ] Chạy lại sau sửa có căn cứ trong phạm vi, không xin duyệt từng lượt. Nếu cùng lỗi lặp hai lần mà chưa có thay đổi hoặc bằng chứng mới, ngừng dispatch mù và phân tích log/ca tái hiện trước; đây không phải điều kiện tự trả việc cho người dùng. Chỉ dừng theo §9 khi cần quyền mới hoặc không còn cách xử lý an toàn trong phạm vi. Không tăng retry hoặc timeout workflow.
- [ ] Mọi thay đổi code sau runtime: chạy lại checks chịu tác động và lấy runtime đúng SHA cuối nếu thay đổi ảnh hưởng build/launch/UI; nếu chỉ prose/link thì ghi rõ runtime ở code-equivalent SHA và delta tài liệu, không gọi đó là runtime exact-final-SHA. Gói này yêu cầu runtime exact-final-SHA để đề nghị nghiệm thu: chốt mọi sửa đổi rồi dispatch lần cuối, hoặc báo thiếu nếu có blocker §9.

### 8.3 Phiên mới, không có lịch sử triển khai

Tạo session mới thực sự trong Antigravity hoặc agent phụ mới không kế thừa lịch sử nếu công cụ hiện có hỗ trợ. Không xóa history rồi gọi cùng phiên là fresh. Codex và Antigravity được kiểm tra riêng nếu có sẵn khả năng tạo phiên trong quyền được duyệt; không cài CLI/app mới, không sửa quyền hoặc giả lập tool. Nếu không tự tạo được một loại phiên, ghi đúng giới hạn và đưa prompt kiểm tra một lần, không tuyên bố đã đạt loại đó.

Chỉ cung cấp repo/worktree, task dưới và yêu cầu chỉ đọc; không cung cấp đáp án hoặc đường dẫn tài liệu cần tìm ngoài AGENTS mặc định. Không bỏ Skill/rule bắt buộc để tạo baseline. Trial không chạy full test/DB/npm install/formatter.

| Trial | Đầu bài cho agent mới | Bằng chứng đạt do người triển khai đối chiếu độc lập |
| --- | --- | --- |
| T1: frontend có test thật | Đánh giá một regression hiện có về control UI; tự chọn test nhỏ và chạy, không sửa product code | Tự tìm AGENTS/CI, chọn owning Vitest test, chạy và đọc exit/counts; phân biệt unit với browser runtime |
| T2: đọc PR/tool output | Review trạng thái PR vừa tạo, current head/required CI và patch liên quan; không sửa/publish | Lấy đúng head/CI; metadata trước rồi targeted patch/job; đọc đủ diff nhiệm vụ; không output bị cắt mà bỏ qua; secrets/user paths không lọt bằng chứng công khai |
| T3: routing và giới hạn | Chỉ đọc: một sửa tài liệu nhỏ cần hướng dẫn nào; một thay đổi module boundary cần nguồn nào; chưa chạy browser thì kết luận được gì | Dẫn đúng conditional sources; không đọc mọi seams vô điều kiện cho docs-only; không bỏ architecture khi boundary changed; không tự nhận runtime/AI/merge |

Agent trial không được sửa worktree shared; dùng pytest cache riêng/disabled và Vitest run không watch. Thu log tool calls, test report và kết luận; người triển khai đối chiếu với nguồn thật, không chỉ chấm lời tự đánh giá. Chỉ kiểm tra đúng ba việc trên, không biến thành Skill Eval mới. Trial xác nhận instruction discovery/report honesty, không chứng minh đầy đủ vòng sửa bug nếu không có sửa product code.

**Quyết định từng trial:** PASS khi có bằng chứng đủ; FAIL khi agent làm sai; BLOCKED/UNVERIFIED nếu thiếu phiên/công cụ/quyền. Không tính thiếu công cụ là Skill FAIL và không đổi UNVERIFIED thành PASS. Nếu routing thất bại, sửa pointer trong phạm vi rồi thử lại phiên mới; không thêm Skill/framework để đạt.

### 8.4 PR và trạng thái kết thúc

- [ ] PR body theo template: scope/AC của năm mục, test thực chạy với số lượng/mã thoát, image build/resource proof, runtime workflow artifact đúng SHA, trial logs đã loại secrets, global diff/hash tách khỏi repo diff, rủi ro và phần chưa thử.
- [ ] Review trước đề nghị nghiệm thu: dùng reviewer độc lập/phiên mới nếu công cụ sẵn có, chỉ đọc diff/source/test evidence đúng head; người triển khai tự sửa finding hợp lệ và xác minh lại. Không coi self-review hoặc bot không phản hồi là đã có review độc lập. Nếu không có reviewer khả dụng, ghi rõ review độc lập còn chờ; CI/runtime không được dùng thay. Không tự nhắn một session người dùng đang dùng mà chưa được giao quyền điều phối session đó.
- [ ] Đối chiếu full required CI với `headRefOid` cuối và `ci-subject` artifact; `CI required` của đúng PR phải success, các job bắt buộc không missing/cancelled/skipped. Không chỉ đọc một job xanh. Đọc findings của bot/người review có liên quan, sửa trong phạm vi và phản hồi bằng chứng; resolve chỉ khi thực sự xử lý.
- [ ] Kiểm tra diff cuối: không file ngoài phạm vi, không lockfile drift, không secret/user-local paths, không evidence lịch sử bị sửa, main/untracked/stack khác giữ nguyên.
- [ ] Báo riêng: đã sửa; local tests; CI; runtime; trial hướng dẫn; review thực tế; nghiệm thu của người dùng; merge/deploy. Trạng thái cuối tối đa là đủ bằng chứng đề nghị nghiệm thu/merge, không tự Accepted hay Merged.

## 9. Điều kiện dừng — hỏi đúng một lần cho đúng phần thiếu

Tiếp tục mọi phần độc lập còn được phép. Không gửi câu hỏi chỉ vì xong một task, cần commit, chạy lệnh thường lệ hoặc gặp lỗi code có thể sửa trong phạm vi.

Chỉ dừng phần phụ thuộc khi:

1. Chưa có phê duyệt V1/quyền nguồn thực thi; chỉ đọc và yêu cầu duyệt cả gói một lần.
2. Không xác định được ownership worktree/global hunk/stack, có người khác dùng port hoặc tài nguyên cần tác động; không chiếm quyền. Local runtime bận thì ưu tiên hosted, không hỏi dừng app nếu hosted đủ.
3. Thiếu công cụ nền, quyền GitHub, quota tính phí mới hoặc không có cách tạo fresh session cần thiết. Báo đúng bằng chứng; tiếp tục checks khác, không cài tool hay giả kết quả.
4. Muốn thay kiến trúc, packaging authority/loader, dependency version, UI identity, dữ liệu thật, OTP/deploy hoặc ranh giới quyền ngoài kế hoạch.
5. Có xung đột thiết kế/nghiệm thu thật không thể giải bằng nguồn hiện hành; nêu file/đoạn mâu thuẫn và lựa chọn cần người dùng quyết định, không hỏi câu chung chung.
6. Cleanup không chứng minh quyền sở hữu hoặc thất bại; giữ bằng chứng và reservation bảo vệ, không tự down/prune/xóa lock để sạch giả.
7. Runtime/CI không thể tiếp tục vì quota/quyền/hạ tầng ngoài phạm vi, hoặc đã điều tra mà phương án sửa đòi vượt ranh giới được duyệt. Một lần test fail, timeout hay cần chạy lại sau sửa không tự nó là lý do xin duyệt. Báo nguyên nhân, lệnh/run và phần còn thiếu; không báo hoàn thành cả gói khi còn mục bắt buộc thiếu bằng chứng.

Khi dừng, dùng một báo cáo gộp: phần đã đạt, blocker, phần vẫn đang tiếp tục, đúng quyền/quyết định cần bổ sung và lệnh dự kiến. Không biến mọi lỗi kỹ thuật thành xin duyệt.

## 10. Danh sách nghiệm thu năm vấn đề

| Mục | Bằng chứng bắt buộc trước đề nghị nghiệm thu |
| --- | --- |
| A Docker | Bốn build callers thống nhất; context không chứa đầu vào ngoài allowlist; image build và đọc đủ resources/loader; entrypoint/migration synthetic hoạt động |
| B Dependency | Regression đúng/sai/path/link/nested/CLI; không side effect khi refusal; bộ cài thuộc worktree, collection và browser launch thực; config-only/cleanup/concurrency/OTP contract cũ không regression |
| C UI | Mapping từng lỗi và assertion; width/height/state/pointer/Operator/long-title theo phạm vi; unit+fixture thực chạy, ảnh render đã mask; application profile riêng |
| D Output | Quy tắc global và ví dụ repo sửa đúng; trial tool calls lấy đúng/đủ, không truncation bị bỏ qua, không công bố dữ liệu nhạy cảm |
| E Routing | Diff nghĩa trước/sau, links/format check; không mất safety/authority; fresh-session discovery Codex/Anti được ghi đúng PASS hoặc chưa kiểm chứng riêng |
| Toàn gói | Full required CI và runtime application đúng subject cuối; không tự merge; report phân biệt code/test/runtime/review/acceptance; mọi giới hạn còn lại nêu rõ |

Không gán hoàn tất toàn gói nếu A/B/C hoặc trial bắt buộc D/E còn thiếu bằng chứng; có thể PR implementation-ready nhưng acceptance-pending. Thiếu trial của một ứng dụng là giới hạn công cụ, không tự coi ứng dụng đó đạt. Không có yêu cầu thử thiết bị cảm ứng vật lý, AI quality, OTP runtime hay đo lợi ích token trong gói này.

## 11. Skills gợi ý cho phiên tiếp nhận

Theo catalog thực tế: `executing-plans`, `using-git-worktrees`, `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `writing-for-agents`, `requesting-code-review`, `pr` khi viết PR. UI chỉ dùng Skill thiết kế/review đúng phần bị tác động, không nạp toàn bộ UI Skills và không đổi bản sắc. Thiếu Skill thì giữ contract repo và báo giới hạn, không tự cài.

## 12. Prompt bàn giao

Người dùng gửi đoạn sau cùng SHA256 của chính file này sau khi duyệt. Đây là mẫu phê duyệt để gửi, không phải tuyên bố đã có phê duyệt trên GitHub:

> Tôi duyệt toàn bộ V1 tại `<USER_HOME>\AppData\Local\Temp\verification-environment-remediation-plan-handoff-20261024.md`, đúng SHA256 tôi gửi kèm. Hãy đọc, xác minh hash rồi tự triển khai đủ năm mục đến khi có bằng chứng nghiệm thu theo kế hoạch. Tôi cho phép các thao tác trong gói quyền §1, gồm cài dependency/Chromium đã khóa trong worktree mới, chạy CI/runtime hiện có, cập nhật global AGENTS đúng phạm vi, commit/push và tạo PR. Tự sửa và kiểm chứng các bước thường lệ; chỉ hỏi khi chạm §9, gộp mọi blocker cần tôi xử lý. Không sửa tài nguyên của phiên khác, không nới CI, không dùng provider trả phí và không tự merge. Cuối cùng báo từng mục đạt tới đâu, bằng chứng đúng SHA, giới hạn còn lại và PR có đủ điều kiện đề nghị nghiệm thu hay chưa.


---

# Phụ lục V2 — Kế hoạch xử lý kết quả review môi trường kiểm chứng (PR #233)

> **Phê duyệt V2:** Được người dùng duyệt tại hội thoại ngày 2026-10-24 từ tệp bàn giao:
> `verification-environment-review-remediation-plan-20261024.md`
> **SHA-256 đã xác minh:** `FDC96841E9C817490B695531B0D99368052629786FD490E8E8B97028A907D7CB`
> **Phạm vi triển khai:** Anti thực hiện sửa mã và kiểm chứng; Codex review độc lập. Tiếp tục trên PR #233, nhánh `fix/verification-environment-reliability`.

## 1. Tóm tắt các nhiệm vụ bổ sung V2
- **F-A (Docker Packaging & Exact Allowlist):**
  - Chuyển `backend/Dockerfile.dockerignore` từ negation thư mục sang danh sách phủ định tệp chính xác (exact-file allowlist), bắt đầu bằng `**`.
  - Liệt kê đủ 177 tệp tracked trong `backend/src`, 53 tệp trong `backend/migrations`, `pyproject.toml`, `alembic.ini`, và 16 tệp force-include resources từ `evals/` và `docs/`.
  - Bổ sung test cấu trúc và probe Docker BuildKit thật kiểm chứng không có sentinel lọt vào context.
- **F-B1 & F-B2 (Physical Containment & Lockfile Node Matching):**
  - Cập nhật helper `isPhysicallyWithin(rootPath, candidatePath)` dùng `fs.realpathSync`, `path.relative`, không hạ chữ thường vô điều kiện để bảo vệ ranh giới case-sensitive trên Linux.
  - Neo `frontend` vào `repository` trước khi kiểm tra các phụ thuộc bên trong.
  - Đối chiếu khai báo root `@playwright/test` giữa `package.json` và `package-lock.json['']`.
  - Duyệt chuỗi resolve (`@playwright/test` -> `playwright` -> `playwright-core`) bằng `createRequire`, so khớp tên package, version với lock node tương ứng và kiểm tra parent dependency spec.
  - Xử lý các link nội bộ và xác nhận CLI nằm trong package `@playwright/test` được chọn.
  - Bổ sung ma trận test synthetic cho các trường hợp: flat, nested, internal link, name mismatch, version mismatch, parent spec mismatch, external junction/symlink.
- **F-C (Củng cố Touch Targets & Quản lý Ảnh kiểm thử):**
  - Đo cả width và height ≥ 44px (với dung sai subpixel) cho panel tools, Appearance/Logout menuitems, review link, dialog buttons, và collapse rail button.
  - Giữ nguyên hợp đồng chiều cao 26px cho điều khiển Operator (`Workspace actions`, `Workspace selector`).
  - Dùng `testInfo.outputPath(...)` với tiền tố `verification-touch-target-` cho các ảnh chụp màn hình kiểm chứng theo từng lần chạy.
  - Cập nhật `.github/workflows/ci.yml` tại step `Upload frontend reports` để upload thêm ảnh đã mask của ca C.
  - Chạy mutation proof tạm thời kiểm chứng assertion width bắt được hồi quy.
- **G-A (Kiểm thử hồi quy cho Runtime Runner):**
  - Thêm tests trong `backend/test/config/test_runtime_evidence.py` xác nhận:
    - Resource check thành công: gọi đúng thứ tự, marker `RUNTIME_PACKAGE_RESOURCES_OK=16`.
    - Resource check thất bại (docker exec nonzero): runner exit khác 0, không tạo evidence, nhưng khối finally cleanup/rollback vẫn được gọi đầy đủ.
    - Thiếu source resource / pyproject rỗng: throw mã lỗi tương ứng.
    - Profile `otp`: không gọi resource checker của application.
- **G-D & G-E (Bằng chứng Phiên mới & Khảo sát Hash):**
  - Ghi nhận thuật toán đo hash global AGENTS (LF-normalized vs raw bytes) và diff đã ẩn danh.
  - Chạy 6 trials phiên mới (T1-T3) độc lập cho Codex và Anti không kế thừa lịch sử chat.

## 2. Bằng chứng kỹ thuật chi tiết theo các mục đã hoàn tất

### A. Docker Exact Allowlist & Runtime Checker (F-A & G-A)
- **F-A:** `backend/Dockerfile.dockerignore` chuyển đổi sang exact-file allowlist bắt đầu bằng `**`. Đã phủ định đúng 177 tệp tracked trong `backend/src`, 53 tệp trong `backend/migrations`, `pyproject.toml`, `alembic.ini`, và 16 tệp force-include resources từ `evals/` và `docs/`.
  - Kiểm chứng: BuildKit probe trên context tổng hợp chứng minh 100% tệp ngoài luồng (sentinels trong `evals/datasets` và `docs/runbooks`) bị loại trừ khỏi Docker build context.
- **G-A:** Đã bổ sung 4 runner regressions trong `backend/test/config/test_runtime_evidence.py`:
  - `test_runtime_package_resources_check_success`: Exec marker 16 được gọi sau identity và trước Playwright, sinh `evidence.json`.
  - `test_runtime_package_resources_check_failure_triggers_cleanup`: Khi exec trả mã khác 0, runner exit khác 0, không sinh `evidence.json`, và khối `finally` cleanup `compose down --volumes` được kích hoạt đầy đủ.
  - `test_runtime_package_resources_missing_sources_or_empty_pyproject`: Bắt đúng mã lỗi `FORCE_INCLUDE_SOURCE_MISSING` và `RUNTIME_PACKAGE_RESOURCES_NONE`.
  - `test_runtime_otp_profile_excludes_package_resources_and_figma_api`: Xác nhận profile OTP không gọi resource check của application và không phụ thuộc `figma-api`.
  - Tương thích Windows PowerShell 5.1: Đã sửa `run-runtime-verification.ps1` dùng `[Security.Cryptography.SHA256]::Create()` và `[Security.Cryptography.RandomNumberGenerator]::Create()` thay thế cho các API chỉ có trên .NET Core.

### B. Ranh giới vật lý & Đối chiếu Lockfile Node (F-B1 & F-B2)
- **F-B1:** Nâng cấp helper `isPhysicallyWithin(rootPath, candidatePath)` sử dụng `fs.realpathSync`, `path.relative`, không hạ chữ thường vô điều kiện, bảo vệ trọn vẹn ranh giới case-sensitive trên Linux. Neo `frontend` vào `repository` trước khi kiểm tra con.
- **F-B2:** Đối chiếu `package.json['devDependencies']['@playwright/test']` với `lock.packages['']['devDependencies']['@playwright/test']`. Duyệt resolution chain (`@playwright/test` -> `playwright` -> `playwright-core`) bằng `createRequire`, so khớp tên package, version, và parent dependency specs. Hỗ trợ symlink/link nội bộ (`link: true`).
  - Kiểm chứng: 15/15 tests trong `test_figma_e2e_harness.py` PASSED, bao gồm các ca từ chối external junction, name mismatch, version mismatch, parent spec mismatch, và chấp nhận nested / internal package link hợp lệ.

### C. Kích thước Touch Targets & Quản lý Ảnh kiểm thử (F-C)
- Đo cả **width và height** ≥ 44px (kèm `SUBPIXEL_TOLERANCE`) cho toàn bộ controls độc lập:
  - Panel tools (`.conversation-panel-tools button`),
  - Menuitem Appearance và Log out,
  - Liên kết Review indexed documents (`.kn-turn-action`),
  - Các nút Choose file, Cancel, Upload document trong Dialog,
  - Nút Collapse rail trên coarse pointer.
  - Giữ nguyên hợp đồng chiều cao 26px cho điều khiển Operator (`Workspace actions`, `Workspace selector`).
- Ảnh kiểm thử: Chuyển toàn bộ sang `testInfo.outputPath('verification-touch-target-*.png')` riêng cho từng lần chạy:
  - `verification-touch-target-320x568.png`
  - `verification-touch-target-390x844.png`
  - `verification-touch-target-768x1024.png`
  - `verification-touch-target-close-long-title-320.png`
  - `verification-touch-target-coarse-pointer-user-1024x768.png`
  - `verification-touch-target-coarse-pointer-operator-1024x768.png`
- Bước upload artifact CI: Cập nhật `.github/workflows/ci.yml` tại `Upload frontend reports` thêm đường dẫn `frontend/test-results/figma-ui/**/verification-touch-target-*.png`.
- **Mutation Proof:** Đã thực hiện kiểm chứng đột biến tạm thời (width: 20px trên `.conversation-panel-tools button`), kết quả test Playwright thất bại chính xác tại assertion chiều rộng: `Error: Panel tool 0 at 320px width (20px) should meet minimum 44px touch target (Expected: >= 44, Received: 20.05)`. Sau đó khôi phục lại mã nguồn nguyên bản.

### D & E. Bằng chứng Phân biệt Hash LF vs Raw Bytes & 6 Fresh Session Trials
- **Phân biệt Hash Global AGENTS.md:**
  - Khảo sát thực tế giữa môi trường Linux (LF) và Windows (CRLF):
    - `BEFORE_SHA256` (bản gốc): LF-normalized = `51ad7806db7d3b6ca3cef157f2778ac4e8aeb59cadf4a219dee878e2c2c71506`; Raw Windows bytes (CRLF) = `057588d0b73033addecec2848f895bbd3c35fb87ba4cbcbbaea49e0ba23ac2c1`.
    - `AFTER_SHA256` (sau sửa V1): LF-normalized = `c416518c7788228de3846e41b14ad54c09e5821632d351f10f6516ab75e3dbee`; Raw Windows bytes (CRLF) = `a520d7ae411030fdb9145c9301570d3d896e1cdbcaef1290946cfd6bf9ca8c0e`.
  - Giá trị ghi nhận trong V1 metadata là hash đã chuẩn hóa ký tự xuống dòng (`\r\n` -> `\n`), bảo đảm tính xác thực độc lập nền tảng.
  - Diff đã ẩn danh (`<USER_HOME>` thay cho đường dẫn tài khoản cá nhân) được lưu tại `.verification/evidence/global-backup/anonymized_global_agents.diff`.
- **Ma trận 6 Fresh Session Trials:**
  - T1: UI Regression Evaluation (Chỉ đọc, chạy test owning Vitest `ui-primitives.test.tsx` và `dialog-menu.test.tsx`).
  - T2: PR Review #233 (Chỉ đọc, kiểm tra CI subject, diff nhiệm vụ, báo cáo rủi ro không rò rỉ secret/đường dẫn cá nhân).
  - T3: Documentation & Module Boundary Routing (Chỉ đọc, kiểm tra quy tắc nạp tài liệu và ranh giới hệ thống).
