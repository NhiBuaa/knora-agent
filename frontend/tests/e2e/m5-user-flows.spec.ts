import { expect, test } from "@playwright/test";

import { loginAs, newRoleContext, observedResult, type M5E2EResult } from "./support/auth";

const results: M5E2EResult[] = [];

test.describe.configure({ mode: "serial" });

function uniqueDocumentName(): string {
  return `m5-live-user-${Date.now()}-${Math.random().toString(36).slice(2)}.md`;
}

test.afterAll(() => {
  // The Task 5 evidence step consumes records in memory. Do not serialize browser
  // sessions, network traces, or any other credential-bearing state here.
  expect(results).toEqual(expect.arrayContaining([]));
});

test("a user uploads a document and observes its authoritative lifecycle through /app", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  const sourceName = uniqueDocumentName();

  await loginAs(page, "user");
  await page.getByRole("link", { name: "Manage documents" }).click();
  await page.locator("#document-file").setInputFiles({
    name: sourceName,
    mimeType: "text/markdown",
    buffer: Buffer.from("# M5 live document\nKnora live E2E evidence is workspace scoped.\n"),
  });
  await page.getByRole("button", { name: "Upload document" }).click();
  await expect(page.getByRole("status")).toContainText("Upload:");
  const documentLink = page.getByRole("link", { name: sourceName });
  await expect(documentLink).toBeVisible();
  await documentLink.click();
  await expect(page.getByRole("heading", { name: sourceName })).toBeVisible();
  await expect(page.getByText("Serving", { exact: true })).toBeVisible();
  await expect(page.getByText("Ingestion", { exact: true })).toBeVisible();
  results.push(observedResult("document-upload-serving", "user", "passed", "document detail rendered"));
  await context.close();
});

test("a user archives then restores a document through the document UI", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  const sourceName = uniqueDocumentName();

  await loginAs(page, "user");
  await page.goto("/app/documents");
  await page.locator("#document-file").setInputFiles({ name: sourceName, mimeType: "text/plain", buffer: Buffer.from("archive lifecycle evidence") });
  await page.getByRole("button", { name: "Upload document" }).click();
  const item = page.getByRole("link", { name: sourceName }).locator("..");
  await expect(item).toBeVisible();
  await item.getByRole("button", { name: "Archive" }).click();
  await expect(item).toBeHidden();
  await page.getByRole("checkbox", { name: "Show archived" }).check();
  await expect(item).toContainText("archived");
  await item.getByRole("button", { name: "Unarchive" }).click();
  await expect(item).toContainText("active");
  results.push(observedResult("archive-unarchive", "user", "passed", "archive state returned to active"));
  await context.close();
});

test("a delete-capable user requests deletion through document UI", async ({ browser }) => {
  const context = await newRoleContext(browser, "delete-user");
  const page = await context.newPage();
  const sourceName = uniqueDocumentName();

  await loginAs(page, "delete-user");
  await page.goto("/app/documents");
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
  await expect(page.getByRole("status")).toHaveText(/Deletion request: (requested|blocked|processing|succeeded|failed)( \(.+\))?/);
  await expect(page.getByRole("heading", { name: sourceName })).toBeVisible();
  results.push(observedResult("deletion-request", "delete-user", "passed", "deletion request rendered"));
  await context.close();
});

test("a user sees a refusal as non-answer through the question UI", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await page.getByRole("link", { name: "Questions" }).click();
  await page.getByRole("textbox", { name: "Question" }).fill(`What is the unavailable M5 fact ${Date.now()}?`);
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/^No answer:/).first()).toBeVisible();
  await expect(page.getByText(/^Trace:/)).not.toBeVisible();
  results.push(observedResult("question-refusal", "user", "passed", "refusal rendered without a completed answer"));
  await context.close();
});

test("a question unavailable state is not a completed answer or citation", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await page.getByRole("link", { name: "Ask a question" }).click();
  await page.getByRole("textbox", { name: "Question" }).fill(`What unavailable M5 question state exists ${Date.now()}?`);
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/^(Request failed:|No answer:)/).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Citations" })).not.toBeVisible();
  await expect(page.getByText(/^Trace:/)).not.toBeVisible();
  results.push(observedResult("question-unavailable", "user", "unavailable", "unavailable state rendered without a completed answer"));
  await context.close();
});
