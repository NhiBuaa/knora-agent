# Knora Keycloak login theme

The theme changes presentation only. Keycloak still owns the username/password form, form action, hidden fields, error handling and OIDC protocol. Knora's BFF keeps state, nonce and S256 PKCE validation.

## Verified Keycloak base

The local image is `quay.io/keycloak/keycloak:26.3.3`, digest `sha256:6a7217a100bd3e5de4063a27a538ef999a3c5a88c4b4ec0ffc0a642aee7b2597`. The inspection used:

```powershell
docker image inspect quay.io/keycloak/keycloak:26.3.3 --format '{{json .RepoDigests}}'
docker create quay.io/keycloak/keycloak:26.3.3
docker cp <container-id>:/opt/keycloak/lib/lib/main/org.keycloak.keycloak-themes-26.3.3.jar <temporary-path>
```

The JAR contains `theme/keycloak.v2/login/theme.properties`, `theme/base/login/*.ftl` and `theme/keycloak.v2/login/resources/css/styles.css`. The v2 login theme declares `parent=base`, `import=common/keycloak`, `styles=css/styles.css`, and PatternFly v5 common styles. Knora inherits v2 and appends `css/knora.css`; it does not replace the forms or templates. This was inspected against the actual image before authoring the theme.

## Local development and deployment

`docker-compose.dev.yml` mounts `themes/knora` read-only. A new `knora-dev` realm imports `loginTheme=knora` from `test/fixtures/keycloak/dev-realm.json`. The persistent `keycloak_dev_data` volume may already contain the realm; import does not update it. For that case, set admin credentials in the current PowerShell process, then run:

```powershell
$env:KNORA_DEV_KEYCLOAK_ADMIN_USERNAME = '<admin username>'
$env:KNORA_DEV_KEYCLOAK_ADMIN_PASSWORD = '<admin password>'
.\scripts\configure-keycloak-theme.ps1
```

The script reads the realm, changes only `loginTheme`, and verifies the setting. It does not delete/re-import users or clients. For another Keycloak host, supply `-BaseUrl` and `-Realm` explicitly. Do not commit credentials.

Build the same theme into a deployment image from the repository root:

```powershell
docker build -f infra/keycloak/Dockerfile -t knora-keycloak:26.3.3 .
```

Inter and Roboto Slab are bundled from `frontend/public/fonts`; their OFL license files are included alongside the theme assets. Theme colors match `frontend/styles/tokens.css`. Keycloak follows the browser's system light/dark setting; the app's preference cookie is not shared with the identity provider.

The current dev realm enables password login, invalid-password feedback, generic errors and logout. Registration and email verification are disabled, and password reset/email delivery is not enabled solely for styling. Theme inheritance still covers Keycloak's available error, expired and logout templates. OIDC redirect allowlists are unchanged.

## Acceptance boundary

Use a disposable realm to check rendered login, invalid credentials, callback state/nonce/PKCE, a protected API request and logout/login again. The logout/login account-switch gate depends on the session fix owned by #132; it must be rerun after that fix is integrated. Do not treat a themed page or a passing unit test as that gate.

Issue #115's disposable Keycloak on port 8183 returned the themed login and stylesheet with HTTP 200. A rejected password returned the inherited Keycloak error on the themed page; a valid password returned HTTP 302 to the configured callback with the original state. A realm update from `keycloak.v2` to `knora` left five users and the `knora-web` redirect allowlist unchanged, and running the update again reported `KEYCLOAK_THEME_ALREADY_SET`. These checks cover the identity provider side only; the complete application logout/account-switch sequence remains gated by #132.
