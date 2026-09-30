# Evidence containment acceptance (#136)

## Scope and status

`retrieval-evidence-containment-v1` is an opt-in evidence-selection correction. It keeps
the M1 candidate count (8), similarity threshold (0.65), evidence count (5), and token
budget (3000). It does not seal the Qwen calibration artifact or complete #105/#116.

The old `adjacent-token-overlap-v1` behavior remains available unchanged. The new
`adjacent-content-containment-v1` policy discards an adjacent same-Chunk-Set candidate
only if its entire whitespace-token sequence occurs in a selected chunk. Case,
punctuation, order and repetitions are significant. Additional facts remain eligible,
subject to the existing budgets.

## Verification recorded on 2026-09-30

- Baseline: 10 evidence/configuration tests passed.
- RED: 10 evidence tests failed, including unique-date, number, negation, order and
  budget cases; the new configuration resolver failed before registration.
- A real PostgreSQL trace for the new configuration failed evaluation-reader provenance
  validation before its configuration was registered there.
- GREEN: 80 focused answering/evaluation-reader tests passed.
- Full suite against the isolated, migrated `knora_issue136_test` database:
  1267 passed, 15 skipped. Skipped tests are not acceptance evidence.
- Ruff, Compose configuration and diff checks passed. Independent review found no
  P0/P1/P2 findings.
- Integration with #105 preserved both its PDF citation test and the new unique-fact
  regression; 18 AnswerQuestion tests passed after resolving their adjacent additions.
- **Live Conversation acceptance remains BLOCKED.** Automatic approval review rejected
  the command to start the isolated API, Conversation worker and frontend, returning
  only `blocked by policy`. No real-model result for the corrected policy is claimed.

## Run the live gate with #105 integrated

Use the branch containing both #105 and #136. Stop the previous daily-dev supervisor
before starting another instance. In the PowerShell session that starts daily dev:

```powershell
$env:KNORA_RETRIEVAL_CONFIGURATION_ID = 'retrieval-evidence-containment-v1'
$env:KNORA_GENERATION_PROVIDER = 'ollama'
$env:KNORA_OLLAMA_GENERATION_MODEL = 'qwen3:8b'
.\scripts\start-dev.ps1
```

Use the existing authorized Workspace containing the supplied PDF and its active Qwen
embedding set. Do not re-import the PDF or change the threshold for this gate.

1. Start a new Conversation and ask `Hướng dẫn này được cập nhật lần cuối vào ngày nào?`.
2. Require an ANSWER containing `25/08/2024`, with a page-1 citation whose checksum is
   `5f9b7592ca8e1ececa7809376573cbd2f10d03446a5a57ebf02370db7f81dda3`.
3. Start another Conversation. Ask `Báo cáo dự án phần mềm được gợi ý trình bày bao nhiêu chương?`,
   then ask the update-date question again. Require the seven-chapter answer and the
   same date and citation checks. Record both Conversation IDs and exact Turn trace IDs.
4. In a separate Conversation, ask the frozen absent-information cases used by #105.
   Require refusal without citations. A refusal before generation cannot establish
   model-backed refusal correctness; report it separately.
5. Inspect each exact Turn's server trace: configuration must be
   `retrieval-evidence-containment-v1`; generation must be completed by Ollama `qwen3:8b`;
   the date chunk must be SELECTED and its alias cited. Check source/version/page/profile
   provenance against the active Workspace corpus and the pinned model digest.
6. Store sanitized IDs, configuration/model identities and pass/fail booleans only.
   Do not commit source text, provider output, credentials, cookies or browser traces.

Standalone retrieval can still miss a chunk below the unchanged threshold. Report that
as a remaining retrieval blocker; do not broaden this fix into threshold calibration.
Keep #105 and #116 open until their own complete gates pass.

## Rollback

Stop the supervisor, select the legacy configuration, and restart:

```powershell
$env:KNORA_RETRIEVAL_CONFIGURATION_ID = 'retrieval-m1-v1'
.\scripts\start-dev.ps1
```

No schema migration, source re-ingestion or embedding mutation is required.
