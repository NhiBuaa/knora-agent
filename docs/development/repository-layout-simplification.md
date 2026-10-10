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
- [ ] Consolidate development Compose services and explicit profiles; update launcher scripts and ownership guards together.
- [ ] Replace old Compose paths in current tests and runbooks; preserve historical evidence as historical evidence.
- [ ] Validate each profile's rendered service graph, isolation and absence of proof instrumentation in ordinary runtime; run affected launcher/OTP tests.
- [ ] Run frontend formatting and verification for the renamed evidence paths; review and update the existing PR.

Key consumers: `scripts/start-dev.ps1`, `scripts/prepare-local-e2e.ps1`, the three
`scripts/prepare-figma-*.ps1` launchers, `scripts/configure-keycloak-email-otp.ps1`,
`backend/test/config/test_figma_e2e_harness.py`, `backend/test/config/test_keycloak_email_otp.py`,
`backend/test/adapters/cli/test_dev_launcher.py`, and `docs/development/keycloak-theme.md`.
