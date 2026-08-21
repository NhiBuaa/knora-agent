## Objective

Remediate the M3 improvement-claim authority so production accepts only a verifiable,
independent authority chain and reads the approved JSON projection as its sole normative source.

Authoritative design: `docs/design/m3-remediation-v4.md`.
Locked guide: `.agents/manual-tests/milestone-3/68-remediation-authority-v3.md`.
Current append-only R1 revision: `.agents/tickets/m3-remediation-r1-v4.md`.

## Acceptance

- Historical generic/self-attested chain is rejected.
- Committed reviewer identity record, canonical identity/scope/response digests, exact subject
  commit/blob, source-author projection, reviewer/approver separation, seal and closure validate.
- Generic, missing, assertion-only, self-authored/self-approved, mutated or caller-overridden
  authority fails closed before policy.
- Approved JSON policy projection is the sole normative value source; production contains no
  duplicated full value-level policy map.
- Focused tests, lint/diff and artifact hygiene pass; raw traces/secrets are not committed.

## Dependency

Child of #48. Independent frontier ticket; #67 is natively blocked by #68.
