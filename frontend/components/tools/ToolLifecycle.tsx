"use client";

import React, { useEffect, useState } from "react";
import type {
  ToolLifecycleItemResponse,
  ToolLifecycleResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";

type LifecycleState =
  | { kind: "loading" }
  | { kind: "available"; items: ToolLifecycleItemResponse[] }
  | { kind: "unavailable" }
  | { kind: "observation_failure"; code?: string | null };

function shown(value: string | number | null | undefined): string {
  return value === null || value === undefined ? "unavailable" : String(value);
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
    <section aria-label="Tool lifecycle">
      <h2>Tool lifecycle</h2>
      {state.kind === "loading" && <p role="status">Loading tool lifecycle…</p>}
      {state.kind === "unavailable" && (
        <p role="status">Tool lifecycle unavailable.</p>
      )}
      {state.kind === "observation_failure" && (
        <p role="alert">
          Tool lifecycle observation failure
          {state.code ? `: ${state.code}` : "."}
        </p>
      )}
      {state.kind === "available" &&
        state.items.map((item) => (
          <article key={item.proposal.proposal_id}>
            <h3>Proposal {item.proposal.proposal_id}</h3>
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
            </dl>
          </article>
        ))}
      <p>Read-only display. Actions are controlled by the operator surface.</p>
    </section>
  );
}
