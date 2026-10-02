# Issue #105 GPT-OSS migration checkpoint — 2026-10-02

## Model and local configuration

The owner approved downloading `gpt-oss:20b`, switching local development generation to it,
and deleting the old Qwen generation tags. The downloaded MXFP4 artifact is 13,793,441,244
bytes, with full digest:

`sha256:17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`

Ollama 0.34.4 on the user-owned endpoint `http://127.0.0.1:11435` reports named reasoning
levels `low`, `medium`, `high`. GPT uses `low`, context 8192, output budget 2048 and
temperature zero. Only final content enters GenerationResult; raw reasoning is not saved.
The ignored primary `.env` now selects GPT-OSS and a 240-second generation HTTP timeout.
Parameter/process/.env precedence remains unchanged.

Exactly `qwen3:4b`, `qwen3:8b`, `qwen3:14b` were removed through Ollama's model API, after
the replacement passed final runtime compatibility smoke checks. Each deletion verified
the exact target digest and read inventory back. The final inventory contains GPT-OSS and
`qwen3-embedding:0.6b`. The embedding digest remains
`ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`, and actual post-deletion
daily preflight resolves the unchanged configuration
`embedding-ollama-qwen3-ac0dc2cd2e4b7e2d44cb70f0`. No re-indexing was performed.

Local `codex/test` is clean at `691a6b810d3f4d729c73f26d4fcc2113f1e477fd`. It preserves
`8ccddc4ce41ff5e5baa10a47cc5ab175351c4d31` and its auth fix. Only reviewed GPT support,
the reasoning-boundary document and formatting repairs were transplanted. The primary
Qwen prompt remains v2 with its original request options; unaccepted v5 prompts, extraction
experiments and reports were not merged into that branch. Primary GPT prompt identity is
`ollama-gpt-oss-low-schema-v3:ollama-qwen3-cited-answer-v2`; the issue worktree has the
separate v5 base identity. Main, issues and retained worktrees were not changed by integration.

## Runtime compatibility repairs

A real v1 schema smoke on the issue worktree passed. The unchanged extraction probe then
failed its preliminary condition. A separate single-request shape diagnostic found a
response lacking required `decision`; it emitted an unexpected `answer` field. This
diagnostic retained only shape/count/usage metadata and did not replace any scored response.
It does not prove that all ten invalid observations have the same cause.

The initial primary v2-base smoke was rejected by the existing validator because its
answer lacked an inline marker despite listing an alias. Supplying schema text alone did
not fix this marker failure. TDD and independent review added GPT-only formatting examples
that explicitly are not evidence, plus the exact existing schema in the system prompt.
The final version is `low-schema-v3:<base>`; Qwen behavior, shared schema, alias checks,
validators, retrieval and production refusal rules remain unchanged.

On the actual committed primary runtime, final smoke checks passed:

| Check | Result | Prompt / completion tokens | Seconds |
| --- | --- | --- | --- |
| Explicit supporting fact, correct value and inline citation | PASS | 551 / 72 | 7.132 |
| Missing requested attribute, structured refusal without citations | PASS | 552 / 48 | 4.991 |

Both finished with `stop` using the pinned GPT tag. These two synthetic provider calls
are runtime compatibility checks. They do not establish semantic quality on the PDF,
durable Conversation acceptance, browser/Keycloak acceptance or release readiness.

## Preliminary extraction gate remains failed

The immutable eleven-case run used clean commit
`e226ce0b9d8b93f61b5f28fca3fa056a7e4a9142`, tree
`eebabf04f65b7ebf22206cea300df7a56be1d04e`, profile `gpt-oss-low-v1`, seed 105 and context
4096. Its extraction prompt/schema/renderer/fixtures/rubric match the previous diagnostic;
the model and request policy differ. Its temperature-zero seed is a repetition control,
not evidence of an independent stochastic sample.

- Eleven observations; zero passed all literal checks.
- Ten `GENERATION_OUTPUT_INVALID` observation failures have no retained valid final and
  are not semantically scorable.
- One retained structurally valid final fails independent semantic review by weakening
  an explicit prohibition. Semantic counts are zero passed / one failed, not zero / eleven.
- No deadline or supervisor failure was observed; process duration was 11.951–37.570 seconds.
  OS startup/kernel scheduling bounds and server cancellation remain unproven.
- All eleven canonical response bindings and source/report/private provenance were verified
  independently. Raw reasoning and intermediate extraction were not retained.

The extraction transport still replaces the production system prompt. The later production
formatting repairs were not applied to this failed run, and its scores were not rewritten.
Seeds 106/107, PDF, original36/revised36, durable Conversation and browser gates were stopped
or not run after the failed preliminary condition. #105 remains unaccepted and #116 remains
the final release gate.

Artifacts:

- `../vietnamese_rag/issue105_process_gptoss20b_seed105_literal.json` — SHA256
  `a84d7812386d3ffbc15219ca7a4fe0d1f753c21df291b8af434b5e66c306bdef`.
- `../vietnamese_rag/issue105_process_gptoss20b_seed105_semantic_review.json` — SHA256
  `9a9beb78a18f04418da24a35a13784f0d7af78109cf3dd508c553ab17c2671bd`.
- Private normalized-final artifact — SHA256
  `44abe2e4a9197f0206ffc915306f003a23c8f3fb08a34a2336db293d69c0c4ef`.
- Independent private review — SHA256
  `a888b019c4d6d2b743d8c09a472ce250237be3e3868149acfa421adb34aca4ba`.

Next #105 work must address GPT extraction-format compatibility with a separately versioned
request, then repeat the preliminary gates without relaxing citations/refusal or reusing
the failed run as acceptance. The owner-facing PDF Conversation gate remains required.

## Code verification

The final runtime code commit is `49cb04bd886dc791419dedc207bfb0374e0cd1cf`.
Full pytest on the isolated, already-migrated `knora_issue105_test` database passed:
**1413 passed, 16 skipped, 28 dependency deprecation warnings, 217.99 seconds**.
The final pass includes the actual spawned GPT composition. Ruff, Compose configuration,
OpenAPI export check and diff checks pass. Compose reports unset local MinIO credential
variables during its configuration-only check; this is not a storage-health assertion.

Primary integration verification passed 73 selected provider/bootstrap/launcher tests;
after the final formatting repair, all 11 primary provider tests passed again. The
runtime ANSWER/REFUSAL smoke and post-deletion daily preflight above exercise the final
primary commit. Frontend files and the generated public API contract were not edited
in this migration. Independent code reviews found no gate-blocking issues in the final
support, transplant and formatting changes; the independent semantic gate still failed
as recorded above.

## Extraction continuation: v2 and v3 (2026-10-02)

The owner approved repairing the extraction JSON contract and then preserving semantic
force before later production/Conversation measurements. These changes are evaluation-only.
The previously failed low-v1 observations remain immutable.

| Profile | Measured commit | Structurally valid | Literal passes | Independently reviewed semantic passes |
| --- | --- | --- | --- | --- |
| `gpt-oss-extraction-v2` | `24cc845a05277ad4bd52acc3150bb84c95cdc1d2` | 11/11 | 7/11 | 7/11 |
| `gpt-oss-extraction-v3` | `571a6ba24ca10420568d121d472d86e8f45a9229` | 11/11 | 7/11 | 7/11 |

Both runs used the pinned GPT-OSS digest, temperature zero, seed 105, context 4096, output
2048, named low reasoning and the 240-second parent supervisor. No deadline/supervisor
failure occurred. All eleven valid finals in each run are semantically scorable; the four
failures are not observation errors. The extraction schema, renderer acceptance, source
quotes, fixture and rubric remained unchanged. No held-out claim or Conversation acceptance
follows from these development-exposed synthetic cases.

V2 fixes the JSON compatibility failure by supplying the exact schema and abstract formatting
examples. Its four semantic failures are unsupported count, weakened prohibition,
irrelevant background citation and omitted qualified exception. V3 adds general modality,
relevance and qualification instructions. Its prohibition passes, but event-year inference
regresses; unsupported count, irrelevant citation and omitted exception remain. The
independent reviewer and root verified all request hashes, runtime/source provenance and
canonical response bindings. Raw model payloads, intermediate extraction and thinking are
not retained; private normalized finals and review notes remain outside Git.

Artifacts in `../vietnamese_rag/`:

- `issue105_process_gptoss20b_extraction_v2_seed105_literal.json`: SHA256
  `9dd41012199ca9517b6b065d36d03ce49406f6736eb2d4c072b18fabd4e3fe58`.
- `issue105_process_gptoss20b_extraction_v2_seed105_semantic_review.json`: SHA256
  `052d82a6af8282d34156763d55cdc18d49f6fa2077d676f551ebe8b0d7f5e140`.
- `issue105_process_gptoss20b_extraction_v3_seed105_literal.json`: SHA256
  `e61e1eb6fb03b745240a742f3a86e6c9ed8690f1d505c91030ba445ca603b84a`.
- `issue105_process_gptoss20b_extraction_v3_seed105_semantic_review.json`: SHA256
  `efb5563cd30352d16efb4b7e020bb13a9beed22f0f32f042d65420a0bef90889`.

V3 private finals SHA256:
`18bb9457c6454e13b90ee2008ce364917421db9170470b946ac451e336fbd010`.
V3 independent private verdict SHA256:
`9bb4c1ff5e14332f2ea051d1215eb46618a35f48800694d8f3552d1b4c7ca040`.

The actual local template SHA256 is
`fa6710a93d78da62641e192361344be7a8c0a1c3737f139cf89f20ce1626b99c`;
its `.System` value is inserted in Harmony developer instructions. No role drop was
demonstrated. All V3 finals finished with `stop`, using 1239–1318 prompt tokens and
48–232 completion tokens, within configured bounds. Structural validity and quote
membership do not prove semantic entailment. The unchanged renderer retains supplied
exceptions; missing qualifications are therefore lost during model selection.

V2 code verification passed 1422 tests, 16 skipped; V3 passed 1424 tests, 16 skipped.
Each reported 28 dependency deprecation warnings. Ruff, Compose configuration, OpenAPI
and diff checks passed. Compose only validates configuration here and reports unset
local MinIO credentials. Independent code review found no remaining blocker for these
bounded measurements; semantic acceptance still failed.

The final bounded instruction trial, `gpt-oss-extraction-v4`, requests compact source-clause
selection and exact source text in `facts.text`. Its schema/renderer and other request bounds
remain unchanged. It requires reviewed committed code and fresh measurement. If this third
repair fails, stop prompt repair and revisit the model/interface design with the owner.
No seeds 106/107, production eleven-case run or PDF/Conversation rerun follows a failed
preliminary gate. No extraction-only changes were integrated into local `codex/test`.
Keep #105 unaccepted and #116 as the final release gate.

V4 premeasurement verification: independent focused review passed 42 tests; full fresh
retry passed 1426 tests, 16 skipped, 28 dependency warnings in 216.59 seconds. The first
full invocation failed the existing completed-worker supervisor test; its cause remains
unestablished. Seven direct calls and the whole ten-test supervisor file then passed.
Only a safe assertion failure message was added; supervisor/deadline/cleanup behavior and
assertions remain unchanged. Both failed/passing log files are retained outside Git.
Ruff, Compose configuration, OpenAPI and diff gates pass. No real V4 result is claimed yet.
