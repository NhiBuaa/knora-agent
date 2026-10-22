# Approved same-attempt revalidation and conditional continuation

[Owner decision](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6186149890)
selects the offline revalidation of saved `pdf-v3-001`, attempt 1. The original failed
capture, counters, partial report and archive manifest in the parent packet remain
historical evidence. This selection does not retry or replace that response.

## Selected observation

- [Selection record](revalidation-selection.json), canonical SHA256
  `c11b02c68114e5c1d65678c5d25cb35af9eaff4069d8841969d0c8fe02d6c799`.
- Owner/status/decision URL, raw capture hash, full original identity, response hash,
  approved proposal/derivation, evaluator source digest and corrected observation
  digest are checked by the shared collector before dispatch or selection.
- Public response, original conversation/turn/trace and **8287.240200001179 ms** live
  latency are unchanged. Original `observation_failure_code` remains historical;
  selected `failure_code` is null after the corrected citation checker accepts it.
- [Offline proof](selection-validation.json): frozen 18 files, 47 snapshot chunks,
  61 mappings / 25 missing anchors, 31 archived input hashes and nine rejected
  citation mutations. No model, database or external HTTP calls.

Both collection and reporting consume this same explicit selection record. There
is no second answer, attempt, dataset or observations store. Approval metadata uses
the repository's existing trusted-record convention; it is not a cryptographic
signature or online verification of GitHub authorship.

## Continuation gates

Total allowance remains **60 query embeddings / 60 generations**, including the
original 1/1. At most 59/59 remain. The first batch admits at most 11 new cases to
complete checkpoint 12; actual usage must be reconciled before further batches of
at most 12. No ingestion, automatic retry, judge, export or paid use is admitted.

The operational launcher may clear only the exact archived initial counter state,
once, after validating this selection. It retains the original stop, snapshot hash
and runtime provenance in continuation history. Later errors cannot use that
approval to resume again. Free admission is tested on a temporary counter copy;
the live stop stays in place until fresh CI/Free/account/quota and actual persisted
binding checks pass. Dataset/configuration and all 60 cases remain unchanged.

## Offline verification

- Collector focused suite: 50 passed. Related PDF/M3/binding suite: 100 passed.
- Original launcher mocks: hard 60/60, both 61st requests blocked, forbidden request
  shapes, durable counters, sticky provider failures and checkpoint boundary pass.
- Continuation self-check: only exact reviewed counter snapshot can resume once;
  counters, original case request flags and history are retained; drift/new stops
  and changed selection are rejected.
- Independent review: no findings; selection and original archive hashes checked.
- Ruff format/check/lint pass. Compose config passes with ambient missing MinIO
  variable warnings. Full suite is left to CI; no unrelated local rerun.

## Runtime status at publication

Continuation has **not run**. Attempts remain 1/60 query and 1/60 generation until
all live gates pass. Semantic review remains pending; this is not a quality PASS.
PR #189 stays Draft. Paid budget is 0 USD.

The `source/` directory records the continuation launcher and offline self-checks.
The original launcher archive in the parent packet is unchanged.
