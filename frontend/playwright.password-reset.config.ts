import { randomUUID } from "node:crypto";
import { defineConfig } from "@playwright/test";

// Separate ports/project keep recovery tests away from the Figma acceptance realm.
const issuer = "http://127.0.0.1:8480/realms/knora-dev";
process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "password-reset-capabilities.spec.ts",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir:
    process.env.KNORA_RESET_PLAYWRIGHT_OUTPUT_DIR ||
    "../.verification/password-reset/playwright-" + randomUUID(),
  use: {
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    baseURL: "http://127.0.0.1:3400",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3400",
    url: "http://127.0.0.1:3400/api/auth/session",
    reuseExistingServer: false,
    env: {
      KEYCLOAK_AUTHORIZATION_URL: `${issuer}/protocol/openid-connect/auth`,
      KEYCLOAK_TOKEN_URL: `${issuer}/protocol/openid-connect/token`,
      KEYCLOAK_JWKS_URL: `${issuer}/protocol/openid-connect/certs`,
      KEYCLOAK_ISSUER: issuer,
      KEYCLOAK_AUDIENCE: "knora-web",
      KEYCLOAK_CLIENT_ID: "knora-web",
      KEYCLOAK_CLIENT_SECRET: "",
      KEYCLOAK_REDIRECT_URI: "http://127.0.0.1:3400/api/auth/callback",
      KEYCLOAK_POST_LOGOUT_REDIRECT_URI: "http://127.0.0.1:3400/",
      KNORA_API_URL: "http://127.0.0.1:8900",
      KNORA_BACKEND_URL: "http://127.0.0.1:8900",
      SESSION_SECRET: "issue162-isolated-test-session-secret",
    },
  },
});
