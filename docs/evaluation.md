# Milestone 1 evaluation

The Milestone 1 runner measures deterministic structural invariants, retrieval quality and system
observations through the versioned `POST /v1/questions` HTTP seam. It does not claim semantic
answer quality. Model-backed semantic scoring belongs to Issue #7.

## Pinned inputs

- Dataset manifest: `evals/datasets/milestone_1.manifest.json` (`m1-dataset-v1`).
- Dataset: `evals/datasets/milestone_1.jsonl`, containing 20 curated cases.
- Corpus manifest: `evals/corpora/milestone_1/manifest.json` (`m1-corpus-v1`).
- Runtime configurations: `chunking-m1-v1`, `embedding-local-m1-v2` and the retrieval
  configuration observed in each persisted Question Trace.
- Workspace: the dedicated local `evaluation-m1-r2` Workspace.

The runner checksum-binds the dataset version, validates every corpus document checksum, verifies
that every relevance judgment resolves to a pinned Chunk, and requires the Workspace's complete
active corpus/configuration state to match the manifest before sending questions.

## Prepare the factual corpus

With PostgreSQL healthy and migrations at head, create the dedicated Workspace once:

```powershell
@'
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import WorkspaceTable
with SessionFactory.begin() as session:
    if session.get(WorkspaceTable, "evaluation-m1-r2") is None:
        session.add(WorkspaceTable(id="evaluation-m1-r2", name="Milestone 1 Evaluation R2"))
'@ | .\.venv\Scripts\python -
```

Ingest every pinned factual Document through the application-backed CLI seam:

```powershell
$manifest = Get-Content -Raw evals\corpora\milestone_1\manifest.json | ConvertFrom-Json
foreach ($document in $manifest.documents) {
    $path = Join-Path evals\corpora\milestone_1 $document.path
    .\.venv\Scripts\knora-ingest.exe $path `
        --workspace $manifest.workspace_id `
        --source-key $document.source_key
}
```

The runner rejects missing, extra or differently derived active Documents. Use a clean dedicated
Workspace rather than mixing unrelated retrieval state into it.

## Run through HTTP

Start Knora in deterministic-local mode with a credential for `evaluation-m1-r2`. Keep the raw
key only in runtime environment state and expose it to the runner through a named variable:

```powershell
$env:KNORA_EVALUATION_API_KEY = "<runtime-only-key>"
```

Always choose a new report path. Publication uses an atomic no-clobber operation, so concurrent or
repeated writers cannot replace completed evidence.

```powershell
.\.venv\Scripts\python -m evals.runners.run_http_eval `
    --dataset evals\datasets\milestone_1.jsonl `
    --dataset-manifest evals\datasets\milestone_1.manifest.json `
    --corpus-manifest evals\corpora\milestone_1\manifest.json `
    --endpoint http://127.0.0.1:8000/v1/questions `
    --report evals\reports\milestone_1-http-r1.json
```

The report separates:

- structural hard gates derived from HTTP responses and trace-scoped PostgreSQL projections,
  including decision/citation contracts, Evidence Set membership, independently resolved
  candidate Workspace ownership and persisted traces;
- per-case and aggregate Recall@8, MRR, hit rate and observed retrieval latency;
- end-to-end latency, usage, cost and provider errors;
- expected-behavior observations, which are not confused with structural validity;
- semantic status, which is explicitly `not_run` in deterministic-local mode.

The trace projection requires both the opaque `trace_id` returned by HTTP and the dataset
Workspace. It does not expose a public trace endpoint or permit trace enumeration.

## Repeatability

Run into a second new path, then compare normalized reports. Only retrieval and end-to-end
wall-clock observations are excluded:

```powershell
.\.venv\Scripts\python -m evals.runners.compare_reports `
    evals\reports\milestone_1-http-r1.json `
    evals\reports\milestone_1-http-r2.json
```

Case ordering, provenance, structural outcomes and retrieval metrics must remain identical.
