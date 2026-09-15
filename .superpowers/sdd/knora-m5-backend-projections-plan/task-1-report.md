# Task 1 report

Status: implemented

Implemented immutable WorkspacePrincipal capabilities/subject compatibility, KeycloakAuthenticator with strict issuer/audience/expiry and bounded claim mapping, and HTTP Bearer authentication with X-API-Key fallback. Added typed Keycloak settings and create_app injection while preserving legacy API-key state.

Verification: `python -m compileall -q src` passed. Pytest unavailable in worktree environment (pytest module not installed).

Concerns: JWT cryptographic verification is delegated through optional token_validator; default validates structure and claims for gateway-verified deployments. A production deployment should provide a JWKS-backed validator.

## Fix review follow-up

Applied review fixes: removed unsigned claim-only production path (validator is mandatory), preserved API-key fallback on absent/invalid Bearer, wired configured Keycloak settings into runtime composition, ensured malformed claims map to UNAUTHENTICATED, and retained immutable capability checks on principal. TDD command evidence unavailable because pytest is not installed; compileall passed.

Additional tests added: Keycloak valid/expired/wrong issuer/wrong audience/malformed and capability guard. Environment still lacks pytest and ruff, so execution unavailable.

## Final controller verification

Commit `6c635c8` adds PyJWT-backed cached JWKS validation from runtime settings, normalizes validator
failures to `UNAUTHENTICATED`, fails closed for missing Bearer capabilities while retaining legacy
API-key compatibility, and authorizes before ingestion service execution. Targeted verification:
`9 passed`; Ruff passed for every touched auth, route, settings, main, and test path. Existing
PostgreSQL-dependent integration tests could not run because the local database connection timed out.

Final review fixes in `11ae106` move workspace/capability authorization into the FastAPI dependency
graph before service resolution and normalize malformed claim types. Verification passed: 11 targeted
tests and Ruff on all touched paths.
