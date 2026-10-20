export function figmaEnvironment(
  ambient: Record<string, string | undefined> = process.env,
) {
  const project = ambient.FIGMA_TEST_PROJECT ?? "knora-figma-e2e";
  if (!/^knora-figma-e2e(?:-[a-z0-9][a-z0-9-]{0,39})?$/.test(project))
    throw new Error("Figma live E2E project must be an isolated test project.");
  return {
    project,
    baseUrl: "http://127.0.0.1:3300",
    apiUrl: "http://127.0.0.1:8800",
    keycloakIssuer: "http://127.0.0.1:8380/realms/knora-dev",
    realm: "knora-dev",
    mailboxUrl: "http://127.0.0.1:8025",
  };
}

export type FigmaEnvironment = ReturnType<typeof figmaEnvironment>;

export function validateFigmaEnvironment(
  values: FigmaEnvironment,
  ambient: Record<string, string | undefined> = process.env,
) {
  const expected = figmaEnvironment(ambient);
  for (const key of Object.keys(expected) as (keyof FigmaEnvironment)[]) {
    if (values[key] !== expected[key]) {
      throw new Error(`Figma live E2E must use the isolated ${key}.`);
    }
  }
  return values;
}

export function figmaRuntimeEnvironment(
  values: FigmaEnvironment,
  ambient: Record<string, string | undefined> = process.env,
) {
  validateFigmaEnvironment(values, ambient);
  for (const name of Object.keys(ambient)) {
    if (
      /^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)/.test(
        name,
      ) &&
      ambient[name]?.trim()
    ) {
      throw new Error(`Figma live E2E ambient override rejected: ${name}.`);
    }
  }
  return {
    KEYCLOAK_AUTHORIZATION_URL: `${values.keycloakIssuer}/protocol/openid-connect/auth`,
    KEYCLOAK_TOKEN_URL: `${values.keycloakIssuer}/protocol/openid-connect/token`,
    KEYCLOAK_JWKS_URL: `${values.keycloakIssuer}/protocol/openid-connect/certs`,
    KEYCLOAK_ISSUER: values.keycloakIssuer,
    KEYCLOAK_AUDIENCE: "knora-web",
    KEYCLOAK_CLIENT_ID: "knora-web",
    KEYCLOAK_REDIRECT_URI: `${values.baseUrl}/api/auth/callback`,
    KEYCLOAK_POST_LOGOUT_REDIRECT_URI: `${values.baseUrl}/`,
    KNORA_API_URL: values.apiUrl,
    KNORA_BACKEND_URL: values.apiUrl,
    SESSION_SECRET: "figma-e2e-test-session-secret-only",
  };
}
