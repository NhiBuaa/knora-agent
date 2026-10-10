import { readFile, writeFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

import { loginAs, newRoleContext, openConversationDraft } from "./support/auth";

const SOURCE = "Teacher Manh - Guidelines 2024.pdf";

async function askAndRecord(page: Page, scenario: "positive" | "negative") {
  const output = process.env.KNORA_OLLAMA_BROWSER_OBSERVATIONS;
  if (!output) throw new Error("Browser observation output is required");
  const admissionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/turns$/.test(new URL(response.url()).pathname),
  );
  const admittedTurn = admissionResponse.then(async (response) => {
    expect(response.ok()).toBe(true);
    return response.json();
  });
  const terminalResponsePromise = page.waitForResponse(
    async (response) => {
      if (
        response.request().method() !== "GET" ||
        !/\/turns\/[^/]+$/.test(new URL(response.url()).pathname)
      )
        return false;
      const turn = await admittedTurn;
      if (
        response.request().method() !== "GET" ||
        !new URL(response.url()).pathname.endsWith(`/turns/${turn.id}`)
      )
        return false;
      const body = await response.json();
      return (
        body.status === "answered" ||
        body.status === "refused" ||
        body.status === "failed"
      );
    },
    { timeout: 240_000 },
  );
  await page.getByRole("button", { name: "Ask" }).click();
  const terminalResponse = await terminalResponsePromise;
  const terminal = await terminalResponse.json();
  expect(terminal.result?.trace_id).toEqual(expect.any(String));
  let observations = {};
  try {
    observations = JSON.parse(await readFile(output, "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
  await writeFile(
    output,
    JSON.stringify(
      {
        ...observations,
        [scenario]: {
          workspace_id: terminal.result.workspace_id,
          conversation_id: terminal.conversation_id,
          turn_id: terminal.id,
          trace_id: terminal.result.trace_id,
        },
      },
      null,
      2,
    ),
  );
}

test("real Ollama Conversation answers from the verified page-one chunk", async ({
  browser,
}) => {
  test.setTimeout(300_000);
  expect(process.env.KNORA_GENERATION_PROVIDER).toBe("ollama");
  expect(process.env.KNORA_OLLAMA_GENERATION_MODEL).toMatch(/^qwen3:(8b|4b)$/);

  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  const directOllamaRequests: string[] = [];
  page.on("request", (request) => {
    if (
      new URL(request.url()).port ===
      new URL(process.env.KNORA_OLLAMA_BASE_URL ?? "http://127.0.0.1:11434")
        .port
    ) {
      directOllamaRequests.push(request.url());
    }
  });

  await loginAs(page, "user");
  await openConversationDraft(page);
  await expect(
    page.getByRole("heading", { name: "Grounded answers from your workspace" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Question" })
    .fill("cần trình bày báo cáo bao nhiêu chương?");
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
  await askAndRecord(page, "positive");

  await expect(page.getByText(/7 chương/).first()).toBeVisible({
    timeout: 120_000,
  });
  await expect(page.getByText(/gộp.*chương/i).first()).toBeVisible();
  const citation = page.getByRole("region", { name: "Citations" });
  await expect(citation).toContainText(SOURCE);
  await expect(citation).toContainText("page 1");
  await expect(citation).toContainText(
    "f3081d1e2e6d069f574162a260070f5bc844ac906fac9dd51ebe8868882c0b2c",
  );

  expect(directOllamaRequests).toEqual([]);
  await context.close();
});

test("real Ollama Conversation refuses an absent deadline without a citation", async ({
  browser,
}) => {
  test.setTimeout(300_000);
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();
  await loginAs(page, "user");
  await openConversationDraft(page);
  await expect(
    page.getByRole("heading", { name: "Grounded answers from your workspace" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Question" })
    .fill("Hạn cuối nộp báo cáo chính xác là ngày nào?");
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
  await askAndRecord(page, "negative");
  await expect(page.getByText(/Refused: insufficient_evidence/i)).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.getByRole("region", { name: "Citations" })).toHaveCount(0);
  await context.close();
});
