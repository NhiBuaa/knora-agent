import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import type { DocumentResponse } from "../../generated/knora-openapi";

const evidence =
  "../.superpowers/figma/q1/evidence/document-navigation-2026-10-08";

test("Documents live navigation preserves owned source and menu lifecycle", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const identity = realm.users.find(
    (user) => user.username === "m5-delete-user",
  );
  if (!identity) throw new Error("Owned synthetic identity missing.");
  fs.mkdirSync(evidence, { recursive: true });
  await openFigmaLogin(page);
  await page.locator("#username").fill(identity.username);
  await page.locator("#password").fill(identity.credentials[0].value);
  await page.locator("#kc-login").click();
  await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
  await page.goto("/workspaces");

  const workspaceName = `Q1 navigation ${randomUUID()}`;
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  const creation = page.getByRole("dialog", { name: "Create workspace" });
  await creation
    .getByLabel("Workspace name", { exact: true })
    .fill(workspaceName);
  const workspaceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/workspaces",
  );
  const selectionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/workspace-selection",
  );
  await creation
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  expect((await workspaceResponse).status()).toBe(201);
  expect((await selectionResponse).status()).toBe(200);
  const workspaceId = new URL(page.url()).pathname.split("/")[2];
  const listPath = `/workspaces/${workspaceId}/documents`;
  await page.goto(listPath);

  const sourceName = `q1-navigation-${randomUUID()}.md`;
  const upload = page.getByRole("button", {
    name: "Upload document",
    exact: true,
  });
  await upload.click();
  const dialog = page.getByRole("dialog", { name: "Upload document" });
  await dialog.getByLabel("Document file").setInputFiles({
    name: sourceName,
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "Synthetic navigation evidence for a seven chapter report.",
    ),
  });
  const uploadRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      new URL(request.url()).pathname ===
        `/api/v1/workspaces/${workspaceId}/documents`,
  );
  const uploadResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/workspaces/${workspaceId}/documents`,
  );
  await dialog
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  const uploadResult = await uploadResponse;
  expect(uploadResult.ok()).toBe(true);
  expect((await uploadRequest).headers()["idempotency-key"]).toBeTruthy();

  const listResponse = await page.request.get(
    `/api/v1/workspaces/${workspaceId}/documents`,
  );
  expect(listResponse.status()).toBe(200);
  const listed = (await listResponse.json()) as {
    documents: DocumentResponse[];
  };
  const source = listed.documents.find(
    (document) => document.source_name === sourceName,
  );
  expect(source).toBeDefined();
  expect(source!.archived).toBe(false);
  expect(source!.ingestion_status).toBe("succeeded");
  expect(source!.embedding_readiness).toBe("ready");
  expect(source!.serving_state).toBe("current");
  expect(source!.current_document_version_id).toBeTruthy();
  expect(source!.served_document_version_id).toBe(
    source!.current_document_version_id,
  );
  const documentId = source!.document_id;
  const detailPath = `/api/v1/workspaces/${workspaceId}/documents/${documentId}`;
  const observations: Record<string, unknown> = {
    workspaceId,
    documentId,
    sourceName,
  };
  const observe = async (archived: boolean) => {
    const response = await page.request.get(detailPath);
    expect(response.status()).toBe(200);
    const document = (await response.json()) as DocumentResponse;
    expect(document.document_id).toBe(documentId);
    expect(document.workspace_id).toBe(workspaceId);
    expect(document.source_name).toBe(sourceName);
    expect(document.archived).toBe(archived);
    return document;
  };
  const expectDetail = async (archived: boolean) => {
    await expect(page).toHaveURL(
      new RegExp(`${listPath.replaceAll("/", "\\/")}/`),
    );
    await expect(
      page.getByRole("heading", { name: sourceName, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: archived ? "Restore document" : "Archive document",
        exact: true,
      }),
    ).toBeVisible();
    await observe(archived);
  };

  await page.getByRole("link", { name: sourceName, exact: true }).click();
  await expectDetail(false);
  await captureIdentity(page, path.join(evidence, "ready-detail.png"));
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();

  const row = page.getByRole("listitem").filter({ hasText: sourceName });
  await row.getByRole("button", { name: `Actions for ${sourceName}` }).click();
  await expect(
    page.getByRole("menuitem", { name: "View details" }),
  ).toBeVisible();
  await captureIdentity(page, path.join(evidence, "ready-menu.png"));
  const archiveRevision = (await observe(false)).revision;
  const archiveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/documents/${documentId}/archive`),
  );
  await page.getByRole("menuitem", { name: "Archive document" }).click();
  expect((await archiveResponse).status()).toBe(200);
  expect((await archiveResponse).request().headers()["if-match"]).toBe(
    String(archiveRevision),
  );
  const archived = await expect
    .poll(async () => (await observe(true)).archived)
    .toBe(true);
  observations.ready = await observe(false).catch(() => null);
  observations.archived = archived;
  await page.getByRole("checkbox", { name: "Show archived" }).check();
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: sourceName, exact: true }).click();
  await expectDetail(true);
  await captureIdentity(page, path.join(evidence, "archived-detail.png"));
  await expect(page.getByRole("link", { name: "← Documents" })).toHaveAttribute(
    "href",
    `${listPath}?archived=true`,
  );
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(`${listPath}?archived=true`);
  await expect(
    page.getByRole("checkbox", { name: "Show archived" }),
  ).toBeChecked();
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();

  const archivedRow = page
    .getByRole("listitem")
    .filter({ hasText: sourceName });
  await archivedRow
    .getByRole("button", { name: `Actions for ${sourceName}` })
    .click();
  await expect(
    page.getByRole("menuitem", { name: "Restore document" }),
  ).toBeVisible();
  await expect(
    page.getByRole("menuitem", { name: "Reprocess document" }),
  ).toHaveCount(0);
  await captureIdentity(page, path.join(evidence, "archived-menu.png"));
  const restoreRevision = (await observe(true)).revision;
  const restoreResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/documents/${documentId}/unarchive`),
  );
  await page.getByRole("menuitem", { name: "Restore document" }).click();
  expect((await restoreResponse).status()).toBe(200);
  expect((await restoreResponse).request().headers()["if-match"]).toBe(
    String(restoreRevision),
  );
  await expect.poll(async () => (await observe(false)).archived).toBe(false);
  await page.getByRole("link", { name: sourceName, exact: true }).click();
  await expectDetail(false);
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  await captureIdentity(page, path.join(evidence, "restored-list.png"));
  observations.final = await observe(false);
  fs.writeFileSync(
    path.join(evidence, "journey.json"),
    JSON.stringify(observations, null, 2),
  );
});
