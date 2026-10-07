"use client";

import React from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { WorkspaceShell } from "@/components/workspaces/WorkspaceShell";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { WorkspaceManagement } from "@/components/workspaces/WorkspaceManagement";
import { ArchivedWorkspaceList } from "@/components/workspaces/ArchivedWorkspaceList";
import { WorkspaceUnavailable } from "@/components/workspaces/WorkspaceHome";
import { ConversationView } from "@/components/conversations/ConversationView";
import { DocumentList } from "@/components/documents/DocumentList";
import { DocumentDetail } from "@/components/documents/DocumentDetail";
import {
  OperatorFrame,
  OperatorLookup,
} from "@/components/operator/OperatorFrame";
import { OperationsView } from "@/components/operator/OperationsView";
import { TraceView } from "@/components/operator/TraceView";
import { EvaluationView } from "@/components/operator/EvaluationView";
import { AuthOutcome } from "@/components/auth/AuthOutcome";
import { ProductHeader } from "@/components/shell/ProductHeader";
import { AccountMenu } from "@/components/shell/AccountMenu";
import {
  answered,
  conversation,
  conversations,
  workspace,
  workspaces,
  visualStates,
} from "./figma-state-fixtures";

const capabilities = [
  "documents:read",
  "documents:write",
  "documents:delete",
  "questions:ask",
  "operator:read",
];

/** This composition is reachable only in the standalone test app, never frontend/app. */
export function FigmaFixtureView() {
  const state = useSearchParams().get("state") ?? "128:110";
  const pathname = usePathname();
  const entry = visualStates.find((item) => item.id === state);
  if (!entry) return <p role="alert">Unknown fixture state</p>;
  if (["228:293", "228:326"].includes(state))
    return (
      <AuthOutcome outcome={state === "228:293" ? "unavailable" : "failed"} />
    );
  const limited = state === "183:334";
  let content: React.ReactNode;
  if (entry.group === "operator") {
    content = (
      <OperatorFrame workspaceId={workspace.id} workspaceName={workspace.name}>
        {state === "194:194" ? (
          <OperationsView
            operations={{
              configuration_version: "operational-alerts-v1",
              workspace_id: workspace.id,
              metrics: {
                queue_depth: 0,
                retry_rate: 0,
                cleanup_failure_total: 0,
                orphan_discovery_total: 0,
                oldest_job_age: 0,
                claim_latency_count: 0,
                claim_latency_sum: 0,
                lease_expiry_recovery_total: 0,
                cleanup_attempt_total: 0,
                orphan_reconciliation_total: 0,
              },
              histograms: {},
            }}
          />
        ) : state === "198:200" ? (
          <>
            <OperatorLookup kind="trace" identifier="fixture-trace" />
            <TraceView
              trace={{
                trace_id: "fixture-trace",
                workspace_id: workspace.id,
                trace_schema_version: 2,
                branch_observation_schema_version: 1,
                branch_observations: [],
                retrieval_configuration_id: "retrieval-local-m1-v1",
                embedding_configuration_id: "embedding-local-m1-v2",
                chunk_set_ids: ["fixture-chunk-set"],
                embedding_set_ids: ["fixture-embedding-set"],
                retrieval_latency_ms: 27.798,
                decision: "ANSWER",
                validation_outcome: "valid",
                answer: answered.result!.answer,
                parsed_markers: ["E1"],
                alias_mapping: { E1: "fixture-chunk" },
                candidate_decisions: [],
                candidates: [],
                provider_metadata: {
                  timing: {
                    clock_resolution_ms: 0.001,
                    phases: { generation: { duration_ms: 42 } },
                  },
                },
              }}
            />
          </>
        ) : (
          <>
            <OperatorLookup kind="report" identifier="fixture-report" />
            <EvaluationView
              evaluation={{
                report_id: "fixture-report",
                workspace_id: workspace.id,
                availability: "unavailable",
                observation_failure: "EVALUATION_REPORT_UNAVAILABLE",
              }}
            />
          </>
        )}
      </OperatorFrame>
    );
  } else if (
    state === "152:128" ||
    (state === "148:116" && pathname === "/workspaces")
  )
    content = <WorkspaceManagement initialWorkspaces={[]} />;
  else if (["154:431", "166:211", "166:290"].includes(state))
    content = (
      <ArchivedWorkspaceList
        initialWorkspaces={
          state === "166:290"
            ? []
            : workspaces.map((item) => ({ ...item, archived: true }))
        }
      />
    );
  else if (state === "183:490") content = <WorkspaceUnavailable />;
  else if (["128:120", "128:121", "183:334"].includes(state))
    content = (
      <DocumentList
        workspaceId={workspace.id}
        workspaceName={workspace.name}
        capabilities={limited ? ["documents:read"] : capabilities}
      />
    );
  else if (["128:122", "128:125", "128:128", "128:131"].includes(state))
    content = (
      <DocumentDetail
        workspaceId={workspace.id}
        documentId="fixture-document"
        capabilities={capabilities}
      />
    );
  else
    content = (
      <ConversationView
        workspaceId={workspace.id}
        workspaceName={workspace.name}
        conversation={{ ...conversation, archived: state === "128:119" }}
        workspaceArchived={state === "183:176"}
        workspaceRevision={workspace.revision}
        initialConversations={conversations}
        workspaceSelector={
          <WorkspaceSelector
            workspaceId={workspace.id}
            workspaceName={workspace.name}
            disabled={state === "183:176"}
          />
        }
      />
    );
  if (entry.group === "operator")
    return (
      <div data-fixture-state={state} className="min-h-dvh bg-surface">
        <ProductHeader
          activeSection="operator"
          workspaceId={workspace.id}
          canOpenOperator
          account={<AccountMenu subject="HN" themePreference="light" />}
        />
        {content}
      </div>
    );
  return (
    <div data-fixture-state={state}>
      <WorkspaceShell
        selectedWorkspace={workspace}
        workspaces={workspaces.map((item) =>
          state === "183:176" && item.id === workspace.id
            ? { ...item, archived: true }
            : item,
        )}
        nextCursor={null}
        capabilities={capabilities}
        subject="HN"
        themePreference="light"
      >
        {content}
      </WorkspaceShell>
    </div>
  );
}
