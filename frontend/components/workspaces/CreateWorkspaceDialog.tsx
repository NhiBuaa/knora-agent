"use client";

import React, { useRef, useState } from "react";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import "./workspaces.css";

export function CreateWorkspaceDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (workspace: WorkspaceResponse) => void | Promise<void>;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  React.useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await browserRequest("/v1/workspaces", {
        method: "POST",
        headers: { "Idempotency-Key": (key.current ??= crypto.randomUUID()) },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!response.ok) throw new Error("creation failed");
      const workspace = (await response.json()) as WorkspaceResponse;
      key.current = null;
      setName("");
      onClose();
      await onCreated(workspace);
    } catch {
      setError("Unable to create Workspace. Retry.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Create workspace"
      className="workspace-dialog workspace-create-dialog [&_.kn-dialog\_\_close]:hidden [&_h2]:font-display [&_h2]:text-[22px] [&_h2]:leading-7 [&_.kn-field\_\_label]:text-xs [&_.kn-field\_\_control]:h-11 [&_.kn-field\_\_control]:rounded-lg [&_.kn-field\_\_control]:text-sm [&_.kn-field\_\_hint]:mt-0.5 [&_.kn-field\_\_hint]:text-[11px]"
    >
      <p className="workspace-dialog-intro m-0 mb-[34px] text-[13px] leading-5 text-text-muted">
        Create a separate space for its own conversations, documents, and
        evidence.
      </p>
      <form onSubmit={(event) => void create(event)}>
        <Field
          id="new-workspace-name"
          label="Workspace name"
          hint="Up to 120 characters."
          error={error ?? undefined}
        >
          <input
            ref={input}
            value={name}
            maxLength={120}
            required
            disabled={busy}
            onChange={(event) => {
              setName(event.target.value);
              key.current = null;
            }}
          />
        </Field>
        {error && <p role="alert">{error}</p>}
        <div className="workspace-dialog-actions mt-[34px] flex flex-wrap justify-end gap-2.5">
          <Button
            className="min-h-[38px] min-w-[82px] text-[13px]"
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            className="min-h-[38px] min-w-[158px] text-[13px]"
            type="submit"
            disabled={busy || !name.trim()}
            loading={busy}
          >
            Create workspace
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
