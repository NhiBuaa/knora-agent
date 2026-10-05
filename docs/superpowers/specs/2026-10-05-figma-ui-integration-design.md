# Knora — Figma UI integration design

Date: 2026-10-05. Status: approved by the user in chat on 2026-10-05, together with the
implementation workflow, Tailwind CSS v4 and proposed directory structure.

## Objective and confirmed decisions

Implement the complete selected Figma interface in the existing Knora application, including
interaction, error, permission, archive and identity states.

- User supplied [KnoraAgent UX Exploration](https://www.figma.com/design/BOVOx0bt1qYJFg9nBq6EaQ/KnoraAgent-UX-Exploration?node-id=124-140).
- User explicitly selected six-digit email OTP password reset, implemented as a separate Keycloak slice.
- Earlier milestone gates are accepted by the owner. This records acceptance, not newly executed tests.
- This delivery is a workflow and implementation proposal. Production code has not been changed.
- Repository baseline inspected: branch codex/test, commit 080b33fd5e103ba6aea49683c3b78e96983dfb1d.
  Recheck the actual base and working tree before implementation; preserve subsequent user changes.

## Design source and coverage

The supplied node 124:140 is the Prototype Flows page. All three pages were inspected:

| Page | Coverage |
| --- | --- |
| 01 · Product Screens, 0:1 | 41 final screen variants; design context and screenshots retrieved for all 41 |
| 02 · Interaction & Response States, 4:2 | Five panel layouts, five response cards, panel interaction rules |
| 03 · Prototype Flows, 124:140 | 38 frames and 89 linked transitions |

The [machine-readable inventory](../../design/figma-ui-inventory-2026-10-05.json) records exact
node IDs, names, links, groups, transitions, tokens and asset references. The inventory is a dated
capture; Figma may change. Refresh affected nodes at execution time and record substantive changes.

Scope interpretation: the initial A/B/C visual explorations are reference alternatives. The later
A2–A9, D, W, O and AU screens plus the connected prototype are the implementation target.
The 1440×994 product wrappers include an annotation strip; the application viewport is 1440×960.

| Group | Final variants | Required implementation |
| --- | ---: | --- |
| Conversations | 9 | Empty, question draft, processing, grounded answer, refusal, interrupted, archived, rail variants, selected citation |
| Documents | 6 | State matrix, upload modal, ready/archived detail, deletion confirmation and result |
| Workspaces | 11 | Selector, creation, no active workspace, actions, archive confirmation, archived list/search/empty, read-only, limited permissions, denied |
| Operator | 3 | Operations, trace lookup/detail and evaluation lookup/unavailable |
| Identity | 12 | Sign-in, invalid/unavailable/failed states, account menu, registration/error, reset request/code/error/new password/success |

Prototype-only intermediate states are included: selected upload, processing list, row menus,
question-ready, trace/report lookup, active-workspace landing and new-account landing.
Prototype clicks that simulate successful server responses become real asynchronous operations.
The prototype timeout/click on “thinking” does not authorize fabricated completion or cancellation.

## Existing architecture to retain

- Next.js 15.5.24, React 18.3.1, TypeScript and Tailwind CSS v4, as requested by the user.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Add tailwindcss and @tailwindcss/postcss through F2, locking resolved versions in package-lock.json.
  Use CSS-first theme configuration and semantic utilities for migrated surfaces. Retain custom CSS
  for specialized panel behavior and legacy consumers during migration. Keycloak retains separate CSS.
- Reuse frontend/styles and frontend/components/ui, existing local Inter/Roboto Slab fonts.
- Keep canonical /workspaces and /operator routes; use frontend/lib/navigation/routes.ts.
- Browser requests continue through the BFF. Keycloak owns credentials, reset codes and passwords.
- PostgreSQL/backend own workspace authorization, ingestion lifecycle, serving state, Turn outcome,
  citations, operator observations and tool approval/execution.
- Source-version identity remains distinct from extraction, chunking and embedding configurations.
- Preserve current M4 observations and existing features even where no replacement Figma frame exists.
- Never hand-edit frontend/generated/knora-openapi.ts.

## Proposed module boundaries

The [workflow directory analysis](../plans/2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến)
defines the existing/target trees, file ownership, state owners, import direction and migration order.
Retain the existing feature-grouped components structure; split large views inside their current
feature folders. Route files compose these modules; shared UI does not depend on domain requests.

| Owner | Responsibility | Existing/new files |
| --- | --- | --- |
| Shared UI | Tokens, assets, accessible primitives, top navigation | styles/*; components/ui/*; components/shell/AppShell.tsx and ProductHeader.tsx |
| Workspace surface | Selection, lists, archive/restore and access states | components/workspaces/*; lib/auth/workspace*.ts; workspace routes |
| Conversation surface | Durable Turn interaction and presentation | components/conversations/*; new ConversationPanels.tsx, ConversationRail.tsx, TurnCard.tsx, ConversationComposer.tsx |
| Evidence surface | Turn-bound citation selection and source details | components/citations/CitationViewer.tsx and EvidenceInspector.tsx |
| Document surface | Upload, search/filter, lifecycle detail and confirmation | components/documents/* |
| Operator surface | Read-only operations, provenance and observation availability | components/operator/*; app/operator/* |
| Identity | Keycloak theme, email OTP provider, registration, BFF error surfaces | themes/knora/*; new infra/keycloak/providers/email-otp-reset/*; existing auth routes |

Extract focused components as their owning task changes the existing large view. Do not create a
second API client, generic state framework or duplicate domain service.

## Data and behavior decisions for implementation

### Documents

DocumentResponse already separates ingestion_status, serving_state and embedding_readiness.
The list endpoint currently returns the complete authorized workspace list, so local document
search/filter is valid. Workspace and conversation lists are paginated and need query-aware search.

Proposed additive backend fields:

- served_document_version_id: nullable string; same snapshot as serving_state.
- last_processed_at: nullable timestamp of the latest successful ingestion for the served version.
  Missing history renders “Unavailable”; a failed attempt must not become a successful timestamp.
- answer_availability: available / unavailable / unknown, projected by the backend using the
  active corpus/configuration and archive rules. It describes eligibility for new questions,
  not proof that an answer has cited the document.
- deletion_request: nullable latest request projection, including request_id, state and failure_reason,
  so reloading the detail page preserves the actual outcome.

The Figma “Used in answers” label needs a tooltip explaining eligibility, or the clearer approved
copy “Available for new answers”. The frontend must not infer it from upload success.

Current request_deletion stores blocked / DOCUMENT_DELETION_POLICY_UNAVAILABLE. Keep that truthful
runtime outcome. Implement the requested/blocked/processing/succeeded/failed UI variants, but do
not make a live request appear accepted or a source unavailable merely to match a screenshot.
The Figma requested result is a supported presentation state exercised with an explicit contract
fixture until an approved backend deletion policy can produce it. A working deletion processor,
retention policy or hard purge is a separate domain expansion, not hidden inside this UI rollout.
This is an explicit live-behavior limitation; full live deletion acceptance cannot be claimed.

### Conversations and evidence

- Durable Turn status/stage determines processing and interruption. Only validated backend results
  render as completed answers. Refusal is distinct from system failure.
- Preserve submission Idempotency-Key, uncertain-outcome recovery, polling cleanup and session expiry.
- Citation selection is scoped by workspace + conversation + Turn + citation identity. Display aliases
  such as [01] must resolve to that Turn's original evidence; never current mutable document content.
- Evidence inspector displays authorized excerpt, source/version/checksum and physical page or lines.
  “Open document” uses the existing authorized document detail route.
- “2 documents checked” is not derivable from the number of citations. Until an authoritative user
  projection exists, use “Available evidence reviewed” without a fabricated count.
- Suggestions fill the composer; sending remains explicit. Example answer text and filenames are fixtures.
- Preserve rename/archive/restore and pagination. No new stop-generation endpoint is implied.

### Workspaces and access

- Selection remains an issuer/subject-bound preference, validated by backend ownership.
- Add optional q to workspace/conversation list contracts, applying filtering before pagination.
  Query/cursor/filter combinations must remain consistent; no “no results” after only checking page one.
- Missing/denied workspace, empty workspace and archived workspace are separate surfaces.
- Archived/read-only/capability-limited buttons reflect backend permissions; hidden buttons provide
  no authorization guarantee by themselves.

### Operator

- Zero is a valid metric value. Missing metric is unavailable.
- Preserve trace provenance, validation result, refusal, accounting/timing when supplied.
- Evaluation unavailable is a designed state matching the current contract. No invented score/report.
- Keep existing tool lifecycle observations reachable and styled consistently.
- Authorization must happen before identifier lookup on every operator route and BFF handler.

### Identity and OTP

User-approved flow: email request → six-digit code → new password → reset success/sign-in.
Registration and its validation screen are in scope. Keycloak 26.3.3 remains the pinned target.

Proposed implementation uses a Keycloak Authenticator/AuthenticatorFactory for email request,
verification and resend, then native Reset Password / UPDATE_PASSWORD. Preserve enrolled MFA;
do not treat email reset OTP as an authenticator enrollment or remove an existing OTP credential.
Enable registration/reset only in the intended realm through an idempotent configuration change.
No destructive realm import, real-user password reset or live SMTP secret change during UI work.

Proposed limits, subject to plan acceptance: six numeric digits; five-minute expiry; five failed
attempts per challenge; 30-second resend cooldown shown in Figma; invalidate the previous code on
resend; one successful consume. Enforce server-side, including cross-node concurrent requests.
Respond uniformly for unknown/disabled accounts and avoid account enumeration or OTP logging.

Reset completion must not accidentally reuse an existing SSO session. The preferred small BFF
extension permits only a fixed prompt=login option and creates a fresh state/nonce/PKCE transaction.
Arbitrary prompt/redirect parameters are not forwarded. Normal sign-in stays unchanged.
Detailed primary-source findings and deployment/test seams are in the research companion.

## Visual and interaction contract

- Use the inventory's Figma tokens and exact leaf/ornament assets. Export original assets locally;
  screenshots are review evidence, never production UI backgrounds.
- Reconcile Figma muted text #657a74 with existing #546b63 using measured contrast. Preserve
  accessible semantic foreground/focus/status tokens; record any necessary visual exception.
- Desktop navigation is 64px high. Documents/Operator use the observed centered 1200px content area.
- Conversation rail supports expanded/collapsed/hidden; inspector supports open/closed.
  Dividers support drag, keyboard resizing and double-click reset; clamp widths to available space.
- Remember panel preferences per browser session and identity/workspace scope; clear on sign-out.
  Do not store source excerpts, credentials or tokens in panel preferences.
- Citation click opens/focuses inspector. Composer remains anchored to the conversation column.
- Dialogs/menus have focus handling, Escape, labels and focus return; status changes use suitable
  live regions. Reduced motion is respected.
- Proposed responsive policy: desktop split panels; tablet/narrow screens use rail drawer and
  evidence sheet with one active overlay. Preserve composer access and avoid page-level overflow.
- Verify at 1440×960, 1024×768, 768×1024 and 390×844. Only the first is a supplied Figma target.
  Preserve existing dark theme compatibility; no exact dark-mode design is claimed.

## Acceptance and exclusions

Acceptance requires every inventory screen/state mapped to a component and test or visual evidence,
all applicable prototype transitions exercised, live backend flows checked, accessible keyboard use,
fresh formatting/type/build/test evidence and independent review.

Known limitations must stay visible: deletion policy unavailable, evaluation report unavailable,
missing authoritative evidence counts, and responsive/dark adaptations beyond supplied frames.
No automatic merge, push, deployment, new skill installation or branch deletion is authorized by
this planning request. The prior owner gate acceptance does not replace verification of new code.
