# Repository layout and Compose simplification

Approved by the owner on 2026-10-10, including the descriptive runbook name and two Compose filenames.

## Design

- Figma verification files live under `.verification/figma/`; generated evidence stays ignored and is preserved locally. Historical `.superpowers/sdd/` reports remain available.
- The workflow is named `production-projections-user-operator-surfaces-verification-runbook.md` and states its functional scope before its historical milestone identifier.
- `docker-compose.yml` is the production deployment configuration entry point. `docker-compose.dev.yml` is the sole development/test entry point. Consolidation alone does not establish production readiness.
- Development and Figma databases, ports and volumes remain isolated. OTP proof instrumentation remains opt-in and separate from the native runtime.
- Existing retained containers and volumes are not removed during configuration migration.

## Implementation plan

- [x] Move Figma verification files and update maintained path references and ignore rules.
- [x] Rename the runbook and update repository references.
- [x] Consolidate development Compose services and explicit profiles; update launcher scripts and ownership guards together.
- [x] Replace old Compose paths in current tests and runbooks; preserve historical evidence as historical evidence.
- [x] Validate each profile's rendered service graph, isolation and absence of proof instrumentation in ordinary runtime; run affected launcher/OTP tests.
- [x] Run frontend formatting and verification for the renamed evidence paths; review and update the existing PR.

Key consumers: `scripts/start-dev.ps1`, `scripts/prepare-local-e2e.ps1`, the three
`scripts/prepare-figma-*.ps1` launchers, `scripts/configure-keycloak-email-otp.ps1`,
`backend/test/config/test_figma_e2e_harness.py`, `backend/test/config/test_keycloak_email_otp.py`,
`backend/test/adapters/cli/test_dev_launcher.py`, and `docs/development/keycloak-theme.md`.

## Compose implementation (2026-10-10)

The standalone dev graph preserves daily names and volume keys. Figma services have
`figma-` names and retain the original Figma volume keys, so service renaming does not
select fresh storage. Native Keycloak runtime and probe nodes are separate services;
proof and commit-reply-loss instrumentation need explicit profiles and guarded launchers.
The scripts start explicit service lists, validate ports/checkout ownership, and do not
remove legacy containers or volumes. Existing containers are still running with their
original labels; migration requires inspecting and stopping those exact owned containers.

Production/default Compose excludes S3 provider acceptance services; those services are
optional in dev. Both entry points retain the existing backend/storage configuration
contract. This maintenance change does not deploy, migrate retained data, or claim
production readiness.

The three old Figma Compose files are removed after updating their maintained consumers.
Historical plans and logs retain their original commands as historical evidence; current
commands are in `docs/development/keycloak-theme.md` and `docs/runbooks/local-development.md`.


## Refactor review and verification

Independent review found a migration blocker: stopped legacy containers were rejected
by the native OTP guards. The corrected guards preserve only stopped legacy resources
with exact project/checkout ownership, while rejecting active legacy/proof containers.
All 32 regression cases passed, including a separate reviewer rerun; final review found
no important blocker.

- Six rendered graphs validated: production, default dev, S3 provider test, Figma,
  OTP proof, and commit-reply fault.
- Figma/proof/fault preparation scripts passed their read-only configuration checks.
- Proxy protocol self-tests: 5 passed.
- Frontend harness/source/config tests: 13 passed across 3 files.
- Prettier, TypeScript, Ruff, OpenAPI exporter and whitespace checks passed.
- Full backend pytest: **1681 passed, 16 skipped, 28 warnings** (350.72 seconds).
  The full backend rerun uses only the owned disposable PostgreSQL database on loopback
  5544. All four proxy selectors are removed from that test process; the first run's
  environment failures and interim mock failures remain in ignored local evidence.

Local command evidence is retained under
`.verification/figma/q1/evidence/compose-refactor-2026-10-10/`; graph artifacts store
service names and profile selections only. No runtime environment/secret dump is published.
