import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Notice";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

afterEach(cleanup);

describe("compact UI primitives", () => {
  it("keeps buttons native, disabled, and non-submitting by default", async () => {
    const user = userEvent.setup();
    const clicked = vi.fn();
    const submitted = vi.fn((event: React.FormEvent) => event.preventDefault());
    render(<form onSubmit={submitted}><Button onClick={clicked}>Open</Button><Button disabled>Upload</Button><Button type="submit">Save</Button></form>);
    const open = screen.getByRole("button", { name: "Open" });
    expect(open).toHaveAttribute("type", "button");
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(clicked).not.toHaveBeenCalled();
    await user.click(open);
    open.focus();
    await user.keyboard("{Enter} ");
    expect(clicked).toHaveBeenCalledTimes(3);
    expect(submitted).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted).toHaveBeenCalledTimes(1);
  });

  it("preserves labels, helper and error relationships for all field controls", () => {
    render(<>
      <Field id="source" label="Source name" placeholder="Enter name" helperText="Shown in citations" aria-describedby="source-context" />
      <Field as="select" id="format" label="Format"><option value="pdf">PDF</option></Field>
      <Field as="textarea" id="notes" label="Notes" error="Notes are required" />
    </>);
    const input = screen.getByRole("textbox", { name: "Source name" });
    expect(input).toHaveAttribute("aria-describedby", "source-context source-helper");
    expect(screen.getByText("Shown in citations")).toHaveAttribute("id", "source-helper");
    expect(screen.getByRole("combobox", { name: "Format" })).toBeInTheDocument();
    const textarea = screen.getByRole("textbox", { name: "Notes" });
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(textarea).toHaveAttribute("aria-describedby", "notes-error");
    expect(screen.getByText("Notes are required")).toHaveAttribute("id", "notes-error");
  });

  it("announces actionable errors and gives other notices visible text", () => {
    render(<><Notice kind="error" title="Upload failed">Try again</Notice><Notice kind="info" title="Queued">Processing will begin shortly</Notice></>);
    expect(screen.getByRole("alert")).toHaveTextContent("Upload failed");
    expect(screen.getByRole("alert")).toHaveTextContent("Try again");
    expect(screen.getByText("Queued").closest("[role=alert]")).toBeNull();
  });

  it("names non-error notice kinds in visible text", () => {
    render(<>
      <Notice kind="warning" title="Update">Check the source</Notice>
      <Notice kind="success" title="Update">Source is ready</Notice>
      <Notice kind="info" title="Update">Processing starts shortly</Notice>
    </>);
    expect(screen.getByText("Check the source").parentElement).toHaveTextContent("Warning");
    expect(screen.getByText("Source is ready").parentElement).toHaveTextContent("Success");
    expect(screen.getByText("Processing starts shortly").parentElement).toHaveTextContent("Information");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows status text alongside an icon", () => {
    render(<StatusBadge kind="success">Ready</StatusBadge>);
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Ready").parentElement?.querySelector("[aria-hidden=true]")).toBeInTheDocument();
  });

  it("renders a page heading and keyboard-focusable empty-state link", async () => {
    const user = userEvent.setup();
    const activated = vi.fn((event: React.MouseEvent) => event.preventDefault());
    render(<><PageHeader title="Documents" description="Workspace sources" /><EmptyState title="No documents" description="Add the first source" action={<a href="/app/documents/new" onClick={activated}>Add document</a>} /></>);
    expect(screen.getByRole("heading", { level: 1, name: "Documents" })).toBeInTheDocument();
    expect(screen.getByText("Workspace sources")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "No documents" })).toBeInTheDocument();
    await user.tab();
    expect(screen.getByRole("link", { name: "Add document" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(activated).toHaveBeenCalledTimes(1);
  });
});
