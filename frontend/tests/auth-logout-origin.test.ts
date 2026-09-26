// @vitest-environment node

import { describe, expect, it } from "vitest";
import { POST } from "@/app/api/auth/logout/route";

describe("logout mutation", () => {
  it("does not clear cookies for a cross-site POST without Origin", async () => {
    const response = await POST(
      new Request("https://app.example/api/auth/logout", {
        method: "POST",
        headers: { "sec-fetch-site": "cross-site" },
      }),
    );

    expect(response.status).toBe(403);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
