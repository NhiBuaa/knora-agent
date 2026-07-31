# Knora Knowledge Agent

Knora is an independent AI support and knowledge service. It turns workspace-scoped source
documents into evidence that can support cited answers and, in later milestones, controlled tool
proposals.

## Current Model

### Knowledge ownership

- A **Workspace** is the tenant boundary for every document, chunk, retrieval operation, trace,
  and evaluation.
- A **Document** is the stable identity of a logical source, uniquely named by `source_key` inside
  one Workspace. Equal content under different source keys remains different Documents. Its
  nullable active pointer selects the Embedding Set currently visible to retrieval.
- A **Document Version** is immutable normalized content identified within a Document by its
  content checksum.
- A **Chunking Configuration** is an immutable parser, chunker and tokenizer configuration.
- A **Chunk Set** is one derivation of a Document Version under one Chunking Configuration.
- A **Chunk** is an ordered retrieval unit inside one Chunk Set and records enough source position
  metadata for its citation to be verified.
- An **Embedding Set** is the vectorization of one Chunk Set under exactly one Embedding
  Configuration.
- A completed Embedding Set may become a Document's **Active Embedding Set**; inactive historical
  sets remain immutable for traceability and are excluded from retrieval.
- An **Evidence Set** is the ordered collection of retrieved Chunks supplied to answer generation.
- An **Evidence Alias** is a request-scoped opaque identifier such as `E1`; application code owns
  its mapping to one Chunk and providers never receive database Chunk IDs.
- A **Retrieval Configuration** is an immutable definition of candidate count, similarity
  threshold, evidence count, token budget and overlap-redundancy policy.
- A **Retrieval Candidate Decision** records a candidate's raw score and whether it was selected or
  excluded by threshold, redundancy or token budget.

### Ingestion

- **Ingest Document** is the single application use case shared by HTTP and CLI entrypoints.
- An **Ingestion Outcome** is `created` when any requested derivation is newly persisted and
  `reused` when the complete requested derivation chain already exists.
- **Activation Changed** reports whether ingestion changed the Document's active pointer,
  independently of whether the derivation chain was created or reused.

### Access boundary

- A **Workspace Principal** is an authenticated application identity authorized for exactly one
  Workspace in Milestone 1.
- An **API Credential** is a rotatable key record identified by safe `key_id`; multiple credentials
  may authorize the same Workspace, but one credential never spans Workspaces.

### Question answering

- A **Question Request** asks Knora to answer within one Workspace.
- A **Cited Answer** is generated from an Evidence Set and exposes citations to its source Chunks.
- A **Structured Generation Result** is either an answer whose inline Evidence Alias markers are
  validated or a structured refusal with reason `INSUFFICIENT_EVIDENCE`.
- A **Citation Projection** is server-resolved metadata pinned to one Document Version and exposed
  for each Evidence Alias used in the answer.
- A **Refusal** is the valid application response when retrieval finds no qualified evidence or a
  valid Structured Generation Result reports insufficient evidence.
- A **Question Trace** records retrieval and generation observations used for debugging and
  evaluation, including every Retrieval Candidate Decision; it is not conversation state.
- An **Evaluation Case** is a versioned question fixture with expected behavior, acceptable source
  documents/chunks and required facts when applicable.
- An **Evaluation Report** separates structural pipeline checks, retrieval metrics, generation
  semantic metrics and system metrics with versioned dataset/configuration/scorer provenance.

### Provider boundaries

- A **Generation Provider** turns a Question and its Evidence Set into generated answer text.
- An **Embedding Provider** turns text into vectors used by ingestion and retrieval.
- An **Embedding Configuration** is an immutable embedding-space identity comprising provider,
  model, dimensions and distance metric.
- A **Deterministic Local Provider** exercises orchestration, schemas, citation/refusal behavior
  and trace persistence without representing semantic quality.
- An **OpenAI-compatible Provider** supplies model-backed generation or embeddings for demos and
  semantic evaluation when enabled by runtime configuration.

### System relationships

- **Document Version → Chunk Set → Embedding Set**: content history, chunk derivation and vector
  derivation have separate immutable identities; re-chunking or re-embedding does not create a new
  Document Version.
- **Ingestion → Retrieval**: ingestion creates or reuses the versioning chain; retrieval selects an
  Evidence Set only from the Active Embedding Sets resolved for that request and Workspace.
- **Ingestion → Document activation**: a compare-and-swap on Document revision activates a
  completed Embedding Set atomically with chain persistence; a stale ingestion cannot overwrite a
  newer activation.
- **HTTP/CLI → Ingest Document**: entrypoints perform transport concerns and delegate all
  ingestion validation and orchestration to the same application use case.
- **Credential → Workspace Principal → Resource**: HTTP authenticates a key and authorizes its
  Workspace before any resource lookup; CLI constructs an explicit principal and uses the same
  authorization policy.
- **Retrieval → Generation**: generation receives evidence through an application contract and
  does not own storage queries; application code supplies request-scoped Evidence Aliases and
  validates the returned markers before resolving citation metadata.
- **Knora → Generation Provider**: application code supplies a Question and Evidence Set through
  the minimal generation contract; domain behavior is not owned by a model vendor.
- **Ingestion → Embedding Provider**: ingestion requests vectors through the minimal embedding
  contract, validates their dimensions and associates the resulting Embedding Set with the
  immutable Embedding Configuration.
- **KittaChat → Knora**: KittaChat may send normalized requests and receive bot responses through
  explicit service contracts; it never shares its database with Knora.
- **Evaluation → Knora**: version-controlled cases exercise public seams and measure retrieval,
  citation, refusal, latency, and cost behavior.
- **Question Trace → Client**: an opaque, workspace-authorized `trace_id` permits debugging without
  granting general trace access.
- **Question Request flow**: retrieve → complete generation → validate structured output and
  citation markers → resolve Citation Projection → persist Question Trace → return response.

## Context Pointers

- Normative rules: [Architecture Standard](docs/standards/architecture.md)
- Product direction: [Project Overview](docs/PROJECT_OVERVIEW.md)
- Approved slice: [Milestone 1 — Cited RAG](docs/specs/milestone-1-cited-rag.md)
