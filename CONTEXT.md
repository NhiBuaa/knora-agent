# Knora Knowledge Agent

Knora is an independent AI support and knowledge service. It turns workspace-scoped source
documents into evidence that can support cited answers and, in later milestones, controlled tool
proposals.

## Current Model

### Knowledge ownership

- A **Workspace** is the tenant boundary for every document, chunk, retrieval operation, trace,
  and evaluation.
- A **Document** is a source artifact owned by one Workspace.
- A **Chunk** is a versioned retrieval unit derived from one Document; its citation identity
  remains traceable to that source.
- An **Evidence Set** is the ordered collection of retrieved Chunks supplied to answer generation.

### Question answering

- A **Question Request** asks Knora to answer within one Workspace.
- A **Cited Answer** is generated from an Evidence Set and exposes citations to its source Chunks.
- A **Refusal** is the valid response when the Evidence Set cannot support an answer.
- A **Question Trace** records retrieval and generation observations used for debugging and
  evaluation; it is not conversation state.

### System relationships

- **Ingestion → Retrieval**: ingestion creates versioned Chunks and embeddings; retrieval selects
  an Evidence Set within the same Workspace.
- **Retrieval → Generation**: generation receives evidence through an application contract and
  does not own storage queries.
- **Knora → Provider**: provider adapters supply embeddings or generated text; domain behavior is
  not owned by a particular provider.
- **KittaChat → Knora**: KittaChat may send normalized requests and receive bot responses through
  explicit service contracts; it never shares its database with Knora.
- **Evaluation → Knora**: version-controlled cases exercise public seams and measure retrieval,
  citation, refusal, latency, and cost behavior.

## Context Pointers

- Normative rules: [Architecture Standard](docs/standards/architecture.md)
- Product direction: [Project Overview](docs/PROJECT_OVERVIEW.md)
- Approved slice: [Milestone 1 — Cited RAG](docs/specs/milestone-1-cited-rag.md)

