# Task 2 report — authorized HTTP lifecycle contract

## Status

Implemented and committed on `codex/m5-backend-projections`.

## Changes

- Added `GET /v1/workspaces/{workspace_id}/operator/tool-lifecycle`.
- Added typed response schemas for available, unavailable, and observation-failure states.
- Reused operator authorization dependency, preserving token → workspace → capability ordering before projection lookup.
- Registered the lifecycle reader in `create_app` and reused the configured action store.
- Added PostgreSQL `list_proposals(workspace_id)` adapter implementation with workspace filtering and stable ordering.
- Added route tests for unavailable, observation failure, and cross-workspace denial before reader invocation.
- Added the OpenAPI path assertion and regenerated checked-in OpenAPI JSON, manifest, and TypeScript client artifacts.

## Verification

- `C:/Developer/Projects/knora-agent/.venv/Scripts/python.exe -m pytest backend/test/adapters/http/test_operator.py backend/test/api/test_openapi_contract.py -q`
  - `7 passed`
- `C:/Developer/Projects/knora-agent/.venv/Scripts/python.exe scripts/export_openapi.py --check`
  - `OpenAPI artifacts are current`
- `C:/Developer/Projects/knora-agent/.venv/Scripts/ruff.exe check ...`
  - passed after removing an unused test import
- `git diff --check`
  - passed

## Scope / concerns

No frontend or proposal/approval/execution write-flow changes were made. The endpoint intentionally exposes only sanitized lifecycle projection fields and no credentials, provider responses, or mutation controls.
