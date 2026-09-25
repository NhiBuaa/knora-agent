import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { hydrateRoot } from "react-dom/client";
import { renderToString, renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readThemePreference, resolveTheme, THEME_COOKIE_NAME } from "@/lib/theme";
import { ThemeControl } from "@/components/ui/ThemeControl";

const cookieValue = vi.hoisted(() => ({ value: undefined as string | undefined }));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: (name: string) => name === "knora_theme" ? { value: cookieValue.value } : undefined }) }));
vi.mock("next/font/local", () => ({ default: () => ({ variable: "font-test" }) }));

afterEach(() => {
  cleanup();
  document.documentElement.removeAttribute("data-theme");
  document.cookie = `${THEME_COOKIE_NAME}=; Path=/; Max-Age=0`;
  cookieValue.value = undefined;
  vi.restoreAllMocks();
});

describe("theme preference", () => {
  it("resolves system against the device while explicit choices win", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("accepts only the three visual choices and treats invalid cookies as system", () => {
    expect(readThemePreference("light")).toBe("light");
    expect(readThemePreference("dark")).toBe("dark");
    expect(readThemePreference("system")).toBe("system");
    expect(readThemePreference("admin-session")).toBe("system");
    expect(readThemePreference(undefined)).toBe("system");
  });

  it.each(["light", "dark", "system", "invalid"])("server renders %s cookie without account state", async (value) => {
    cookieValue.value = value;
    const { default: RootLayout } = await import("@/app/layout");
    const markup = renderToStaticMarkup(await RootLayout({ children: <main>Knora</main> }));
    expect(markup).toContain("<main>Knora</main>");
    expect(markup).toContain(`value="${value === "invalid" ? "system" : value}" selected=""`);
    if (value === "light" || value === "dark") expect(markup).toContain(`data-theme="${value}"`);
    else expect(markup).not.toContain("data-theme=");
  });

  it("persists a choice for reload and returns to CSS system mode", () => {
    const { unmount } = render(<ThemeControl initialPreference="system" />);
    const control = screen.getByRole("combobox", { name: "Appearance" });
    fireEvent.change(control, { target: { value: "dark" } });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.cookie).toContain(`${THEME_COOKIE_NAME}=dark`);
    unmount();
    render(<ThemeControl initialPreference={readThemePreference(document.cookie.split("=")[1])} />);
    expect(screen.getByRole("combobox", { name: "Appearance" })).toHaveValue("dark");
    fireEvent.change(screen.getByRole("combobox", { name: "Appearance" }), { target: { value: "system" } });
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(document.cookie).toContain(`${THEME_COOKIE_NAME}=system`);
  });

  it("never persists a value outside the visual preference allowlist", () => {
    render(<ThemeControl initialPreference="dark" />);
    fireEvent.change(screen.getByRole("combobox", { name: "Appearance" }), { target: { value: "unknown" } });
    expect(document.cookie).toContain(`${THEME_COOKIE_NAME}=system`);
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("keeps explicit selection fixed across device changes and leaves system to CSS", () => {
    const { rerender } = render(<ThemeControl initialPreference="light" />);
    document.documentElement.dataset.theme = "light";
    window.dispatchEvent(new Event("change"));
    expect(document.documentElement.dataset.theme).toBe("light");
    rerender(<ThemeControl initialPreference="system" />);
    fireEvent.change(screen.getByRole("combobox", { name: "Appearance" }), { target: { value: "system" } });
    window.dispatchEvent(new Event("change"));
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("hydrates the same choice rendered by the server without mismatch", async () => {
    const host = document.createElement("div");
    host.innerHTML = renderToString(<ThemeControl initialPreference="dark" />);
    document.body.append(host);
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    let root: ReturnType<typeof hydrateRoot> | undefined;
    await act(async () => { root = hydrateRoot(host, <ThemeControl initialPreference="dark" />); });
    expect(host.querySelector("select")).toHaveValue("dark");
    expect(error).not.toHaveBeenCalled();
    await act(async () => root?.unmount());
    host.remove();
  });
});
