# Keep evaluation authority and data permissions in Knora

Status: accepted design through Issue #158; implementation and quality acceptance remain distinct.

Knora owns datasets, gold, manifests, runs, reports and release gates. DeepEval supplies correctness,
answer relevancy and faithfulness observations; Ragas prepares multi-hop review drafts and may
experiment with NoiseSensitivity when inputs and judge are suitable. They consume the same
captured application output and provenance. Tool thresholds do not become Knora gates, and drafts
require the owner's approval before gold promotion. Citation and refusal verification remain
independent. This avoids competing dataset, runner and release authorities.

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

Decision records: [approved implementation](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6170561475),
[shared boundary](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6170886584),
[zero-cost preflight](https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6170823327).
