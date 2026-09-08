# External review packet: Issue #79 M4.5 remediation guide v4

## Binding

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Remediation slice: GitHub Issue #79
- Reviewed integration head: `83b51cbae9c5cdc43fc8f6082c98e9a66304059e`
- Final-review result SHA-256: `c3dc09bd4dd306f55821c8bba78b4f7482f43dec10ce2c39bda7e8b89cc67917`
- Prior external BLOCK: `.agents/review/m4-issue-79-remediation-guide-external-review-v3-response-1.json`
- Prior external BLOCK SHA-256: `2cbb9adb0d5fca1b1aa0170c1603f6e1bec7a676b26798e5f5ae6ce09863c8c3`
- Guide: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v4.md`
- Guide SHA-256: `ff0eff4dac729ad19c4a2b13f4b2eb64c3ffa58c2c95d81648ce7043675d73e9`
- Structured test cases: `.agents/review/m4-issue-79-test-cases-v4.json`
- Test-case SHA-256: `a1bf215c36c5df6537d6b218527d712732cc0eb2d849b9a14fd06b7a37c21713`

## Exact correction for the prior BLOCK

Both execution and reconciliation matrices now explicitly require independently authored fixtures
and expected envelopes: they must not import, derive, mirror, or read expected values from
production mappers, serializers, enums, or types.

The guide and structured cases now explicitly require a recursive zero-hit scan of every public
projection, error envelope, and captured audit snapshot for every forbidden category:
`rejection_code`, raw provider data, provider routing data, keys, credentials, and internal
exception material.

The prior v3 requirements remain: exact `502/TOOL_PROVIDER_FAILURE` with sanitized
`failure_code`, exact `409/TOOL_EXECUTION_IN_PROGRESS`, exact
`409/TOOL_EXECUTION_FENCED`, `202` for applicable non-terminal ambiguity/not-found results, and a
current sanitized `ToolProposalProjection` on every execution/reconciliation result. Regression,
append-only Evaluation, and separate human-approval boundaries remain unchanged.

## Requested response

Review whether these exact changes close `EXT-V3-01` and `EXT-V3-02`. Reply with exactly one
leading verdict, `APPROVE` or `BLOCK`, followed by concise evidence and bound to the four SHA-256
digests above. This is advisory guide review only; it does not approve code or implementation.
