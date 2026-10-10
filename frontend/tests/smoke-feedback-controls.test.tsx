import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { WorkspaceManagement } from "@/components/workspaces/WorkspaceManagement";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { UploadDocumentDialog } from "@/components/documents/UploadDocumentDialog";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));
afterEach(cleanup);
it("groups workspace actions behind one menu and opens rename dialog", () => {
  render(
    <WorkspaceManagement
      initialWorkspaces={[
        {
          id: "w",
          name: "Research",
          archived: false,
          revision: 1,
          created_at: "2026-10-10",
        },
      ]}
    />,
  );
  expect(
    screen.queryByRole("textbox", { name: /Rename/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Research/ })).toHaveAttribute(
    "href",
    "/workspaces/w/conversations",
  );
  fireEvent.click(screen.getByRole("button", { name: "Actions for Research" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Rename workspace" }));
  expect(
    screen.getByRole("dialog", { name: "Rename workspace" }),
  ).toBeVisible();
});
it("offers styled light dark and system radio choices", () => {
  render(<ThemeControl initialPreference="system" />);
  fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
  fireEvent.click(screen.getByRole("radio", { name: "System" }));
  expect(document.documentElement).not.toHaveAttribute("data-theme");
});
it("reacts to dragging files over the upload target and clears after drop", () => {
  const file = new File(["source"], "notes.txt", { type: "text/plain" });
  const onFile = vi.fn();
  render(
    <UploadDocumentDialog
      open
      file={null}
      busy={false}
      error={null}
      onFile={onFile}
      onClose={vi.fn()}
      onUpload={vi.fn()}
    />,
  );
  const target = screen.getByText("Drop a file here").parentElement!;
  fireEvent.dragEnter(target, {
    dataTransfer: { types: ["Files"], files: [file] },
  });
  expect(target).toHaveAttribute("data-drag-active", "true");
  expect(within(target).getByText("Release to add this file")).toBeVisible();
  fireEvent.drop(target, { dataTransfer: { types: ["Files"], files: [file] } });
  expect(onFile).toHaveBeenCalledWith(file);
  expect(target).toHaveAttribute("data-drag-active", "false");
});
