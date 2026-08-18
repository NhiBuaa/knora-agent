## R1 revision v2 — authority identity provenance

This append-only ticket revision supersedes the scope clarification in
`.agents/tickets/m3-remediation-r1.md` and is governed by `docs/design/m3-remediation-v3.md`.

### Additional locked invariants

- The external-review artifact must carry `reviewer_id`, `identity_kind`, `source_record`,
  `identity_digest`, reviewed subject commit/blob, complete-scope digest, `verdict`,
  `reviewer_was_author`, `reviewer_was_approver`, response digest, seal and closure.
- `reviewer_id` must be a concrete execution-task identity; generic placeholders and
  payload-only independence assertions are invalid.
- Production derives the source-commit author from Git and compares it with reviewer and
  approver identities. Missing or self-authored/self-approved evidence returns
  `AUTHORITY_VALIDATION_FAILURE` before policy evaluation.
- The approved JSON projection is the sole normative value source; Python may validate schema
  and types but may not duplicate policy values.

### Acceptance additions

- Mutate each identity provenance field, source commit/blob and review scope; every mutation
  fails closed.
- Verify the sealed review response and closure digest against the exact subject commit and
  complete package scope.
- Prove the historical generic/self-attested chain is rejected and the new concrete chain passes.
