# External review packet: Issue #79 M4.5 remediation guide v6 correction-2

## Binding

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Remediation slice: GitHub Issue #79
- Reviewed integration head: `2e66060b9ca7628acddf3b5d9a87d0c75fa92654`
- Fixed-point descriptor: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-fixed-point-v3.json`
- Fixed-point SHA-256: `84f5d90fdb52553e15990fdfefa5f229fda00d56d355a744c30b5c5a15a1852e`
- Spec-axis review: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-spec-v3.json`
- Spec-axis review SHA-256: `74cf3a30c6e5e0fdee355032006b64247566372074d6a1f13e5fb2141ee8997a`
- Prior approved guide: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v5.md`
- New guide: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v6-correction-1.md`
- New guide SHA-256: `d50cc24a725d0fb117919a8f988512465a6345a5517476888b0398ac71ac5c84`
- New structured test cases: `.agents/review/m4-issue-79-test-cases-v6.json`
- Test-case SHA-256: `00bf66123972c9fd1ac97aeaf8cabdbbb785a775a834de2dfc10790a0be87209`

## Requested guide review

The integrated fixed point has four new Major specification findings. Review whether v6 closes
these exact gaps without widening Issue #79 and without weakening the 13 inherited v5 cases:

1. PostgreSQL terminal/observation constraints must persist the closed provider request-rejected,
   scope-denied and reconciled request-rejected outcomes and retain their exact public mappings.
2. PostgreSQL lease/CAS/fencing transitions must use one captured `transaction_timestamp()` per
   transaction, not moving `clock_timestamp()` values.
3. `ToolProposalProjection` and every execution/reconciliation result must carry a sanitized,
   durable execution projection that excludes provider/routing/secret/internal material.
4. Audit and sanitized execution projections must retain only a validated safe `failure_code` for
   closed terminal outcomes while excluding private `rejection_code` and raw provider data.

The guide adds M4-79-TC-14 through M4-79-TC-17 and preserves all v5 cases, independent fixtures,
root-CWD migration regression, append-only Evaluation history, human approval and final-review
boundary. The worker scope remains Issue #79 remediation only.

## Required response

Reply with exactly one leading verdict, `APPROVE` or `BLOCK`, followed by concise evidence bound to
the fixed-point, spec-axis review, guide and test-case SHA-256 values above. This is advisory guide
review only; it does not approve code, acceptance, integration, issue closure or the final feature
review.




