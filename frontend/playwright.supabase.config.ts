import { defineConfig, devices } from "@playwright/test";

process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "supabase-auth.spec.ts",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: "./test-results/supabase-e2e",
  use: {
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    baseURL: "http://127.0.0.1:3500",
    ...devices["Desktop Chrome"],
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  webServer: [
    {
      command: "node tests/e2e/support/supabase-fixture-server.mjs",
      url: "http://127.0.0.1:54321/auth/v1/health",
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3500",
      url: "http://127.0.0.1:3500/auth/login",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        KNORA_AUTH_PROVIDER: "supabase",
        SUPABASE_URL: "http://127.0.0.1:54321",
        SUPABASE_PUBLISHABLE_KEY: "test-anon-key",
        SUPABASE_JWT_ALGORITHM: "ES256",
        KNORA_API_URL: "http://127.0.0.1:54321",
        KNORA_BACKEND_URL: "http://127.0.0.1:54321",
        SESSION_SECRET: "supabase-e2e-isolated-session-secret-32-bytes!",
      },
    },
  ],
});
