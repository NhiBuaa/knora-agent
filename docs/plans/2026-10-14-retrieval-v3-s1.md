# Retrieval V3 S1 Implementation Plan

> **For agentic workers:** Use `subagent-driven-development` for corpus preparation and review, or `executing-plans` inline for integration. Track steps below; user has already authorized A and PR publication.

**Goal:** Implement A and present 16 PDFs/60 source-gold cases and an executable baseline adapter for review without model calls.

**Architecture:** Source gold is independent of derived chunks. A small PDF adapter uses existing production HTTP routes, persisted projections, and public citation validators. Free-only preflight and simple durable counters protect the conditional B execution.

**Tech Stack:** Python >=3.12,<3.15, pypdf 6.14.2, existing httpx/SQLAlchemy/pytest; no production dependencies added.

**Spec:** `docs/specs/2026-10-14-retrieval-v3-s1.md`

## Global Constraints

- Paid budget 0 USD; no model calls in A. B waits for owner corpus/gold approval and Free preflight.
- Baseline unchanged: pypdf layout-v2, Qwen3 0.6B 1024d, GPT-OSS20B max_tokens=1024, threshold 0.65.
- No changes to production behavior, DB schema, shared current runners, dependency manifests or framework migration.
- Preserve PDF/case distributions from the spec. Drafts are pending owner approval; never self-approve.
- Worktree `C:/Developer/Projects/knora-agent-worktree/issue-153-pdf-baseline`; owned resources only.

### Task 1: Corpus and source gold review candidate

**Files:** `evals/datasets/pdf_retrieval_v3_v1.py`, `.manifest.json`, `.jsonl`; `evals/corpora/pdf_retrieval_v3_v1/`; `evals/test/test_pdf_retrieval_v3_dataset.py`.

**Interfaces:** Produce `load_dataset(manifest_path: Path, dataset_path: Path) -> PdfDataset`.
`PdfDataset` exposes `sources`, `anchors`, `cases`, `corpus_sha256`, `dataset_sha256`.
Each source has `id`, `path`, `sha256`, `page_count`, `category`, `kind`, `license`, `source_url`, `license_url`.
Each anchor has `id`, `source_id`, `page`, `text`, `region`.
Each case has `id`, `category`, `language`, `question`, `expected_behavior`, `reference_answer`,
`required_facts`, `evidence_groups` (tuple of tuples of anchor IDs; outer AND, inner OR),
`parent_case_id` optional and `no_answer_scope` optional. Case and source IDs are stable.
`validate_approval(dataset, approval: dict)` rejects pending, wrong owner, or digest drift.

- [x] Write tests before implementation: modified PDF must fail hash validation; missing anchor/nonexistent page/empty AND group invalid; follow-up parent must exist and precede child; REFUSAL must have no positive gold; approval must match both digests and owner `NhiBuaa`.
- [x] Run `.venv/Scripts/python -m pytest evals/test/test_pdf_retrieval_v3_dataset.py -q` and record expected RED.
- [x] Implement a compact strict loader using dataclasses/JSON/hashlib; validate exact distributions, unique IDs, safe relative paths, PDF hashes/page counts, source licenses, cases/facts/groups and source closure. No second annotation framework.
- [x] Prepare actual 16 PDFs: 13 labelled authored synthetic fixtures (2 clean/3 hierarchy/2 columns/3 hard tables/3 scans), 3 actual ACL academic papers (PhoBERT/PhoNLP/ViT5, CC BY4.0 primary copyright page). Vietnamese diacritics in fixtures, actual table geometry/merged headers/columns/images, not plain prose pretending to be complex PDF. Keep recipes/source metadata/license evidence. Use bundled PDF tooling for authoring if needed, no runtime dependency.
- [x] Prepare actual 60 authored candidate questions/facts/references/source anchors, preserving exact case distribution. Six multi-hop cases need a necessary lookup then a second source step, not arbitrary paired questions. Eight follow-ups depend on real preceding questions. No-answer records explain corpus-bounded absent facts.
- [x] Create corpus README and five review Markdown batches of 12 with reference/facts, visible page/region, exact source evidence, exposure `agent-authored; no model calls; owner review pending`. Synthetic answers come from fixture content; real facts checked against actual PDF page. Do not fabricate extraction fidelity or license facts.
- [x] Run focused tests GREEN, `ruff format` on changed Python and `ruff check` on changed Python. Self-review, commit only these files. Report RED/GREEN evidence and limitations to controller.

### Task 2: Derivation projection, reviewed binding and HTTP observations

**Files:** `backend/src/knora/adapters/postgres/evaluation_reader.py`, its current test; `evals/runners/pdf_source_binding.py`, `pdf_retrieval_v3.py`, focused tests.

**Interfaces:** Consume `PdfDataset` from Task 1. Projection retains all legacy fields and adds raw hash/parser/normalizer/chunker/pages/offsets/checksum. Binding proposals are hash-bound to persisted chunks; review record explicitly approves selected alternatives. HTTP observation carries run/case/attempt/trace/workspace IDs and response digest; #158 consumes captured observations later.

- [x] Add failing tests for repeated exact text ambiguity, missing extraction, source/derivation drift, unreviewed scoring rejection, AND/OR group coverage, public/trace answer/workspace mismatch and follow-up Turn correlation.
- [x] Run focused tests RED, implement smallest read-only projection and source binding using exact text occurrences on expected source/page; never accept a proposal automatically.
- [x] Reuse `validate_public_response` and `validate_public_citations_against_trace` from `evals.runners.milestone_3`; observe public upload/job/Q&A/conversation HTTP and exact persisted trace. Poll only admitted IDs, bounded polling, idempotency per run/case. No private prompt/candidate content passed to the public-only scorer.
- [x] Build local immutable observation/report publication with total 60 denominators, explicit extraction/mapping/provider/observation/answer errors and not_run tools/pending semantic reviews. Do not create framework judging.
- [x] Run focused tests and real owned Postgres/HTTP integration using deterministic providers, including legacy evaluation-reader tests; keep model calls disabled.

### Task 3: Conditional B launch guard, docs and PR

**Files:** `evals/runners/pdf_baseline_runtime.py`, focused tests, append only PDF section in `docs/evaluation.md`; continuity evidence.

- [x] Add failing tests: paid/unknown plan, missing corpus/gold approval or stale quota evidence stops before provider dispatch; timeout counts remain; limits persist on resume; quota error stops until reset; no overwrite of completed observations.
- [x] Implement eval-only httpx boundary hooks/counters for <=70 generation attempts and <=2500 embedding strings including retries. Require verified Free eligibility and remaining-quota snapshot before B; no monetary reserve or automatic upgrade. Injection uses current provider/client/create_app seams; no edits to production defaults.
- [x] Document commands for review, upload/binding, reviewed scoring and conditional baseline resume. Clearly separate A deterministic evidence from B model quality; no claims of calibrated threshold or final acceptance.
- [ ] Verify repository pytest on owned DB, Ruff format/check/lint and Compose config; run applicable isolated PDF/Turn E2E. Any unavailable checks must be recorded accurately.
- [ ] Review the entire branch, fix actionable findings, commit/push unique feature branch, create PR for owner review and attach artifact. Record decision/result/PR in #153, leave B and parent acceptance pending. Never merge/deploy/Done.
