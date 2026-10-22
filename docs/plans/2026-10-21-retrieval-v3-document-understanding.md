# Retrieval V3 — Kế hoạch S3: Document Understanding

> Dành cho người/agent thực thi: dùng `executing-plans` sau khi phạm vi được duyệt; tuân thủ [plan cha](2026-10-21-retrieval-v3-coordination.md), đặc biệt ràng buộc dữ liệu và quy trình kiểm chứng.

**Mục tiêu:** Có biểu diễn tài liệu chuẩn độc lập parser, layout/table/hierarchy và OCR chọn lọc, anchors có thể kiểm chứng; so sánh Docling với pypdf trên dữ liệu S1 trước quyết định mặc định production.

**Kiến trúc:** Giữ facade `PdfTextExtractor.extract()` tương thích; tách extraction/normalization khỏi chunking ở nội bộ. Adapter trả dữ liệu Knora, không đưa `DoclingDocument` vào domain/persistence/citation. PostgreSQL gắn canonical provenance với derivation/Chunk Set.

**Công nghệ:** pypdf baseline; Docling native parsing/rendering không model local, OCR/layout có AI chỉ qua Cloudflare. Đánh giá `langchain-docling` và `langchain-text-splitters` ở adapter boundary; loader mặc định không được kích hoạt model local.

**Đặc tả:** [#153](https://github.com/NhiBuaa/knora-agent/issues/153), Document Understanding + Evaluation-driven Development; [audit S3](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6309121037). **Trạng thái:** áp dụng Q1–Q7 của plan cha; người thực thi chốt persistence/profile bằng evidence G3. Cloudflare-only ưu tiên hơn hướng local OCR trước đây; runtime chưa được chạy trong lượt sửa plan.

## Ràng buộc và bàn giao

- Đầu vào: S2 đã nghiệm thu, S1 raw/source-gold/Baseline B nguyên vẹn. Không làm lại S2 hoặc sửa gold để khớp OCR.
- Giữ ADR0007 một physical page/chunk, content đúng slice `[start,end)` trong canonical page text, checksum và configuration identity. Relations có thể nối nhiều trang; không tự đổi public locator sang cross-page chunk.
- Đổi parser/chunker tạo derivation/Chunk Set mới của cùng raw Document Version. Không sửa source version hoặc ghi đè derivation đang phục vụ.
- OCR là capability bắt buộc, chỉ kích hoạt trang/region cần thiết, gồm mixed PDF có header text nhưng nội dung chính là raster. Không dùng minchars toàn file làm bộ phát hiện duy nhất.
- Bàn giao S4: schema/profile IDs, source-map validators, heading/table metadata, reviewed bindings/structure annotations và finite lexical population mới nếu chunks thay đổi; comparison + E2E report. Population này phục vụ benchmark cố định; S4 sở hữu production corpus động cho nguồn mới ngoài manifest. Structure annotations S3 không thay ranking relevance judgments; S4 Task 7 tạo supplement/scorer riêng từ accepted source/derivation bindings trước benchmark search. Parser routing/default chọn bằng evidence theo Q2, owner giữ final acceptance/cutover.

## Task 1 — Chốt canonical model và compatibility seam

**Files:** sửa `backend/src/knora/ingestion/pdf.py`, `backend/src/knora/adapters/pdf/pypdf.py`, `backend/src/knora/adapters/pdf/_pypdf_chunking.py`; tạo `backend/src/knora/ingestion/pdf_structure.py`, `backend/test/ingestion/test_pdf_structure.py`; mở rộng `backend/test/adapters/pdf/test_pypdf.py` và `backend/test/ingestion/test_pdf_job_processing.py`.

- [ ] Dùng quyết định canonical model Knora + adapters nội bộ đã có trong #153 §9.1; không hỏi lại SDK model hay Markdown-only. Chốt shape tối thiểu: raw hash/version/config digest, pages, ordered typed blocks, heading parents/path, table rows/columns/cells/merged spans, figure placeholders và native/OCR source anchors. Chỉ giữ dữ kiện thực có; metadata thiếu là unavailable. Ghi extraction completeness theo page/region để S7 không suy nguồn thiếu từ vùng chưa đọc được.
- [ ] Viết tests canonical validator: duplicate IDs, cyclic heading parent, invalid page/range/bbox, table span vượt grid, ambiguous source map, hash mismatch và incomplete pages đều bị từ chối. Trường `charspan` của item không tự được coi là offset canonical page.
- [ ] Thêm parity tests cho pypdf plain/layout: pages/content/checksum/offsets/chunk ordinals/token counts/derivation IDs giữ nguyên. Chạy test trước, xác nhận case mới fail đúng lý do; tách nội bộ mà không đổi facade/callers.
- [ ] Run sau sửa: `python -m pytest -p no:cacheprovider backend/test/ingestion/test_pdf_structure.py backend/test/ingestion/test_pdf_job_processing.py backend/test/adapters/pdf/test_pypdf.py`. Đọc số test; pypdf cần môi trường Windows phù hợp như CI.
- [ ] Gate G3 phần thiết kế: ghi contract/persistence và review tại #153 trước đổi schema/behavior; lựa chọn kỹ thuật theo Q2, không xin lại quyết định canonical model. Commit phần compatibility đã kiểm chứng với `Refs #153`.

## Task 2 — Chunking theo cấu trúc và source-map chính xác

**Files:** tạo `backend/src/knora/ingestion/pdf_chunking.py`, `backend/test/ingestion/test_pdf_chunking.py`; sửa `ingestion/pdf.py`, `ingestion/pdf_structure.py` trong package nêu trên và `_pypdf_chunking.py` chỉ khi cần bridge.

- [ ] Viết fixture nhiều cột, heading/TOC/header lặp, bảng merged cells, bảng tiếp trang và text lặp gây offset mơ hồ. Giữ fixtures mới nhỏ, synthetic; không đổi PDFs/gold đóng băng.
- [ ] Test thứ tự đọc, heading path, deterministic table serialization, giới hạn token/page, mỗi content slice và quan hệ cell/block→source. Không dựng heading/bbox từ text nếu parser không cung cấp chứng cứ.
- [ ] Tách source text khỏi search context. Tên tài liệu/heading xác thực được dùng metadata/search representation, không chèn phần suy diễn vào source citation. Chưa bật AI contextualization hoặc parent-child expansion.
- [ ] Thử splitter LangChain qua adapter với offsets/token budgets lặp lại được; loader `DOC_CHUNKS`/`MARKDOWN` mặc định không tự chứng minh giữ source map. Chỉ tích hợp khi parity đạt; ghi mismatch và dùng Knora chunker khi cần giữ invariants, không gọi migration đã xong nếu còn thiếu.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/ingestion/test_pdf_chunking.py backend/test/ingestion/test_pdf_structure.py backend/test/adapters/pdf/test_pypdf.py`; kiểm tra parity không đổi. Commit task sau diff review.

## Task 3 — Docling không model local và Cloudflare OCR/layout

**Files:** tạo `backend/src/knora/adapters/pdf/docling.py`, `backend/test/adapters/pdf/test_docling.py`; adapter OCR/layout Cloudflare tại `backend/src/knora/providers/cloudflare/pdf_understanding.py` và test cùng owning package nếu provider hiện có chưa đáp ứng. Sửa `backend/pyproject.toml`, `backend/src/knora/ingestion/pdf.py`, `backend/src/knora/infrastructure/settings.py`, composition `backend/src/knora/main.py`; dùng lại provider HTTP và subprocess/resource seam, không dựng local inference server.

- [ ] G3 feasibility trước integration: pin Docling native API/deps/license; chứng minh đường native/rendering không khởi tạo layout/OCR/table/local VLM hoặc downloader. Chọn Cloudflare vision/OCR route có API/model identity thực, quota $0, input limits, Việt–Anh/table quality và page/source-map fidelity. `toMarkdown` chỉ là candidate conversion, không tự chứng minh scanned OCR/table/provenance. Nếu Cloudflare không đáp ứng requirement bắt buộc, báo xung đột có evidence để owner quyết định; không bật local model hoặc bỏ OCR.
- [ ] Ghi exact runtime envelope theo plan cha §0: 1 PDF tại một thời điểm, maximum bytes/pages/render pixels, local process-tree CPU/RAM/storage/deadline; remote calls/tokens/retries/cost/quota và cleanup. Chỉ public/synthetic được phép gửi Cloudflare. Không áp pypdf 30s/256MiB hoặc waiver S2 cho Docling.
- [ ] Red fake-converter/provider tests: native/layout/table/scan/mixed, malformed/partial/missing page, exception/crash/timeout/RSS và CF 429/quota/unsupported language. Chặn model loaders/downloads và non-Cloudflare endpoints/redirects trước khi có egress; assert zero local inference/download calls. Test thư viện mặc định tự tải model bị từ chối. Không publish partial hoặc kích hoạt fallback local dù có text; giữ serving derivation cũ.
- [ ] Implement native pipeline không ML và remote Cloudflare adapter tối thiểu sau feasibility/parity review. `enable_remote_services=False` không tự chặn weights download; không dùng standard pipeline mặc định. Nếu dùng Docling remote VLM seam phải opt-in tường minh, allowlist Cloudflare, disable mọi stage local ML và chứng minh không có hidden provider. Không cài/tải weights; pin model ID và request/response digest, provider không cho revision/hash thì ghi unavailable, không bịa pin.
- [ ] Viết test selective OCR page/region: text header không che khuất raster evidence; pages đủ text không bị OCR toàn file. Giữ confidence/engine/regions trong provenance khi thật sự có; không đoán số thiếu.
- [ ] Run offline `python -m pytest -p no:cacheprovider backend/test/adapters/pdf/test_docling.py backend/test/ingestion/test_pdf_job_processing.py` và Cloudflare adapter suite mới. Sau runtime preflight mới đo remote OCR thật, quota/error và local render child-tree timeout/cleanup. Fake tests không chứng minh Việt–Anh OCR; báo riêng. Commit task.

## Task 4 — Persistence, population và lifecycle xuyên cả hai nhánh

**Files:** sửa `backend/src/knora/ingestion/job_processing.py`, `backend/src/knora/adapters/postgres/ingestion_jobs/coordination.py`, `backend/src/knora/adapters/postgres/tables.py`, `backend/src/knora/ingestion/lexical_population.py`, `backend/src/knora/infrastructure/lexical_configuration.py`; migrations theo thư mục Alembic hiện hành chỉ khi schema cần đổi. Tests: `backend/test/adapters/postgres/test_pdf_derivation_finalization.py`, `test_pdf_evaluation_e2e.py`, `test_s2_reprocess_retry.py`, `test_s2_job_readiness.py`, `backend/test/ingestion/test_lexical_population.py`.

- [ ] Chốt persistence tối thiểu sau kiểm tra schema main: canonical structured data gắn Chunk Set, giới hạn kích thước/format, commit nhất quán với chunk source map. Không thêm object store/job lifecycle thứ hai; migration additive và reprocess được, không backfill bằng suy diễn.
- [ ] Red tests cho **dense và extraction-only** finalization, thay `heading_path=[]` chỉ khi provenance hợp lệ; invalid/partial structure không commit hoặc activate. Kiểm tra fencing/lease, stale CAS, retry/crash và serving old derivation.
- [ ] New chunks không thuộc frozen47/upload profile S2. Tạo finite measured population/profile cho benchmark S3 với đúng native token counts/avg_len/checksums; giữ nguyên S2 manifests/config identities và `VerifiedLexicalPopulation` guard. Reindex/stage/receipt/readback trước CAS theo lifecycle hiện có. Không claim profile finite này nhận được PDF bất kỳ; bàn giao S4 Task 2 để giải quyết corpus membership/statistics động và chuyển toàn snapshot tương thích, không chỉ đổi digest cho một document.
- [ ] Shared schema/readers/composition delta có base/head/hunks và finite ACK mới với #158/#192 nếu bị tác động. Public chunk/citation/read projections giữ thông tin source cần thiết; cập nhật CONTEXT/ADR/seams đúng owner nếu có quyết định mới, giữ lịch sử cũ.
- [ ] Trên DB riêng đã duyệt, run `python -m pytest -p no:cacheprovider backend/test/adapters/postgres/test_pdf_derivation_finalization.py backend/test/adapters/postgres/test_pdf_evaluation_e2e.py backend/test/adapters/postgres/test_s2_reprocess_retry.py backend/test/adapters/postgres/test_s2_job_readiness.py backend/test/ingestion/test_lexical_population.py`. Thêm denied/cross-tenant/archive/stale/revoke/citation tests theo surface bị đổi; commit sau đạt.

## Task 5 — Annotation cấu trúc độc lập với parser

**Files:** tạo `evals/datasets/pdf_document_structure_v1.py`, `evals/datasets/pdf_document_structure_v1.manifest.json`, approval/annotation artifacts theo convention dataset hiện có và `evals/test/test_pdf_document_structure_dataset.py`; sửa `evals/runners/pdf_source_binding.py` chỉ để đọc version bổ sung. Giữ nguyên mọi `pdf_retrieval_v3_v1*` và Baseline B.

- [ ] Lập sampling manifest theo raw source hash, physical page/region và category native/multi-column/table/scan/mixed/hierarchy; ghi quyền sử dụng, số đơn vị cần review và phần không được annotate. 86 anchors hiện chỉ có source/page/text/region, không đủ ground truth cho mọi metric cấu trúc.
- [ ] Chuẩn bị truth bổ sung: transcription chuẩn cho vùng chấm completeness/CER/WER; ordered block IDs/reading order; table cell text/row/column/merged spans; heading IDs/parent relationships. Kiểm tra độc lập từ raw PDF, tách candidate outputs; synthetic fixtures/output model không tự là reviewed truth. Gom annotation/binding/rubric/hashes và kết quả review độc lập thành một gói freeze S3 để owner duyệt theo Q5, không hỏi từng vùng hoặc ký thay reviewer/owner.
- [ ] Chốt metric applicability và denominator theo page/region/table/heading/category trước benchmark: completeness trên vùng có transcription, order trên blocks đã review, table trên cell/grid truth, hierarchy trên relationships đã review; báo coverage annotation và missing/rejected labels riêng. Thiếu truth bắt buộc ở category mục tiêu thì chưa được chọn parser cho category đó; không bỏ scan/mixed failures để đạt gate.
- [ ] Red validator tests cho raw-hash drift, page/region thiếu, duplicate block IDs, invalid order/table spans/heading tree, thiếu reviewer và metric dùng label sai loại. Implement versioned loader tối thiểu; không sửa approval lịch sử hoặc nhãn để candidate đạt.
- [ ] Run `python -m pytest -p no:cacheprovider evals/test/test_pdf_document_structure_dataset.py evals/test/test_pdf_source_binding.py`; review annotation package và G3 metric protocol trước benchmark. Commit schema/validators và annotation artifacts được phép riêng.

## Task 6 — So sánh parser, binding và E2E có nguồn chuẩn

**Files:** sửa `evals/runners/pdf_source_binding.py`, `evals/runners/pdf_retrieval_v3.py` khi canonical projection cần bổ sung; tests `evals/test/test_pdf_source_binding.py`, `test_pdf_retrieval_v3_dataset.py`, `test_pdf_retrieval_v3.py`, `test_pdf_revalidation_selection.py`, `test_s2_pdf_retrieval_only.py`. Báo cáo mới dưới `evals/reports/` theo convention run hiện có, không ghi đè Baseline B.

- [ ] Test source-map/hash drift/ambiguous anchor/OCR khác transcription và exact workspace+trace binding. Source reviewer xác minh binding mới trước scoring; không fuzzy-match rồi tự gọi accepted.
- [ ] Trên cùng 16 source bytes được phép: giữ 86 anchors cho binding protocol hiện có, supplement Task 5 cho completeness/order/table/hierarchy/CER/WER đúng vùng/denominator. So pypdf↔Docling native+Cloudflare với chunker cố định trước; ablation chunker riêng sau. Đối chiếu quyền từng source trước gửi cloud; phần chưa có quyền ghi not_run, không âm thầm bỏ khỏi denominator. Báo page-span fidelity, extraction completeness, category failures và CF usage; không gọi anchors là full-page truth.
- [ ] Đủ 60 attempts và denominators; báo extraction/mapping failures riêng. Giữ embedding/query/ranking/generation cố định để cô lập parser; E2E model/provider chỉ sau quyền riêng. Kết nối runner Knora hiện có, không xây framework/judge mới.
- [ ] Runtime được duyệt: upload→persist→index readiness/CAS→query→source citation; partial/crash/retry/archive/stale/rollback; BM25-only vẫn 0 query embeddings. Đo resource envelope cả process tree, p50/p95 và failure rate thực.
- [ ] Run offline `python -m pytest -p no:cacheprovider evals/test/test_pdf_source_binding.py evals/test/test_pdf_retrieval_v3_dataset.py evals/test/test_pdf_retrieval_v3.py evals/test/test_pdf_revalidation_selection.py evals/test/test_s2_pdf_retrieval_only.py`; Ruff/CI/runtime/review theo plan cha. Commit eval changes riêng sau kiểm chứng.

## Gate nghiệm thu và quay lui

- [ ] Không sai nguồn/quyền/version/citation; parser-dependent binding review đủ, cả hai finalization paths giữ lifecycle safety. Fixture PASS không thay bằng chứng OCR/layout thật.
- [ ] Gói kết quả chỉ rõ hard gates, reviewed labels/denominators, quality/resource/Cloudflare usage và phần chưa kiểm chứng. Theo Q2 người thực thi chọn routing/default từng category từ development evidence và review, không xin lại từng lựa chọn kỹ thuật; thiếu nhãn/Cloudflare feasibility bắt buộc thì category chưa đạt. Owner giữ quyền duyệt gold freeze và final acceptance; không được gọi remote output là verified source nếu source mapping chưa đạt.
- [ ] Quay lui: chọn pypdf/profile cũ tường minh và serving generation đã xác minh, không relabel Docling failure thành pypdf success. Generation mới chưa đạt bị giữ không phục vụ, cleanup idempotent theo ownership. S4 nhận exact profiles/contracts/report đã được review.

## Tài liệu kỹ thuật đã đối chiếu

[DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/), [OCR](https://docling-project.github.io/docling/concepts/OCR/), [offline/artifacts options](https://docling-project.github.io/docling/usage/advanced_options/), [LangChain Docling loader](https://docs.langchain.com/oss/python/integrations/document_loaders/docling). Tài liệu API được tra qua Context7; pin runtime phải xác minh lại khi thực thi, không lấy docs main làm dependency đã được duyệt.

[Docling native PDF và remote options](https://docling-project.github.io/docling/usage/advanced_options/) mô tả native parsing không layout/OCR/table models; default pipeline có thể tự download models. [Cloudflare conversion](https://developers.cloudflare.com/workers-ai/features/markdown-conversion/) là khả năng cần đo trong quota, không là bằng chứng OCR/provenance đã đạt. Đối chiếu ngày 21/10/2026 qua Context7 và tài liệu chính thức; chưa gọi provider.
