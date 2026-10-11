import { expect, test } from "@playwright/test";

import {
  loginAs,
  newRoleContext,
  openConversationDraft,
  openRetainedConversation,
} from "./support/auth";
import { openFigmaLogin } from "./support/figma-auth";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";

test.describe.configure({ mode: "serial" });

test("a submitted Conversation Turn survives page reload without another POST", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  await loginAs(page, "user");
  await openConversationDraft(page);
  await expect(
    page.getByRole("heading", { name: "Grounded answers from your workspace" }),
  ).toBeVisible();
  const question = `Durable turn ${Date.now()}`;
  let submissions = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/conversations\/[^/]+\/turns$/.test(new URL(request.url()).pathname)
    ) {
      submissions += 1;
    }
  });
  await page.getByRole("textbox", { name: "Question" }).fill(question);
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(
    page.getByRole("paragraph").filter({ hasText: question }).first(),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("paragraph").filter({ hasText: question }).first(),
  ).toBeVisible();
  expect(submissions).toBe(1);
  await context.close();
});

function uniqueDocumentName(): string {
  return `m5-live-user-${Date.now()}-${Math.random().toString(36).slice(2)}.md`;
}

async function workspacePath(
  page: import("@playwright/test").Page,
): Promise<string> {
  const href = await page
    .getByRole("link", { name: "Documents", exact: true })
    .first()
    .getAttribute("href");
  const pathname = new URL(href ?? page.url(), page.url()).pathname;
  const matched = pathname.match(/^\/workspaces\/[^/]+/);
  if (!matched) throw new Error("No active Workspace route after login");
  return matched[0];
}

async function projectTerminalTurn(
  page: import("@playwright/test").Page,
  status: "refused" | "failed" | "interrupted",
  result: Record<string, unknown> | null,
  errorCode: string | null = null,
) {
  await page.route(
    "**/api/v1/workspaces/*/conversations/*/turns?*",
    async (route) => {
      const segments = new URL(route.request().url()).pathname.split("/");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: `projected-${status}`,
              conversation_id: segments[segments.length - 2],
              sequence: 1,
              question: "What does the guide say?",
              status,
              stage: null,
              result,
              error_code: errorCode,
            },
          ],
          next_cursor: null,
        }),
      });
    },
  );
}

test("a persisted refusal remains a non-answer in the Conversation UI", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  if (
    process.env.FIGMA_TEST_MODE === "application" &&
    process.env.FIGMA_TEST_CASE === "m5-refusal"
  ) {
    const identity = realm.users.find((user) => user.username === "m5-user");
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
  } else {
    await loginAs(page, "user");
  }
  await page
    .getByRole("link", { name: "Conversations", exact: true })
    .first()
    .click();
  await projectTerminalTurn(page, "refused", {
    decision: "REFUSAL",
    answer: null,
    citations: [],
    refusal_reason: "INSUFFICIENT_EVIDENCE",
    trace_id: "fixture-trace",
    workspace_id: "m5-workspace",
  });
  await openRetainedConversation(page);
  await expect(page.getByText(/^Refused:/).first()).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "I don’t have enough evidence to answer that.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No supporting citation" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Citation \d+:/ }),
  ).toHaveCount(0);
  const responseBody = page
    .getByRole("listitem", { name: "Question 1" })
    .locator("article > p");
  await expect(responseBody).toHaveCount(1);
  await expect(responseBody).toHaveText("Refused: INSUFFICIENT_EVIDENCE");
  await context.close();
});

test("a persisted failed Turn has no answer or citation", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await projectTerminalTurn(page, "failed", null, "PROVIDER_REQUEST_FAILED");
  await openRetainedConversation(page);
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "PROVIDER_REQUEST_FAILED" })
      .first(),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Citations" }),
  ).not.toBeVisible();
  await context.close();
});

test("a persisted interrupted Turn remains visibly uncertain", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await projectTerminalTurn(page, "interrupted", null);
  await openRetainedConversation(page);
  await expect(page.getByText("Outcome uncertain")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Citations" }),
  ).not.toBeVisible();
  await context.close();
});

test("a user uploads a document and observes its authoritative lifecycle through canonical routes", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  const sourceName = uniqueDocumentName();

  await loginAs(page, "user");
  await page.goto(`${await workspacePath(page)}/documents`);
  await page.locator("#document-file").setInputFiles({
    name: sourceName,
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# M5 live document\nKnora live E2E evidence is workspace scoped.\n",
    ),
  });
  await page.getByRole("button", { name: "Upload document" }).click();
  await expect(page.getByRole("status")).toContainText("Upload:");
  const documentLink = page.getByRole("link", { name: sourceName });
  await expect(documentLink).toBeVisible();
  await documentLink.click();
  await expect(page.getByRole("heading", { name: sourceName })).toBeVisible();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await expect(page.getByText("unavailable", { exact: true })).toBeVisible();
  await context.close();
});

test("a user archives then restores a document through the document UI", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  const sourceName = uniqueDocumentName();

  await loginAs(page, "user");
  await page.goto(`${await workspacePath(page)}/documents`);
  await page.locator("#document-file").setInputFiles({
    name: sourceName,
    mimeType: "text/plain",
    buffer: Buffer.from("archive lifecycle evidence"),
  });
  await page.getByRole("button", { name: "Upload document" }).click();
  const item = page.getByRole("link", { name: sourceName }).locator("..");
  await expect(item).toBeVisible();
  await item.getByRole("button", { name: "Archive" }).click();
  await expect(item).toBeHidden();
  await page.getByRole("checkbox", { name: "Show archived" }).check();
  await expect(item).toContainText("archived");
  await item.getByRole("button", { name: "Unarchive" }).click();
  await expect(item).toContainText("active");
  await context.close();
});

test("a delete-capable user requests deletion through document UI", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "delete-user");
  const page = await context.newPage();
  const sourceName = uniqueDocumentName();

  await loginAs(page, "delete-user");
  await page.goto(`${await workspacePath(page)}/documents`);
  await page.locator("#document-file").setInputFiles({
    name: sourceName,
    mimeType: "text/plain",
    buffer: Buffer.from("deletion request lifecycle evidence"),
  });
  await page.getByRole("button", { name: "Upload document" }).click();
  const documentLink = page.getByRole("link", { name: sourceName });
  await expect(documentLink).toBeVisible();
  await documentLink.click();
  await page.getByRole("button", { name: "Request deletion" }).click();
  const deletionStatus = page.getByRole("status");
  await expect(deletionStatus).toHaveText(
    /Deletion request: (requested|queued|blocked|processing|succeeded|failed)( \(.+\))?/,
  );
  await expect(page.getByRole("heading", { name: sourceName })).toBeVisible();
  const deletionState = await deletionStatus.textContent();
  const accepted =
    deletionState === "Deletion request: requested" ||
    deletionState === "Deletion request: queued";
  expect(
    accepted ||
      deletionState ===
        "Deletion request: blocked (DOCUMENT_DELETION_POLICY_UNAVAILABLE)",
  ).toBe(true);
  await context.close();
});
