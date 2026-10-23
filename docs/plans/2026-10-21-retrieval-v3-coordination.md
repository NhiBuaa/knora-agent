# Retrieval V3 — Kế hoạch điều phối S3–S8

> Dành cho người/agent thực thi: dùng `executing-plans` theo từng plan con sau khi phạm vi tương ứng được duyệt. Tài liệu này điều phối phụ thuộc và nghiệm thu; tiến độ thực tế ghi tại Issue/PR.

**Mục tiêu:** Hoàn thành sáu giai đoạn còn lại của Issue #153, từ Document Understanding đến nghiệm thu bản phát hành Retrieval V3, giữ nguyên kết quả S2.

**Kiến trúc:** PostgreSQL giữ nguồn, quyền, phiên bản và trạng thái phục vụ có thẩm quyền. Qdrant là chỉ mục dẫn xuất có thể dựng lại. Parser → chunking → query planning → retrieval/ranking → evidence → answering có ranh giới rõ, dùng lại các seam hiện hữu.

**Công nghệ:** Python, PostgreSQL, Qdrant, pypdf; Docling chỉ dùng phần không chạy model local, AI OCR/layout và mọi inference dùng Cloudflare. LangChain tích hợp từng seam sau kiểm chứng tương thích. Cross-encoder phải có endpoint Cloudflare và đạt chất lượng Việt–Anh; tên mục tiêu `Qwen3-Reranker-0.6B` trước đây không chứng minh provider hỗ trợ. Không thêm hệ orchestration/queue/plugin mới.

**Đặc tả:** [Issue #153](https://github.com/NhiBuaa/knora-agent/issues/153), đặc biệt các mục 3–6 và quyết định Document Understanding, Query Understanding, Stable Contracts, Evaluation-driven Development. [Thứ tự S1–S8](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6162248497) được bổ sung bởi các quyết định mới hơn trong Issue.

**Trạng thái tài liệu:** Cập nhật theo bảy câu trả lời được người dùng duyệt ngày 21/10/2026, cùng hai sửa đổi: Cloudflare-only AI và tự tra lại nguồn trước kết luận thiếu thông tin. Lượt này sửa bảy plan; chưa bắt đầu implementation/runtime. Hợp đồng dưới đây áp dụng khi thực thi, không chuyển quyền runtime S2 sang V3 hoặc cấp quyền merge/deploy tại target chưa xác định.

## 0. Hợp đồng thực thi đã thống nhất

| Câu hỏi | Quyết định và cách thực hiện |
| --- | --- |
| Q1 — Điểm kết thúc | Hoàn thành toàn #153, gồm triển khai tại target được duyệt và kiểm tra sau triển khai; RC đạt chỉ là mốc trung gian. Public demo #181 là scope riêng. S8 chuẩn bị một gói cutover cụ thể để owner quyết định cuối cùng. |
| Q2 — Quyền tự quyết | Người thực thi chọn thuật toán, pins, routing, persistence, tham số và giới hạn hữu hạn bằng tài liệu, development benchmark và review độc lập trong ràng buộc đã duyệt. G3–G7 là gates bằng chứng: đạt thì tiếp tục, không xin lại từng quyết định kỹ thuật. Không được tự hạ acceptance criteria, đổi scope sản phẩm, quyền dữ liệu hoặc ngân sách. |
| Q3 — AI và tài nguyên | Chỉ Cloudflare cho embedding, vision/OCR/layout có AI, reranking, query planning, support/completeness, generation và semantic judge nếu dùng. Không Ollama, tải weights hoặc chạy model local CPU/GPU. Local backend/PostgreSQL/Qdrant, parser/rendering/tokenization/scoring không model được phép. Trả phí 0 USD; không nâng gói/overage, không đổi provider ẩn. Chỉ dữ liệu public/synthetic được phép gửi; private #146 giữ local và không đưa vào đường AI cloud. |
| Q4 — Workload | Mục tiêu kiểm chứng: 3 câu hỏi đồng thời, 1 PDF xử lý tại một thời điểm, corpus tối đa 10.000 chunks. Đây là workload mục tiêu, chưa phải năng lực đã đo. ANN scale diagnostic riêng, không thay gold hoặc tự nâng production workload. |
| Q5 — Dữ liệu và người review | Người thực thi chuẩn bị source/gold/bindings và kiểm tra độc lập candidate outputs; gom thành gói ở các mốc freeze S3, S4, S7 và S8 để owner duyệt. Không hỏi theo từng chunk/case; không ký thay owner hoặc tự coi nhãn máy sinh là truth. |
| Q6 — Thiếu bằng chứng | Top-K thiếu không có nghĩa tài liệu thiếu. Tự tìm lại trong nguồn được phép, kiểm tra đúng chương/trang/phạm vi rồi trả lời kèm citation nếu tìm được. Chỉ nói “tài liệu không nêu [thông tin cụ thể]” khi phạm vi cần thiết được kiểm tra đủ. Extraction/OCR lỗi, quota/deadline/budget hết hoặc coverage chưa biết là chưa xác minh được. Ambiguity thì hỏi rõ trong Conversation; không bịa phần so sánh còn thiếu. S7 Task 7 sở hữu quy trình có giới hạn này. |
| Q7 — Điều phối | Plan cha được cập nhật #153/PR và gửi yêu cầu ACK/phối hợp hữu hạn trong scope đã duyệt; tiếp tục phần độc lập khi chờ. Không sửa worktree khác hoặc lấy runtime/credential của họ; không ôm toàn #148/#150/#158. Phụ thuộc bắt buộc chưa đạt không được miễn hoặc gọi Done. |

Trước mỗi runtime package, người thực thi ghi exact source/model/endpoint/config IDs, quyền tài khoản, tài nguyên riêng và **con số** tối đa cho pages/bytes/tokens/calls/retries/concurrency/wall time/storage, gồm cả tra nguồn bổ sung; kiểm tra quota còn lại và cơ chế chặn trả phí trước gọi. Tự chọn mức hữu hạn trong quyền/tài nguyên đã có, freeze trước run, ghi observed usage; thiếu quota thì chia batch/checkpoint hoặc dừng package với lý do cụ thể, không retry vô hạn hoặc tự mua thêm. Có model trong catalog không chứng minh quyền tài khoản hay chất lượng. Không đủ dữ liệu được phép thì gói tương ứng chưa nghiệm thu.

Chỉ đưa owner quyết định phần không thể tự suy ra: quyền dữ liệu/tài nguyên chưa được cấp, thay ràng buộc hoặc requirement xung đột khả năng Cloudflare, các gói gold freeze và nghiệm thu/cutover cuối. Gom các mục chưa giải quyết thành một gói có phương án, bằng chứng và ảnh hưởng. Target triển khai, credentials/ownership và cutover cụ thể hiện chưa có trong bảy câu trả lời; S8 phải xác định và trình duyệt trước thao tác đó. Không gọi toàn chương trình Done khi chỉ có RC.

## 1. Điểm xuất phát đã kiểm tra

- S2 được [owner nghiệm thu PASS](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6308954098). [PR #204](https://github.com/NhiBuaa/knora-agent/pull/204) đã merge tại `de7f97dac40823cc5b9da3e626522a05caa8b732`; head được nghiệm thu là `49187d037c919b75db65fe4a20fb1009629b9206`. Không làm lại S2; các test S2 trong plan là kiểm tra hồi quy khi bị ảnh hưởng.
- Bộ S1 source-gold/Baseline B đã có trong main qua tích hợp S2. PR S1 là [#189](https://github.com/NhiBuaa/knora-agent/pull/189), hiện CLOSED, không phải #184 và không phải đã merge. Review ngữ nghĩa/chất lượng S1 còn là việc riêng; không dựng lại corpus hoặc gọi baseline cũ là chất lượng V3 đã đạt.
- [Audit S3](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6309121037) là đầu vào thiết kế, chưa phải quyết định cho triển khai. Checkout soạn plan: `ac48a372d78e48d8dfa3f32424fb98dfe54af9c1`; backend/evals tương đương main nêu trên tại lúc audit.
- Mọi lần thực thi phải đọc lại main, Issue và thay đổi liên quan sau mốc này. Không lấy trạng thái trong plan thay cho trạng thái GitHub hiện hành.

## 2. Sáu plan con và thứ tự bàn giao

| Giai đoạn | Plan thực thi | Đầu vào bắt buộc | Đầu ra để giai đoạn sau dùng |
| --- | --- | --- | --- |
| S3 | [Document Understanding](2026-10-21-retrieval-v3-document-understanding.md) | S2 đã nghiệm thu; source-gold S1; quyết định model/provenance S3 | Canonical source model, parser/chunker có version, annotations cấu trúc được review; finite population mới cho benchmark |
| S4 | [Dense và hybrid search](2026-10-21-retrieval-v3-dense-hybrid-search.md) | S3 có derivation/profile ổn định để so sánh | Ba mode cho PDF/text, backfill và corpus-statistics snapshot động; filtered HNSW/TurboQuant, DBSF 200+200→100; reviewed development relevance judgments và ranking scorer trước benchmark |
| S5 | [Sequential Dependence ranking](2026-10-21-retrieval-v3-sequential-dependence-ranking.md) | S4 candidate/metric contracts và development judgments; tokenizer/positions cùng version | Ordered/unordered positional scoring ≤100 candidates sau DBSF; evaluation-only Phrase Boost comparator có công thức/version, ablation và fallback rõ |
| S6 | [Reranking và evidence](2026-10-21-retrieval-v3-reranking-evidence.md) | S5 ranking/traces ổn định | Cross-encoder cấu hình được, chuẩn hóa điểm, MMR, evidence budgets và fallback DBSF+SDM |
| S7 | [Query Understanding và coverage](2026-10-21-retrieval-v3-query-understanding-coverage.md) | S6 evidence contract và toàn chuỗi retrieval | Planner có giới hạn, chọn đủ nhóm, tự tra nguồn bổ sung, final-support/answer-completeness trước delivery; runtime không dùng gold |
| S8 | [Tích hợp và phát hành](2026-10-21-retrieval-v3-integrated-release.md) | S3–S7 có bằng chứng riêng, phụ thuộc liên quan có trạng thái rõ | RC cố định, held-out, security/recovery/rollback, owner nghiệm thu và triển khai/kiểm tra target được duyệt |

Đường chính: **S3 → S4 → S5 → S6 → S7 → S8**. Có thể đọc tài liệu/chuẩn bị fixtures của phần sau sớm. Không tích hợp dựa trên contract chưa chốt, không lấy CI của một SHA làm bằng chứng cho SHA khác. Mỗi phần chỉ bàn giao sau review và gate của chính phần đó; không chờ S8 mới kiểm tra bảo mật hoặc chất lượng.

## 3. Ràng buộc chung

1. **Quyền và lifecycle:** trusted Workspace/tenant/document/group scope do backend và PostgreSQL quyết định trước Top-K ở mọi branch. Kiểm tra lại eligibility trước generation và trước lưu/giao citation. Không dùng newest source version thay cho serving pointer; không để archive/revoke/delete/stale generation lọt qua fallback.
2. **Nguồn và citation:** source text, search-normalized text và AI-generated text là các biểu diễn khác nhau. Citation truy về đúng Document Version/page/span/region đã xác minh. Không dùng offsets sau NFKC/lowercase làm offsets nguồn; không bịa bbox, confidence hoặc hierarchy.
3. **Cấu hình bất biến:** không sửa ID/behavior legacy V1/V2, threshold `0.65` hoặc `0.657410732025`. Score BM25/cosine/DBSF/SDM/reranker không cùng đơn vị. Policy mới có ID/version, quy tắc sufficiency và calibration riêng. Legacy evidence giới hạn 5 chunks/3000 tokens giữ nguyên; muốn khác cần policy mới được duyệt.
4. **Baseline đã chốt:** HNSW `m=16`, `ef_construct=100`, `hnsw_ef=256`; TurboQuant `bits4`, float32 originals cold/on disk, quantized pinned/RAM, `rescore=true`, `oversampling=2.0`; không `datatype=turbo4`, không quantize sparse. BM25 200 + dense 200 → native DBSF 100 → SDM ≤100. RRF `k=60` là so sánh/quay lui; ACORN chỉ theo bằng chứng filtered recall.
5. **S2 là nền đã có:** BM25-only từ query đến evidence có **0 query embedding calls**, optional embedding provenance đúng mode, leases/fencing/CAS/receipts/reconcile tiếp tục áp dụng. Lỗi dịch vụ/chỉ mục thiếu không được đổi thành refusal “không có bằng chứng”.
6. **Chi phí và dữ liệu:** tuân thủ Q3: mọi AI chỉ Cloudflare, không local inference/weights. Quyền runtime S2 không thay preflight V3 về endpoint, tài khoản, dữ liệu và quota. Private #146 không gửi cloud; chỉ chạy kiểm tra không AI phù hợp tại local hoặc ghi trường hợp AI chưa chạy, không tự đổi nhãn/loại khỏi denominator để báo đạt.
7. **Không mở rộng hạ tầng:** giữ queue/job hiện có. HyDE, AI contextualization, parent-child expansion và multi-hop production cần chứng minh nhu cầu/duyệt tương ứng; không là việc ngầm của bảy plan này. Không đưa LangGraph/Agents của #147 vào #153.

## 4. Dữ liệu đánh giá và hợp đồng bàn giao

Nguồn cố định: corpus SHA256 `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`, dataset SHA256 `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`. Giữ nguyên `evals/datasets/pdf_retrieval_v3_v1*`, approval/manifests, raw PDFs, gold và các báo cáo lịch sử. Phiên bản bổ sung có review riêng; không sửa gold để làm candidate đạt.

Baseline B: 16 documents/47 chunks, 61 mapped/25 missing anchors; 60 cases gồm 35 retrieval-evaluable, 17 extraction/mapping missing, 8 no-answer. Đây là số lịch sử, không phải kết quả mới. Mapping mới phải review nguồn trước scoring. Không tính missing/not-applicable thành miss=0; không gọi 86 anchors là ground truth đầy đủ mọi trang.

S3 bổ sung annotation cấu trúc có version/review riêng, gắn raw hashes và vùng được chấm; không biến 86 anchors thành transcription/table/heading truth. Finite population dùng so parser không giải quyết upload production: S4 phải sở hữu corpus membership/statistics snapshot động, chuyển generation nhất quán, text-ingestion producer và backfill. S4 Task 7 chuẩn bị development relevance judgments và pure ranking scorer trước benchmark Task 8; đây là supplement riêng với S3 structure truth, không phụ thuộc held-out S8. S5 dùng cùng snapshot cho positional statistics, cùng ranking judgments/scorer cho comparator; S6 giữ bounded candidate pool và locators để S7 chọn đủ nhóm trước MMR fill, revalidate final support rồi kiểm tra đủ nội dung answer.

### Ma trận so sánh bắt buộc theo §6 của Issue

| Nhóm | Đối chứng và candidate bắt buộc | Owner / gate |
| --- | --- | --- |
| Lexical | PostgreSQL FTS vs Qdrant BM25-only vs BM25+Phrase Boost vs BM25+SDM; k1/b `1.2/0.75`, `0.9/0.4`, `1.5/0.75`, measured avg_len, global-vs-tenant IDF | S4 đo FTS/BM25 và profile; S5 hoàn tất phrase/SDM; S8 xác nhận |
| Semantic | pgvector baseline vs Qdrant HNSW cùng model/dimensions/metric/filter; Qdrant exact filtered float32 làm reference ANN | S4 / G4; S8 |
| Quantization | float32 exact + HNSW vs bits4 giữ float32 originals; dense Recall@200, hybrid nDCG@10/MRR/citations, p50/p95/RAM/disk/indexing throughput, cold/warm cache | S4 / G4; S6 kiểm tra tác động evidence; S8 |
| Hybrid | Legacy PostgreSQL FTS+vector+Knora RRF vs full V3 vs DBSF+SDM không neural reranker | S6 hoàn tất ablation sau S4–S5; S8 xác nhận cùng RC |

Mục tiêu quantization đã có trong Issue: **mức giảm tuyệt đối hybrid nDCG@10 ≤0.01** so với float32 HNSW tương ứng, giữ các tầng khác cố định. Chốt metric protocol/relevance labels hợp lệ trước đo; binary relevance chỉ dùng khi protocol xác nhận phù hợp. Thiếu nhãn thì gate chưa đánh giá được, không bỏ mục tiêu hoặc ghi PASS. Với ngưỡng quality/SLO còn mở, người thực thi đề xuất con số từ baseline S3–S7 trên workload Q4, ghi lý do/đánh đổi và review độc lập; freeze cùng gói G8 trước final held-out. Không tự nhận một SLO kinh doanh chưa được nêu là đã duyệt, không hạ ngưỡng sau xem kết quả. Corpus 47 chunks không chứng minh ANN Recall@200: S4 chuẩn bị workload scale riêng, eligible population >200 và bằng chứng ANN thực thi, tách khỏi semantic gold và frozen 16/60.

Phân chia gate không tạo vòng phụ thuộc: G4 nghiệm thu subset lexical/semantic/quantization đã có tại S4 bằng development supplement/scorer; G5 bổ sung Phrase Boost/SDM; G6 hoàn tất ranking/evidence hybrid matrix; G7 bổ sung query/group-selection/answer-completeness. G8 kiểm tra toàn bộ trên RC và held-out độc lập bằng metric protocol/scorer đã kiểm chứng. Không dùng chung candidate pool để so khả năng tìm ứng viên của hai retrievers; chỉ fixed-pool cho ablation scorer/reranker, còn system comparison giữ nguồn/cases/scope cố định và ghi candidate pool riêng từng policy.

Mỗi bàn giao ghi trong Issue/PR, không tạo session ledger cạnh tranh:

- Full subject/base SHA; tree/diff và config/profile/schema/model/artifact hashes; upstream gate được dùng.
- Producer/consumer contracts, migration/backfill/reindex nếu có; compatibility tests, cách opt-in/quay lui.
- Từng case/run/attempt/workspace/trace ID có join chính xác; attempted/evaluable/failed/not_run, failure taxonomy, per-stage observations. Stage chưa chạy là `not_run`/`unavailable`, không phải 0 ms/0 cost.
- Các phép đo đúng tầng: extraction → query → candidate recall → ranking → coverage/selection → answer/citation. Faithfulness không thay correctness; không dùng LLM judge bù lỗi deterministic security/provenance.
- Quality delta, p50/p95, CPU/RAM local, index size, Cloudflare calls/quota/chi phí đo được dưới cùng workload/hardware. Không yêu cầu GPU local. Chưa có nhãn relevance grades thì không báo nDCG/MAP như đã hợp lệ.
- Findings/review, CI đúng head, runtime đúng subject và owner acceptance là các trạng thái độc lập. Không suy từ một trạng thái sang trạng thái khác.

## 5. Các điểm quyết định cần chuẩn bị trước thực thi

| Gate | Gói cụ thể phải sẵn sàng để review | Tài liệu chịu trách nhiệm |
| --- | --- | --- |
| G3 | Canonical Knora model/source-map/persistence, compatibility; reviewed structure annotations/metric denominators; Docling không local model + Cloudflare OCR/layout feasibility, finite resource envelope | S3 |
| G4 | Profile dense/hybrid, pins server/client, collection schema/IDF; dynamic corpus-statistics transition; PDF/text ingestion/backfill; reviewed development judgments/scorer; valid ANN và subset matrix §6 thuộc S4 | S4 |
| G5 | Công thức SDM, positions/window/smoothing/weights; Phrase Boost evaluation policy/formula/lambda; calibration protocol và lexical matrix | S5 |
| G6 | Cloudflare cross-encoder/model identity/license/quota và Việt–Anh quality; system Admin config, normalization/MMR, finite inference envelope | S6 |
| G7 | Query/source-verification limits, ambiguity/absence/unknown; support, selection/repair, final-answer completeness và semantic false-pass gates | S7 |
| G8 | Frozen quality/security/SLO/cost gates, held-out, RC identity, target/rollout/rollback, owner acceptance và kiểm tra sau triển khai | S8 |

G3–G7 dùng quyền tự quyết Q2: ghi lựa chọn cụ thể, kiểm chứng và review rồi đi tiếp khi đạt, không yêu cầu owner duyệt từng tham số. Human source/gold freeze Q5 và final G8 vẫn cần record của người có quyền; review độc lập không thay owner acceptance. Giá trị chưa chọn không được gọi đã chốt; runtime cần preflight hữu hạn theo §0. Thiếu quyền không cản test offline hoặc chuẩn bị gói review.

## 6. Phối hợp và migration từng phần

- #153 sở hữu production parser/query/retrieval, PDF gold/mapping và các gates Knora. [#158](https://github.com/NhiBuaa/knora-agent/issues/158)/[#192](https://github.com/NhiBuaa/knora-agent/issues/192) sở hữu DeepEval/Langfuse/Workbench integration và live package của họ. Không thiết kế lại hosting, judge, retention hoặc export trong plan này.
- Shared readers/schema/composition chỉ phối hợp khi có **delta mới**: chỉ rõ base/head, file/hunks, producer/consumer, yêu cầu ACK hữu hạn. ACK cũ đã hoàn tất không bị mở lại. Không sửa worktree của bên kia hoặc mượn DB/port/credential/runtime của họ.
- LangChain: S3 loaders/Docling và splitters; S4 Embeddings/Cloudflare adapter và `langchain-qdrant`; S6 Chat Models/Prompt Templates/Structured Outputs; S7 rewrite/multi-query/decomposition. Kiểm tra parity ở từng seam; không wrapper nào được gọi local model/provider khác. Native adapter là phương án hợp lệ đã cho phép khi abstraction không giữ Knora invariants: ghi mismatch/tests/lý do, không xin lại quyết định này hoặc nói toàn bộ code đã dùng framework.
- #148 Group Knowledge và #150 purge/retention có authority riêng. Test phần thực sự tích hợp; thiếu phụ thuộc thì ghi chưa kiểm chứng, không tạo hỗ trợ giả. [#181](https://github.com/NhiBuaa/knora-agent/issues/181) vẫn cần toàn #153 + #158 và nghiệm thu chất lượng; S2 hoặc một plan con PASS không gỡ dependency này.

## 7. Quy trình lặp cho từng task

- [ ] Đọc lại AGENTS/CONTEXT/architecture/seams và Issue; xác nhận authorization, trạng thái upstream, working tree và exact base. CodeGraph theo đúng worktree; Context7 cho API thư viện. Tạo worktree implementation riêng trực tiếp dưới `C:/Developer/Projects/knora-agent-worktree`, nhánh/thư mục tên mô tả, không chỉnh worktree phiên khác.
- [ ] Xác định callers/tests/fixtures/config/exports bị ảnh hưởng. Viết test hành vi/negative trước, chạy thấy failure đúng nguyên nhân; chỉ sửa đủ boundary cần thiết, chạy lại đúng test đến đạt. Test fixture không chứng minh model/runtime thật.
- [ ] Commit theo task sau khi kiểm tra diff và kiểm chứng cần thiết. Commit message mô tả thay đổi, có `Refs #153`; không trộn frozen data hoặc thay production defaults ngoài scope.
- [ ] Với Python diff: `python -m ruff format .`, `python -m ruff format --check .`, `python -m ruff check .`. Nếu frontend/shared/generated có diff, chạy các formatting/export checks bắt buộc theo AGENTS; không sửa generated OpenAPI bằng tay.
- [ ] Theo [Verification Contract](../runbooks/ci.md#verification-contract), chọn đúng backend/database/windows/runtime partition. `--ci-suite` luôn đi cùng `--ci-selection`; không dùng backend partition để claim test pypdf thuộc windows đã chạy. Đọc JUnit/selection, đếm collected/executed/pass/fail/skip; exit 0 với 0 test không đạt gate.
- [ ] DB/runtime/provider commands trong plan chỉ chạy trên môi trường riêng đã được duyệt theo [Agent environment](../runbooks/agent-environment.md). Ghi lệnh/exit/count/hash và lỗi của mọi attempt; không đè failed attempts. Cleanup chỉ tài nguyên đã xác nhận ownership.
- [ ] Review diff, xử lý findings, cập nhật Issue/PR theo trạng thái: code đã viết, kiểm tra local, CI, runtime, review, nghiệm thu, merge, deploy. Thực hiện selective closeout theo [issue tracker guide](../agents/issue-tracker.md#selective-closeout). Không tự merge.

## 8. Điều kiện hoàn tất toàn chương trình

- [ ] Sáu plan con có deliverables và evidence được chấp thuận, mọi requirement bắt buộc có case/trace/test tương ứng.
- [ ] S8 chứng minh end-to-end PDF/Turn và text HTTP/CLI, backfill/corpus transitions, tự tra nguồn/absence-vs-unknown, group-aware selection/final-support/answer-completeness, matrix §6 và ANN hợp lệ trên workload Q4, Cloudflare-only/no-local-model, recovery/security trên RC đã pin.
- [ ] Owner nghiệm thu và duyệt cutover cụ thể; triển khai tại target đó và kiểm tra sau triển khai đạt, có đường quay lui đã thử và kế hoạch nghỉ legacy. Chỉ RC đạt, thiếu target hoặc dependency bắt buộc vẫn là chưa hoàn thành toàn #153; không gộp public demo #181 vào scope này.
- [ ] Tiến độ/acceptance nằm ở #153/PR; bảy tài liệu này vẫn là kế hoạch có liên kết, không thành nguồn trạng thái thứ hai.
