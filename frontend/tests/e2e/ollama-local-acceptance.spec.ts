import { expect, test } from "@playwright/test";

import { loginAs, newRoleContext } from "./support/auth";

const SOURCE = "Teacher Manh - Guidelines 2024.pdf";

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
  await page.getByRole("button", { name: "New Conversation" }).first().click();
  await expect(page.getByText("No questions yet.")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Question" })
    .fill("cần trình bày báo cáo bao nhiêu chương?");
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
  await page.getByRole("button", { name: "Ask" }).click();

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
  await page.getByRole("button", { name: "New Conversation" }).first().click();
  await expect(page.getByText("No questions yet.")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Question" })
    .fill("Hạn cuối nộp báo cáo chính xác là ngày nào?");
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/Refused: insufficient_evidence/i)).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.getByRole("region", { name: "Citations" })).toHaveCount(0);
  await context.close();
});
