## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the read-only `ticket_lookup` capability end to end. A Workspace-authorized caller can use
the static typed capability only after Knora authenticates the caller, authorizes the path Workspace,
resolves the exact Workspace-to-external-scope binding, verifies the approved `m4r1` resource
reference and authorizes that resource. Unauthorized or cross-Workspace requests fail before the
external provider is invoked.

The slice establishes the typed `SupportToolGateway` read boundary and deterministic SQLite
reference-provider contract needed by later execution work. It does not add a plugin framework or
allow read/reconciliation authority to imply write authority.

## Acceptance criteria

- [ ] `ticket_lookup` is exposed through a static, typed, versioned and allowlisted capability
  registry; no dynamic discovery or plugin loading is introduced.
- [ ] `ReadTool.execute(ReadToolCommand, WorkspacePrincipal)` accepts an opaque
  `ticket_reference` and returns only the approved `TicketLookupResult` fields: opaque reference,
  title, status and summary.
- [ ] Authentication and path-Workspace equality are checked before any scoped resource lookup.
- [ ] `ExternalResourceReference` uses the single approved `m4r1.<payload>.<HMAC-SHA256>` envelope
  plus trusted reference store. Verification covers canonical protected bytes, key version and
  active/retiring/revoked state, expiry, Workspace, capability/version, binding claims and matching
  stored claims before revealing a provider resource identity.
- [ ] Current `WorkspaceResourceAuthorizer` authorization completes after reference verification and
  before `SupportToolGateway.lookup_ticket` receives an `AuthorizedExternalResource`.
- [ ] Unauthorized, cross-Workspace, missing-binding, malformed/tampered/expired/unknown-key/
  revoked-key reference, missing trusted-store record and scope-mismatch cases fail closed with zero
  gateway invocation and no resource-existence leakage.
- [ ] `SupportToolGateway.lookup_ticket(LookupTicketRequest(scope, resource))` is typed and never
  exposes provider SDK objects, raw provider IDs or persistence records to application callers.
- [ ] An authorized absent ticket returns the safe authorized not-found result; provider scope denial,
  unavailability and contract-invalid responses retain distinct typed outcomes and public mappings.
- [ ] The Workspace-scoped HTTP route
  `POST /v1/workspaces/{workspace_id}/tools/ticket-lookup` authenticates first, forbids extra request
  fields and maps authentication/authorization/malformed-reference/schema/authorized-not-found and
  provider-contract outcomes according to the approved design.
- [ ] Deterministic fake-gateway tests assert pre-invocation authorization and zero calls on every
  denial. SQLite reference-provider contract tests prove scoped lookup, restart persistence and
  defense-in-depth without sharing state with `ToolActionStore`.
- [ ] No write capability, provider write or approval/execution authority is granted by this read
  slice.
- [ ] Existing M1–M3 authorization, retrieval, citation/refusal and regression behavior remains
  green.

## Blocked by

None — can start immediately and remains parallel with #76.
