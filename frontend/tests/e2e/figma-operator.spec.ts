import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import { figmaEnvironment } from "./support/figma-environment";
import type {
  QuestionResponse,
  WorkspaceResponse,
} from "../../generated/knora-openapi";

const evidence = "../.superpowers/sdd/2026-10-05-figma-ui-operator/evidence";

async function login(page: Page, username: string) {
  const identity = realm.users.find((user) => user.username === username);
  if (!identity) throw new Error("Isolated Operator fixture identity missing.");
  await openFigmaLogin(page);
  await page.locator("#username").fill(identity.username);
  await page.locator("#password").fill(identity.credentials[0].value);
  await page.locator("#kc-login").click();
  await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
}

async function workspace(page: Page, name: string): Promise<WorkspaceResponse> {
  const response = await page.request.post("/api/v1/workspaces", {
    headers: { "Idempotency-Key": randomUUID() },
    data: { name },
  });
  expect(response.ok()).toBe(true);
  return response.json();
}

async function select(page: Page, id: string) {
  const response = await page.request.post("/api/workspace-selection", {
    headers: {
      Origin: figmaEnvironment().baseUrl,
      "Sec-Fetch-Site": "same-origin",
    },
    data: { workspaceId: id },
  });
  expect(response.ok()).toBe(true);
}

test.describe("isolated Figma Operator journeys", () => {
  // The default M5 wildcard also discovers this file; its own endpoint guards remain unchanged.
  test.skip(
    ({ baseURL }) => baseURL !== figmaEnvironment().baseUrl,
    "Run with playwright.figma-operator.config.ts against the guarded isolated graph.",
  );

  test("five Operator states expose actual authorized observations and preserve Workspace switching", async ({
    page,
  }) => {
    await login(page, "m5-operator");
    const observed = await workspace(
      page,
      `Research workspace ${randomUUID()}`,
    );
    await select(page, observed.id);
    const question = "The report contains seven chapters.";
    const ingestion = await page.request.post(
      `/api/v1/workspaces/${observed.id}/documents`,
      {
        headers: { "Idempotency-Key": randomUUID() },
        multipart: {
          source_key: "operator-evidence.md",
          file: {
            name: "operator-evidence.md",
            mimeType: "text/markdown",
            buffer: Buffer.from(question),
          },
        },
      },
    );
    expect(ingestion.ok()).toBe(true);
    const answered = await page.request.post("/api/v1/questions", {
      data: { workspace_id: observed.id, question },
    });
    expect(answered.ok()).toBe(true);
    const result = (await answered.json()) as QuestionResponse;
    expect(result.workspace_id).toBe(observed.id);
    expect(result.trace_id.length).toBeGreaterThan(0);

    await page.goto("/operator/operations");
    await expect(
      page.getByRole("heading", { name: "Operations", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("group", { name: "Runtime signals" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: `Switch workspace: ${observed.name}` }),
    ).toBeVisible();
    const content = await page.locator("main.operator-surface").boundingBox();
    expect(content).toMatchObject({ x: 120, y: 64, width: 1200 });
    await captureIdentity(page, `${evidence}/O1-live.png`);

    await page.getByRole("link", { name: "Traces", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Open trace" }),
    ).toBeDisabled();
    await captureIdentity(page, `${evidence}/O2-lookup-live.png`);
    await page
      .getByRole("textbox", { name: "Trace ID", exact: true })
      .fill(result.trace_id);
    await page.getByRole("button", { name: "Open trace" }).click();
    await expect(
      page.getByRole("heading", { name: "Trace summary" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Trace context" }),
    ).toContainText(result.trace_id);
    await expect(
      page.getByRole("region", { name: "Observed result" }),
    ).toContainText(result.decision);
    await expect(
      page.getByRole("region", { name: "Candidate provenance" }),
    ).toContainText("operator-evidence.md");
    await page.getByText("Additional provenance", { exact: true }).click();
    await expect(page.getByText(observed.id, { exact: true })).toBeVisible();
    await page.getByText("Additional provenance", { exact: true }).click();
    await captureIdentity(page, `${evidence}/O2-detail-live.png`);

    await page.getByRole("link", { name: "Evaluations", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Open report" }),
    ).toBeDisabled();
    await captureIdentity(page, `${evidence}/O3-lookup-live.png`);
    await page
      .getByRole("textbox", { name: "Report ID", exact: true })
      .fill("operator-no-persisted-report");
    await page.getByRole("button", { name: "Open report" }).click();
    await expect(
      page.getByRole("heading", { name: "Evaluation report unavailable" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Report context" }),
    ).toContainText("EVALUATION_REPORT_UNAVAILABLE");
    await expect(page.getByRole("link", { name: /download/i })).toHaveCount(0);
    await captureIdentity(page, `${evidence}/O3-unavailable-live.png`);

    const next = await workspace(
      page,
      `Next Operator workspace ${randomUUID()}`,
    );
    await page
      .getByRole("button", { name: `Switch workspace: ${observed.name}` })
      .click();
    await page
      .getByRole("searchbox", { name: "Search workspaces" })
      .fill(next.name);
    await page.getByRole("button", { name: next.name, exact: true }).click();
    await expect(page).toHaveURL(/\/operator\/evaluations$/);
    await expect(
      page.getByRole("textbox", { name: "Report ID", exact: true }),
    ).toHaveValue("");
    await expect(
      page.getByRole("button", { name: `Switch workspace: ${next.name}` }),
    ).toBeVisible();
  });

  test("cross-Workspace and capability denials expose no trace content", async ({
    page,
    browser,
  }) => {
    await login(page, "m5-other-workspace");
    const foreign = await workspace(
      page,
      `Foreign Operator workspace ${randomUUID()}`,
    );
    const operatorContext = await browser.newContext();
    const operator = await operatorContext.newPage();
    try {
      await login(operator, "m5-operator");
      const response = await operator.request.get(
        `/api/operator/traces/missing-trace?workspaceId=${foreign.id}`,
      );
      expect(response.status()).toBe(403);
      await operator.goto(
        `/operator/traces/missing-trace?workspaceId=${foreign.id}`,
      );
      await expect(operator.getByRole("alert")).toHaveText(
        "You are not authorized to inspect this trace.",
      );
      await expect(
        operator.getByRole("heading", { name: "Candidate provenance" }),
      ).toHaveCount(0);
    } finally {
      await operatorContext.close();
    }
    const deniedContext = await browser.newContext();
    const denied = await deniedContext.newPage();
    try {
      await login(denied, "m5-no-operator");
      await denied.goto("/operator/operations");
      await expect(denied.locator('main[role="alert"]')).toHaveText(
        "Operator access denied.",
      );
      await expect(
        denied.getByRole("heading", { name: "Operational observations" }),
      ).toHaveCount(0);
    } finally {
      await deniedContext.close();
    }
  });
});
