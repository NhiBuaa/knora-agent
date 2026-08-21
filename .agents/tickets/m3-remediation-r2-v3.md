## R2 revision v3 — canonical population and latency semantics

This append-only ticket revision is governed by `docs/design/m3-remediation-v4.md` and
supersedes R2 v2. The case-ID digest uses compact sorted JSON plus one UTF-8 newline exactly as
specified. Manifest file/content digests use raw committed bytes. Paired equality is field-level
for generation/scorer versions, model, prompt, policy, stochasticity and every other equal field;
only the six retrieval configuration fields differ. `m3-paired-latency-v1` uses
`m3-latency-boundary-v1` with the explicit retrieval and executor boundaries in design v4.
Streaming cannot reuse this metric. Acceptance includes a structural/request proof that no
evaluation-only retrieval path is invoked.
