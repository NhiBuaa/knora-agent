// @vitest-environment node

import { describe, expect, it } from "vitest";
import { POST } from "@/app/api/auth/logout/route";

describe("logout mutation", () => {
  it("accepts a browser same-origin POST when Next represents its internal URL as localhost", async () => {
    const response = await POST(
      new Request("http://localhost:3000/api/auth/logout", {
        method: "POST",
        headers: {
          host: "127.0.0.1:3000",
          origin: "http://127.0.0.1:3000",
          "sec-fetch-site": "same-origin",
        },
      }),
    );
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "http://127.0.0.1:3000/?signed-out=1",
    );
  });
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
