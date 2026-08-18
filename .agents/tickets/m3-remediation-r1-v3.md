## R1 revision v3 — executable reviewer identity proof

This append-only ticket revision is governed by `docs/design/m3-remediation-v4.md` and
supersedes R1 v2. The reviewer artifact must bind the committed identity record
`.agents/review/identities/codex-agent-m3-remediation-external-review-v2.json`, its Git blob,
raw SHA-256 and the canonical `identity_digest`. `scope_digest` and `response_sha256` use the
exact canonical serialization defined in design v4. Production derives the source-commit author
from Git and rejects generic, assertion-only, self-authored or self-approved chains before policy.

The approved JSON policy projection remains the sole normative value source; Python only validates
schema/types and bound content.
