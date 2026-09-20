import { expect, test } from "@playwright/test";

import { armM5E2EFault, loginAs, newRoleContext } from "./support/auth";

test.describe.configure({ mode: "serial" });

function uniqueDocumentName(): string {
  return `m5-live-user-${Date.now()}-${Math.random().toString(36).slice(2)}.md`;
}

test("a user sees a refusal as non-answer through the question UI", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await page.getByRole("link", { name: "Questions" }).click();
  const absentFact = `M5 absent fixture fact ${Date.now()} ${Math.random().toString(36).slice(2)}`;
  await page.getByRole("textbox", { name: "Question" }).fill(absentFact);
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/^No answer:/).first()).toBeVisible();
  await expect(page.getByText(/^Trace:/)).not.toBeVisible();
  await context.close();
});

test("a user sees a provider failure without a final answer or citation", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await armM5E2EFault(page, "provider_failure");
  await page.getByRole("link", { name: "Questions" }).click();
  await page.getByRole("textbox", { name: "Question" }).fill("How does Knora answer questions?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Request failed: PROVIDER_REQUEST_FAILED" }).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Citations" })).not.toBeVisible();
  await expect(page.getByText(/^Trace:/)).not.toBeVisible();
  await context.close();
});

test("a user sees an interrupted request without a final answer or citation", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await armM5E2EFault(page, "stream_interruption");
  await page.getByRole("link", { name: "Questions" }).click();
  await page.getByRole("textbox", { name: "Question" }).fill("What can Knora tell me about this workspace?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The request was interrupted. It was not completed." }).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Citations" })).not.toBeVisible();
  await expect(page.getByText(/^Trace:/)).not.toBeVisible();
  await context.close();
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
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await expect(page.getByText("unavailable", { exact: true })).toBeVisible();
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
  const deletionStatus = page.getByRole("status");
  await expect(deletionStatus).toHaveText(/Deletion request: (requested|queued|blocked|processing|succeeded|failed)( \(.+\))?/);
  await expect(page.getByRole("heading", { name: sourceName })).toBeVisible();
  const deletionState = await deletionStatus.textContent();
  const accepted = deletionState === "Deletion request: requested" || deletionState === "Deletion request: queued";
  expect(accepted || deletionState === "Deletion request: blocked (DOCUMENT_DELETION_POLICY_UNAVAILABLE)").toBe(true);
  await context.close();
});
