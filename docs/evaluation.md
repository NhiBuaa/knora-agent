# Milestone 1 evaluation

The Milestone 1 runner measures deterministic structural invariants, retrieval quality and system
observations through the versioned `POST /v1/questions` HTTP seam. Deterministic-local mode does
not claim semantic answer quality. Model-backed mode adds the first semantic baseline through an
explicit, versioned scorer without applying an arbitrary quality threshold.

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
- semantic status, which is explicitly `not_run` in deterministic-local mode. Model-backed mode
  reports citation entailment, faithfulness, answer relevance and refusal correctness under a
  dedicated `semantic` section.

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

## Model-backed semantic baseline

Run the application in `openai-compatible` mode with an active corpus derived under the same
immutable OpenAI-compatible Embedding Configuration used by the runtime. The repository includes
`evals/corpora/milestone_1/manifest.openai-compatible.json` for this derivation; it keeps the
factual content checksums while pinning `embedding-openai-m1-v1`. Keep the provider key
and scorer key in runtime environment state only. The application provider and the semantic judge
may use the same compatible endpoint, but they remain separate runtime roles.

The runner requires all of the following for model-backed mode:

- `--scorer-version`, a versioned scorer identity;
- `--scorer-method`, the explicit measurement method;
- `KNORA_SEMANTIC_SCORER_BASE_URL`;
- `KNORA_SEMANTIC_SCORER_API_KEY`;
- `KNORA_SEMANTIC_SCORER_MODEL`.

Optional scorer pricing variables are `KNORA_SEMANTIC_SCORER_PRICING_VERSION`,
`KNORA_SEMANTIC_SCORER_INPUT_COST_PER_MILLION_TOKENS` and
`KNORA_SEMANTIC_SCORER_OUTPUT_COST_PER_MILLION_TOKENS`. Missing pricing is reported as
`unavailable`; it is never guessed.

Use a fresh report path for every run:

```powershell
.\.venv\Scripts\python -m evals.runners.run_http_eval `
    --dataset evals\datasets\milestone_1.jsonl `
    --dataset-manifest evals\datasets\milestone_1.manifest.json `
    --corpus-manifest evals\corpora\milestone_1\manifest.openai-compatible.json `
    --endpoint http://127.0.0.1:8000/v1/questions `
    --report evals\reports\milestone_1-semantic-baseline-r1.json `
    --mode model-backed `
    --scorer-version semantic-scorer-v1 `
    --scorer-method llm-judge-v1
```

The semantic report keeps deterministic structural validity separate from model-judged citation
entailment/support. System observations remain separate under `system`, including application and
scorer latency, token usage, cost and provider errors. The first 20-case run is a baseline
observation, not a portfolio claim: CV claims require at least 50 cases and an explicit dataset
size and measurement method.

### Gemini OpenAI-compatible temporary runtime

Gemini can be used through its OpenAI-compatible base URL for both application generation and
embeddings. The approved Gemini embedding space is the separate, versioned
`embedding-gemini-m1-v1` (`gemini-embedding-001`, 1536 dimensions, cosine). Keep the application
embedding space at 1536 dimensions and use the provider-specific manifest
`evals/corpora/milestone_1/manifest.gemini.json`, which pins that configuration. Re-embed and
activate the corpus under this configuration; do not switch only an environment variable or mix
its vectors with another configuration. The Gemini OpenAI-compatible embedding response may omit `data[*].index`;
the adapter preserves wire order when that field is absent and rejects a response whose vector
length is not 1536.

Example runtime values (keep API keys only in process environment or an untracked `.env`):

```text
KNORA_PROVIDER_MODE=openai-compatible
KNORA_OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
KNORA_OPENAI_EMBEDDING_MODEL=gemini-embedding-001
KNORA_OPENAI_EMBEDDING_CONFIGURATION_ID=embedding-gemini-m1-v1
KNORA_OPENAI_GENERATION_MODEL=gemini-3.1-flash-lite
KNORA_SEMANTIC_SCORER_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
KNORA_SEMANTIC_SCORER_MODEL=gemini-3.1-flash-lite
```

Verify exact model IDs with `GET /models` and probe `POST /embeddings` with `dimensions=1536`
before ingesting. Free-tier rate limits are project/model scoped; pace scorer requests for a full
20-case run so transient throttling is not confused with semantic quality.
