import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import { figmaEnvironment } from "./support/figma-environment";
import type {
  QuestionResponse,
  WorkspaceResponse,
} from "../../generated/knora-openapi";

const evidence =
  "../.verification/figma/q1/evidence/operator-tab-journeys-2026-10-08";

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

async function expectWorkspace(page: Page, name: string) {
  await expect(
    page.getByRole("button", { name: `Switch workspace: ${name}` }),
  ).toBeVisible();
}

async function expectOperations(page: Page, name: string) {
  await expect(page).toHaveURL(/\/operator\/operations(?:\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Operations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("group", { name: "Runtime signals" }),
  ).toBeVisible();
  await expectWorkspace(page, name);
}

async function expectTraceLookup(page: Page, name: string) {
  await expect(page).toHaveURL(/\/operator\/traces(?:\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Question trace", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Trace ID", exact: true }),
  ).toHaveValue("");
  await expect(page.getByRole("button", { name: "Open trace" })).toBeDisabled();
  await expectWorkspace(page, name);
}

async function expectEvaluationLookup(page: Page, name: string) {
  await expect(page).toHaveURL(/\/operator\/evaluations(?:\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Evaluation report", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Report ID", exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Open report" }),
  ).toBeDisabled();
  await expectWorkspace(page, name);
}

async function clickTab(
  page: Page,
  name: "Operations" | "Traces" | "Evaluations",
) {
  await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
  await page.getByRole("link", { name, exact: true }).click();
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
    await expectOperations(page, observed.name);
    const content = await page.locator("main.operator-surface").boundingBox();
    expect(content).toMatchObject({ x: 120, y: 64, width: 1200 });
    await captureIdentity(page, `${evidence}/O1-live.png`);

    // edge 54: Operations -> empty evaluation lookup.
    await clickTab(page, "Evaluations");
    await expectEvaluationLookup(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-54.png`);

    // edge 60: empty evaluation lookup -> Operations.
    await clickTab(page, "Operations");
    await expectOperations(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-60.png`);

    // Return to the named source state before exercising edge 61.
    await clickTab(page, "Evaluations");
    await expectEvaluationLookup(page, observed.name);
    // edge 61: empty evaluation lookup -> empty trace lookup.
    await clickTab(page, "Traces");
    await expectTraceLookup(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-61.png`);

    // edge 55: empty trace lookup -> Operations.
    await clickTab(page, "Operations");
    await expectOperations(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-55.png`);

    await clickTab(page, "Traces");
    await expectTraceLookup(page, observed.name);
    await captureIdentity(page, `${evidence}/O2-lookup-live.png`);

    // edge 56: empty trace lookup -> empty evaluation lookup.
    await clickTab(page, "Evaluations");
    await expectEvaluationLookup(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-56.png`);

    // The existing lookup capture is retained in the new task evidence directory.
    await captureIdentity(page, `${evidence}/O3-lookup-live.png`);

    // Open the real trace so the detail source can exercise edge 58.
    await clickTab(page, "Traces");
    await expectTraceLookup(page, observed.name);
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

    // edge 58: actual trace detail -> Operations.
    await clickTab(page, "Operations");
    await expectOperations(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-58.png`);

    // Reopen the real detail and retain the existing edge 59 into Evaluations.
    await clickTab(page, "Traces");
    await expectTraceLookup(page, observed.name);
    await page
      .getByRole("textbox", { name: "Trace ID", exact: true })
      .fill(result.trace_id);
    await page.getByRole("button", { name: "Open trace" }).click();
    await expect(
      page.getByRole("region", { name: "Trace context" }),
    ).toContainText(result.trace_id);
    await expect(
      page.getByRole("heading", { name: "Trace summary" }),
    ).toBeVisible();
    await clickTab(page, "Evaluations");
    await expectEvaluationLookup(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-59.png`);
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

    // edge 63: evaluation unavailable -> Operations.
    await expect(
      page.getByRole("region", { name: "Report context" }),
    ).toContainText("operator-no-persisted-report");
    await expect(
      page.getByRole("region", { name: "Report context" }),
    ).toContainText("EVALUATION_REPORT_UNAVAILABLE");
    await expectWorkspace(page, observed.name);
    await clickTab(page, "Operations");
    await expectOperations(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-63.png`);

    // edge 64: evaluation unavailable -> empty trace lookup.
    await clickTab(page, "Evaluations");
    await expectEvaluationLookup(page, observed.name);
    await page
      .getByRole("textbox", { name: "Report ID", exact: true })
      .fill("operator-no-persisted-report");
    await page.getByRole("button", { name: "Open report" }).click();
    await expect(
      page.getByRole("heading", { name: "Evaluation report unavailable" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Report context" }),
    ).toContainText("operator-no-persisted-report");
    await expect(
      page.getByRole("region", { name: "Report context" }),
    ).toContainText("EVALUATION_REPORT_UNAVAILABLE");
    await expectWorkspace(page, observed.name);
    await clickTab(page, "Traces");
    await expectTraceLookup(page, observed.name);
    await captureIdentity(page, `${evidence}/edge-64.png`);

    // Return to the unavailable report for the existing refresh and observation assertions.
    await clickTab(page, "Evaluations");
    await expectEvaluationLookup(page, observed.name);
    await page
      .getByRole("textbox", { name: "Report ID", exact: true })
      .fill("operator-no-persisted-report");
    await page.getByRole("button", { name: "Open report" }).click();
    await expect(
      page.getByRole("heading", { name: "Evaluation report unavailable" }),
    ).toBeVisible();

    const refreshed = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        response
          .url()
          .includes("/operator/evaluations/operator-no-persisted-report"),
    );
    await page.getByRole("button", { name: "Open report" }).click();
    expect((await refreshed).ok()).toBe(true);
    await expect(
      page.getByRole("button", { name: "Open report" }),
    ).toBeEnabled();
    await expect(
      page.getByRole("heading", { name: "Evaluation report unavailable" }),
    ).toBeVisible();
    await page
      .getByRole("textbox", { name: "Report ID", exact: true })
      .fill("operator-subsequent-report");
    await page.getByRole("button", { name: "Open report" }).click();
    await expect(
      page.getByRole("region", { name: "Report context" }),
    ).toContainText("operator-subsequent-report");
    await expect(
      page.getByRole("button", { name: "Open report" }),
    ).toBeEnabled();

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
