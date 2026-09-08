# External review packet: Issue #79 M4.5 remediation guide

## Binding

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Remediation slice: GitHub Issue #79
- Reviewed integration head: `83b51cbae9c5cdc43fc8f6082c98e9a66304059e`
- Final-review result: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-result-v1.json`
- Final-review result SHA-256: `c3dc09bd4dd306f55821c8bba78b4f7482f43dec10ce2c39bda7e8b89cc67917`
- Guide: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v3.md`
- Guide SHA-256: `1ab563dce3bf3a24b71aa577c85b07f6ad1e433d0c2fd44d60780a1602e1e8be`
- Structured test cases: `.agents/review/m4-issue-79-test-cases-v3.json`
- Test-case SHA-256: `55137e9e0f5360a6896eea71c8a99f505b282e9bccbb6c22b3a62197e48c17d0`

## Review scope

Review only whether the v3 guide and test cases adequately close these two final-review Major findings. This is an advisory guide review, not code review or implementation approval.

1. The execution/reconciliation public HTTP mapping must provide the closed error envelopes:
   - terminal provider failure: `502` / `TOOL_PROVIDER_FAILURE` with only a sanitized `failure_code`;
   - contention: `409` / `TOOL_EXECUTION_IN_PROGRESS`;
   - fencing: `409` / `TOOL_EXECUTION_FENCED`.
   `rejection_code`, raw provider data, routing, credentials, keys and internal exception material must never be public.
2. Every execution and reconciliation result must include the current sanitized `ToolProposalProjection`, including lifecycle, revision and audit information while excluding the forbidden material above.

## Required reviewer checks

- Confirm separate execution and reconciliation HTTP matrices cover success, terminal failures, indeterminate/not-found, in-progress, fenced, authority-denial and compatibility-stale paths as applicable.
- Confirm matrices must be independent fixtures rather than derived from production mappers, serializers, enums or types.
- Confirm exact status/code/field constraints and recursive forbidden-field scan are explicit.
- Confirm every result, including failure and non-terminal results, requires a current sanitized projection.
- Confirm regression, append-only Evaluation and human-approval boundaries remain intact.
- Flag any missing acceptance condition that would let either Major finding recur undetected.

## Requested response

Reply with exactly one leading verdict, `APPROVE` or `BLOCK`, followed by concise evidence. For `BLOCK`, name the missing guide/test-case requirement precisely. Bind your response to the three SHA-256 digests above.
