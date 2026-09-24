export type M5E2EEnvironment = {
  baseUrl: string;
  apiUrl: string;
  keycloakIssuer: string;
};

function requiredEnvironmentValue(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(
      `M5 live E2E configuration error: required ${name} is missing or empty. ` +
        "Set the test-only environment variables before running Playwright.",
    );
  }
  return value;
}

export function m5E2EEnvironment(): M5E2EEnvironment {
  return {
    baseUrl: requiredEnvironmentValue("M5_E2E_BASE_URL"),
    apiUrl: requiredEnvironmentValue("M5_E2E_API_URL"),
    keycloakIssuer: requiredEnvironmentValue("M5_E2E_KEYCLOAK_ISSUER"),
  };
}
