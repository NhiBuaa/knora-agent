# Issue 158: incremental evaluation integrations

Approved scope: https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6170561475

## Global constraints

- Knora alone owns datasets, gold, manifests, runs, reports and quality gates.
- Reuse captured application observations; never rerun answering for each tool.
- Cloudflare GPT-OSS 20B is the preferred judge. Only explicitly approved public/synthetic inputs may leave the machine. Private inputs without egress permission fail before HTTP.
- One DeepEval trial is conditionally authorized: at most 24 HTTP attempts, at most 60 minutes, paid budget 0 USD. Verify the actual Free plan/quota before inference. Unknown or Paid plan means no live calls. Timeouts consume attempts; resume must not reset the count.
- Langfuse Cloud export stays OFF. Only opaque IDs, approved metadata and numeric diagnostics can be previewed/exported; never raw content, source names, reasons or credentials.
- No automatic release thresholds, gold promotion, enforcement, runtime changes, model downloads, upgrades or merge. Guardrails implementation remains separate in #188, shadow only.
- #153 owns PDF gold/binding/evaluation_reader. This branch owns scoring/correlation/export, optional dependencies and focused documentation. Do not edit #153 reader or production answering.
- Install optional packages in this worktree's Python 3.12 environment. Mock tests and local tests do not use shared services.
- Ragas calls have no live authorization in this trial. Draft limit 12, Vietnamese/English, final review by owner; multi-hop needs at least two necessary evidence steps.

## Task 1: DeepEval and durable correlation

Implement the smallest usable integration into existing Knora Evaluation. Read AGENTS.md and required documents, existing eval runners/scorer, exact trace binding/projection. Add optional pinned DeepEval dependency after compatibility check, schema-aware Cloudflare custom judge, correctness/answer relevancy/faithfulness metrics and safe admission. Keep the public-only citation/refusal scorer separate. Explicitly distinguish exact generation evidence from retrieval candidates and citation excerpts: missing exact evidence cannot produce a full-context faithfulness score.

Use existing report publication/provenance and semantic scoring seams. Store supplementary scores/status, local rationale and tool/method/model/input provenance with run/case/attempt/trace correlation. Preserve M3 trace_id durably. No success/threshold from DeepEval becomes a release gate. Provide an operational CLI or existing runner option with no default network calls, data approval and immutable artifacts. Guard the HTTP boundary with durable attempt accounting, deadline and no hidden paid-provider fallback. Live preflight must fail closed on unverified zero-cost conditions; do not implement a billing platform.

TDD meaningful transport/projection/publication tests first. Inspect actual installed DeepEval API, disable telemetry/dotenv/key discovery before import, use explicit model and direct measurement. Test real metrics with mocked HTTP, schema/truncation/failures, private rejection, mismatched IDs/evidence, timeout/cap persistence and no-clobber publication. Do not call Cloudflare. Commit only task changes and report commands/results/limits.

## Task 2: Ragas review drafts

Use explicit Ragas generator/LLM/embedding adapters over the approved provider contract from Task 1, with no automatic model/provider defaults or network calls. Consume approved Knora source chunks/locators/digests without a second ingestion/dataset store. Produce local reviewer packets with up to 12 Vietnamese/English drafts, reference answers, exact evidence anchors, necessary hop claims and generator provenance. Retain drafts as pending owner review; no automatic gold insertion. Validate missing evidence/node mapping and reject unsupported multi-hop claims. NoiseSensitivity is experimental only, unavailable when required inputs/judge are absent; avoid duplicate DeepEval metrics. Document call inventory including transformations/embeddings before any future live approval. TDD tests with actual installed Ragas API and mock provider; no model downloads or paid calls.

## Task 3: Langfuse metadata bridge

Add the minimal optional Langfuse integration from persisted Knora observations, with local preview and export OFF by default. Strict payload construction uses only project-scoped opaque IDs and allowlisted safe diagnostics. Preserve stable joins and original durations; never convert monotonic ticks to fake wall-clock spans. Test nested raw-content/error/credential sentinels, deterministic IDs and off-mode behavior against the actual SDK/transport. Provide simple Tokyo Hobby owner-only setup, API/UI deletion and readback instructions for the seven-day target. Export activation/credentials remain separately approved. No runtime decorators, cleanup service or new observability authority.

## Task 4: integration evidence and PR

Update the evaluation guide and domain decision documentation; coordinate shared sections through #153. Run required pytest, Ruff format/check/lint and Compose configuration gates. Review the whole branch for authority, egress, import telemetry, joins and budget bypasses. Attempt read-only Free-plan/quota verification only after mocked code is ready; if no zero-dollar guarantee is available, record live DeepEval as not run. Report package compatibility, mocked versus live evidence and remaining acceptance in #158 and PR. Push only this feature branch, attach the created PR, no merge/deploy/Done.
