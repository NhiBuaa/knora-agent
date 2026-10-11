# Task 1 report — primary Keycloak OTP image and secret contract

## Changed files

- `docker-compose.dev.yml`: changed only the primary `keycloak-dev` service to build from
  `infra/keycloak/Dockerfile`; retained its ports, realm import, theme mount, and data volume;
  declared the seven external `KC_SMTP_*` variables with unset values.
- `.env.example`: added blank placeholder entries for the seven `KC_SMTP_*` names.
- `backend/test/config/test_keycloak_theme.py`: added service graph and placeholder-only
  contract assertions, including the unchanged isolated `figma-keycloak` and `figma-mail`
  surfaces.

## Verification

- RED: the new primary graph test failed with `KeyError: 'build'` against the upstream image.
- RED: the new SMTP example test failed with `KeyError: 'KC_SMTP_HOST'`.
- GREEN: focused graph tests — `2 passed, 15 deselected`.
- Focused config regression — `37 passed in 13.23s`.
- `docker compose -f docker-compose.yml config --quiet` — exit 0.
- `docker compose -f docker-compose.dev.yml config --quiet` — exit 0.
- Ruff on the changed test — all checks passed.
- `git diff --check` — clean.

## Self-review

The primary service now packages the existing provider through the repository Dockerfile. Its
existing realm import, theme mount, port, healthcheck, command, and persistent data volume are
unchanged. Figma Keycloak, Mailpit, and OTP proof services were not modified. No realm migration,
SMTP delivery, provider build, or secret-bearing runtime action was run.

## Concerns

- The SMTP variables are intentionally unset in tracked files. A later runtime configuration task
  must supply reviewed local or deployment values and map them into Keycloak realm SMTP metadata.
- The primary image is built by Compose without an explicit image tag; Compose will use its normal
  project/service build tag.
