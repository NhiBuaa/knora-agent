# Architecture Standard

These rules are normative for Knora unless superseded by an approved Standard or ADR.

## Ownership and boundaries

- Knora owns Workspaces, Documents, Chunks, embeddings, Question Traces and evaluations.
- KittaChat owns users, conversations and messages.
- Knora must not access KittaChat's database directly. Integration uses authenticated API or event
  contracts.
- Agent failure must not break KittaChat's ordinary message delivery.

## Evidence and tenant safety

- Every ingestion and retrieval operation must be scoped to exactly one Workspace.
- A Cited Answer may cite only Chunks present in the Evidence Set used for that answer.
- When evidence cannot support an answer, the system returns a Refusal and must not fabricate a
  citation.
- Documents, Chunks and evaluation data must not contain production secrets in version control.

## Provider and configuration boundaries

- Application and domain behavior must depend on provider contracts rather than a specific LLM or
  embedding vendor.
- Prompt, model, chunking and retrieval configurations must be versioned when they can affect an
  evaluation result.
- Provider credentials enter through runtime configuration and must never be committed.

## Tool actions

- Tools are classified as read-only or write/destructive.
- Write or destructive actions require explicit human approval by default.
- Tool input must be schema-validated; side effects require an idempotency key and audit trail.
- An agent cannot infer access rights that were not supplied by the authenticated caller.

## Verification

- Public behavior is tested through approved HTTP, application and evaluation seams.
- Metrics claimed in portfolio material must name the dataset size and measurement method.
- Multi-agent orchestration requires evaluation evidence that its quality or maintainability gain
  justifies added latency and cost.

