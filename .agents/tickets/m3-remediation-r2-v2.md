## R2 revision v2 — manifest and paired-report binding

This append-only ticket revision supersedes the scope clarification in
`.agents/tickets/m3-remediation-r2.md` and is governed by `docs/design/m3-remediation-v3.md`.

### Additional locked invariants

- Production binds exact paths, Git blobs/commit, file SHA-256 digests, dataset content digest,
  exact sorted 50-case-ID digest, corpus version and Chunk Set provenance from the immutable
  M3 manifests. Repository-state mutation is not accepted as a substitute for this binding.
- Paired reports must match every equal-provenance field individually, including generation
  configuration, scorer configuration/model/prompt/policy/stochasticity, evaluation commit and
  artifact schema. Only the six retrieval-configuration fields listed in the design may differ.
- Pair-level latency is `m3-paired-latency-v1`, per-case and explicit; no aggregate hard cutoff
  or cross-metric inference is allowed.
- Acceptance must include structural/request evidence that `HttpEvaluationExecutor` uses the
  public Q&A endpoint and never invokes an evaluation-only retrieval path.

### Acceptance additions

- Wrong path/blob/digest, case-ID digest, generation/scorer field and evaluation-only-path
  mutations each fail closed.
