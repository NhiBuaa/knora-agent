# Retrieval V3 — Kế hoạch sửa lỗi sau code review

> Dành cho agy: dùng `executing-plans`, xử lý từng task và tự review trước chuyển bước. Đây là phần bổ sung để hoàn thành bảy plan đóng băng; không thay thế hoặc giảm yêu cầu của chúng. Không tự tạo subagents chỉ vì tài liệu này.

**Mục tiêu hiện hành (checklist R6 sau review R5):** Hoàn tất 15 ID chưa đạt, kiểm lại 17 ID đạt trong phạm vi review và giao đủ bằng chứng G3–G8. Đọc §16 cùng R5 §15 và thiết kế kế thừa §14.2–§14.6. R5 tại commit `4d48f56c0a93d5019b6840bee4ffcb31a8e48a39` đã được owner duyệt ở [#153 comment 6381910609](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6381910609). R6 cụ thể hóa các sửa chữa trong phạm vi ấy; không thay D1–D8, ngưỡng nghiệm thu hoặc quyền merge/deploy.

**Kiến trúc:** Sửa tại owner của từng stage S3→S8, truyền thay đổi upstream xuống stack. PostgreSQL giữ nguồn, quyền, phiên bản, canonical derivation và serving state; Qdrant là projection có thể dựng lại. Dùng các seam ingestion, answering, provider và runtime hiện hữu; không thêm orchestration hoặc kho trạng thái song song.

**Công nghệ:** Python 3.12 của CI; PostgreSQL, Qdrant; pypdf legacy và đề xuất native pdfplumber/PDFium tại D1; Cloudflare là provider AI duy nhất; pytest, Ruff và các workflow hiện hành. Không chạy Docling ML local.

**Đặc tả:** [Issue #153](https://github.com/NhiBuaa/knora-agent/issues/153); [frozen PR #215](https://github.com/NhiBuaa/knora-agent/pull/215); plan cha `2026-10-21-retrieval-v3-coordination.md` và sáu plan con cùng thư mục. Review lần một: `C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-chain-code-review-20261022.md`; review sau remediation: `C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-remediation-code-review-20261022.md`.

**Phiên bản hiện hành:** §16 là checklist sửa chữa sau independent review R5 ngày 24/10/2026; §1–§15 giữ lịch sử và các hợp đồng kế thừa. Các câu “chờ duyệt” tại R4/R5 bên dưới mô tả lúc soạn, không phủ nhận approval R5 đã dẫn ở đầu file. Bản R4 đầu vào là commit `0251a1a6e2cd9ec52d53794016dc91a7ff6053d1`, SHA256 toàn file `69011840ce8596cdf14e9843f817ea3da53b9d1bbed437768e6b3178fc532ad7`. Không sửa hồi tố nội dung hoặc nguồn phê duyệt cũ; revision R6 thực tế được ghi trong gói bàn giao sau commit.

**Lịch sử R2:** R1 đã vào main qua PR #215, merge commit `ada17099050030fe527227fce0f2956539a2892f`. R2 được soạn tại `C:/Developer/Projects/knora-agent-worktree/docs-retrieval-v3-acceptance-remediation`, nhánh `docs/retrieval-v3-acceptance-remediation`, từ đúng merge commit đó; commit R2 `b6cff8626eb5722f27fd756f1622929908c2b63a`. Không sửa bảy plan đóng băng. Những câu mô tả lần soạn R1/R2, pins cũ và lỗi401 ở các mục dưới là lịch sử.

**Thẩm quyền:** R5 §15 cùng D1–D8 đã được duyệt theo reference ở đầu file. Yêu cầu mới trong hội thoại ngày 24/10/2026 là lập kế hoạch xử lý kết quả review R5 và prompt giao Anti. Phiên soạn R6 chỉ sửa tài liệu; Anti tiếp tục quyền triển khai/verification đã được R5 cấp sau khi đối chiếu exact approval, target và ownership. Không xin lại các quyết định không đổi; chỉ trình delta nếu thật sự vượt phạm vi đã duyệt. Merge/deploy/đóng Issue vẫn chưa được cấp quyền.

**Quyết định owner bổ sung về số lượt thực thi (24/10/2026):** Trong hội thoại này, owner yêu cầu ưu tiên đạt chất lượng và nghiệm thu, cho phép số lượt gọi AI cần thiết miễn không phung phí. Bỏ các trần tổng tự đặt của R4: 6.000 requests/campaign, các quota con theo loại call, 128 journeys/RC, 3 RC và 8.000 neurons/ngày nội bộ. Chính sách thay thế ở §14.5 áp dụng cho phần này; đây không phải lời duyệt toàn bộ R4 hay quyền bắt đầu runtime. Cloudflare-only/$0, quyền dữ liệu, giới hạn an toàn từng request và owner acceptance vẫn theo phạm vi đã chốt.

**Ngày cập nhật:** 24/10/2026, Asia/Saigon. Đây là đề xuất kế hoạch, không phải trạng thái nghiệm thu. Tiến độ và quyết định thực tế tiếp tục ghi ở #153/PR được phép, không cập nhật tài liệu này thành session ledger.

## 1. Ràng buộc áp dụng cho mọi task

1. Không làm lại S2; chỉ chạy regression liên quan. Giữ nguyên source-gold, corpus, Baseline B và approval lịch sử. Supplement mới phải có version, source review và freeze hợp lệ trước dùng để chọn cấu hình/chấm gate.
2. **Q3:** mọi embedding, OCR/layout có AI, reranking, planning/support/completeness/generation/judge có model chỉ dùng Cloudflare. Không Ollama, không provider ngầm khác, không tải weights hay local CPU/GPU inference. Parser/render/tokenizer/scoring không model và test doubles offline được phép nhưng không chứng minh semantic quality. Không phát sinh trả phí, nâng gói hoặc overage.
3. Chỉ nguồn public/synthetic có quyền được gửi cloud; private #146 giữ local, ghi not_run khi AI chưa được phép. Không loại ca khỏi denominator để đạt gate.
4. Giữ quyền Workspace/document/version và serving pointers do PostgreSQL quyết định trước Top-K; revalidate trước generation, persist và delivery. Giữ leases/fencing/CAS/receipts/reconcile; không dùng payload Qdrant làm nội dung có thẩm quyền.
5. Giữ baseline HNSW `m=16`, `ef_construct=100`, `hnsw_ef=256`; TurboQuant `bits4`, float32 originals cold/on disk, quantized pinned/RAM, `rescore=true`, `oversampling=2.0`; sparse không quantize, không `datatype=turbo4`. BM25 200 + dense 200 → DBSF 100 → SDM tối đa100 → rerank/coverage/evidence.
6. Legacy V1/V2 giữ ID, behavior và thresholds `0.65`/`0.657410732025`, evidence5 chunks/3000tokens. Hành vi V3 opt-in qua policy/config có version. BM25-only có0 query embedding calls. Không đổi operational error thành refusal thiếu thông tin.
7. **Q6:** Top-K miss không chứng minh nguồn thiếu. Tự tra nguồn đúng scope/version/page; found thì trả lời và cite; chỉ verified_absent sau kiểm đủ phạm vi có completeness. OCR/lookup/quota/deadline/coverage không rõ là unknown/operational error. Ambiguity là yêu cầu làm rõ trong Conversation, không bịa phần so sánh còn thiếu.
8. Không merge/deploy, force-push/reset, xóa branch/worktree/volume, đổi credentials/quyền dữ liệu, cài host tool/plugin hoặc bật provider mới theo kế hoạch này. Commit/push sửa trên chính các PR được giao theo quyền hiện hữu; nếu quyền của phiên đích không bao gồm publication thì chuẩn bị diff và gói publish, không suy quyền từ việc có credentials.
9. Thực thi kỹ thuật theo Q2: tự chọn implementation, version/pins tương thích và giới hạn hữu hạn bằng tài liệu + development evidence + review. Không hỏi lại từng tham số; không tự hạ tiêu chí hoặc ký thay owner. Gom phần cần owner thành các gói tại §9.
10. Sửa code ở stage sớm nhất sở hữu lỗi; không chỉ vá S8. Trước ghi xác nhận exclusive ownership worktree, giữ thay đổi của phiên khác. Không mượn runtime/DB/credentials của #158/#192 hoặc owner khác.

### Phân trang: xử lý khác biệt diễn đạt, không đổi requirement ngầm

ADR0007 và CONTEXT hiện quy định **mỗi chunk nằm trong một trang vật lý**, cho phép nhiều chunks trong cùng trang với target500/overlap75/max650tokens. Handoff/user diễn đạt “1 trang=1chunk”. Hai câu không tương đương.

Triển khai ngay phần chắc chắn chung: physical page anchors chính xác, không gộp nội dung xuyên trang, không giả page1/COMPLETE. Giữ policy ADR hiện hữu trong lúc sửa, không bỏ token cap hoặc âm thầm đổi legacy chunk count. Đưa đối chiếu này vào gói G3 cho owner: đề xuất chuẩn hóa câu chữ theo ADR; nếu owner yêu cầu đúng một chunk/page thì trình tác động với trang vượt650tokens và policy version mới trước áp dụng. Không tuyên bố đã giải quyết cách hiểu còn mâu thuẫn chỉ bằng CI xanh; phần khác không phải chờ câu hỏi này.

## 2. Subjects và đường dẫn nhận việc

Root duy nhất: `C:/Developer/Projects/knora-agent-worktree/`. `R` trong các path bên dưới nghĩa là root của **stage đang sửa**, không phải primary checkout hoặc mặc định S8.

| PR | Thư mục / branch | Head review ban đầu |
|---|---|---|
|215|`docs-retrieval-v3-plans` / `docs/retrieval-v3-plans`|`964e3481551230a99400d1a4e47368b0617491b0`|
|216 S3|`feat-retrieval-v3-document-understanding` / `feat/retrieval-v3-document-understanding`|`2158c58f2e4a166511773bda16f47cf0ee969db8`|
|217 S4|`feat-retrieval-v3-dense-hybrid-search` / `feat/retrieval-v3-dense-hybrid-search`|`5d75d2f044f4c22db28cd5cab8de5d36ba1e98a4`|
|218 S5|`feat-retrieval-v3-sequential-dependence-ranking` / `feat/retrieval-v3-sequential-dependence-ranking`|`d1756f602851ed4ebbfc1523ad6eea012b097bfa`|
|219 S6|`feat-retrieval-v3-reranking-evidence` / `feat/retrieval-v3-reranking-evidence`|`2647cee1bbcd93fd9302a5d5fc48aa16f0174314`|
|220 S7|`feat-retrieval-v3-query-understanding-coverage` / `feat/retrieval-v3-query-understanding-coverage`|`622fa778d1745456f28168931acd484375355546`|
|221 S8|`feat-retrieval-v3-integrated-release` / `feat/retrieval-v3-integrated-release`|`a1ed551f5dc73e5a7446058d4858f654faaf4bf4`|

Đây là pins của review, không khóa head phải giữ nguyên sau remediation. Tại lần đọc thành công trong phiên lập plan, local heads vẫn như trên; #215 và #221 remote cũng khớp, đều OPEN. Các PR còn lại có remote snapshot từ review. Lần định đọc lại full status bị automatic approval reviewer lỗi401 trước thực thi; agy phải refresh toàn bộ, không gọi các số trên là trạng thái live.

### Liên kết bảy plan đã đóng băng

Các liên kết dưới đây pin commit `964e3481551230a99400d1a4e47368b0617491b0`; đọc bản worktree và đối chiếu commit trước dùng nếu branch đã đổi:

| Owner | Frozen plan |
|---|---|
|Cha|[Coordination](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-coordination.md)|
|S3|[Document understanding](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-document-understanding.md)|
|S4|[Dense/hybrid search](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-dense-hybrid-search.md)|
|S5|[Sequential dependence ranking](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-sequential-dependence-ranking.md)|
|S6|[Reranking/evidence](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-reranking-evidence.md)|
|S7|[Query understanding/coverage](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-query-understanding-coverage.md)|
|S8|[Integrated release](https://github.com/NhiBuaa/knora-agent/blob/964e3481551230a99400d1a4e47368b0617491b0/docs/plans/2026-10-21-retrieval-v3-integrated-release.md)|

Review ghi #215/#216 có required CI thành công; #217–#221 chưa có required CI. Workflow `CI` có `workflow_dispatch`, nên có thể chạy thủ công đúng branch ngay trước merge; không cần sửa trigger hoặc hạ branch protection. Dispatch trước merge không thay PR CI của synthetic merge sau retarget.

## 3. Quy trình kiểm chứng dùng cho từng task

Mỗi task là một vòng: **đọc callers/tests/config → thêm ca đỏ đúng nguyên nhân → chạy thấy lỗi → sửa tối thiểu → ca xanh + regression boundary → review diff → commit có `Refs #153`**. Những bước này là checkbox thực thi, không cho phép sửa expected output/gold để che hồi quy.

Tại `R` xác nhận `.venv` thuộc đúng checkout. Dùng `.venv/Scripts/python.exe` hoặc interpreter đã pin của chính worktree; không mượn môi trường owner khác. Ví dụ command offline:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& ./.venv/Scripts/python.exe --version
& ./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider backend/test/adapters/pdf/test_docling.py
```

Nếu pytest plugin autoload bị tắt trong phiên thì thêm `-p pytest_asyncio.plugin` cho async suites. Không nhận async-not-supported, thiếu dependency, collection0 hoặc skip là ca đã kiểm. Đọc root `conftest.py`/workflow trước chạy: test dưới `backend/test/adapters/postgres` và CLI reindex có thể nối DB; chỉ chạy chúng với DB test riêng sau preflight, không chạy tràn từ suite cha.

Python diff bắt buộc, từ root stage: `python -m ruff format .`, `python -m ruff format --check .`, `python -m ruff check .`; kiểm diff sau format. Frontend/shared/OpenAPI nếu bị tác động theo AGENTS. Chọn CI partitions theo runbook; `--ci-suite` luôn kèm `--ci-selection`. Không chạy runtime/profile chỉ vì tên file nằm trong `runtime_test`.

Manual CI trên branch đã push, trong quyền hiện hữu:

```powershell
gh workflow run ci.yml --repo NhiBuaa/knora-agent --ref feat/retrieval-v3-dense-hybrid-search
```

Ghi run ID và xác minh `headSha`, `ci-subject`, test selection/counts, required aggregate; branch có commit mới phải kiểm lại. Python3.13 local không thay Python3.12 compatibility. Không tái sử dụng CI/runtime của head cũ.

> 🧠 **From Hindsight memory (Conventions and patterns)** — Quy tắc lịch sử tách workflow source khỏi full `subject_sha` của code cần kiểm. Đã đối chiếu lại với runbook CI hiện hành; dùng hợp đồng hiện hành, không dùng ví dụ SHA cũ hoặc tự suy mọi task cần OTP.

### Checklist đóng một finding

- [ ] Liên kết F-ID → commit owning stage → ca đỏ trước sửa → ca xanh sau sửa.
- [ ] Callers, worker/CLI/HTTP, config, fixtures, exports và downstream contracts bị ảnh hưởng đã được kiểm.
- [ ] Tách code/local/CI/runtime/review/gold approval/owner acceptance/merged/deployed; thiếu một tầng thì ghi rõ chưa kiểm.
- [ ] Mọi artifact có subject/config/dataset/scorer hashes và actual attempts/pass/fail/not_run; không nhận report tự ghi PASS thiếu raw evidence.
- [ ] Nếu finding không còn đúng trên head mới, ghi diff và ca phản chứng; không lặng lẽ xóa F-ID. Cả25 IDs đều cần disposition.

## 4. Thứ tự và ownership của 25 findings

| Task | Owning stage | Findings chính | Phụ thuộc / cổng |
|---|---|---|---|
|T0|điều phối|inventory và hồ sơ claims F16 được gắn chưa xác minh sớm|trước sửa|
|T1|S3 fix → S4–S8|F01|Python3.12 guard trước mọi stage|
|T2|S3|F02|Cloudflare wire đúng|
|T3|S3|F03, F24|T2; physical source/completeness|
|T4|S3|F04, F20|T3; G3|
|T5|S4|F05, F06, F11|S3 source contract; composition/Q3|
|T6|S4|F07, F23, F25|T5; projection/pool contracts|
|T7|S4|F19|scorer trước benchmarks; G4|
|T8|S5|F08|S4 authoritative stats + T6; G5|
|T9|S6|F09, F10|S4 pool/S5 scores; G6|
|T10|S7|F12, F18, F22|S6 evidence; query/support|
|T11|S7|F13|T10 + persisted S3 source coverage|
|T12|S7|F14, F15|T10/T11; G7|
|T13|S8|F16, F17, F21|tất cả upstream; G8|

Thứ tự chính vẫn S3→S4→S5→S6→S7→S8. Có thể đọc/viết offline fixtures task sau khi chờ owner package nhưng không gọi stage phụ thuộc đã đạt nếu gate trước chưa đủ. Sau mỗi stage sync vào branch ngay sau rồi truyền tiếp; G8 kiểm hợp nhất một lần nữa trên RC cuối.

## 5. S3 — Khôi phục document-understanding thật và G3

Đọc plan gốc `2026-10-21-retrieval-v3-document-understanding.md`, Tasks1–6. Các task dưới đây không thay nhiệm vụ table/heading/reading-order truth hoặc Việt–Anh OCR đã freeze.

### T0 — Nhận ownership, pins và sửa mức tin cậy của hồ sơ

**Files:** đọc AGENTS/CONTEXT/architecture/seams, toàn bộ frozen plans và review25 findings. Không sửa report lịch sử. Nhập tài liệu này vào vị trí chính thức sau xác nhận đúng branch/không trùng file.

- [ ] Đọc Issue/PR discussions mới; lấy full head/base/state/CI, `git status`, ancestry và diff stage. Nếu head đã đổi, review delta thay vì chồng patch lên thông tin cũ.
- [ ] Xác nhận phiên cũ đã checkpoint/nhường quyền; không có hai writer cùng worktree. File lạ/untracked phải giữ nguyên. Primary `codex/test` với `pr_body.md`, `update_pwsh.py` nằm ngoài phạm vi.
- [ ] Tại #153/PR theo quyền Q7 đã có, ghi kết luận review: G3–G8 chưa được xác nhận; report PASS cũ chưa là acceptance. Giữ report cũ làm lịch sử và tạo kết quả mới có supersedes/provenance, không ghi đè.
- [ ] Đối chiếu F16 từ raw paths/manifest/RC/approval URLs trước tin vào bảng aggregate; chuẩn bị gói gold cần owner duyệt ngay từ đầu, không đợi cuối mới phát hiện thiếu quyền.

**Đầu ra:** inventory subjects/ownership trong Issue/PR; danh sách exact upstream subjects và kế hoạch đo, chưa có runtime claim.

### T1 — Đồng bộ dataclass fix xuyên stack (F01)

**Files:** `R/backend/src/knora/adapters/pdf/docling.py`, `R/backend/test/adapters/pdf/test_docling.py` tại S3 và downstream. Không rewrite fix thành cơ chế kế thừa mới.

- [ ] Giữ `PdfExtractionConfiguration.__post_init__(self)` của `2158c58f`; test parent limits không dương và `enable_local_models=True` đều bị từ chối.
- [ ] Sync upstream vào S4 rồi S5→S8 bằng merge không rewrite history khi nhánh sạch và exclusive. Kiểm `git show 2158c58f`/ancestry trước merge, không chép toàn S8 ngược lên S3. Nếu commit đã có, không áp dụng lần hai.
- [ ] Chạy `test_docling.py` trên Python3.12 của CI/own interpreter; thêm negative config ca còn thiếu. Mỗi downstream phải có fix thực, không chỉ ancestry marker.
- [ ] Ghi commit/head mới; trước các đợt đo chính phải truyền tiếp toàn bộ sửa S3 sau T4, không coi bước sync sớm này là đã sync hết remediation.

**Đạt khi:** tất cả S4–S8 có fix; CI3.12 khởi tạo config và negative validation đạt. S3 local7 tests chỉ là regression cơ bản, không G3.

### T2 — Cloudflare conversion đúng wire và fail rõ (F02)

**Files:** `R/backend/src/knora/providers/cloudflare/pdf_understanding.py`; tạo test owner `R/backend/test/providers/cloudflare/test_cloudflare_pdf_understanding.py`; cập nhật fake converter `test_docling.py` khi contract đổi.

**Seam:** giữ `CloudflarePdfUnderstandingProvider.convert_to_markdown(bytes)` và immutable response ở provider boundary; canonical pages/source map do extraction layer xử lý, không lấy response Markdown làm oracle.

- [ ] Context7 resolve/query và official REST docs cho đúng API hiện hành; pin request/response fixture đã khử dữ liệu. Multipart `files`; result list theo file, kiểm `data`, `format`, conversion errors, identity, empty/partial/malformed response. Không tự đoán revision.
- [ ] Đặt ca đỏ theo hợp đồng thật, bổ sung multiple files/unexpected filename/missing content và HTTP429/timeout. Ví dụ ca schema ngay tại test file mới:

```python
def test_tomarkdown_parses_real_envelope():
    import httpx
    from knora.providers.cloudflare.pdf_understanding import CloudflarePdfUnderstandingProvider

    def endpoint(request):
        assert b'name="files"' in request.content
        return httpx.Response(200, json={"success": True, "result": [
            {"name": "document.pdf", "format": "markdown", "data": "# Policy"}
        ]})

    with httpx.Client(transport=httpx.MockTransport(endpoint), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="a" * 32, api_token="test-only", client=client
        )
        assert provider.convert_to_markdown(b"%PDF-test").content == "# Policy"
```

- [ ] Chạy file mới + `backend/test/adapters/pdf/test_docling.py`, thấy ca schema đỏ trước sửa rồi xanh. Đây là offline wire evidence; remote call chỉ sau runtime preflight §8.

**Đạt khi:** response đúng không còn list.get crash, response sai không được gắn COMPLETE; không rò token/request content trong lỗi/log.

### T3 — Physical-page source map, selective OCR và resource envelope (F03/F24)

**Files:** `R/backend/src/knora/adapters/pdf/docling.py`, `ingestion/pdf_structure.py`, `ingestion/pdf_chunking.py`, `ingestion/pdf.py`; adapter pypdf/render/subprocess hiện có khi cần. Tests: `backend/test/adapters/pdf/test_docling.py`, `backend/test/ingestion/test_pdf_structure.py`, `test_pdf_chunking.py`, `test_pdf_job_processing.py`.

**Consumes:** raw PDF/version/config + conversion/OCR boundary đã validate. **Produces:** canonical physical pages/blocks/tables, true native/OCR provenance và completeness; chunks giữ source page/span, tokenizer/config version để T4 lưu.

- [ ] Ca đỏ: native PDF2 pages với nội dung riêng; scan page; mixed native/scan; page trống; heading/table qua trang; conversion mất trang; bbox không có; OCR429/partial. Kiểm output page numbers khớp physical source, nội dung trang2 không có source anchor trang1. Không bịa bbox/confidence/native origin từ Markdown.
- [ ] Dùng page-aware native parser/render không model có provenance; nối selective OCR thật vào `extract()` theo page cần OCR. Không sửa bằng split Markdown headings hoặc hardcode page1. Thư viện khởi tạo local OCR/layout/model downloader phải fail trước gọi.
- [ ] Bounded read tối đa `max_raw_bytes+1`, kiểm pages/page-stream/total-stream/render pixels theo config trước remote work. Enforce memory/CPU/process-tree deadline cho child parse/render và total deadline cả remote+retry; error giữ serving derivation cũ, cleanup chỉ owned child.
- [ ] Ca đỏ giới hạn: stream quá bytes không bị đọc vô hạn; số trang quá cap; parser/render memory/timeout; remote429/retry hết trần. Kiểm không còn call sau budget và không publish partial canonical COMPLETE.
- [ ] Offline tests theo bốn file trên; runtime parser/OCR/source fidelity đo ở G3 sau quyền/caps. Nếu Docling không cung cấp native route không ML đạt requirement, dùng native adapter được plan cho phép và ghi parity/mismatch; không cài weights hoặc đổi provider để vượt chặn.

**Đạt khi:** source-page mapping có thể kiểm lại độc lập; completeness thiếu là unknown, không nguồn đầy đủ giả. Giải quyết đối chiếu ADR trong gói G3; không tự đổi token policy.

### T4 — Canonical persistence, reload/lifecycle và gold portability (F04/F20)

**Files:** `R/backend/src/knora/adapters/postgres/ingestion_jobs/coordination.py`, `adapters/postgres/tables.py`, `ingestion/job_processing.py`, `ingestion/pdf.py`; migration additive trong thư mục Alembic hiện hữu nếu cần. Dataset owner `evals/datasets/pdf_document_structure_v1.py`, `.gitattributes` chỉ pin line endings cho artifact liên quan; không normalize raw PDF bytes.

**Tests:** `backend/test/adapters/postgres/test_pdf_derivation_finalization.py`, `test_pdf_evaluation_e2e.py`, `test_s2_reprocess_retry.py`, `test_s2_job_readiness.py`; `evals/test/test_pdf_document_structure_dataset.py`.

- [ ] Viết round-trip DB tests trên cả hai nhánh finalization: save/reload giữ pages, ordered blocks, table cells/merged spans, headings, anchors, native/OCR origin, completeness, block/table IDs và search context khi tồn tại. Bind DocumentVersion/ChunkSet/config/raw hash, không lưu canonical JSON ở Qdrant làm authority.
- [ ] Migration cùng atomic finalization; failure/lease-stale/CAS retry không kích hoạt partial derivation; reprocess/idempotent retry không trộn canonical của ChunkSet khác. Migration/backfill chỉ trên stack riêng được phép; legacy row thiếu structure phải ghi unavailable, không chế dữ liệu.
- [ ] Ca gold hash LF/CRLF cho cùng text artifact cho cùng canonical digest theo convention được pin; đổi nội dung thật hoặc raw PDF vẫn bị từ chối. Chọn narrow `.gitattributes` LF hoặc existing canonical-text hashing, giải thích tương thích historical hash; không sửa frozen expected hash để khớp checkout.
- [ ] Offline chạy `evals/test/test_pdf_document_structure_dataset.py`; DB suites chỉ trong own disposable DB sau §8. Chuẩn bị reviewed structure annotations từ raw sources độc lập output parser, metrics/denominators và approval đúng artifact theo S3 Task5/6.

**G3:** T2–T4 và gốc S3 đạt; Python3.12 CI đúng head, runtime extraction/persistence/source mapping có evidence, gold/source approval thật. Sync accepted source contract và fixes xuống S4→S8; thiếu gold/quyền runtime giữ gate chưa đạt, tiếp tục phần offline độc lập.

## 6. S4–S6 — Retrieval/ranking chạy qua application seam

### T5 — Compose V3, dynamic ingestion và Cloudflare-only (F05/F06/F11)

**Files:** tại S4: `backend/src/knora/main.py`, `bootstrap.py`, `infrastructure/lexical_configuration.py`, `infrastructure/settings.py`, `ingestion/module.py`, `ingestion/search_indexing.py`, `adapters/postgres/ingestion_store.py`, `adapters/postgres/search_index_store.py`, `adapters/cli/reindex_search.py`, `providers/cloudflare/embedding.py` và embedding config owner.

**Tests:** mở rộng `backend/test/answering/test_dense_hybrid_contract.py`, `backend/test/providers/cloudflare/test_cloudflare_embedding.py`, `backend/test/adapters/cli/test_reindex_search.py`, `backend/test/ingestion/test_search_indexing.py`, `backend/test/adapters/postgres/test_text_search_indexing.py`, `test_corpus_statistics_transition.py`; config/composition tests tại owning package hiện có.

- [ ] Ca composition đi từ deployment selector qua actual main/bootstrap đến index/store/provider: BM25-only, dense-only, hybrid đều khởi tạo đúng profile; V3 không phụ thuộc finite S2 manifest. Giữ finite benchmark profile và S2 semantics nguyên trạng.
- [ ] Guard mọi V3 AI route trước provider creation/invocation: CF embedding/generation/OCR/rerank/planning/support/checker/judge nếu có; Ollama/Gemini/generic non-CF endpoint bị từ chối. Kiểm endpoint allowlist/redirect/token safety. Legacy adapter vẫn có thể tồn tại cho ngoài V3; không xóa cả hệ provider để sửa guard.
- [ ] Payload theo model contract: BGE nhận `text`, Qwen giữ contract riêng. Test document/query batching/order/dims/token bounds và HTTP errors theo fixture thực; không đổi model vì muốn test xanh. BGE max input phải được enforce/route rõ trong profile, không truncate citation text ngầm.
- [ ] Nối PDF/text HTTP/CLI producers và dynamic corpus membership/statistics bằng existing job/lease seam. Backfill có selection/dry-run/checkpoint/resume thật; không chỉ bỏ finite guard và giả active generation. Empty corpus hợp lệ khác missing profile/index.
- [ ] Test text upload ngoài16-PDF manifest → stage → validate → activate → retrieve; PDF tương tự. Test retry/partial indexing/rollback/archive/reprocess làm membership/stats thay đổi nhất quán; không activate trước receipt. HTTP/CLI dùng cùng application seam.

**Đạt khi:** V3 thực sự chọn được mode và index; tất cả AI route sai bị chặn trước model call; dynamic producer/consumer hoạt động end-to-end trên DB test riêng, BM25 query embedding count=0.

### T6 — Candidate pool, dense provenance và collection readback (F07/F23/F25)

**Files:** S4 `backend/src/knora/answering/stores.py`, `adapters/postgres/lexical_retrieval.py`, `adapters/postgres/search_index_store.py`, `ingestion/search_indexing.py`, `adapters/qdrant/search_index.py`, `adapters/qdrant/native_search_index.py`.

**Tests:** `backend/test/adapters/qdrant/test_dense_search_index.py`, `test_search_index.py`, `test_native_search_index.py`, `test_langchain_parity.py`; `backend/test/adapters/postgres/test_s2_generation_loading.py`, `test_answering_store.py`; `backend/test/answering/test_dense_hybrid_contract.py`.

**Produces:** authorized pool≤100 với query/generation/profile/embedding-set identity và locators; T8/T9/T10 chỉ giảm pool ở đúng tầng evidence/output.

- [ ] Red rank9 fixture được SDM/reranker đưa vào evidence; store không cắt theo outputTop8 trước scoring. Assert each prefetch limit200, fused limit100, all tenant/version/generation filters trước selection; malformed/duplicate IDs bị từ chối.
- [ ] Ca hai completed embedding sets cùng768dimensions nhưng khác model/config; generation bắt buộc chọn set đã pin, không maxUUID. Staging/readback/receipt/retrieval xác minh config/set/dimension/vector completeness/digest; query không được tự gắn embedding ID của mình cho vectors không có proof. Missing vector/mixed model giữ generation chưa phục vụ.
- [ ] Red existing collection cùng dimension nhưng sai distance/datatype/on-disk/HNSW/TurboQuant: `ensure_collection()` phải từ chối, không tự PATCH collection đang serving. Đối chiếu wire + normalized readback của đúng server pin; defaults/cold/pinned/float32 phải có evidence. Rescore/oversampling kiểm ở query params; extra JSON fields trong create body không là proof server thực thi.
- [ ] Dùng lại offline repro `retrieval_v3_collection_review_probe.py` làm mẫu negative contract; chuyển thành owning test. Kiểm float32 reference vs bits4 configuration và rollback collection riêng. Native/LangChain parity nếu wrapper không giữ invariant thì native path có lý do/tests theo plan.

**Đạt khi:** pool thật giữ≤100 qua ranking; vector/projection có provenance kiểm được, collection mismatch fail rõ; authority/lifecycle regressions vẫn đạt.

### T7 — Scorer đúng protocol trước benchmark (F19)

**Files:** S4 `evals/runners/retrieval_ranking.py`, `evals/test/test_retrieval_ranking.py`, development dataset/manifest/approval owner hiện có.

- [ ] Recall@k đếm unique relevant items, denominator là tổng relevant items trong judged universe; graded gains giữ cho DCG/nDCG. Ca `[3,1]` lấy item grade3 cho recall0.5, không0.75.
- [ ] MRR@k chỉ xét rank≤k; positive rank11 cho MRR@10=0. Nếu muốn MRR không cutoff thì giữ tên/protocol riêng, không ghi @10. Empty/IDCG0/unjudged/duplicate cases giữ policy rõ; missing judgments không biến thành irrelevant.
- [ ] Thêm ca đỏ tối thiểu dùng API hiện có:

```python
def test_recall_counts_items_not_grade_weight():
    from evals.runners.retrieval_ranking import compute_recall_at_k
    assert compute_recall_at_k([3, 0], total_positive=2, k=2) == 0.5
```

- [ ] Chạy `evals/test/test_retrieval_ranking.py` và development dataset tests; sửa callers/aggregation/report version để không so số cũ sai protocol với số mới. Freeze valid development judgments trước scoring/tuning; approval URL phải duyệt đúng supplement/hash, không comment S1 runtime binding.

**G4:** đủ T5–T7 và S4 Task8 trên runtime có quyền: PDF/text/backfill/corpus transition; exact filtered reference/ANN diagnostics eligible population>200; full S4 subset matrix; cùng source/model/filter và raw captures. Workload target3 queries/1PDF/10kchunks; quantization degradation hybrid nDCG@10≤0.01 so float32 HNSW. Thiếu nhãn/ANN path/usage evidence thì không PASS. Chỉ diagnostic synthetic vectors không chứng minh semantic embedding quality.

### T8 — SDM dùng authoritative corpus statistics (F08)

**Files:** S5 `backend/src/knora/answering/module.py`, `answering/sequential_dependence.py`, `ingestion/lexical_population.py` (owner `CorpusStatisticsSnapshot`), `ingestion/lexical_positions.py`, `adapters/postgres/search_index_store.py` và statistics reader owner hiện hữu. Không tạo file/store authority mới chỉ vì tên `corpus_statistics`.

**Tests:** `backend/test/answering/test_sequential_dependence.py`, `backend/test/ingestion/test_corpus_statistics.py`, `test_lexical_positions.py`, `backend/test/adapters/postgres/test_corpus_statistics_transition.py` và dense/hybrid contract tests.

- [ ] Lookup corpus membership/statistics snapshot đã pin theo Workspace/serving generations/tokenizer, không tính collection frequency/total_tokens từ Top-K. Bind actual digest/profile/version trong trace, không lấy lexical policy ID giả làm digest.
- [ ] Ca cùng corpus snapshot và pair query/chunk, thay distractor pool không đổi background probabilities; chuyển active generation mới đổi statistics digest đúng một lần, stale snapshot/revoke fail trước generation.
- [ ] Golden numerical tests ordered/unordered windows, smoothing, tokenizer positions và term frequencies theo plan S5. Không trộn normalized lexical offsets vào source offsets. Candidate pool≤100 từ T6, không quay lạiTop8.
- [ ] Calibration/ablation cùng development judgments/protocol T7; Phrase Boost chỉ evaluation comparator, giữ công thức/version/lambda; lexical matrix và raw captures có thể tính lại.

**G5:** statistics/positions đúng snapshot; numerical tests và lexical matrix/calibration đạt trên head S5; truyền xuống S6–S8.

### T9 — Reranker config/provider/wire thực và fallback (F09/F10)

**Files:** S6 `backend/src/knora/answering/stores.py`, `answering/reranking_configuration.py`, `answering/reranking.py`, `answering/module.py`, `providers/cloudflare/reranking.py`, `main.py` và lifecycle close owner.

**Tests:** `backend/test/providers/cloudflare/test_cloudflare_reranking.py`, `backend/test/answering/test_reranking_configuration.py`, `test_reranking_pipeline.py`, `test_reranking_mmr.py`, `test_dense_hybrid_contract.py`.

- [ ] Thống nhất immutable policy IDs giữa factory/resolver/admin settings và inject provider/config đúng lifecycle từ main. Test actual deployment selector→resolved config→provider call→score mapping→evidence, không chỉ helper hoặc fake success trace.
- [ ] Context7 + official API pin response envelope/model/context identity; parse `result.response` theo actual schema. Fixture reordered/partial/duplicate/unknown context IDs phải không gán score theo vị trí ngầm. Validate finite scores, normalization và missing outputs.
- [ ] API429/timeout/malformed/partial dùng fallback DBSF+SDM được trace đúng; fallback không local model, không Phrase Boost production, không làm mất source eligibility/snapshot fence. Cả enabled/disabled/provider-not-configured path đều có test và config error tường minh.
- [ ] MMR và evidence budget preserve coverage group candidates để S7 chọn đủ nhóm trước fill; score kinds tách biệt. Provider close/error/timing được trace, lỗi không report0ms/0cost như chạy thành công.
- [ ] Chạy selected reranking tests rồi runtime invocation sau preflight: endpoint/model quyền thật, Việt–Anh source-reviewed quality, ablation legacy/full/no-neural cùng cases, usage/quota/$0. Model catalog hoặc tiếng Anh name không chứng minh bilingual quality.

**G6:** neural stage chạy thật khi enabled, safe fallback và full matrix có evidence; không gọi green mocks là nghiệm thu chất lượng.

## 7. S7 — Query, source recovery và câu trả lời đủ nội dung

### T10 — Atomic groups, execute variants và pool cap (F12/F18/F22)

**Files:** S7 `backend/src/knora/answering/query_planning.py`, `query_results.py`, `evidence_support.py`, `evidence.py`, `module.py`, `stores.py`; LangChain query adapter hiện có chỉ khi contract cần, không tạo pipeline khác.

**Tests:** `backend/test/answering/test_query_plan_models.py`, `test_query_results.py`, `test_evidence_support.py`, `test_group_evidence_selection.py`, `test_dense_hybrid_contract.py`, `test_bm25_contract.py`; adapter planner tests owning package.

- [ ] Mỗi subquestion chỉ chứa phần cần trả lời của chính nhóm; global protected spans không tự trở thành constraint của mọi nhóm. Ca câu so sánh C2 thời hạn/C5 giảm giá, chỉ chunkC2 không được support nhómC5.
- [ ] Support dùng source facts/constraints đủ và exact boundaries: C2 khácC20;14khác140; AUTH_403 không thay AUTH_404; ngày/đơn vị/phủ định/contradiction kiểm riêng. Keyword40%/citation/LLM self-report không là chứng minh factual support. Nếu dùng semantic assessor thì CF-only, schema/budget/unknown và nguồn có quyền; runtime không import gold.
- [ ] Nối plan.variants/subquestion searches vào application seam thật; aggregate provenance/fair pooling với cap toàn request, không≤100 cho từng variant rồi ghép vô hạn. Fast path không nuốt typo/accent hypothesis cần thiết; không tự sửa identifier/số/ngày/phủ định hoặc thay ý nghĩa.
- [ ] Cap kiểm trước mỗi append; duplicate identity includes authorized canonical source identity. Negative config cap0/âm phải được validate, cancellation/deadline không phát sinh searches tiếp theo. Round-robin3 groups/cap2 trả≤2.
- [ ] Thêm ca đỏ tại test_query_results.py, dùng `_make_candidate` đã có trong cùng file:

```python
def test_cap_is_enforced_inside_round_robin():
    result = merge_cross_query_candidates(
        {f"q{i}": [_make_candidate(f"c{i}", 0.5)] for i in range(3)},
        max_total_candidates=2,
    )
    assert result.total_candidates == 2
    assert len(result.candidates) == 2
```

**Đạt khi:** executed searches/trace trùng finite plan, groups gắn đúng nguồn; ca sai số/chương/identifier không false-supported; aliases/source offsets không drift sau rewrite.

### T11 — Source-verification đúng Q6, quyền và coverage (F13)

**Files:** S7 `backend/src/knora/answering/source_verification.py`, `stores.py`, `module.py`, `evidence_support.py`, PostgreSQL authorized source reader tại owner hiện có, canonical reader của T4; tests `backend/test/answering/test_source_verification.py`, `test_s2_snapshot_fence.py`, `test_module.py` và PostgreSQL reader tests trên DB riêng.

**Contract tối thiểu:** outcome phân biệt found, verified_absent, unknown/unverified và ambiguity; checked document-version/page/section scope + completeness + budget/deadline + snapshot token/provenance. Có thể giữ tên `unverified` đang có; không tự thêm public enum trước review caller contract.

- [ ] Không reuse dense/hybrid config với vector=None cho targeted lexical lookup. Chọn lexical-only authorized search profile hoặc source-reader seam thực. Search chỉ tìm locator; verified absence cần enumerate/inspect toàn phạm vi bắt buộc trong canonical nguồn có completeness.
- [ ] Empty Top-K và all-hits-already-known đều không chứng minh absence. Catalog chỉ chứng minh section không tồn tại nếu catalog đủ, đúng source/version và truy vết nguồn; catalog partial không đủ. Không tự lấy newest version thay serving pointer.
- [ ] Tự recovery một package hữu hạn: xác định missing groups → locate/read allowed source pages → assess facts → repair evidence trong budget → final support recheck. Giữ provenance, dedupe và eligibility khi thu thêm source. Không chạy jobs/OCR vô hạn trong answering; cần extraction mới thì chỉ dùng lifecycle được duyệt, timeout/partial là unknown.
- [ ] Cases bắt buộc: source cóC5 nhưng Top-K miss→found/cite; source complete thật không cóC5→verified_absent; OCR missing/page unknown/permission changed/deadline/quota/lookup exception→unknown hoặc lỗi vận hành tương ứng; nhiềuC5 trong tài liệu khác→ambiguity theo scope. Unauthorized decoy không tham gia hoặc tiết lộ sự tồn tại.
- [ ] Caller switch theo outcome; không mọi unsupported đều REFUSAL INSUFFICIENT_EVIDENCE. Revalidate generation snapshot sau recovery và trước deliver/persist. Nếu public API/Conversation cần delta, truy đầy đủ HTTP/SSE/OpenAPI/frontend callers theo plan S7 Task8, regenerate/export đúng tool; không chỉ đổi prompt.

**Đạt khi:** demo “tìm lại tài liệu trước kết luận thiếu” có test application + runtime thật; verified_absent cần source-coverage evidence, unknown không giả absence.

### T12 — Versioned final completeness và legacy compatibility (F14/F15)

**Files:** S7 `backend/src/knora/answering/generation_validation.py`, `answering/module.py`, `answering/evidence.py`, `providers/generation.py`, `providers/structured_generation.py`, Cloudflare generation và LangChain adapter áp dụng. Conversation context/stream callers nếu bị tác động.

**Tests:** `backend/test/answering/test_answer_group_completeness.py`, `test_module.py`, `test_issue_61_trace_contract.py`, `test_question_stream_answering.py`, `test_reranking_pipeline.py`, `test_dense_hybrid_contract.py`, `backend/test/adapters/qdrant/test_langchain_parity.py`, `backend/test/conversations/test_context.py`.

- [ ] Opt-in V3 planner/support/completeness theo policy/config version; legacy flows không vô điều kiện qua keyword gate. Follow-up dùng context để hiểu câu hỏi nhưng context không trở thành evidence. Không sửa legacy tests/gold cho hợp gate mới.
- [ ] Contract required-group → substantive final answer span → verified source span/citation, dùng selected evidence và source support đã revalidate. Check cả single-group lẫn multi-group; nhắc tên nhóm/citation đơn thuần không đủ, marker order/source-version mapping vẫn giữ.
- [ ] Red câu trả lời `Chương 2 và Chương 5. [[E1]] [[E2]]` với nguồn2chương: phải bị từ chối vì không trả lời facts; thêm sai số/ngày/phủ định, đúng facts nhưng citation nhầm, answer bỏ1nhóm, hallucinated complete claim. Positive paraphrase đúng nguồn phải được chấp nhận, không buộc literal keyword overlap.
- [ ] Semantic checker nếu chọn dùng Cloudflare theo Q2 phải có version/schema/budget và source-reviewed false-complete/false-insufficient tests; unknown/error là operational state, không tự PASS. Không dùng LLM fill claim map làm oracle độc lập.
- [ ] Validation trước SSE answer bytes và persist, không stream nửa câu so sánh rồi mới reject. Nếu contract cần buffer/regenerate bounded, pin budget và trace; exhausted repair không giả hoàn chỉnh.
- [ ] Chạy toàn `backend/test/answering`, Qdrant parity và context suites phù hợp; review baseline của15 lỗi ở báo cáo:12answering+1parity+2CRLF. Mỗi lỗi có disposition, không chỉ tăng tổng test xanh. Các DB/runtime cases tách tầng.

**G7:** execute bounded variants thật; source found/absence/unknown/ambiguity đúng; support/group selection/final completeness có source-reviewed labels và false-pass metrics; không hồi quy legacy, snapshot fence/stream errors đúng. G7 gold freeze gom owner duyệt theo §9.

## 8. Runtime và ngân sách — chuẩn bị sớm, chỉ gọi khi đủ quyền

Không tự chọn nguồn credentials hoặc target từ `.env` ambient. Đọc `docs/runbooks/agent-environment.md` + Feature Map + `ci.md`; harness application hiện dùng deterministic providers, không chứng minh V3 Cloudflare và không tự xử lý worker PDF/Turns. Runtime retrieval phải bổ sung worker/real paths theo T13, không đổi nhãn helper thành runtime.

Trước mỗi package, agy tự chọn/freeze **con số hữu hạn** theo Q2 trên tài nguyên đã được cấp và quota thực: raw bytes/pages/render pixels/tokens; max searches/variants/merged/rerank inputs; recovered pages/regions; max calls per route + retries + total token/call quota; concurrency≤3queries/1PDF; max corpus10kchunks cho production claim; CPU/RAM/disk/process/deadline; attempt count; cleanup/rollback ownership. Giá trị phải ghi cụ thể trong preflight artifact trước run, không dùng chữ “bounded” thay số và không chọn cap sau khi xem score.

- [ ] Validate account/model/endpoint/license/rights, source classification và $0 enforcement/quota remaining trước first call; chỉ tham số/quota đã có không cần hỏi lại owner. Thiếu quyền hoặc free-quota hard stop không thể chứng minh thì package chưa chạy, không tự trả phí.
- [ ] Dùng DB/collection/project/ports/output directory riêng, identity gắn đúng subject và reservation; không nối localhost bất kỳ vì test mặc định. Không dừng tiến trình hoặc cleanup volume của owner khác.
- [ ] Capture attempts/failures/usage của mọi run; quota cạn/deadline thì checkpoint, không retry vô hạn hoặc thay provider. Benchmark synthetic index riêng với semantic gold; không overclaim semantic quality.
- [ ] Chỉ dừng package phụ thuộc bị thiếu quyền/gold; tiếp tục code/tests offline, chuẩn bị reviewers/runbooks/other packages. Chỉ hỏi owner khi §9 áp dụng và gộp một packet có lựa chọn/ảnh hưởng.

## 9. S8, evidence thật và gói quyết định cho owner

### T13 — Rebuild hồ sơ nghiệm thu, runtime và runbook (F16/F17/F21)

**Files:** S8 `evals/datasets/pdf_retrieval_release_v1.py`, manifest/held-out source artifacts/approval owner, `evals/test/test_pdf_retrieval_release_dataset.py`; `scripts/run-runtime-verification.ps1`, `scripts/runtime_evidence.py`, `.github/workflows/runtime-verification.yml`, `backend/test/config/test_runtime_evidence.py`, actual `backend/runtime_test/test_retrieval_v3_recovery.py`; runtime tests per stage theo plan gốc; `docs/runbooks/retrieval-v3-release.md`. Reports mới theo run convention hiện có, không ghi đè lịch sử.

- [ ] Release loader phải dùng path/manifest/schema/hash/split/bindings thực, fail missing file/approval, duplicate IDs, contaminated split hay version mismatch. Không hardcode4samples; không thêm36cases giả để đủ con số40. Số cases được owner freeze theo protocol, report dùng đúng actual count/denominators.
- [ ] Ca đỏ loader missing path hiện có API:

```python
def test_release_loader_rejects_missing_artifact(tmp_path):
    import pytest
    from evals.datasets.pdf_retrieval_release_v1 import load_release_dataset
    with pytest.raises((FileNotFoundError, ValueError)):
        load_release_dataset(tmp_path / "missing.jsonl")
```

- [ ] Approval trỏ đúng source/gold artifact/hash/scope/reviewer và thời điểm trước scoring. Comment duyệt7plans không phải structure gold; S1 runtime binding không phải relevance judgments. Human owner phải xác nhận, không tự ghi “approved” hoặc ký thay. Giữ nguồn cũ, thêm superseding record có provenance.
- [ ] Thay profile unit-only bằng actual application/worker/DB/Qdrant + Cloudflare permitted routes: fresh PDF→canonical DB→projection→Turn→validated cited answer; text HTTP/CLI→index/query; backfill/checkpoint; 3modes; real source recovery; tenant/revoke/stale generations; archive/reprocess/outage/reconcile/rebuild/recovery. Fake unit tests vẫn ở local tier, không được nâng thành runtime evidence.
- [ ] Evidence validator reject helper-only report, missing source/config/image/tool identities, JUnit0/skip/fail/duplicate, wrongsubject và incomplete scenario set. Trace joins tới actual attempts/resources/generations. Pin đúng tested subject dù workflow source là main; PR head và synthetic checkout là các identity khác nhau.
- [ ] Recovery phải thử purge/rebuild/active snapshot và failure paths trên owned stack theo #150 authority. Không xóa source/backup/volume ngoài retention/approval; thiếu copy retention policy thì ghi deletion chưa hoàn tất. Qdrant outage/CF429/malformed/OCR timeout không giả absence hay fallback model.
- [ ] Runbook lấy IDs/lệnh từ actual CLI/parser/resolver. Kiểm `--help`/parser contracts offline trước viết; không dùng `--check-only`, `--mode hybrid` hay selectors không tồn tại. Pin modelcodeđangdùng, Phrase Boost evaluation-only. Chọn rollback selector có thật + expected serving state và thử rollback trên test stack.
- [ ] Tạo valid RC bằng full Git SHA có thật sau upstream fixes; freeze config/source/dataset/scorer/criteria/threshold/SLO hashes trước held-out. Chuẩn bị countersigned metric/gold packages và source permissions; không nhận RC hash không resolve hoặc aggregate không có raw captures.
- [ ] Run required CI đúng head, accepted G3–G7 regressions, matrix/ANN/held-out/workload/security/recovery/resource/cost gates. Nếu sửa code sau đo, tạo RC mới và đánh giá lại phần bị ảnh hưởng theo frozen protocol, không tune trên held-out đã xem hoặc loại failed cases.
- [ ] Review độc lập gói cuối. Với head đổi sau merge cần artifact→build/subject mapping và chạy lại gates bắt buộc. G8 RC đạt là sẵn sàng trình owner; không phải merged/deployed/IssueDone.

### Owner packets hữu hạn; không hỏi lắt nhắt

1. **G3 source/structure freeze:** annotations/raw hashes/rubric/coverage/denominators + đối chiếu cách diễn đạt page/chunk, phương án tuân ADR và tác động nếu strict1chunk/page; quyền nguồn nào còn thiếu. Chuẩn bị cả phương án và evidence trước gửi, không hỏi từng bbox/chunk.
2. **G4 development relevance freeze:** queries/universe/judgments/bindings/scorer protocol/hashes độc lập candidate và review record; có cách xử lý unjudged trước benchmark.
3. **G7 support/completeness freeze:** labels và taxonomy found/absence/unknown/ambiguity/false-supported/false-complete; public contract delta nếu thực sự cần, không hỏi lại Q6 đã chốt.
4. **G8 final packet:** held-out/gates/SLO/cost freeze trước run; sau run có exactRC/rawmetrics/CI/runtime/fault/rollback/review. Kèm approved-target proposal: deployment identity/ownership/credentials references không secrets, backup/rollback/observation/cutover commands và rủi ro. Owner nghiệm thu + lệnh merge/cutover riêng; nếu không đủ quyền chưa thực hiện.

Nếu thiếu quyền/data/resources không có trong session, gộp cùng packet gần nhất; ghi phần agy đã hoàn tất và tác động thiếu quyền. Không mặc định phải hỏi owner duyệt từng config/algorithm; không dùng im lặng làm approval. Nếu requirement Cloudflare/$0 không khả thi, trình số liệu/phương án trong ràng buộc, không tự bật local hoặc provider khác.

## 10. Gate đóng stage và merge tuần tự

| Gate | Hồ sơ bắt buộc trước chuyển stage |
|---|---|
|G3|page/source/completeness thật; persistence/reload2paths; limits; reviewed structure truth; CF/native feasibility; CI3.12+runtime đúng subject|
|G4|3modeapplication + PDF/text/backfill/dynamicstats; 200+200→100; denseidentity/configreadback; scorer/judgments valid; ANN/matrix/≤0.01quantizationtarget|
|G5|corpus snapshot/positions đúng; SDM numerical+calibration/lexicalmatrix; PhraseBoost chỉeval|
|G6|reranker actualinvocation+mapping/bilingualquality; boundedpool/MMR/evidence; safeDBSF+SDMfallback; hybridablation|
|G7|variants thực thi; groupfact support; sourcefound/absence/unknown; finalfacts/citations trướcstream/persist; legacyregressions; reviewedlabels|
|G8|upstreamaccepted; realRC+heldout+criteriafreeze; CIsubject/runtime/fault/resource/cost/rollback; owneracceptance và targetpackage|

Stage chưa đủ bằng chứng ghi đúng chưa đạt; không thay gate bằng số tests, không coi `not_run` làPASS. Agy có thể chuẩn bị phần độc lập phía sau khi chờ packet nhưng không tích hợp/release dựa vào upstream chưa nghiệm thu.

**Merge order:** #215→#216→#217→#218→#219→#220→#221. Kế hoạch này không cấp lệnh merge.

- Khi upstream sửa xong, sync từ branch gần nhất sang downstream, chạy manual CI trước merge để bắt lỗi sớm. Không cần merge để chứng minh từng fix.
- Chỉ sau owner ra lệnh merge: merge upstream, reconcile branch kế với main theo merge method thực tế, retarget về main, kiểm diff stage-only và full required PR CI/synthetic checkout. Không force-push/rebase shared branch hoặc tự xóa ancestry chỉ vì squash; nếu cần history rewrite, trình patch/history plan có ownership trước.
- Không đóng #153 tại “RC accepted”. Q1 còn approved deployment, rollout và post-deploy smoke/observation/rollback readiness. Merge/deploy phải có instruction cụ thể ở thời điểm đó.

## 11. Gói agy phải trả lại để review một lượt

- [ ] Bảng25F-IDs, mỗi ID có owning PR/head/commit, test trước-sau, evidence link và disposition. Không bỏP2; không tự waive invariant.
- [ ] Stage heads/base/upstream mapping, diff summaries và CI run IDs, actual selected/executed/pass/fail/skip counts. Tách Python3.12 compatibility khỏi local3.13.
- [ ] G3–G8 evidence matrix: required artifacts + hash + source/config/RC + rawattempt joins + review/approval record; missing/notrun giữ nguyên.
- [ ] Migration/backfill compatibility; fallback/rollback rehearsal; no-local-model/no-download/CF-only guards + observed quota/$0; source permissions và data retention limits.
- [ ] Bộ regression cuối: không còn15failures từ review trừ disposition có evidence được chấp thuận; affected tests meaningful và full required CI đúng head. Không đưa DB connection-refused sơ bộ vào codefailcount.
- [ ] Owner packet duy nhất cho việc thực sự còn chờ; progress thường lệ ở #153/PR. Nếu chưa đủ runtime/quyền/gold, ghi chính xác phase hoàn tất và yêu cầu còn thiếu, không gọi Done.

**Điểm dừng của lần giao này:** agy sửa + kiểm chứng trong quyền hiện hữu, chuẩn bị PRs/gates/cutover packet và trả review; chỉ tiếp tục merge/deploy khi có lệnh trực tiếp. Codex phiên soạn dừng tại bàn giao, không chạy implementation song song.

## 12. R2 — Delta bắt buộc sau review remediation, giao Anti đến nghiệm thu

Mục này bổ sung các ca còn sót cho T0–T13, thay thế inventory và điểm dừng cũ khi mâu thuẫn; các yêu cầu kỹ thuật, bảo mật và gate ở §1–§11 vẫn áp dụng. Không triển khai lại các phần đã PASS. Không sửa hồi tố phê duyệt, gold hoặc reports cũ. R2 là kế hoạch thực thi, không là sổ tiến độ; kết quả thực ở #153/PR.

### 12.1 Nhận việc, phiên bản và ranh giới quyền

Snapshot sau review ngày22/10/2026; Anti phải refresh trước ghi:

| PR | Subject đã review/test | Thay đổi quan sát cuối review |
|---|---|---|
|215|9fb3111d0c731802a645e1bdbdde45f5649308d1 local|Đã MERGED; GitHub head trước merge4f441a76c3f0d3c7968420d8a48bc08d2fe889cf, merge ada17099050030fe527227fce0f2956539a2892f|
|216|5a9ff2bb6f6779116105a9d4ee71318cb621a994|Remote54a77d4d280539620fdfca1e9e8d71398e950e70 sau merge main; CI đang chạy tại snapshot|
|217|b880915b53054f619dfe5ccd679d7711274a4975|Chưa có CI required tại snapshot|
|218|31f483d954c6bdce9472dd84883581bf5efbdf07|Chưa có CI required tại snapshot|
|219|fce76051e6286ce7e8274055c08b7089f4782faa|Chưa có CI required tại snapshot|
|220|cad488c704197a3f97a364ea2d4abdab83f8c970|Chưa có CI required tại snapshot|
|221|2d36bc83fe59b9b4f9759e302e69e9eee9dc2c89|Chưa có CI required tại snapshot|

Diff5a9ff2bb→54a77d4d chỉ test/config/docs, không đổi source Retrieval V3 hoặc migration. Không gán CI/test của5a cho54a. Worktree từng stage dùng đúng bảng §2; docs R2 ở worktree riêng nêu đầu tài liệu, không lấy `docs-retrieval-v3-plans` đã merge làm nhánh tiếp tục mặc định. Không thao tác primary dù nó đã chuyển về main. Người giao đang chỉ soạn tài liệu; Anti nhận writer tại các stage sau xác nhận phiên cũ đã checkpoint/nhường quyền.

- [ ] Ghi root/branch/status/worktree list, remote head/base/state, approval reference và delta từ subject review. Nếu có thay đổi mới, xác minh finding bằng code + ca tái hiện trước áp patch; không lùi SHA hoặc reset để khớp bảng.
- [ ] Đọc review mới và probe JSON/script trong bàn giao. Mười finding đã PASS: **F01,F04,F06,F07,F09,F10,F15,F19,F20,F22**. Mười lăm finding còn mở: **F02,F03,F05,F08,F11,F12,F13,F14,F16,F17,F18,F21,F23,F24,F25**, thêm **N01**. Đủ26 IDs cần disposition cuối.
- [ ] Ghi chú mới ở #153/PR rằng G3–G8 chưa nghiệm thu, liên kết review/R2 và giữ report cũ. Bỏ closing keyword `Closes #153` ở #220; thay bằng `Refs #153` và cập nhật claims sai trong body #221 theo quyền Q7, không đóng Issue.
- [ ] Sửa T0–T13 tại stage sớm nhất; commit riêng theo hành vi, push đúng PR trong quyền Q7. Chuẩn bị docs R2 từ branch riêng nếu cần nhập main; #215 đã merge nên không push để kỳ vọng sửa PR đã đóng. Không tự mở rộng quyền publish/merge/deploy hoặc gửi yêu cầu cho người/agent ngoài quyền Q7 đã có.

### 12.2 Pha A — N01 trước, sau đó đóng 15 finding tại đúng owner

#### R0 — Đồng bộ migration S3 xuống toàn stack (N01/P1; mở rộng T1)

**Files:** S3/S4–S8 `backend/migrations/versions/20261022_0158_canonical_document_structure.py`, migration canonical cũ `20261022_0157_canonical_document_structure.py` nếu vẫn tồn tại, `20261021_0157_text_search_parent_link.py`; tests cấu hình migration đang có và DB upgrade trên DB disposable. Đối chiếu tên thực tế ở mỗi stage trước sửa.

- [ ] Trước merge upstream, ghi DAG migration từng branch. S3 phải có `20261022_0158`, down_revision=`20261022_0157`; S4–S8 hiện còn hai heads `20261021_0157`/`20261022_0157`.
- [ ] Merge latest S3 vào S4, resolve rename/ancestry đúng mục đích, rồi S4→S5→S6→S7→S8. Giữ sửa dataclass. Không thêm dummy merge revision để che duplicate DDL, không sửa migration đã chạy tại target có thật; nếu có target như vậy, inventory revision và chuẩn bị forward-compatible migration trước thay đổi.
- [ ] Kiểm tất cả sáu DAG bằng lệnh offline sau, ở từng worktree; kỳ vọng đúng một head và không mất revision kế thừa:

```powershell
& ./.venv/Scripts/python.exe -c "from alembic.script import ScriptDirectory; s=ScriptDirectory('backend/migrations'); print(s.get_heads()); assert len(s.get_heads()) == 1"
```

- [ ] Trên DB test riêng: upgrade từ base migration đã được stage hỗ trợ và từ current main lên head, kiểm columns/constraints/structure round-trip, replay upgrade không duplicate DDL; dùng database CI hiện hữu. Không chạy upgrade/downgrade trên DB người dùng để kiểm.

**Đạt:** một head ở mỗi stage, schema đúng, DB test/CI đạt và mapping upstream commits rõ; source S4–S8 không còn migration fork cũ. Nếu chưa có quyền DB thì đóng phần DAG/code riêng, DB verification vẫn chưa đạt.

#### R1 — PDF conversion, physical source và giới hạn (F02/F03/F24; T2–T4)

**Files:** S3 `providers/cloudflare/pdf_understanding.py`, `adapters/pdf/docling.py`, helper `adapters/pdf/pypdf.py`, `_pypdf_process.py`, `_pypdf_limits.py` nếu tái sử dụng; `ingestion/pdf_structure.py`. Paths source đều dưới `backend/src/knora/`. Tests hiện có: `backend/test/providers/cloudflare/test_cloudflare_pdf_understanding.py`, `backend/test/adapters/pdf/test_docling.py`, `backend/test/ingestion/test_pdf_structure.py` và owning PostgreSQL finalize/reload tests.

- [ ] F02: giữ wire đã sửa, thêm ca HTTP200/outer success nhưng `result[0].format='error'`; phải trả conversion/provider error có phân loại, không biến thành text rỗng/PDF_TEXT_INSUFFICIENT. Kiểm file identity/count, schema/data type, format và error trước dùng data. Không nhận malformed response bằng fallback permissive.
- [ ] F03: PDF native2trang vẫn ra2physical pages. PDF không phân giải được physical structure không được đổi thành page1/complete=true từ Markdown. Tiled scans phải render toàn trang hoặc tất cả regions có coverage kiểm chứng; mixed page không bỏ ảnh chỉ vì có vài ký tự native. Dựng CanonicalTable/cells/spans từ nguồn thực, không bịa layout từ text.
- [ ] Offsets lấy từ chính canonical page text và delimiter thực. Thêm ca `First paragraph.\n\n\nSecond paragraph.`, CRLF, nhiều khoảng trắng và blank page: mỗi block phải bằng `page.text[start:end]`; không dùng `end+2` mặc định.
- [ ] F24: cấu hình stream cap1byte phải từ chối content stream lớn hơn1byte trước parse sâu. Cưỡng chế max raw/page/total stream, memory, render pixels/OCR regions và whole-operation deadline; worker/process bị dừng và cleanup khi quá giới hạn. Reuse bounded parser helpers; không chỉ tăng HTTP timeout.
- [ ] Tests phải mô phỏng hoặc tạo PDF hợp lệ để kiểm từng nguyên nhân riêng, không lấy malformed EOF thay resource-limit test. Integration kiểm nguồn/table/block offsets + JSON persistence/reload ở cả dense và extraction-only. Tiếp tục native/no-AI và Cloudflare-only OCR theo Q3.

**Đạt:** toàn bộ ca phản ví dụ bị chặn đúng lỗi, source anchors và completeness có chứng cứ, G3 gold review/DB/runtime theo §9–§10. F04/F20 giữ regression, không làm lại S2.

#### R2 — Composition, Cloudflare guard và vector projection (F05/F11/F23/F25; T5–T7)

**Files:** S4 `main.py`, `bootstrap.py`, `infrastructure/lexical_configuration.py`, `adapters/cli/reindex_search.py`, `ingestion/search_indexing.py`, `adapters/postgres/search_index_store.py`, `adapters/qdrant/search_index.py`, `adapters/qdrant/native_search_index.py`. Tests: `backend/test/test_bootstrap.py`, `test_main_lifecycle.py`, `backend/test/answering/test_dense_hybrid_contract.py`, `backend/test/adapters/qdrant/test_search_index.py`, `test_native_search_index.py`; ingestion/PG/CLI integration owners của T5/T6.

- [ ] F11: dùng selector có thẩm quyền `cloudflare-workers-ai` thống nhất guard/factory/resolver. Test valid Cloudflare pair với fake credentials và mocked client phải build được, chưa network; non-CF neural provider bị từ chối trước request. Deterministic test double được cô lập offline, không coi là neural inference hoặc bằng chứng runtime Q3.
- [ ] F05: bỏ phụ thuộc finite S2 population khi bật V3 dynamic. Nối actual index/embedding configuration/lexical profile/statistics từ HTTP, CLI, PDF worker, backfill tới AnswerQuestion. Không tạo profile giả avg_len=256/digest0 hoặc đổi tên thành corpus-dynamic để vượt guard. Snapshot/profile lấy từ PG đúng corpus membership, activation/CAS và serving state.
- [ ] Application tests phải đi qua bootstrap/main, không chỉ dựng use case bằng tay: fresh text/PDF, backfill checkpoint, ba mode, add/archive/reprocess/switch; BM25 không query-embed, dense/hybrid bind đúng model/config/dims. CF-only $0 và quyền nguồn là precondition cho phần live, không cấm backend/Qdrant/scoring local không model.
- [ ] F23: pin exact completed active Embedding Set, Chunk Set/configuration và vector coverage vào manifest/generation/readback receipt. Dense/hybrid stage thiếu vector phải lỗi trước activation; sparse-only không bị ép có vector. Readback chứng minh identity/dimensions/coverage/vector content theo digest manifest có thể xác minh; không dùng label profile hay with_vector=false một mình làm chứng cứ vector đã lưu.
- [ ] Thêm missing vector, partial vectors, same-dimension/wrong-model, wrong-set, altered vector/digest, stale pointer và cross-tenant cases. PG authority được revalidate trước query/receipt/activation; Qdrant payload không quyết định nguồn/quyền.
- [ ] F25: effective collection readback bắt buộc đúng float32/Cosine/HNSW/on-disk và quantization TurboQuant bits4/always_ram đã pin. Missing quantization và scalar int8 phải lỗi khi yêu cầu TurboQuant; float32 comparator dùng policy riêng có thật. Thêm hai ca đỏ đã tái hiện, cùng query rescore/oversampling checks; không chấp nhận `bits=None`.
- [ ] Model ID trong config/runbook/manifest phải đúng provider support và quality evidence. F06 đã sửa payload BGE-base, chưa chứng minh BGE-M3. Không đổi label profile hoặc reuse vectors để gọi nó là M3; Q2 cho phép chọn Cloudflare model phù hợp qua benchmark trong ràng buộc Việt–Anh, model/dims mới tạo immutable profile và derivation đúng chuẩn.

**Đạt:** composition3modes thật, no bogus profile, fail-closed vector/collection, regression F06/F07/F19 và G4 matrix/ANN/CI. Sửa được guard không thay quota/$0 evidence.

#### R3 — SDM không tính từ Top-K (F08; T8)

**Files:** S5 `answering/module.py`, `ingestion/lexical_population.py`, PG statistics producer/reader trong `adapters/postgres/search_index_store.py` và activation owner. Tests `backend/test/ingestion/test_corpus_statistics.py`, `backend/test/answering/test_dense_hybrid_contract.py` và PG snapshot tests.

- [ ] Dùng CorpusStatisticsSnapshot có authoritative PG membership/revision, tokenization và positions cùng phiên bản với serving generation. Snapshot được sản xuất/cập nhật trên transitions, pin vào stage/query; cache key đầy đủ, không chỉ workspace + một digest không kiểm nguồn.
- [ ] Thiếu/lỗi/sai snapshot phải trả operational/degraded status theo fallback đã duyệt, không tự đếm `candidates` rồi gắn digest hợp lệ và `sdm.status=completed`. Không bỏ kiểm tra chỉ vì scorer nhận đúng type.
- [ ] Test tập3Top-K từ corpus lớn hơn3: scorer dùng toàn corpus snapshot; thay thành Top-K khác không đổi corpus counts. Thiếu snapshot/store exception/digest/tokenizer/membership mismatch phải không gọi scorer bằng stats tự chế. Kiểm archive/reprocess làm invalidation đúng và PG reload có cùng snapshot.

**Đạt:** không còn Top-K frequency fallback, numeric tests/calibration/comparator và G5 có nguồn stats truy vết. S6 chỉ regression F09/F10, thêm live bilingual/fallback quality cho G6 khi đủ preflight; không viết lại provider đã sửa.

#### R4 — Query execution, source recovery và factual answer (F12/F13/F14/F18; T10–T12)

**Files:** S7 `answering/query_planning.py`, `query_results.py`, `evidence_support.py`, `source_verification.py`, `generation_validation.py`, `module.py`, `stores.py`, authorized PG source reader. Tests: `backend/test/answering/test_query_plan_models.py`, `test_query_results.py`, `test_evidence_support.py`, `test_source_verification.py`, `test_answer_group_completeness.py`, `test_module.py`, `test_question_stream_answering.py`; context/parity và source-reader integration theo T11/T12.

- [ ] F12: từ câu `So sánh thời hạn đổi trả Chương 2 và Chương 5, kèm AUTH_403 và AUTH_404`, giữ đủ predicate, số, đơn vị, phủ định và required facts theo nhóm; không chỉ tạo hai câu `Thông tin quy định về ...`. Không chia identifier sai nhóm hoặc biến mọi global identifier thành constraint mỗi nhóm.
- [ ] Hai nguồn chỉ nói đồng phục, dù đúng heading, phải không support câu đổi trả/mã lỗi. Positive có đúng source facts phải support; C2/C20,14/140, AUTH_403/AUTH_404 và negation mismatch phải được tách. Boundary regex là regression, không là toàn bộ support oracle.
- [ ] F18: actual AnswerQuestion thực thi plan variants/subquestions, dùng shared authorized scope/snapshot, merge bằng helper đã cap; spy store xác nhận số searches, query texts, provenance và tổng pool≤100. Query ngắn `chuong2 quy dinh thoi han bao hanh san pham` phải có typo/accent strategy có kiểm chứng, không fast-path bỏ qua mặc định. Không sửa identifier hoặc tăng call budget vô hạn.
- [ ] F13: không gọi hybrid retrieval với query_vector/config=None. Dùng authorized lexical locator/source reader phù hợp, đọc đúng canonical source/version/page và completeness. Nối recovery cả single missing intent và multi-group, repair evidence rồi recheck; empty/duplicate lookup vẫn unverified. Thêm application test qua PostgresAnsweringStore, không chỉ fake store trả sẵn recovered chunks.
- [ ] Ma trận Q6: Top-K thiếuC5 nhưng nguồn có→find/read/answer/cite; nguồn đầy đủ thật không cóC5→verified_absent kèm checked scope; nguồn partial/OCR/quota/deadline/revoke/lookup exception→unverified hoặc operational error; nhiều nguồn cùngC5 chưa xác định→ambiguity. Không lộ nguồn không có quyền.
- [ ] F14: bỏ heuristic năm từ làm bằng chứng đủ ý; gắn required fact/group→answer span→source span/citation. Với evidence C2=7ngày, C5=miễnphí: câu `Chương 2 và Chương 5, đây chỉ là phần giới thiệu tổng quan chung. [[E1]] [[E2]]` phải bị từ chối; câu `Chương 2: 7 ngày [[E1]]. Chương 5: miễn phí [[E2]].` phải được nhận. Thêm đúng facts/sai cite, sai số, thiếu một nhóm và paraphrase đúng; không chỉ blacklist đúng chuỗi probe.
- [ ] Semantic assessor nếu cần theo Q2 chỉ Cloudflare, có schema/version/budget/unknown; không import gold vào runtime, không lấy claim map do cùng generator tự khai làm oracle. Validation trước answer bytes SSE và persist, legacy/context flows opt-in đúng version. Kiểm F15/F22 và toàn callers bị tác động.

**Đạt:** ca false-supported/false-complete và false-reject đã tái hiện đều được sửa, query thực thi thật, tra nguồn đúng Q6, G7 reviewed labels/application/runtime đạt. Không dùng vài unit tests để suy tất cả câu trả lời đều đúng.

#### R5 — Dataset, runtime, report và runbook có bằng chứng (F16/F17/F21; T13)

**Files:** S8 `evals/datasets/pdf_retrieval_release_v1.py`, dataset/manifest owner, `evals/test/test_pdf_retrieval_release_dataset.py`; `scripts/run-runtime-verification.ps1`, `scripts/runtime_evidence.py`, `.github/workflows/runtime-verification.yml`; `backend/test/config/test_runtime_evidence.py`, `backend/runtime_test/test_retrieval_v3_recovery.py`; `docs/runbooks/retrieval-v3-release.md`. Dùng convention reports hiện có cho record mới, không ghi đè lịch sử.

- [ ] F16: production/release loader bắt buộc artifact path + manifest/split/schema/hash/source/version và phê duyệt đúng dataset, không dùng4hardcoded examples làm held-out. Missing/default artifact, duplicate, hash/split/source mismatch, approval chỉ trỏ homepage hoặc7planfreeze phải fail. Nếu giữ examples, đặt rõ fixture-only và không cho release selector nhận chúng.
- [ ] Chuẩn bị source/gold thật, số cases và denominator từ artifact thực; không bù36cases giả hoặc gọi4cases là40. Gold không lấy output candidate làm truth. Phê duyệt trước scoring, held-out không tune; thiếu freeze ghi chưa đạt. Report mới ghi rõ supersedes claim cũ nào, raw captures/metrics/attempts/subject và approval bindings.
- [ ] F17: runtime profile chạy owned application + PDF worker + PostgreSQL + Qdrant + approved Cloudflare routes, actual lifecycle/state assertions. Dời helper/fake-store checks về contract tier nếu cần; validator không cấp runtime PASS cho helper-only/JUnit0/skip/scenario missing hoặc wrongsubject.
- [ ] Runtime bắt buộc: fresh PDF/text/CLI/backfill, ba modes, query variants/facts/cites, Q6found/absence/unknown, archive/revoke/stale generation, CF429/malformed/timeout, Qdrant outage, controlled derived-index loss/rebuild từ PG/retained sources, activation/reconcile và rollback. “Purge” chỉ trên dữ liệu/collection disposable của package theo retention/ownership được phép, không thử xóa nguồn thật.
- [ ] F21: runbook command/model/profile/KNORA env names lấy từ parser/resolver/config thực; dùng đúng `--dry-run` và `retrieval-hybrid-rerank-top8-v3`. Rollback phải phục vụ corpus động hiện hành trên safe configuration/generation đã thử, không dùng finite47 S2 manifest hoặc vectors khác model. Đồng bộ candidate cap100, model thật, workflow SHA/subject SHA, quota/backup/observation/rollback triggers cụ thể.
- [ ] Rerun full affected contract/CI/runtime/matrices trên final RC sau upstream fixes; không nâng report sau đổi code mà giữ captures cũ. ANN diagnostic và semantic dataset có denominator riêng; quota/observability failure không được đổi thành no-answer. Giữ failed attempts và deterministic audit trail.

**Đạt:** artifact thật và reviewed freeze, runtime thật/recovery có before-after evidence, runbook chạy được trên owned test stack, G8 đạt cùng upstream. “Runtime runner gọi đúng tên test” chưa đủ.

### 12.3 Pha B — Đóng gates bằng chứng trên đúng subject

Mỗi R-task: reproduce ca đỏ đã nêu → sửa root cause/callers → ca xanh + regression → review diff → commit stage → sync downstream → kiểm layer cần thiết. Không dừng sau khi chỉ code xanh; chuẩn bị sớm dataset/gold/resources của gate tiếp theo. Nếu chờ quyền, tiếp tục phần độc lập đã được phép.

| Gate | Bắt buộc bổ sung R2 | Regression phải giữ |
|---|---|---|
|G3|R0/R1; physical/table/coverage/offset/resource, hai finalize paths và reloadPG; reviewed structure truth + runtime|F01/F04/F20; Python3.12 CI|
|G4|R0/R2; 3modes dynamic cho PDF/text/backfill; exact embedding/collection identity; source-reviewed ranking/ANN/matrix theo frozen plan|F06/F07/F19, BM25 query-embedding0, legacy/S2 contracts|
|G5|R3; immutable PG corpus snapshot, transitions/cache and positional/calibration/PhraseBoost comparator|numerical SDM + lexical matrix|
|G6|Upstream G3–G5; actual Cloudflare bilingual reranker/evidence, timeout/malformed fallback và ablation|F09/F10 lifecycle/schema; max100/evidence budget|
|G7|R4; variants execute, fact preservation/support, Q6source recovery, final factual answer before stream|F15/F22; answering/context/parity; negative authz/source fences|
|G8|R5 + G3–G7; held-out/criteria/RC freeze, full CI/runtime/fault/rebuild/rollback/resource/$0 evidence, independent review|all26finding disposition + original full release matrices|

**Environment/import gate:** không coi `.venv` ở đúng thư mục là đủ. Trước pytest pin PYTHONPATH và assert `knora.__file__`, hoặc dùng checkout guard mới trên main; giữ bằng chứng import và Python version trong log. Ví dụ ở stage đang làm:

```powershell
$stageRoot = (git rev-parse --show-toplevel).Trim()
$env:PYTHONPATH = "$stageRoot/backend/src;$stageRoot"
$env:PYTHONDONTWRITEBYTECODE = '1'
& ./.venv/Scripts/python.exe -c "import pathlib,knora; expected=pathlib.Path('backend/src/knora/__init__.py').resolve(); print(knora.__file__); assert pathlib.Path(knora.__file__).resolve()==expected"
if ($LASTEXITCODE -ne 0) { throw 'Wrong checkout imported' }
```

Chạy các selections chỉ rõ ở R1–R5, rồi affected answering/context/parity/provider/evals và full required CI theo runbook. DB/runtime selections chỉ trên owned resources. Ruff format/check và shared/frontend/OpenAPI checks nếu chạm đúng bề mặt. Không chạy lại optional suites sau khi đã đủ chứng cứ, trừ để giải quyết rủi ro cụ thể hoặc required gate.

**Bằng chứng review đầu vào, không tái sử dụng như run mới:** S8 Python3.13.15 có491 core +77 eval/evidence tests đạt; S3 pinned5a có31 tests đạt; đây là599 lượt, không599testsduynhất. S3 CI3.12 xanh tại5a; không suy sang remote54a hoặc S4–S8. Probe không network tái hiện failures. Anti phải tạo evidence mới cho code mình sửa, gồm cả không còn false-reject câu trả lời ngắn đúng nguồn.

### 12.4 Pha C — Gói quyền, freeze và nghiệm thu đến hết Q1

**Chuẩn bị ngay ở R0, không để đến cuối mới hỏi:** kiểm quyền hiện có trong Issue/PR/runbook/approved package, source public/synthetic, free account/quota hard stop, target/runtime ownership và gold approver. Không kế thừa runtime envelope/credential/expiry của #158/#192; không reset clock cũ nếu cùng package đã được duyệt. Nếu không có approval package, không tự ghi là đã có.

- [ ] Trước mỗi live package, Anti freeze artifact có số cụ thể: bytes/pages/stream/render pixels/memory/deadline; variants/searches/recovery pages/merged cap/rerank inputs; calls/tokens/retries/attempts theo từng route và toàn package; concurrency, disk/output/cleanup ownership. Workload vẫn tối đa3queries/1PDF/10kchunks, phí0USD. Không chọn giới hạn sau khi thấy score, không dùng từ “bounded” thay con số.
- [ ] Ghi approval timestamp/expiry nếu có, package start/end deadline, run/attempt ID, counters tiêu hao và usage còn lại. Final runtime/held-out không auto-retry; lỗi giữ evidence, sửa code tạo RC/package mới trong quyền có thật, không tự reset attempts/quota/approval. Hết quyền/quota/clock chỉ dừng phần phụ thuộc, checkpoint và tiếp tục offline được phép.
- [ ] **Gói owner sớm:** gom source/structure G3, relevance G4, support/completeness G7 thành một gói nếu đã chuẩn bị đủ; kèm artifact hashes, source quyền, rubric/labels/denominators và phương án ADR0007. Nếu các freeze phụ thuộc chưa sẵn, không ký trước nhãn chưa được review. Không hỏi từng case/chunk, không hỏi lại Q3/Q6.
- [ ] **Gói trước held-out:** RC/config/dataset/scorer/criteria/SLO/workload/cost freeze và live resource/quota envelope. Anti tự chọn kỹ thuật/finite bounds theo Q2; chỉ đưa owner phần cần gold approval, quyền chưa có hoặc thay tiêu chí. Không bịa numeric quality threshold còn chưa được duyệt; dùng frozen thresholds sẵn có, phần chưa có chuẩn bị đề xuất dựa development evidence trước chạy held-out.
- [ ] **Gói nghiệm thu/cutover cuối:** bảng26IDs với source/test/CI/runtime/review, G3–G8, exact RC/build/base/merge mapping, raw captures và usage, target/credentials ownership references không secrets, backup/restore, migration/backfill, quantitative triggers/observation và lệnh cutover/rollback đã rehearsal. Owner xem một gói cụ thể; không chỉ thông báo “xin quyền deploy” khi chưa chuẩn bị.

ADR0007: sửa ngay mô tả sai “1trang=1chunk” trong runbook thành quy tắc page-bounded hiện có, ghi rõ correction không đổi chunking policy. Đưa yêu cầu strict1chunk/page còn mâu thuẫn vào gói sớm; chỉ thực hiện policy đổi nghĩa khi owner chốt, không bỏ token cap hoặc coi ambiguity đã được duyệt. Các fix physical anchors/coverage không phải chờ quyết định này.

**Thứ tự merge sau lệnh trực tiếp của owner:** #215 đã merge → #216 → #217 → #218 → #219 → #220 → #221. Trước từng bước, sync upstream/main, retarget đúng base khi phù hợp, kiểm stage-only diff và full required CI của merge candidate; source SHA đổi thì map/rerun gates bị tác động. Không tự bật auto-merge hoặc force-push shared history. R2 docs branch nếu chưa nhập thì chuẩn bị diff/PR riêng trong quyền publish, không merge lén vào stage code để thay authority.

**Anti giữ nhiệm vụ đến nghiệm thu:** không kết thúc việc vì đã push hoặc CI xanh. Khi chạm human gate, trả đúng một packet với việc đã xong, việc còn chờ, quyết định cần owner, phương án khuyến nghị và lệnh tiếp tục; chờ trả lời cho phần phụ thuộc. Sau lệnh merge/cutover rõ ràng, tiếp tục cùng kế hoạch, kiểm đúng deployed build/config/generation, smoke PDF/text/query/recovery/authz và observation/rollback readiness. Chỉ đề nghị đóng #153 sau Q1 deployed + post-deploy acceptance; thiếu target/approval là chưa hoàn tất, không đổi scope thành RC-only.

### 12.5 Checklist bàn giao và tự kiểm kế hoạch

- [ ] Một bảng cuối trong #153/PR có26IDs: finding, owner stage/commit, test đỏ/xanh, CI run+subject, runtime/gold/review disposition;15old+N01 đều đóng bằng evidence hoặc ghi rõ chưa đạt, không waive P2/invariant.
- [ ] Report mới không ghi G3–G8PASS nếu thiếu source/gold/CI/runtime tương ứng; lịch sử cũ giữ nguyên và được supersede rõ. No skipped/error/timeout/unverified làPASS.
- [ ] Mọi phần đã PASS chỉ regression; F01 dataclass không apply lại, F20 không đổi frozen bytes, F06 không gọi BGE-base làBGE-M3, không làm lại S2.
- [ ] Chuỗi migration/corpus statistics/vector/source coverage có owner và downstream propagation; tests gọi application seams, không chỉ helpers hoặc self-report.
- [ ] Boundary quyền dữ liệu/tenant/source-version, secrets, Cloudflare/$0, no-local-weights, rollback và cleanup được kiểm ở các paths bị sửa. Report tách implemented/local/CI/runtime/review/accepted/merged/deployed.
- [ ] Tiến độ, approvals và bước tiếp theo ở Issue/PR; không biến plan/handoff thành ledger mới. Codex phiên soạn chỉ bàn giao; không implement hoặc chạy provider/runtime song song với Anti.

## 13. R3 — Xử lý các điểm chưa đạt sau review độc lập R2

### 13.1 Phạm vi hiện hành và điều kiện nhận việc

Nguồn chi tiết và phản ví dụ: `C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-r2-independent-code-review-20261023.md`; probes offline: `retrieval_v3_r2_review_probes_20261023.py` và `.json` cùng thư mục. Probes là đầu vào tái hiện, không phải gold và không thay application tests. Hai JSON pins `retrieval-v3-r2-review-20261023-local-pins.json` và `retrieval-v3-r2-review-20261023-github.json` là snapshot review, không phải bằng chứng HEAD hiện hành sau khi Anti nhận việc.

| Owner sửa đầu tiên | PR / worktree dưới root ở §2 | HEAD đã review | Mục phải sửa |
|---|---|---|---|
| S3 | #216 / feat-retrieval-v3-document-understanding | ab4a6fc777d6ba973c6bf8c166f4443af4865ef0 | F02(P2), F03(P1), F24(P2), R2-N02(P1) |
| S4 | #217 / feat-retrieval-v3-dense-hybrid-search | 309597c55d31d534ee93a66f89b850de44f3a1e9 | F05(P1), F23(P2) |
| S5 | #218 / feat-retrieval-v3-sequential-dependence-ranking | 87e26df8608a6ed66185af1ea17d632e0df652b3 | F08(P2) |
| S6 | #219 / feat-retrieval-v3-reranking-evidence | a82f81ab187b793646f20e73c14c2c347e4cee4d | R2-N03(P2) |
| S7 | #220 / feat-retrieval-v3-query-understanding-coverage | 0fff1edd96ed3ac3fa856f5f4242cdee343c81e5 | F12(P1), F13(P1), F14(P1), F18(P2) |
| S8 | #221 / feat-retrieval-v3-integrated-release | fbed98e0dad80b86a773b74bcb856b7bed9f85b4 | F16(P1), F17(P1), F21(P2) |

**13 mục giữ regression:** N01, F01, F04, F06, F07, F09, F10, F11, F15, F19, F20, F22, F25. Đây là PASS về lỗi cụ thể với giới hạn trong review; G3–G8 đều chưa đạt. Bảng nghiệm thu cuối phải có **28IDs = N01 + F01–F25 + R2-N02 + R2-N03**. ID theo report, không gán lại theo tên stage trong prompt cũ.

- [ ] **R3-0 — Intake:** đọc review, §1/§12/§13 và bảy plan đóng băng; xác nhận branch, root, clean/dirty, PR base/head/ancestry và quyền sở hữu từng worktree trước ghi. HEAD lệch thì kiểm diff/CI mới và cập nhật mapping trong PR; không reset về pins cũ hoặc đè thay đổi của phiên khác. Chỉ hỏi phần thiếu quyền/đụng owner, tiếp tục đọc và phần độc lập.
- [ ] Tái hiện ca đỏ bằng đúng checkout guard §12.3; ghi Python/import path/command/exit code. Dùng môi trường hiện có, không tự cài tool hay mượn dịch vụ. CI phải có Python3.12; kết quả local3.13 không thay nó. Không sửa gold để khớp output candidate.
- [ ] Kiểm tra sớm các gói §12.4: target disposable/ownership, dữ liệu public/synthetic, quyền cloud/free quota và gold approver. Chuẩn bị source/gold/criteria/resources cụ thể trong khi sửa offline; gom một packet cho mỗi phụ thuộc thực sự cần owner, không hỏi lại Q3/Q6 hoặc từng tham số Q2.
- [ ] Tất cả R3-1→R3-6 theo chu trình: ca đỏ → sửa owner/callers/fixtures → ca xanh và ca đúng không bị từ chối → review → commit PR owner → truyền upstream xuống các nhánh sau, giải quyết conflict theo semantics → kiểm lại. Không vá riêng S8, không force-push hoặc chuyển nhánh worktree của người khác. Có thể chuẩn bị dataset/approval sớm, nhưng final runtime/held-out chỉ chạy sau freeze RC.

### 13.2 R3-1 — S3: profile, coverage, envelope và giới hạn tài nguyên

**Sửa tại #216 trước; truyền xuống #217–#221.** Files chính: `backend/src/knora/adapters/pdf/docling.py`, `providers/cloudflare/pdf_understanding.py`, `main.py`, `ingestion/jobs.py`, `ingestion/pdf.py`, `ingestion/job_processing.py` dưới cùng `backend/src/knora/`; các owner `adapters/postgres/ingestion_jobs/submission.py`, `coordination.py` và resolver/profile đang có. Không tạo subsystem profile thứ hai.

- [ ] **R2-N02 trước:** Docling có cấu hình/ID có version riêng, từ submission → persisted parser/chunker identity → resolver → worker → extraction result/finalization. Không dùng ID `pypdf-layout` cho nội dung Docling; không chỉ đổi nhãn đầu ra. Cùng raw PDF giữ DocumentVersion nhưng tạo ChunkSet mới đúng derivation; cache/legacy references vẫn immutable. Ca âm: resolver không biết profile, worker trả sai identity, cache pypdf cũ không được nhận là Docling. Nếu cần migration additive, giữ đồ thị hợp lệ và tương thích dữ liệu cũ.
- [ ] **F02:** kiểm toàn Cloudflare envelope trước sử dụng: success/errors, kiểu `data`, cardinality/tên artifact đúng request, format và content type hợp lệ; chặn dict thay list, tên khác, dư/thiếu file, `format:error`, nội dung sai kiểu. Mỗi ca trả lỗi provider có kiểu đúng hợp đồng, không rơi `.strip()` ngoài hợp đồng. Ca dương: response thật hợp lệ được parse giữ provenance/source map.
- [ ] **F03:** text header + scanned body không được COMPLETE khi chỉ đọc header; OCR phải bao phủ mixed regions/physical page và mọi tiles cần thiết, không chỉ `images[0]`. Tạo canonical table/cells và source spans thực; heading/bbox/coverage không được suy nhãn COMPLETE từ vài chuỗi Markdown. Không xác minh đủ thì incomplete/operational đúng loại. Kiểm native, scanned, mixed, tiled, table multi-cell và page/source offsets; cấm cross-page chunk, giữ token policy ADR0007 ở §1.
- [ ] **F24:** deadline và memory phải được cưỡng chế bằng isolation/cancellation seam sẵn có, gồm native parsing/render/OCR stages và cleanup. Ca đỏ 1ms budget/native50ms hiện vẫn success phải hết; thêm worker timeout/memory exhaustion không leak process/file và không finalize COMPLETE. Không mang miễn trừ giới hạn S2 sang Docling; số cụ thể chọn/freeze theo §12.4, không chỉ thêm trường config không thực thi.
- [ ] Tests: bổ sung vào `backend/test/adapters/pdf/test_docling.py`, `backend/test/providers/cloudflare/test_cloudflare_pdf_understanding.py`, `backend/test/ingestion/test_pdf_structure.py`, `test_pdf_chunking.py`, `test_pdf_job_processing.py`; profile submission/resolver và hai finalization paths có ca application-level. Với PG được phép, chứng minh reload canonical structure/identity, mismatch rejection và legacy nonmutation. Không dùng DB có dữ liệu để chạy fixture phá hủy.

**Lệnh offline tối thiểu ở S3 sau checkout guard:** `python -m pytest backend/test/adapters/pdf/test_docling.py backend/test/providers/cloudflare/test_cloudflare_pdf_understanding.py backend/test/ingestion/test_pdf_structure.py backend/test/ingestion/test_pdf_chunking.py backend/test/ingestion/test_pdf_job_processing.py`. Chạy thêm selections profile/resolver/finalization đã thay đổi; ghi rõ node IDs và kết quả. **Điều kiện ra bước:** bốn mục không còn phản ví dụ, identity xuyên luồng đúng, F01/F04/F20 không hồi quy; G3 vẫn cần source truth/PG/runtime và CI3.12.

### 13.3 R3-2 — S4: corpus động thực và tính toàn vẹn vector

**Sửa tại #217; truyền xuống #218–#221.** Files chính dưới `backend/src/knora/`: `main.py`, `infrastructure/lexical_configuration.py`, `adapters/cli/reindex_search.py`, ingestion module/jobs/job_processing/search_indexing/lexical_population, PG search_index_store/lexical_retrieval/answering_store, Qdrant search_index/native_search_index. Dùng profile/generation và ingestion seams hiện có.

- [ ] **F05:** create_app phải tạo index hợp lệ cho ba modes V3 dù không có finite S2 population; producer phục vụ text/PDF ingest, backfill/reindex và activation từ corpus động. CLI thực có đường nhận/chọn profile đúng, `load_profile` không ValueError ở cấu hình được runbook hỗ trợ. Không phục hồi dummy/frozen profile hoặc giả index chỉ để bootstrap qua.
- [ ] Đường dương qua HTTP và CLI thật: fresh text/PDF → jobs → PG canonical chunks/embeddings/statistics → projection receipts → activation → query BM25-only/dense-only/hybrid. Archive/reprocess/reload giữ membership/generation đúng. BM25-only có0 query embedding calls, candidate merge tối đa100 và V3 Cloudflare guard không hồi quy.
- [ ] **F23:** pin immutable embedding-set/configuration/generation/dimension và expected vector contents/digest từ PG; readback kiểm vectors thực lưu ở Qdrant, không chỉ payload hay `with_vector=False`. Ca đỏ altered vector `9.0` đủ768dimensions, missing vector, sai set/model cùng chiều, mixed sets, thiếu active configuration và receipt tampering phải chặn activation/serving. Không chọn set bằng UUID descending rồi gắn config của query lên set khác. Receipt ràng buộc chính corpus/vector/collection/config đã kiểm.
- [ ] Thêm integration tests ở các test modules tương ứng PG/Qdrant/CLI/main/ingestion đang có; mocks chỉ kiểm hợp đồng, server readback thật thuộc G4/G8. Giữ N01/F06/F07/F11/F19/F25: không đổi BGE-base thành BGE-M3 trên giấy, không lược Recall/MRR, không hạ bits4 thành scalar int8.

**Lệnh offline ở S4:** `python -m pytest backend/test/test_main_lifecycle.py backend/test/adapters/cli/test_reindex_search.py backend/test/adapters/qdrant/test_native_search_index.py backend/test/adapters/qdrant/test_dense_search_index.py backend/test/ingestion/test_search_indexing.py backend/test/ingestion/test_lexical_population.py`. Thêm PG selection `backend/test/adapters/postgres/test_text_search_indexing.py` và tests identity/readback sau khi kiểm fixture/target có quyền; ghi nguyên commands trong PR. Chạy CLI `--help`/`--dry-run` theo parser thực; backfill thật chỉ trên target được phép. **Điều kiện ra bước:** ba modes đi qua application seams, identity/vector corruption bị chặn; G4 còn cần actual ANN trên corpus eligible>200, exact filtered comparator và matrix bits4 nDCG drop≤0.01 theo frozen plan, không dùng helper top200 làm ANN.

### 13.4 R3-3 — S5: CorpusStatisticsSnapshot có thẩm quyền

**Sửa tại #218; truyền xuống #219–#221.** Files chính: `backend/src/knora/answering/module.py`, `sequential_dependence.py`, `ingestion/lexical_population.py`, PG search_index_store/answering_store và activation/cache owners đang có.

- [ ] **F08:** SDM chỉ nhận snapshot đã persist ở PG, bắt buộc identity/digest/tokenizer/revision/membership đúng serving generation/profile; thiếu digest phải fail trước scoring, không chấp nhận chỉ vì đúng Python type. Reader phải kiểm actual membership/frequencies tương ứng, không đếm active chunks rồi tự gắn profile digest.
- [ ] Producer/update/invalidation nằm trong lifecycle ingest/activate/archive/reprocess/reload. Cache key và invalidation đủ identity; nhiều process không dùng snapshot cũ sau serving switch. Không tính corpus frequencies từ Top-K, không thêm kho statistics có thẩm quyền ngoài PG.
- [ ] Tests tại modules SDM/corpus statistics và PG lifecycle hiện hữu: None/wrong digest, sai tokenizer/membership/revision, pool3 so với100 cùng snapshot cho background statistics như nhau, archive/reprocess/switch/reload/multiworker không stale. Ca dương numerical SDM và calibration matrix đúng; Phrase Boost chỉ eval comparator. PG integration chỉ trên target được phép.

**Lệnh offline ở S5:** `python -m pytest backend/test/answering/test_sequential_dependence.py backend/test/ingestion/test_corpus_statistics.py backend/test/ingestion/test_lexical_population.py`. Sau khi kiểm fixture/target có quyền, chạy `python -m pytest backend/test/adapters/postgres/test_corpus_statistics_transition.py` và lifecycle selections bị tác động; lưu expected numerical values, không chỉ assert completed. **Điều kiện ra bước:** không score thiếu authority/snapshot match, transitions đúng và upstream regressions xanh; G5 cần numerical/positional/calibration matrix đầy đủ trên snapshot được pin.

### 13.5 R3-4 — S6: thu thập test bằng cấu hình CI mặc định

**Sửa tại #219; truyền xuống #220–#221.** **R2-N03:** `backend/test/answering/test_reranking.py` trùng basename `backend/test/providers/cloudflare/test_reranking.py`; pytest mặc định prepend gây `import file mismatch`, kể cả khi CI deselect test sau collection.

- [ ] Đổi provider test thành `backend/test/providers/cloudflare/test_cloudflare_reranking.py`, theo convention đã có ở S8; cập nhật mọi selection/runner/docs tham chiếu, không đổi import mode toàn repo chỉ để che lỗi. S8 có answering suite khác: preserve phần rename và MMR coverage khi sync, không chép đè bằng S6 cũ.
- [ ] Tái hiện bằng `python -m pytest --collect-only backend/test/answering/test_reranking.py backend/test/providers/cloudflare/test_reranking.py` trước sửa; sau sửa dùng tên thực mới trong cùng default invocation và CI partition của runbook. Không thêm `--import-mode=importlib` để gọi là đã sửa.
- [ ] Sau sửa tại S6 chạy `python -m pytest --collect-only backend/test/answering/test_reranking.py backend/test/providers/cloudflare/test_cloudflare_reranking.py`, rồi cùng command bỏ `--collect-only`. Ở downstream dùng tên thực đã có, kiểm lại collection với CI flags mặc định.
- [ ] Chạy cả provider và answering suites; giữ F09/F10 ID/lifecycle/result.response/remap/error fallback, DBSF+SDM thứ tự, pool≤100, MMR evidence≤5chunks/3000tokens. Giữ ca malformed/timeout/429/duplicate/out-of-range/nonfinite. Không viết lại provider đã đạt nếu không có lỗi mới.

**Điều kiện ra bước:** collection và tests bằng flags CI mặc định đạt trên S6, S7, S8; G6 vẫn cần Cloudflare rerank Việt–Anh, fallback ablation/quality và resource/quota evidence thật, không suy từ31tests offline.

### 13.6 R3-5 — S7: facts theo ý, variants thực thi, tra nguồn và kiểm answer

**Sửa tại #220; truyền xuống #221.** Files chính dưới `backend/src/knora/answering/`: `module.py`, `query_planning.py`, `query_correction.py`, `query_results.py`, `evidence_support.py`, `source_verification.py`, `generation_validation.py`, `stores.py`; nối PG authorized canonical source reader. Kiểm callers ở conversations/context và generation/stream/persist khi thay hợp đồng; giữ V3 opt-in và legacy behavior.

- [ ] **F12:** tách predicate/fact/number/unit/negation/identifier theo đúng nhóm ý nghĩa, chỉ chia sẻ predicate thật sự chung. Ca dương `Chương2 đổi trả7ngày / Chương5 giảm20%` được support bởi hai nguồn đúng; AUTH_403/AUTH_404 không bị sao chép sang cả hai nhóm. C2 khác C20; sai nhóm, sai số/đơn vị/phủ định bị loại. Giữ exact boundaries và atomic subquestions.
- [ ] **F18:** AnswerQuestion thực thi correction/decomposition/multi-query theo policy V3, không chỉ tạo helper variants. Spy ở application store chứng minh variant được search, dùng cùng authoritative snapshot, fair merge/dedup/provenance, cap toàn pool100 kể cả append recovery. Clear query giữ fast path; không gọi model/retry ngầm. Tự chốt số variants/subqueries/calls/deadline hữu hạn từ development evidence theo Q2 và freeze trước live, không bịa cap4 từ prompt; cap2 chỉ là ca F22.
- [ ] **F13:** recovery áp dụng cả single/multi intent; BM25-only recovery dùng đúng hợp đồng, sau đó đọc canonical source/catalog có quyền, đúng document/version/sections/pages và completeness. Có facts thì repair evidence → answer/cite; chỉ verified_absent khi kiểm đủ toàn scope được phép. Không catalog/partial OCR/quota/deadline/reader failure → unverified hoặc operational đúng loại; Top-K empty không thành absence. Ambiguity đi Conversation; revoke/version switch ở reader và trước delivery không lộ nguồn cũ.
- [ ] **F14:** kiểm độc lập required fact → answer span → cited source span trước SSE answer bytes và persist. Với E1=`C2 đổi trả7ngày`, E2=`C5 miễn phí vận chuyển`: answer70ngày/E1, đảo citation E1/E2 và câu không có facts nhưng chứa từ khóa đều phải bị từ chối; answer ngắn đúng và paraphrase đúng phải được nhận. Không vá blacklist filler hoặc lấy generator tự xác nhận/gold làm truth runtime. Nếu cần model support/completeness, chỉ Cloudflare qua seam hiện hữu với schema/version/budget và unknown handling; không tạo judge framework song song hay cho model confidence làm oracle.
- [ ] Tests tích hợp planner/support/source verification/query results/completeness/module/stream/persist/conversations hiện có phải cover positive+negative, authz/version và quota/errors; riêng S7 tên planner là `backend/test/answering/test_query_planning.py`, S8 đã đổi thành `test_query_plan_models.py`. Không dùng selections của S8 rồi nói S7 đã được kiểm.

**Lệnh offline ở S7:** `python -m pytest backend/test/answering/test_query_planning.py backend/test/answering/test_query_correction.py backend/test/answering/test_query_results.py backend/test/answering/test_evidence_support.py backend/test/answering/test_source_verification.py backend/test/answering/test_generation_validation.py backend/test/answering/test_answer_group_completeness.py backend/test/answering/test_module.py backend/test/conversations/test_context.py`. Thêm stream/persist/parity/provider selections tương ứng callers đã sửa; mock spies chứng minh thực thi nhưng không thay semantic gate. **Điều kiện ra bước:** bốn mục hết phản ví dụ qua AnswerQuestion, F15/F22 và legacy không hồi quy; G7 còn cần source-reviewed independent labels và false-accept/false-reject matrix trên policy đã freeze.

### 13.7 R3-6 — S8: held-out, runtime thật, runbook và bằng chứng cuối

**Sửa tại #221 sau khi nhận upstream; chuẩn bị quyền/gold sớm từ R3-0.** Files chính: `evals/datasets/pdf_retrieval_release_v1.py`, JSONL/manifest/approval owners, `evals/test/test_pdf_retrieval_release_dataset.py`; `scripts/run-runtime-verification.ps1`, `scripts/runtime_evidence.py`, `.github/workflows/runtime-verification.yml`, `backend/runtime_test/`, `docs/runbooks/retrieval-v3-release.md`; report mới theo convention đã có.

- [ ] **F16:** loader/runner bắt buộc path thực + schema/version/split/source/manifest/count/hash và phê duyệt ràng buộc đúng artifact, không chỉ tính SHA hoặc đọc3strings trong test. Missing metadata/split/approval, wrong hash/count/source/version, duplicates, wrong manifest và fallback hardcoded4cases đều fail release admission. Fixture examples không được làm held-out. Dùng quy trình gold đang có; không tạo36cases giả cho đủ40, không lấy output candidate sửa gold, không gọi freeze bảy plan là duyệt dataset mới. Nếu thiếu duyệt, chuẩn bị gói cụ thể và dừng scoring phụ thuộc, tiếp tục offline.
- [ ] **F17 — contract failures trước:** sửa fixtures dense/hybrid thiếu `active_embedding_configuration_id` trong các runtime contract tests, phù hợp schema authority mới và thêm negative mismatch. Không xóa assertions hoặc lọc chỉ `ann_recall/decoy` để bỏ hai ca đang fail. Tách rõ helper/contract từ journey dịch vụ; cả hai tầng phải có selections/counters trung thực.
- [ ] **F17 — runtime:** runner chuẩn bị/kiểm ownership/readiness của application+PDF worker+PG+Qdrant trên target được phép; fresh PDF/text và ba modes qua luồng thật. ANN đo actual approximate query đối chiếu exact cùng eligible population/filter; bits4 dùng vectors/collection server thật, không lấy exact top200 giả ANN hay tự tạo gold top15. Đo đầy đủ matrices G3–G8 theo frozen plans, gồm workload3queries/1PDF/10kchunks, raw latency/resources/$0 counters và rerank/fallback quality.
- [ ] Runtime journeys có captures: source reload/activate, Q6found/absence/unknown, variants và facts/citations, archive/revoke/stale generation, controlled429/malformed/network timeout, Qdrant outage, derived collection loss/rebuild từ PG/retained source, reconcile/fencing và rollback. Fault injection được phép là công cụ gây lỗi có kiểm soát; không gọi kết quả fake-store là recovery thật. Không xóa canonical sources hoặc resource không thuộc package. Cleanup có receipts cho resource mình tạo.
- [ ] **F21:** runbook lấy env `KNORA_...`, model/profile/retrieval IDs, flags và cap từ resolver/parser thực; phân biệt branch prefetch200 và merged final100. Không ghi BGE-M3 nếu profile chạy BGE-base. Rollback phục vụ corpus động hiện hành bằng config/generation tương thích đã rehearsal, không dùng finite47 V1; lệnh `--dry-run`, checkpoint/resume, backfill, backup/restore và quantitative rollback triggers chạy được. Sửa diễn đạt page-bounded theo ADR0007, không đổi policy ngầm.
- [ ] Báo cáo mới ghi rõ supersede claims RC cũ/50counts/unsupported metrics nào; giữ lịch sử, ghi denominator từ artifacts thật, failed attempts và not_run. Không tái sử dụng captures trước code/subject/config đổi. Sửa code sau freeze → tạo RC mới, map/rerun phần bằng chứng bị ảnh hưởng theo quyền/quota còn lại, không tự reset attempts hoặc lén tune held-out.

**Kiểm:** `python -m pytest evals/test/test_pdf_retrieval_release_dataset.py backend/test/config/test_runtime_evidence.py` sau checkout guard; chạy đầy đủ runtime contract selections và real runtime runner bằng flags hiện hành trong `--help`, trên package được phép. Không in secrets hoặc credential values. **Điều kiện ra bước:** artifacts/gold/criteria/resource freeze thật, runner/validator không cấp PASS cho skip/empty/wrongsubject/helper-only, journeys/matrices/runbook có raw captures kiểm lại được và independent review không còn lỗi chặn.

### 13.8 Cổng kiểm chứng, giao trả và quyền nghiệm thu

| Gate | Điều kiện bổ sung bắt buộc R3 trước PASS |
|---|---|
| G3 | R3-1; Docling derivation identity end-to-end, mixed/tiled/table/source coverage, enforced memory/deadline, hai PG finalize/reload paths, reviewed structure truth, Python3.12 CI |
| G4 | R3-2; ba modes dynamic qua HTTP/CLI/jobs, vector corruption/identity readback thật, actual ANN/exact filtered + quantization/ranking matrices, N01/F06/F07/F11/F19/F25 regressions |
| G5 | R3-3; persisted authoritative snapshot và transitions/cache/multiworker, numerical/positional/calibration matrices, Phrase Boost chỉ comparator |
| G6 | R3-4; default CI collection ở owner/downstream, actual Cloudflare bilingual reranking/evidence+fallback ablation, max100/evidence5/3000 và quota/resource proof |
| G7 | R3-5; per-group facts, variants executed, authorized canonical source recovery cả single/multi, Q6, final answer/source/citation alignment trước stream/persist, independent semantic labels+matrix |
| G8 | R3-6 và G3–G7; approved held-out/criteria/config/RC freeze, full CI/runtime/fault/rebuild/rollback/$0 evidence, đủ28IDs và independent review; chưa gồm quyền merge/deploy tự động |

> 🧠 **From Hindsight memory (Conventions and patterns)** — Workflow source SHA và tested subject SHA được ghi riêng; đã đối chiếu lại yêu cầu này trong runbook CI hiện hành. Không kế thừa quyền runtime từ một run lịch sử.

- [ ] **CI từng stage:** snapshot review chỉ #216 có `CI required SUCCESS`; Sourcery SKIPPED của #217–#221 không phải full CI. Dùng workflow_dispatch đang có trong `.github/workflows/ci.yml` trên branch đúng nếu quyền publication/CI cho phép; kiểm full required jobs và SHA thực chạy. Trước merge vẫn cần gate của merge candidate/retarget theo runbook, không coi manual run cũ là bằng chứng mọi merge candidate. Workflow source SHA và tested subject SHA ghi riêng theo runbook CI; checkout/import guard áp dụng cả local lẫn workflow.
- [ ] **Migration:** snapshot S3 một head `20261022_0158`; S4–S8 một head `20261021_0157` nối sau0158. Không sửa lịch sử chỉ để mọi stage in cùng tên head. Kiểm một head hợp lệ trên từng subject, cùng đường nâng cấp theo stack; migration/reload thật trên DB được phép trước G8, giữ canonical data và rollback plan.
- [ ] **Bất biến:** Cloudflare-only/$0/no local weights; PG authority và Qdrant derived/rebuildable; Workspace/version fences; ADR0007 page-bounded/token caps; giữ frozen bytes/approvals/source gold/S2; không dùng private #146 ở cloud. Dependency import/startup paths không tải weights hoặc local inference. Model-free parsing/tokenization/test doubles được tách khỏi AI-quality evidence.
- [ ] Sau mỗi code delta chạy scoped red/green/regression rồi Ruff format/check theo AGENTS; shared/frontend/generated checks khi chạm đúng surface. Trước kết luận dùng verification-before-completion, đọc logs/counters/artifact hashes thay vì chỉ exit summary. Không chạy thêm optional suites khi đã đủ bằng chứng, trừ required gate/rủi ro cụ thể.
- [ ] **Giao trả:** trong #153/PR được phép có đủ28IDs, mỗi dòng owner commit/ca đỏ-ca xanh/local checks/CI run+subject/runtime+raw captures/gold binding/review disposition; ma trận G3–G8 và trạng thái đã sửa code, local, CI, runtime, quality, reviewed, accepted, merged, deployed riêng. 13mục regression không tự chứng minh gate. Thiếu quyền, skipped, unknown, chưa duyệt hoặc thiếu capture ghi chưa đạt, không PASS có điều kiện.
- [ ] Independent review lại final subject/stack và từng stage-only diff; mọi P1/P2 trên15mục mở phải đóng hoặc nêu chưa đạt để owner quyết định thực sự, không tự waive. Giữ các ca đúng concise/paraphrase cùng ca sai số/cite để tránh chỉ giảm false accept bằng cách từ chối mọi câu.
- [ ] Anti tiếp tục theo nhiệm vụ đến nghiệm thu, không kết thúc ở push/CI. Nếu cần owner, gom packet đã chuẩn bị theo §12.4: việc xong, phần phụ thuộc, artifacts/hash, lựa chọn khuyến nghị, quyền/quota/gold/tiêu chí cần chốt và bước tiếp tục. Không hỏi lại decisions Q3/Q6; không đợi approval để làm phần độc lập đã được giao.
- [ ] Chỉ sau lệnh trực tiếp hiện hành của owner mới merge #216→#217→#218→#219→#220→#221 (#215 đã merge), rồi cutover/deploy trong quyền cụ thể và post-deploy acceptance Q1. CI xanh không tự cấp quyền merge/deploy hoặc đóng #153. Nếu chưa có lệnh/target/quyền, giao gói sẵn sàng review và ghi rõ phần còn chờ, không gọi Done toàn Issue.

## 14. R4 — Thiết kế và kế hoạch đóng các điểm chưa đạt sau R3

> **ĐỀ XUẤT CHỜ DUYỆT.** Dành cho Anti: sau khi owner duyệt đúng revision, dùng `executing-plans`; thực hiện các checkbox theo dependency, tự kiểm và giao review độc lập. Không tự tạo subagents cho implementation; riêng reviewer gold được ủy quyền ở D7 là vai trò độc lập, không là quyền sửa worktree của người khác. Không coi R4 đã được duyệt chỉ vì file này được commit.

### 14.0 Đầu vào, phạm vi và baseline

Nguồn đầu vào: [review độc lập R3](C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-r3-independent-code-review-20261023.md), [probe gốc chạy lại](C:/Users/NhiBuaa/AppData/Local/Temp/retrieval_v3_r3_independent_probes_20261023.json), [probe bổ sung](C:/Users/NhiBuaa/AppData/Local/Temp/retrieval_v3_r3_additional_review_probes_20261023.py) và JSON cùng tên. Probes không phải gold. Trước thực thi, đưa ca đỏ cần giữ vào test owner thích hợp, không để acceptance phụ thuộc duy nhất vào Temp.

Ngày24/10/2026 đã xác minh lại local=GitHub,6worktree sạch, PRs OPEN với base đúng stack:

| Owner | HEAD đầy đủ | Cần sửa | Regression đã PASS |
|---|---|---|---|
| S3/#216 | d67da5b0c0984dfdd5a3a266dfe4d3a74735d300 | F03(P1),F24(P2) | F01,F02,F04,F20,R2-N02 |
| S4/#217 | 4939137f58ff8ddcaead072ceb6f4faa0a129630 | F05(P1),F23(P2) | N01,F06,F07,F11,F19,F25 |
| S5/#218 | 91543e0ac29275a201f9944a3bd96557aaad9487 | F08(P2) | Numerical/positional/legacy ranking contracts |
| S6/#219 | 3f63d3fc9c303dd061cbff38b63457bd9b586aa8 | Không mở lại provider đã sửa | F09,F10,R2-N03 |
| S7/#220 | bfa8f65ec9d8a0e4d92ae4d6b54a8749a76899b7 | F13(P1),F14(P1),F18(P2),R3-N04(P1) | F12,F15,F22 |
| S8/#221 | 2e87d304bd290b715d395e092437277464a28bfc | F16(P1),F17(P1),F21(P2) | All upstream contracts |

17PASS là disposition lỗi cụ thể, không phải G3–G8. Review trước có966lượt test pass với trùng lặp; CI#216/run39963932354 và #221/run39966308918 đạt, S8 ci-subject checkout_sha khớp. Những số này là baseline lịch sử, không làm bằng chứng R4 mới. #215 đã merge; không sửa bảy plan đóng băng. R4 là phần bổ sung; tất cả29IDs phải có disposition, không làm lại S2.

### 14.1 Nghiên cứu, phương án và lựa chọn đề xuất

**Nguồn hiện hành:** ADR0004/0007/0017/0019, source ở các HEAD trên, CodeGraph S8 current/pending0 và đối chiếu owner source trực tiếp. Không coi graph S8 thay bằng chứng owner; owner S3–S5 chưa có map tại research snapshot. Trước sửa code làm CodeGraph theo AGENTS đúng root. Các note chi tiết chỉ là research scratch; kế hoạch/thẩm quyền vẫn ở tài liệu này:

- [PDF/resource research](C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-pdf-remediation-design-research-20261024.md).
- [Corpus/vector/statistics research](C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-authority-remediation-design-research-20261024.md).
- [Source recovery/answer research](C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-answer-remediation-design-research-20261024.md).

| Vấn đề | Phương án so sánh | Chọn và đánh đổi |
|---|---|---|
| Native layout/table | Tự viết geometry bằng pypdf; pdfplumber/PDFium không model; local Docling ML | Chọn native geometry + Cloudflare OCR. Thêm dependency có lock; không chạy local ML. Adapter hiện tại dùng pypdf, không được gọi là native Docling layout. |
| Resource | Cooperative elapsed/RSS; supervisor process hiện hữu; limiter mới | Dùng chung supervisor ADR0004; hard-limit trước start, bounded IPC và kill/join. Đổi private transport hẹp, giữ pypdf public behavior. |
| Dynamic corpus | Dummy/frozen profile; re-extract toàn corpus mỗi lần; PG snapshot + canonical reindex | Chọn snapshot + job engine hiện hữu. Thêm schema/operation V3, tránh lặp OCR/embedding không cần; staging có thể tạm unavailable khi quyền/source đổi. |
| Vector receipt | Hash payload Qdrant; raw-byte PG equality; PG expected + versioned float32/Cosine comparator | Chọn comparator từ authority PG. Phải xử lý normalization/rounding; không dùng epsilon rộng tùy ý để pass. |
| Answer correctness | Keyword overlap; chỉ trích nguyên văn; verifier Cloudflare riêng | Chọn deterministic boundary checks +1verifier riêng; giữ paraphrase. Thêm latency/quota và lỗi model tương quan; không có cam kết đúng tuyệt đối. |
| Release evidence | Helper suites; stack/runners hiện có mở rộng journeys | Chọn stack thực với captures cùng RC. Không thêm nền tảng eval/observability khác. |

Nguồn primary quyết định thiết kế:

1. [pypdf extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html): text visitor không phải table/OCR engine, có caveat coordinates/memory. [pdfplumber source/README](https://github.com/jsvine/pdfplumber/blob/stable/README.md) có chars/words/table geometry và PDFium render; phù hợp PDF máy sinh, không hứa tự giải đúng mọi scan/bảng.
2. [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html): dùng hard OS limits/owned process tree hiện hữu; không thay bằng timer trong cùng parser process.
3. [Qdrant Cosine](https://qdrant.tech/documentation/faq/qdrant-fundamentals/), [vectors/datatype](https://qdrant.tech/documentation/manage-data/vectors/), [pinned v1.19.2 OpenAPI](https://raw.githubusercontent.com/qdrant/qdrant/v1.19.2/docs/redoc/master/openapi.json), [Cosine implementation](https://raw.githubusercontent.com/qdrant/qdrant/v1.19.2/lib/segment/src/spaces/simple.rs): server normalize vector, float32 semantics; query quantization params/IDF corpus scope phải theo pinned wire schema.
4. [Cloudflare PDF conversion](https://developers.cloudflare.com/workers-ai/features/markdown-conversion/how-it-works/): Markdown không tự chứng minh physical page/cell source map. [JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/) không bảo đảm đáp ứng schema ở mọi tình huống, không streaming; [20B model page](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/) có response_format nhưng danh sách generic chưa thống nhất, phải kiểm exact-model contract.
5. [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) và [errors](https://developers.cloudflare.com/workers-ai/platform/errors/): Free10.000neurons/ngày, reset00:00UTC; Paid có overage. Khai cost=0 không chặn billing; $0 đòi account/route/limit evidence thực.

> 🧠 **From Hindsight memory (Issue158 incremental DeepEval Ragas Langfuse evaluation)** — #153 sở hữu source/gold/PDF projection; #158 sở hữu tích hợp evaluation tools, không tạo hệ thống chuẩn thứ hai. Đã đối chiếu quyết định này trong Issue#153 §12.4 và frozen S8 plan; R4 chỉ nối vào các seams có thẩm quyền đó, không nhận trạng thái cũ của #158 là trạng thái live.

### 14.2 Gói quyết định duyệt một lần D1–D8

Đây là **delta xin duyệt**, chưa có approval. Một lời duyệt đầy đủ ở §14.7 cấp quyền cho Anti thực hiện nội bộ mà không xin lại từng file/tham số. Q3/Q6 giữ nguyên; các lựa chọn sau thay câu chữ hoặc bổ sung cơ chế mà R3 chưa chốt:

| ID | Quyết định đề xuất | Giới hạn và quyền tự quyết sau duyệt |
|---|---|---|
| D1 | Dùng native geometry pdfplumber/PDFium + Cloudflare OCR/vision, thay việc coi adapter mang tên Docling là đã có Docling layout | Đây là delta engine của S3; giữ toàn bộ yêu cầu layout/table/source fidelity và pypdf legacy, không đổi tên requirement để PASS. Candidate pdfplumber0.11.10 đã tra; Anti chọn exact compatible transitive pins/hashes qua Windows/Linux CI. Không host installer, local weights hay model library. |
| D2 | Dùng supervisor process ADR0004 cho native/render/assembly, absolute deadline cả OCR/conversion | Giữ25MiB raw,500pages,4MiB/page stream,64MiB total stream,60s,512MiB; thêm4M pixels/render,64M pixels/job. Child/output cleanup phải kiểm thật. Không hỗ trợ hard-limit thì typed failure, không unbounded fallback. ADR0007 chuẩn hóa page-bounded, target500/overlap75/max650; không một-chunk-mỗi-trang. |
| D3 | Thêm PG immutable corpus snapshot/head và operation V3 `corpus_reindex` qua job engine hiện hữu | S4 owns additive migration sau head hiện hành; parent chạy thật từ canonical PG, mỗi parent mới1indexchild, giữ S2 semantics. Không fake dense succeeded, không Redis/queue mới. Native tokenizer upstream counter được promote với source/license/reproducible WASI build+Node runner pin trong app image/toolchain; không Temp dependency/network download lúc request. |
| D4 | Version mới cho query/source/answer support; cùng snapshot cho toàn request; max8searches/4required groups | Không truncate mất ý; group thứ5 đi clarification. Nqueries=Nreturned vectors. Giữ200+200→100, evidence5/3000tokens, inner cap2. Source recovery1pass, tối đa4docs/1024chunks/2MiB/8batches/10s; metadata catalog cap10.000members, partial luôn unverified. |
| D5 | Giữ1answer-generation call hiện hành, thêm tối đa1verification-only call Cloudflare cùng model20B cho V3 ANSWER | Explicit amendment call budget; không selector/second answer/rewrite/regeneration. Verifier15s,8192input tokens,2048output tokens,32statements; question pipeline absolute90s gồm mọi phase. Một batch;0retry; REFUSAL không gọi verifier. Legacy v21 bytes/schema không đổi, đổi bytes phải version và finite shared-owner ACK. |
| D6 | Anti được tạo/chạy/cleanup disposable verification stack trong namespace riêng, tải/build app dependencies/images đã khai báo; Cloudflare chỉ nguồn public/synthetic và $0 hard stop | Reuse launcher/reservation/CI/run evidence; cho phép wipe/reset **chỉ resources tạo mới trong package đã ghi ownership**. Không localhost/DB có dữ liệu khác, không chiếm port/kill session khác. Credentials chỉ qua loader backend hiện hữu, không log; chỉ gọi khi xác minh Free account/no paid route. Paid/unknown plan hoặc paid-only model → không dispatch. |
| D7 | Ủy quyền các vai trò độc lập ở §14.6A: người soạn nguồn/gold, người duyệt nguồn/gold, người chạy held-out và người review code/evidence; thay yêu cầu owner ký từng freeze S3/S4/S7/S8 | Delta Q5 cần owner đồng ý rõ. Anti được giao các vai trò này cho agent/session riêng, có identity và context riêng; người sửa candidate không kiêm soạn/duyệt/chạy held-out, người soạn không tự duyệt gold. Quyền ghi chỉ artifact mới trong namespace được giao theo §14.6A, không sửa code hoặc gold lịch sử. Không giả human approval hay khả năng cách ly dữ liệu chưa kiểm. Owner vẫn nghiệm thu RC và ra lệnh merge/cutover cuối. Nếu không duyệt D7, gom việc duyệt gold và quyền reviewer vào một packet cho owner trước held-out. |
| D8 | Giao Anti chọn pins/numerical implementation và freeze protocol trước scoring; chấp thuận các sàn chất lượng đề xuất ở §14.6A, quy trình nâng snapshot ở §14.3B và điều phối phụ thuộc ở §14.6D; được commit/push các PR owner, dispatch CI và cập nhật #153/PR đúng scope | Sàn tuyệt đối không được derive xuống theo baseline yếu. Không tự hạ gates, mua dịch vụ, bật provider khác, sửa frozen gold/S2, triển khai thay #148/#150/#158, merge/deploy/đóng Issue. Chỉ hỏi lại khi có scope/quyền mới, xung đột owner hoặc phương án không khả thi có bằng chứng; dừng đúng phần phụ thuộc và tiếp tục phần độc lập. |

**Không hứa một lần giao là mọi lỗi kỹ thuật đều biến mất.** Mục tiêu là không dừng xin lại quyết định đã nằm trong D1–D8. Runtime/gold chưa tồn tại không được ghi đã duyệt; D7 là ủy quyền quy trình tương lai, không phải phê duyệt nhãn chưa đọc. Đổi requirement/cost/permission vẫn cần owner; các thao tác merge/deploy cuối phải dựa gói kết quả thực.

### 14.3 Hợp đồng thiết kế xuyên stage

Tên dưới là **giao diện đích đề xuất**, chưa tồn tại hết ở HEAD. Giữ tên hiện có nếu trách nhiệm/signature tương đương; không tạo wrapper chỉ để giống plan. Application ports thuộc ingestion/answering; ORM/network adapter chỉ ở adapters/composition. ADR0004/0017/0019 và seams được cập nhật đúng delta sau duyệt, không tạo authority song song.

#### A. PDF regions và resource supervisor

- Child parse/render xuất private bounded region DTO: physical_page, region_id, source_sha, coordinate-space/crop/rotation, origin, text, offsets, optional bbox/table/cells/confidence, expected/processed region coverage. Không nhận page/source identity từ model tự khai.
- Native chars/table cells lấy geometry thật. Scanned/mixed/tiled render **composed visible region/page**, không OCR từng XObject mù thứ tự. Mọi crop có source hash/page/bbox/request identity; response không có tọa độ chỉ có crop-level anchor. Structured vision tables phải schema/grid/crop-bound valid và qua source truth; không bịa cell bbox từ Markdown hoặc model confidence1.0.
- Assemble theo reading order và cursor offsets ngay lúc append; không tìm lại repeated strings bằng find(). Native/OCR giữ origin riêng; confidence không có để None. Serializer/from_dict/PG round-trip giữ fields mới; incomplete không activate hay dùng để verified_absent. OCR đúng ngữ nghĩa là quality metric riêng với coverage.
- Bounded copy/hash → spawn → hard OS limit → handshake start → parse/render stages → Cloudflare với remaining deadline/budget → bounded assembly/result → parent reject late success → kill/join/close/unlink. Dùng shared supervisor `_pypdf_process.py`, không supervisor thứ hai. Parent-origin network I/O cũng nhận remaining timeout,0retry; không có dispatch sau cancellation. Remote request đã gửi không thể hứa hủy billing; giữ usage reservation khi local timeout.
- Windows Job KILL_ON_JOB_CLOSE + memory limit; Linux delegated cgroup memory.max + RLIMIT_AS lớp phụ và parent-death/owned-tree cleanup được kiểm. Không có delegation không chạy unbounded. Không kill theo tên/PID chưa xác minh.

#### B. Corpus snapshot, producer và atomic activation

- S4 thêm `lexical_corpus_snapshots` (workspace/policy/revision, base_active_snapshot, immutable manifest/schema/membership/statistics/profile digests) và `lexical_corpus_heads` (workspace+policy PK, desired/active snapshot, monotonic corpus revision). Pin Workspace/document revisions riêng với corpus revision. Manifest members dùng document/version/chunk-set/chunk-ID+ordinal/checksum; **không dedupe theo source SHA** hoặc text checksum.
- Manifest có version rõ: **v1 do S4 tạo** chứa membership, native BM25 counts/tokenizer evidence/avg_len/profile; **v2 do S5 tạo** bổ sung SDM tokenizer/scorer-policy, full-corpus frequencies/token totals và digests. Không để SDM placeholder rồi điền vào snapshot đã publish. Không dùng tiktoken chunk counts hoặc regex approximate làm native BM25 parity. Promote counter upstream source/license/build/hash từ native parity; Node WASI đóng gói model-free, bounded process, không toolchain service mới. Không dựng statistics từ Top-K hoặc gắn profile digest lên newly counted chunks.
- Nâng S4→S5 bằng durable transition mới, cause `statistics_schema_upgrade`, ghi `base_active_snapshot_id` và v1 manifest digest. S5 builder đọc canonical PG của **toàn membership**, sinh v2 với ID/digest mới ngoài transaction dài; CAS kiểm lại source/chunk-set/membership/corpus-head revisions trước publish. V1 và approval/trace cũ giữ nguyên bytes. Hai worker/call replay cùng transition dùng idempotency/fencing hiện hữu; crash không để v2 thiếu statistics thành active.
- Receipt của v1 không đổi nhãn thành v2. Chỉ tạo receipt v2 mới sau khi đối chiếu lại projection với canonical expected identities/vectors/profile/membership và full readback; có thể reuse projection nếu mọi input và server contract còn khớp. Không OCR/rechunk/re-embed chỉ vì đổi schema statistics. Nếu profile/index inputs đổi, chạy `corpus_reindex` cho membership chịu ảnh hưởng theo B/C; không bỏ reindex bằng receipt copy. Swap snapshot cùng all member lexical heads/receipt references trong một PG transaction.
- S4 standalone chỉ biết v1, không import S5. S5 reader hỗ trợ đọc lịch sử v1/v2 nhưng **SDM serving bắt buộc v2 đầy đủ**; trước cutover tiếp tục S4 BM25 nếu snapshot cũ còn authorized, còn S5 route báo chưa sẵn sàng. Sau cutover, mọi producer text/PDF/CLI/archive/reprocess ở S5–S8 sinh v2 qua builder chung trước activation. S5 sở hữu additive decoder/builder/routing và migration nếu cần, nối sau S4, giữ một Alembic head tại mỗi stage. Unknown schema fail-closed; không âm thầm tính stats trong request.
- Rollback S5 phải chọn reader/config hiểu snapshot đang active hoặc tạo fresh v1 transition từ **membership hiện hành** rồi CAS trước khi bật S4 BM25; không chạy binary S4 trên v2 không hiểu, downgrade in-place hoặc resurrect archived/revoked v1. Tắt SDM cho tới khi v2 hợp lệ được tạo lại. Kiểm upgrade/rollback trên DB đã có dữ liệu S4, không chỉ fresh schema.
- `prepare_corpus_transition(workspace_id, policy_id, expected_revision, cause)` capture canonical membership trong short PG transaction, tạo desired revision và durable work. Tính nặng ngoài locks từ immutable inputs; CAS kiểm lại toàn bộ membership/source/head revisions. Text/PDF finalize, CLI, archive/unarchive/reprocess đều enqueue qua seam chung trong transaction canonical commit.
- `corpus_reindex` parent mới cho mỗi document thực thi load/validate/prepare canonical chunks/embedding authority, tạo đúng1lexical_index child. Additive trigger/routing/status/readiness/retry/fencing hỗ trợ kind mới; không nới parent validation toàn cục. Profile đổi → restage **toàn membership** vì weights dùng avg_len tại index time. Batch64points với loop hữu hạn, không truncate document>64chunks.
- Child finalize chỉ ghi verified receipt, không activate riêng từng doc của transition. `commit_corpus_transition(snapshot_id, expected_revision)` yêu cầu đủ toàn membership/receipts và source/Workspace fences, swap corpus head và all member lexical heads trong1PG transaction. Partial/race/reply-loss không tạo partial serving. Giữ old snapshot nếu còn hợp lệ; archive/revoke khiến old invalid thì unavailable tới snapshot mới, không phục vụ stale để giữ uptime.
- Empty corpus có explicit empty snapshot/count0, không dummy avg_len/digest; không SDM scoring trên empty. Rollback/rebuild tạo fresh eligible generation bằng jobs/CAS, không resurrect revoked head. Cleanup chỉ projection không active/desired; không xóa canonical sources/embeddings/old traces.
- `read_serving_snapshot_in_transaction(...)` và `read_corpus_statistics_in_transaction(..., expected_snapshot)` trả persisted verified identities/digests/frequencies. Bỏ correctness dependency vào global `_CORPUS_STATS_CACHE`; đọc PG head mỗi request. Chưa cần Redis, notification hay cache layer mới.

#### C. Vector/collection/IDF authority

- PG pin immutable embedding_set/config/config-digest/dimension/Cosine/float32 và ordered chunk→raw-vector digest. `load_generation` lấy exact set của manifest; missing active/config/mixed set fail-closed, không UUID-desc hay gắn query config lên dữ liệu không rõ.
- Stage/readback bắt buộc with_vector=True cho đủ mọi member; expected contents/digest lấy PG. Float32/Cosine comparator có policy riêng: derive server-equivalent normalization từ PG, dùng tolerance suy từ error bounds và actual pinned-server positives, không JSON-byte equality/raw vector hash equality. Giữ PG raw immutable. Test missing/forged payload digest không được skip; payload digest chỉ diagnostic.
- Receipt V3 versioned ràng buộc snapshot+membership/profile, generation/content, collection/server config, embedding manifest, comparison-policy, count/coverage và raw readback capture hash. Corpus CAS không chấp nhận receipt tamper/partial/wrong set.
- Pinned v1.19.2 wire test cả PUT collection và query: rescore/oversampling nằm trong **query quantization params**, không lấy fields collection không hợp schema làm evidence. Explicit bits4/float32-original/on_disk/pinned quantized/HNSW; không dựa rescore default. Đây là compatibility risk phát hiện khi thiết kế; không đổi F25 PASS offline trước đây thành runtime PASS.
- V3 sparse BM25 IDF corpus scope = cùng workspace/generation/profile filter từ PG snapshot (pinned API params.idf.corpus), kể cả hybrid sparse prefetch. Stage/historical/foreign-workspace decoys không được đổi active population IDF. Nếu actual pinned server không hỗ trợ contract, gate chưa đạt; không fallback global. S2 frozen query path giữ nguyên.

#### D. Một read snapshot cho toàn answering request

- Thêm `RetrievalReadSnapshot` immutable trong answering store port: authorized workspace/scope, retrieval/lexical/embedding policies, toàn bộ active document/version/chunk-set/index-generation/embedding-set IDs, structure checksum và corpus statistics snapshot/digest. Capture trong short PG repeatable-read; không giữ transaction qua Cloudflare.
- `capture_retrieval_snapshot(...) → RetrievalReadSnapshot`; `retrieve_candidates(..., snapshot=...) → RetrievalResult` có cùng snapshot identity **kể cả empty**; `read_canonical_source_scope(..., snapshot, cursor, limits) → CanonicalSourceRead`. Authorization từ admitted principal/command, không tin caller allowlist hay Qdrant payload.
- Validate **từng result** trước merge/rerank, cả membership từng candidate và envelope IDs. Hydrate canonical PG content, không chỉ đối chiếu checksum tự khai từ remote. Mismatch/stale/non-typed contract abort attempt; không union versions, không tự restart request với snapshot mới.
- Full read snapshot và mọi branch observations/query/group mapping đi vào trace. Revalidate trước mỗi external content-bearing call, transactional persist và final delivery/recovery. Query2 ngoại scope không được tới reranker/generator/verifier. In-flight revoke không thể unsend request đã ra cloud, nhưng cấm gửi tiếp và cấm giao answer/citations cũ.
- Lịch query theo required groups trước, composite query nếu còn slot, rồi variants round-robin tới8. Reserve1search mỗi required group, max4groups; không truncate sau variants. Embedding response đúngN, đúngdimensions/config/provider/model/finiteness/index order; vector bằng nhau có thể hợp lệ nhưng thiếuN không được broadcast. Merged cap100 kể cả recovery, evidence5chunks/3000tokens.

#### E. Canonical source recovery và Q6

- Scope: explicit authorized document/reference → admitted Conversation source context → unique authorized catalog match. Không chọn document đầu từ Top-K. Nhiều source khả dĩ → clarification, không đoán; unauthorized không tiết lộ sự tồn tại.
- `CanonicalSourceRead` gồm exact snapshot/doc/version/structure/content checksums, section/page/block anchors, canonical windows, completeness/coverage/cursor/exhaustion và observed counts/reason. PG reader enumerate scope có giới hạn, không similarity Top-K. Đọc named section trước; cần thì traverse canonical scope trong D4. Không chạy OCR/reprocess inline để né deadline.
- FOUND cần factual text, không heading-only; map về same candidate type và kiểm lại source/window/cap. VERIFIED_ABSENT chỉ sau scope đủ và completeness có bằng chứng. Catalog complete chứng minh **section không tồn tại**, không chứng minh mọi semantic fact vắng. Keyword miss sau full scan cũng không đủ cho arbitrary semantic absence; chưa có complete auditable rule thì UNVERIFIED. Không thêm LLM call để tự tạo bằng chứng absence.
- Một lượt recovery cho toàn missing groups, giữ per-group outcome FOUND/VERIFIED_ABSENT/UNVERIFIED/AMBIGUOUS. Thiếu một vế comparison không sinh nửa so sánh; trả thông tin thiếu đúng phạm vi hoặc clarification/operational state. Nguồn cóC5 nhưng Top-K miss phải được đọc, bổ sung evidence và trả lời/cite nếu facts đủ. Partial/OCR/quota/deadline/error không biến thành “tài liệu không có”.

#### F. Answer span/citation và verifier riêng

- Giữ statement/group boundaries từ fixed-slot composer v21 khi render, không cắt theo dấu chấm cuối trước citation. Exact composed answer hash + statement IDs/text ranges/aliases là internal typed projection; kiểm text/ranges/aliases phủ toàn factual body, kể cả before/items/after. Không đổi public answer schema chỉ để lộ implementation metadata.
- Mọi V3 ANSWER, kể cả1intent, kiểm deterministic IDs/section/number-unit-date-entity tuples/source checksums và exact spans. Explicit conversion7days↔1week được test; không tự đổi month↔days hay dùng bag-of-numbers/global negation. Uncertain tuple không tự contradiction.
- Task-specific `AnswerSupportVerifier.verify(question, groups, answer_projection, evidence, snapshot_digest)` dùng existing Cloudflare transport với prompt/schema `cloudflare-gpt-oss-answer-support-v1`, model hiện có20B. Model không sửa answer, không tools/URL retrieval; question/source/answer đều untrusted data. Không đưa gold/chunk relevance labels vào runtime prompt.
- Strict result envelope: answer_digest/snapshot_digest; đúng1entry mỗi statement với SUPPORTED/CONTRADICTED/UNKNOWN, source_refs alias+exact_quote+half-open offsets+reason enum; đúng1entry mỗi required group ANSWERED/MISSING/UNKNOWN+statement_ids. additionalProperties=false; local kiểm cardinality/coverage/digests/offsets/quote exact từ PG-selected evidence. Model không override hard auth/identifier/contradiction failures.
- Chỉ answer khi mọi factual statement SUPPORTED và mọi required group ANSWERED bởi supported statements. Invalid/unknown/timeout/quota/malformed không deliver successful answer và không persist recoverable valid answer; trace tách invalid-output khỏi verifier-unavailable. Giữ safe error/refusal contracts hiện hữu, thêm typed code chỉ nếu mapping HTTP/SSE/Conversation được kiểm đầy đủ; không giả INSUFFICIENT_EVIDENCE khi source thực có facts. Không stream answer bytes trước validation; progress events được giữ.
- Một model cùng family có thể cùng sai; verifier verdict không là independent oracle. G7 cần source-reviewed positives/negatives/held-out, deterministic security và counterexamples. REFUSAL không qua verifier nhưng source-absence reason vẫn phải có Q6 proof.

#### G. Identity và compatibility

Policy IDs mới: `query-planning-v3-r4-v1`, `canonical-source-recovery-v3-r4-v1`, `answer-support-verification-v3-r4-v1`; native parser `pdf-parser-native-geometry-cloudflare-v2`, extraction-options/schema riêng. Dynamic lexical policy `bm25-word-dynamic-corpus-v1`; exact profile/snapshot instance có digest riêng. Giữ mọi historical ID/bytes/source/ChunkSet/trace; không relabel pypdf/Docling cũ thành implementation mới.

Resolver nhận immutable configs mới: `retrieval-bm25-top8-v3-r4-v1`, `retrieval-dense-top8-v3-r4-v1`, `retrieval-hybrid-top8-v3-r4-v1`, `retrieval-hybrid-rerank-top8-v3-r4-v1`. Nếu code có profile thứ5 thì khai rõ cùng registry theo factory thực, không tạo alias không resolve. Thay suffix detection `endswith('-v3')` bằng explicit capabilities; unknown config fail. Reranker ID F09 giữ nguyên vì provider bytes/behavior không đổi. Cloudflare embedding model được chọn theo existing resolver + development matrix, **không tuyên bố BGE-M3** nếu đang chạy BGE-base/Qwen3. Không đổi dimensions/space chỉ để khớp runbook.

Trace R4 có schema version mới/decoder riêng cho cả3modes (hiện _trace chọn schema3 chỉ lexical). Migrate trace validators/persist/Conversation readers cùng nhau, giữ legacy decoders. Mandatory read-snapshot/verifier provenance không lén gắn semantics mới lên oldtrace3. Approved implementation cập nhật CONTEXT/ADR/seams tại owner hiện có cho các delta tương ứng.

### 14.4 Các task triển khai và kiểm chứng

Mọi task: ca đỏ trên owner → sửa application/callers/adapters/fixtures/docs tương ứng → ca xanh và ca đúng không bị reject → scoped regression → Ruff/format và diff review → commit có Refs#153 → sync lần lượt downstream, kiểm semantics/conflicts. Không force-push. Test snippets dưới là **acceptance shapes để thêm vào test module đã chỉ**, fixture/helper cần được định nghĩa tại cùng task từ raw/canonical boundary; không có nghĩa các helper này đã tồn tại. Test DB chỉ disposable package D6.

#### R4-0 — Intake và chuẩn bị gói freeze sớm

**Owner:** docs/điều phối, sau đó từng stage. **Files:** plan này chỉ tham chiếu; tiến độ/approval ở #153/PR. Source/gold/criteria artifacts theo existing evals convention, không session ledger mới.

- [ ] Xác nhận path/branch/status/worktree ownership và local/GitHub/base/ancestry, revision R4 được duyệt, D1–D8 exceptions. HEAD đổi thì đọc delta và refresh tests/CI; không reset về pins.
- [ ] Đọc seven frozen plans, ADR/seams/ci/agent-environment; kiểm conftest routing. Ghi interpreter/import path bằng checkout guard §12.3, Python3.12 CI; không mượn ambient DB/runtime của #158/#192.
- [ ] Trích29ID thành acceptance matrix trong PR; đánh dấu12open/17regression, chưa có stage accepted. Đưa oldG8 unsupported claims vào superseding-report queue, giữ lịch sử.
- [ ] Ngay đầu việc, lập source permissions/independent reviewer/criteria protocol/package manifest theo §14.6; kiểm tool/container/account capability read-only. Thiếu quyền/cloud/source chỉ chặn phần phụ thuộc; code/offline vẫn tiến hành.
- [ ] Hoàn tất mốc DEP0 ở §14.6D: nhận diện owner từng phụ thuộc và artifact cần giao; ghi một dependency packet sớm trong #153/PR. Đăng ký riêng người soạn, người duyệt, người chạy held-out và namespace/access theo §14.6A; kiểm cách ly trước khi tạo hidden cases. Không chờ RC cuối mới phát hiện thiếu quyền hoặc nguồn nghiệm thu.

#### R4-1 — Native/OCR provenance và structure thật (F03)

**Owner S3/#216. Files:** `backend/pyproject.toml` và dependency/build owners; `adapters/pdf/docling.py` (compat facade hoặc đổi private driver có resolver rõ), `providers/cloudflare/pdf_understanding.py`, `ingestion/pdf_structure.py`, `pdf.py`, `pdf_chunking.py`; submission/resolver/job_processing/finalization hai paths. **Produces:** region-preserving canonical structure + new derivation identity theo A/G.

- [ ] Thêm raw PDF fixtures/test helper cho native/multi-column/rotated/mixed/tiled/merged table; independent source truth không sinh từ candidate parser. Thêm positive/negative source spans và serializer round-trip.
- [ ] Ca đỏ bắt buộc, acceptance shape trong `backend/test/adapters/pdf/test_docling.py`:

```python
def test_mixed_page_preserves_region_provenance(mixed_pdf, extractor):
    result = extractor.extract(mixed_pdf)
    page = result.structure.pages[0]
    assert {block.origin.value for block in page.blocks} == {"native_text", "ocr"}
    assert all(block.confidence is None for block in page.blocks if block.origin.value == "ocr")
    for block in page.blocks:
        assert page.text[block.start_offset:block.end_offset] == block.text
```

- [ ] Adapter geometry/render/region/cells theo A, validate provider schema và crop/grid; native+OCR không duplicate text. Missing required table cells/provenance giữ incomplete, không tuyên bố F03 đóng chỉ bằng origins.
- [ ] Bump identity xuyên submission→persist→resolver→worker→finalize; same raw PDF giữ DocumentVersion, tạo ChunkSet mới. PG reload cảdense/extraction-only giữ structure/checksums, legacy bytes không mutate.
- [ ] Chạy owner5PDF suites §13.2, thêm actual native table/reading-order/round-trip/PG selections; F01/F02/F04/F20/R2-N02 regression. G3 structure truth/liveOCR còn là gate riêng, không coi mocked text đủ.

#### R4-2 — Hard deadline/memory và cleanup (F24)

**Owner S3/#216. Files:** `adapters/pdf/_pypdf_process.py`, `pypdf.py`, `_pypdf_limits.py`, driver ở R4-1, provider remaining-timeout/lifecycle; tests `backend/test/adapters/pdf/test_pypdf.py`, `test_docling.py`, PDF worker tests. **Consumes:** existing OS limiter; **produces:** one absolute-budget extraction outcome.

- [ ] Tái hiện memory1byte, child sleep/allocate, delayed conversion và parent-death trong spawned process thật; không chỉ Mock sleep quanh helper.
- [ ] Test shape (helper `run_owned_extraction_probe` trong cùng test module tạo/chạy/inspect child do fixture sở hữu):

```python
def test_late_success_cannot_finalize(owned_probe):
    observed = owned_probe(timeout_ms=20, native_sleep_ms=100, late_success=True)
    assert observed.error_code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert observed.active_derivation is None
    assert observed.owned_pids_remaining == ()
    assert observed.owned_tempfiles_remaining == ()
```

- [ ] Refactor shared private supervisor theo A; hard limit installed trước handshake, bounded source/output/pixels, remaining timeout mọi CF call, reject late success sau conversion/assembly. Cleanup idempotent của ownertree, parent healthy.
- [ ] Test actual Windows Job và Linux cgroup/memory/cancel/startup unavailable/broken IPC/reply loss; parent SIGKILL chỉ claim no-orphan nếu có OS mechanism và test. Chạy pypdf legacy regression + Python3.12 CI; không tăng budget để làm hết test đỏ.

#### R4-3 — Dynamic producer và corpus transition (F05; nền F08)

**Owner S4/#217. Files:** `ingestion/lexical_population.py`, `search_indexing.py`, `jobs.py`, `job_processing.py`, text module/store, PDF finalize, `adapters/postgres/tables.py`, `search_index_store.py`, ingestion_jobs routing/submission/coordination, `adapters/cli/reindex_search.py`, `main.py`, resolver;1additive migration + ADR0019/seams delta. **Produces:** B và versioned manifest/receipt input; S5 dùng cùng snapshot.

- [ ] Thêm DB/schema/job constraints additive theo B, newoperation corpus_reindex; migration chain không sửa0157/0158 lịch sử. Legacy rows giữ decoder; V3 thiếu snapshot fail. Empty/repeated-source/repeated-chunk valid theo exact membership.
- [ ] Ca đỏ HTTP text/PDF và CLI không finite population→durable transition/parents/children; CLI dry-run không ghi. Không dummy avg_len256/zero digest, fake parent, UUID-desc/latest-config hoặc swallow skipped document errors.
- [ ] Test shape tại PG `test_corpus_statistics_transition.py`, DB disposable:

```python
def test_corpus_switch_requires_every_member_receipt(corpus_case):
    prepared = corpus_case.prepare_two_document_transition()
    corpus_case.finish_first_child(prepared)
    assert corpus_case.active_snapshot() == prepared.base_snapshot
    corpus_case.finish_last_child(prepared)
    assert corpus_case.active_snapshot() == prepared.snapshot_id
    assert corpus_case.active_member_ids() == prepared.all_member_ids
```

- [ ] Promote exact native tokenizer counter source/license/reprobuild/hashes, bounded model-free runner trong app/worker image; kiểm fresh Unicode/punctuation/underscore/dot/empty/repeated parity, không trỏ Temp binary. Đo tokenizer resource cost; failure unavailable, không approximate fallback.
- [ ] Nối common enqueue/prepare/stage/receipt/CAS cho text/PDF/CLI/backfill/archive/reprocess/unarchive; >64chunks stage đủ batches. Crash/retry/late lease/partial receipt/two last workers/concurrent upload+archive không partial activation. Snapshot invalid source dừng serving đúng contract.
- [ ] Chạy S4 offline selections §13.3 và CLI/PG disposable suites, actual3mode journeys tại R4-11. Newmigration phải một head mỗi stage, S5–S8 nối đúng, không ép giữ tên head0157 sau additive change.

#### R4-4 — PG vector receipt, collection wire và IDF (F23; F25 regression)

**Owner S4/#217. Files:** `adapters/qdrant/search_index.py`, `native_search_index.py`; PG load_generation/lexical_retrieval; receipt types và tests Qdrant/PG. **Consumes:** R4-3manifest/vectors; **produces:** verified receipt theo C.

- [ ] Ca đỏ corrupted vector768values9.0 với payload digest missing/forged, wrong model/set same dimension, missing active config, partial readback và tampered receipt.
- [ ] Positive numeric normalization test trước làm comparator; acceptance shape:

```python
def test_readback_uses_pg_expected_not_remote_digest(vector_case):
    assert vector_case.verify_server_cosine_float32_readback() is not None
    with pytest.raises(ProjectionResponseError):
        vector_case.verify_corrupted_readback(remove_payload_digest=True)
    with pytest.raises(ProjectionResponseError):
        vector_case.verify_corrupted_readback(forge_payload_digest=True)
```

- [ ] Implement PG expected mandatory và comparison-policy version; tolerance từ float32 analysis/server fixtures, pin trước final. Missing digest không làm skip; no JSON/rawbyte equality. Kiểm full coverage trong bounded batches.
- [ ] Kiểm actual PUT/query/readback theo pinned OpenAPI, quantization/rescore/oversampling đúng chỗ và hybrid prefetch cũng đúng; không dùng internal-policy fields làm fake server evidence. Sparse IDF corpus filter bound snapshot, inactive/foreign decoys không đổi active BM25 scores.
- [ ] Offline native/dense/Qdrant+PG assertions; actual pinned server positives/corruption/IDF/readback tại R4-11. Không hạ TurboQuantbits4 thành int8 hoặc đổi Cosine cho dễ so.

#### R4-5 — SDM đọc persisted snapshot (F08)

**Owner S5/#218. Files:** `answering/sequential_dependence.py`, `module.py`, `adapters/postgres/search_index_store.py`, `answering_store.py`, snapshot decoder/builder và common producer routing; additive migration trong `backend/migrations/versions/` nếu cần; tests SDM/corpus/PG transitions. **Consumes:** immutable S4 v1 snapshot; **produces:** fresh v2 transition, persisted SDM CorpusStatistics và reader/producer compatibility theo §14.3B.

- [ ] Tạo fixture S4 v1 đã active với canonical chunks/embeddings và receipts thật. Chạy upgrade job, chứng minh v1 bytes/hash không đổi, v2 có parent digest và full-corpus stats, không parse/embed lại khi inputs giữ nguyên. Chặn S5 serving trước activation; sau activation tất cả member heads/receipts cùng v2. Test unknown schema, missing section, replay, crash/resume, hai workers, concurrent archive/upload/reprocess và rollback theo B; không lấy migration success thay serving proof.
- [ ] Persist SDM full-corpus counts/frequencies theo scorer policy, recompute canonical digest khi load, kiểm identity/tokenizer/revision/member/profile. Không recompute active chunks trong request path; bỏ correctness cache và fallback khi thiếu authority.
- [ ] Test red→green missing/wrong digest/tokenizer/membership/revision/frequency, transition1→2members, archive/reprocess/restart2workers. Test shape:

```python
def test_statistics_follow_serving_snapshot_not_process_cache(statistics_case):
    old = statistics_case.read_worker_a()
    statistics_case.activate_two_member_snapshot()
    new = statistics_case.read_worker_a()
    other = statistics_case.read_worker_b()
    assert old.snapshot_id != new.snapshot_id
    assert new.total_chunks == other.total_chunks == 2
    assert new.statistics_digest == other.statistics_digest
```

- [ ] Pool3 và100 dùng cùng background snapshot; numerical ordered/unordered/positional/calibration theo frozen S5, không sửa formula/gold để pass. Phrase Boost eval comparator, không fallbackproduction. S5minimum45tests baseline chỉ lịch sử; chạy lại scoped và PG transition thật đúng quyền.

#### R4-6 — S6 nhận upstream và giữ provider đã đạt

**Owner S6/#219. Files:** chỉ connected callers/schema changes cần do upstream; `backend/test/answering/test_reranking.py`, `backend/test/providers/cloudflare/test_cloudflare_reranking.py`, evidence/MMR tests và lifecycle refs.

- [ ] Sync R4-1→5; default pytest collection và hai suites trên, không importlib workaround. F09/F10/R2-N03 giữ ID/result.response/remap/lifecycle/fallback DBSF+SDM.
- [ ] max100 rerank inputs/evidence5/3000tokens; test timeout429/malformed/duplicate/out-of-range/nonfinite fallback. Actual bilingual quality/ablation trong R4-11; không viết lại provider nếu không có defect mới.

#### R4-7 — Mọi query cùng snapshot, finite fair variants (R3-N04/F18)

**Owner S7/#220. Files:** `answering/stores.py`, `module.py`, `query_planning.py`, `query_results.py`, lexical/dense/hybrid result validators; PG answering/lexical store và trace readers/persistence. **Consumes:** B/Csnapshot; **produces:** D, no invalid secondary result tới provider.

- [ ] Ca đỏ application spy2searches validator1lần; query2wrongworkspace/generation/emptycontract/version switch. Test shape tại `test_module.py`:

```python
async def test_secondary_query_mismatch_stops_before_any_provider(answer_case):
    answer_case.second_result_has_foreign_generation()
    with pytest.raises(KnoraError):
        await answer_case.execute_multi_query()
    assert answer_case.reranker_calls == 0
    assert answer_case.generator_calls == 0
    assert answer_case.verifier_calls == 0
    assert answer_case.valid_answer_traces == ()
```

- [ ] Capture once/retrieve withsnapshot/validate every result; full metadata and branch/group observations go into trace; content PG hydrate; all send/persist/delivery fences theo D. Không tự restart snapshot stale.
- [ ] Query scheduling group-first8searches/4groups; cap bên trong vòng; responseNvectors exact, bool/nonfinite/config mismatch reject. Tests1vector2queries phải fail,2validvectors giốnggiátrị vẫn được nhận; fifth requiredgroup clarification, không silentdrop.
- [ ] Apply new trace/profile/capability registry G cho tất cả modes, legacy decoders giữ; test singlequery/empty/multi/Conversation follow-up/SSE/trace recovery/parity. F12/F15/F22 và legacy không hồi quy.

#### R4-8 — Canonical source reader/recovery (F13)

**Owner S7/#220. Files:** `answering/source_verification.py`, `stores.py`, `module.py`, evidence_support/results, PG canonical structure/content reader trong answering adapter; Conversation/HTTP/SSE callers chỉ nếu safe reason chưa được truyền. **Consumes:** Dsnapshot + S3completeness; **produces:** E, per-group proof/outcome.

- [ ] Bổ sung typed canonical reader/catalog/exhaustion, actual authorized PG bodies/anchors, bounded cursor theo E. BM25 targeted lookup chỉ locator; không dùng query_vector=None với hybrid config để giả canonical read.
- [ ] Test shape sourceC5outsideTopK tại application+PG fixture:

```python
async def test_topk_miss_reads_canonical_source_before_absence(recovery_case):
    recovery_case.hide_chapter5_from_search_but_keep_complete_source()
    result = await recovery_case.execute()
    assert recovery_case.canonical_reader_calls > 0
    assert result.group_outcome("Chương 5") == "found"
    assert result.cites_chapter5_fact()
```

- [ ] Negative matrix: complete source thật khôngC5→specificverified_absent; partialOCR/catalog/read/bodymissing/budget/error→unverified/operational; multi-source→clarification; unauthorized decoy không đọc/tiếtlộ. Không dùng keywordmiss để kết luận semanticabsence.
- [ ] Recovery1pass đủ mọi group, preserve pool100/evidence5/3000/groupcap2; infeasible fullcomparison không sinh nửaanswer. Test revoke/versionchange mọi cửa đọc/provider/persist/delivery, reusedConversation refs không trở thành facts.

#### R4-9 — Statement/citation projection và semantic verifier (F14)

**Owner S7/#220. Files:** `answering/generation_validation.py`, `module.py`, generation result contract; `providers/openai_compatible/answer_blocks.py` internal composer projection; task-specific `answering/answer_support.py` và `providers/cloudflare/answer_support.py` chỉ vì trách nhiệm mới; composition/config/lifecycle; existing HTTP/SSE/Conversation errors/history. **Consumes:** D/E + final selected evidence; **produces:** F, validated answer/typed failure.

- [ ] Tái hiện tất cả probes trong `test_generation_validation.py`, `test_answer_group_completeness.py`, application/stream/persist suites. Matrix phải có singleintent, số70,7tháng, phủđịnh, citeđảo, heading/filler, groupomission; positives ngắn, paraphrase7ngày↔1tuần, citation sau dấu chấm, multi-sentence/v21 lists.
- [ ] Preserve composer statement boundaries, local hard mappings và strict verifier schema theo F. Test shape với injected verifier contract:

```python
@pytest.mark.parametrize("case", ["wrong_number", "wrong_unit", "wrong_negation", "swapped_cite"])
async def test_invalid_facts_never_emit_answer_bytes(answer_case, case):
    result = await answer_case.run_stream(case)
    assert result.answer_bytes == b""
    assert result.valid_answer_trace is None

@pytest.mark.parametrize("case", ["concise", "paraphrase", "citation_after_period"])
async def test_supported_surface_is_not_rejected(answer_case, case):
    result = await answer_case.run_stream(case)
    assert result.is_valid_answer
```

- [ ] Runtime verifier same20B nonstream1batch theo D5, no retry/regeneration. Exact-model minimal capability proof trước semantic runs; schema support không được suy từ catalog. Timeout/quota/malformed/UNKNOWN không cache-valid hoặc pretendmissingfacts. Lifecycle close đúng và requestcounters đầy đủ; injection từ source không sửa policy/tool/schema.
- [ ] Không dùng mock verdict để nghiệm thu semantic: R4-11 chạy source-reviewed gold independent của verifier/generator. Same-model correlated errors ghi residualrisk, hard invariants0violation không bù bằng judge. Nếu20B không đáp ứng contract thì giữ gate chưa đạt, không tự đổi provider/model/semanticgate; chuẩn bị evidence packet duy nhất.

#### R4-10 — Release admission fail-closed (F16)

**Owner S8/#221. Files:** `evals/datasets/pdf_retrieval_release_v1.py`, release manifest/approval/schema owners, `evals/test/test_pdf_retrieval_release_dataset.py`, release runners/callers. **Consumes:** approved source/gold/protocol package; **produces:** hash-bound ReleaseDataset admission.

- [ ] Mọi actual/explicit/default path enforce manifest+approval, không is_default bypass; no hardcoded sample fallback. Nếu cần examples, test fixture riêng không nằm release runner route. Missing file/schema/version/split/source/bindings/count/hash/approval/duplicates đều fail.
- [ ] Approval record phải pin exact dataset/source/gold/scorer/criteria hashes, approver identity+role/authority/reference/timestamp trước scoring. Source/approval issue-root URL chung chung không chứng minh đúngartifact; không bịa ownerđãduyệt. Anti không nâng existing4samples thành independentheldout.
- [ ] Test exact current counterexample:

```python
def test_explicit_path_still_requires_manifest_and_approval(tmp_path, valid_release_bytes):
    target = tmp_path / "unapproved-release.jsonl"
    target.write_bytes(valid_release_bytes)
    with pytest.raises(DatasetContractError):
        load_release_dataset(target, enforce_approval=True)
```

- [ ] Test wrong hash/count/version/source/split, duplicate ID/sourcecontamination, expired/revokedapprovalpolicy và nofallbackdefaultmissing. Add release schema/version mới nếu mandatorybindings đổi; preserve oldartifacts decoder/history, không sửa gold bytes theo output.
- [ ] Admission kiểm role/identity, source-label freeze trước candidate outputs, approved exact revision và visibility/contamination record theo §14.6A; implementer tự ký, curator tự duyệt, exposed held-out hoặc approval trỏ version khác đều reject. Baseline/candidate dùng cùng sealed inputs và source judgments; chunk bindings riêng từng subject, không sửa source truth theo extractor.

#### R4-11 — Runtime thật, matrices và runbook (F17/F21)

**Owner S8/#221**, lỗi code quay về owner rồi cascade. **Files:** `scripts/run-runtime-verification.ps1`, `scripts/runtime_evidence.py`, runtime workflow/tests/config tests, existinglauncher/reservation/Compose definitions, `docs/runbooks/retrieval-v3-release.md`, CI/evaluation/runbook owners nếu contract đổi. **Consumes:** upstream fixes + freeze package; **produces:** actual journeys/rawcaptures cùng RC.

- [ ] Tách offline contracts khỏi service qualification. Chạy đủ21contractcases hiện có, không `-k ann_recall or decoy` để né wire tests. Bỏ synthetic ANN/quantization/top15labels khỏi acceptance; có thể giữ helperdemo ở testtier, tên/report không runtimeclaim.
- [ ] Reuse launcher/reservation/Doctor; extend actual application+PDFworker+PG+Qdrant runtime path và nguồn public/synthetic, CF thật khi D6preflight đủ. Không copy S2stack rồi dùng finite S2profile làmV3proof. Namespace resources mới/credentials riêng/labelowned, stack prep/cleanup theo §14.5; sharedports foreignbusy phải chờ, khôngkill.
- [ ] Journeys bắt buộc: freshPDF/textHTTP/CLI/backfill→canonicalPG→projectionreceipt→atomicactivate→query/Turn;3modes; source recoveryfound/absence/unknown/ambiguity; variants/answerfacts/citations; data+Workspaceauth/activeversion/revoke; upload/archive/reprocess/concurrentcorpus; defaultverifier/CF429/malformed/timeout; Qdrantoutage/lostcollection→rebuildfromPG/retainedsources; lease/replyloss/reconcile/CAS; optin/rollbackfences. Fault injection ở ownedboundary, không dùng fake store làm recoveryproof.
- [ ] Actual ANN cùng query/filter/eligiblepopulation/serverbuild; exact request exact=true/quantization.ignore=true, ANN explicit HNSWef256/rescore/oversampling. Corpuseligible>200 và recorded index/fullscanthreshold/readiness đủ chứng minh đường index; có200points không tự làANN. Compare returnedlists thực, khôngchế approximate từexact. Float32/Bits4 quality labels độc lập, absolute nDCG@10drop≤0.01 giữ nguyên.
- [ ] Đủ frozenmatrices: FTS/BM25/k1-b/tenantIDF/phrase/SDM; pgvector/Qdrant cùngspace; float32exact/HNSW/bits4; legacyRRF/fullV3/DBSF+SDMnorereanker; queryeffects táchrankingablation. Metricsappropriate/denominators/uncertainty/coldwarm/10kchunks/3queries+1PDF/calls/resources/$0 và lỗi/notrun đầy đủ. #148/#150/#158 chưaaccepted là dependency chưađạt, khôngimplementlấnowner hoặc giảtest.
- [ ] Evidencevalidator versioned binding subject/workflow/PRhead/syntheticcheckout/build/images/config/dataset/gold/scorer/criteria, actualselected+executedscenario/nodeIDs, rawJUnit/captures/hashes and traceattemptjoins. Sanitizedgeneric testcase count không thayrawscenarioidentity. Reject helper-only/empty/skipped/error/failed/duplicate/wrongsubject/missingresources/incompletescenario. Test shape:

```python
def test_helper_only_artifact_is_not_runtime_acceptance(runtime_packet):
    runtime_packet.set_execution_kind("offline_contract")
    with pytest.raises(ValueError):
        runtime_packet.validate_as_retrieval_runtime()
```

- [ ] Runbook đúng parser/resolver/env/model/IDs vàpagebounded/token caps; prefetch200/merge100 táchrõ. BM25-only0queryembeddings không có nghĩa0cloudgeneration. `print(setting)` không làhealthcheck; unit test không làrollbacksmoke. Viết command/config switch có thật và xácminh deployedconfig/generations/requests saurollback. Không bịa p95target chưafreeze.
- [ ] Report mới supersede olddd5aRC/PASS50claims bằng exactRC+actualcounts; giữ historicalreports. CIgreen không làrealruntime; annotation rõ code/local/CI/runtime/quality/review/owneraccepted/merged/deployed.

#### R4-12 — Hoàn tất review/CI và giao nghiệm thu

- [ ] Sau mỗi owningfix sync downstreamS3→S8, đọc stage-onlydiff và tests bị ảnhhưởng; không patchS8alone. Commit/push/CI trongD8scope, khôngforcepush. Trướcfinalfreezecheck sạch/HEAD/GitHub/ancestry/migrationuniquechain/format/checks.
- [ ] FullCI Python3.12 cho từngownerHEAD/mergecandidate theo workflow/routing hiện hành; readci-subjectartifact actualcheckout vsPRhead+workflowSHA. Reviewindependent khôngcònP1/P2 trên29IDs hoặc ghi chưađạt, khôngselfwaive. NativeCFlimits/actualstack vàqualityevidence phảiđúngRC.
- [ ] Hoàn tất mốc DEP1/DEP2 và capability evidence §14.6D. Chỉ trình nghiệm thu G8 khi toàn bộ điều kiện bắt buộc đủ; nếu phụ thuộc ngoài scope còn thiếu, giao packet phần kỹ thuật đã kiểm và dependency blockers, giữ G8 chưa đạt và tiếp tục phần độc lập. Không kết thúc nhiệm vụ bằng nhãn RC-ready thay cho nghiệm thu. Issue Q1 vẫn gồm approved deployment/post-deploy; chuẩn bị target/build/config/migrations/backfill/backup/rollback/observation trước xin lệnh cuối.
- [ ] Chỉ saulệnhmerge/cutovercụthể: #216→#217→#218→#219→#220→#221 (#215đãmerge), retarget/reconcile/testmergecandidate; sourceđổi map/rerungates. Deployđúngtarget, postdeployPDF/text/QA/recovery/auth/revokesmoke+observation vàrollbackreadiness. Chưađượclệnh thì ghi RCready/chưamerge/deploy, toànIssuechưaDone; không xinlạithiếtkếD1–D8.

### 14.5 Quyền chạy, sử dụng AI có mục đích và tiếp tục tới nghiệm thu

**D6 chỉ có hiệu lực sau duyệt R4.** Trước mỗi gói chạy, Anti ghi vào manifest hiện hữu: người thực thi, mục đích, source permissions, code/config/image digests, resource names/IDs, DB/collection/bucket/ports, reservation, lệnh, giới hạn, cleanup và nơi giữ bằng chứng. Tên resource mới dùng prefix riêng có run ID; verify resolved targets trước mọi reset. Không suy quyền reset từ một DATABASE_URL.

| Phần việc | Quyền sau duyệt | Điều kiện dừng và hành vi |
|---|---|---|
| Offline/CI | Chạy test, build/lock dependencies và images của ứng dụng; commit/push đúng PR owner; dispatch workflow hiện hữu | Không sửa shared runtime/host tools, force-push hay đổi required checks. Shared file có owner khác cần ACK hữu hạn cho hunk cụ thể; im lặng không là đồng ý. |
| Disposable runtime | Tạo, migrate, seed, fault-inject, reset và cleanup chỉ DB/collection/volumes/process tree mới do gói đó tạo | Existing/foreign resources và dữ liệu người dùng không được đụng. Port/reservation bận thì chờ/chọn port được launcher hỗ trợ, không kill phiên khác. Thiếu hard-limit capability thì qualification chưa đạt. |
| Cloudflare | Account Free xác minh được, model/route nằm trong free allocation; backend credential loader; public hoặc synthetic sources đã có quyền | Paid/unknown plan, không chứng minh route miễn phí, credentials/quota không rõ: không gửi request. Không mua quota, bật Paid, local inference hoặc đổi provider/model để vượt chặn. |
| Quota của nhà cung cấp | Dùng phần Free allocation thực còn khả dụng, kiểm account/route/usage trước dispatch; không áp thêm trần neurons/ngày nội bộ | Ước tính theo model pricing hiện hành để reserve input/output; unknown/failed send giữ reservation tới reconcile. Free account hard stop bảo vệ $0; reservation không cấp quyền chiếm quota của client khác. Hết quota thì tiếp tục phần offline và phần cloud khi quota có lại, không xin tăng ngân sách số lượt. |
| Toàn đợt triển khai | Không áp trần tổng số AI calls, không chia quota cứng theo OCR/embedding/rerank/answer/verifier/judge, không áp trần journeys/RC | Được gọi đủ để tái hiện, nghiên cứu phương án trong scope, sửa, so sánh, hồi quy và nghiệm thu. Ghi actual HTTP attempts, child fan-out, tokens/neurons, errors và kết quả; số đo này phục vụ truy vết và chống lãng phí, không là bộ đếm dừng công việc. |
| Vòng sửa và RC | Không áp trần số vòng sửa, RC hoặc lần chạy nghiệm thu; tiếp tục tới khi đạt các tiêu chí và có bằng chứng hợp lệ | Mỗi final run giữ nguyên subject/config/gold/criteria đã freeze và không retry ngầm. Nếu sửa sau khi xem held-out thì chuyển bộ đã lộ thành development, chuẩn bị held-out mới qua D7; giữ mọi failed attempt và không hạ tiêu chí để kết thúc sớm. |

Quota reset lúc 00:00 UTC (07:00 Việt Nam). Được tiếp tục phần còn lại trong ngày UTC sau theo cùng approval, sau kiểm lại account/quota/subject; không cần xin duyệt lại chỉ vì quota Free cạn. Quota nhà cung cấp là điều kiện chờ tiếp tục, không phải lý do bỏ nhiệm vụ hoặc ghi đã nghiệm thu. Nếu phiên không còn chạy, ghi checkpoint ở #153/PR để lần tiếp theo tiếp tục; không tự tạo lịch/automation. Không hứa hoàn tất trong một ngày khi mức Free không đủ. Client không cung cấp usage đáng tin phải dùng reservation bảo thủ và account-side Free hard stop; usage không đo được ghi unknown, không ghi $0 đã chứng minh.

**Chống phung phí bằng mục đích và bằng chứng:** trước mỗi batch, ghi câu hỏi kỹ thuật/lỗi/gate cần giải quyết, phần thay đổi hoặc điều kiện mới so với lần trước, số lượt dự kiến, đầu ra cần đọc và bước tiếp theo theo kết quả. Số lượt dự kiến là ước lượng để vận hành; có thể điều chỉnh theo bằng chứng mà không xin lại owner về số call. Tái sử dụng embeddings/captures/results khi đúng source/input/model/config/subject và gate cho phép; không reuse stale evidence. Chỉ chạy lại phần bị ảnh hưởng hoặc full suite khi required gate cần. Không lặp cùng input/config/điều kiện chỉ để săn một lần xanh, không gọi model thay phép kiểm deterministic đủ dùng, không bỏ failed attempts hoặc tune trên held-out đã lộ. Nếu lặp mà không có tiến triển, đổi hướng chẩn đoán hoặc phương án trong scope; chỉ trình owner khi có quyết định sản phẩm/quyền mới hay bất khả thi đã được chứng minh, không vì đạt một số lượt tùy ý.

Mỗi request vẫn chịu timeout/token/payload/concurrency/resource caps và chính sách retry của hợp đồng phục vụ; bỏ trần tổng lượt triển khai không biến request thành vòng lặp vô hạn hoặc tự thêm generation/verifier calls vào production pipeline. Provider outage/quota chờ theo tín hiệu phục hồi có thật, không busy-retry. Batch final không retry ngầm; một lần chạy lại có chủ đích phải là attempt mới có lý do, identity và raw outcome riêng. Việc này không tự cấp quyền dùng ngân sách, cloud export hoặc resources riêng của Issue khác.

Workload hữu hạn: quality corpus ở §14.6; scale corpus 10.000 canonical chunks, tối đa 3 queries đồng thời +1 PDF; 30 warm query observations và 5 cold-stack observations trên mỗi cấu hình đo latency, cùng hardware/process limits. Reuse embeddings canonical khi model/input/config không đổi; tạo phiên bản mới khi đổi space. Không đẩy corpus vượt 10.000 để ép ANN rồi nhận production claim; nếu không chứng minh index path ở workload này, ANN gate chưa đạt và báo cấu hình/planner evidence. Ghi riêng build/index time với query latency. Một extraction tối đa 60s; một question tối đa 90s; job retry durable tối đa 3 attempts theo policy hiện hữu, không nhân thành inference retries ngầm.

**Tự sửa đến nghiệm thu:** Anti tự xử lý lỗi implementation, test, migration, batching, parser/registry, CI và sync cascade trong D1–D8; không hỏi lại cách đặt tên private helper, SQL join, pins tương thích hay thứ tự task đã chốt. Lỗi mới cùng nguyên nhân/ranh giới được sửa tại owner và thêm regression. Thay scope/AI model/billing/quyền dữ liệu, không có shared-owner ACK, hoặc exact-model/server chứng minh phương án không khả thi thì dừng đúng phần phụ thuộc, tiếp tục phần độc lập và gom **một** packet gồm bằng chứng, tác động, phương án và một quyết định cần owner. Không tự hạ criteria hoặc báo Done để tránh hỏi.

Cleanup sau capture/hash: chỉ resources sở hữu trong manifest, giữ retained canonical fixtures/artifacts theo policy. Kiểm không còn own process/port/temp/object namespace; failures ghi vào evidence. Không xóa old PR artifacts/gold/approval để làm sạch báo cáo.

### 14.6 Protocol freeze, gold độc lập và tiêu chí nghiệm thu

#### A. Gói freeze trước khi nhìn final scores

Reviewer được D7 ủy quyền duyệt **nội dung thật** của package; không chỉ ký manifest chưa đọc. Đăng ký các vai trò sau tại R4-0 trong package của Workbench hiện hữu, với actor/session identity, quyền, artifact namespace, approval reference và thời điểm bắt đầu. Đây là phân quyền công việc, không tạo hệ thống evaluation mới:

| Vai trò | Được đọc/ghi | Điều kiện độc lập |
|---|---|---|
| Anti triển khai | Code, rubric, development cases; cung cấp exact candidate/comparator SHAs và config hashes | Không soạn/duyệt/chạy hidden suite; không nhận hidden questions, expected answers hay raw per-case outputs trước khi packet kết quả được chốt |
| Người soạn nguồn/gold | Tạo public/synthetic PDF mới, source labels, questions, manifest và judgments trong namespace evaluation mới của package; chỉ đọc canonical PG khi bind derivation | Agent/session riêng, không kế thừa context sửa candidate hoặc kết quả thử; không lấy candidate parser/generator/verifier làm oracle; không tự ký approval |
| Người duyệt nguồn/gold | Đọc raw source/rendered pages, labels, rubric và manifest; ghi approval hoặc rejection cho đúng hashes | Khác implementer và người soạn; chưa thấy candidate answers/scores trước freeze; có quyền D7 thật, không giả human review |
| Người chạy held-out | Đọc approved sealed package; chạy existing runner trên exact frozen subjects trong D6 resources; ghi raw observations, hashes, attempts và metric reports | Khác implementer; không sửa code/labels/criteria; chỉ mở results cho implementer sau khi toàn bộ paired run và report đã chốt; có thể là người duyệt sau source freeze |
| Người review code/evidence cuối | Đọc code, raw results và toàn bộ approvals sau freeze; ghi disposition từng ID/gate | Khác implementer; có thể là người duyệt nguồn nếu vẫn đáp ứng blind-before-freeze; không tự thay owner acceptance |

**Nơi giữ và quyền truy cập:** reuse dataset/source/approval storage của Workbench và ObjectStore trong D6 package, dưới namespace riêng `evaluation/<package_id>/held-out/<dataset_version>/`; đây là tên logic do backend cấp, không phải quyền tự đặt object keys. Package manifest pin actual dataset/source object IDs, hashes, người giữ dữ liệu và visibility. Người soạn chỉ ghi artifacts mới ở namespace này; runner/reviewer chỉ ghi kết quả/approval được giao. Trước scoring không đưa hidden bytes lên nhánh code, PR hoặc chat của implementer. Sau khi report chốt, source/gold/approval snapshots được lưu theo existing evaluation retention và publish bản được phép qua các owners `evals/corpora/`, `evals/datasets/`, `evals/reports/`; không sửa bytes lịch sử hoặc chỉ giữ bản duy nhất trong Temp. Việc publish không thay authoritative Workbench record.

Agent chạy cùng Windows user có thể có quyền filesystem rộng: session riêng chỉ cho **độc lập theo quy trình và nhật ký**, không chứng minh ACL cách ly. D7 đề xuất chấp thuận mức này khi kiểm được fresh context, artifact visibility và access transcript, không có implementer reads. Nếu công cụ không giữ được hidden context/record, chuyển việc giữ/chạy dữ liệu sang reviewer session do owner kiểm soát; thiếu vai trò/quyền thì ghi blocker ở R4-0, không tự gọi suite đã lộ là blind. Không gửi nội dung nhạy cảm qua cloud; chỉ public/synthetic trong D6.

**Hai lần đóng băng, không tạo vòng lặp oracle:** (a) curator và reviewer chốt raw hashes, source facts/regions/cells/reading order/hierarchy, expected group outcomes và rubric **trước** đọc candidate derivations/answers; (b) runner bind source anchors vào từng subject's canonical chunk sets/authorized universe bằng read-only PG và source offsets, reviewer kiểm mapping rồi pin dataset/approval/scorer/criteria trước scoring. Binding không được đổi source facts; không map được thì sửa candidate hoặc reject package, không sửa đáp án theo extractor. Baseline và candidate có bindings riêng nhưng cùng source truth. Approval/visibility/access records là bắt buộc khi admission; không có role hợp lệ hoặc không biết dữ liệu đã lộ hay chưa thì final gate chưa đạt.

- Giữ nguyên frozen exploratory 16 PDF/60 questions và Baseline B; dùng làm development/regression. Bổ sung development source mappings/judgments đã review để chạy đủ matrices. Probes R3 là ca development, không đưa vào held-out rồi nhận tính độc lập.
- Held-out R4: **ít nhất 60 câu mới trên ít nhất 12 PDF public/synthetic mới**, không trùng raw source hash hay diễn đạt lại ca đã tune. Phân tầng primary: 10 simple facts, 12 multi-part/comparison, 10 table/layout, 8 follow-up/reference, 8 typo/unaccented, 6 multi-hop, 6 absence/unknown/ambiguity =60. Cross-tags bảo đảm Việt–Anh, mixed native/scan, multi-column/rotation, concise/paraphrase, numbers/units/negation, citation position và adversarial source. Mỗi required tag phải có ≥2 cases; thiếu tag thì bổ sung case, không đếm duplicated prompt như source diversity.
- Source truth có raw hash, page/region/cell/section anchors, exact source spans, facts/conditions, per-group outcome và refusal/clarification reason. Reviewer đọc source độc lập; không dùng candidate extractor hoặc runtime verifier làm oracle. Nếu native visual geometry cần đối chiếu thì dùng raw rendered page cùng source, không chỉ text do candidate sinh.
- Retrieval judgments ghi authorized universe/snapshot/hash, binary grade0/1 theo frozen S4 rubric hoặc graded policy mới có lý do; judgments thiếu không tự là0. Review đủ judged universe cần cho metric; không dùng số relevant trong Top-K làm denominator. Calibration/development/held-out split có manifest và contamination checks.
- Pin source/dataset/gold/approval/scorer/metric/rubric/protocol/criteria hashes, models/prompt IDs, server/images, configs, resources, attempts/cold-warm/denominators và candidate/comparator SHAs trước scoring. Tất cả admission paths qua F16, không default-path bypass. Nếu thiếu một binding thì không chạy final scoring.

**Chốt ngưỡng bằng protocol đã duyệt, không hỏi từng con số:** các số dưới là **sàn kỹ thuật R4 đề xuất trong D8**, chưa phải business SLO hay kết quả đã đo. Reviewer pin baseline/eligible set/scorer trước held-out; được siết thêm theo baseline tốt hơn, không derive xuống dưới sàn theo development yếu. Duyệt đúng revision R4 là duyệt cả bảng này một lần:

1. Hard gates: 0 unauthorized/stale/mixed-snapshot deliveries; 0 accepted known wrong-number/unit/polarity/source-swap và false-absence trên safety subset; 100% mandatory concise/paraphrase/citation-after-period positives không bị false-reject; 100% emitted citation/source offsets và statement mappings hợp lệ. Unknown/error không tính là correct answer. Các gate này kiểm trên finite suite, không là bảo đảm mọi đầu vào tương lai.
2. Retrieval quality: paired macro Recall@8/Recall@100, nDCG@10/MRR của full candidate không thấp hơn legacy comparator trên cùng development/final evaluable sets và universe, **đồng thời đạt bảng sàn bên dưới**. Numerical comparison chỉ cho phép floating-rounding tolerance đã pin, không margin ngữ nghĩa tự chọn. Quantization: absolute nDCG@10 loss ≤0.01 bits4 so với float32 HNSW, giữ ranking/query layers khác cố định. Báo ablations dù comparator thua; không bắt từng optional comparator thắng mọi metric.
3. PDF/answer quality: reviewer chốt source units, required facts/groups và baseline eligible sets trước đo. Candidate phải đạt cả sàn và không kém baseline trên cùng eligible set; metric hướng cao dùng `max(sàn, baseline)`, metric lỗi hướng thấp dùng `min(trần lỗi, baseline)`. Baseline không evaluable phải bổ sung labels trước freeze, không lấy baseline0 để tự PASS. Mọi primary stratum và native/scan/mixed category báo riêng; critical-case failure vẫn chặn release dù macro tốt.
4. Resource/latency: same hardware/workload, p95 full pipeline candidate ≤ min(90s, baseline full-pipeline p95 +15s), phần +15s là envelope verifier D5; legacy baseline cũng chạy thật với phase/calls tường minh. PDF ≤60s/512MiB theo D2, process kill/cleanup bắt buộc. Báo p50/p95/RAM/disk/throughput/calls của mọi required comparator; không suy tốc độ từ async/mocks. Đây là **ngưỡng kỹ thuật R4 đề xuất**, không phải business SLO đã tồn tại. Không đủ observations hoặc baseline không chạy được thì resource gate chưa đạt, không tự bỏ comparator.
5. Báo paired per-case deltas và uncertainty theo scorer policy pin (bootstrap 1.000 repetitions, fixed seed trong manifest, case-level resampling); uncertainty chỉ mô tả độ chắc của mẫu, không đổi hard gates hoặc tự tuyên bố significance. Failed/missing/N/A tách rõ; không loại candidate errors khỏi denominator để tăng quality. Gói freeze phải ghi exact numeric baseline/derived thresholds từ các công thức trên trước final scoring; **sau khi owner duyệt** D7/D8, reviewer được chốt theo protocol mà không cần hỏi lại từng số.

| Metric và mẫu số chốt trước chạy | Sàn/trần tuyệt đối đề xuất |
|---|---|
| Retrieval trên mọi câu gold có ít nhất một relevant chunk, authorized fully judged universe; macro từng query, Recall denominator là toàn relevant universe | nDCG@10 ≥0.85; MRR (first relevant rank trong top100, miss=0) ≥0.90; Recall@8/@100 giữ điều kiện không kém baseline. Báo thêm ceiling `min(K, R)/R` khi có R relevant chunks, không đặt raw Recall@8 gần1 khi R>8 rồi sửa judgments để đạt. Queries không có relevance là nhóm Q6, không gán Recall=1 |
| Supported complete answer: số câu trả lời đủ mọi facts/conditions/required groups, đúng nguồn và citations, chia **toàn bộ câu gold answerable** | ≥90% toàn bộ; ≥80% trong từng primary stratum có câu answerable. Refusal/clarification sai, error, timeout, UNKNOWN hoặc trả thiếu tính 0, kể cả verifier từ chối một đáp án có thể trả lời |
| Required-group completeness: số nhóm có đầy đủ source-supported facts/conditions và citation, chia toàn required groups của câu answerable; báo thêm macro theo câu | ≥95% toàn bộ; ≥90% từng primary stratum có nhóm answerable; macro theo câu cũng ≥95%. Không dùng heading/filler làm nhóm hoàn tất |
| Factual/citation precision: từng factual statement đã phát phải được source-review hỗ trợ, đủ number/unit/polarity/conditions; offsets/aliases đúng nguồn | 100% trên suite; ít nhất một unsupported statement hoặc sai mapping chặn gate. Không có output không tự PASS: answer-rate gate riêng vẫn áp dụng |
| Q6: outcome FOUND/VERIFIED_ABSENT/UNVERIFIED/AMBIGUOUS đúng source gold, chia toàn groups được gán outcome; suite phải có ít nhất 2 groups mỗi outcome | ≥95% tổng; 100% safety subset, 0 false-absence và 100% mandatory FOUND positives, gồm Top-K rỗng nhưng nguồn có chương/fact. Không chuyển lỗi hệ thống thành absence |
| Extraction fact accuracy và table-cell accuracy: đúng giá trị/đơn vị/điều kiện và source anchor, chia source units bắt buộc đã gán nhãn | Mỗi metric ≥95% tổng và macro theo PDF; ≥90% mỗi category native/scan/mixed có liên quan; critical facts/cells 100%. Ít nhất 100 fact units, 50 cells trên ≥3 PDF có bảng; missing source output tính sai, không bỏ PDF extraction failure |
| Transcription so raw-source transcription độc lập, normalization/tokenization version pin trước chạy; toàn text regions đã gán nhãn | CER ≤2%, WER ≤5%; missing text tính deletions, thừa text tính insertions; báo tổng và từng native/scan/mixed, mỗi category đều phải đạt. Không dùng candidate text làm reference |
| Reading order và hierarchy so source graph độc lập: đúng directed order pairs / toàn labeled pairs; parent-child edge precision/recall/F1 trên labeled graph | Order accuracy ≥95%; hierarchy F1 ≥0.90. Ít nhất 50 order pairs và 20 hierarchy edges, mỗi loại trải trên ≥3 PDF; missing edges là false negatives, thêm sai là false positives |

Tất cả tỉ lệ dùng counts nguyên gốc và phép chia chưa làm tròn; với N cases cần `ceil(sàn × N)` successes. Báo numerator/denominator và phân phối theo strata; thiếu mẫu số bắt buộc hoặc source labels chưa duyệt là **chưa đủ bằng chứng**, không N/A để né gate. Có primary stratum không mang answerable/region loại đó chỉ được loại khỏi metric tương ứng nếu reviewer đã xác nhận trước freeze; vẫn phải qua outcome/safety metric thích hợp. Các minimum dataset/observation counts là yêu cầu đủ bằng chứng, không phải giới hạn số lượt AI hoặc số vòng thực hiện.

Một final result dùng toàn bộ case manifest, không cherry-pick. Thấy held-out rồi sửa candidate → chạy development lại, freeze RC mới và gold mới với reviewer. Không giới hạn số RC hay vòng sửa; tiếp tục phân tích, sửa và kiểm chứng tới khi đạt. Nếu có blocker thực về quyền, dependency hoặc tính khả thi, giao evidence và quyết định cần thiết, giữ phần chưa đạt để tiếp tục sau khi gỡ blocker; không bỏ nhiệm vụ vì số lượt gọi hoặc “nghiệm thu có điều kiện” để đóng lỗi.

#### B. Ma trận 29 IDs và G3–G8

Mọi row phải có owner HEAD, regression node IDs/command+exit/count, CI subject, actual runtime scenario/capture khi cần, semantic labels và reviewer disposition. Không đánh PASS chỉ vì có code hoặc một test cùng tên. Inventory cố định: `N01, F01–F25, R2-N02, R2-N03, R3-N04` =29 IDs.

| Gate | Điều kiện đủ trên RC mới | IDs trọng tâm / phụ thuộc |
|---|---|---|
| G3 | Native/table/mixed source truth, provenance/offset/PG round-trip, page-bounded cap, Cloudflare-only OCR; hard timeout/memory/cleanup thật Windows và Linux | F03/F24 đóng; F01/F02/F04/F20/R2-N02 không hồi quy |
| G4 | Fresh text/PDF/CLI/backfill → durable corpus transition → đủ verified receipts → atomic PG heads; 3 modes, PG expected vectors, exact collection/query/IDF wire; scale/ANN + S4 matrix hợp lệ | F05/F23 đóng; N01/F06/F07/F11/F19/F25 giữ; phụ thuộc G3 |
| G5 | Persisted, digest-verified v2 statistics đúng serving snapshot; S4 v1→S5 v2 upgrade/replay/crash/rollback và fresh workers/archive/reprocess không stale; numerical SDM và phrase comparator/matrix | F08 đóng; v1 immutable, không recompute Top-K; phụ thuộc G4 |
| G6 | Unified provider lifecycle/envelope/fallback, bilingual quality, bounds 100→5/3000, real usage and ablation | F09/F10/R2-N03 giữ; G4/G5 và accepted provider capability/quota |
| G7 | Mọi search/source read/provider/persist/delivery cùng authorized snapshot; fair variants/cardinality; canonical Q6 recovery; statement/span verifier với true positives/negatives và held-out quality | F13/F14/F18/R3-N04 đóng; F12/F15/F22 giữ; G3–G6 |
| G8 | Admission fail-closed; đủ actual stack journeys, security/fault/rebuild/rollback, matrices, semantic/runtime/CI exact RC; independent source/gold/roles/criteria approved, đủ sàn §14.6A và dependency evidence §14.6D; runbook command thật và target packet | F16/F17/F21 đóng; all29 disposition và G3–G7; owner RC acceptance riêng |

F17/G8 không đóng bằng21 helper contract tests; cần actual selected/executed scenario IDs và raw captures. Dependencies #148/#150/#158 xử lý theo capability/mốc/authority ở §14.6D, không đánh đồng Issue OPEN với mọi capability đều thiếu hoặc Issue CLOSED với evidence đúng RC. Phụ thuộc bắt buộc chưa đủ vẫn chặn gate, không mở rộng R4 thành implementation dự án đó. CI green, local tests, runtime verified, AI quality, reviewed, owner accepted, merged và deployed là các trạng thái riêng.

#### C. Gói nghiệm thu cuối để owner quyết định một lần

Anti gửi một packet trong #153/PR, gồm: (1) D1–D8 approval đúng revision; (2) code/PR/base/CI subjects và clean checkout; (3)29-ID matrix cùng raw tests; (4)G3–G8 evidence/limitations và từng capability disposition §14.6D; (5)gold/source/scorer/criteria hashes, role/access/contamination records và review authority; (6)runtime/model/usage/$0/account evidence; (7)security/lifecycle/rebuild/rollback captures; (8)merge order và exact target rollout proposal. Mọi command phải copy được từ runbook thật, secrets chỉ là backend env references.

Target proposal lấy từ existing operator/deployment records bằng read-only discovery; ghi host/environment/resource IDs, build/config/migration/backfill order, backup/restore scope, health/smoke/observation và rollback triggers đã derive trước scoring. Thiếu target được giao thì nói rõ; không tự thay bằng public demo. Owner cần ra **một lệnh cuối cụ thể** cho nghiệm thu RC và merge/cutover đúng target. Quyền này không được suy từ việc duyệt thiết kế R4.

Trước lệnh cuối: trạng thái cao nhất là “đủ bằng chứng trình nghiệm thu RC, chưa merge/deploy”. Sau lệnh: thực hiện sequential merge #216→#221, verify merge candidates/required CI, triển khai và post-deploy theo frozen packet. Nếu merge resolution hoặc target config đổi behavior/subject thì revalidate gates bị ảnh hưởng; không dùng CI/runtime của SHA cũ làm bằng chứng SHA mới. Issue#153 chỉ Done khi owner acceptance và post-deploy requirements của frozen S8 thực sự hoàn tất.

#### D. Phụ thuộc ngoài scope và đường tới nghiệm thu toàn phần

Đọc lại GitHub ngày 24/10/2026: [#148](https://github.com/NhiBuaa/knora-agent/issues/148), [#150](https://github.com/NhiBuaa/knora-agent/issues/150), [#158](https://github.com/NhiBuaa/knora-agent/issues/158) đều OPEN, `assignees=[]`. Đây là snapshot điều phối, không kết luận mọi phần code đều chưa làm. **NhiBuaa là owner quyết định phạm vi/nghiệm thu; người triển khai từng phụ thuộc phải có assignment/ACK cụ thể trong Issue đó**, không tự suy Anti sở hữu cả ba. Anti sở hữu nối/kiểm chứng seam Retrieval V3 và lập packet phụ thuộc ở #153 theo Q7; không dùng runtime/credentials của owner khác.

| Phụ thuộc / capability cần phân định | Bên giao và bằng chứng tối thiểu | Anti thực hiện trong R4 / điều kiện gate |
|---|---|---|
| #148: group→Workspace authorization, membership/revoke và citation delivery nếu target thực sự tích hợp KittaChat | Owner #148 giao accepted API/schema/scope mapping, lifecycle/revoke rules, implementation subject và actual cross-service evidence; hoặc owner ghi rõ disposition cho release **không cung cấp group integration**, có target/config/surface inventory chứng minh | R4 kiểm private Workspace authorization/revoke và read-only inventory integration surfaces. Không giả group mapping bằng mock rồi claim #148. Disposition “chưa tích hợp” là bản ghi giới hạn, không phải #148 PASS. Nếu frozen requirement/target đòi group integration, G8 tiếp tục bị chặn đến khi bên #148 giao đủ; muốn giảm requirement cần owner phê duyệt delta riêng, không suy từ D8 |
| #150: retention/reference guards, purge eligibility và rebuild/rollback không làm sống lại dữ liệu đã xóa/thu hồi | Owner #150 giao policy/API/lifecycle version đã duyệt, capabilities thực sự có, exact subject và requested/processing/succeeded/failed + idempotency/reconcile/tenant evidence cho phần purge bắt buộc | Anti kiểm archive/reprocess/revoke, retained-source rebuild và guards trên disposable resources; có thể kiểm guard từ chối xóa nguồn đang được tham chiếu. Không coi guard đó là worker hard-purge, không tự viết deletion backend. Thiếu policy hoặc worker evidence mà frozen lifecycle gate yêu cầu → lifecycle/G8 chưa đạt; không đổi sang “purge simulated” hoặc tự miễn retention |
| #158/#192: incremental evaluation integration theo accepted contract, scorer inputs, run/case/attempt/trace correlation và quyền Langfuse | Owner #158 giao accepted contract/version/subject, compatible artifact schemas, scorer execution evidence và permission/export/retention disposition. Giữ Knora/Workbench là authority; dữ liệu/gold do #153 sở hữu | Anti cung cấp captured observations và source-reviewed gold/bindings qua seams đã duyệt, chạy required integrations bằng own D6 package hoặc nhận exact compatible evidence có quyền. Langfuse disabled/outage là trạng thái phải báo theo contract, không tự bật export; thiếu required semantic evidence hoặc accepted disposition → quality/G8 chưa đạt. Không làm lại integration #158 hay lấy CI #192 thay AI quality |

**Các mốc bắt buộc, không để đến cuối mới hỏi:**

1. **DEP0 — R4-0, trước external runtime/held-out:** Anti đọc Issue/PR/contracts hiện hành, lập trong #153 một bảng requirement→capability→owner/ACK→artifact/version→milestone→gate cho cả ba hàng. Ghi rõ missing owner/deliverable, target applicability và điều kiện nhận hàng; gom một packet các điểm owner cần chốt ngay khi intake bản R4 được duyệt. Có owner thực thi rồi mới ghi tên; chưa có thì ghi “chưa được giao”, không bịa assignment hoặc lấy im lặng làm ACK. Phần code/offline không phụ thuộc tiếp tục được.
2. **DEP1 — trước freeze RC:** nhận và kiểm accepted contract/schema/policy/applicability của từng capability; đối chiếu hunk/base/subject với shared readers bằng finite ACK nếu bị tác động. Thay đổi interface quay về owning stage rồi cascade; chỉ thiếu external implementation thì giữ capability pending, tiếp tục hoàn tất các phần R4 độc lập. Không thay source truth, criteria hoặc cấp thêm quyền để né blocker.
3. **DEP2 — trước đề nghị G8/RC acceptance:** chạy hoặc kiểm evidence của mọi required capability trên đúng RC/compatible pinned dependency subjects và approved target envelope; ghi điều kiện applicability đã được owner giải quyết. Mọi capability bắt buộc phải có evidence đạt, không dùng việc đóng Issue hay một comment “đã làm” thay kết quả. Nếu còn thiếu, bàn giao gói phần kỹ thuật + blocker chính xác cho owner phụ thuộc, giữ G8 chưa đạt và tiếp tục khi nhận artifact; không báo đã nghiệm thu hoặc abandon vì đã dùng nhiều lượt.
4. **DEP3 — trước merge/cutover:** kiểm lại dependency subjects/config/permissions còn khớp, không có revoke/change làm evidence cũ vô hiệu; revalidate gate chịu ảnh hưởng. Owner ra lệnh cuối trên packet đã đủ, không tự chuyển dependency pending thành waiver.

**Ba ranh giới hoàn thành:** (a) các fix R4 có code/local/CI/runtime/review evidence của riêng chúng; (b) G8 và RC đủ điều kiện trình nghiệm thu khi cả upstream gates, sàn chất lượng và required dependency evidence đầy đủ; (c) #153 Done sau owner acceptance + authorized merge/deploy/post-deploy theo S8. Đạt (a) không thay (b)/(c). R4 không cấp quyền làm thay ba dự án phụ thuộc: nếu owner chưa giao deliverables ngoài scope thì không thể cam kết một mình Anti đóng toàn #153. Packet DEP0 làm rõ việc đó từ đầu, không tạo vòng xin lại các quyết định đã duyệt.

### 14.7 Cách duyệt và bàn giao

**Approval packet đề nghị:** owner duyệt R4 §14 tại exact commit hoặc SHA256 của toàn file được đính kèm, gồm D1–D8, protocol/ngưỡng ở §14.6, quyền disposable/$0 ở §14.5 và ủy quyền reviewer D7. Duyệt plan không có nghĩa source/gold chưa tạo đã được duyệt. Approval reference được ghi trung thực trong #153/PR; nếu chỉ có hội thoại, ghi hội thoại và exact revision, không bịa URL.

Mẫu phản hồi đủ để mở execution: **“Duyệt R4 §14 đúng revision trong gói bàn giao, gồm D1–D8 và §14.5–14.6. Giao Anti triển khai và tự sửa trong phạm vi này đến khi đủ bằng chứng trình nghiệm thu; chưa cấp quyền merge/deploy.”** Có thể ghi ngoại lệ theo D-ID trong cùng một phản hồi; phần phụ thuộc ngoại lệ không được làm như đã duyệt.

Prompt gửi Anti sau khi owner duyệt:

> Đọc R4 §14 trong `docs/plans/2026-10-22-retrieval-v3-review-remediation.md` ở worktree `C:/Developer/Projects/knora-agent-worktree/docs-retrieval-v3-acceptance-remediation` và exact revision/approval trong gói bàn giao. Dùng executing-plans, xử lý 12 điểm mở tại đúng stage rồi sync #216→#221; giữ29-ID regression, không làm lại S2. Ngay R4-0 chốt dependency packet DEP0 và vai trò giữ/chạy gold độc lập. Tuân thủ D1–D8, immutable v1→v2 upgrade, sàn chất lượng và disposable/$0 đã duyệt; không giới hạn tổng lượt AI/RC/vòng sửa, tránh chạy lãng phí. Tự sửa/test/CI/runtime/review tới đủ G3–G8; thiếu external capability thì giữ gate chưa đạt và tiếp tục phần độc lập. Ghi evidence ở #153/PR, chỉ gom hỏi khi vượt scope/quyền hoặc bất khả thi có bằng chứng. Giao một packet nghiệm thu + rollout proposal cuối; chưa merge/deploy nếu chưa có lệnh owner.

**Tự rà soát plan (24/10/2026):** 12 điểm mở đều có owner/task/contract và exit evidence;17 regression được map trong29 IDs; các delta engine/calls/permissions/gold/thresholds nêu rõ để duyệt. Không sửa7 frozen plans/S2, không tạo evaluation authority mới. Research không phải prototype/CI/runtime proof: exact-model JSON, parser fidelity, pinned Qdrant IDF/quantization và platform hard-limit còn phải qualification bằng task đã chỉ. Không che các rủi ro đó bằng lời hứa “giao một lần chắc chắn Done”.

**Điều chỉnh sau review plan:** điểm1 có capability/owner/evidence/mốc DEP0–DEP3 và phân biệt fix-ready/G8/#153 Done (§14.6D, R4-0/12); điểm2 có sàn tuyệt đối, công thức so baseline và mẫu số/error semantics (§14.6A/Gates); điểm4 có v1/v2 upgrade/CAS/receipt/compatibility/rollback và test DB S4 có dữ liệu (§14.3B, R4-5/G5); điểm5 có curator/reviewer/runner độc lập, quyền artifact/access/two-phase freeze và admission (§14.2D7, §14.6A, R4-0/10). Điểm3 giữ đúng điều chỉnh owner: không áp trần tổng AI calls/journeys/RC/vòng sửa; chỉ giữ per-request/resource safety và $0 (§14.5). Đây là thay đổi thiết kế chờ duyệt đúng revision, không phải evidence các gates đã đạt hoặc dependencies đã được giao.

## 15. R5 — Hoàn tất các hợp đồng còn thiếu sau review R4

### 15.1 Đầu vào, phạm vi và nguyên nhân chưa đạt

**Ngày đối chiếu:** 24/10/2026, Asia/Saigon. Đây là kế hoạch sửa, không phải một lần chạy lại nghiệm thu. Read-only đối chiếu lại local/GitHub cho thấy sáu PR OPEN, HEAD khớp, các worktree sạch và base vẫn nối tuần tự như bảng dưới. Những kết quả probe/test ở review R4 là đầu vào lịch sử tại các HEAD này; không coi thao tác soạn R5 là đã chạy lại tests/runtime.

| Stage / PR | Worktree dưới `C:/Developer/Projects/knora-agent-worktree/` | HEAD local = GitHub |
|---|---|---|
| S3 / #216 | `feat-retrieval-v3-document-understanding` | `bbb0ac73e17833f4a9c4953d72e22724001dbc08` |
| S4 / #217 | `feat-retrieval-v3-dense-hybrid-search` | `f2947976de69cbeeaefb6a77709baa2553d4a516` |
| S5 / #218 | `feat-retrieval-v3-sequential-dependence-ranking` | `58fb759dec35efa29bd05de6ac62d4a4562aa2a1` |
| S6 / #219 | `feat-retrieval-v3-reranking-evidence` | `9d0c19bdf83b3ef846a17275509cf681edeeafcd` |
| S7 / #220 | `feat-retrieval-v3-query-understanding-coverage` | `e159bf1589d9cb22ed6edc838efdc265aa143e2c` |
| S8 / #221 | `feat-retrieval-v3-integrated-release` | `3d14936864bf23314990ca57930f75acf5adb4be` |

**Nguyên nhân chung:** Một số test chỉ kiểm helper hoặc tên tính năng, trong khi đường chạy thật chưa thực hiện hợp đồng đã thiết kế. Ví dụ: transition nhận danh sách thiếu member; test child completion có callback `pass`; readback tin digest do Qdrant trả; kiểm resource ở extractor cũ; runtime suite dùng hits tổng hợp. R5 yêu cầu chứng minh từ đầu vào ứng dụng đến trạng thái/đầu ra thật, đồng thời kiểm ca đúng không bị loại nhầm.

**Chọn phương án:** Tiếp tục thiết kế và seams §14, hoàn thành các lát cắt xuyên application/store/provider/runtime. Vá assertion riêng lẻ không đóng được lỗi authority; viết lại retrieval/evaluation thành hệ thống khác tăng phạm vi và phá bằng chứng lịch sử. Không thêm orchestration, model local, evaluation authority hoặc làm lại S2.

#### Inventory cố định và tiêu chí đóng

| ID còn mở | Owner | Phản ví dụ/thiếu sót phải loại bỏ | Task R5 |
|---|---|---|---|
| F03 | S3 | Native vẫn là text phẳng; OCR từng XObject rồi append, thiếu table/reading order/geometry thật; confidence mặc định 1.0 | 1 |
| F24 | S3 | Memory budget cực nhỏ và deadline đã hết vẫn có thể thành công ở đường Docling/native hiện hành | 2 |
| F05 | S4 | Text/CLI còn profile giả hoặc thiếu; transition thiếu member vẫn activate, sinh corpus trộn profile | 3 |
| F23 | S4 | Vector khác PG nhưng thiếu/giả payload digest vẫn có thể nhận receipt | 4 |
| F08 | S5 | Cache theo profile digest trả statistics cũ khi membership đổi; statistics chưa là snapshot PG immutable đầy đủ | 5 |
| F13 | S7 | Recovery vẫn dựa BM25/catalog không đủ identity/coverage; chưa đọc nguồn canonical để phân định Q6 | 8 |
| F14 | S7 | Bag-of-words chấp nhận sai đơn vị/phủ định hoặc số ở single-intent; loại nhầm đáp án ngắn/citation sau dấu chấm | 9 |
| F18 | S7 | Variants chiếm slot của required groups; batch thiếu vectors bị broadcast; cần giữ inner pool cap | 7 |
| R3-N04 | S7 | Chưa capture snapshot trước mọi search; recovery/empty result và thay đổi quyền giữa các phase chưa được fence đầy đủ | 7–9 |
| F16 | S8 | Default loader có fallback sample; approval/hash chưa đủ để admission bản release mới | 10 |
| F17 | S8 | Helpers/JUnit/synthetic hits được dùng thay actual stack journeys và semantic evidence | 11–12 |
| F21 | S8 | Runbook gọi factory/settings sai, chỉ in config; chưa chứng minh rollout/rebuild/rollback qua seam thật | 11 |

**17 ID chống hồi quy:** `N01, F01, F02, F04, F06, F07, F09, F10, F11, F12, F15, F19, F20, F22, F25, R2-N02, R2-N03`. Trạng thái PASS của review trước chỉ có hiệu lực trong phạm vi bằng chứng trước; phải kiểm lại tại RC mới. Giữ registry 29 ID lịch sử, không đổi nghĩa để khớp tên test.

| ID mới, P2 | Owner | Điều kiện đóng |
|---|---|---|
| R5-N01 | S4 | Sửa test configuration đang đòi candidate pool 8 cho hybrid đã chốt 100; kiểm bảng từng config, không thay mọi số 8; legacy/top8 output giữ đúng contract |
| R5-N02 | S7 | Sửa collision basename hai `test_query_planning.py` tại owning stage, cập nhật mọi runner/selection; pytest mặc định collect được cả answering và LangChain; giữ rename đã có ở S8 |
| R5-N03 | S8/docs | Sửa registry/evidence mapping và báo cáo thay thế cho ledger sai ID/plan SHA hoặc claim PASS ngoài scope; giữ bản ghi lịch sử, không sửa hồi tố approval |

R5 có **32 disposition = 29 lịch sử + 3 mới**, không phải 32 lỗi code đang mở. F19 giữ nghĩa scorer; F20 giữ nghĩa gold/hash; R2-N02 giữ nghĩa derivation/profile identity; R2-N03 giữ nghĩa reranker test collection. Bằng chứng Qdrant wire, page cap, bbox hoặc timeout không tự đóng bốn mục đó. Mỗi row cần requirement gốc → production entrypoint → test node/scenario → subject → kết quả/giới hạn.

### 15.2 Nghiên cứu bổ sung và các quyết định thực thi

Kế thừa D1–D8, toàn bộ ngưỡng và mẫu số §14.6A, các giới hạn mỗi request §14.2 và protocol DEP0–DEP3. R5 không hạ ngưỡng theo baseline, không đặt lại ngân sách tổng. Bổ sung các quy tắc dưới để Anti tự giải quyết kỹ thuật trong phạm vi được duyệt:

1. **PDF native:** Dùng chars/words/cells geometry của [pdfplumber](https://github.com/jsvine/pdfplumber/blob/stable/README.md); page/crop render bằng PDFium, serial trong child process vì [PDFium không an toàn khi gọi đồng thời nhiều thread](https://pypdfium2.readthedocs.io/en/stable/python_api.html). Pin source/wheels/transitive dependencies cho Windows/Linux, không cài Docling ML. Chưa có source label thì chưa được claim table/reading-order fidelity.
2. **OCR:** Qualify đúng model/endpoint/envelope đang cấu hình bằng public/synthetic development crops trước khi khóa parser. Caption/Markdown không chứng minh OCR đầy đủ hoặc cell geometry. Chỉ nhận trường response được adapter contract pin; missing/truncated/unknown shape phải thành incomplete/error. Confidence không có là `None`; chỉ giữ crop-level bbox nếu model không trả geometry đáng tin. Không có quyền tự đổi model/provider hoặc chạy local để cứu gate; model hiện có không đạt sau qualification thì gom báo cáo bất khả thi kèm phương án Cloudflare/$0 cho owner, tiếp tục các task độc lập.
3. **Hard limits:** Tái sử dụng handshake trong `_pypdf_process.py`: child đợi lệnh start, parent cài limiter rồi mới cho parse. [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) và [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) có semantics khác RSS: ghi rõ committed/virtual/process-tree limits, peak RSS là số đo riêng. Linux `RLIMIT_AS` đơn lẻ không chứng minh tree budget. Thiếu hard-limit capability thì lỗi có kiểu, không chạy vô hạn. Dùng absolute wall deadline ở parent cho parse/render/network/assembly, không lấy CPU-time thay wall-time.
4. **Qdrant:** Contract theo [OpenAPI v1.19.2](https://raw.githubusercontent.com/qdrant/qdrant/v1.19.2/docs/redoc/master/openapi.json), không API master hoặc defaults. Qualification phải xác nhận actual server build, collection readback và query payload; `rescore/oversampling` thuộc query quantization, IDF corpus thuộc query params. `bits4` trong JSON chỉ là implemented, chưa chứng minh ANN quality. Expected vector lấy PG, so float32/Cosine theo §14.3C.
5. **Verifier:** [Exact model gpt-oss-20b](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/) là Cloudflare-hosted; schema support phải qualify ở exact route/model bằng request/response thực. Strict local validation vẫn bắt buộc; model verdict không thay auth/source identity hoặc human/source-reviewed gold. Nếu contract không đáp ứng thì giữ gate chưa đạt; không fallback keyword để ghi supported.
6. **Chi phí:** [Cloudflare Free allocation](https://developers.cloudflare.com/workers-ai/platform/pricing/) có giới hạn nhà cung cấp. Không giới hạn tổng AI calls, tổng journeys, số RC hoặc vòng sửa. Hết Free quota thì lưu checkpoint và tiếp tục phần offline/chờ quota phục hồi; không bật Paid, không bỏ việc, không chuyển local. Dedupe input/config không đổi, lưu calls/outcomes và chạy lại theo giả thuyết; safety limit mỗi request giữ nguyên §14.5.

Các tài liệu này hỗ trợ lựa chọn thiết kế; không thay qualification/test/runtime. R5 không cho phép mặc nhiên coi Cloudflare-hosted là $0: vẫn cần account/route/usage evidence của D6.

### 15.3 Hợp đồng bàn giao giữa các task

Đọc đầy đủ §14.3A–G trước sửa. Đây là yêu cầu bổ sung cho các giao diện đích đã định nghĩa tại đó; tên mới là đề xuất, không phải claim API đã tồn tại.

| Sản phẩm / owner | Bên nhận | Bất biến phải kiểm tại boundary |
|---|---|---|
| Canonical structure + parser/options identity / S3 | PG finalize, chunking, S4 và source reader S7 | Physical page/crop transform/origin/offset/coverage thật; LF hashing pin; mọi chunk ≤650 tokens và không xuyên trang; một trang dài được nhiều chunks |
| Snapshot v1 + receipt / S4 | All producers, serving, S5 | Membership lấy toàn bộ canonical PG trong transaction; profile/stats/schema digests immutable; `commit_corpus_transition(snapshot_id, expected_revision)` không tin caller list |
| Snapshot v2 / S5 | SDM/S6/S7 | Statistics đúng toàn membership, tokenizer policy và active head; v1→v2 tạo ID/digest mới, không mutate/copy nhãn receipt; không tính frequencies trong HTTP request |
| `RetrievalReadSnapshot` / S7 | Every retrieve/recovery/rerank/generate/verify/persist/delivery | Capture trước search, snapshot identity bắt buộc kể cả empty; hydrate PG; validate từng result trước provider; revoke/change thì abort, không union generations |
| `CanonicalSourceRead` / S7 | Q6/group evidence | Exact scope/version/checksums, cursor/exhaustion/coverage; FOUND có factual content; absence cần chứng minh đầy đủ đúng scope; budget/error/partial→UNVERIFIED |
| Answer projection + support verdict / S7 | HTTP/SSE/Conversation | Answer digest, statement ranges/group IDs/source quote offsets có kiểu; tất cả factual statements supported, mọi required group complete; không phát answer trước validation |
| Release admission + raw observations / S8 | Existing evaluation/runtime/owner | Bind code/config/images/dependency subjects/source/gold/scorer/criteria; raw scenario IDs và executed coverage; UNKNOWN/helper-only không PASS |

**Cách báo lỗi đã chốt:** Giữ public error envelope hiện hành. Projection/serving mismatch đi qua lỗi retrieval unavailable hiện hữu; input/output model sai đi qua invalid-generation contract hiện hữu; provider timeout/quota là operational failure, không đổi thành “tài liệu không có”. Internal reason enums phân biệt snapshot stale, incomplete source, verifier unavailable và invalid verdict. Nếu public enum còn thiếu, thêm versioned mapping cùng HTTP/SSE/Conversation readers/tests trong đúng task; không lén thay semantics enum cũ hoặc gửi answer tạm. AMBIGUOUS trả clarification không tiết lộ unauthorized source. REFUSAL/Q6 absence chỉ dùng khi proof tương ứng đủ, không dùng làm vỏ cho outage.

**Thứ tự thực hiện:** R5-0 → S3 (1→2) → S4 (3→4) → S5 (5) → S6 (6) → S7 (7→8→9) → S8 (10→11→12). Intake gold/dependencies ở task0 chạy sớm; final held-out chỉ sau freeze. Mỗi owner commit fix và sync lần lượt mọi downstream trước giao gate; không chỉ vá S8. G6 vẫn cần G4/G5, dù không có ID code mới ở S6.

### 15.4 Các task thực hiện

**Chu trình bắt buộc cho từng task:** đọc callers và fixture safety → thêm ca đỏ từ production boundary → lưu command/exit/error cho thấy đúng lỗi → sửa toàn callers/config/schema/docs chịu ảnh hưởng → chạy ca đỏ thành xanh và true-positive → scoped regression/format/check → review diff/commit → cascade và kiểm tại downstream. Các test pseudocode bên dưới mô tả assertions; implementer phải định nghĩa fixture từ raw input/PG/app seams, không stub phần đang cần chứng minh. Không sửa gold/expected output để né lỗi.

Lệnh Python dùng checkout guard §12.3, interpreter và dependency lock đúng worktree; CI là Python3.12. Với mỗi module mới phải thêm path vào các selections hiện có, không tạo runner song song. Test DB/process/container chỉ chạy trong package D6 đã duyệt, không dùng DB đang giữ dữ liệu của người dùng.

#### R5-0 — Intake và dựng ma trận bằng chứng trước khi sửa

**Owner:** Anti điều phối; dùng tài liệu này và #153/PR, không tạo ledger mới. **Kế thừa:** R4-0, §14.6D.

- [ ] Recheck từng worktree/branch/dirty/HEAD/base/GitHub, plan revision và approval reference; giữ unrelated files. HEAD đổi thì đọc delta và cập nhật pin, không reset về bảng §15.1.
- [ ] Tạo 32-row matrix trong PR theo registry §15.1; đưa 12 ID mở + 3 mới vào hàng cần sửa, 17 mục vào regression; cột code/local/CI/runtime/quality/review/accepted tách riêng. Chưa chạy ghi chưa kiểm chứng, không tự PASS theo tên test.
- [ ] Đọc hai probe lịch sử `C:/Users/NhiBuaa/AppData/Local/Temp/retrieval_v3_r2_review_probes_20261023.py` và `retrieval_v3_r3_additional_review_probes_20261023.py`. Đưa các phản ví dụ phù hợp vào test phát triển có version tại owning stage; không chạy nguyên script có write side effects hoặc dùng Temp làm dependency. Giữ raw probe output trước và sau fix.
- [ ] Hoàn tất DEP0 và phân vai D7 từ đầu. Freeze source facts/criteria độc lập trước nhìn candidate; bind chunk/relevance khi RC frozen theo §14.6A. Thiếu owner/contract/permission ghi chính xác một packet sớm, tiếp tục phần độc lập.

**Exit:** Scope/pins/32-ID registry/counterexample inventory và gói dependency/roles có thể review. Không nhận ledger tự khai làm bằng chứng duyệt.

#### R5-1 — Extraction có native geometry và OCR provenance thật

**Owner S3/#216. Files/callers/tests:** R4-1 và §14.3A/G; dependency lock, parser resolver/submission, cả hai PG finalization paths. Mở rộng `backend/test/adapters/pdf/test_docling.py`, provider PDF tests và structure/chunk/job tests hiện hữu. Parser identity mới theo §14.3G, không relabel derivation cũ.

- [ ] Thêm fixtures native hai cột/bảng, mixed native+scan, repeated text, rotated/cropped page và tiled/composed image. Source-reviewed expected anchors/cells/order lấy raw PDF, không lấy parser output làm expected.
- [ ] Thực hiện native geometry → composed render có transform → Cloudflare OCR → assembly theo reading order; source page/region/hash do host cấp, model không tự cấp identity. Không append OCR sau toàn native text hoặc tìm offsets bằng `find()` trên repeated text.
- [ ] Kiểm schema/coverage/truncation từng provider response, thiếu confidence giữ `None`; chỉ cell bbox có bằng chứng mới lưu. Typed incomplete không activate derivation hoặc cho Q6 absence. Round-trip structure/origin/offsets qua serialize/PG reload và citation reader.
- [ ] Ca bắt buộc: native-table có cell giá trị/đơn vị/bbox thật; mixed regions đúng origin; duplicate text không trỏ nhầm; crop/rotation map đúng physical page; trang dài tách nhiều chunks đúng token cap. Legacy pypdf identity/result không đổi.

**Exit:** F03 hết phản ví dụ ở application/PG path, F01/F02/F04/F20/R2-N02 regression; G3 fidelity vẫn cần source-gold metrics và runtime task11.

#### R5-2 — Hard resource budget trên chính extractor mới

**Owner S3/#216. Files:** R4-2, shared `_pypdf_process.py`/limiter, new native driver và provider timeout. Không viết supervisor thứ hai.

- [ ] Dùng child start-handshake hiện có, install limits trước parse/render; native dependencies chỉ làm việc sau handshake. Mọi IPC frame, render pixels và assembled output có bound §14.2D2.
- [ ] Parent giữ deadline tuyệt đối, check trước/sau từng phase và trước accept result; OCR/conversion nhận remaining timeout. Cancellation cấm dispatch tiếp; kill/join/close/unlink verified. Không hứa remote call đã gửi sẽ không tính usage.
- [ ] Thêm actual native-driver tests: memory limit cực nhỏ không được thành công; provider trả sau deadline dù payload hợp lệ vẫn thất bại; parse/render child treo bị kill; oversized output, cancellation và concurrent jobs không rò process/handle/temp. Kiểm fake-provider chỉ trong contract tests; hard OS limit phải có actual process evidence.
- [ ] Chạy Windows và Linux hard-limit/cleanup suites trên resources được giao; Linux không có cgroup delegation phải fail closed. Tách peak RSS observation khỏi memory-limit semantics trong report.

**Exit:** F24 có evidence đúng driver mới trên cả hai OS, legacy pypdf regression xanh; không nhận test chỉ chạy extractor cũ.

#### R5-3 — Corpus transition toàn membership, durable và atomic

**Owner S4/#217. Files/callers:** R4-3; `main.py`, text/PDF finalize, CLI/backfill, archive/reprocess, jobs routing, PG tables/store và additive Alembic migration. Tests: `test_corpus_statistics_transition.py`, text indexing/PDF finalization/CLI/config/application suites.

- [ ] Thêm immutable `lexical_corpus_snapshots`/`lexical_corpus_heads` v1 và durable `corpus_reindex` theo §14.3B. Authoritative membership capture từ PG, không caller-provided items. Profile đổi restage toàn corpus; parent thật đọc canonical chunks/embeddings, tạo đúng một index child/document.
- [ ] Mọi producer vào cùng transition seam; bỏ avg_len256/digest zero/UUID-desc selection và `profile=None` cho route V3 mới. Counter native model-free được package/reproducible build như D3; không regex/tiktoken giả BM25 parity. Empty corpus có snapshot count0 riêng.
- [ ] `commit_corpus_transition(snapshot_id, expected_revision)` kiểm đủ receipts của exact manifest và CAS mọi source/head revisions trong một transaction; child chỉ hoàn tất receipt. Fault giữa hai member updates phải rollback cả hai, không giữ B/A; replay/lost response idempotent, two-worker race chỉ một commit hợp lệ.
- [ ] Thay test callback `pass` bằng chạy child qua job store/processor thật trên disposable PG. Kiểm source add/remove/archive/reprocess, producer text+PDF+CLI, document>64chunks và service restart trước activation. Assert PG all heads/profile/snapshot digests cùng generation và serving sau restart, không chỉ assert method return.
- [ ] Sửa R5-N01 tại `backend/test/answering/test_retrieval_configuration.py`: bảng expected theo exact config ID; hybrid candidate100, final top8/evidence5 giữ riêng; legacy configs immutable. Chạy toàn module, không `-k` né assertion cũ.

**Exit:** F05/R5-N01 đóng bằng end-to-end producer + PG transition; Alembic một head với ancestry đúng. Head hiện tại S3 `20261022_0158`, S4+ `20261021_0157` là lịch sử đầu vào; additive migration mới được phép đổi head ID, không ép giữ `0157` bằng xóa migration/data.

#### R5-4 — Receipt so vector từ PG và đúng collection/query wire

**Owner S4/#217. Files/tests:** R4-4; PG generation/embedding-set loader, Qdrant dense/native adapters và tests, receipt/CAS consumers.

- [ ] Load exact embedding manifest từ PG, reject missing/mixed/config/dimension mismatch. Stage và readback tất cả members `with_vector=True`, so ordered identities + server-equivalent float32/Cosine vectors theo policy pin.
- [ ] Ca đỏ phải gọi production stage/readback method với PG expected manifest: vector thay toàn phần, đảo chunk vectors, thiếu vector, missing digest và forged digest. Cả hai digest cases phải reject khi vector sai; vector đúng có normalization/float rounding hợp lệ phải pass. Test query parser riêng không chứng minh readback.
- [ ] Bind receipt version/snapshot/membership/profile/embedding/comparison policy/server/collection/count/capture hash; CAS từ chối thiếu hoặc receipt khác generation. Không lấy hash trên remote payload làm expected authority.
- [ ] Qualify pinned-server collection readback, bits4 và query rescore/oversampling; filtered IDF scope ở sparse và hybrid prefetch. Decoy foreign/staged/historical points không đổi population dùng tính IDF. Actual ANN comparator/quantization quality ở task11, không bằng synthetic hits.

**Exit:** F23 đóng; F06/F07/F11/F19/F25 regression theo đúng nghĩa gốc; contract wire pass chưa tự bằng ANN/quality PASS.

#### R5-5 — Persisted SDM statistics, không stale cache

**Owner S5/#218. Files/tests:** R4-5; lexical population/statistics builder, PG reader/store, sequential dependence/module và shared producer routing.

- [ ] Builder ngoài request tạo v2 từ canonical full membership, counts/window frequencies/tokenizer policy/digests; persist immutable. Serving reader nhận expected snapshot, đọc head từ PG mỗi request; bỏ correctness dependency vào global cache `(workspace, profile_digest)`.
- [ ] Implement v1→v2 upgrade và rollback §14.3B trên DB có dữ liệu S4. Same profile nhưng membership 1→2 phải đọc statistics mới; worker mới và worker đang chạy phải cùng kết quả. Không đổi v1 bytes hoặc reuse receipt bằng đổi nhãn.
- [ ] Ca numerical so expected corpus frequencies từ raw canonical fixture, không Top-K. Bao gồm archive/revoke/reprocess, cross-workspace, unknown schema, corrupt digest, crash/replay, concurrent CAS và fresh restart. Missing stats fail closed ở SDM; S4 mode chỉ tiếp tục khi snapshot còn authorized và compatible.

**Exit:** F08 đóng ở PG integration và application scoring; F09/F10 không hồi quy qua downstream. Không acceptance bằng test in-memory builder riêng.

#### R5-6 — Nhận upstream tại S6 và giữ reranker/fallback

**Owner S6/#219. Files/tests:** R4-6; các caller/trace decoder bị ảnh hưởng bởi snapshot, reranking/MMR/lifecycle suites.

- [ ] Cascade S3→S5; default collection cùng answering/provider reranker tests, giữ rename tại owning stage. Giữ `reranking-cloudflare-bge-base-v1`, `result.response`, remapping và close/lifecycle.
- [ ] Timeout/malformed/quota/provider failure đi DBSF+SDM trên snapshot đã validate; fallback không làm sống lại candidate sai quyền/version. Candidate≤100, MMR≤5chunks/3000tokens; actual provider/ablation ở task11.

**Exit:** Regression F09/F10/R2-N03 xanh; G6 vẫn chờ G4/G5 và chất lượng thực.

#### R5-7 — Snapshot toàn request và query scheduling công bằng

**Owner S7/#220. Files/tests:** R4-7, §14.3D/G; answering stores/module/query planning/results, PG adapter, trace decoder/persist và Conversation context callers. Tests module/query models/results/evidence, dense/hybrid/BM25 và context.

- [ ] Capture immutable authorized snapshot trước search đầu tiên trong PG transaction ngắn; truyền vào mọi branch kể cả empty/recovery. Validate envelope và hydrate canonical candidates trước merge/rerank; revalidate trước mỗi external content call, persist và delivery. Không giữ transaction qua network.
- [ ] Reserve một search cho từng required group trước, rồi composite/variants round-robin tới tối đa8; max4groups, group5 clarification. Planner sử dụng resolved retrieval context; ví dụ “7 chương” → “bao gồm những chương nào?” phải truy lại đúng tài liệu với evidence mới, không lấy assistant answer làm nguồn.
- [ ] Embedding N queries đòi N vectors đúng order/dimension/finiteness/config, không broadcast một vector. Giữ merged pool100, evidence5/3000 và inner round-robin cap2, kiểm cap ngay trong inner loop.
- [ ] Actual AnswerQuestion spies/assertions: secondary search foreign document/version, empty result thiếu snapshot, recovery stale snapshot, revoke sau search/trước generator/trước verifier/trước persist/trước delivery đều chặn đúng phase, không rò source. Đáp án hợp lệ cùng snapshot vẫn pass cả sync/stream/recovery readers.
- [ ] Đóng R5-N02: tại S7 đổi model test thành `backend/test/answering/test_query_plan_models.py` và adapter thành `backend/test/adapters/langchain/test_langchain_query_planner.py` theo S8 hiện hữu; cập nhật refs/CI partition. Default pytest collect/execution không importlib workaround. Thay `endswith('-v3')` bằng registry capabilities cho IDs mới §14.3G.

**Exit:** R3-N04/F18/R5-N02 đóng; F12/F15/F22 giữ. Trace schema mới cho mọi V3 mode và readers legacy có tests, không chỉ lexical trace.

#### R5-8 — Q6 đọc lại tài liệu canonical trước khi nói không có

**Owner S7/#220. Files/tests:** R4-8; source_verification/store port/module, PG canonical source reader, structure completeness và source/stream/Conversation tests.

- [ ] Implement bounded `read_canonical_source_scope(..., snapshot, cursor, limits)` theo §14.3E, từ PG structure/chunks; scope ưu tiên explicit authorized source → Conversation context → unique authorized catalog match. Không chọn source đầu Top-K; ambiguous clarification, unauthorized không tiết lộ.
- [ ] Một pass cho missing groups trong budget D4. FOUND đọc nội dung thật, kiểm anchors và bổ sung evidence qua validator/caps. VERIFIED_ABSENT chỉ khi chứng minh đúng phạm vi; section catalog đầy đủ chỉ chứng minh section vắng, không suy fact ngữ nghĩa vắng. Partial/budget/deadline/quota/unclassified luôn UNVERIFIED.
- [ ] Ma trận bắt buộc: Top-K rỗng nhưng PG có chương5→FOUND và trả đúng facts/cites; nguồn không có chương5 với catalog/coverage đủ→VERIFIED_ABSENT; scope partial→UNVERIFIED; hai nguồn khả dĩ→AMBIGUOUS; một vế so sánh thiếu→không sinh nửa so sánh. Heading-only không hoàn tất required group; semantic keyword miss không tự absence.
- [ ] Test provider/Qdrant search unavailable nhưng canonical authorized read vẫn làm việc khi contract cho phép; lỗi canonical reader là operational failure. Không inline OCR/reprocess hoặc lấy provider text ngoài snapshot để cứu đáp án.

**Exit:** F13 hết phản ví dụ; Q6 proof và coverage trace có PG integration, không mock catalog không identity.

#### R5-9 — Kiểm sự thật theo statement/span, giữ đáp án ngắn đúng

**Owner S7/#220. Files/tests:** R4-9, §14.3F; fixed-slot composer internal projection, generation_validation/module, new answer_support port/provider, lifecycle/config, HTTP/SSE/Conversation readers.

- [ ] Composer giữ statement/group IDs và exact text ranges qua before/items/after; hash final answer, kiểm ranges/aliases phủ toàn factual body. Không cắt statement bằng dấu chấm rồi làm mất citation phía sau; public answer schema v21 giữ tương thích.
- [ ] Deterministic checks number/unit/entity/date/polarity/source spans cho mọi ANSWER kể cả single intent; whitelist conversion7days↔1week, không month↔days. Không dùng bag-of-words/count để kết luận supported. Mọi group cần factual support, không filler/heading.
- [ ] Một `AnswerSupportVerifier.verify(...)` Cloudflare20B verification-only theo D5, strict schema/digests/cardinality/source quote offsets §14.3F; no tools/rewrite/extra retry. Source/answer/question là untrusted data, không được thay system rules. Gold không vào runtime prompt.
- [ ] Parameterized negatives: wrong_number70, wrong_unit7months, negation, swapped cite, missing group, outside-evidence quote, forged offsets/digest, duplicate/missing statement, prompt injection và malformed/timeout/quota. Positives: concise đúng nguồn, citation sau dấu chấm, one-week paraphrase, multi-sentence/list đủ nguồn. Chạy cả actual AnswerQuestion/persist/stream và provider contracts; assert không phát successful answer khi verifier chưa valid.
- [ ] Invalid/UNKNOWN/unavailable giữ reason riêng và safe public error mapping §15.3, không fake “không đủ thông tin” hoặc VERIFIED_ABSENT. REFUSAL không gọi verifier, nhưng Q6 reason vẫn cần proof. Chất lượng theo source-reviewed gold, không lấy model verdict tự chứng minh đúng.

**Exit:** F14 và R3-N04 phần verifier/delivery đóng, không false-reject positive matrix. G7 còn cần held-out answer-rate/completeness/precision §14.6A.

#### R5-10 — Release admission không bypass qua default/sample

**Owner S8/#221. Files/tests:** R4-10; `evals/datasets/pdf_retrieval_release_v1.py`, manifest/schema/approval owners, release runners và loader tests.

- [ ] Route V3 release bắt buộc explicit sealed artifact hoặc canonical default có cùng admission; missing default/source/manifest/approval không fallback bốn sample. Historical sample chỉ dùng development/legacy được gọi rõ, không được báo release-ready.
- [ ] Bind source/gold/split/approval/roles/scorer/criteria/config và hashes bắt buộc theo protocol §14.6A; reject duplicate IDs, overlapping splits, source mismatch, missing hash, malformed approval hoặc unauthorized reviewer. Approval cũ đúng artifact không bị sửa hồi tố; tạo version release mới khi contract mới cần.
- [ ] Test tất cả entrypoints/runners, `enforce_approval=True`, explicit/default path, approved-but-no-hash, hash sai, contaminated set và valid freeze. Parser unit success không thay runner admission. Không hardcode owner string làm bằng chứng đã duyệt.

**Exit:** F16 đóng trên loader và release command thật; bộ4case cũ không dùng làm held-out60questions/12PDF mới.

#### R5-11 — Runtime/CI/runbook kiểm đúng ứng dụng thật

**Owner S8/#221**, code lỗi trả về owning stage rồi cascade. **Files:** R4-11; runtime launcher/tests/evidence schemas/workflow, `docs/runbooks/retrieval-v3-release.md`, actual CLI/settings composition.

- [ ] Runbook dùng symbols thật: bỏ import `create_engine_and_session_factory` không tồn tại, dùng composition hiện hành và `lexical_qdrant_url`; `retrieval_configuration_for_id` phải được resolve qua ứng dụng, không chỉ print constructed object. Kiểm actual `--help`, `--dry-run`, `--checkpoint-file`, `--batch-size`; chỉ thêm flag nếu implementation/parser/test cùng task, không viết CLI giả. Dùng config ID mới đã resolve trong §14.3G.
- [ ] Xóa việc chọn `-k ann_recall`/synthetic test như bằng chứng ANN; registry runtime phải liệt kê actual collected/executed scenario IDs và fixture kind. Tái sử dụng `backend/runtime_test/`, existing runtime profiles/runners, PG/Qdrant/app/CF thực trên namespace D6. Helper tests giữ nhãn contract-only.
- [ ] Journeys bắt buộc: text/PDF ingest→canonical PG→index→retrieve→answer/citation; all modes/query planning/follow-up; source recovery; CF reranker/verifier failure; archive/reprocess/revoke/tenant isolation; partial transition crash/replay; Qdrant corruption/rebuild; v1→v2 và config rollback từ membership hiện hành. Không reset/purge tài nguyên ngoài ownership; #150 hard-purge evidence theo DEP2, không dùng simulated worker.
- [ ] Actual ANN eligible corpus>200, exact filtered comparator cùng snapshot; run embedding/sparse/dense/SDM/phrase/rerank/MMR/quantization matrices đã yêu cầu. Bind inputs/config/server/tie policy; không giả top196hits hoặc synthetic bits4 delta. Run required workload/resource/latency và source/answer metrics đủ mẫu số §14.6A, dùng baseline-derived p95 formula đã duyệt, không tự đặt1000ms.
- [ ] `runtime_evidence.py` kiểm raw capture kinds/subject/config/images/namespace/gold/scorer/criteria/phase coverage và selected/executed/missing scenarios; JUnit count/hash không đủ. Missing identity hoặc helper-only phải reject. Actual provider không gọi được ghi pending, không mock để nhận runtime PASS.
- [ ] CI stack: `.github/workflows/ci.yml` chỉ tự chạy PR base main. Sau push ở từng owner dùng `gh workflow run ci.yml --ref <exact-owner-branch>` rồi lấy run đúng branch/head/event. Đọc artifact `ci-subject.json`: `checkout_sha` phải bằng HEAD đã review; không lấy Sourcery SKIPPED làm CI. Merge candidate vào main sau này vẫn cần required CI đúng subject, không bỏ branch protection.
- [ ] Đóng R5-N03 bằng báo cáo thay thế trong #153/PR: correct full R4 SHA ở §15.1/header, canonical ID meanings, raw evidence scope và mọi unsupported PASS. Ledger ngoài repository chỉ tham chiếu lịch sử; không ghi đè. Ghi approval source trung thực, không sửa nhãn owner-approved để tự cấp quyền.

**Exit:** F17/F21/R5-N03 có actual evidence, copied runbook commands chạy trên own disposable stack. Không cần live provider trước task0 approval/D6; trước đó chỉ code/offline/contract checks.

#### R5-12 — Review độc lập và trình nghiệm thu một gói

**Owner:** Anti điều phối + independent reviewer/held-out runner D7. **Nguồn:** #153/PR và artifact convention hiện hữu; không thêm approval ledger.

- [ ] Thực hiện DEP1 trước freeze, DEP2 trước G8 và DEP3 trước merge proposal. Đóng mọi row32IDs bằng production evidence, full local regression/CI đúng RC, kiểm không sửa frozen gold hoặc10ID PASS lịch sử để qua tests.
- [ ] Freeze code/config/dependency subjects, source/gold/scorer/criteria/role records và expected matrices trước final scoring. Chạy held-out bằng independent runner; implementer không tự soạn/duyệt/chạy gold kín. Không claim process isolation là ACL nếu chưa kiểm.
- [ ] Reviewer đọc connected code/diff/capture, kiểm false positives và false rejects. Nếu phát hiện lỗi, sửa tại owner → cascade → CI/tests → freeze RC mới → independent confirmation chưa lộ theo §14.6A; bộ đã xem trở thành development. Không cherry-pick/cắt denominator/hạ gates để đạt.
- [ ] Tiếp tục đến khi mọi required gate/evidence đạt. Thiếu external capability, quyền hoặc Free quota chỉ dừng phần phụ thuộc, lưu checkpoint và tiếp tục phần độc lập; không bỏ vì số lần chạy. Không tự nhận conditional acceptance thay một gate thiếu.
- [ ] Giao packet §15.6 có target rollout/rollback proposal cụ thể để owner quyết định một lần. Đủ bằng chứng trình nghiệm thu chưa có nghĩa owner đã accepted/merged/deployed.

### 15.5 Lệnh kiểm chứng và điều kiện không được bỏ qua

Thực thi tại đúng owner worktree với checkout guard §12.3 và environment theo runbook. Commands dưới là selections tối thiểu; phải bổ sung tests của callers/schema/provider mới đã chạm. Các module test đề xuất rename chỉ chạy sau rename tại task7. DB/runtime có quyền là điều kiện riêng, không suy từ connection string.

| Owner | Selections tối thiểu sau fix |
|---|---|
| S3 | `python -m pytest backend/test/adapters/pdf/test_docling.py backend/test/adapters/pdf/test_pypdf.py backend/test/providers/cloudflare/test_cloudflare_pdf_understanding.py backend/test/ingestion/test_pdf_structure.py backend/test/ingestion/test_pdf_chunking.py backend/test/ingestion/test_pdf_job_processing.py` |
| S4 | `python -m pytest backend/test/answering/test_retrieval_configuration.py backend/test/adapters/cli/test_reindex_search.py backend/test/ingestion/test_search_indexing.py backend/test/adapters/qdrant/test_dense_search_index.py backend/test/adapters/qdrant/test_native_search_index.py` |
| S4/S5, disposable DB | `python -m pytest backend/test/adapters/postgres/test_corpus_statistics_transition.py backend/test/adapters/postgres/test_text_search_indexing.py` và actual producer/finalization integration nodes đã bổ sung |
| S5 | `python -m pytest backend/test/answering/test_sequential_dependence.py backend/test/ingestion/test_corpus_statistics.py backend/test/ingestion/test_lexical_population.py` |
| S6 | `python -m pytest backend/test/answering/test_reranking.py backend/test/providers/cloudflare/test_cloudflare_reranking.py` và actual MMR/lifecycle/fallback nodes |
| S7 collection | `python -m pytest --collect-only backend/test/answering/test_query_plan_models.py backend/test/adapters/langchain/test_langchain_query_planner.py`; sau đó bỏ `--collect-only` để chạy |
| S7 behavior | `python -m pytest backend/test/answering/test_module.py backend/test/answering/test_source_verification.py backend/test/answering/test_generation_validation.py backend/test/answering/test_answer_group_completeness.py` và new verifier/provider/stream/persist integration nodes |
| S8 | `python -m pytest evals/test/test_pdf_retrieval_release_dataset.py backend/test/config/test_runtime_evidence.py`; runtime chạy bằng actual profile/launcher command đã kiểm ở task11 |

Mỗi task Python: `python -m ruff format .`, `python -m ruff format --check .`, `python -m ruff check .` theo repository policy và đọc diff format; giữ changes ngoài ownership. Dùng full CI partition theo CI runbook trước freeze, không chỉ selections này. Thu command/exit/count/skips/interpreter/import path; missing path/collection error là lỗi cần sửa tại owner, không tự loại selection. Skipped mandatory DB/runtime tests không đóng gate.

**Các phép thử chống “xanh giả”:** production method phải được gọi; service restart/fresh worker phải đọc PG; partial transition fault phải có DB rollback; vector corruption phải đổi actual vector; source recovery phải đọc canonical PG dù Top-K miss; verifier phải kiểm cả đáp án đúng ngắn; runtime bundle helper-only/missing identity phải bị từ chối; default release loader thiếu manifest phải thất bại. Các phép thử này là development regressions, không thay held-out quality.

### 15.6 Ma trận cổng và gói kết quả cuối

Giữ toàn bộ điều kiện G3–G8 và các ngưỡng §14.6A/B, không copy rồi vô tình đổi mẫu số. Gắn thêm conditions của R5:

| Gate | Task / bằng chứng bổ sung bắt buộc | Trạng thái lúc soạn R5 |
|---|---|---|
| G3 | 1–2: native/scan/mixed source truth, PG round-trip, đúng driver hard OS limits/cleanup cả Windows/Linux | Chưa đủ điều kiện nghiệm thu |
| G4 | 3–4: mọi producer, all-member atomic transition, PG-expected receipts, actual collection/query/ANN matrices, R5-N01 | Chưa đủ điều kiện nghiệm thu |
| G5 | 5: persisted v2, fresh worker/membership changes, v1 upgrade và rollback trên DB có dữ liệu | Chưa đủ điều kiện nghiệm thu |
| G6 | 6 +11: regression provider/fallback/MMR và real quality/usage, G4/G5 đạt | Chưa đủ điều kiện nghiệm thu |
| G7 | 7–9: snapshot fences, canonical Q6, true-positive/negative support validation, follow-up, R5-N02 và held-out metrics | Chưa đủ điều kiện nghiệm thu |
| G8 | 10–12: admission, actual stack/security/lifecycle/rebuild/rollback, exact CI/semantic/source evidence,32dispositions, R5-N03 và required DEP2 capabilities | Chưa đủ điều kiện nghiệm thu |

**Packet cuối:** exact plan approval → six owner/base/HEAD + final integrated RC →32-ID evidence matrix →G3–G8 matrix/raw captures/commands/CI subjects →source/gold/scorer/criteria manifests và independent role/freeze records →provider/account/usage/$0 evidence →dependency/applicability/owner ACK →target build/migration/backfill/health/observation/rollback proposal. Mỗi claim nêu code/local/CI/runtime/quality/review/owner acceptance riêng; không dùng xanh CI để thay quality hoặc acceptance.

PR #215 đã merged, không merge lại. Thứ tự dự kiến còn lại #216→#217→#218→#219→#220→#221. Với mỗi merge candidate, base/conflict resolution/subject đổi phải kiểm lại phần bị ảnh hưởng và required CI; runtime RC cũ chỉ dùng khi chứng minh compatibility/bindings còn đúng. Owner cần ra lệnh merge/deploy trên packet cuối. #153 Done theo S8 sau acceptance + authorized rollout/post-deploy, không suy từ việc Anti đã đóng code findings.

### 15.7 Gói duyệt tập trung và prompt gửi Anti

**Một lần duyệt thiết kế:** owner duyệt đúng commit hoặc SHA256 toàn file sau khi soạn xong, gồm §15 + các phần kế thừa §14.2–§14.6 (D1–D8, quyền D6/D7, ngưỡng và dependencies). Nếu có bằng chứng duyệt R4 đúng revision thì dẫn lại, không yêu cầu ký lại các quyết định không đổi. Nếu chưa liên kết được thì một lời duyệt R5 gộp các điều khoản này, không tự nhận ledger đã cấp quyền. Anti ghi reference thật ở #153/PR trước triển khai.

Mẫu phản hồi:

> Duyệt R5 §15 đúng revision bàn giao, cùng D1–D8 và §14.3–§14.6 được kế thừa. Giao Anti tự triển khai, sửa, kiểm chứng, commit/push các PR owner, dispatch CI và chạy disposable/$0 verification trong phạm vi đã nêu tới khi đủ bằng chứng trình nghiệm thu G3–G8. Không giới hạn tổng lượt AI/RC/vòng sửa, tránh lãng phí. Chưa cấp quyền merge/deploy.

**Tự quyết sau duyệt:** implementation details/pins tương thích, tests/fixtures phát triển, additive migrations và trace versioning đã thiết kế, sửa lỗi/review/cascade/re-run, vai trò độc lập trong quyền D7. Không xin lại từng command, numerical implementation hoặc freeze đã nằm trong protocol. **Chỉ gom hỏi khi** cần đổi sản phẩm/kiến trúc/ngưỡng/quyền/chi phí, có xung đột ownership thật hoặc qualification chứng minh phương án không khả thi; kèm evidence và lựa chọn cụ thể, tiếp tục phần độc lập. Không dùng việc chưa pass sau nhiều lần như lý do tự dừng hoặc xin hạ chuẩn.

Prompt ngắn gửi Anti sau duyệt (đính kèm full commit/SHA256 thực của bản này):

> Đọc và thực hiện R5 §15 cùng §14.2–§14.6 trong `docs/plans/2026-10-22-retrieval-v3-review-remediation.md`, worktree `C:/Developer/Projects/knora-agent-worktree/docs-retrieval-v3-acceptance-remediation`, đúng revision/approval bàn giao. Dùng executing-plans; xử lý R5-0→12 tại đúng owner S3–S8 và cascade #216→#221. Đóng12ID mở +3ID mới, giữ17regression, giao đủ32dispositions/G3–G8 với code/local/CI/runtime/quality riêng. Không làm lại S2, sửa gold để pass, chạy local AI hoặc phát sinh phí. Không trần tổng AI/RC/vòng sửa; tự sửa và kiểm chứng tới đủ nghiệm thu trong quyền đã duyệt. Chốt DEP0/roles từ đầu, giữ required external capability pending khi thiếu; ghi evidence ở #153/PR. Chỉ gom hỏi khi vượt scope/quyền hoặc bất khả thi có bằng chứng. Giao một packet nghiệm thu/rollout cuối; chưa merge/deploy.

**Tự kiểm kế hoạch R5:** 12 ID mở đều có owner/production boundary/regression/exit;17regression giữ nguyên nghĩa;3lỗi mới có disposition riêng; quyền và dependencies có điểm kiểm sớm; không thêm trần tổng calls/rounds. Exact parser/model/server/OS/runtime/quality vẫn cần qualification và evidence khi thực thi. Kế hoạch này làm rõ đường tới nghiệm thu, không cam kết mọi phụ thuộc ngoài quyền của Anti chắc chắn sẵn sàng.

## 16. R6 — Checklist xử lý kết quả independent review R5

### 16.1 Nguồn, quyền và phạm vi không đổi

**Đề bài:** yêu cầu trong hội thoại ngày 24/10/2026: lập kế hoạch xử lý các điểm chưa đạt của review R5 và cung cấp prompt ngắn giao Anti. Review trong cùng hội thoại là nguồn findings; không bịa URL review. Đây là checklist thực thi các hợp đồng R5 đã duyệt, không phải một thiết kế thay thế. Chưa triển khai code hoặc chạy runtime trong lúc soạn mục này.

**Bản duyệt gốc:** `docs/plans/2026-10-22-retrieval-v3-review-remediation.md` tại commit `4d48f56c0a93d5019b6840bee4ffcb31a8e48a39`, [#153 comment 6381910609](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6381910609). SHA256 file Windows CRLF là `2a211d578d5be887f135982500e207b4552075efe0d3a66df86517959d3110aa`; Git blob LF là `bf5497549599827e7e4bfab0133d3f2dee43c2ab6707adb2d527d71c2cc68361`. Đây là cùng nội dung với encoding newline khác nhau; ghi rõ khi đối chiếu, không đổi hash artifact mà vẫn gọi là cùng bytes.

**Kế thừa bắt buộc:** bảy plans đóng băng, §14.2 D1–D8, §14.3A–G, §14.5, §14.6 và toàn §15. Không làm lại S2, không hạ ngưỡng, đổi mẫu số, sửa gold để pass, chạy local AI/weights hoặc phát sinh phí. Native PDF/tokenizer không dùng ML vẫn được phép theo D1/D3. Không đặt trần tổng AI calls/journeys/RC/vòng sửa; giữ per-request safety và Free-provider limits. Hết Free quota thì checkpoint/chờ và làm phần độc lập, không bật Paid/local hoặc bỏ nhiệm vụ.

**Quyền tiếp tục:** Anti đối chiếu approval gốc và dùng quyền D6–D8 để sửa code, commit/push các PR owner, chạy CI và disposable verification đúng namespace được giao. Không xin duyệt lại thiết kế hoặc từng lệnh đã được phép. Nếu phát hiện delta thật về scope/architecture/criteria/cost/permission/ownership, gom một packet gồm evidence và lựa chọn; tiếp tục phần độc lập. Chưa merge/deploy/đóng Issue, chưa tự nhận owner accepted.

### 16.2 Pins và registry 32 ID

Baseline dưới đây là đối tượng review R5, không phải SHA bắt buộc reset về khi Anti bắt đầu. Cả sáu worktree sạch khi review kết thúc. Mỗi intake/cascade/freeze phải đọc lại GitHub và ghi HEAD/base mới cùng delta trong #153/PR; giữ thay đổi của phiên khác.

| Stage / PR | Worktree dưới `C:/Developer/Projects/knora-agent-worktree/` | HEAD đã review | CI đã đọc trong review |
|---|---|---|---|
| S3 / #216 | `feat-retrieval-v3-document-understanding` | `0ac3a4aa9afcee29d7077fe7a621e4fe902221ce` | run `40082928715`, success |
| S4 / #217 | `feat-retrieval-v3-dense-hybrid-search` | `0e9fddf5ab7830f735cb052c97ab445b03be7b44` | run `40082921114`, failure |
| S5 / #218 | `feat-retrieval-v3-sequential-dependence-ranking` | `7237a185d091767c08b12c3db9fe808d4e31edb8` | run `40082912178`, failure |
| S6 / #219 | `feat-retrieval-v3-reranking-evidence` | `4c9659c47d0cc6bf766bfb501fab82cd40ece906` | run `40082903394`, failure |
| S7 / #220 | `feat-retrieval-v3-query-understanding-coverage` | `cc8be7fbd09dc11e27e570e06c402948c597b1aa` | run `40082894852`, failure |
| S8 / #221 | `feat-retrieval-v3-integrated-release` | `cf7ccfe3427a271932a12ba5352e08c7e5fa5397` | run `40082885468`, success |

**15 ID phải xử lý:** `F03,F24,F05,F23,F25,F08,F13,F14,F18,R3-N04,F16,F17,F21,R2-N03,R5-N03`.

**17 ID kiểm chống hồi quy:** `N01,F01,F02,F04,F06,F07,F09,F10,F11,F12,F15,F19,F20,F22,R2-N02,R5-N01,R5-N02`. PASS trong review trước chỉ là lỗi cụ thể ở phạm vi đã kiểm, không đóng runtime/quality/gate.

Không đổi nghĩa ID: F19=scorer, F20=gold/hash, R2-N02=derivation identity, R2-N03=reranker test collection. Hai lỗi collection embedding/generation là việc sửa CI cùng phạm vi; ghi evidence riêng, không gán sai thành lỗi provider hay tạo finding ID thứ33 để né registry. R5-N01 đã cascade đủ candidate100; R5-N02 đã đổi query test basename: chỉ regression, không làm lại fix.

### 16.3 Thứ tự và hợp đồng nhận hàng

Anti thực hiện **R6-0 → S3(R6-1) → S4(R6-2) → S5(R6-3) → S6(R6-4) → S7(R6-5) → S8(R6-6) → R6-7**. Curator/dependency intake bắt đầu ngay R6-0, held-out sau freeze. Sửa collection test ngay tại owner sớm nhất trong quá trình đi qua S4/S6, không chờ S8. Sau mỗi owner fix, merge upstream theo cách không force-push vào từng downstream và kiểm conflicts/semantics; không chỉ vá bản tích hợp.

Giao diện đích giữ §14.3/§15.3: S3 giao canonical geometry/origin/coverage + parser identity; S4 giao immutable corpus snapshot v1 và receipt từ PG expected vectors; S5 giao v2 statistics; S7 giao request-wide `RetrievalReadSnapshot`, `CanonicalSourceRead`, statement projection/verdict; S8 chỉ nhận captures thực gắn identities. Tên interface ở kế hoạch là đích thiết kế; không giả rằng chúng đã tồn tại ở baseline, không tạo wrapper cho đủ tên.

**Chu trình mỗi lát sửa:** ca đỏ tại production entrypoint → ghi lỗi đúng nguyên nhân → sửa callers/schema/config/docs chịu ảnh hưởng → ca xanh và true-positive → scoped regressions/format → đọc diff → commit → cascade → xác minh downstream. Pseudocode assertions bên dưới là yêu cầu test, không phải file chạy độc lập; implementer phải định nghĩa fixture có kiểu từ raw input/PG/application seams tại owning test module. Mock chỉ kiểm hợp đồng, không đóng DB/process/server/provider runtime.

#### R6-0 — Intake, resources, source truth và ma trận trước khi sửa

**Owner:** Anti điều phối; tài liệu kế hoạch ở nhánh `docs/retrieval-v3-acceptance-remediation`. Tiến độ, evidence và blockers giữ trong #153/PR; không tạo ledger song song.

- [ ] Kiểm repository/root/branch/status/worktree ownership, remote/base/HEAD sáu PR và exact plan/approval. Ghi trong một comment intake:32ID, trạng thái code/local/CI/runtime/quality/review/accepted, owner task và dependency. Đọc delta nếu HEAD đã đổi, không reset/stash/ghi đè.
- [ ] Đọc logs CI S4–S7 nêu ở §16.2 và chuyển từng phản ví dụ review thành development regression tại owner. Ba test CLI S4 trước đó lỗi DB authentication là lỗi môi trường; không nhận password/URL có sẵn làm quyền reset. Dùng disposable DB được D6 cấp, xác minh target bằng metadata an toàn trước chạy.
- [ ] Hoàn tất DEP0 theo §14.6D cho #148/#150/#158, giữ capability pending khi chưa có accepted contract/artifact; không làm thay dự án phụ thuộc hoặc tự miễn requirement.
- [ ] Đăng ký độc lập curator/reviewer/runner/code reviewer theo D7 và namespace Workbench hiện hữu. Bắt đầu nguồn/gold mới theo §14.6A ngay; không đợi sửa code xong mới phát hiện thiếu người giữ gold. Giữ fresh context và access records, không nói có ACL isolation khi chỉ tách session.
- [ ] Chốt ownership của app/PG/Qdrant/ObjectStore/ports/reservations trong D6 package, exact model/server/OS pins và Free/no-paid preflight. Chỉ wipe/reset resources tạo mới thuộc package này. Qualification thất bại thì ghi contract/error cụ thể, không tự chuyển model/provider/paid route.

**Exit:** có intake32IDs, resource envelope, roles và dependency packet thực; thiếu external capability không cản code/offline độc lập. Không claim acceptance ở task intake.

#### R6-1 — S3: native geometry và hard process limits (F03/F24)

**Modify:** `backend/src/knora/adapters/pdf/docling.py`, shared `adapters/pdf/_pypdf_process.py`/`_pypdf_limits.py`, `providers/cloudflare/pdf_understanding.py`, `ingestion/pdf.py`/`pdf_structure.py`/`pdf_chunking.py`, extractor resolver/worker/PG finalizers chịu ảnh hưởng và `backend/pyproject.toml` theo D1. Native driver mới đặt trong package PDF hiện có, không supervisor mới. **Tests:** `backend/test/adapters/pdf/test_docling.py`, `test_pypdf.py`, `backend/test/providers/cloudflare/test_cloudflare_pdf_understanding.py`, `backend/test/ingestion/test_pdf_structure.py`, `test_pdf_chunking.py`, `test_pdf_job_processing.py` và PG finalization suites hiện hữu.

- [ ] Chuyển ba phản ví dụ thành ca đỏ: RSS vượt budget vẫn thành công; native table không có cells/bbox; mixed OCR nối sau toàn native text. Sửa `except` không được nuốt chính `PdfExtractionError`; lỗi capability/psutil không được âm thầm tắt giới hạn bắt buộc.
- [ ] Hoàn thành D1 geometry/render/transform/assembly, không dừng ở sửa regex. Raw fixtures: native hai cột, bảng không có ký tự pipe, repeated text, rotated/cropped, tiled/composed images, mixed native+scan. Expected facts/cells/order lấy raw source độc lập. Giữ origin, source hash/page/region, offsets theo cursor; không `find()` chọn nhầm repeated text.
- [ ] Tái dùng supervisor handshake: child chưa parse trước khi hard limiter cài xong; parent enforce wall deadline cả OCR/assembly và reject late success. Pass remaining timeout vào transport; cancellation không dispatch tiếp. Không có capability hard-limit thì typed failure; kill/join/close/unlink đúng owned tree.
- [ ] Test Windows Job/Linux cgroup bằng process thật, giới hạn D2, parse/render treo, tiny budget, output quá lớn và timeout sau provider response; lưu elapsed/limit/exit/cleanup/peak observations. Phân biệt committed/cgroup limit với số đo RSS. Fake response chỉ chứng minh deadline contract, không chứng minh cloud/process thật.
- [ ] Pin parser/config mới §14.3G, giữ legacy immutable; chạy source→submission→worker→PG serialize/reload→chunk/citation. Trang dài phải có nhiều chunks ≤650 tokens và không xuyên trang, overlap≤75; không ép 1trang=1chunk. Incomplete không activate hoặc làm Q6 absence.

**Assertions bắt buộc:**

```python
# Trên actual application/driver fixtures, không chỉ gọi check_limits().
assert extraction_over_memory.succeeded is False
assert late_valid_response.succeeded is False
assert owned_child_tree_after_timeout == ()
assert canonical_native_table.cells == source_reviewed_cells
assert pg_reloaded_structure == extracted_structure
assert all(c.page_start == c.page_end and c.token_count <= 650 for c in chunks)
```

**Exit:** F03/F24 có production + PG/process evidence cả hai OS; F01/F02/F04/F20/R2-N02 regression. G3 còn cần fidelity metrics §14.6A ở R6-7, không đóng bằng mock OCR hoặc bảng Markdown tự dựng.

#### R6-2 — S4: corpus activation, vector receipt, collection và CI (F05/F23/F25)

**Modify:** `backend/src/knora/adapters/postgres/search_index_store.py`, tables/additive Alembic migrations, `ingestion/search_indexing.py`/job routing/text+PDF finalizers, `adapters/cli/reindex_search.py`, `adapters/qdrant/search_index.py`/`native_search_index.py`, composition/capabilities. **Tests:** corpus transition/text/PDF indexing integration suites; `backend/test/adapters/qdrant/test_dense_search_index.py`, `test_native_search_index.py`, CLI/config suites §15.5. **Collection fix owner:** rename `backend/test/adapters/langchain/test_embedding.py` → `test_langchain_embedding.py` như bản S8 hiện có; tìm mọi refs và CI selections trước rename, giữ assertion nội dung.

- [ ] Ca đỏ production transition: manifest có A,B nhưng mới có receipt A phải reject và giữ toàn bộ heads cũ. Không dùng `items` caller làm full membership. Implement immutable snapshot/head v1 + durable `corpus_reindex` và API `commit_corpus_transition(snapshot_id, expected_revision)` theo D3/§14.3B.
- [ ] Parent/children/jobs thật, không callback `pass`; profile/embedding-set chọn từ exact manifest PG, bỏ avg_len256/digest0/UUID-desc cho route V3. Text/PDF/CLI/backfill/archive/reprocess đi cùng seam. Hỗ trợ document>64chunks bằng batches có receipts/completeness, không nâng cap không giới hạn.
- [ ] Disposable PG test: crash sau update member đầu phải rollback toàn bộ; replay/lost reply idempotent; hai workers CAS chỉ một transition thắng; add/remove/revoke/restart không phục vụ corpus trộn profile. Empty corpus là explicit snapshot count0.
- [ ] PG raw vectors immutable là expected authority. Thay JSON float/raw-hash equality bằng comparison policy versioned server-equivalent float32/Cosine §14.3C; payload digest chỉ diagnostic. Qualify tolerance từ error bounds và actual pinned-server positives trước freeze; reject wrong/swapped/missing/forged vectors. Không dùng tolerance tùy ý đủ lớn để mọi vector pass.
- [ ] Positive đi qua `stage_generation`→actual readback→receipt→CAS phải chấp nhận normalization/float32 hợp lệ. Negative thay actual vector nhưng giữ/giả payload digest phải bị từ chối. Receipt bind exact snapshot/embedding set/config/comparison/server/collection/capture/count.
- [ ] Readback effective float32/Cosine/on-disk/HNSW/bits4/always_ram theo pin. Thêm negatives uint8, float16, sai distance, thiếu fields không chứng minh được effective value, sai HNSW/quantization. Known server defaults chỉ được normalize khi có pinned schema + actual evidence, không tự coi missing là compatible. Đưa rescore/oversampling đúng query wire; kiểm filtered IDF scope sparse/hybrid và decoys. Không PATCH collection serving để ép pass.
- [ ] Kiểm default collection toàn test roots/CI partitions tại S4; lỗi generation collision nếu có tại stage này cũng rename tại owner sớm nhất có file, giữ refs. Cascade lên S5–S8 rồi chạy lại configuration module: hybrid pool100, finalTop8 và evidence5 là các lớp khác nhau; R5-N01 chỉ regression.

```python
assert partial_transition.rejected and heads_after == heads_before
assert crash_between_member_updates.rolled_back
assert normalized_correct_vector.receipt_valid
assert swapped_or_corrupt_vector.rejected
assert effective_uint8_collection.rejected
assert unverifiable_collection_configuration.rejected
```

**Exit:** F05/F23/F25 có DB/server production positives+negatives; F06/F07/F11/F19/R5-N01 giữ. N01 mỗi stage một head với ancestry đầy đủ, được phép additive head mới; không xóa migration/data để ép tên head cũ. ANN/quality còn ở R6-7.

#### R6-3 — S5: persisted statistics v2 (F08)

**Modify:** `backend/src/knora/adapters/postgres/search_index_store.py`, corpus builder/schema/migrations trong `ingestion/`, `answering/sequential_dependence.py`, `answering/module.py`/store ports/callers. **Tests:** `backend/test/answering/test_sequential_dependence.py`, `backend/test/ingestion/test_corpus_statistics.py`, `test_lexical_population.py`, `backend/test/adapters/postgres/test_corpus_statistics_transition.py` và existing application SDM tests.

- [ ] Ca đỏ cùng profile: thêm hoặc đổi canonical document làm frequencies/token totals đổi mà digest giữ nguyên phải thất bại. Đọc fresh worker lẫn worker cũ; không chứng minh chỉ bằng object identity hoặc in-memory builder.
- [ ] Builder ngoài HTTP request tạo immutable snapshot v2 từ full authorized membership, đủ unigram/ordered/window frequencies và policy/digests. Reader nhận expected snapshot, kiểm active head/revisions/schema/digest và đọc persisted statistics; không scan/tokenize toàn corpus hoặc giữ workspace lock qua network trong request.
- [ ] Numerical fixture expected tính từ raw corpus độc lập, không từ Top-K; corpus khác frequencies/membership có snapshot/digest khác dù lexical profile bằng nhau. Digest verification phải phát hiện bytes bị sửa, không chỉ có chuỗi khác rỗng.
- [ ] Chạy v1 S4 có dữ liệu→v2 upgrade→fresh restart→rollback/rebuild theo §14.3B. Unknown/corrupt/stale stats fail closed; không sửa bytes v1, đổi nhãn receipt hoặc phục hồi revoked generation. Kiểm crash/race/archive/reprocess và compatibility S4-only.

```python
assert stats_a.snapshot_id != stats_b.snapshot_id
assert stats_a.statistics_digest != stats_b.statistics_digest
assert fresh_worker.stats == serving_worker.stats == independently_expected_stats
assert answering_request.performed_corpus_tokenization is False
assert tampered_or_stale_snapshot.rejected
```

**Exit:** F08 có persisted PG numerical/application evidence; không đóng chỉ vì bỏ cache. G5 cần upgrade/rollback đúng dataset và chất lượng SDM qua R6-7.

#### R6-4 — S6: collection, provider và fallback (R2-N03)

**Modify/test:** `backend/test/answering/test_reranking.py`, `backend/test/providers/test_reranking.py`, `backend/test/providers/cloudflare/test_cloudflare_reranking.py`, LangChain generation test/refs, existing reranking/MMR/module lifecycle suites và callers chịu ảnh hưởng upstream. Rename provider-generic `test_reranking.py` thành `test_reranking_contract.py`; rename LangChain `test_generation.py` thành `test_langchain_generation.py` như S8; không rename lại provider Cloudflare đã đúng.

- [ ] Tái hiện `import file mismatch` với đúng pytest configuration/collection CI, rồi sửa basename tại S6; embedding collision đã nhận từ S4. Cập nhật mọi selections/runner/refs. Không đổi `--import-mode` hoặc deselect test để che lỗi.
- [ ] Giữ `reranking-cloudflare-bge-base-v1`, `result.response`, remap/cardinality, close/lifecycle và fallback DBSF+SDM. Reranker timeout/malformed/quota không phục hồi candidate stale/ngoại quyền; fallback cùng snapshot đã validate, pool≤100, evidence≤5chunks/3000tokens.
- [ ] Default collect và full CI partition phải thành công tại S6 và S7 sau cascade; S8 CI xanh không thay CI của owner. F09/F10 regression và actual fallback/usage quality ở R6-7.

**Exit:** R2-N03 đóng bằng collect/execution thực, CI đúng owner HEAD; không đổi nghĩa ID thành chỉ test provider envelope. Giữ source/security fences trước mọi cloud content call.

#### R6-5 — S7: snapshot xuyên request, Q6, support và follow-up (F13/F14/F18/R3-N04)

**Modify:** `backend/src/knora/answering/module.py`, `stores.py`, `source_verification.py`, `generation_validation.py`, query planning/results/evidence/trace configuration, `adapters/postgres/answering_store.py`/canonical reader, `providers/cloudflare/` answer-support adapter, `main.py`/bootstrap lifecycle, HTTP/SSE/Conversation readers. New support port/provider dùng tên đích §14.3F; chỉ tạo module có trách nhiệm ấy trong package hiện hữu. **Tests:** S7 selections §15.5, `test_s2_snapshot_fence.py`, dense/hybrid contracts và existing API/Conversation/stream/persist suites; thêm provider verifier tests tại package Cloudflare, đặt basename riêng.

- [ ] R3-N04: capture `RetrievalReadSnapshot` trong short PG transaction trước search đầu; mọi branch/empty/recovery phải trả đúng snapshot và canonical membership/content. Validate/hydrate từng result trước merge/rerank; không union generations để hợp thức hóa.
- [ ] Dùng trace version mới rõ ràng cho cả BM25/dense/hybrid; decoder/persist/recovery readers cùng đổi, legacy decoders giữ. Ca đỏ dense/hybrid schema2 bypass phải chuyển thành rejection khi revoke xảy ra lúc generation. Không chỉ đổi số schema mà thiếu mandatory snapshot/verdict fields.
- [ ] Revalidate trước reranker/generator/verifier, trong transaction persist và trước final delivery/recovery. Actual AnswerQuestion spies: foreign secondary/recovery, empty thiếu snapshot, revoke trước mỗi phase và sau persist trước delivery đều chặn answer/source bytes; không giữ PG transaction qua network, không gửi partial answer trước validation.
- [ ] F13: implement `read_canonical_source_scope(..., snapshot, cursor, limits)` từ PG structure/chunks, không similarity Top-K. Scope explicit→admitted context→unique authorized catalog; ambiguous clarification. Một bounded pass cho toàn missing groups theo D4. FOUND có facts+anchors; VERIFIED_ABSENT cần complete exact scope; partial/budget/error không báo “tài liệu không có”. Catalog section không chứng minh semantic fact absence.
- [ ] F18: registry capabilities thay suffix detection, planner dùng resolved retrieval context. Reserve từng required group rồi composite/variants round-robin≤8; group5 clarification, không INSUFFICIENT_EVIDENCE. Nqueries=Nvalid vectors, không broadcast; pool≤100, evidence≤5/3000, inner cap2 giữ.
- [ ] Follow-up positive qua Conversation thật: hỏi “báo cáo được gợi ý trình bày bao nhiêu chương?”→7; hỏi “bao gồm những chương nào?”→liệt kê đúng7tên từ cùng authorized source với evidence mới. Assistant answer chỉ giúp resolve context, không làm source truth. Source ambiguous/revoked thì không đoán.
- [ ] F14: exact statement/group ranges từ composer, phủ toàn factual body cả before/items/after; hash final text. Deterministic checks cho mọi V3 ANSWER kể cả single-intent; không bag-of-words/numbers hoặc cắt dấu chấm bỏ claim trước citation.
- [ ] Implement một verification-only Cloudflare call theo D5/§14.3F, strict digest/cardinality/quote offsets và group coverage; runtime input không chứa gold. UNKNOWN/malformed/timeout/quota không deliver successful answer hoặc fake refusal/absence. REFUSAL không gọi verifier. Không thêm answer rewrite/retry để né verdict.
- [ ] Negative source “Thời hạn đổi trả là 7 ngày.” phải reject đủ ba outputs: “Sao Hỏa có sự sống [[E1]].”; “Mọi khách hàng được hoàn tiền vô điều kiện. Thời hạn đổi trả là 7 ngày [[E1]].”; “Phí vận chuyển là 7 ngày [[E1]].”. Thêm swapped citations,70/ngày-tháng, negation, forged offsets/digest và prompt injection. Positives “7 ngày”, “1 tuần”, citation sau dấu chấm, short/list/multi-sentence đúng nguồn phải pass. Tất cả đi qua actual execute/persist/HTTP/SSE/Conversation, không chỉ validator helper.

```python
assert topk_empty_but_pg_has_chapter5.outcome == "FOUND"
assert complete_scope_without_chapter5.outcome == "VERIFIED_ABSENT"
assert partial_scope.outcome == "UNVERIFIED"
assert two_authorized_possible_sources.outcome == "AMBIGUOUS"
assert five_required_groups.requests_clarification
assert followup.chapters == seven_source_reviewed_chapter_names
assert unrelated_or_uncited_claim.successful_answer is False
assert concise_supported_answer.successful_answer is True
assert revoked_during_generation.persisted_successful_answer is False
assert revoked_before_delivery.delivered_answer_bytes == b""
```

**Exit:** cả bốn ID có PG/application/delivery evidence đúng phase; F12/F15/F22/R5-N02 giữ. Đóng regression không tự đóng quality/follow-up held-out G7; protocol §14.6A vẫn áp dụng.

#### R6-6 — S8: admission, runtime thật, runbook và báo cáo thay thế (F16/F17/F21/R5-N03)

**Modify:** `evals/datasets/pdf_retrieval_release_v1.py`, actual release entrypoints/manifests, `scripts/run-runtime-verification.ps1`, `scripts/runtime_evidence.py`, `backend/runtime_test/test_dense_hybrid_search.py`/`test_retrieval_v3_recovery.py` và runtime scenarios hiện hữu, `docs/runbooks/retrieval-v3-release.md`. **Tests:** `evals/test/test_pdf_retrieval_release_dataset.py`, `backend/test/config/test_runtime_evidence.py`, existing runtime/CLI/config tests. Runtime artifacts/reports giữ convention hiện hữu, không evaluation runner mới.

- [ ] F16: mọi release path explicit/default/runner bắt buộc sealed package đủ hash/source/gold/split/approval/roles/scorer/criteria/config theo §14.6A. Approval thiếu `dataset_sha256` hoặc chỉ owner string+version phải reject. Legacy4samples chỉ chạy development với nhãn rõ; không admit làm release. Positives approved exact bytes và two-phase bindings phải pass.
- [ ] F17: synthetic ANN/recovery suites giữ nhãn contract-only, không làm gate runtime. Bỏ selector dùng `ann_recall or decoy` như proof. Runtime scenarios dùng actual app/PG/Qdrant/Cloudflare trên package D6; corpus đủ>200 eligible, exact filtered comparator và bits4 cùng snapshot/query/config. Không tự dựng top196 hoặc hoán vị ranking để có metric đẹp.
- [ ] Evidence loader bắt buộc subject/config/server/image identities/namespace/raw capture kind/provider usage và actual executed scenario coverage; helper-only/JUnit-only hoặc thiếu images/config/capture bị reject. Positive actual bundle pass; record skips/errors/missing riêng, không count thành runtime success.
- [ ] Journeys đủ §15.4 R5-11: text/PDF ingest→canonical/index/answer/citation;3modes;planning/follow-up/Q6;reranker/verifier failures;archive/reprocess/revoke/isolation;partial transition/restart;Qdrant corruption/rebuild;v1→v2/rollback. Required dependency capabilities cần DEP2 evidence, không mock giả.
- [ ] F21: runbook dùng `lexical_qdrant_url` và validation lỗi cấu hình rõ, bỏ `s.qdrant_url`. Copy từng lệnh `--help`/`--dry-run`/checkpoint/reindex/config/health từ runbook chạy trên resources được giao. Cutover/rollback thử trên disposable stack, đọc effective running config+heads+response/trace sau restart; in factory object không chứng minh đã đổi deployment. Không thực hiện cutover production hoặc deploy thật.
- [ ] R5-N03: giữ nguyên artifact lịch sử, xuất báo cáo thay thế đúng32IDs tại report convention hiện hữu, dẫn lại RC `dd5a5add...` là historical/unsupported cho current acceptance. Cập nhật #153/PR summary liên kết report mới và correct plan SHA/ID meanings; không sửa owner approval, không tự ghi NhiBuaa đã thẩm định khi chưa có. Tách code/local/CI/runtime/quality/review/accepted và raw evidence links.

```python
assert approved_version_without_hash.rejected
assert default_legacy_samples_as_release.rejected
assert exact_approved_sealed_release.admitted
assert helper_only_runtime_bundle.rejected
assert missing_image_or_capture_identity.rejected
assert runbook_probe_uses_declared_settings_only
assert disposable_rollback.effective_config == pinned_rollback_config
```

**Exit:** bốn ID có admission negatives/positives, actual runtime/CLI/effective-state proof và superseding report. Báo cáo mới không ghi PASS gate trước khi R6-7 đủ mọi điều kiện.

#### R6-7 — Cascade, freeze, independent review và một packet nghiệm thu

**Owner:** Anti điều phối; curator/reviewer/held-out runner độc lập D7. **Tests/commands:** giữ §15.5, mở rộng tests mới vào CI selections có thẩm quyền và dùng existing runtime/evaluation runners. Không chạy nguyên script Temp chưa kiểm side effects.

- [ ] Tại từng owner chạy checkout/import guard §12.3; local Python3.13 trước đây không thay Python3.12 CI. Default collect toàn CI test roots, chạy đầy đủ partitions bắt buộc trên đúng subjects; không importlib workaround/skips mandatory để xanh. Python: Ruff format/check/lint theo repository. Nếu docs/shared tooling thuộc selection thì format/check tương ứng; không format ngoài ownership.
- [ ] Push/dispatch CI từng PR sau cascade, lưu branch/head/event/run và đọc `ci-subject.json` checkout SHA. Current success S3/S8 và failure S4–S7 chỉ baseline; final cần fresh CI của cả sáu HEAD. Run workflow từ nguồn được CI runbook quy định, pin full candidate `subject_sha` khi workflow có input ấy; workflow SHA/run ID không thay subject SHA.
- [ ] DEP1 trước freeze. Kiểm không sửa frozen plans/gold/S2 hoặc bỏ fixtures/assertions bắt lỗi; source labels mới phải độc lập. Two-phase freeze theo §14.6A: source facts trước candidate output; mapping/chunk judgments của exact subjects trước final scoring. Held-out mới≥12PDF/60questions gồm≥8follow-up, không dùng probes đã lộ để claim blind.
- [ ] Independent runner chạy toàn manifest và matrices baseline/candidate/quantization/scoring theo §14.6A. Giữ nguyên ngưỡng/mẫu số/strata/resource/p95 formula, factual/citation precision100%, mandatory Q6 positives và zero false-absence. Không tự copy số aggregate từ report cũ hoặc hạ chuẩn khi baseline yếu.
- [ ] Independent reviewer đọc connected code/callers + raw captures,32-ID matrix và G3–G8. Có lỗi thì trả owner→sửa→cascade→CI→freeze lại subjects bị ảnh hưởng→confirmation độc lập. Dữ liệu held-out đã lộ thành development theo protocol; không giới hạn số RC/vòng sửa, tránh replay inputs/config không đổi vô ích.
- [ ] DEP2 đủ required capability evidence trước G8. Giao packet §16.4 với blockers chính xác nếu còn; tiếp tục phần không phụ thuộc. Không đổi pending thành conditional acceptance. Owner acceptance và DEP3/merge/deploy là bước sau, chưa thực hiện trong nhiệm vụ này.

### 16.4 Điều kiện kết thúc và gói trả kết quả

| Gate | R6 owner tasks | Bằng chứng phải có ngoài code/local |
|---|---|---|
| G3 | 1 | Native/scan/mixed fidelity, canonical PG reload và true hard-limit/cleanup Windows+Linux |
| G4 | 2 | Dynamic producers/full-membership CAS, actual normalized vector receipt, effective collection/query/IDF/ANN |
| G5 | 3 | PG immutable statistics v2, fresh workers/numerical full corpus và v1 upgrade/rollback |
| G6 | 4 +7 | Default collection/CI, real provider lifecycle/fallback/quality/usage; G4/G5 đủ |
| G7 | 5 +7 | Full request fences, canonical Q6, all-statement support, concise positives/follow-up và held-out thresholds |
| G8 | 6 +7 | Sealed release admission, actual stack/lifecycle/rebuild/rollback,32dispositions, superseding report, required DEP2 evidence và toàn upstream gates |

**Mỗi row32IDs:** original requirement/owner → production entrypoint → regression node/scenario → exact HEAD/base/config/schema → command/exit/count/skips → CI checkout/run → raw runtime/quality artifact/hash khi bắt buộc → reviewer disposition/limits. Một ID có thể code/local đạt nhưng gate vẫn pending; không ghi PASS trọn hàng khi phần bắt buộc thiếu.

**Packet cuối một lần:** approved R5 + R6 revision/diff → six HEAD/base và integrated RC →32-ID/G3–G8 matrices →commands/CI/raw captures →source/gold/scorer/criteria/role/freeze bindings →Cloudflare actual account/route/usage/$0 evidence →dependency owners/applicability/ACKs →effective target/migration/backfill/health/observation/rollback proposal. Chỉ secrets được che; IDs/hashes/counts/timestamps/failed observations cần cho audit phải giữ.

Đạt đủ packet là **đủ bằng chứng trình nghiệm thu**, không phải owner accepted, merged, deployed hoặc #153 Done. PR #215 đã merge. Thứ tự còn lại #216→#217→#218→#219→#220→#221, sau owner ra lệnh và required CI đúng merge subjects; conflicts/base/identity đổi phải revalidate phần chịu ảnh hưởng. Không triển khai chỉ để hoàn tất checklist này.

### 16.5 Prompt giao Anti và tự kiểm checklist

Prompt ngắn (gói bàn giao kèm full commit R6 thực tế):

> Tiếp tục #153 theo R6 §16 trong `docs/plans/2026-10-22-retrieval-v3-review-remediation.md`, worktree `C:/Developer/Projects/knora-agent-worktree/docs-retrieval-v3-acceptance-remediation`; đọc exact revision bàn giao cùng R5 đã duyệt ở #153 comment6381910609 và D1–D8. Dùng executing-plans, xử lý R6-0→7 tại đúng owner S3–S8, cascade #216→#221; đóng15ID còn mở, kiểm17regression và đủ32dispositions/G3–G8. Tự sửa/test/CI/runtime/review tới đủ bằng chứng nghiệm thu; không làm lại S2, sửa gold để pass, chạy local AI hoặc phát sinh phí. Không trần tổng AI/RC/vòng sửa, tránh lãng phí; quyền/resources/dependencies theo plan, chỉ gom hỏi khi thật sự vượt phạm vi đã duyệt. Ghi evidence đúngHEAD ở #153/PR, giao một packet cuối; chưa merge/deploy/đóng Issue.

**Tự kiểm R6:**15ID chưa đạt đều có owner, production counterexample, cách sửa trong hợp đồng R5, negative/positive và exit;17regression giữ đúng nghĩa. Các thiếu sót cũ không bị rút thành chỉ sửa assertion/RSS check/JSON digest/regex/JUnit. Hai OS, full-member PG, real Qdrant/CF, held-out roles/dependencies và six-PR CI có gate riêng. Không thêm giới hạn tổng lượt hoặc authority/evaluation store mới; không tuyên bố các tasks đã thực hiện khi mới soạn checklist.
