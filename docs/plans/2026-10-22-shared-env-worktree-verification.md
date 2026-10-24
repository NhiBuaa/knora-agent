# Shared Environment & Worktree Verification — Implementation Plan V1

> **For agentic workers:** Dùng Skill `executing-plans` nếu có trong catalog và được phép. Triển khai tuần tự; không tự giao cho các phiên khác hoặc chiếm worktree đang có chủ sở hữu.

**Mục tiêu:** Giữ một file `.env` local tại thư mục Knora chính; mỗi Issue chạy đúng code trong worktree của mình và tham chiếu file đó, không cần merge vào branch test.

**Cách làm:** Tận dụng `-EnvFile` của launcher hiện có. Tách nguồn cấu hình dùng chung khỏi lựa chọn code, quyền chạy AI và đích dữ liệu. Không tạo launcher, Skill, dependency hoặc hệ thống trạng thái mới.

**Công nghệ hiện có:** PowerShell, pytest, Docker Compose, Playwright và GitHub Actions.

**Nguồn yêu cầu/phê duyệt:** Hội thoại hiện tại: người dùng đã thống nhất cách dùng `.env` tại thư mục chính và yêu cầu lập kế hoạch. Đây là bản kế hoạch đề xuất V1; chưa phải phê duyệt triển khai hoặc quyền gọi provider.

## 1. Hiện trạng đã kiểm tra

- `main` trên GitHub tại lúc lập kế hoạch: `36bb3d5042ea764508210b29ab08a9dfd5cf7bdc`.
- Thư mục chính: `C:\Developer\Projects\knora-agent`; nhánh đang mở là `codex/test`, không phải `main`. Đây chỉ là nơi giữ cấu hình, không phải đích sửa code của nhiệm vụ này. Không đổi nhánh để làm cho nó mang tên `main`.
- `C:\Developer\Projects\knora-agent\.env` tồn tại, được Git bỏ qua và không được theo dõi. Chưa đọc hoặc công bố giá trị bên trong.
- `scripts/start-dev.ps1:248-282` đã có `Import-DotEnv` và `-EnvFile`; biến môi trường của process được ưu tiên khi đã có giá trị theo điều kiện hiện hành.
- `scripts/start-ollama-demo.ps1` cũng hỗ trợ `-EnvFile`; `docs/runbooks/local-ollama.md` đã mô tả đường chạy này.
- `start-dev.ps1` dùng project Docker cố định `knora-dev`; launcher Ollama mặc định cũng dùng một project cố định riêng. Đổi đường dẫn `.env`, database hay cổng không chứng minh quyền sở hữu hoặc cách ly toàn bộ stack.
- `docs/runbooks/agent-environment.md` đã có smoke trình duyệt bằng môi trường tạm, provider giả lập. Không nạp nguyên `.env` AI vào harness này hoặc đổi nó sang provider thật.
- `-PreflightOnly` của launcher AI có thể gọi endpoint embedding; không phải bước kiểm tra chỉ đọc và không được chạy trước khi có quyền tương ứng.
- Đã dùng CodeGraph nhưng kết quả truy vấn không bao phủ đúng luồng PowerShell; các kết luận về launcher được đối chiếu trực tiếp với source tại SHA nêu trên.

## 2. Giới hạn chung

- Không merge code vào branch test chỉ để lấy cấu hình. Không commit/copy file `.env` thật vào repository, không di chuyển hoặc sửa file dùng chung trong nhiệm vụ này.
- Không tự thay đổi cấu hình cấp user/system hoặc môi trường của session khác. Khởi chạy bằng process con riêng, không dot-source launcher vào shell dùng chung.
- Không tắt cơ chế kiểm tra quyền sở hữu, chiếm cổng, xóa khóa, restart stack hoặc nhận lại volume không rõ chủ sở hữu.
- Không migrate, ghi dữ liệu hoặc chạy cleanup trên database/bucket/realm đang sử dụng. Database/bucket riêng chưa đủ nếu container, realm, logs hoặc worker vẫn xung đột.
- V1 chạy tuần tự các lượt cần cùng tài nguyên; không mở rộng sang nhiều stack đồng thời hoặc thêm khả năng đổi project Docker trong gói này.
- Không cài công cụ, tải model, kích hoạt provider, gọi API có phí hoặc deploy. Một lượt AI thật cần xác định sẵn endpoint/model, dữ liệu được phép gửi, số yêu cầu tối đa, thời gian và chi phí được duyệt. Thiếu quyền thì ghi chưa kiểm chứng, không tự suy ra từ việc có token.
- Giữ evidence tại Issue/PR; loại secrets bằng `[REDACTED]`, ẩn danh đường dẫn user-local khi công bố. Không đăng nguyên `.env`, toàn bộ môi trường process hoặc log chưa rà soát.

## 3. Đích triển khai và các file liên quan

Sau khi kế hoạch được duyệt, kiểm tra lại remote, base, worktrees và quyền sở hữu. Nếu chưa có đích được giao, đề xuất branch `chore/worktree-env-verification`, worktree `C:\Developer\Projects\knora-agent-worktree\chore-worktree-env-verification`, từ `main` mới nhất đã xác minh. Kiểm tra đường dẫn/nhánh chưa được dùng trước khi tạo; không sửa tại checkout chính.

| File hiện có | Vai trò dự kiến |
| --- | --- |
| `docs/runbooks/local-development.md` | Nguồn chính hướng dẫn tham chiếu `.env` từ worktree, thứ tự cấu hình và điều kiện an toàn |
| `docs/runbooks/local-ollama.md` | Liên kết ngắn tới hướng dẫn chung; giữ riêng giới hạn của launcher Ollama |
| `docs/runbooks/agent-environment.md` | Chỉ thêm liên kết/phân biệt smoke giả lập và lượt AI thật nếu còn thiếu |
| `backend/test/adapters/cli/test_dev_launcher.py` | Tái sử dụng kiểm thử dotenv, process con, startup refusal và reservation |
| `backend/test/adapters/cli/test_ollama_launcher.py` | Tái sử dụng fixture HTTP giả, `-EnvFile`, thứ tự ưu tiên và bảo vệ secrets |
| `scripts/start-dev.ps1`, `scripts/start-ollama-demo.ps1` | Chỉ sửa nếu regression chứng minh lỗi thuộc phạm vi; không tạo parser hoặc launcher song song |

Không sửa `AGENTS.md` nếu liên kết runbook hiện tại đã đủ để agent tìm thấy. Nếu cần lưu kế hoạch vào repo, dùng `docs/plans/2026-10-22-shared-env-worktree-verification.md` trên worktree được giao; không tạo thêm bản trạng thái. Ghi SHA và tham chiếu phê duyệt đúng phiên bản trong Issue/PR.

## 4. Các bước thực hiện

### A. Chốt cấu hình và đường chạy thực sự được hỗ trợ

- [x] Đọc `AGENTS.md`, các nguồn bắt buộc của repo, runbook và bản kế hoạch được duyệt; kiểm tra Git tại đúng đích trước khi sửa.
- [x] Kiểm tra `.env` nguồn có thể truy cập nhưng không in nội dung. Chỉ ghi tên biến cần thiết, có/thiếu, và loại cấu hình: AI, xác thực, storage, địa chỉ ứng dụng.
- [x] Đối chiếu biến của process với file nguồn bằng tên và trạng thái, không đưa giá trị nhạy cảm ra log. Giữ thứ tự ưu tiên hiện có; không âm thầm xóa biến của người dùng để tạo PASS.
- [x] Với task cụ thể, xác định launcher hỗ trợ provider đó. Chọn rõ đường dẫn code, Python/package của worktree, dependencies khớp lockfile và địa chỉ frontend/backend sẽ kiểm tra.
- [x] Kiểm tra chỉ đọc cổng, container, database, bucket và chủ sở hữu. Nếu không có đường chạy đã được phép và bảo đảm dữ liệu an toàn, dừng phần runtime, nêu đúng khoảng trống; không chạy launcher cố định trên stack đang dùng. Nếu cần mở rộng launcher để cách ly, tách đề xuất đó để duyệt, không giấu trong sửa tài liệu.

**Đạt bước A:** Biết chính xác code nào chạy, cấu hình lấy từ đâu, loại kiểm chứng nào khả thi và giới hạn quyền. Chưa có nghĩa đã chạy ứng dụng.

### B. Chứng minh tái sử dụng `.env` bằng kiểm thử không gọi AI thật

- [ ] Chạy và đọc các regression hiện có trước khi thêm test. Fixture dùng file cấu hình tổng hợp trong thư mục tạm, không đọc `.env` thật.
- [ ] Nếu còn thiếu, mở rộng test trong hai file hiện có để chứng minh: file nằm ngoài worktree và đường dẫn chứa khoảng trắng được đọc; giá trị chứa `=` được giữ; tham số/process/file tuân thủ thứ tự hiện hành; process con nhận đúng cấu hình tổng hợp.
- [ ] Kiểm tra trường hợp thiếu file, file sai định dạng và môi trường xung đột. Test phải xác nhận mã lỗi hiện có, không có dấu hiệu startup thành công, không gọi endpoint thật và không lộ chuỗi secret giả trong stdout/stderr.
- [ ] Xác nhận file cấu hình nguồn không bị ghi lại và môi trường của process cha không bị thay đổi. Với hành vi thêm mới, viết regression gây lỗi trước, sửa tối thiểu rồi chạy lại.
- [ ] Tái sử dụng HTTP server giả và fixture CLI của repo; không tự thêm hook hoặc framework. Các subprocess test có timeout hữu hạn; cô lập proxy/cache/config theo quy định test hiện hành.

Lệnh kiểm thử dự kiến, chạy từ worktree được giao bằng Python đã xác minh thuộc checkout:

```powershell
$regressionCache = Join-Path ([IO.Path]::GetTempPath()) ('knora-env-regression-' + [guid]::NewGuid().ToString('N'))
python -m pytest -o "cache_dir=$regressionCache" backend/test/adapters/cli/test_dev_launcher.py backend/test/adapters/cli/test_ollama_launcher.py -q
```

Đọc số PASS/FAIL/SKIP và exit code; skip do thiếu shell không được tính là đã kiểm tra shell đó. Nếu thay đổi launch/harness/ownership, chạy thêm `backend/test/config/test_figma_e2e_harness.py` và ba application smoke journeys sẵn có theo Agent Environment, trong môi trường tạm được phép. Nếu chưa thể chạy, không tuyên bố đã kiểm chứng thay đổi runtime.

**Đạt bước B:** Tái sử dụng cấu hình được chứng minh bằng dịch vụ giả; không chứng minh provider thật hoặc chất lượng AI.

### C. Cập nhật hướng dẫn tối thiểu

- [ ] Bổ sung một mục tại `local-development.md`; các runbook khác chỉ liên kết, không chép lại toàn bộ hướng dẫn.
- [ ] Giải thích `.env` thuộc đường dẫn local, không thuộc tên branch; đọc file tại checkout chính không có nghĩa chạy code của checkout đó. Không yêu cầu checkout chính phải chuyển sang `main`.
- [ ] Đưa ví dụ gọi launcher từ worktree với `-EnvFile` tuyệt đối, nhưng đặt bước xác minh tài nguyên/quyền AI trước ví dụ. Ghi rõ launcher, model, endpoint và tham số chỉ là cấu hình; không phải bằng chứng cách ly hay quyền suy luận.
- [ ] Nêu rõ không dùng đường chạy smoke giả lập để đánh giá AI; không sửa `.env` chung để điều chỉnh riêng một Issue. Các override hợp lệ chỉ tồn tại trong process chạy riêng.
- [ ] Kiểm tra liên kết, cú pháp PowerShell, formatting theo file bị sửa và `git diff --check`. Không chạy formatter ghi lại hàng loạt file không thuộc nhiệm vụ.

### D. Thử một nhiệm vụ thật khi đủ điều kiện

- [ ] Chọn một tác vụ nhỏ hiện có của Knora cần AI, với đầu vào tổng hợp và tiêu chí đạt cụ thể. Không tạo thay đổi production giả để trình diễn.
- [ ] Ghi trước gói chạy: worktree/commit, nguồn cấu hình, tài nguyên được phép dùng, provider/model, ngân sách request/thời gian, dữ liệu gửi và điều kiện dừng. Token trong `.env` không tự cấp quyền cho gói này.
- [ ] Nếu được phép, thực thi một lượt bằng launcher hiện có; quan sát log và kết quả. Nếu cần UI, xác nhận trình duyệt trỏ đúng build rồi thực hiện hành trình tương ứng. Một response HTTP hoặc một câu trả lời không rỗng chỉ chứng minh kết nối, không chứng minh chất lượng.
- [ ] Thu kết quả đúng SHA/diff: request thành công/thất bại, model được chọn, đầu ra kỳ vọng so với thực tế, UI nếu có và phần chưa kiểm chứng. Không dùng bằng chứng cũ cho code mới.
- [ ] Cleanup chỉ process/tài nguyên do lượt chạy sở hữu và có quyền dọn. Nếu DB/bucket tạm chưa có thủ tục xóa an toàn, giữ lại và báo rõ; không dùng `down --volumes` cho stack dùng hằng ngày.
- [ ] Nếu thiếu tài nguyên cách ly, model, quyền hoặc ngân sách, báo phần AI thật chưa kiểm chứng và điều kiện tiếp tục; không mở rộng phạm vi để tạo PASS.

### E. Kiểm chứng bằng phiên agent mới và hoàn tất PR

- [ ] Phiên mới chỉ nhận mục tiêu, worktree và nguồn hướng dẫn, không nhận lời giải từng bước. Giao bài thử: tự tìm cách dùng `.env` ở checkout chính từ worktree, chọn kiểm thử, nhận ra giới hạn ownership và quyền gọi AI.
- [ ] Quan sát lệnh và kết quả thực thi thực tế. Nếu chưa được phép chạy AI, phiên đó phải dừng đúng giới hạn; không chấm thành công về runtime AI chỉ vì nó chọn đúng hướng dẫn.
- [ ] Commit/push thay đổi đúng worktree, tạo PR nhắm `main` sau khi được phép triển khai. Không đưa file `.env` vào staged diff.
- [ ] Xác nhận toàn bộ required CI trên SHA cuối cùng theo Verification Contract. CI không dùng `.env` local, không thêm secrets/provider và không bỏ test để đạt PASS.
- [ ] Báo riêng: đã sửa, test local, CI, runtime, đánh giá AI và review. Không tự merge hoặc deploy.

## 5. Tiêu chí nghiệm thu

1. Không cần branch test hoặc merge tạm để sử dụng cấu hình AI.
2. Worktree dùng được file `.env` tại đường dẫn chính mà không ghi/sao chép nó; code và Python package thuộc đúng worktree.
3. Kiểm thử xác nhận thứ tự cấu hình, lỗi đầu vào, bảo vệ secrets và không làm thay đổi môi trường cha/file nguồn.
4. Không ảnh hưởng stack/dữ liệu của phiên khác. Đường chạy chưa hỗ trợ cách ly được ghi là giới hạn, không được lách guard.
5. Hướng dẫn được tìm thấy từ routing hiện có, không có nguồn sự thật mới hoặc parser/launcher trùng lặp.
6. Phiên agent mới chứng minh tìm/chọn/chạy các kiểm tra được phép. Test giả, smoke ứng dụng và AI thật được báo riêng.
7. Nếu chưa chạy AI thật an toàn, có thể review phần hướng dẫn/regression nhưng không nghiệm thu mục tiêu kiểm thử AI thật. Required CI PASS chỉ xác nhận phạm vi CI.

## 6. Trạng thái lúc lập kế hoạch

Chỉ đọc nguồn và lập kế hoạch. Chưa sửa repository, chưa tạo branch/worktree, chưa đọc giá trị secrets, chưa chạy test, launcher hoặc provider. Bản V1 cần được duyệt trước triển khai; quyền chạy AI thật vẫn cần được xác định theo gói chạy cụ thể.
