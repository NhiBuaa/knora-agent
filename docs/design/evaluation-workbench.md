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
The dense HTTP profile requires the actual workspace corpus to match the reviewed sources exactly.
A dataset source-key prefix does not filter Q&A retrieval; extra active sources block preparation
instead of producing a misleading READY result. Gold and saved reports remain unchanged.

PDF runs reuse RunStore and its fenced claim/checkpoint/finish lifecycle. The initial deterministic
report preserves every selected gold case and retained-source preparation state before execution;
terminal reports include blocked/failed/indeterminate cases and their reasons. Transport ambiguity
stops dispatch without automatic retry. Case reads prefer fresh checkpoints over an older report.
Runs detail polls progress; Case/Report screens label saved snapshots and offer a GET-only refresh.
Original PDF links use the existing authorized BFF route. Neither gold nor legacy metric contracts
change. Real-model UI acceptance, an owned runtime binding and provider quota approval remain
separate from this offline integration checkpoint.

## Supplementary A3/R2 implementation checkpoints

A3 proposes at most twelve drafts from retained PDF extraction snapshots through a registered
server profile. Draft import requires explicit selection of existing source anchors; it creates
an unreviewed A2 case, never gold or freeze approval. Unsupported categories, missing extraction
and missing profiles remain explicit readiness failures. Backend endpoints and fixed same-origin
BFF routes cover preflight, proposal batches and draft import. Live proposal profiles are blocked;
default application wiring has no proposal provider.

R2 scores exact saved observations without starting another Q&A run. The initial mappings resolve
the complete native M3 manifest or the exact frozen Builder PDF version/digest. Issue #153's PDF
format is explicitly unsupported until separately verified. REFUSAL, missing reference, missing
generation evidence and unavailable captures remain visible with per-metric applicability. No
semantic scores overwrite the deterministic report or imply quality acceptance.

Scoring preflight binds the selected saved inputs, dataset, binding, model, prompt version and
configuration. A scoring-purpose preflight cannot admit Q&A. The existing run stores append-only
supplementary batches with request idempotency; each dispatched case is durably marked uncertain
before its judge callback. Interrupted requests return the saved batch without replay. Callback
input, result and configuration snapshots are copied so callback mutation cannot rewrite input
provenance. Results must match the original run/case/trace, input digest and scorer identity.

Runs detail exposes profile readiness, case selection, preflight, scoring and saved per-case
metrics/rationale plus existing Case/Trace links. Read and launch capabilities remain distinct;
the browser cannot provide endpoints, paths, credentials or a scorer callback. Scoring profiles
are trusted server registrations. Default wiring registers none and live profiles are blocked
pending exact provider/egress/quota/budget authorization. Tests exercise the existing DeepEval
Cloudflare adapter through MockTransport only; no live acceptance is implied.

The existing application factory accepts explicit native/PDF, proposal and scoring profiles from
a trusted server host. Defaults stay empty; composition itself neither prepares a corpus nor
calls a provider. This is not a browser registry, runtime activation or live approval mechanism.
An actual corpus preparation/binding adapter and approved execution envelope are still required
for an owner UI demonstration; injected service fixtures alone do not prove that workflow.

## Trusted-host Live Admission

The owner approved this implementation separately from real execution. An explicitly injected
live profile requires an immutable host approval for the exact purpose, Workspace, profile and
input digest. Preflight, persisted admission and dispatch all recheck that authority. Safe approval
provenance is nested in existing run bindings, scoring inputs or proposal inputs; historical gold
and results are not rewritten. Browser input cannot create or enlarge this authority.

The host must supply fresh Workers Free/account/quota evidence, public or synthetic data authority,
a zero paid budget, an absolute deadline and exact provider request digests. A FULL-synchronous
SQLite journal reserves every HTTP attempt before egress and retains the stop latch and uncertain
request across restart. Exact endpoint/model/token/body checks, no redirects or retries, bounded
responses and a killable provider helper enforce the finite envelope. Missing evidence, drift,
expired proof, exhausted quota, stop or an uncertain prior request denies further dispatch.

Profiles must use the admission-created client at the actual provider boundary. This is a trusted
host composition contract, not a sandbox for arbitrary callbacks. Remote Q&A HTTP helpers without
an in-process guarded provider boundary remain blocked. Default profile registration stays empty.
Offline mock verification and independent source review do not authorize runtime activation,
provider calls, export, billing changes or merge; these require their separate owner decisions.

## Separate corpus preparation authority

The owner selected A: materialize and activate exactly two retained READY PDF versions under a
separate `corpus_prepare` trusted-host scope. The frozen dataset/digest, owner, Workspace/dataset
revisions, source/version/original/snapshot identities and hashes, document revisions and current
and active pointers, immutable parser/chunking/embedding configuration, job IDs and exact embedding
request digests are part of its input. The provider envelope pins the request budget and zero
retries. Gold approval and read-only `reviewed_pdf_preparation` do not grant this authority.

Admission durably records the operation before creating its two single-attempt processing jobs.
The host supplies a bounded `AttemptRuntime` and the actual handler's guarded embedding client;
the derivation thread receives the exact dispatch context. Stop or deadline cancels supervision
and fences late egress. A detached thread keeps its runner slot until physical exit. Both
derivations must succeed before their existing fenced activation finalizers share one transaction;
failure of either rolls back both active pointers and derivations. Owner, frozen/source/config and
revision pins are rechecked at provider dispatch and before/after activation.

Ordinary workers cannot claim, renew, recover, retry or close these jobs. Interrupted operations
remain durably stopped (or STARTED after a host crash), with admitted jobs retained and fenced;
there is no implicit recovery/retry. Any reconciliation needs a new reviewed scope and approval.
This adapter has no HTTP route, default registration or activation at startup. QA, scoring,
proposals and binding approval retain separate authority. Offline/mock evidence supplies no live
execution, quota, cost or runtime permission.
