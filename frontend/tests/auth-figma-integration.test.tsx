import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { AccountMenu } from "@/components/shell/AccountMenu";
import { panelPreferenceKey } from "@/lib/conversations/panel-preferences";

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

describe("public authentication outcomes", () => {
  it.each([
    ["unavailable", "Sign-in is temporarily unavailable", "Try again"],
    ["failed", "Couldn’t sign you in", "Try signing in again"],
  ])(
    "renders %s with a fixed retry and no callback details",
    async (outcome, heading, retry) => {
      const load =
        outcome === "unavailable"
          ? import("@/app/auth/unavailable/page")
          : import("@/app/auth/failed/page");
      await expect(load).resolves.toHaveProperty("default");
      const Page = (await load).default;
      render(<Page />);
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
      expect(screen.getByRole("link", { name: retry })).toHaveAttribute(
        "href",
        "/api/auth/login",
      );
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
      expect(
        screen
          .getByRole("complementary", { name: "Knora" })
          .querySelector("img"),
      ).toHaveAttribute("src", "/brand/knora-leaf.svg");
    },
  );
});

describe("account outcome controls", () => {
  it("shows the available subject safely without inventing email or profile claims", () => {
    render(<AccountMenu subject="<actual-subject>" themePreference="system" />);
    fireEvent.click(
      screen.getByRole("button", { name: "Account: <actual-subject>" }),
    );
    const menu = screen.getByRole("menu");
    expect(within(menu).getByText("Signed in")).toBeVisible();
    expect(within(menu).getByText("<actual-subject>")).toBeVisible();
    expect(within(menu).queryByText(/@/)).not.toBeInTheDocument();
    expect(menu.querySelector("actual-subject")).toBeNull();
    expect(within(menu).getByText("System")).toBeVisible();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Appearance" }));
    expect(screen.getByRole("dialog", { name: "Appearance" })).toBeVisible();
  });

  it("clears all conversation panel preferences on logout while preserving other storage", () => {
    const first = panelPreferenceKey(
      { issuer: "https://id.test", subject: "alice" },
      "workspace-a",
    )!;
    const second = panelPreferenceKey(
      { issuer: "https://id.test", subject: "bob" },
      "workspace-b",
    )!;
    sessionStorage.setItem(first, "panel-a");
    sessionStorage.setItem(second, "panel-b");
    sessionStorage.setItem("unrelated", "keep");
    render(<AccountMenu subject="alice" themePreference="dark" />);
    fireEvent.click(screen.getByRole("button", { name: "Account: alice" }));
    const logout = screen.getByRole("menuitem", { name: "Log out" });
    expect(logout.closest("form")).toHaveAttribute(
      "action",
      "/api/auth/logout",
    );
    expect(logout.closest("form")).toHaveAttribute("method", "post");
    fireEvent.submit(logout.closest("form")!);
    expect(sessionStorage.getItem(first)).toBeNull();
    expect(sessionStorage.getItem(second)).toBeNull();
    expect(sessionStorage.getItem("unrelated")).toBe("keep");
  });
});
