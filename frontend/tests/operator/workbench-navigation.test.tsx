import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const route = vi.hoisted(() => ({ pathname: "/operator/datasets" }));
vi.mock("next/navigation", () => ({
  usePathname: () => route.pathname,
  useSearchParams: () => new URLSearchParams("workspaceId=workspace-a"),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/components/workspaces/WorkspaceSelector", () => ({
  WorkspaceSelector: () => <button>Switch workspace</button>,
}));

import { OperatorFrame } from "@/components/operator/OperatorFrame";

afterEach(cleanup);

describe("Workbench module navigation", () => {
  it.each(["datasets", "runs"])(
    "activates the %s module and preserves workspace on links",
    (section) => {
      route.pathname = `/operator/${section}/opaque-id`;
      render(
        <OperatorFrame workspaceId="workspace-a" workspaceName="Workspace A">
          <p>Module content</p>
        </OperatorFrame>,
      );
      const label = section === "datasets" ? "Datasets" : "Runs";
      expect(screen.getByRole("heading", { name: label })).toBeVisible();
      expect(screen.getByRole("link", { name: label })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(screen.getByRole("link", { name: "Datasets" })).toHaveAttribute(
        "href",
        "/operator/datasets?workspaceId=workspace-a",
      );
      expect(screen.getByRole("link", { name: "Runs" })).toHaveAttribute(
        "href",
        "/operator/runs?workspaceId=workspace-a",
      );
      expect(screen.getByRole("link", { name: "Traces" })).toBeVisible();
      expect(screen.getByText("Module content")).toBeVisible();
    },
  );
});
