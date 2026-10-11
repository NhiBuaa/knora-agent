# Figma Document navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development for implementation and independent review.

**Goal:** Exercise actual Documents row/menu/detail navigation and menu lifecycle actions, retaining the archived filter when returning from Archived detail.

**Architecture:** A focused application E2E specification uses existing native login, isolated runtime and real Documents modules. Backend projections supply identities, lifecycle and source provenance. An archived detail back link requests the existing local archived filter; DocumentList consumes that explicit URL preference without granting capability or changing the API.

**Tech Stack:** Next.js, TypeScript, Tailwind CSS v4, Playwright, Keycloak, PostgreSQL.

**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md); Documents edges in [dated inventory](../../design/figma-ui-inventory-2026-10-05.json) and [coverage ledger](../../development/figma-ui-visual-coverage.md).

## Global Constraints

- Canonical `/workspaces` and `/operator` routes; no generated OpenAPI edits or production API changes.
- Preserve backend authority and truthful state. A Ready-only list does not prove the processing source of edge7.
- Use owned isolated `knora-figma-e2e` runtime through `openFigmaLogin`; no environment overrides.
- Synthetic data may be created and archived/restored through the existing authorized application; retain it after testing. No deletion submission, cleanup, worker, outage or credential configuration changes.
- Every maintained frontend change requires format followed by format:check; run typecheck sequentially.
- Preserve historical captures. This task writes only `.verification/figma/q1/evidence/document-navigation-2026-10-08/`.
- Execution follows Upload trigger independent approval, with a fresh clean tracked BASE. One implementer, no children.

## File structure and interfaces

Create `frontend/tests/e2e/figma-document-navigation.spec.ts`: owns this cohesive live journey and test-local assertion helpers. Consume `openFigmaLogin`, `captureIdentity`, checked-in synthetic realm identity, and generated `DocumentResponse`/`WorkspaceResponse` types. Avoid enlarging the existing interaction specification.

Modify `frontend/playwright.figma.config.ts`: include the new specification only in application testMatch. Default native and fixture selections remain intact.

Modify `frontend/tests/e2e/support/figma-environment.test.ts`: update the existing application selection assertion to include the new specification and retain the native/fixture/special-selection assertions.

Modify `frontend/components/documents/DocumentDetail.tsx`: archived Document's actual back link includes `?archived=true`; non-archived detail retains the existing URL. Modify `frontend/components/documents/DocumentList.tsx`: initialize its existing local filter from that exact preference through existing Next searchParams API. No source state or permission is inferred from the query.

Modify `frontend/tests/document-figma-states.test.tsx`: extend its existing Next navigation mock with searchParams and a focused archived-return test. Query defaults are empty for all pre-existing cases.

Modify `docs/development/figma-ui-visual-coverage.md` and `docs/development/figma-ui-implementation-record.md`: record edge-specific results, source/destination IDs, actual backend statuses and retained limitations. Eight maintained files total, plus this preparation plan.

## Task 1: Prove live row, menu and back navigation

**Create:** `frontend/tests/e2e/figma-document-navigation.spec.ts`.
**Modify exactly:** the config, existing environment test, existing document-figma-states test, DocumentList, DocumentDetail and two development documents named above.

**Consumes:** `openFigmaLogin(page)`, `captureIdentity(page,path)`, realm `m5-delete-user`, native authenticated BFF and current Documents links/actions.
**Produces:** named live journey `Documents live navigation preserves owned source and menu lifecycle`, scoped captures and JSON observation, explicit edge classifications.

- [ ] Read the existing live Documents setup in `figma-ui-interactions.spec.ts`, navigation owner callsites, generated response shape and source ledger. Use systematic-debugging and TDD for the known filter-reset gap. DocumentList currently initializes false and DocumentDetail's back link omits the filter; edge21 requires the archived-list destination. Only that owner correction is authorized; diagnose/escalate unrelated failures.
- [ ] Configure application selection to include both current interactions and new specification. Preserve special `m5-refusal`, native and fixture selection behavior. Use the existing environment guard; no new runtime.

```ts
testMatch: mode === "fixture"
  ? ["figma-ui-visual.spec.ts", "figma-ui-interactions.spec.ts"]
  : mode === "application"
    ? ["figma-ui-interactions.spec.ts", "figma-document-navigation.spec.ts"]
    : "figma-identity.spec.ts";
```

- [ ] Create one desktop1440×960 live test, timeout120000. Login with checked-in owned identity via native form. Create a unique Workspace through the real Create workspace dialog; assert POST201, selection200 and matching destination ID. Use the current UI Upload dialog to submit one unique Markdown file containing harmless synthetic evidence. Assert accepted successful upload and nonempty Idempotency-Key; read the authenticated Documents projection to locate its exact source_name/document_id/workspace_id. Do not infer Ready from upload success: assert returned archived=false, ingestion_job_id=null and ingestion_status=null for the synchronous Markdown path, embedding_readiness=ready, serving_state=current and returned source/served version identities. This correction follows the observed persisted projection; it does not characterize asynchronous PDF ingestion.
- [ ] Define local `observeDocument(expectedArchived)` helper: authenticated GET200 exact scoped path, exact source_name and IDs, expected archived state; record revision, current/served version, serving/availability and deletion projection. Define `expectDetail(expectedArchived)` to assert exact URL, named heading and Archive/Restore button reflecting that same projection. Compare provenance before/after lifecycle to ensure archive changes lifecycle without replacing source identity.

```ts
const response = await page.request.get(`/api/v1/workspaces/${workspaceId}/documents/${documentId}`);
expect(response.status()).toBe(200);
const observed = await response.json() as DocumentResponse;
expect(observed.document_id).toBe(documentId);
expect(observed.workspace_id).toBe(workspaceId);
expect(observed.source_name).toBe(sourceName);
expect(observed.archived).toBe(expectedArchived);
```

- [ ] With Show archived unchecked, click the actual exact filename link, assert Ready detail and source observation; click actual `← Documents`, assert exact list URL, same source row and unchecked filter. This exercises a Ready-only list path/back; retain edge7's processing-source limitation.
- [ ] Check Show archived, verify actual checked input, click the same row again and assert exact destination/source. This covers edge10. Return via actual back link; verify same row and Ready detail's default unchecked destination. Check Show archived again before subsequent menus. Open its real Actions trigger, assert Ready source/menu entries, click View details, then assert exact URL/heading/source for edge15 and return by edge18. Re-check Show archived before the next action because Ready back intentionally targets the normal list.
- [ ] Open Ready menu and invoke Archive document. Capture the matching scoped POST and assert status200 with If-Match equal to observed revision. Read back archived=true with revision advanced and unchanged source version identity. Assert actual list remains the destination and the archived row is visible with Show archived checked; record this difference from edge16's illustrated direct detail destination. Click the actual archived filename link and assert Archived detail/source for edge12; actual back link must prove edge21 to list with `?archived=true`, checked Show archived and the same archived source row retained. Run this live journey before the owner fix and record the expected RED at this assertion, preserving created synthetic data and diagnostic capture.
- [ ] After RED, apply the minimal owner correction and rerun with fresh unique owned data. Exact query preference initializes only the local boolean. Existing checkbox remains a local filter; no backend scope/mutation, navigation to another Workspace or shared navigation helper change. Preserve unrelated query handling. Ready back remains the bare canonical list URL.

```ts
// DocumentList, using the already installed Next hook:
const searchParams = useSearchParams();
const [showArchived, setShowArchived] = useState(
  () => searchParams?.get("archived") === "true",
);
// DocumentDetail's existing back Link:
href={`${routes.documents(workspaceId)}${document?.archived ? "?archived=true" : ""}`}
```
- [ ] Open archived menu, assert Restore document present and Reprocess absent. Click View details and prove exact Archived destination/source for edge25; return through real back link. Reopen menu, invoke Restore document; assert exact unarchive POST200/If-Match, read back archived=false/revision advanced/source identity unchanged and verify restored row plus actual list URL. Record edge27's actual list outcome separately from illustrated direct detail. Click restored row and verify Ready detail; return to list.
- [ ] Open/close Ready and Archived menus using their actual trigger click during the corresponding states, proving exact toggle sources for edges14/24 in addition to prior Escape evidence. No request-deletion confirmation or reprocess action.
- [ ] Capture Ready detail, Ready menu, Archived detail, Archived menu and final restored list, waiting for loaded local fonts/images. Inspect relevant desktop images. Write `journey.json` containing edge evidence, scoped routes/IDs, statuses/revisions/source projections, actual destinations and limitations. Never write credentials/tokens/cookies/action URLs or substitute API bodies. Preserve all data; no cleanup.
- [ ] Run only this named live journey from frontend with `$env:FIGMA_TEST_MODE='application'; npm exec playwright test -- --config=playwright.figma.config.ts --grep 'Documents live navigation preserves owned source and menu lifecycle'`. Remove the task-local selection environment afterward. Inspect command exit and output. Avoid rerunning existing broader lifecycle test because it overwrites historical evidence.
- [ ] Extend the existing hoisted navigation mock in `document-figma-states.test.tsx` with `search: ""`, return `new URLSearchParams(navigation.search)` from `useSearchParams` and reset search in beforeEach. Add a focused test starting with `archived=true`, a real archived Document projection and authorized GET list fixture: checked filter displays its filename on initial render; uncheck hides it. Add assertions to the existing detail rendering cases for archived back URL versus normal Ready back URL. The optional query access handles absent search context in current non-router component tests. Keep all pre-existing assertions.
- [ ] Run existing `tests/e2e/support/figma-environment.test.ts` focused Vitest selection; update its application selection expectation using `toEqual` for the exact two-element array. Preserve all environment guards and existing native/fixture/special-selection assertions. Run `document-figma-states.test.tsx` and `documents-management.test.tsx` focused regressions; no new shared setup/mock changes. Run sequential `npm --prefix frontend run format`, `format:check`, `typecheck`, `git diff --check`. If test/config code changes after the covering run, run the affected journey again.
- [ ] Update only observed edge rows and the two documentation records. Claim no processing-source proof, deletion, native OTP, full-frame parity or full regression. Self-review scoped diff; commit exactly eight maintained files and write full task report with RED/GREEN commands/exits/captures and all limitations. Controller performs independent Spec and Quality review.
