# M5.4 live E2E provider-fault and stream-interruption seam

## Status

Design approved in conversation on 2026-09-20. This amendment exists solely to complete the previously blocked M5.4 live scenarios. It does not change a production user contract.

## Problem

M5.4 proves ordinary authenticated user and operator journeys through real Keycloak, Next.js BFF, and the backend. Provider failure and an abruptly interrupted SSE stream remain `BLOCKED_LIVE_E2E`: no supported public mechanism can cause either outcome deterministically.

Browser-side fabrication, direct database writes, special user questions, and production-only configuration changes are prohibited because they would bypass backend ownership or test a different contract. The shared editable Python environment also resolves `knora` to the primary checkout. A local worktree virtual environment is required to run the standard backend gate against this branch.

## Decision

Add a test-only, in-memory M5 E2E fault controller that is constructed only when an explicit M5-E2E runtime setting is enabled. It offers exactly two one-shot scenarios:

- `provider_failure`: the next eligible streamed question receives the existing backend-owned terminal SSE `failure` event with the established safe provider error code.
- `stream_interruption`: the next eligible streamed question emits `started`, then the backend closes the SSE response without a terminal event.

The controller is unavailable in normal and production composition. The ordinary question route, its OpenAPI contract, browser UI, authorization semantics, retrieval, persistence, and provider contracts do not gain test switches or special input values.

## Components and data flow

1. The M5-E2E-only API router exposes a narrow control endpoint for an authenticated local test caller. It accepts only the closed scenario enum and a target Workspace/user binding.
2. The router authorizes the control operation before creating or reading any script. It rejects a mismatched Workspace, unknown scenario, non-test environment, duplicate active script, and replay.
3. The controller stores one script in memory. It is bound to the requested principal and Workspace, and may be consumed once by that exact principal's next streamed question.
4. The existing question route still authenticates and authorizes before resource lookup or side effects. After that boundary, `AnswerQuestion.execute_stream` consumes a matching script.
5. For provider failure, the backend emits its ordinary terminal failure contract. For stream interruption, it yields only `started` and terminates the response. The frontend SSE consumer consequently classifies the observed disconnect as `STREAM_INTERRUPTED`; it never invents a final answer.
6. Playwright first configures the local scenario, then uses the normal browser UI. It asserts only public UI outcomes. It does not write the database, mint tokens, or intercept the question response.

## Safety and isolation

- The router and controller are mounted only under the explicit M5-E2E configuration; normal Docker, development, and production app construction have no control endpoint.
- The environment owns the capability to enable faults. A user question never selects a fault.
- The control surface has a fixed scenario allowlist, one-shot consumption, principal/Workspace binding, and no arbitrary error payload, provider input, database access, or persistent state.
- Authorization occurs before script lookup and before any ordinary question execution. A rejected control request cannot affect a later real question.
- The fault is applied only after normal streamed-question authorization. It cannot be used to turn a missing-session, cross-Workspace, or unauthorized request into a misleading provider or interruption outcome.
- No secret, token, cookie, provider payload, or raw exception is placed in committed test evidence.

## Test plan and acceptance criteria

Backend tests first demonstrate RED cases for: controller absence outside M5-E2E, control-operation authorization before lookup, principal/Workspace binding, one-shot consumption, safe provider failure serialization, and interrupted stream containing `started` but no terminal event. The smallest backend implementation then makes them green.

Playwright adds two real-Keycloak scenarios. The provider-failure scenario must show the existing safe failure state and no cited final answer. The interruption scenario must show an interrupted state and no final answer/citations. Both use the normal question UI after server-side setup.

Create an isolated `.venv` directly in the M5.4 worktree and install this worktree's backend into it; do not modify the shared primary-checkout environment. The standard Python command will then run through that local `.venv`.

The M5.4 gate can be marked complete only when the complete command sequence passes from the M5.4 worktree, the two formerly blocked scenarios have live evidence, evidence is appended and sanitized, and a whole-branch review has no unresolved load-bearing finding. The deletion-policy result remains `UNAVAILABLE` unless the product separately gains an approved deletion policy.

## Non-goals

- A production fault-injection API or customer-visible testing feature.
- New provider modes, provider error taxonomies, or changes to retrieval/citation/refusal logic.
- Browser mocks, response interception, direct database writes, fabricated sessions, or fabricated SSE/provider outcomes.
- Treating unavailable deletion as a successful deletion.
