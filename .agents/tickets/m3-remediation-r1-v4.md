## R1 revision v4 — final reviewer identity binding

This append-only ticket revision is governed by `docs/design/m3-remediation-v4.md` and
supersedes R1 v3. The active authority chain must bind the concrete reviewer identity record
`.agents/review/identities/codex-agent-m3-final-package-review-v4.json`, its Git blob/raw SHA-256
and canonical `identity_digest`, together with the active scope/response projections and
`.agents/review/m3-remediation-v4-review-closure-final.json`. The historical R1 v3 reviewer
identity remains preserved and is not an active authority input.

The production validator derives the source-commit author from Git and rejects generic,
assertion-only, self-authored or self-approved chains before policy. The approved JSON policy
projection remains the sole normative value source; Python validates only its schema, types and
bound content. `scope_digest` and response digests use the exact canonical serialization defined
in design v4.
