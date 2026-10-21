# Issue 153 — S1 A verification and review handoff

Date: 2026-10-14. A implements the approved preparation scope; this document
records engineering evidence, not owner gold approval or Retrieval V3 acceptance.
Authority: [Q6](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6163913631).
Paid allowance remains **0 USD**. No application model, judge or Cloudflare
request was made during A. No corpus/gold approval record was manufactured.

## Branch and ownership

- Base: `7697615395e469863279b9f5286b4ebed2396144`; remote main rechecked unchanged.
- Branch: `feature/issue-153-pdf-baseline`.
- Worktree: `C:/Developer/Projects/knora-agent-worktree/issue-153-pdf-baseline`.
- Owned Compose project: `knora153s1`; Postgres loopback **55453**, its own volume.
- Tests used that project's `knora` database. Conditional B requires a separate
  `knora153s1_baseline` database and API **8153**, not yet launched.
- Shared reader/docs ownership was coordinated in #158 before edits:
  [file boundary](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6163923743),
  [runtime ownership](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6165258538).
- An initial reader test reached default 5432 and failed authentication before
  mutation; every subsequent DB command explicitly targeted owned 55453.

## Candidate and review gates

[Corpus README and five review batches](../../evals/corpora/pdf_retrieval_v3_v1/README.md):
16 PDFs, 35 physical pages, 86 source anchors, 60 cases, five batches of 12.
There are 13 labelled synthetic edge fixtures and three original ACL academic
papers. Hashes, licenses, physical-page regions, reference facts, AND/OR groups,
follow-up parents, absence scopes and exposure are recorded in the same corpus.

- Corpus SHA-256: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`.
- Dataset SHA-256: `12127bf8d8a06bb3aac3719d2cd6726370b5ae8fec029a77c925bb00c4aeaf97`.
- All inputs remain **owner review pending**. Agent code review does not approve
  the corpus, freeze gold or approve source-to-chunk binding.
- Case 010 was corrected during review to preserve its remote-order exception.
  Multi-hop validation now rejects OR alternatives satisfiable from one source.
- Tools/judges/export remain #158's responsibility; its tools consume captured
  observations instead of running application questions again.

## Tests and review

- Corpus contract: missing-feature RED, then malformed-PDF/digest-scheme RED;
  multi-hop bypass RED (`DID NOT RAISE`), then **20 focused tests passed**.
- Binding: missing-module RED, then **10 focused tests passed** covering exact
  repetition, ambiguity, missing extraction, drift and AND/OR coverage.
- Reader: missing PDF provenance attribute RED; **six real Postgres tests passed**,
  retaining legacy contracts and workspace/archive isolation.
- HTTP/guard review regressions covered nested production provider errors,
  conversation provider errors, missing parent context, continuation after a
  failed parent, UTC-midnight pause and digest drift before quota retry.
- Production PDF integration passed with a genuine PDF, actual pypdf worker,
  real Postgres, Q&A, parent/follow-up Turn and cross-owner rejection. HTTP used
  ASGI transport and deterministic providers; this does not prove TCP, deployed
  Keycloak or Cloudflare model quality.
- Read-only corpus and runner reviewers confirmed their P2 findings resolved.
- Initial full pytest: **1,949 passed / 20 failed / 16 skipped**. Failures were
  caused by inherited SOCKS proxy environment without optional `socksio`.
  Removing proxy variables only in the offline test subprocess resolved all
  affected groups: **103 passed**. No dependency/test/threshold was weakened.
- Next full run: **1,970 passed / 1 failed / 16 skipped**. Global Turn recovery
  encountered another test's deliberately incomplete expired fixture. The new PDF
  E2E now creates its own UUID database on the same owned Postgres, migrates it,
  uses scoped session injection and drops only that database after execution.
  Isolated E2E passed with the full worker/recovery path enabled. The fixture was
  independently reviewed. No production recovery behavior was changed.
- Docker stopped the S1 container during a later session interruption. Only the
  already-owned `knora153s1-postgres-1` was restarted; no other container was changed.
- Final changed-scope verification: **70 passed / 1 warning** on the final tree
  (dataset, binding, HTTP, Free guard, existing reader and isolated PDF E2E).
- Latest whole-suite attempt stopped without a final report around 88%; its log
  includes Windows launcher/memory-preflight failures while available RAM fell
  below the unchanged 768 MiB safety minimum. It is **not a passing full gate**.
  PR remains Draft pending an uninterrupted full verification/required CI result.
- After memory recovered, all affected Windows launcher/bootstrap/worker/readiness
  groups passed on the unchanged final code: **107 passed in 176.80 seconds**.
  This targeted rerun resolves their observed failures; it is not a replacement
  for a single complete whole-suite gate.
- Ruff format/check/lint and `docker compose -p knora153s1 config --quiet` passed.
  Compose validation used non-secret MinIO placeholders and started no extra service.
- Initial Hindsight search/list/capture were unavailable (`ECONNREFUSED`). A later
  search/read succeeded but contained no S1-specific decision or test evidence;
  verification here uses code, issue approval and observed command results.

## Offline baseline sizing

Actual production pypdf layout-v2 extraction was run on every candidate PDF,
without model calls. These figures describe derivation sizing, not source gold
or provider token accounting.

| Source | Pages | Chunks | cl100k chunk tokens | Extracted characters / error |
| --- | --- | --- | --- | --- |
| clean-01 | 2 | 2 | 192 | 429 |
| clean-02 | 1 | 1 | 173 | 420 |
| hierarchy-01 | 1 | 1 | 184 | 418 |
| hierarchy-02 | 1 | 1 | 187 | 423 |
| hierarchy-03 | 2 | 2 | 225 | 536 |
| columns-01 | 1 | 1 | 159 | 339 |
| columns-02 | 1 | 1 | 156 | 462 |
| table-01 | 1 | 1 | 130 | 290 |
| table-02 | 1 | 1 | 134 | 301 |
| table-03 | 1 | 1 | 134 | 291 |
| scan-01 | 1 | 0 | 0 | PDF_TEXT_INSUFFICIENT |
| scan-02 | 1 | 1 | 41 | 127; title/footer only |
| scan-03 | 1 | 0 | 0 | PDF_TEXT_INSUFFICIENT |
| academic-phobert | 6 | 14 | 7,340 | 22,029 |
| academic-phonlp | 7 | 13 | 7,189 | 22,862 |
| academic-vit5 | 7 | 7 | 63 | 243; severe extraction loss |
| Total | 35 | 47 | 16,307 | Full corpus retained |

Total PDF bytes: 2,083,688. Initial sizing is 47 document embedding strings plus
60 query strings, up to 60 generation calls / 61,440 configured output tokens.
Retry-inclusive caps remain 2,500 embedding strings and 70 generation attempts.
Provider tokenization, input prompts, retries and other sessions' usage mean
this is not a guarantee of fitting the remaining Free quota in one day.

## Outstanding owner/runtime work

1. Review PR and all five corpus/gold packets, then explicitly approve both digests.
2. Verify the actual Cloudflare account's Free plan, quota, model eligibility and
   account/session ownership before B. No such live check was performed in A.
3. Upload all 16 through public HTTP, retain extraction failures, propose bindings
   from persisted derivations and obtain owner binding review before scoring.
4. Capture all 60 cases with the unchanged baseline, pausing on quota until reset.
   Record correctness/citation/refusal review against exact response digests.
5. Keep tools unavailable as `not_run`; do not claim S1 B or V3 acceptance from A.

No OCR/Docling/LangChain migration, #147 Agent work, merge, deploy or Done.
