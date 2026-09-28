"use client";

import React, { useEffect, useState } from "react";
import type {
  ToolLifecycleItemResponse,
  ToolLifecycleResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { Notice } from "@/components/ui/Notice";
import { StatusBadge } from "@/components/ui/StatusBadge";
import "./tool-lifecycle.css";

type LifecycleState =
  | { kind: "loading" }
  | { kind: "available"; items: ToolLifecycleItemResponse[] }
  | { kind: "unavailable" }
  | { kind: "observation_failure"; code?: string | null };

function shown(value: string | number | null | undefined): string {
  return value === null || value === undefined ? "Unavailable" : String(value);
}

export function ToolLifecycleDisplay({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<LifecycleState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await browserRequest(
          `/v1/workspaces/${encodeURIComponent(workspaceId)}/operator/tool-lifecycle`,
        );
        if (!response.ok) {
          if (!cancelled)
            setState({
              kind: "observation_failure",
              code: `HTTP_${response.status}`,
            });
          return;
        }
        const body = (await response.json()) as ToolLifecycleResponse;
        if (cancelled) return;
        if (body.availability === "available") {
          setState({ kind: "available", items: body.items ?? [] });
        } else if (body.availability === "unavailable") {
          setState({ kind: "unavailable" });
        } else {
          setState({ kind: "observation_failure", code: body.code });
        }
      } catch {
        if (!cancelled) setState({ kind: "observation_failure" });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  return (
    <section aria-label="Tool lifecycle" className="tool-lifecycle-secondary">
      <h2>Tool lifecycle</h2>
      {state.kind === "loading" && <p role="status">Loading tool lifecycle…</p>}
      {state.kind === "unavailable" && (
        <Notice
          kind="warning"
          role="status"
          title="Tool lifecycle unavailable."
        />
      )}
      {state.kind === "observation_failure" && (
        <Notice
          kind="error"
          role="alert"
          title="Tool lifecycle observation failure"
        >
          {state.code && (
            <details>
              <summary>Technical details</summary>
              <code>{state.code}</code>
            </details>
          )}
        </Notice>
      )}
      {state.kind === "available" &&
        state.items.map((item) => (
          <article key={item.proposal.proposal_id}>
            <h3>Proposal {item.proposal.proposal_id}</h3>
            <StatusBadge
              kind={
                item.execution?.lifecycle === "succeeded"
                  ? "success"
                  : item.execution?.lifecycle === "failed"
                    ? "error"
                    : "warning"
              }
            >
              {shown(item.execution?.lifecycle)}
            </StatusBadge>
            <dl>
              <dt>Proposal state</dt>
              <dd>{shown(item.proposal.state)}</dd>
              <dt>Proposal revision</dt>
              <dd>{shown(item.proposal.revision)}</dd>
              <dt>Approval decision</dt>
              <dd>{shown(item.approval.decision)}</dd>
              <dt>Approval decided at</dt>
              <dd>{shown(item.approval.decided_at)}</dd>
              <dt>Approval actor</dt>
              <dd>{shown(item.approval.actor_kind)}</dd>
              <dt>Execution lifecycle</dt>
              <dd>{shown(item.execution?.lifecycle)}</dd>
              <dt>Execution revision</dt>
              <dd>{shown(item.execution?.revision)}</dd>
              <dt>Execution generation</dt>
              <dd>{shown(item.execution?.generation)}</dd>
              <dt>Reconciliation status</dt>
              <dd>{shown(item.reconciliation?.status)}</dd>
              <dt>Reconciliation observation</dt>
              <dd>{shown(item.reconciliation?.observation_type)}</dd>
              <dt>Reconciliation observed at</dt>
              <dd>{shown(item.reconciliation?.observed_at)}</dd>
              <dt>Execution finalized at</dt>
              <dd>{shown(item.execution?.finalized_at)}</dd>
              <dt>Execution failure</dt>
              <dd>{shown(item.execution?.failure_code)}</dd>
            </dl>
          </article>
        ))}
      <p>Read-only display. Actions are controlled by the operator surface.</p>
    </section>
  );
}
