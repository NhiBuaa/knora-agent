# Knora Feature Map

Start with the [agent environment](../runbooks/agent-environment.md) for Launch, Doctor,
Drive, observation and cleanup. This initial map covers the standalone browser surface,
not KittaChat integration. Code/tests are discovery evidence; only an executed application
journey is runtime evidence. Fixture-mode rendering is not a live backend proof.

The layout follows the discover/drive/evidence approach in Lauren Tan's
[P-Stack verification workflow](https://github.com/cursor/plugins/blob/main/pstack/skills/create-verification-skill/SKILL.md).
Runtime observations and limits belong in the implementation PR; refresh them when the
corresponding feature changes rather than treating old screenshots as current acceptance.

Initial live smoke, 2026-10-19: **3 passed, 0 skipped** on a freshly migrated disposable
stack built from `6d1bfca` plus this change. Evidence is the runbook's three named journeys,
their JUnit and per-test JSON/screenshots, not the historical fixture screenshots.

| Area           | Runtime verified in this smoke                                                              | Not established by it                                                     |
| -------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Authentication | Native login, logout, forced sign-in                                                        | Registration, recovery/OTP, refresh/expiry, real SMTP                     |
| Workspace      | UI create/select, UI archive/restore, persisted revisions                                   | Rename, pagination, concurrent conflicts, cross-owner access              |
| Documents      | UI Markdown upload, ready/current projection, archive/restore, deletion-request observation | PDF processing/re-index, search, completed deletion                       |
| Conversations  | Real seeded history navigation, draft/new-hub controls, archived read-only boundary         | UI-persisted creation, submitted/terminal Turns, answer quality/citations |

The synthetic deletion request returned 202 then **blocked** with
`DOCUMENT_DELETION_POLICY_UNAVAILABLE`; that is an observed limitation, not a successful
hard deletion. No worker was started. The separate fresh-agent rerun and exact evidence
locations are reported in the PR; this table is not a full release-profile qualification.

## Authentication

### Sub-features

Native Keycloak sign-in, invalid-credential correction, registration, sign-out, forced
reauthentication, session renewal/expiry and password recovery. Application entrypoints:
`frontend/app/api/auth/{login,callback,session,logout}/route.ts`; native presentation:
`themes/knora/login`; session authority: `frontend/lib/auth/session.ts`.

### How to get to it (user POV)

Open `/api/auth/login`; protected Workspace routes also redirect there. Native login uses
`#kc-form-login`, fields `#username`, `#password` and submit `#kc-login`.
Registration is the `Create account` link. Sign-out is available in the account menu.
Use only synthetic identities from `test/fixtures/keycloak/figma-realm.json` on the
verified disposable stack (`m5-user` for normal journeys; `m5-delete-user` only for the
synthetic document-deletion journey). Never copy a developer's browser cookies or tokens.

### Driving it with Playwright

`frontend/tests/e2e/support/figma-auth.ts` validates ownership before opening login.
The runbook's `live account logout and forced sign-in at 1440` case in
`figma-ui-interactions.spec.ts` checks native login, logout and a fresh authorization
transaction without business writes. `figma-identity.spec.ts` has the broader identity
journeys, including native registration and test-mail password reset.
Success requires the owned Workspace UI/session and correct logout behavior, not just
Keycloak's form or `/api/auth/session` returning 200.

### Gotchas

The isolated Mailpit realm is not daily Gmail SMTP and does not prove production delivery.
OTP/storage-proof profiles have their own guarded setup; they are outside this smoke.
Renewal, real-time expiry, registration, recovery and multi-replica refresh coordination
must not be marked verified from the login/logout smoke. Never retain native auth URLs,
email links or browser state; use the harness's masked screenshots only.

## Workspace

### Sub-features

Create, list/paginate, select/switch, rename, archive and restore private Workspaces.
Selection is a browser hint; backend issuer/subject ownership remains authoritative.
Routes: `frontend/app/workspaces/{page.tsx,archived/page.tsx,[workspaceId]/page.tsx}`;
controls: `frontend/components/workspaces/{WorkspaceManagement,WorkspaceSelector}.tsx`.

### How to get to it (user POV)

After login, open `/workspaces`. Use button/dialog `Create workspace`, field
`Workspace name`, then its `Create workspace` submit. Successful creation navigates to
`/workspaces/<id>/conversations`. `Workspace actions` exposes `Archive workspace`;
the archive dialog confirms it. An archived Workspace displays `Archived workspace ·
Read-only` and `Restore workspace`. The selector is labelled `Switch workspace`.

### Driving it with Playwright

`figma-document-navigation.spec.ts` creates a real Workspace through the UI, checks POST
201 plus selection POST 200 and the resulting route. The existing `owned Workspace
restores from the Conversation bottom bar while an archived Conversation stays archived`
case seeds its conversations through authenticated BFF calls, then drives archive/restore
through the UI and verifies revisions and persisted archive flags. These are partial
journeys, not proof that every seed was created via a user interaction.

### Gotchas

Archiving a Workspace does not unarchive an archived Conversation on restore. Write actions
are hidden in read-only states. Rename, pagination, cross-owner denial and concurrent
revision-conflict handling exist in code/tests but need separate runtime checks; the smoke
does not prove them. Workspace IDs from old artifact JSON do not identify current data.

## Documents

### Sub-features

Upload Markdown/text or PDF, list/search/filter, detail/source projection, archive/restore,
PDF job observation/re-index and asynchronous deletion request. Routes:
`frontend/app/workspaces/[workspaceId]/documents/{page.tsx,[documentId]/page.tsx}`;
controls: `frontend/components/documents/{DocumentList,DocumentDetail}.tsx`.

### How to get to it (user POV)

In an owned Workspace open `/workspaces/<id>/documents`. Click `Upload document`, use
dialog `Upload document` / field `Document file`, then submit. Open the source-name link
for details, `← Documents` to return. Row button `Actions for <source name>` offers
`View details`, `Archive document` or `Restore document`. `Show archived` includes
archived sources. `Search documents` is the search field. `Request deletion` requires
the deletion capability and an explicit confirmation dialog. When re-uploading a file
whose document is currently archived, Knora retains the archived state, displays a clear
notice (`This document already exists and is archived. Restore it to use it again.`), and
provides a direct `Restore document` action to unarchive and re-activate it.

### Driving it with Playwright

Reuse `Documents live navigation preserves owned source and menu lifecycle` in
`figma-document-navigation.spec.ts`. It uploads a unique synthetic Markdown source through
the UI, checks real ingestion/projections (`ready`, `current`, current=served version),
archive/restore response revisions and unchanged source identity, then requests deletion
and observes its pending/blocked projection. Evidence is per-test `evidence/journey.json`
plus screenshots. No database mutation or mocked HTTP response substitutes for that proof.

### Gotchas

Markdown ingestion is synchronous: a null ingestion job is expected. PDF acceptance is
not PDF readiness: this stack starts no extractor/ingestion worker. Search behavior,
large/invalid uploads, PDF parsing/reprocess and completed hard deletion are not verified
by the Markdown journey. A deletion request is not permission to delete retained sources;
this test acts only on its fresh synthetic data, and cleanup removes only its stack.

## Conversations

### Sub-features

Conversation hub/history, new draft, create on question submission, archive/restore,
durable queued Turns, history reconciliation, answer/refusal rendering, per-message
question and answer copy with canonical citation Markdown links, and citation
inspection. Routes: `frontend/app/workspaces/[workspaceId]/conversations/{page.tsx,
[conversationId]/page.tsx}`; controls: `frontend/components/conversations/
{ConversationPanels,ConversationView,TurnCard}.tsx`.

### How to get to it (user POV)

Open `/workspaces/<id>/conversations` or select a retained Conversation. Button
`New Conversation` opens the empty hub; field `Question` and button `Ask` submit.
Each user question provides a dedicated Copy button copying verbatim question text.
Each completed authoritative answer provides a dedicated Copy button converting
validated citation markers `[[E#]]` into markdown links with canonical application
document routes; completed refusal notices copy their displayed refusal text.
Copy buttons remain functional in archived read-only conversations without
triggering mutations. An archived Conversation shows `Archived conversation · Read-only`,
no composer, and `Restore conversation` only when its Workspace is active.
Answer citations open the `Evidence Inspector` complementary panel.

### Driving it with Playwright

The runbook's Workspace-restore case navigates real seeded Conversations, edits an
unsubmitted draft, uses `New Conversation`, archives/restores the Workspace and proves
the archived Conversation stays archived in an authoritative GET. It does **not** submit
a question or complete a Turn. The broader lifecycle test in `figma-ui-interactions.spec.ts`
checks admission/lost-response recovery; controller cases check terminal states.
`figma-conversation-navigation.spec.ts` includes recovery/expiry/history journeys, some
requiring controller-produced artifacts. Read each precondition before selecting it.

### Gotchas

`New Conversation` navigation is not proof of a persisted new Conversation. Without a
Turn worker, admitted Turns remain queued; do not interpret a waiting indicator as an
answer. Completed answers/refusals, semantic quality, citations, interruption recovery,
history pagination and session-expiry draft recovery remain outside this smoke's proof.
Fixture answers and old `live-*-terminal.json` files cannot fill those gaps.
