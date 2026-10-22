# Retrieval V3 — Kế hoạch S6: Reranking và evidence

> Dành cho người/agent thực thi: dùng `executing-plans` theo scope đã duyệt và [plan cha](2026-10-21-retrieval-v3-coordination.md). Nhận bàn giao [S5](2026-10-21-retrieval-v3-sequential-dependence-ranking.md), chuẩn bị evidence seam cho [S7](2026-10-21-retrieval-v3-query-understanding-coverage.md).

**Mục tiêu:** Cross-encoder đa ngôn ngữ cấu hình được bởi Admin toàn hệ thống, kết hợp điểm đã chuẩn hóa và MMR để chọn evidence đúng nguồn/budget; lỗi model quay về cùng DBSF+SDM an toàn.

**Kiến trúc:** Reranker là provider sau SDM, tách khỏi generation và eligibility. Candidate IDs/provenance bất biến; evidence selection giữ citation, containment và budgets. Không để client/query planner chọn model hoặc mở scope.

**Công nghệ:** Cross-encoder trên Cloudflare, không local inference/weights. `Qwen3-Reranker-0.6B` là tên mục tiêu cũ, chưa chứng minh có endpoint Cloudflare; candidate khác phải đạt Việt–Anh quality gate và yêu cầu cross-encoder. LangChain Chat Models/Prompt Templates/Structured Outputs chỉ gọi Cloudflare sau provider seam, giữ Knora validation.

**Đặc tả:** [#153](https://github.com/NhiBuaa/knora-agent/issues/153), configurable cross-encoder, normalization/MMR, fallback và stable evidence contracts. **Trạng thái:** áp dụng Q1–Q7; lựa chọn model/normalization/MMR theo G6, không tải weights hoặc dùng quyền S2 để gọi runtime mới.

## Ràng buộc và hợp đồng

- Input reranker: query và authorized/hydrated source candidates sau SDM, tối đa 100 trong hybrid single-query; model/config ID, token/candidate/deadline budget. Output score gắn đúng candidate ID, score kind/model revision, không tự sinh source/citation.
- Không đồng nhất tên `Qwen` với production evidence-calibration policy cũ. Reranker score không tự là probability của answer correctness hoặc evidence sufficiency; threshold/model/policy được hiệu chuẩn riêng, không sửa `0.65`/`0.657410732025`.
- Legacy selection 5 chunks/3000 tokens/containment giữ behavior dưới ID cũ. Policy mới có thể đổi thứ tự/MMR trong budget đó; tăng budget phải có quyết định/policy riêng.
- S7 sẽ thêm support assessor, group-aware selection và answer completeness. S6 bàn giao cả bounded ranked candidate pool trước selection lẫn selected IDs, source text/locators, token costs, truncation mapping và query-group provenance; không discard pool trước khi S7 có cơ hội reserve đủ required groups. Group ID chỉ là nhãn mục tiêu, không phải kết luận supported. S7 kiểm tra final support sau MMR/budget và đủ nội dung answer trước delivery, không lấy reranker score làm support truth.

## Task 1 — Provider contract, pins và runtime feasibility

**Files:** tạo `backend/src/knora/providers/reranking.py`, `backend/test/providers/test_reranking.py`, `backend/src/knora/providers/cloudflare/reranking.py`, `backend/test/providers/cloudflare/test_reranking.py`; sửa dependency/composition hiện hành sau feasibility review G6. Dùng lại HTTP/auth/account settings, không dựng local inference adapter.

- [ ] G6 feasibility trước integration: tra catalog/API chính thức và quyền tài khoản Cloudflare; lập candidate cross-encoder matrix theo model ID, license/terms, query-document schema, output scores/index mapping, batching/truncation, Việt–Anh quality, latency/quota/$0. Model revision provider không cung cấp thì ghi rõ model-ID/config/time và giới hạn reproducibility; không bịa weights hash.
- [ ] Tài liệu Cloudflare có `@cf/baai/bge-reranker-base`; đây là candidate khả dụng trong catalog, không chứng minh Việt–Anh đạt hoặc tương đương Qwen. Chọn trong Cloudflare bằng development labels và review theo Q2; nếu không candidate nào đáp ứng yêu cầu đa ngôn ngữ/cross-encoder thì giữ G6 chưa đạt, trình một xung đột cụ thể có evidence. Không tự thay bằng local Qwen, provider khác hoặc prompt LLM rồi gọi là cross-encoder. Model card Qwen không là bằng chứng hosted availability; không dùng `from_pretrained`.
- [ ] Red tests deterministic fake provider: output order đổi, duplicate/missing/unknown IDs, nonfinite score, invalid shape, timeout, unavailable, budget/truncation lỗi. Input phải chỉ chứa authorized source text; reject model đổi candidate IDs.
- [ ] Implement Cloudflare adapter sau feasibility: ID mapping độc lập response order, finite batching/deadline/retries/calls theo §0 plan cha, endpoint/redirect allowlist và quota preflight. Red tests chặn local loader/download/non-CF endpoint, account/model config sai, 429 và hết quota; không tự tăng gói hoặc đổi provider. Test instruction-like source text không đổi quyền/config/score parsing.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/providers/test_reranking.py backend/test/providers/cloudflare/test_reranking.py`; runtime smoke/quality riêng sau preflight. Commit contract/provider riêng, không thêm adapter không dùng.

## Task 2 — Admin system configuration có version và rollback

**Files:** sửa `backend/src/knora/answering/retrieval_configuration.py`, `backend/src/knora/infrastructure/settings.py`, `backend/src/knora/main.py`; tạo `backend/src/knora/answering/reranking_configuration.py`, `backend/test/answering/test_reranking_configuration.py`.

- [ ] Dùng resolver deployment-wide cấu hình bất biến hiện có làm baseline; Admin vận hành chọn versioned Cloudflare config đã kiểm chứng. Không yêu cầu UI/hot-switch mới để đáp ứng system configuration. Nếu phát hiện nhu cầu sản phẩm mới ngoài baseline, gom đề xuất authz/audit/CAS/storage để owner quyết định; không biến Workspace owner thành system Admin.
- [ ] Config gồm provider/model/revision/template/score normalization+weights/MMR/token-candidate budgets/timeouts/fallback policy, ID/digest. Phiên bản không đổi giữa một request; thay model/config tạo ID mới, trace biết version đã dùng.
- [ ] Tests từ chối config thiếu license/compatible artifact/unknown model/nonfinite weights/invalid budgets. Client request, PDF, history hoặc LLM không được override deployment model/scope; config cũ resolve nguyên behavior.
- [ ] Test switch/rollback config giữa requests, request đang chạy giữ snapshot; endpoint mới chỉ khi scope riêng được duyệt và có unauthorized/non-Admin/CAS/audit tests. Baseline versioned resolver là lựa chọn hợp lệ, không hỏi lại việc xây Admin UI.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/answering/test_reranking_configuration.py backend/test/answering/test_retrieval_configuration.py`; commit config sau quyết định G6, không đổi default production ngay.

## Task 3 — Chuẩn hóa, MMR và selection có budget

**Files:** sửa `backend/src/knora/answering/evidence.py`, `backend/src/knora/answering/stores.py`; tạo `backend/src/knora/answering/reranking.py`, `backend/test/answering/test_reranking.py`; mở rộng `backend/test/answering/test_evidence.py`, `test_citation_excerpt.py`.

- [ ] Chốt normalization/combination và MMR redundancy metric từ development ablation; nếu MMR dùng vector, định nghĩa rõ mode BM25 không có dense embeddings. Không gọi query embedding trong BM25 hoặc ép sparse candidate có embedding provenance chỉ để MMR chạy.
- [ ] Red tests scale-invariance/degenerate equal scores/nonfinite/missing score, canonical identity ties và duplicate overlap. Không cộng raw BM25/cosine/DBSF/SDM/model scores. Mỗi decision lưu score/policy/outcome đủ audit.
- [ ] MMR giảm redundancy nhưng không loại unique source facts/citation anchors; containment vẫn chỉ đúng scope/chunk set/page quan hệ hợp lệ. Preserve bounded pre-selection candidates, group provenance, token costs và exact retained source spans cho S7 Task 6. Policy mới phải cho phép reserve verified support bundles trước MMR fill và không thay bundle nếu làm mất required group. Test trim/dedup/MMR làm assessment cũ invalid; không chuyển `coverage_id` thành supported chỉ vì chunk còn tồn tại. S6 single-query không cần giả lập multi-group verifier trước S7; giữ seam và legacy parity.
- [ ] Budget tokens/chunks sau selection phải đúng actual source text gửi generation; quá dài/truncation không cắt mất locator hoặc relabel source. Test duplicate paragraphs, conflicting documents, unique table evidence, empty candidates và token boundary.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/answering/test_reranking.py backend/test/answering/test_evidence.py backend/test/answering/test_citation_excerpt.py`; commit task khi cả legacy policy parity đạt.

## Task 4 — Pipeline, fallback và generation framework seam

**Files:** sửa `backend/src/knora/answering/module.py`, `backend/src/knora/answering/generation_validation.py`, `backend/src/knora/providers/structured_generation.py`, `backend/src/knora/providers/cloudflare/generation.py` và `backend/src/knora/providers/openai_compatible/generation.py` nếu được dùng làm transport Cloudflare; tạo `backend/src/knora/adapters/langchain/generation.py`, `backend/test/adapters/langchain/test_generation.py` khi cần bridge. Tests owning generation/provider và `backend/test/answering/test_module.py`, `test_generation_validation.py`, `test_question_stream_answering.py`, `test_s2_snapshot_fence.py`; giữ legacy compatibility, V3 chỉ resolve Cloudflare.

- [ ] Viết stage-order tests DBSF→SDM→cross-encoder→normalized combination→MMR/budget→generation. Lỗi/unavailable/invalid model output/budget exhaustion fallback **DBSF+SDM cùng scope**, ghi reason và model not-used; không dùng model khác hoặc coi operational fault thành no-evidence refusal.
- [ ] PostgreSQL recheck trước model thấy source, trước generation và citation persist/delivery; source/archive/revoke race fail closed, không chỉ revalidate lúc retrieval. Trace giữ pre/post ranks, score kinds/config, duration/usage, fallback và original IDs.
- [ ] Chat Models/Prompt Templates/Structured Outputs integration giữ prompt/version/schema/citation aliases/order/refusal semantics. Provider hỗ trợ structured mode nào phải xác minh; schema parsed success vẫn qua Knora validation. Không bật agent/tool loop hoặc tự gửi trace sang LangSmith.
- [ ] Bàn giao generation seam cho S7 Task 8: versioned required-group/support inputs và group→final-answer spans/citation mapping thêm tại protocol/adapter boundary mà legacy config vẫn chạy. S7 sở hữu source recovery/completeness, tests thiếu một phần và failure-before-delivery; S6 adapter parity không thay semantic evidence.
- [ ] Test malformed JSON, unsupported structured mode, refusal schema, invented citation, repeated markers, streaming disconnect/cancel. Frozen prompt/integration owner có delta thì phối hợp đúng base/hunks, không tự viết lại prompt-policy công việc khác.
- [ ] Run selected suites ở trên và `backend/test/answering/test_bm25_contract.py`; shared trace/readers ACK chỉ delta mới. Commit pipeline/framework changes theo phần đã verified.

## Task 5 — Model/evidence ablation và runtime acceptance

**Files:** sửa `evals/runners/pdf_retrieval_v3.py`, `evals/test/test_pdf_retrieval_v3.py`; tạo `evals/test/test_reranking_observations.py`, `backend/runtime_test/test_reranking_evidence.py`; calibration evidence mới theo convention `evals/calibration/`, không sửa artifacts legacy.

- [ ] Test score/usage/outcome projection nối exact case/run/trace/model/config; stages chưa chạy là unavailable/not_run. DeepEval/Langfuse qua #158 khi integration và quyền đã sẵn sàng; không tạo judge khác hoặc export private data mặc định.
- [ ] Dùng development judgments/scorer/metric policy S4: fixed candidate-pool ablation DBSF+SDM, +cross-encoder, +normalization/combination, +MMR; quality/ranking/coverage và final answer/citation riêng. System comparison §6 dùng candidate pool riêng của mỗi policy trên cùng source/cases/parser/embedding/query inputs/scope: legacy PostgreSQL FTS+vector+Knora RRF vs full V3 vs DBSF+SDM không neural reranker. Full V3 trước S7 chỉ là ranking/evidence candidate; final query/group-selection/answer-completeness effects đo riêng ở S7/S8. Development data chọn parameters; threshold calibration có split độc lập, sealed hashes/criteria trước validation.
- [ ] Giữ quantization đối chứng float32 HNSW vs bits4 cùng reranker/selection; kiểm tra mức giảm tuyệt đối hybrid nDCG@10 ≤0.01 theo protocol plan cha, MRR/citations và cold/warm resource deltas. Không dùng reranker đổi model/weights để che quantization loss trong cùng phép so sánh; thiếu relevance labels thì gate chưa đạt.
- [ ] Đo model actual p50/p95, batch/concurrency/cold/warm, local CPU/RAM, CF calls/token truncation/quota/cost trên workload 3 câu hỏi đồng thời của Q4; multilingual/table/identifier/no-answer/failure cases. Chặn vượt free quota trước gọi, không đòi local GPU/weights; có quyền tài khoản và dữ liệu cụ thể trước runtime.
- [ ] Runtime outage/timeout/partial scores/config switch/rollback và revoke/active-version races phải giữ evidence/citation safety; full E2E answer không được đánh đồng với model scorer smoke.
- [ ] Ruff/targeted regression/required CI đúng head và runtime đúng subject; trình G6 parameters/provider/default recommendation với acceptance evidence và limits. Commit eval/report changes đã review.

## Gate nghiệm thu và quay lui

- [ ] Cross-encoder Cloudflare chạy được, đạt Việt–Anh quality và license/profile/quota gates; không lấy model smoke thay chất lượng hoặc gọi target Qwen đã đạt khi model khác. Admin đổi versioned system config, client không đổi model. Normalization/MMR có ablation, BM25 không query embedding.
- [ ] Budget/citation/provenance/coverage metadata giữ đúng; fallback DBSF+SDM đã thử thật và không ẩn lỗi. Config/model score không thay các legacy calibrated thresholds.
- [ ] Quay lui config/reranker về version đã xác minh hoặc explicit DBSF+SDM khi model lỗi, cùng scope/snapshot; giữ artifacts để replay. S7 nhận selection/trace contracts, calibration và resource envelope đã review.

## Tài liệu kỹ thuật đã đối chiếu

[Qwen model card](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), [LangChain models/structured output](https://docs.langchain.com/oss/python/langchain/models#structured-output). Context7 mô tả schema parsing/provider-specific methods; đây không là bằng chứng model/API hiện có trên tài khoản Knora hoặc schema validation thay authorization/citation validation.

[Cloudflare BGE reranker](https://developers.cloudflare.com/workers-ai/models/bge-reranker-base/) được đối chiếu qua Context7/tài liệu chính thức ngày 21/10/2026. Catalog không xác nhận Qwen target hoặc chất lượng Việt–Anh; không có provider runtime nào được chạy trong lượt sửa plan.
