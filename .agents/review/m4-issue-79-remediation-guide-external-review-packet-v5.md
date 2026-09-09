# External review packet: Issue #79 M4.5 remediation guide v5

## Binding

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Remediation slice: GitHub Issue #79
- Reviewed integration head: `7097116557745d5bf2c72d0ab5d4542b529131e2`
- Fixed-point descriptor SHA-256: `3006e223dd9685808b370c78c4656f983aad70529bb28dfb4f082f9c5e5dcd0f`
- Final-review result: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-result-v2.json`
- Final-review result SHA-256: `e4f10e48a82498300ce7454910558b44cb4c4d44bce9a45aacf99d9ac5b70446`
- Prior approved guide: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v4.md`
- Prior approved guide SHA-256: `ff0eff4dac729ad19c4a2b13f4b2eb64c3ffa58c2c95d81648ce7043675d73e9`
- New guide: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v5.md`
- New guide SHA-256: `fdfa18f89b1456c2660082ff23cb0a469fcb7b4fa4331b3bc2a59d9a1183e773`
- New structured test cases: `.agents/review/m4-issue-79-test-cases-v5.json`
- Test-case SHA-256: `471cd3eac173df599d127544a0207f697c61dc3083f029d604d9a648a928fe49`

## Requested guide review

The final feature review returned `REQUEST_CHANGES` with seven Major findings and zero Critical
findings. Review whether v5 closes the following exact gaps without widening Issue #79:

1. Lookup malformed typed provider results and HTTP response-model failures must normalize to
   `502/TOOL_PROVIDER_CONTRACT_INVALID` rather than an untyped 500.
2. A proven no-write `provider_request_rejected` outcome must be typed, durable and mapped to
   `502/TOOL_PROVIDER_REQUEST_FAILED`.
3. Reconciliation must authorize the stored exact resource/scope/claims against current authority
   before trusted routing or provider observation, independently of expired write-token validity.
4. Definitive `provider_scope_denied` must map to `403/TOOL_RESOURCE_ACCESS_DENIED`, not a
   non-terminal `202`.
5. Provider tuple/shape/type/exception failures must remain inside the typed gateway contract.
6. Public execution/reconciliation projections and audit snapshots must recursively exclude
   `rejection_code`, raw provider data, provider routing data, keys, credentials and internal
   exception material while preserving the current sanitized proposal projection.
7. Every matrix must use independently authored fixtures and expected envelopes, and the worker
   must preserve the final-review boundary, accepted frontier and `main` identity.

The guide adds explicit Test Cases M4-79-TC-12 and M4-79-TC-13 and expands TC-01, TC-03, TC-05
and TC-07 to make each requirement observable. It preserves the previously approved v4 cases,
root-CWD migration regression, append-only Evaluation lifecycle and human-approval boundary.

## Required response

Reply with exactly one leading verdict, `APPROVE` or `BLOCK`, followed by concise evidence bound
to the fixed-point, result, guide and test-case SHA-256 values above. This is advisory guide review
only; it does not approve code, acceptance, integration, issue closure or the final feature review.
