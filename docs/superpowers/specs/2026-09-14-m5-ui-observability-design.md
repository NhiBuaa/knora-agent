# Milestone 5 UI and Observability Design

**Status:** Design approved by user on 2026-09-14  
**Branch:** `codex/m5-checkpoint`  
**Scope:** M5.1 backend projections/contracts, M5.2 user surface, M5.3 operator surface,
and M5.4 contract/end-to-end verification.

## 1. Goal and guiding boundaries

Milestone 5 exposes the capabilities already built by Knora as a usable and inspectable product
surface. The backend remains the source of truth for domain state, evidence, decisions,
authorization, and observations. The frontend is a consumer of explicit contracts and never a
second domain authority.

M5 is a new architectural surface, not a redesign of ingestion, retrieval, answering, or M4
approval semantics. Existing M1–M4 contracts remain compatible unless this design explicitly adds
an additive public projection or transport contract.

## 2. Chosen architecture

```text
Browser
  │ Keycloak login; httpOnly session cookie
  ▼
Next.js BFF (`frontend/`)
  ├─ /app       user surface
  ├─ /operator  operator surface
  └─ server-side routes forward the Keycloak bearer token
             │
             ▼
FastAPI (`backend/`)
  ├─ validates the Keycloak token
  ├─ creates a WorkspacePrincipal
  ├─ authorizes workspace and capability before resource lookup
  └─ projects domain state into public REST/SSE contracts
```

There is one Next.js application in a sibling `frontend/` directory in this repository. It is
not placed inside `backend/`, and M5 does not create a second operator application.

Keycloak is the concrete OIDC provider. The BFF owns browser session handling and never exposes
Knora credentials to browser JavaScript. FastAPI remains the final authority: it validates the
token, maps it to a `WorkspacePrincipal`, checks the requested workspace, then checks a capability
such as `operator.read` before it reads a resource or begins a side effect.

The M5 implementation must update the Architecture Standard to permit bearer-token Keycloak
authentication on HTTP workspace endpoints. `X-API-Key` remains supported for CLI, legacy, and
non-OIDC integration paths.

## 3. Product and ownership decisions

### 3.1 Chat and history

M5 provides a single-turn question workspace. `POST /v1/questions` remains the canonical
synchronous contract. The user surface may show previous turns held in browser/session state,
but that list is presentation state and is not authoritative persistence.

Knora does not add a durable `Conversation` or `Message` domain in M5. Knora's durable execution
history is `Question Trace`, including question, answer/refusal, citations, evidence and execution
provenance. KittaChat continues to own users, conversations and messages; future cross-system
conversation integration belongs to M6.

### 3.2 Documents

The user surface supports document list/detail, upload, ingestion status, archive and unarchive,
and reprocess where the existing backend contract permits it. Archive is a persisted,
reversible backend state and is not merely a browser filter.

Users may archive and unarchive documents within their authorized Workspace. Operators may create
deletion requests. A deletion request is an asynchronous lifecycle work item: the backend checks
retention/reference eligibility, performs cleanup/reconciliation according to the existing object
lifecycle rules, and exposes states and failures. M5 does not expose immediate hard deletion from
the UI or invent a new deletion policy.

### 3.3 M4 tools

The UI may display proposal, approval, execution, reconciliation, success, failure and
indeterminate observations from the existing M4 projections. It cannot create approval authority,
change a proposal after approval, or execute a write merely because a button was clicked. The
backend M4 workflow remains authoritative.

## 4. M5.1 backend public contracts

M5.1 locks additive public projections and transport contracts before user/operator UI work.

### 4.1 Document and lifecycle projections

The backend exposes Workspace-scoped list/detail projections containing only authorized fields:

- document identity and source key/name;
- archive state;
- current version and serving projection;
- ingestion summary and related job status;
- version/derivation metadata required for user inspection.

Archive/unarchive commands use backend revision or equivalent optimistic concurrency semantics.
Deletion-request submission is idempotent and returns a durable request/work identity plus its
current state. The public state model distinguishes requested, blocked/ineligible, processing,
succeeded and failed outcomes; exact names must remain consistent across REST schema and UI.

### 4.2 Question response and SSE

The existing synchronous question response continues to return the server-resolved answer/refusal,
citations and `trace_id`.

An additive SSE transport emits ordered stage events:

```text
started
retrieving
selecting_evidence
generating
final_validated | refusal | failure
```

Only one terminal event is valid. `final_validated` carries the same server-validated answer and
`CitationProjection` semantics as the synchronous response. `refusal` carries a refusal reason and
trace correlation but no citations. `failure` carries a safe public error classification and is
not converted into an answer or refusal by the client.

The first implementation does not expose raw provider token deltas or a `partial` answer event:
the current
`GenerationProvider` returns a complete structured result, and citation validation happens after
completion. If the connection ends before a terminal event, the client shows an interrupted or
unavailable state and does not claim completion. Any server-side continuation or cancellation
behavior must be explicit in the transport contract.

### 4.3 Citation projection

Citation inspection uses the exact `CitationProjection` returned by the server: evidence alias,
document/version identity, source locator, excerpt, checksum and page/offset metadata when
available. The client never reconstructs a citation by looking up the current/latest document or
by interpreting provider metadata. A refusal never renders as an answer with citations.

### 4.4 Operator read contracts

Operator endpoints expose authorized read projections for:

- exact `QuestionTrace` retrieval and candidate/branch provenance;
- evaluation report, dataset/configuration provenance and failure taxonomy;
- retrieval latency and phase timings;
- token usage and estimated cost, when present and authorized;
- ingestion/object-lifecycle operational snapshots and alerts;
- M4 proposal/execution lifecycle observations where authorized.

Missing trace, metric, configuration or provenance is represented explicitly as unavailable or an
observation failure. Zero is used only when the backend contract says the measured value is zero.
An opaque `trace_id` or proposal ID never grants read access.

### 4.5 Contract generation

FastAPI's OpenAPI document is the single public contract source. The frontend consumes a generated
TypeScript client/types package. Contract-drift checks run in CI/build verification; hand-written
duplicate response shapes are not the source of truth.

## 5. Frontend surface

### 5.1 `/app` user area

The user area provides document management, upload and job progress, archive/unarchive, a question
workspace, session-held turn history, SSE progress states, synchronous fallback, answer/refusal/
failure rendering, citation inspection, and read-only M4 lifecycle display.

Route guards improve navigation but do not replace backend authorization. User-visible loading/
progress, final, refusal, failure and interrupted states are distinct. There is no provisional
answer text in the first implementation; unvalidated text is never styled as a completed cited
answer.

### 5.2 `/operator` operator area

The operator area provides trace/evaluation/operational views using the backend projections. It
requires the operator capability in the backend; the UI must handle an authorization response or
missing observation without fabricating a dashboard value.

Sensitive provider details, raw exceptions, credentials, internal IDs and unapproved diagnostics
are filtered by the backend projection layer before reaching the browser.

## 6. Error, authorization and missing-data semantics

All workspace requests follow this sequence:

1. validate the Keycloak token and establish the principal;
2. authorize the requested Workspace;
3. authorize the capability for the operation;
4. look up the resource and perform the operation.

Unauthorized or cross-Workspace requests return safe errors without revealing whether a resource
exists. The BFF does not downgrade, reinterpret, or retry an authorization failure.

Network disconnects, provider failures, missing trace/metric data, and deletion cleanup failures
remain visible states. No layer infers success from a timestamp, an empty list, stale client state,
or a default value.

Archive/unarchive and deletion requests carry an idempotency/revision contract so browser retries
do not create duplicate logical transitions. Existing M4 idempotency and approval semantics are
consumed unchanged.

## 7. Slice sequencing and ownership

1. **M5.1 backend projections/contracts:** FastAPI schemas/routes, Keycloak validation boundary,
   document/archive/deletion-request projections, SSE event contract, operator read contracts,
   OpenAPI generation and backend contract tests.
2. **M5.2 user surface:** files under `frontend/` for `/app`, BFF calls, document/chat/citation/
   loading/error states and user-facing M4 projection display.
3. **M5.3 operator surface:** files under `frontend/` for `/operator` and any narrowly scoped BFF
   client wiring; it consumes M5.1 projections and requires operator capability.
4. **M5.4 contract and end-to-end verification:** authorization, workspace isolation, missing-data
   behavior, backend ownership, M4 exposure and M1–M4 regression.

M5.2 and M5.3 may run in parallel only after M5.1's public-contract checkpoint passes and their
owned files/tests remain disjoint. M5.4 runs last.

## 8. Verification and acceptance

Backend tests cover token validity/expiry, workspace and capability denial before lookup, projection
field filtering, archive/delete-request lifecycle, SSE ordering and terminal-event rules,
answer/refusal/citation fidelity, rejection of provisional/unvalidated output, OpenAPI drift, and
preservation of the `X-API-Key` path.

Frontend and browser tests cover Keycloak session behavior, BFF forwarding, document lifecycle,
SSE stage/final/refusal/failure/interruption states, citation inspection, operator denial, missing
observations, and M4 lifecycle display without client-side authority.

The release gate includes:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
docker compose config --quiet
git diff --check
```

The M5 acceptance gate requires observable evidence that user document/chat/citation behavior
matches backend state; progress/interruption, refusal and failure are not confused with final
answers; operator
views show only authorized, execution-bound data; unavailable observations remain visible; and no
UI action bypasses workspace authorization, M4 approval, or backend ownership.

## 9. Deferred decisions and non-goals

- Durable Knora conversations/messages are deferred to a later slice or M6 integration design.
- Raw token streaming is deferred until a provider-level streaming contract can preserve structured
  validation and citation safety.
- Hard deletion execution policy is not redefined by M5; the UI submits/observes a backend-owned
  request lifecycle.
- GraphQL, a second operator app, a generic BI/observability platform, and client-side retrieval or
  evaluation are outside M5.
- The concrete Next.js OIDC library and Keycloak realm/bootstrap details are implementation-plan
  choices; they must not change the public ownership or authorization rules above.
