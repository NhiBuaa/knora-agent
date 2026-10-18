# Keep evaluation authority and data permissions in Knora

Status: accepted design through Issue #158; implementation and quality acceptance remain distinct.

Knora owns datasets, gold, manifests, runs, reports and release gates. DeepEval supplies correctness,
answer relevancy and faithfulness observations; Ragas prepares multi-hop review drafts and may
experiment with NoiseSensitivity when inputs and judge are suitable. They consume the same
captured application output and provenance. Tool thresholds do not become Knora gates, and drafts
require the owner's approval before gold promotion. Citation and refusal verification remain
independent. This avoids competing dataset, runner and release authorities.

Issue #153 owns the 16-PDF/60-question Gold Dataset and Retrieval V3 baseline. Issue #158
integrates these tools with Knora's datasets, provenance, runners and reports. Ragas proposes new
questions only when a later evaluation expansion is needed; it does not regenerate #153's 60
questions or expand gold automatically. Every proposed addition requires owner review.

Cloudflare Workers AI GPT-OSS 20B is the preferred judge, subject to human comparison. Approved
public/synthetic inputs may leave the machine for Cloudflare; private inputs without permission
remain local. Langfuse Cloud Hobby in Tokyo receives only opaque IDs, approved metadata and numeric
diagnostics, initially accessible only to the owner. Export stays off until its separate approval
and data-policy verification, including deletion/readback for a seven-day retention target.
Guardrails AI belongs to Issue #188 in shadow mode; existing security gates remain authoritative.

The first DeepEval trial is conditional on verified zero paid cost and public/synthetic permission,
with at most 24 HTTP attempts and 60 minutes. An unknown or Paid Workers plan blocks that trial;
free quota alone cannot guarantee zero overage on Paid. No automatic upgrades, new models, paid
providers, Cloud export or enforcement follow from installing the packages.

Dashboard evidence for the same account may establish Free/quota when the billing API returns
403. Verification alone does not authorize a model call: each live run needs explicit approval.
Code integration may merge after CI and review pass without live quality evidence; Issue #158
remains In Progress until the owner accepts actual quality.

Decision records: [approved implementation](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6170561475),
[shared boundary](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6170886584),
[zero-cost preflight](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6170823327).

## Evaluation Workbench

The [approved Workbench contract](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6185802219)
connects Dataset Builder and Evaluation Runner through Knora-owned, versioned gold. Gold approval
verifies original-PDF evidence independently of current extraction/chunking or runtime binding;
binding incompleteness does not prevent freeze. Selection and binding are separate artifacts rather
than rewritten gold. Reports retain every selected case, including missing/unscorable/failed cases,
and disclose metric-specific populations. New PDF evidence-group coverage has its own scope and
contract; it does not replace M3 or #153 metrics.

R3 (#198) is accepted using manually authored, reviewed/frozen A2 gold and a deterministic report.
Ragas-to-Runner integration belongs to the final parent #192 demo; DeepEval is supplementary and
cannot block deterministic evaluation. Partial deterministic reports explicitly retain pending
semantic sections and do not weaken complete M3 report validation. Owner gold approval grants
neither provider egress permission nor live execution authority. See
[owner approval](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6185965119) and
[design](../design/evaluation-workbench.md).

## Corpus preparation authority

The owner selected the separate `corpus_prepare` trusted-host scope for the Workbench. One
immutable operation may materialize and activate exactly two pinned READY PDF Document Versions;
it must retain their Document Version identities and cannot touch the FAILED source, another
Workspace, Gold, thresholds or historical runs. The plan binds owner identity, Workspace/dataset
revisions, raw and original-object hashes, extraction snapshots, chunking/embedding configurations,
job IDs and one bounded attempt per source. Existing read-only binding preparation remains
read-only, while Q&A, scoring, proposal and binding-review authorities stay separate.

Admission records the plan before mutation and persists the stop/deadline state. The authority is
rechecked before job admission, at each provider dispatch and immediately before and after the
existing fenced activation finalizer. Ordinary worker claim and expiry recovery exclude these jobs;
missing authority, drift, expiry, stop or an uncertain operation fails closed. This design is
implemented and tested only with offline/mock I/O under the approved implementation scope; no
runtime activation, real provider call, billing change, export or deployment follows from it.
