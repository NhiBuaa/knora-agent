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
Guardrails AI was scoped to Issue #188 in shadow mode; existing security gates remain authoritative.

Disposition (2026-10-18): the owner [archived #188 as research-only](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6245695420).
Preserve its code and evidence; Detection Completed = NO and Protection Enabled = NO.
This does not approve runtime detector integration or reopen provider/activation permissions.
See the [#188 master plan](../plans/2026-10-16-issue-188-master-plan.md)
and [CI runbook](../runbooks/ci.md) for the retained research boundary.

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
Gold may retain additional sources, including failed extraction records, while the plan pins only
the two-source subset and the adapter rejects non-READY sources;
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

## Response-dependent admission and one bounded execution package

The owner approved code implementation of the [reviewed continuation plan](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6267679308),
recorded in [the code approval checkpoint](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6268076220).
Q&A generation depends on selected retrieval evidence, and later DeepEval prompts depend on earlier
judge responses. Mock request hashes cannot authorize those real requests. The trusted host must
derive each permitted request from pinned Knora input, code/template/schema identities and validated
responses of the same case or saved capture, then journal its digest before dispatch. Corpus
preparation and proposal requests retain exact-digest authorization. Browser payloads cannot supply
or enlarge this authority; the default live registry remains denied.

The same admission journal owns one immutable execution package and seven fixed operation slots:
corpus preparation (2), Gold v1 ANSWER (2), Gold v1 REFUSAL (2), Ragas proposal (1), Ragas ANSWER (2),
and two judge batches (12 each). The total is at most 33 HTTP attempts, with no retries or transfer of spare
capacity. Package, slot and request reservation must be atomic. Input binding is one-time; missing
or changed journal identity, pending/ambiguous operations, stop, error or expiry prevents further
inference. A restart cannot reset consumed calls or replay a started slot.

A separately approved live decision pins the reviewed code SHA, package identity, account/resources,
journal and manifest. It starts the 24-hour first-start limit and 48-hour package deadline; code
approval starts neither clock. At most three owned runtime windows, each at most 15 minutes, require
startup reservation and independent cleanup before their deadline. Each slot requires fresh Free
quota proof and immutable admission valid at most 5 minutes. No retained runtime or old envelope is
adopted merely because files still exist. Binding review remains a separate authority.

After reopening a draft, the owner reviews all current case digests again before freeze. Before
judge scoring, the owner records independent correctness/relevancy/faithfulness assessments against
the saved captures. The later comparison retains disagreements and missing evidence. Agreement on
two pilot answers is neither judge calibration nor benchmark-wide quality acceptance. Implementation,
offline tests, exact-SHA CI, actual PostgreSQL/provider execution and owner acceptance remain distinct.


## Addendum: Evaluation Tools Acceptance Envelope (Issue #158)

The owner approved the evaluation tools acceptance plan (`docs/plans/evaluation-tools-acceptance.md`)
for Issue #158. This acceptance round establishes a versioned execution package (`manifest_version: 2`)
with a finite, immutable envelope distinct from the legacy Issue #192 pilot:

1. **Scope and Data Authority**: Restricted to public/synthetic Gold sources under #153 (at most 6 PDF sources),
   6 selected baseline B continuation clean captures (ANSWER) and 2 saved REFUSAL controls, along with 4
   deterministic synthetic controls (wrong-fact, off-topic, unsupported, missing-exception) having fixed
   `validation_origin` descriptors. Legacy pilot journals remain read-only historical diagnostic records;
   they do not grant retroactive inference authority.
2. **Finite Inference Envelope**:
   - Total upper bound of **139 HTTP inference attempts** under Cloudflare Workers Free (paid budget USD 0).
   - Fixed slots: `corpus_prepare` (6), `qa_gold_v1_answer` (12), `ragas_vi_draft` (1), `judge_real` (72),
     `judge_synthetic` (48), and `refusal_deterministic` (0).
   - Saved branch: clean saved captures allow skipping fallback corpus and Q&A slots (`skipped_slots`) without
     transferring spared quota to other operations.
3. **Execution Windows and Clocks**:
   - At most **2 local runtime stack startups** and at most **8 execution windows** (up to 60 minutes each).
   - Hard package deadline of **7 days** from the atomically anchored first dispatch.
4. **Langfuse Pilot Authority**: A dedicated export seam allowing at most 3 traces and 3 observations
   (1 canary + 2 selected captures, 0 scores) with strict metadata allowlisting, opaque project-scoped IDs,
   immediate readback verification, and bounded batch deletion.
