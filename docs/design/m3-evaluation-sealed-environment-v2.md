# M3 sealed evaluation environment V2

V1 remains immutable. V2 moves the authoritative measurement snapshot after exclusive ownership
and keeps the seal an evaluation orchestration boundary, not a production-wide mutation feature.

```text
bootstrap/provision corpus → acquire exclusive seal
→ corpus-closure PASS + capture Binding V3/configuration snapshot
→ inject startup auth → start production API → measured Q&A
→ post-run verification while sealed → stop API → release seal/process/ephemeral credential
```

## Control-plane seam

```text
EvaluationEnvironmentSeal.acquire(run owner)
  -> exclusive ownership capability

EvaluationEnvironmentSeal.capture_preflight(capability)
  -> closure PASS + Binding V3/configuration snapshot

EvaluationEnvironmentSeal.verify_unchanged(capability, snapshot)
  -> post-run PASS | EVALUATION_ENVIRONMENT_DRIFT
```

Bootstrap may materialize corpus before acquiring seal, but `capture_preflight` occurs only after
the capability is held and supplies the sole authority snapshot for measured Q&A. If acquisition
fails, no Q&A occurs.

The guarantee that corpus/retrieval provenance does not change while sealed can use the isolated
evaluation topology, exclusive run ownership, restricted actors/credentials, or an existing
centralized mutation guard. #51 does not require adding evaluation-specific seal checks to every
production ingestion/reprocess/delete/activation path. TC-01 tests the mutation paths and actors
that are supported and present in this evaluation topology; they must not mutate the sealed
environment. Q&A and trace persistence remain permitted.

Post-run verification happens while still sealed and compares active closure, Binding V3 and
resolved retrieval configuration with the sealed snapshot. Any drift invalidates the entire run as
an environment/observation failure and prevents quality score publication. All seal control-plane
actions are outside request Q&A timing and excluded from `end_to_end_latency_ms`.
