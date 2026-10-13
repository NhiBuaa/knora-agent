# Issue #169: answer and source formatting verification

Date: 2026-10-13 (Asia/Ho_Chi_Minh)

Branch: `fix/169-structured-evidence`, starting from main
`5d318f5908f7a4a1ef63e3cf3bb832538872b2c3`.
User acceptance is pending; the Issue remains open and In Progress.

## Diagnosis and scope

The original persisted answer and citation excerpt each contained zero newlines.
The matching stored Chunk also contained zero newlines. Against the same original
PDF bytes, pinned pypdf plain extraction produced one newline on page 1; layout
extraction produced 38. Normalization/chunking and the bounded citation excerpt
preserve interior newlines. The Inspector already uses `white-space: pre-wrap`.
Reconstructing a list in the Inspector would invent source structure.

The answer was generated with Cloudflare prompt v2, and TurnCard rendered it in a
plain paragraph. The generation trace was valid and mapped E1 to its actual Chunk;
the raw marker was a rendering omission, not a missing citation mapping.

The fix uses a new immutable PDF extraction/chunking profile for new HTTP uploads
and Cloudflare prompt v3 with formatting guidance. Chat parses Markdown with inert
HTML and resolves original validated markers to the existing CitationChip and
selection callback. Unknown/malformed/repeated projections and parser-consumed
markers surface `GENERATION_OUTPUT_INVALID`. Server validation and authorization
are unchanged. Excerpts remain literal server-projected text.

TurnCard changes are limited to answer rendering. Suggestion text, buttons and
handlers owned by #170 are unchanged. See [ADR 0016](../adr/0016-layout-preserving-pdf-extraction.md)
for immutable profile and reprocessing boundaries.

## Regression and local verification

| Check | Result |
| --- | --- |
| Full Python suite, `python -m pytest --rootdir . --confcutdir . backend/test evals/test -q` | 1,892 passed, 16 skipped, exit 0 |
| Frontend Vitest | 464 passed, 52 files |
| Focused Playwright fixtures | 3 passed |
| Actual provider projection UI replay | 1 passed |
| Frontend format then format check; shared format then shared format check | passed |
| Frontend typecheck, lint and production build | passed; three pre-existing composer image lint warnings |
| Ruff format, format check and lint | passed, 378 Python files formatted |
| OpenAPI export check, Compose config and diff whitespace check | passed |

Python used the worktree environment and a separate migrated local database.
Ambient HTTP/HTTPS/ALL/NO_PROXY values were removed only from the test process to
avoid an unavailable SOCKS extra and a malformed inherited bypass value. No
developer configuration file was edited.

The 16 skips are 12 tests guarded for a separately named isolated database, three
locked/manual PDF baseline checks, and one explicitly enabled real-Ollama check.
They are exclusions, not passing evidence. The first full run exposed 11 stale
fixed-profile Cloudflare fixture failures; the fixture now resolves the persisted
profile and all 15 Cloudflare application tests pass. An existing 200 ms lease
test also failed on timing in that run; it passed separately and in the final full
run without code changes. No failing result is counted as a pass.

Regression coverage includes paragraphs/headings/lists, reversed E1/E2 citation
array ordering and exact selection, malformed/unmapped/repeated markers, markers
inside Markdown link/image/code syntax, decoded unvalidated text, inert HTML,
multiline literal excerpts, page/version/offset projections and extraction of
independently positioned/scaled PDF lines. Existing provider application tests
continue to exercise invalid output and cross-workspace denial.

Browser checks exercise Chat and Evidence Inspector at 1440x960 and the existing
1912x1114 viewport: list structure, inline chip selection, exact excerpt text,
wrapping, version, document link, provenance offsets and no horizontal overflow.
The existing open-inspector fixture also passes. Screenshots were inspected locally.

## Real provider observation

A separate local workspace/database received the original PDF bytes through HTTP
upload and the real ingestion worker, then queried Cloudflare Workers AI. No
production corpus, historical Chunk or citation was rewritten.

| Observation | Result |
| --- | --- |
| Upload / Job | 202 / succeeded |
| Original count-only question | valid short answer, zero newlines |
| Same question requesting a list | valid answer, 13 newlines |
| Bounded source excerpt | 10 newlines |
| Prompt | `cloudflare-gpt-oss-cited-answer-v3` |
| Trace validation | valid |
| Citation targets checked | 1; document/version/page/offset/checksum match stored Chunk |

The actual public projection was replayed into the UI at 1912x1114 and inspected:
seven list items, no raw marker, selected source text identical to the payload and
matching historical version. This is a formatting/citation observation, not a
generation-quality or release Runtime Verification claim.

## Evidence handling and limits

Published evidence contains counts and safe outcomes only. Tokens, credentials,
cookies, authentication URLs, original PDF bytes, raw source text, raw provider
payloads and database dumps are excluded. Raw local observations and screenshots
remain under ignored `.verification/issue-169/`.

Existing flattened historical excerpts cannot recover line structure through CSS.
Resubmit the same original PDF/source key after deployment to obtain the new
derivation. Old citation targets remain valid. Legacy queued/reprocessed jobs keep
their captured profile. Complex PDF layout fidelity is outside this fix.

No merge, Issue closure or Done transition is authorized before user acceptance.
