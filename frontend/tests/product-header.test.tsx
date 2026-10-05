import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ProductHeader } from "@/components/shell/ProductHeader";
import { AppShell } from "@/components/shell/AppShell";
import { AccountMenu } from "@/components/shell/AccountMenu";

const currentRoute = vi.hoisted(() => ({
  pathname: "/workspaces/ws-a/documents",
}));
vi.mock("next/navigation", () => ({
  usePathname: () => currentRoute.pathname,
}));
afterEach(cleanup);

it("uses canonical workspace destinations and only exposes authorized Operator navigation", () => {
  const view = render(
    <ProductHeader
      activeSection="documents"
      workspaceId="ws/a"
      canOpenOperator={false}
      account={<span>Account</span>}
    />,
  );
  expect(screen.getByRole("link", { name: "Conversations" })).toHaveAttribute(
    "href",
    "/workspaces/ws%2Fa/conversations",
  );
  expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.queryByRole("link", { name: "Operator" }),
  ).not.toBeInTheDocument();
  view.rerender(
    <ProductHeader
      activeSection="operator"
      workspaceId={null}
      canOpenOperator
      account={null}
    />,
  );
  expect(screen.getByRole("link", { name: "Operator" })).toHaveAttribute(
    "href",
    "/operator",
  );
  expect(screen.getByRole("link", { name: "Conversations" })).toHaveAttribute(
    "href",
    "/workspaces",
  );
  expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
    "href",
    "/workspaces",
  );
});

const shellProps = {
  workspaces: [
    {
      id: "first-listed",
      name: "Another workspace",
      archived: false,
      revision: 0,
      created_at: "2026-10-05T00:00:00Z",
    },
  ],
  nextCursor: null,
  capabilities: [],
  subject: "real-user",
  themePreference: "system" as const,
};

it("binds shell navigation to the route workspace instead of the first listed workspace", () => {
  currentRoute.pathname = "/workspaces/route-workspace/documents";
  render(<AppShell {...shellProps}>Content</AppShell>);
  const navigation = screen.getByRole("navigation", {
    name: "Primary navigation",
  });
  expect(
    within(navigation).getByRole("link", { name: "Documents" }),
  ).toHaveAttribute("href", "/workspaces/route-workspace/documents");
  fireEvent.click(screen.getByRole("button", { name: "Menu" }));
  expect(screen.getByRole("link", { name: "Another workspace" })).toBeVisible();
});

it.each([
  "/workspaces",
  "/workspaces/archived",
  "/workspaces/new",
  "/workspaces/%61rchived/documents",
  "/workspaces/%6Eew/documents",
  "/operator",
  "/workspaces/%E0%A4%A/documents",
])(
  "does not interpret reserved or malformed route %s as a workspace ID",
  (pathname) => {
    currentRoute.pathname = pathname;
    render(<AppShell {...shellProps}>Content</AppShell>);
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
      "href",
      "/workspaces",
    );
  },
);

it("renders supplied identity safely while preserving appearance and logout", () => {
  render(<AccountMenu subject="<actual-user>" themePreference="system" />);
  fireEvent.click(
    screen.getByRole("button", { name: "Account: <actual-user>" }),
  );
  expect(screen.getByText("<actual-user>")).toBeVisible();
  expect(
    screen.getByRole("menuitem", { name: "Log out" }).closest("form"),
  ).toHaveAttribute("action", "/api/auth/logout");
  fireEvent.click(screen.getByRole("menuitem", { name: "Appearance" }));
  expect(screen.getByRole("dialog", { name: "Appearance" })).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Appearance" })).toHaveValue(
    "system",
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Appearance" }), {
    target: { value: "dark" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Account: <actual-user>" }),
  );
  fireEvent.click(screen.getByRole("menuitem", { name: "Appearance" }));
  expect(screen.getByRole("combobox", { name: "Appearance" })).toHaveValue(
    "dark",
  );
});
