# M3 sealed evaluation environment V1

This authority extends the pre-start bootstrap lifecycle. It prevents corpus/retrieval provenance
drift during an M3 #51 run without adding any behavior to the measured Q&A path.

```text
bootstrap → corpus-closure PASS → seal environment → inject startup auth
→ start production API → measured Q&A → post-run closure/provenance verification → teardown
```

## Control-plane seam

```text
EvaluationEnvironmentSeal.acquire(preflight snapshot, run owner)
  -> exclusive sealed-environment capability

EvaluationEnvironmentSeal.verify_unchanged(capability)
  -> post-run PASS | environment drift failure

EvaluationEnvironmentSeal.release(capability)
  -> teardown
```

The capability is owned by one evaluation run. Acquisition requires a verified Binding V3 and
corpus-closure PASS snapshot. If exclusivity cannot be established, acquisition fails and no
measured Q&A is sent.

While held, control-plane mutation seams reject ingestion, reprocess, delete, activation, Document
Version/Chunk Set rebinding, Binding V3 replacement and resolved Retrieval Configuration change in
the sealed Workspace. Q&A and Question Trace persistence remain allowed. This is a provenance seal,
not a request lock.

After all Q&A observations, `verify_unchanged` re-reads active corpus closure, V3 source bindings
and resolved Retrieval Configuration and compares each with the preflight snapshot. Any mismatch
is `EVALUATION_ENVIRONMENT_DRIFT`; the run is an environment/observation failure, not quality-valid,
and no quality scores are published. Acquisition, verification and release are outside individual
Q&A request/response intervals and are excluded from `end_to_end_latency_ms`.
