# Evaluation Workbench

Status: owner-approved design; implementation and product acceptance are separate.

Authority: [Issue #192](https://github.com/NhiBuaa/knora-agent/issues/192),
[contract and implementation plan](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6185802219),
[owner approval](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6185965119).

## Modules and authority

Dataset Builder prepares retained PDF sources, proposes or manually authors cases, obtains human
review, and freezes a versioned gold dataset. Evaluation Runner consumes frozen datasets without
requiring another Builder run. Knora owns canonical datasets, approvals, manifests, selections,
bindings, runs, observations, reports, and gates. DeepEval scores saved captures; Ragas proposes
drafts. Neither creates a second gold authority. Langfuse export and Guardrails enforcement remain
off. Existing M3 and Issue #153 contracts and release artifacts remain unchanged.

## Minimal canonical contract

The versioned dataset reference contains dataset ID, version, Workspace, format/metric contract,
and digest. Legacy references retain native checksums and existing release authority. New PDF gold
uses immutable source references (Document, Document Version, raw SHA-256) and cases with stable IDs,
question, reference answer/required facts, expected ANSWER/REFUSAL, language/category, required
evidence groups, and ordered context dependencies.

An evidence group requires at least one accepted alternative; all required groups must be covered.
Each anchor identifies its source version and physical page plus reviewed quote or region. Text
offsets are start-inclusive/end-exclusive and require the exact extraction snapshot and checksum.
Independent extraction processing records and runtime bindings are separate artifacts and do not
participate in gold identity. A reviewed anchor's extraction snapshot ID, checksum, and offsets
are part of immutable gold when supplied; later re-extraction never updates that reviewed anchor.
Original-PDF verification can justify freezing despite incomplete extraction or runtime binding.
Failed extraction does not become successful preparation and remains visible.

New PDF gold hashes canonical UTF-8 JSON with sorted object keys, compact separators, no BOM or
trailing newline, and meaningful array order preserved. Identity/version, sources, cases and metric
contract participate. Digest itself, mutable processing state, runtime binding and freeze approval
do not. Freeze approval binds the exact gold digest and owner identity. Frozen edits create another
version. Freeze approval is never provider, egress, or execution authorization.

Selection records exact dataset/version/digest, selected case IDs, and ordered context-only
dependencies. It does not edit gold or its population. Unknown/duplicate IDs and cyclic dependencies
fail validation. Context-only cases are disclosed separately and do not enter metric denominators.
Unsupported follow-up execution is a readiness blocker, never a silently flattened question.

## Results and metrics

Execution state is distinct from quality acceptance. Each selected case remains represented when
blocked, not run, failed, unscorable, or indeterminate. A missing/mismatched correlated trace is an
observation failure. Exact `(workspace_id, trace_id)` correlation comes from the response; latest
or timestamp lookup is prohibited. Saved captures are immutable inputs for supplementary scorers.

PDF evidence-group coverage uses all ordered fused candidates before evidence selection. Coverage
of the exact evidence sent to generation is a separate diagnostic. V1 adds no cutoff K; candidate
budget, actual count and retrieval configuration remain provenance. Missing/ambiguous required
bindings make the case unscorable, not a smaller denominator. Valid miss is zero. No-answer
retrieval is not applicable; false REFUSAL on an answerable case remains applicable. Empty metric
denominators yield null. Reports disclose dataset, selected, context-only, attempted, observed,
applicable and evaluable populations. M3 Recall@8/MRR and #153 metrics keep their original meanings.

Deterministic report sections may be available while semantic review is pending. Such a report is
explicitly incomplete for semantic/release acceptance; the existing complete M3 report validator
is not weakened and no fabricated semantic result is passed to it.

## Access and execution

Workspace ownership is checked before resource lookup or effects. Reading requires operator:read;
source PDFs also require documents:read. Dataset writes require evaluations:write; upload also
requires documents:write. Owner review/freeze requires evaluations:approve. Run admission requires
evaluations:run, and Q&A execution retains its questions:ask authority. No runtime permissions are
automatically provisioned. Browser requests carry IDs and registered profiles, never commands,
local paths, arbitrary endpoints or credentials.

Live execution needs separate exact-scope approval, provider compatibility and fresh Workers
Free/account/model/quota proof, with enforceable provider HTTP-attempt, token and time limits.
Unknown proof blocks live calls. No paid fallback, model download, shared-runtime change, or
automatic replay of indeterminate provider requests is permitted. Completed captures and consumed
attempts survive interruption. Private data without egress permission remains local.

## Delivery boundaries

1. Shared contract code and fixtures form a common checkpoint under #192.
2. R1 (#193) and A1 (#194) proceed in separate worktrees after that checkpoint.
3. A2 (#195) prioritizes basic manual creation/review/freeze. Contract semantics preserve multi-hop,
   scoped no-answer, and follow-up; advanced editors/orchestration do not block it.
4. R3 (#198) depends only on R1 and A2 and is accepted with manually authored A2 gold, independently
   of DeepEval or Ragas. It produces a deterministic report.
5. R2 (#196) adds DeepEval scoring to saved captures. A3 (#197) extends the existing Ragas adapter
   to reviewed new-PDF proposals. The A3-to-R3 demo belongs to parent #192 acceptance.

The coordinator owns shared contracts, root wiring, table/migration ordering, capability fixtures,
navigation and generated OpenAPI. R1 owns run/execution/report behavior; A1 owns source preparation
and retention. Shared changes are coordinated in issue discussions before editing. Reuse current
PostgreSQL, ObjectStore, worker patterns, runners and trace viewer. No additional framework or
queue infrastructure is introduced by this design.

## R3 implementation checkpoint

Builder PDF selection carries the complete frozen reference into the existing Runs preflight.
The server resolves that exact version and digest; the browser does not supply a runtime binding.
A registered PDF runtime profile prepares an independently reviewed binding snapshot containing
the source hashes, runtime chunk/embedding sets, configurations, candidate budget and reviewed
anchor-to-chunk alternatives. The binding review digest is independent of freeze approval and
never grants provider-call permission. A profile must verify its owned runtime corpus afresh.
Preflight, admission and the queued worker recheck the snapshot before dispatch. Default application
wiring registers no executable profiles; live profiles remain blocked pending separate approval.

PDF runs reuse RunStore and its fenced claim/checkpoint/finish lifecycle. The initial deterministic
report preserves every selected gold case and retained-source preparation state before execution;
terminal reports include blocked/failed/indeterminate cases and their reasons. Transport ambiguity
stops dispatch without automatic retry. Case reads prefer fresh checkpoints over an older report.
Runs detail polls progress; Case/Report screens label saved snapshots and offer a GET-only refresh.
Original PDF links use the existing authorized BFF route. Neither gold nor legacy metric contracts
change. Real-model UI acceptance, an owned runtime binding and provider quota approval remain
separate from this offline integration checkpoint.
