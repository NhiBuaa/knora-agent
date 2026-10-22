# Retrieval V3 — Kế hoạch sửa lỗi sau code review

> Dành cho agy: dùng `executing-plans`, xử lý từng task và tự review trước chuyển bước. Đây là phần bổ sung để hoàn thành bảy plan đóng băng; không thay thế hoặc giảm yêu cầu của chúng. Không tự tạo subagents chỉ vì tài liệu này.

**Mục tiêu:** Khắc phục 15 findings còn mở và N01 sau review lần hai, giữ regression cho 10 findings đã PASS, chứng minh G3–G8 theo đúng subject và theo việc đến nghiệm thu toàn #153 trong quyền đã cấp.

**Kiến trúc:** Sửa tại owner của từng stage S3→S8, truyền thay đổi upstream xuống stack. PostgreSQL giữ nguồn, quyền, phiên bản, canonical derivation và serving state; Qdrant là projection có thể dựng lại. Dùng các seam ingestion, answering, provider và runtime hiện hữu; không thêm orchestration hoặc kho trạng thái song song.

**Công nghệ:** Python 3.12 của CI; PostgreSQL, Qdrant, pypdf/Docling không local ML; Cloudflare là provider AI duy nhất; pytest, Ruff và các workflow hiện hành.

**Đặc tả:** [Issue #153](https://github.com/NhiBuaa/knora-agent/issues/153); [frozen PR #215](https://github.com/NhiBuaa/knora-agent/pull/215); plan cha `2026-10-21-retrieval-v3-coordination.md` và sáu plan con cùng thư mục. Review lần một: `C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-chain-code-review-20261022.md`; review sau remediation: `C:/Users/NhiBuaa/AppData/Local/Temp/retrieval-v3-remediation-code-review-20261022.md`.

**Phiên bản R2:** R1 đã vào main qua PR #215, merge commit `ada17099050030fe527227fce0f2956539a2892f`. R2 được soạn tại `C:/Developer/Projects/knora-agent-worktree/docs-retrieval-v3-acceptance-remediation`, nhánh `docs/retrieval-v3-acceptance-remediation`, từ đúng merge commit đó. Không sửa bảy plan đóng băng. Những câu mô tả lần soạn R1, pins cũ và lỗi401 trong các mục dưới là lịch sử; §12 quy định delta thực thi hiện hành.

**Thẩm quyền:** Người dùng yêu cầu lập kế hoạch và prompt chuyển Anti sau review lần hai trong hội thoại này, ngày22/10/2026; chưa có phê duyệt nghiệm thu hoặc lệnh merge/deploy R2. Khi người dùng gửi prompt bàn giao có SHA của R2, Anti ghi nhận đúng lời giao đó và SHA trong #153/PR theo Q7, không bịa approval URL. Quyền kỹ thuật Q2 tiếp tục áp dụng trong phạm vi đã duyệt; các gói gold và cutover vẫn cần owner theo Q1/Q5.

**Ngày:** 22/10/2026, Asia/Saigon. Đây là kế hoạch, không phải trạng thái nghiệm thu. Tiến độ và quyết định thực tế tiếp tục ghi ở #153/PR được phép, không cập nhật tài liệu này thành session ledger.

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
