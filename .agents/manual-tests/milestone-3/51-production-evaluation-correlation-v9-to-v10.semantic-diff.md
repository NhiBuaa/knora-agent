# Semantic diff: issue-51-v9 → issue-51-v10

## Changed

- Defines a pre-start control-plane lifecycle: bootstrap Workspace/credential, inject normal startup
  auth configuration, start production API, run closure preflight, then make production Q&A calls.
- Authorizes an idempotent application/control-plane Workspace provisioner; forbids ad-hoc
  acceptance SQL and a public acceptance-only endpoint.
- Makes the raw scoped key ephemeral launcher/evaluator runtime input only. Binding/report/log/
  committed evidence retain no raw key. The started API uses ordinary `ApiKeyAuthenticator`; no hot
  reload, evaluation-only auth path, or credential mutation occurs during measurement.

## Unchanged

- Binding V3, corpus closure, mandatory per-source version/Chunk Set triple gate, canonical Chunk
  identity, resolver, Recall@8/MRR/denominator, citation, semantic and latency semantics.
