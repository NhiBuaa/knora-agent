# Issue 153 — S2.1 offline contract checkpoint

Date: 2026-10-15. Scope: code and offline unit tests only. No S2.2 execution or runtime acceptance.

## Authority and coordination

Owner approval, recorded in first person:

> Tôi duyệt roadmap S2.1–S2.4; trước mắt chỉ triển khai S2.1 bằng code và unit tests offline. Tôi duyệt BM25 raw scores, không áp numeric cutoff chưa calibrated; Top-8 là so sánh chính và Top-200 là diagnostic riêng. Tôi chưa chốt pins/production, runtime, migrations hoặc model calls.

The [owner record](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6192431015)
supplements the [approved roadmap proposal](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6192173446).
The [#158/#192 ACK](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6192449827)
was received before shared-file edits. Workbench, Runs API/UI/OpenAPI, evaluation authority,
dependencies and deployment selectors are outside this change.

Worktree: `C:/Developer/Projects/knora-agent-worktree/issue-153-s2-contracts`.
Branch: `feature/issue-153-s2-contracts`, based on reviewed S1 commit
`a67842e73959ecf4434ad027abd35983fc08017f`. Review this delta against
`feature/issue-153-pdf-baseline`; PR #189 remains Draft and unchanged.

## Implemented contract

- Resolve retrieval mode before readiness. BM25 requires lexical readiness and passes no
  embedding configuration/vector; dense/hybrid still require their embedding context and threshold.
- Add store-resolved `LexicalGeneration` identities, BM25 raw score/rank/generation and versioned
  branch observations. Validate workspace, document/version/ChunkSet/generation identity, finite
  scores, rank order/uniqueness and coherent observations before evidence selection/generation.
- Reuse the existing evidence selector, generation validator and citation path. Lexical traces use
  schema 3 / branch schema 2; existing dense/hybrid trace serialization remains schema 2 / 1.
  Embedding is explicitly `not_run`, with no fabricated EmbeddingSet/provider usage.
- Add pure `project_bm25_trace` for a trusted offline snapshot; replay evidence selection and
  validate aliases and generation state. S2.2 must supply an authoritative PostgreSQL snapshot;
  trace self-assertions cannot establish active-generation authorization.
- Preserve ordered candidates, selected generation evidence, scores and rejection reasons in a
  schema-1 capture/report supplement. Missing historical fields are `unavailable`; unobserved
  candidates remain `unknown`. Frozen metric names, semantics and denominators are unchanged.
- Production PostgreSQL lexical readiness/retrieval explicitly raise
  `LEXICAL_RETRIEVAL_UNAVAILABLE` before opening a session. The diagnostic configuration is an
  explicit offline composition, not a registered deployment mode. There is no Qdrant adapter,
  tokenizer implementation, index lifecycle, migration or production switch in S2.1.

### Diagnostic comparison limits

The fixture uses a Top-200 diagnostic configuration with no numeric cutoff. Per-case coverage
keeps `retrieved_top8`, `retrieved_top200` and `generation_selected` separate. These are supplemental
views of **post-revalidation ordered candidates**. With native-rank gaps, the first eight admitted
candidates can differ from native ranks 1–8. `generation_selected` is actual evidence in the trace;
it does not claim a separate Top-8 selector replay. That controlled comparison belongs to S2.4.

Baseline B remains post-vector-threshold `0.65`. Its unavailable pre-threshold lists prevent an
isolated algorithm-versus-threshold conclusion. A nonempty BM25 list does not establish answer
sufficiency or semantic quality. No BM25 numeric threshold has been calibrated or applied.

## Owner Human Review record

> Tôi đồng ý ACCEPT 001/005/012 và REJECT 014/032, giữ nguyên historical findings và phạm vi verdict dưới đây.

Scope: the saved attempt 1 responses in run `s1-runtime-binding-20261015-01`, reviewed at `a67842e`.
The following SHA values are `response_sha256` from the existing human packet, not new responses.

| Case | Owner verdict | Response SHA-256 | Scope |
| --- | --- | --- | --- |
| 001 | ACCEPT | `771c285f4bc78ddbfcba89c5d4e181673e322c5a91ba0a9417773d59d0513c9f` | Reviewed same-attempt revalidation; historical citation structural failure remains recorded. |
| 005 | ACCEPT | `338780f5f55c94fe2c487ce6a3e5981b95adef51e77edfb6335d04bbd9b5463c` | Reviewed answer and source evidence. |
| 012 | ACCEPT | `eb85f7e7370fe350879aa8f43f03863d7ec16ec63734ce877fde75b8a0a28194` | Reviewed 30/90-day distinction and citation. |
| 014 | REJECT | `d44ff845714d2ff3629463fc2e07027ebded648f8beee670702688d8df146b56` | Wrong answer language; missing exact bindings do not alone prove hallucination. |
| 032 | REJECT | `7dad8fc85facf6f87042adf28d7932ab6b6d420016cb24f8f00a12041f395d13` | Overbroad prohibition drops “chỉ vì ngoài giờ”; no new downgrade permission inferred. |

These five verdicts do not approve the remaining responses, change extraction/mapping status,
or establish semantic PASS for all 60 cases. The original Baseline B packet is not rewritten.

## Verification

Use the existing S1 virtualenv interpreter read-only with this worktree's `backend/src` and root
on `PYTHONPATH`. No dependency installation or runtime/model calls were needed.

| Check | Result |
| --- | --- |
| `pytest backend/test/answering evals/test/test_pdf_retrieval_v3.py evals/test/test_pdf_revalidation_selection.py evals/test/test_milestone_3_runner.py evals/test/test_milestone_3_comparison.py evals/test/test_evaluation_ownership.py -q --tb=short` | 229 passed |
| `python -m ruff format .`, `python -m ruff format --check .`, `python -m ruff check .` | Passed |
| `docker compose config --quiet` | Passed; unset local MinIO credential warnings only, no service started |
| Frozen paths `evals/corpora`, `evals/datasets`, `evals/reports` versus `a67842e` | No changes |
| Independent code review | Three validation defects reproduced with failing tests and fixed; re-review found no remaining blocker for S2.1 |
| Whole offline CI partition collection | Blocked: existing interpreter lacks optional `deepeval` and `ragas`; not claimed passed |

Tests exercise the fake lexical store through application, trusted pure projection, mock HTTP
capture and supplemental report. They include empty/generated refusal, missing provider, malformed
generation state, provenance drift, contradictory observations and native-rank gaps. They do not
prove PostgreSQL/Qdrant compatibility, tenant/stale runtime isolation, tokenizer quality or IDF scope.

The current CI workflow triggers PRs against `main` only. A stacked Draft PR against the S1 branch
does not automatically receive `CI required`; no manual service workflow was dispatched.

## Next checkpoint

Stop here for owner review. S2.2 remains pending: lexical readiness and durable lifecycle, independent
from embedding activation, with a separately approved isolated migration/runtime window. Pins,
single-shard authorized-corpus IDF and tokenizer compatibility/isolation must be verified before
S2.3/S2.4 runtime claims. Paid usage remains USD 0; no merge or deployment is authorized.
