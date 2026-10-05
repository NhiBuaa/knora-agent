import React, { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/Dialog";
import { Menu } from "@/components/ui/Menu";

afterEach(cleanup);

it("traps modal focus at visible boundaries despite CSS-hidden ancestor controls", async () => {
  render(
    <Dialog open title="Visible boundaries" onClose={vi.fn()}>
      <button>Visible last action</button>
      <style>{`.hidden-modal-actions { display: none; }`}</style>
      <div className="hidden-modal-actions">
        <button>Hidden last action</button>
      </div>
    </Dialog>,
  );
  const first = screen.getByRole("button", {
    name: "Close Visible boundaries",
  });
  const last = screen.getByRole("button", { name: "Visible last action" });
  await userEvent.tab({ shift: true });
  expect(last).toHaveFocus();
  await userEvent.tab();
  expect(first).toHaveFocus();
});

it("skips CSS-hidden ancestor actions during menu arrows and End", async () => {
  render(
    <Menu label="Visible actions">
      <button role="menuitem">First visible</button>
      <style>{`.hidden-menu-actions { display: none; }`}</style>
      <div className="hidden-menu-actions">
        <button role="menuitem">Hidden middle</button>
      </div>
      <button role="menuitem">Last visible</button>
      <div className="hidden-menu-actions">
        <button role="menuitem">Hidden end</button>
      </div>
    </Menu>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Visible actions" }));
  expect(screen.getByRole("menuitem", { name: "First visible" })).toHaveFocus();
  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitem", { name: "Last visible" })).toHaveFocus();
  await user.keyboard("{Home}{End}");
  expect(screen.getByRole("menuitem", { name: "Last visible" })).toHaveFocus();
});

it("dismisses an all-disabled menu on Escape while focus remains on its trigger", async () => {
  render(
    <Menu label="Unavailable actions">
      <button role="menuitem" disabled>
        Unavailable
      </button>
    </Menu>,
  );
  const user = userEvent.setup();
  const trigger = screen.getByRole("button", { name: "Unavailable actions" });
  await user.click(trigger);
  expect(screen.getByRole("menu")).toBeVisible();
  expect(trigger).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("labels the modal and closes it on Escape", async () => {
  const onClose = vi.fn();
  render(
    <Dialog open title="Create workspace" onClose={onClose}>
      <button>Cancel</button>
    </Dialog>,
  );
  expect(
    screen.getByRole("dialog", { name: "Create workspace" }),
  ).toBeVisible();
  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalledTimes(1);
});

it("traps modal focus, skips disabled controls and returns focus after close", async () => {
  function Example() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>Create</button>
        <Dialog
          open={open}
          title="Create workspace"
          onClose={() => setOpen(false)}
        >
          <button disabled>Unavailable</button>
          <input aria-label="Name" />
          <button onClick={() => setOpen(false)}>Cancel</button>
        </Dialog>
      </>
    );
  }
  render(<Example />);
  const user = userEvent.setup();
  const trigger = screen.getByRole("button", { name: "Create" });
  await user.click(trigger);
  const first = screen.getByRole("button", { name: "Close Create workspace" });
  expect(first).toHaveFocus();
  await user.tab({ shift: true });
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  await user.tab();
  expect(first).toHaveFocus();
  screen.getByRole("dialog").focus();
  await user.tab({ shift: true });
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("does not render closed dialogs and dismisses only a backdrop click", () => {
  const close = vi.fn();
  const view = render(
    <Dialog open={false} title="Upload" onClose={close}>
      Content
    </Dialog>,
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  view.rerender(
    <Dialog open title="Upload" onClose={close}>
      <p>Content</p>
    </Dialog>,
  );
  fireEvent.click(screen.getByText("Content"));
  expect(close).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("dialog"), { clientX: -1, clientY: -1 });
  expect(close).toHaveBeenCalledTimes(1);
});

it("does not treat padding inside the dialog rectangle as its backdrop", () => {
  const close = vi.fn();
  render(
    <Dialog open title="Upload" onClose={close}>
      Content
    </Dialog>,
  );
  const dialog = screen.getByRole("dialog");
  vi.spyOn(dialog, "getBoundingClientRect").mockReturnValue({
    left: 100,
    top: 100,
    right: 660,
    bottom: 520,
  } as DOMRect);
  fireEvent.click(dialog, { clientX: 104, clientY: 104 });
  expect(close).not.toHaveBeenCalled();
  fireEvent.click(dialog, { clientX: 90, clientY: 104 });
  expect(close).toHaveBeenCalledTimes(1);
});

it("opens a menu with ArrowDown, skips disabled actions, wraps and returns focus on Escape", async () => {
  render(
    <Menu label="Document actions">
      <button role="menuitem">Details</button>
      <button role="menuitem" disabled>
        Reprocess
      </button>
      <button role="menuitem">Archive</button>
    </Menu>,
  );
  const user = userEvent.setup();
  const trigger = screen.getByRole("button", { name: "Document actions" });
  trigger.focus();
  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("menu", { name: "Document actions" })).toBeVisible();
  expect(screen.getByRole("menuitem", { name: "Details" })).toHaveFocus();
  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitem", { name: "Archive" })).toHaveFocus();
  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitem", { name: "Details" })).toHaveFocus();
  await user.keyboard("{End}");
  expect(screen.getByRole("menuitem", { name: "Archive" })).toHaveFocus();
  await user.keyboard("{Home}{Escape}");
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("dismisses menus after actions, outside clicks and Tab without stealing outside focus", async () => {
  render(
    <>
      <Menu label="Actions">
        <button role="menuitem">Archive</button>
      </Menu>
      <button>Outside</button>
    </>,
  );
  const user = userEvent.setup();
  const trigger = screen.getByRole("button", { name: "Actions" });
  await user.click(trigger);
  await user.click(screen.getByRole("menuitem", { name: "Archive" }));
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  await user.click(trigger);
  await user.click(screen.getByRole("button", { name: "Outside" }));
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Outside" })).toHaveFocus();
  await user.click(trigger);
  await user.tab();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Outside" })).toHaveFocus();
});

it("lets native form actions submit before their menu is dismissed", async () => {
  const submitted = vi.fn((event: React.FormEvent) => event.preventDefault());
  render(
    <Menu label="Account">
      <form onSubmit={submitted}>
        <button type="submit" role="menuitem">
          Log out
        </button>
      </form>
    </Menu>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Account" }));
  await user.click(screen.getByRole("menuitem", { name: "Log out" }));
  expect(submitted).toHaveBeenCalledTimes(1);
});

it("leaves the whole menu on Tab instead of tabbing through each action", async () => {
  render(
    <>
      <Menu label="Actions">
        <button role="menuitem">Details</button>
        <button role="menuitem">Archive</button>
      </Menu>
      <button>Outside</button>
    </>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Actions" }));
  await user.tab();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Outside" })).toHaveFocus();
});
