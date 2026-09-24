# M5.4 Task 2 report

Added the authorization and ownership matrix through public backend and frontend seams.

- Invalid and expired bearer authentication returns the same `UNAUTHENTICATED` response before any opaque lookup.
- Missing `operator:read` returns `CAPABILITY_ACCESS_DENIED` before lookup.
- Cross-workspace opaque operator IDs return `WORKSPACE_ACCESS_DENIED` without lookup.
- M4 tool-proposal access cannot bypass workspace authorization or invoke actor/workflow lookup.
- Existing X-API-Key callers retain workspace-scoped access.
- Browser BFF tests preserve 401/403 denial responses and never invent success.

Focused backend verification: `5 passed`.

The repository's default Vitest include pattern is `tests/**/*.test.ts(x)`, so the required
`frontend/tests/browser/m5-authorization.spec.ts` artifact is not auto-discovered by the default
script; it remains a browser-facing evidence spec and is covered by the recorded matrix.
