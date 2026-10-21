# Issue #188 P1 Step A — offline evidence and observation contract

**October 17 follow-up:** Owner accepted the exact 16-case annotation packet
`f022804002150805827c16bac9231afc0a34c0b2ea12e77a26ba2704b9731bfc`
through the consolidated P3 approval in this chat. The draft bytes remain immutable;
the acceptance binding is recorded in the P3 configuration observation. Detector
quality remains unaccepted. The first P3 reserved attempt stopped without an HTTP
response; no native completed evaluation exists and Guardrails was disabled with
OFF readback. Historical P1-only approval wording below describes that earlier phase.

**Renewed P3 follow-up:** Trial-002 subsequently completed all 16 approved POSTs
and correlated native logs: 8 explicit P1 flags (6 attacks, 2 quoted controls),
8 Success-only outcomes unavailable, no completed negatives. Guardrails/DLP are
OFF and both finite trial grants are consumed. Full-population recall/FPR, quality
acceptance and Detection Completed remain unestablished. See the
[renewed P3 evidence](issue-188-p2-capability-investigation.md#renewed-p3-session--trial-002-october-17).

Authority: [owner approval](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6199169575)
and [single Master Plan](../plans/2026-10-16-issue-188-master-plan.md), phase P1.
This is an implementation/evidence note, not another implementation plan.

Review artifact: Draft [PR #205](https://github.com/NhiBuaa/knora-agent/pull/205), stacked on
PR #199 `bd5f288`. Code subject `e7a6e28d42475389e9c35e3b083f6876c8976413`; this follow-up
changes only handoff documentation. Exact-head unified CI is linked on PR/#188, using manual
branch dispatch because the existing PR trigger covers `main`, not this stacked base.

## Scope and reuse

`evals.runners.cloudflare_p1_shadow` prepares exact system + question/evidence messages using
the existing Cloudflare prompt and `user_message` serializer. Evidence order, aliases, Unicode
and whitespace are retained without truncation. This is generation evidence, not a whole-PDF
scan. A missing question or non-exact/missing evidence remains unavailable; never re-answer.
Native identity/conflict validation, reviewed-only metrics/populations and atomic non-overwrite
publication reuse PR #199 helpers. Those helpers, historical Secrets reports, backend/default
dependencies, CI, runtime and #153 gold are unchanged.

The runner has no network transport, token lookup, model download or Gateway configuration.
`--live` or `--authorization-manifest` exits with `LIVE_CONTRACT_NOT_APPROVED`, even if a file
claims approval. A future native adapter needs an approved phase and verified contract.

## Inputs and label review

Fixture: `evals/test/fixtures/cloudflare_p1_shadow/cases.json`. Sixteen synthetic development
cases: each of VI/EN has four attacks and four controls. Attacks cover override, fake canary
exfiltration, role spoofing and an instruction at the boundary between evidence units. Controls
cover quoted security research, legitimate procedural imperatives, role vocabulary and long
evidence boundaries. URLs use `example.invalid`; no real credentials or sensitive documents.

`labels.review.draft.json` binds proposed labels to the fixture SHA256. Its reviewer and decision
reference are null: **not approved labels**. The target is injection instruction presence in
selected generation evidence, not successful exploitation or prevention. After explicit owner
review of the exact fixture digest, a separate review artifact can supply `reviewed_by` and the
actual #188 approval-comment URL. The runner reuses the existing review validator; changing
fixture bytes invalidates that review. Native capture labels cannot be promoted through fixture
mode without explicit synthetic provenance. This fixture is supplementary development data in
Knora Evaluation, not a second gold source or release gate.

## Additive supplementary contract

Report schema `knora-security-observation-v2` is an offline supplement; existing Secrets schema
v1 remains unchanged. It preserves native run/attempt/trace/workspace and other capture identities,
source artifact SHA, exact message SHA, configuration SHA, scope and language. It contains no raw
messages, secret matches, arbitrary provider reasons, response bodies or credentials.

- Status: `detected`, `clear`, `unavailable`, `unknown`, `error`, `timeout`.
- Only explicit completed positive/negative observations can enter confusion metrics, and only
  with separately reviewed labels. HTTP 200 alone is not a negative. Missing/truncated log,
  incomplete evaluation, unknown schema and missing verdict remain unavailable.
- All selected cases remain in population; errors/timeouts/unreviewed/unavailable are explicit.
  Metrics are null when no labels are reviewed. VI/EN and scope groups use the existing metric
  semantics; failed cases do not disappear from denominators.
- `provider_quality_evidence=false`, `live_requests=0`, `enforcement=off`, `export=off`,
  `release_gate=false`, `replay_permitted=false`, `detection_completed=false`,
  `protection_enabled=false` are explicit.
- Accounting separates selected, imported attempted, observed, completed and retries. One
  imported dispatch maximum per selected unit; retries/duplicates fail. An indeterminate
  outcome stays unknown; an already-sent timeout remains counted and never replays.

The optional imported bundle `hypothetical-p1-v1` / log `hypothetical-p1-log-v1` is a **local
development test format invented for P1 tests, not a Cloudflare API schema**. It requires
`development_only=true`, source/config digests and per-row input/native identity binding.
Only this explicit hypothetical format can demonstrate positive/negative parser behavior.
Unknown/native shapes produce unavailable; they are not interpreted as verified provider data.
403/429, transport timeout and unexpected Guardrails 2016/2017 blocks are safe diagnostics.
No live readiness or Cloudflare quality follows from a mock import.

## CLI

Run from repository root with `PYTHONPATH=backend/src` and an existing backend environment:

```powershell
python -m evals.runners.cloudflare_p1_shadow --cases evals/test/fixtures/cloudflare_p1_shadow/cases.json --expected-sha256 sha256:2cac53d286a9ca1496614c9a5f24af548efd35380b92bb6063299f106d10a186 --output evals/reports/cloudflare_p1_shadow/prepared-001.json
```

For a native saved capture use `--capture` instead of `--cases`, with its exact byte SHA.
For hypothetical imports add `--observations PATH --observations-sha256 sha256:...`.
Reports are immutable; choose a new output path for a new run. Label review is optional and
separate via `--label-review PATH`; the unapproved draft deliberately fails review validation.

## Verification and acceptance

Technical P1 completion is separate from owner acceptance of labels and detector
quality. Final #188 states are **Detection Completed** and **Protection Enabled** independently:
neither is established here; enforcement OFF cannot support any attack-prevention claim.

### Offline artifacts

- Fixture SHA256: `2cac53d286a9ca1496614c9a5f24af548efd35380b92bb6063299f106d10a186`.
  A directory-local `.gitattributes` preserves LF bytes across platforms for digest binding.
- `evals/reports/cloudflare_p1_shadow/prepared-001.json`: all 16 selected units retained;
  zero attempted/completed/live requests; 16 unreviewed/unavailable detector outcomes; metrics
  null. Exact inputs are prepared in memory, never published as raw report text.
  File SHA256 `8b324a176d630d6cebf555214cface261b9056b0d65d121b2530af602bf87de1`.
- `evals/reports/cloudflare_p1_shadow/saved-pdf-prepared-001.json`: reuses the frozen #153 saved
  capture SHA `6daa50d8876efa79663ae433c7a0b2b8028a6f0091a8602d4fdd080dc7224729`;
  one generation-evidence unit unavailable because exact evidence/question is missing. Native
  failure/identity are preserved, zero attempts; this is no usable detector result.
  File SHA256 `cd835585f70c8d80071bf3526dc5941c02394533a484f481849a93f082e5dc57`.

### Review and gates

Independent review found contradictory restart accounting and missing safe subgroup metadata.
Regression tests were first observed failing, then both defects repaired and independently
re-reviewed: spec and code quality approved for the fixes. A final whole-P1 review also approved
both spec compliance and code quality, with no remaining findings. Focused result: **40 P1 + 16 Secrets
tests passed**. The real Secrets integration also passed in its existing isolated pinned
environment; no dependency was added to backend. Portable backend/evaluation suite ran with the
existing installed evaluation environment, no dependency installation. Final exact-head CI and
gate evidence are linked from the #188 handoff; no runtime/live quality is implied.

Ruff format/check/lint, generated OpenAPI check and Compose configuration validation pass.
Initial broad invocation failed collection in the default backend environment (missing
DeepEval/Ragas); the existing evaluation environment resolved it without skips. The first full
suite overlapped the deliberate P1 RED stage (37 expected missing-runner failures, 1380 other
tests passing); the subsequent run passed 1417 tests before three review regressions were added.
**Final portable run: 1420 passed, 621 deselected, zero skips/errors/failures**, including those
three regressions; 101.66 seconds. The 621 are explicit existing CI partitions for Windows,
database and runtime, not hidden P1 skips. Audit-hook verification of fixture preparation and
report digests saw **zero socket/DNS/subprocess attempts**. Report directory LF attributes keep
the recorded byte hashes stable. Existing deprecation warnings are
not a detector quality result. No full local database/services/runtime activation was performed.

## P2 entry conditions — historical handoff, superseded by the current Master

This P1 handoff recorded the state before the owner approved the P2 continuation.
The current status and authority are now maintained in the [Master Implementation
Plan](../plans/2026-10-16-issue-188-master-plan.md) and [P2 capability
investigation](issue-188-p2-capability-investigation.md). The following list remains
useful as the original P1-to-P2 gate record; it must not be read as denying the
approved P2 research/Dashboard-read envelope.

1. Owner authorizes a concrete P2 investigation envelope. This was subsequently approved;
   no cloud trial starts from P1 completion alone.
2. Same-account least-privilege read access or owner dashboard snapshot resolves the previous
   403/code10000. The approved Dashboard read supplied current token/account/plan/usage metadata;
   historical credential continuity, Gateway/log cohort, billing mode, quota timestamp and
   retention remain unresolved.
3. Verify a native completed-positive and completed-negative result/log mapping, correlation,
   segmentation/roles/threshold behavior and streaming limits. The hypothetical parser is not
   evidence for this contract.
4. Establish current P1 + generation + logs billing and a conservative bounded trial packet.
   Unknown cost remains a gate; do not call inference to discover price.
5. Before P3, separately approve exact labels/digests, data egress, dedicated FLAG-only Gateway
   diff/log retention/readback, provider/model/call/token/time/cost caps and stop/rollback policy.
   P2 research permission itself grants no configuration or inference authority.

No model inference, Gateway/config/logging mutation, cost, runtime activation, enforcement,
export or merge occurred in this phase. PR #199 remains a separate unmerged Secrets baseline.

### Acceptance handoff

- P1 offline technical deliverables, tests, preparation artifacts and independent review are
  complete; final technical DoD additionally requires exact-head unified CI success as recorded
  on PR/#188. This does not mean owner acceptance of detection quality.
- Sixteen fixture labels await digest-bound owner review. No real P1 execution or TP/FP/FN/TN
  result exists; mock tests demonstrate orchestration only.
- `Detection Completed: no` for the final agreed #188 scope/quality.
- `Protection Enabled: no`; enforcement and runtime activation remain OFF/unapproved.
- P2 was not authorized by this historical handoff; the later continuation approval is recorded
  in the Master and its P2 artifact. Retain Draft/Open and Project In Progress until owner
  disposition.
