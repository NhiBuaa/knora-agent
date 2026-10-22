# A2 checkpoint — manual PDF gold review

## Implemented

- Basic Operator form authors/edits ANSWER and scoped REFUSAL cases without JSONL. It displays
  references, required facts, AND/OR evidence, context dependencies, original PDFs and source identity.
  Advanced cases remain view/review only; the basic editor cannot silently flatten them.
- Case review requires `evaluations:approve`, source-read access and a human note. Issuer/subject
  come from authenticated server identity, not browser fields. Reviews bind exact case digests.
- Freeze previews the canonical gold digest, requires that exact digest/revision, and stores an
  immutable version with owner approval. Reopening creates a new draft and preserves old versions.
  Rejected cases stay visible in the draft and do not enter gold. Editing cases or adding sources
  invalidates prior reviews. Freeze does not require successful extraction or runtime binding.
- Source/checksum/snapshot/offset validation, retained-source protection and the existing catalog
  remain in use. The frozen catalog population contains accepted gold only; a reopened draft never
  advertises its old digest as the identity of edited cases.
- Added bounded BFF routes, capability-aware UI, no-store responses and generated OpenAPI.
  The coordinator's unpublished/unapplied 0049 migration contains the new fields/version table.

## Evidence

- Python 3.13 focused backend: **76 passed** (evaluation domain/HTTP and dataset persistence).
- Frontend Operator/Runs: **114 passed**; frontend typecheck and formatting passed.
- Ruff format/check, OpenAPI check, Compose config and `git diff --check` passed.
- Independent A2 review found an offset-clipping edge; a failing regression reproduced it, the
  validation was fixed, and that test passed. Final reviewer reported no remaining findings.
- Python 3.12 focused backend: **76 passed**, using the existing evaluation interpreter without
  modifying it. Full Python collection in the primary environment failed because optional
  DeepEval/Ragas are absent; the broader 3.12 run has no retained terminal result and is not a pass.
- Full frontend: 507 passed, one route-render test skipped after its build setup exceeded its
  90-second hook timeout. Standalone `npm --prefix frontend run build` passed (existing image
  optimization warnings in ConversationComposer).

## Boundaries and remaining acceptance

No model calls, runtime/database migrations, shared-service changes, export, enforcement or merge
were performed. PostgreSQL locking and live-browser owner acceptance remain unverified here.
An upload crossing the freeze boundary can leave a staged object in the established ObjectStore/DB
transaction gap; ADR 0006's existing orphan reconciliation and diagnostic retention still apply.
R3 must consume this canonical artifact directly and demonstrate new Q&A/report independently of
DeepEval/Ragas. The MVP remains in progress.

## Security coordination

Minimal boundary published and read back in
[#188 discussion](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6187911953):
native saved captures or retained source/snapshot artifacts in, separate local shadow report out.
Preserve every observation status and native identity. No canonical schema or shared dependency
change is required; discuss concrete shared diffs before editing. Workbench does not wait for #188.
