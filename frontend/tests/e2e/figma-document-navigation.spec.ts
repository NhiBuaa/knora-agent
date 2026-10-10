import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import type { DocumentResponse } from "../../generated/knora-openapi";

const evidence =
  "../.verification/figma/q1/evidence/document-menu-destinations-2026-10-09/fix-http200-2026-10-09";

// Keep projection reads in the authenticated browser. APIRequestContext omits
// Secure cookies on http://127.0.0.1 while Chromium treats loopback as trustworthy.
async function readProjection<T>(page: Page, pathname: string) {
  return page.evaluate(async (url) => {
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
    });
    return { status: response.status, body: (await response.json()) as T };
  }, pathname);
}

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
  const selectionRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      new URL(request.url()).pathname === "/api/workspace-selection",
  );
  await creation
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  const created = await workspaceResponse;
  const selected = await selectionResponse;
  const selection = await selectionRequest;
  expect(created.status()).toBe(201);
  expect(selected.status()).toBe(200);
  const createdBody = (await created.json()) as { id: string };
  const workspaceId = createdBody.id;
  expect(workspaceId).toBeTruthy();
  expect(selection.postDataJSON()).toMatchObject({ workspaceId });
  await expect(page).toHaveURL(`/workspaces/${workspaceId}`);
  const listPath = `/workspaces/${workspaceId}/documents`;
  await page.goto(listPath);

  const sourceName = `q1-navigation-${randomUUID()}.md`;
  const upload = page.getByRole("button", {
    name: "Upload document",
    exact: true,
  });
  await expect(upload).toHaveCSS("color", "rgb(255, 255, 255)");
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
  expect(new URL(uploadResult.url()).pathname).toBe(
    `/api/v1/workspaces/${workspaceId}/documents`,
  );
  const uploadBody = (await uploadResult.json()) as {
    document_id?: string;
  };
  expect(uploadBody.document_id).toBeTruthy();
  expect((await uploadRequest).headers()["idempotency-key"]).toBeTruthy();

  const listResponse = await readProjection<{ documents: DocumentResponse[] }>(
    page,
    `/api/v1/workspaces/${workspaceId}/documents`,
  );
  expect(listResponse.status).toBe(200);
  const listed = listResponse.body;
  const source = listed.documents.find(
    (document) => document.source_name === sourceName,
  );
  expect(source).toBeDefined();
  expect(source!.document_id).toBe(uploadBody.document_id);
  expect(source!.archived).toBe(false);
  // Markdown ingestion is synchronous and does not create an ingestion job.
  expect(source!.ingestion_job_id).toBeNull();
  expect(source!.ingestion_status).toBeNull();
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
    routes: [],
  };
  const observe = async (archived: boolean, stage?: string) => {
    const response = await readProjection<DocumentResponse>(page, detailPath);
    expect(response.status).toBe(200);
    const document = response.body;
    expect(document.document_id).toBe(documentId);
    expect(document.workspace_id).toBe(workspaceId);
    expect(document.source_name).toBe(sourceName);
    expect(document.archived).toBe(archived);
    expect(document.current_document_version_id).toBeTruthy();
    expect(document.served_document_version_id).toBe(
      document.current_document_version_id,
    );
    expect(document.serving_state).toBe("current");
    expect(document.answer_availability).toBeTruthy();
    if (stage) {
      (observations.routes as unknown[]).push({
        stage,
        path: detailPath,
        status: response.status,
        revision: document.revision,
        archived: document.archived,
        current_document_version_id: document.current_document_version_id,
        served_document_version_id: document.served_document_version_id,
        serving_state: document.serving_state,
        answer_availability: document.answer_availability,
        deletion_request: document.deletion_request,
      });
    }
    return document;
  };
  const expectDetail = async (archived: boolean) => {
    await expect(page).toHaveURL(`${listPath}/${documentId}`);
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

  await page.getByRole("checkbox", { name: "Show archived" }).check();
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: sourceName, exact: true }).click();
  await expectDetail(false);
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  await expect(
    page.getByRole("checkbox", { name: "Show archived" }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: "Show archived" }).check();

  const row = page.getByRole("listitem").filter({ hasText: sourceName });
  const readyTrigger = row.getByRole("button", {
    name: `Actions for ${sourceName}`,
  });
  await readyTrigger.click();
  await expect(
    page.getByRole("menuitem", { name: "View details" }),
  ).toBeVisible();
  await expect(readyTrigger).toHaveAttribute("aria-expanded", "true");
  await readyTrigger.click();
  await expect(readyTrigger).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await readyTrigger.click();
  await expect(readyTrigger).toHaveAttribute("aria-expanded", "true");
  await captureIdentity(page, path.join(evidence, "ready-menu.png"));
  await page.getByRole("menuitem", { name: "View details" }).click();
  await expectDetail(false);
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  await expect(
    page.getByRole("checkbox", { name: "Show archived" }),
  ).not.toBeChecked();
  await page.getByRole("checkbox", { name: "Show archived" }).check();
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();
  await readyTrigger.click();
  await expect(readyTrigger).toHaveAttribute("aria-expanded", "true");
  const readyProjection = await observe(false, "ready-before-archive");
  const archiveRevision = readyProjection.revision;
  const archiveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/documents/${documentId}/archive`),
  );
  await page.getByRole("menuitem", { name: "Archive document" }).click();
  const archivedResponse = await archiveResponse;
  expect(archivedResponse.status()).toBe(200);
  expect(archivedResponse.request().headers()["if-match"]).toBe(
    String(archiveRevision),
  );
  await expectDetail(true);
  await captureIdentity(
    page,
    path.join(evidence, "archived-after-menu-archive.png"),
  );
  await expect(page.getByRole("link", { name: "← Documents" })).toHaveAttribute(
    "href",
    `${listPath}?archived=true`,
  );
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(`${listPath}?archived=true`);
  await expect.poll(async () => (await observe(true)).archived).toBe(true);
  const archivedProjection = await observe(true, "archived-after-archive");
  expect(archivedProjection.revision).toBeGreaterThan(archiveRevision);
  expect(archivedProjection.current_document_version_id).toBe(
    readyProjection.current_document_version_id,
  );
  expect(archivedProjection.served_document_version_id).toBe(
    readyProjection.served_document_version_id,
  );
  expect(archivedProjection.serving_state).toBe(readyProjection.serving_state);
  expect(readyProjection.answer_availability).toBe("available");
  expect(archivedProjection.answer_availability).toBe("unavailable");
  expect(archivedProjection.deletion_request).toEqual(
    readyProjection.deletion_request,
  );
  observations.archive = {
    status: archivedResponse.status(),
    ifMatch: String(archiveRevision),
    revision: archivedProjection.revision,
  };
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
  const archivedTrigger = archivedRow.getByRole("button", {
    name: `Actions for ${sourceName}`,
  });
  await archivedTrigger.click();
  await expect(
    page.getByRole("menuitem", { name: "Restore document" }),
  ).toBeVisible();
  await expect(
    page.getByRole("menuitem", { name: "Reprocess document" }),
  ).toHaveCount(0);
  await expect(archivedTrigger).toHaveAttribute("aria-expanded", "true");
  await archivedTrigger.click();
  await expect(archivedTrigger).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await archivedTrigger.click();
  await expect(archivedTrigger).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("menuitem", { name: "View details" }).click();
  await expectDetail(true);
  await expect(page.getByRole("link", { name: "← Documents" })).toHaveAttribute(
    "href",
    `${listPath}?archived=true`,
  );
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(`${listPath}?archived=true`);
  await expect(
    page.getByRole("checkbox", { name: "Show archived" }),
  ).toBeChecked();
  await archivedTrigger.click();
  await expect(archivedTrigger).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("menuitem", { name: "Restore document" }),
  ).toBeVisible();
  await captureIdentity(page, path.join(evidence, "archived-menu.png"));
  const restoreRevision = (await observe(true)).revision;
  const restoreResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/documents/${documentId}/unarchive`),
  );
  await page.getByRole("menuitem", { name: "Restore document" }).click();
  const restoredResponse = await restoreResponse;
  expect(restoredResponse.status()).toBe(200);
  expect(restoredResponse.request().headers()["if-match"]).toBe(
    String(restoreRevision),
  );
  await expectDetail(false);
  await captureIdentity(
    page,
    path.join(evidence, "ready-after-menu-restore.png"),
  );
  await expect(page.getByRole("link", { name: "← Documents" })).toHaveAttribute(
    "href",
    listPath,
  );
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  const restoredProjection = await expect
    .poll(async () => {
      const document = await observe(false);
      return document.archived ? null : document;
    })
    .toBeTruthy()
    .then(async () => observe(false, "ready-after-restore"));
  expect(restoredProjection.revision).toBeGreaterThan(restoreRevision);
  expect(restoredProjection.current_document_version_id).toBe(
    readyProjection.current_document_version_id,
  );
  expect(restoredProjection.served_document_version_id).toBe(
    readyProjection.served_document_version_id,
  );
  expect(restoredProjection.serving_state).toBe(readyProjection.serving_state);
  expect(restoredProjection.answer_availability).toBe(
    readyProjection.answer_availability,
  );
  expect(restoredProjection.deletion_request).toEqual(
    readyProjection.deletion_request,
  );
  observations.restore = {
    status: restoredResponse.status(),
    ifMatch: String(restoreRevision),
    revision: restoredProjection.revision,
  };
  await page.getByRole("link", { name: sourceName, exact: true }).click();
  await expectDetail(false);
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Show archived" }),
  ).not.toBeChecked();
  await page.getByRole("link", { name: sourceName, exact: true }).click();
  await expectDetail(false);
  await page
    .getByRole("button", { name: "Request deletion", exact: true })
    .click();
  const deletionDialog = page.getByRole("dialog", {
    name: /Request document deletion/i,
  });
  await expect(deletionDialog).toBeVisible();
  const deletionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/documents/${documentId}/deletion-request`),
  );
  await deletionDialog
    .getByRole("button", { name: /Request deletion/i })
    .click();
  const deletionResult = await deletionResponse;
  expect(deletionResult.status()).toBe(202);
  expect(deletionResult.request().headers()["idempotency-key"]).toBeTruthy();
  await expect(
    page.getByRole("region", { name: "Deletion request" }).first(),
  ).toContainText(/pending|requested|blocked/i);
  const deletionProjection = await observe(false, "deletion-blocked");
  expect(deletionProjection.deletion_request).toBeTruthy();
  observations.deletion = {
    status: deletionResult.status(),
    deletion_request: deletionProjection.deletion_request,
  };
  await captureIdentity(page, path.join(evidence, "deletion-requested.png"));
  await page.getByRole("link", { name: "← Documents" }).click();
  await expect(page).toHaveURL(listPath);
  await expect(
    page.getByRole("link", { name: sourceName, exact: true }),
  ).toBeVisible();
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(Array.from(document.images, (image) => image.decode()));
  });
  await captureIdentity(page, path.join(evidence, "restored-list.png"));
  observations.final = await observe(false);
  fs.writeFileSync(
    path.join(evidence, "journey.json"),
    JSON.stringify(observations, null, 2),
  );
});
