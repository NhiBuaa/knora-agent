import React from "react";
import { readFileSync } from "node:fs";
import path from "node:path";
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

  it("offers the locked button variants with semantic signature and ghost styles", () => {
    render(<><Button variant="signature">Review</Button><Button variant="ghost">More</Button></>);
    expect(screen.getByRole("button", { name: "Review" })).toHaveAttribute("data-variant", "signature");
    expect(screen.getByRole("button", { name: "More" })).toHaveAttribute("data-variant", "ghost");
    const css = readFileSync(path.resolve(__dirname, "../styles/controls.css"), "utf8");
    expect(css).toMatch(/\.kn-button\[data-variant="signature"\][^{]*\{[^}]*var\(--signature\)[^}]*var\(--signature-foreground\)/s);
    expect(css).toMatch(/\.kn-button\[data-variant="ghost"\][^{]*\{[^}]*background:\s*transparent/s);
    expect(css).not.toContain('data-variant="quiet"');
  });

  it("preserves native child props and connects field labels, hints and errors", () => {
    render(<>
      <Field id="source" label="Source name" hint="Shown in citations">
        <input id="old-source" className="source-control" placeholder="Enter name" aria-describedby="source-context" required />
      </Field>
      <Field id="format" label="Format"><select defaultValue="pdf"><option value="pdf">PDF</option></select></Field>
      <Field id="notes" label="Notes" error="Notes are required"><textarea rows={4} /></Field>
    </>);
    const input = screen.getByRole("textbox", { name: "Source name" });
    expect(input).toHaveAttribute("id", "source");
    expect(input).toHaveAttribute("class", expect.stringContaining("source-control"));
    expect(input).toHaveAttribute("placeholder", "Enter name");
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("aria-describedby", "source-context source-hint");
    expect(screen.getByText("Shown in citations")).toHaveAttribute("id", "source-hint");
    expect(screen.getByRole("combobox", { name: "Format" })).toBeInTheDocument();
    const textarea = screen.getByRole("textbox", { name: "Notes" });
    expect(textarea).toHaveAttribute("rows", "4");
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(textarea).toHaveAttribute("aria-describedby", "notes-error");
    expect(screen.getByText("Notes are required")).toHaveAttribute("id", "notes-error");
  });

  it("announces actionable errors and gives other notices visible text", () => {
    render(<><Notice kind="error" title="Upload failed" role="alert">Try again</Notice><Notice kind="info" title="Queued">Processing will begin shortly</Notice></>);
    expect(screen.getByRole("alert")).toHaveTextContent("Upload failed");
    expect(screen.getByRole("alert")).toHaveTextContent("Try again");
    expect(screen.getByText("Queued").closest("[role=alert]")).toBeNull();
  });

  it("names non-error notice kinds in visible text", () => {
    render(<>
      <Notice kind="warning" title="Update">Check the source</Notice>
      <Notice kind="system" title="Update">Source is processing</Notice>
      <Notice kind="info" title="Update">Processing starts shortly</Notice>
    </>);
    expect(screen.getByText("Check the source").parentElement).toHaveTextContent("Warning");
    expect(screen.getByRole("status")).toHaveTextContent("In progress");
    expect(screen.getByText("Processing starts shortly").parentElement).toHaveTextContent("Information");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("preserves caller notice roles and leaves non-actionable errors non-assertive", () => {
    render(<>
      <Notice kind="error" title="Saved error">Review later</Notice>
      <Notice kind="error" title="Tracked error" role="status">Already recorded</Notice>
      <Notice kind="system" title="Background task" role="note">Working</Notice>
    </>);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Tracked error");
    expect(screen.getByRole("note")).toHaveTextContent("Background task");
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
