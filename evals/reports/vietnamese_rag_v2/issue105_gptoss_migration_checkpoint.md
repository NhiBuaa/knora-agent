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

## Final bounded extraction trial: v4 fails (2026-10-02)

Measured clean source `112f0208cd4ecf3f25ccf5d2efb47c66972697e2`, tree
`bf8a320c7ef8aa18a62bae37f2a96a6ab777f4a8`, profile `gpt-oss-extraction-v4`:

- Eleven structurally valid finals; nine literal and nine independent semantic passes.
- `metadata_count` copies the entire source as ANSWER although the requested count is
  absent. It no longer invents a count but still fails the required refusal.
- `rule_with_exception` copies the ordinary requirement but omits the permitted alternative,
  eligibility and required approval. The other nine finals pass independent semantic review.
- No deadline/supervisor failure. Process latency 7.370–39.750 seconds; prompt tokens
  848–927 and completion tokens 49–171. All finals finish with `stop`.
- Pinned model, low reasoning, temperature zero, seed 105, context 4096, output 2048 and
  240-second supervisor remain unchanged. This is one development-exposed run.
- Root and independent reviewer verified all eleven response, actual request and parent/child
  runtime bindings. No raw reasoning/intermediate extraction is persisted.

Artifacts in `../vietnamese_rag/`:

- `issue105_process_gptoss20b_extraction_v4_seed105_literal.json`: SHA256
  `c4c0c795df34d7218c1957ca78f4aca997a793c5e561879dca2b4671c0dc29f4`.
- `issue105_process_gptoss20b_extraction_v4_seed105_semantic_review.json`: SHA256
  `dfd2dfc36ba9f88531eb0569299fdcc2ac67d1a18030b64f6af5e6a12eb39cdb`.
- Private normalized finals: SHA256
  `ad1de7009d58b4e5f650cbcc4ae19b123926cedb8752ea5c3756f020396eddbb`.
- Independent private verdict: SHA256
  `5268231ad148260ce32967d9804b2c1e86d4d825ed6e3ead4a8e4ed50bd345ea`.

The unscored `issue105_gptoss_schema_thinking_diagnostic.json` (SHA256
`312384a06aeee208f6bfcde6eb9ae1779209a959d43b401ba3844cf3952b8678`) compares
schema-on/off on the exception case. Both requests retain the same model, v4 prompt,
low reasoning, seed/context/output policy. Both return five-field JSON with zero exception
entries, 59 thinking characters and 95 generated tokens. No raw provider content/thinking
was retained; only shape/count/usage/request hashes. This single pair supplies no evidence
that removing schema fixes the failure, and is not a scored retry or acceptance artifact.
Its timeout is cooperative HTTP; no parent-supervisor deadline claim applies to it.

The approved three-repair stop condition now applies. Later seeds, production-provider
grounding, original36/revised36, durable Conversation and browser gates remain unperformed.
The supported medium reasoning level is a possible next isolated hypothesis, not measured
or selected for production. Discuss the changed request policy with the owner before code.
Local `codex/test` stays clean at `691a6b810d3f4d729c73f26d4fcc2113f1e477fd`.
Keep PR #135 draft, #105 unaccepted and #116 as the final release gate; retain worktrees.

## Owner-approved medium trial fails (2026-10-02)

After reviewing the failed low v4 gate, the owner explicitly approved one medium reasoning
trial with the same prompt/schema/fixture/rubric/bounds. The new evaluation-only profile is
`gpt-oss-extraction-v4-medium-v1`; its prompt identity and SHA256 remain v4, while the
request-policy identity distinguishes medium. No production selection or validator changes.

Measured clean source `bbb75522a7ae1b9e6dc2d3d9f2f3556767ca139c`, tree
`85338951de28062dffbed2dc8a07cbc4039776bf`:

- Eleven structurally valid finals; **nine literal and nine independently reviewed semantic
  passes**. Both failures remain `metadata_count` and `rule_with_exception`.
- The absent count is still answered with program parts. The ordinary requirement is still
  given without its permitted alternative, eligibility and required approval.
- Ten normalized finals are identical to low v4; the remaining shorter final still fails
  the same refusal criterion. No semantic gate improvement occurs in this single run.
- All eleven wire requests record medium and exact v4 system/user prompt hashes, temperature
  zero, seed 105, context 4096 and output 2048. Root and independent reviewer verified
  request/source/runtime and all canonical response bindings.
- No deadline/supervisor failure. Process latency 18.045–65.501 seconds, median 27.637;
  prompt tokens 848–927, completion tokens 116–710; every final finishes with `stop`.
- This is one development-exposed seed-105 run, not held-out or Conversation acceptance.
  Raw provider payloads and thinking are not persisted.

Artifacts in `../vietnamese_rag/`:

- `issue105_process_gptoss20b_extraction_v4_medium_seed105_literal.json`: SHA256
  `53af45a4ab7cbbea05ae56728668af18e947205d38f6061d33c6677ffc10a86c`.
- `issue105_process_gptoss20b_extraction_v4_medium_seed105_semantic_review.json`: SHA256
  `f525795b11b1bffe6c71440e020d549574ffd1e63d11b122d6a6ae77250f2db0`.
- Private normalized finals: SHA256
  `45182aac4ed188543e2115d6ed50b144ad747b6234788a1dad19cb14ebe93060`.
- Independent private verdict: SHA256
  `d66669032568265668aa3509dec3b0d0fd67cf6665cce274a49e6bece8d948ad`.

Code verification: root and independent review each passed 45 focused tests. Fresh full
isolated PostgreSQL gate passed 1429 tests, 16 skipped, 28 dependency warnings in 225.09
seconds. Ruff, Compose configuration, OpenAPI and diff checks pass. Compose's unset local
MinIO credential warnings do not establish storage health. No actionable code-review finding.

The approved preliminary failure stop condition applies. No later seeds, production-provider
grounding or PDF/original36/revised36/Conversation/browser measurements follow this run.
The reported token headroom and normal completion do not identify a token/deadline cutoff;
quote membership still cannot establish correct question support or qualification coverage.
Discuss the model/interface design before further implementation. Do not select medium for
daily dev from this failed trial. Local `codex/test` remains clean at `691a6b8`; PR #135
stays draft, #105 remains unaccepted, #116 remains the final release gate; keep worktrees.

## Owner-approved extraction and audit trial (2026-10-02)

After the failed medium trial, the owner approved an evaluation pipeline with two fixed
stages. EXTRACT uses the exact v4 prompt; AUDIT checks its untrusted provisional selection
against the complete original question/evidence. The backend renders only the final exact
source clauses. Both stages use medium, seed 105, temperature zero, context 4096 and at
most 1024 output tokens each. One 240-second owned deadline includes startup, digest
verification and both calls. Invalid output at either stage fails without repair/retry
or conversion to refusal. Production, schema, renderer, core validator and fixtures remain
unchanged; strict fact equality applies only to the new experimental transport.

Measured clean source `ae3000af3ba23afb55b516503321da03475dfe64`, tree
`93bde1f6357d004595f0af997de186c84f8317d7`, profile
`gpt-oss-extraction-two-stage-v1`:

- Eleven structurally valid finals; **eleven literal and eleven independently reviewed
  semantic passes**, zero failures and zero unscorable observations.
- The absent requested count correctly refuses. The ordinary rule includes its permitted
  alternative, eligibility and required approval. The other original criteria also pass.
- Root and reviewer independently verified all eleven canonical response bindings, 22
  actual EXTRACT/AUDIT request controls, eleven EXTRACT user hashes, committed source
  hashes and parent/child production runtime bindings. Ordered prompt manifest SHA256:
  `cb6dadb11ffeff87ee779e26b6b264e4e960f6d191949661b77cd1c19a67463d`.
- AUDIT user hashes bind actual requests but cannot be reconstructed from retained finals
  because provisional selections were deliberately discarded. Source and roundtrip tests
  verify that the full original question/evidence is copied before adding that selection.
  Neither review claims complete AUDIT body/hash reconstruction.
- No deadline/supervisor failure. Process latency 56.602–147.830 seconds, median 89.667;
  aggregate prompt 1740–1942 / completion 310–1417 tokens; all finish with stop. The
  transport enforces each stage's own 1024-token output limit.
- Four finals repeat supported source clauses: `explicit_prohibition`,
  `prohibited_requirement`, `caveat_after_distractor`, `rule_with_exception`. One also
  contains unnecessary supported background. These reduce presentation quality without
  changing the fixed semantic verdict; the rubric has not been broadened or relaxed.
- This is one development-exposed seed-105 run, not held-out or production/Conversation
  acceptance. No raw provider payloads, provisional selections or thinking are persisted.

Artifacts in `../vietnamese_rag/`:

- `issue105_process_gptoss20b_two_stage_seed105_literal.json`: SHA256
  `485cf20daf3a375deb7daef7d2b0de2106f05a20da2bfa96da1e52f5ff3c8378`.
- `issue105_process_gptoss20b_two_stage_seed105_semantic_review.json`: SHA256
  `2da5dd4d3024b15ac8e8a9cd2b56f4789bd0eb02960841f084a2f1385c067e3f`.
- Private normalized finals: SHA256
  `0cd751fb24dc871621b72ad29fe4cebce9c20b78b477eb174290fd7a9a01d79b`.
- Independent private verdict: SHA256
  `60e927d6f46037d73c766dfe0c925d89ad4d19f63f806ea9a78fa1fc86133b58`.

Premeasurement gates: root 69 focused tests; independent code review 67 (without two
unchanged thinking tests), no actionable finding. Fresh full isolated PostgreSQL gate:
1451 passed, 16 skipped, 28 dependency warnings in 239.08 seconds. Ruff, Compose
configuration, OpenAPI and diff checks pass. Compose's missing local MinIO credential
warnings are configuration observations, not proof of storage health.

The approved trial ends after these eleven cases. Later seeds, actual production-provider
grounding, original36/revised36 PDF, durable Conversation and browser/BFF/Keycloak gates
remain unperformed. The next design step must address presentation, latency and production
integration before those gates. Do not select this experiment for daily dev. Local
`codex/test` remains clean at `691a6b810d3f4d729c73f26d4fcc2113f1e477fd`; keep PR #135
draft, #105 unaccepted and #116 as final release gate. Preserve every prior failed report,
branch and worktree; no main merge or issue closure.

## Owner-approved source-clause deduplication trial (2026-10-02)

The owner selected a duplication-only change after the first two-stage trial. The new
evaluation profile `gpt-oss-extraction-two-stage-dedup-v1` validates the final AUDIT
selection with the existing renderer, then joins only identical or overlapping/adjacent
unambiguous selected spans from the same source alias. It copies their source text
verbatim and retains full exceptions, refusal and errors. EXTRACT/AUDIT prompts, medium
reasoning, source and fixture, model/digest, schema, temperature zero, seed 105, context
4096, 1024 output tokens per stage, two calls and the shared 240-second deadline remain
unchanged. This is evaluation-only; production, daily dev and local `codex/test` did not
select the profile.

Measured clean source `387c7cb1f2d8af779be77f05d8ed5824d69c979b`, tree
`d55cd5b1ac0073e60e50a9596a946a9b9727c245`:

- Eleven structurally valid finals, **eleven literal and eleven independently reviewed
  semantic passes**, zero failures or unscorable observations. All seven answers retained
  the requested facts and qualifications; the four refusals remained correct. No final
  repeats a selected source clause, versus four repeated-clause finals in the prior
  two-stage run. Atlas retains one supported but unnecessary background sentence. These
  presentation notes are outside the unchanged semantic rubric.
- Eleven ordered EXTRACT/AUDIT pairs used medium, temperature zero, seed 105, context
  4096 and output cap 1024 per stage. Root and independent reviewer checked the 22
  request records, eleven EXTRACT user hashes, all eleven canonical final bindings,
  source/prompt/schema/fixture hashes and parent/child runtime source hashes. AUDIT user
  hashes cannot be reconstructed from final-only artifacts because provisional selections
  were deliberately discarded; committed source and adapter tests establish original
  question/evidence construction. No complete AUDIT body reconstruction is claimed.
- No process deadline, supervisor or structural failure. Process latency was
  **66.702–171.070 seconds, median 101.199**. Ollama was observed as 0.35.0 before and
  after; the pinned GPT-OSS digest and model-template hash matched. The earlier trial ran
  against Ollama 0.34.4. This is not a controlled speed comparison, and before/after
  snapshots are not an attestation of every instant during the run.
- No provider payloads, provisional selections or thinking were retained. Normalized
  final text and the independent detailed verdict stay in private files outside Git.

Append-only artifacts in `../vietnamese_rag/`:

- `issue105_process_gptoss20b_two_stage_dedup_seed105_literal.json`: SHA256
  `dd558d0b374c4ade35cdecdf9b310e816f9d9e318504e71977c7f0264b520c0a`.
- `issue105_process_gptoss20b_two_stage_dedup_seed105_semantic_review.json`: SHA256
  `a6f51bc5335bd48161c4d9ad7cf32e4e6577aea3c172db8a0d30134299e4cfda`.
- `issue105_process_gptoss20b_two_stage_dedup_seed105_runtime.json`: SHA256
  `201fe6c07f3b5d9a3f8dce7c40a17df01d25c168c00d2749994356c7d0f1a6f2`.
  This is the LF-normalized Git artifact; the original CRLF runtime capture and the
  private-review `runtime_observation_sha256` are
  `343d02cb95fc0a126c345c45dfcba4b75313ec30723160ca9bd337f683220f95`.
- Private normalized finals: SHA256
  `893807c3df671c0fd4eb5b9c58d7dd74b6522745af8ab08d08ae5bfa26837660`.
- Independent private verdict: SHA256
  `ccf3cff0aba98ed867a670ded8507952d2f7df9855207f52cc1198040546c61c`.

Premeasurement code gates: root 104 focused tests; independent code review 67 focused
tests without actionable findings. Fresh full isolated PostgreSQL gate: 1486 passed,
16 skipped, 28 dependency warnings. Ruff, Compose configuration, OpenAPI and diff checks
passed. The prior failed observations remain preserved. This single development-exposed
seed 105 probe is not held-out or #105 acceptance. Later seeds, production integration,
original36/revised36 PDF, durable Conversation, Keycloak/BFF/browser and correlated trace
gates remain. Keep PR #135 draft, #105 unaccepted, #116 the final release gate; do not
merge, close issues or remove worktrees.
