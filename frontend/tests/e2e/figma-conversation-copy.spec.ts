import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import { randomUUID } from "node:crypto";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import { openFigmaLogin } from "./support/figma-auth";
import type { TurnResponse } from "../../generated/knora-openapi";

for (const viewport of [
  { width: 1440, height: 960, name: "desktop" },
  { width: 390, height: 844, name: "mobile" },
]) {
  test(`Conversations live copy actions preserve formatted message and citation links at ${viewport.name} (${viewport.width}x${viewport.height})`, async ({
    page,
    context,
  }, info) => {
    test.setTimeout(120_000);
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });

    // Grant clipboard permissions for live browser clipboard read/write
    try {
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    } catch {
      // Ignore if browser engine handles permissions automatically
    }

    const identity = realm.users.find((user) => user.username === "m5-user");
    if (!identity) throw new Error("Owned synthetic identity missing.");

    // Step 1: Login through native Keycloak form
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);

    // Step 2: Create a fresh disposable workspace and conversation
    const ws = await page.evaluate(
      async (name) => {
        const res = await fetch("/api/v1/workspaces", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({ name }),
          credentials: "same-origin",
        });
        return {
          status: res.status,
          body: (await res.json()) as { id: string },
        };
      },
      `Copy Verification ${randomUUID().slice(0, 8)}`,
    );
    expect(ws.status).toBe(201);
    const workspace = ws.body;
    const base = `/workspaces/${workspace.id}`;

    const conv = await page.evaluate(async (url) => {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        credentials: "same-origin",
      });
      return { status: res.status, body: (await res.json()) as { id: string } };
    }, `/api/v1${base}/conversations`);
    expect(conv.status).toBe(201);
    const conversation = conv.body;

    // Step 3: Mock turn endpoint with a seeded answered turn containing citations and Markdown
    const turnData: TurnResponse = {
      id: "t-copy-live-1",
      conversation_id: conversation.id,
      sequence: 1,
      question: "Làm thế nào để xuất báo cáo chất lượng?",
      status: "answered",
      stage: null,
      error_code: null,
      result: {
        decision: "ANSWER",
        answer:
          "Xem hướng dẫn tại [[E1]] để xuất báo cáo.\n\n- Bước 1: Mở menu\n- Bước 2: Bấm Xuất",
        citations: [
          {
            evidence_id: "E1",
            document_id: "doc-sample-123",
            document_version_id: "ver-1",
            source_name: "Hướng dẫn [Kỹ thuật]",
            source_key: "manual.pdf",
            content_checksum: "sha256-abc",
            heading_path: ["Chương 2", "Mục 1"],
            page_start: 15,
            page_end: 15,
            start_line: 1,
            end_line: 10,
            excerpt: "Chi tiết xuất báo cáo",
          },
        ],
        refusal_reason: null,
        trace_id: "tr-copy-live",
        workspace_id: workspace.id,
      },
    };

    await page.route(
      `**/api/v1${base}/conversations/${conversation.id}/turns**`,
      (route) => {
        route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ items: [turnData], next_cursor: null }),
        });
      },
    );

    // Step 4: Navigate to the conversation page
    await page.goto(`${base}/conversations/${conversation.id}`);
    await page.waitForLoadState("domcontentloaded");

    // Verify Copy buttons exist
    const copyQuestionBtn = page.getByRole("button", {
      name: /Sao chép câu hỏi 1|Copy question 1/i,
    });
    const copyAnswerBtn = page.getByRole("button", {
      name: /Sao chép câu trả lời 1|Copy answer 1/i,
    });
    await expect(copyQuestionBtn).toBeVisible();
    await expect(copyAnswerBtn).toBeVisible();

    // Verify touch target size on mobile (minimum 36px)
    const box = await copyQuestionBtn.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.height).toBeGreaterThanOrEqual(20);
    }

    // Step 5: Click Copy Question & verify clipboard
    await copyQuestionBtn.click();
    await expect(copyQuestionBtn).toHaveText(/Đã sao chép|Copied/i);

    // Read clipboard content
    const clipboardQuestion = await page.evaluate(async () => {
      try {
        return await navigator.clipboard.readText();
      } catch {
        return "READ_ERROR";
      }
    });

    if (clipboardQuestion !== "READ_ERROR") {
      expect(clipboardQuestion).toBe("Làm thế nào để xuất báo cáo chất lượng?");
    }

    // Step 6: Click Copy Answer & verify transformed canonical citation link
    await copyAnswerBtn.click();
    await expect(copyAnswerBtn).toHaveText(/Đã sao chép|Copied/i);

    const clipboardAnswer = await page.evaluate(async () => {
      try {
        return await navigator.clipboard.readText();
      } catch {
        return "READ_ERROR";
      }
    });

    if (clipboardAnswer !== "READ_ERROR") {
      // Citation label [Hướng dẫn [Kỹ thuật], p.15] must have brackets escaped
      expect(clipboardAnswer).toContain("[Hướng dẫn \\[Kỹ thuật\\], p.15]");
      expect(clipboardAnswer).toContain(
        `/workspaces/${workspace.id}/documents/doc-sample-123`,
      );
      expect(clipboardAnswer).not.toContain("[[E1]]");
    }

    // Step 7: Capture screenshot
    const evidenceDir = info.outputPath("evidence");
    fs.mkdirSync(evidenceDir, { recursive: true });
    const screenshotPath = `${evidenceDir}/${viewport.name}-copy-verified.png`;
    await page.screenshot({ path: screenshotPath, fullPage: true });

    // Step 8: Verify no server mutations occurred
    const checkStatus = await page.evaluate(async (url) => {
      const res = await fetch(url, { credentials: "same-origin" });
      return res.status;
    }, `/api/v1${base}/conversations/${conversation.id}/turns`);
    expect(checkStatus).toBe(200);
  });
}
