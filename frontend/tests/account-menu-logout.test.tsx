import React from "react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountMenu } from "@/components/shell/AccountMenu";
import { panelPreferenceKey } from "@/lib/conversations/panel-preferences";

describe("AccountMenu logout loading state", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders idle state initially without progress bar or loading state", async () => {
    const user = userEvent.setup();
    render(<AccountMenu subject="alice@example.com" themePreference="light" />);

    // Open menu
    await user.click(
      screen.getByRole("button", { name: "Account: alice@example.com" }),
    );

    const logoutButton = screen.getByRole("menuitem", { name: "Log out" });
    expect(logoutButton).toBeInTheDocument();
    expect(logoutButton).not.toHaveAttribute("aria-busy");
    expect(logoutButton).not.toHaveAttribute("data-loading");
    expect(logoutButton).not.toBeDisabled();
    expect(
      screen.queryByRole("progressbar", { name: "Signing out" }),
    ).not.toBeInTheDocument();
  });

  it("transitions to loading state upon form submission with spinner and progress bar", async () => {
    const prefKey = panelPreferenceKey(
      { issuer: "https://id.test", subject: "alice@example.com" },
      "workspace-default",
    )!;
    sessionStorage.setItem(prefKey, "custom-panel-state");

    const user = userEvent.setup();
    render(<AccountMenu subject="alice@example.com" themePreference="light" />);

    await user.click(
      screen.getByRole("button", { name: "Account: alice@example.com" }),
    );
    const form = screen
      .getByRole("menuitem", { name: "Log out" })
      .closest("form")!;

    // Submit the form
    fireEvent.submit(form);

    // Preferences should be cleared
    expect(sessionStorage.getItem(prefKey)).toBeNull();

    // Button should now be in loading state
    const loadingButton = screen.getByRole("menuitem", {
      name: /Signing out/i,
    });
    expect(loadingButton).toBeInTheDocument();
    expect(loadingButton).toHaveAttribute("aria-busy", "true");
    expect(loadingButton).toHaveAttribute("data-loading", "true");
    expect(loadingButton).toBeDisabled();

    // Menu panel should remain mounted and visible
    const menuPanel = screen.getByRole("menu", {
      name: "Account: alice@example.com",
    });
    expect(menuPanel).toBeVisible();

    // Blur or outside pointerdown should NOT close the menu while logout is locked
    fireEvent.blur(menuPanel, { relatedTarget: null });
    expect(
      screen.getByRole("menu", { name: "Account: alice@example.com" }),
    ).toBeVisible();

    fireEvent.pointerDown(document.body);
    expect(
      screen.getByRole("menu", { name: "Account: alice@example.com" }),
    ).toBeVisible();

    // Top progress bar should be visible
    const progressBar = screen.getByRole("progressbar", {
      name: "Signing out",
    });
    expect(progressBar).toBeInTheDocument();

    // Theme button should be disabled during logout
    const themeButton = screen.getByRole("menuitem", { name: "Appearance" });
    expect(themeButton).toBeDisabled();
  });

  it("prevents double submission while logout is in-flight", async () => {
    const user = userEvent.setup();
    render(<AccountMenu subject="alice@example.com" themePreference="light" />);

    await user.click(
      screen.getByRole("button", { name: "Account: alice@example.com" }),
    );
    const logoutButton = screen.getByRole("menuitem", { name: "Log out" });
    const form = logoutButton.closest("form")!;

    fireEvent.submit(form);

    // Second submit attempt
    const event = new Event("submit", { bubbles: true, cancelable: true });
    form.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
  });
});
