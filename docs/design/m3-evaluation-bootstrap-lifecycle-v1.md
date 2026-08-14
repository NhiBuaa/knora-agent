# M3 evaluation bootstrap lifecycle V1

This authority complements immutable Environment Binding V3. It determines how an isolated
evaluation environment exists before a normal production Q&A process starts; it does not change
the measured request path.

```text
EvaluationEnvironmentBootstrap.prepare(manifest, environment request)
  → idempotent Workspace control-plane seam
  → normal application/ingestion corpus materialization
  → verified Binding V3 + ephemeral scoped raw credential
  → runtime launcher injects startup auth configuration
  → create_app() starts normal ApiKeyAuthenticator
  → corpus-closure preflight
  → production POST /v1/questions
```

## Control-plane seams

```text
EvaluationWorkspaceProvisioner.provision_or_reuse(workspace specification)
  -> persisted isolated Workspace

EvaluationEnvironmentBootstrap.prepare(manifests, environment specification)
  -> Binding V3 + EphemeralEvaluationCredential

ProductionRuntimeLauncher.start(startup auth configuration)
  -> production API process
```

`EvaluationWorkspaceProvisioner` is idempotent and application/control-plane owned; it is neither
ad-hoc SQL from acceptance nor a public acceptance-only HTTP endpoint. Bootstrap calls normal
application/ingestion seams to materialize the corpus and reads authoritative projections to verify
Binding V3 and closure.

`EphemeralEvaluationCredential` contains the raw credential and its Workspace-scoped normal
credential record only while the launcher is preparing the process. The launcher serializes the
hash-only normal credential record into `KNORA_API_CREDENTIALS_JSON` (or a typed equivalent) before
calling `create_app()`. Nothing stores the raw value in Binding V3, logs, reports, or committed
artifacts. The API process uses the existing `ApiKeyAuthenticator` exactly as any normal process;
there is no request override, hot reload, or mutation during a measured run. Teardown removes the
process/runtime configuration and ends the ephemeral credential lifecycle. #51 does not need a
separate revocation mechanism.

The evaluator starts only after process startup and closure preflight. It receives the raw key only
as runtime input to Q&A calls; it cannot invoke provision, credential issue, activation, or revoke.
