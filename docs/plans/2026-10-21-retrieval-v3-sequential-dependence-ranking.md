# Retrieval V3 — Kế hoạch S5: Sequential Dependence ranking

> Dành cho người/agent thực thi: dùng `executing-plans` trong scope đã duyệt và [plan cha](2026-10-21-retrieval-v3-coordination.md). Đầu vào [S4](2026-10-21-retrieval-v3-dense-hybrid-search.md); đầu ra cho [S6](2026-10-21-retrieval-v3-reranking-evidence.md).

**Mục tiêu:** Triển khai SDM bắt buộc với unigram, ordered và unordered positional features; đo đóng góp thực sau DBSF, giữ dense evidence và source provenance.

**Kiến trúc:** Positional data là derivation có tokenizer/content/generation identity. SDM xếp hạng lại authorized candidates sau retrieval/fusion, không mở thêm scope hoặc tự lấy ứng viên mới. Qdrant DBSF không thực hiện SDM.

**Công nghệ:** Python thuần cho scoring/validators theo reference đã chọn; lưu/rebuild positional projection từ PostgreSQL source, dùng lại generation/jobs hiện có. Không thêm search engine hoặc plugin framework.

**Đặc tả:** [#153](https://github.com/NhiBuaa/knora-agent/issues/153), SDM/score semantics/ablations. **Trạng thái:** áp dụng Q1–Q7; người thực thi tự chốt công thức/window/smoothing/weights từ reference, development và review G5 theo Q2, không hỏi owner từng tham số. SDM/Phrase Boost là deterministic local scoring không AI; mọi AI ở chuỗi bao quanh chỉ Cloudflare, không local weights/model.

## Hợp đồng đầu vào/đầu ra

- Input: query tokens theo lexical policy, tối đa 100 DBSF candidates của cùng authorized snapshot; canonical chunk identity/content/checksum, tokenizer/index generation, branch score/ranks và positional derivation khớp. Corpus membership/statistics snapshot ID từ S4 Task 2 là phần bắt buộc, không tạo population độc lập chỉ cho SDM.
- Output: cùng candidate identities và provenance, thứ tự deterministic, thành phần SDM + policy/version + normalization/combination context; không biến missing lexical term thành lý do loại dense candidate.
- Native NFKC/lower giữ dấu/số của S2 tiếp tục là baseline. Source offsets không lấy từ search-normalized token positions. Nếu thử segmentation mới, có version/license/index-query parity, reindex riêng và ablation, không đổi S2 profile.
- Lexical BM25+SDM diagnostic có policy/candidate depth riêng để so sánh; không đổi frozen S2 diagnostic Top-200 hoặc gọi lexical pipeline là DBSF khi không fusion.
- Development relevance judgments/metric-policy/scorer nhận từ S4 Task 7, cùng source/derivation bindings đã review. Phrase Boost là comparator có version dành cho evaluation ở Task 4; không thêm nó vào production V3 thay SDM.
- S7 targeted source recovery vẫn dùng scope/snapshot/tokenizer/score policy của S4–S5; không phát sinh AI hoặc bỏ SDM guards để tìm thêm nguồn. Đo SDM trên workload Q4 (3 câu hỏi đồng thời, 1 PDF, tới 10.000 chunks) với finite CPU/RAM/deadline theo plan cha; không dùng scope thống kê để cấp quyền đọc.

## Task 1 — Reference, numerical contract và golden vectors

**Files:** tạo `backend/src/knora/answering/sequential_dependence.py`, `backend/test/answering/test_sequential_dependence.py`; sửa `backend/src/knora/answering/stores.py`, `backend/src/knora/answering/retrieval_configuration.py` chỉ phần score/config cần thiết.

- [ ] Chuẩn bị G5: đề xuất log-linear SDM gồm term/ordered adjacent-query-pair/unordered-window features theo [Metzler–Croft 2005](https://lintool.github.io/Ivory/docs/publications/Metzler_Croft_SIGIR2005.pdf). Chốt count definition, window boundary, repeated tokens, document/collection lengths, smoothing và stats scope; không gọi một phrase bonus là SDM.
- [ ] Định nghĩa score lớn hơn tốt hơn, xử lý zero/missing stats/empty query/one token/nonfinite inputs, tie-break và cách giữ dense candidates không có lexical hits. Score combination với DBSF có normalization/version riêng, không cộng raw scores khác đơn vị.
- [ ] Viết independent hand-computed reference fixtures: cùng unigram counts nhưng đổi thứ tự/khoảng cách phải cho ordered/unordered components khác nhau; repeated terms, exact window edge, Việt–Anh, `AUTH_403`, `3.1`, số và phủ định. Assert từng component bằng sai số số học cụ thể trong fixture, không chỉ so thứ tự cuối.
- [ ] Test invalid weights/window/config/statistics; input/output candidate IDs không thay, permutation cho cùng tie-break. Chạy red trước, implement pure scorer sau khi mathematical contract được review; không tune bằng held-out.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/answering/test_sequential_dependence.py backend/test/answering/test_retrieval_configuration.py`; commit scorer/reference tests có `Refs #153`.

## Task 2 — Positional derivation có version và đủ scope

**Files:** tạo `backend/src/knora/ingestion/lexical_positions.py`, `backend/test/ingestion/test_lexical_positions.py`; sửa `backend/src/knora/ingestion/search_indexing.py`, `backend/src/knora/adapters/postgres/search_index_store.py` và persistence schema hiện có chỉ nếu không lưu được typed positions; tests `backend/test/ingestion/test_search_indexing.py`, `backend/test/ingestion/test_lexical_population.py`.

- [ ] Red tests index/query tokenization parity, deterministic term positions, chunk-boundary behavior, content hash/tokenizer mismatch, old generation và source-normalization separation. Không tính positions từ OCR item charspan khi không có valid source map.
- [ ] Chọn lưu thêm projection hay tính từ authorized hydrated chunks theo measured CPU/storage. Quyết định trước implementation, so sánh write/rebuild cost với query latency; không tạo bảng/index lớn nếu dữ liệu hiện có đủ và latency đạt.
- [ ] Nếu cần persisted stats, dùng cùng corpus membership/tokenizer/statistics snapshot và transition S4 cho PDF/text/backfill; phrase stats mở rộng có digest gắn snapshot đó. Unigram/phrase collection statistics theo scope đã duyệt, không đọc tenant khác hoặc dùng newest source thay serving set; thiếu/stale bị phát hiện, không coi là 0 thật. Test add/delete/reprocess và snapshot switch giữa hydrate/scoring không trộn positions/stats; rollback cùng compatible snapshot.
- [ ] Reuse staged jobs/receipts/fencing/idempotency. Hash positions và tokenizer/config vào identity; retry/rebuild tái lập được. Thay tokenizer cần derivation/profile mới; không ghi đè vị trí cũ hoặc bỏ S2 population guard.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/ingestion/test_lexical_positions.py backend/test/ingestion/test_search_indexing.py backend/test/ingestion/test_lexical_population.py`; affected DB readiness/reconcile tests trên môi trường riêng đã duyệt. Commit task.

## Task 3 — Tích hợp sau DBSF, traces và lỗi

**Files:** sửa `backend/src/knora/answering/module.py`, `backend/src/knora/answering/stores.py`, `backend/src/knora/adapters/postgres/answering_store.py` và candidate hydration boundary nếu cần; tạo `backend/test/answering/test_sdm_pipeline.py`; mở rộng `backend/test/answering/test_module.py`, `test_s2_snapshot_fence.py`.

- [ ] Viết stage-order test: BM25/dense prefetch → DBSF100 → SDM≤100 → evidence. Assert observed unique counts, không có query/embedding/provider calls phát sinh trong scorer và dense-only relevant chunk không bị drop do sparse score thiếu.
- [ ] Test same chunk/source locators qua reordered output; PostgreSQL scope/provenance validation trước scoring, và recheck trước generation/citation vẫn chạy. Archive/revoke/switch race không phục vụ stale scores/evidence.
- [ ] Trace feature counts/score components, stats generation, weights/window/version, pre/post ranks, duration và failure reason; redact theo policy. Unrun SDM là `not_run`, không ghi score 0. Legacy readers giữ schema cũ, schema mới phân biệt score kind.
- [ ] Chốt trước G5 lỗi nào là invalid provenance bắt buộc dừng và lỗi nào cho phép explicit rollback DBSF. Rollback SDM chưa đạt không đồng nghĩa requirement SDM đã nghiệm thu. Không silently bypass positional mismatch rồi báo V3 success.
- [ ] Run `python -m pytest -p no:cacheprovider backend/test/answering/test_sdm_pipeline.py backend/test/answering/test_sequential_dependence.py backend/test/answering/test_module.py backend/test/answering/test_s2_snapshot_fence.py`; finite ACK cho shared trace/reader delta mới nếu cần. Commit task.

## Task 4 — Comparator BM25+Phrase Boost có công thức và version

**Files:** tạo `evals/runners/phrase_boost.py`, `evals/test/test_phrase_boost.py`; sửa `evals/runners/pdf_retrieval_v3.py`, `evals/test/test_pdf_retrieval_v3.py` để replay comparator trên saved authorized BM25 candidates/positions cùng S4 metric policy. Không tạo production retriever hoặc thay config S2.

- [ ] Chuẩn bị numerical contract G5 cho diagnostic policy `bm25-phrase-boost-v1` đề xuất: cùng BM25 Top-200 candidate pool, tokenizer/positions/statistics snapshot của Task 2, chỉ đổi thứ tự. Query có n tokens tạo n-1 ordered adjacent pairs; mỗi pair đóng góp 1 nếu xuất hiện liên tiếp trong cùng chunk, kể cả pair lặp ở các vị trí query khác nhau. Không match xuyên chunk/page, không fuzzy match identifiers hoặc đổi normalization.
- [ ] Công thức đề xuất để review trước code: `u=(bm25-min_score)/(max_score-min_score)` trong fixed pool, `u=0` nếu mọi điểm bằng nhau; `p=matched_query_pairs/(n-1)` với n≥2, ngược lại p=0; `score=(1-lambda)*u+lambda*p`, `0≤lambda≤1`. Sort score giảm rồi canonical chunk ID; singleton/empty query không có phrase contribution, empty candidate pool trả danh sách rỗng trước normalization. Chốt lambda bằng development split S4 và freeze trước validation; mọi đổi công thức/tokenizer/normalization tạo policy version mới, trace giữ raw BM25/u/p/lambda và pre/post ranks.
- [ ] Red hand-computed tests: query `[a,b,c]`, candidate X BM25=2 với `[a,b,c]`, Y BM25=4 với `[c,b,a]`; ở lambda=0.75, `u(X)=0,p(X)=1,score(X)=0.75`, `u(Y)=1,p(Y)=0,score(Y)=0.25`. Lambda=0 giữ BM25 order dưới comparator tie policy. Thêm repeated pairs, equal/zero scores, one token, chunk boundary, Việt–Anh/số/phủ định, nonfinite/invalid lambda và hash/tokenizer mismatch; output candidate IDs/provenance bất biến.
- [ ] Implement pure evaluation scorer sau G5 numerical review, không query/model/network calls và không dùng held-out để chọn lambda. Test runner binds đúng comparator policy/snapshot/judgment hashes; source reviewer labels từ S4 giữ độc lập scorer.
- [ ] Run `python -m pytest -p no:cacheprovider evals/test/test_phrase_boost.py evals/test/test_pdf_retrieval_v3.py evals/test/test_retrieval_ranking.py`; commit comparator/tests riêng. Task 5 mới so BM25-only/phrase/SDM, không gọi phrase bonus là SDM hoặc tự bật comparator production.

## Task 5 — Ablation, quality và resource gate

**Files:** sửa `evals/runners/pdf_retrieval_v3.py`, `evals/test/test_pdf_retrieval_v3.py`; tạo `evals/test/test_sequential_dependence_observations.py`; runtime test mới `backend/runtime_test/test_sequential_dependence.py` chỉ với scope đã duyệt. Reports mới theo run convention dưới `evals/reports/`.

- [ ] Test reader rejects missing/nonfinite/incorrect score kind, wrong generation/stat hashes, pre/post candidate mutation và false `not_run` values. Không đổi metric/denominator của M1/M3/Vietnamese.
- [ ] Hoàn tất lexical matrix §6 bằng scorer/judgments S4 và comparator Task 4: PostgreSQL FTS vs Qdrant BM25-only vs BM25+Phrase Boost vs BM25+SDM trên cùng source/labels/parser và authorized scope. Với ablation phrase/SDM giữ candidate pool cố định; báo retrieval candidate differences của FTS/BM25 riêng. Hybrid DBSF vs DBSF+SDM giữ cùng candidates; ranking/coverage tách candidate recall để không gán lỗi retrieval cho SDM. Bàn giao S6 baseline DBSF+SDM không neural reranker, comparator/metric policy hashes và report cho full-vs-legacy comparison.
- [ ] So lexical config/tokenizer/k1-b ablations của S4 với positions tương thích; báo exact/phrase/identifiers, order/proximity, tiếng Việt có/không dấu và dense-only-supported cases. Tính MRR/nDCG/MAP chỉ khi labels đáp ứng metric.
- [ ] Đo query p50/p95, CPU/RAM, positional build/storage/rebuild, stats lag và bounded failure/fallback. Số liệu runtime sau authorization; offline golden tests không chứng minh latency/load thật.
- [ ] G5 ghi weights/window/smoothing/normalization được chọn từ development, uncertainty/rollback và review độc lập; đạt gates thì bàn giao S6 theo Q2, không đợi owner duyệt lại thuật toán. Giữ depth 200+200→100; không thay gold hoặc acceptance threshold. Ruff, affected suites, exact-head CI và exact-subject runtime/review theo plan cha; commit eval sau đạt.

## Gate nghiệm thu và quay lui

- [ ] Reference fixtures chứng minh đủ unigram/ordered/unordered SDM, không thay bằng phrase boost; ≤100 fused candidates và không mất dense evidence vì thang điểm.
- [ ] Provenance/stats scope/version đúng, no cross-tenant/stale leak, traces giải thích được pre/post ranks; chất lượng/tài nguyên đạt tiêu chí đã duyệt.
- [ ] Quay lui bằng policy DBSF đã xác minh, giữ projection/receipt cũ phục vụ và rebuild được. Nếu SDM chưa đạt, ghi giai đoạn chưa nghiệm thu; không giảm requirement. S6 nhận score contract, config/stat hashes, candidate list và ablation report đã review.
