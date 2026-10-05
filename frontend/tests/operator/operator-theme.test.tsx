import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/operator" }));

afterEach(cleanup);

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => ({
    issuer: "https://id.example/realm",
    subject: "operator",
    workspaceIds: [],
    accessToken: "server-token",
    capabilities: ["operator:read"],
  })),
}));
vi.mock("@/lib/auth/workspace-preference", () => ({
  WORKSPACE_PREFERENCE_COOKIE: "knora_workspace_preference",
  decodePreference: vi.fn(async () => "workspace-a"),
}));
vi.mock("@/lib/api/client", () => ({
  KnoraApiError: class KnoraApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  knoraRequest: vi.fn(async (path: string) =>
    path.includes("limit=20")
      ? { items: [], next_cursor: null }
      : { id: "workspace-a", name: "Workspace A", archived: false },
  ),
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => ({ value: "dark" }) })),
}));

import OperatorLayout from "@/app/operator/layout";
import { knoraRequest, KnoraApiError } from "@/lib/api/client";

describe("operator theme access", () => {
  it("opens one Appearance control with the server supplied theme from the account menu", async () => {
    render(await OperatorLayout({ children: <p>Operations</p> }));
    fireEvent.click(screen.getByRole("button", { name: "Account: operator" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Appearance" }));
    expect(
      screen.getAllByRole("combobox", { name: "Appearance" }),
    ).toHaveLength(1);
    expect(screen.getByRole("combobox", { name: "Appearance" })).toHaveValue(
      "dark",
    );
    expect(
      within(
        screen.getByRole("navigation", { name: "Primary navigation" }),
      ).getByRole("link", { name: "Operator" }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("keeps Workspace selection available when a signed hint is no longer owned", async () => {
    vi.mocked(knoraRequest).mockImplementation(async (path) => {
      if (path.includes("limit=20"))
        return { items: [], next_cursor: null } as never;
      throw new KnoraApiError(403, null);
    });
    render(await OperatorLayout({ children: <p>Operations</p> }));
    expect(screen.getByText("Select a workspace")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    expect(
      screen.getByRole("navigation", { name: "Workspace navigation" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Close menu" }));
    fireEvent.click(screen.getByRole("button", { name: "Account: operator" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Appearance" }));
    expect(screen.getByRole("combobox", { name: "Appearance" })).toHaveValue(
      "dark",
    );
  });
});
