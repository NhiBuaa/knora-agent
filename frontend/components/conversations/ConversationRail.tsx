"use client";
import React from "react";
import Link from "next/link";
import type { PanelPreferences } from "@/lib/conversations/panel-preferences";
import type { ConversationResponse } from "@/generated/knora-openapi";
import { ConversationList } from "./ConversationList";
export function ConversationRail({
  workspaceId,
  workspaceName,
  workspaceSelector,
  conversations = [],
  nextCursor = null,
  selectedId,
  workspaceArchived = false,
  archived = false,
  onChanged,
  mode,
  onChange,
  overlay = false,
}: {
  workspaceId: string;
  workspaceName?: string;
  workspaceSelector?: React.ReactNode;
  conversations?: ConversationResponse[];
  nextCursor?: string | null;
  selectedId?: string;
  workspaceArchived?: boolean;
  archived?: boolean;
  onChanged?: (conversation: ConversationResponse) => void;
  mode: PanelPreferences["rail"];
  onChange: (mode: PanelPreferences["rail"]) => void;
  overlay?: boolean;
}) {
  const collapsed = mode === "collapsed";
  return (
    <nav
      aria-label="Conversations"
      data-rail={mode}
      className={`m-0 flex h-full min-h-0 flex-col gap-3 border-r border-border bg-surface pb-4 pt-[18px] ${collapsed ? "items-center px-4" : "px-4"}`}
    >
      {collapsed ? (
        <button
          type="button"
          aria-label="Expand workspace context"
          title={workspaceName ?? "Workspace"}
          onClick={() => onChange("expanded")}
          className="m-0 flex size-10 shrink-0 items-center justify-center rounded-[10px] border border-border bg-surface-subtle p-0 text-[13px] font-semibold"
        >
          {(workspaceName ?? workspaceId).trim().charAt(0).toLocaleUpperCase()}
        </button>
      ) : (
        <div className="flex shrink-0 flex-col gap-1">
          {(!workspaceSelector || overlay) && (
            <p className="text-[10px] font-semibold text-text-muted">
              WORKSPACE
            </p>
          )}
          {(!overlay && workspaceSelector) || (
            <p className="truncate text-sm font-semibold">
              {workspaceName ?? workspaceId}
            </p>
          )}
          {overlay && (
            <Link href="/workspaces" className="text-xs text-action-text">
              Manage workspaces
            </Link>
          )}
        </div>
      )}
      <ConversationList
        workspaceId={workspaceId}
        initialConversations={conversations}
        nextCursor={nextCursor}
        workspaceArchived={workspaceArchived}
        presentation={collapsed ? "collapsed" : "rail"}
        selectedId={selectedId}
        archived={archived}
        onChanged={onChanged}
      />
      <button
        type="button"
        aria-label={collapsed ? "Expand rail" : "Collapse rail"}
        onClick={() => onChange(collapsed ? "expanded" : "collapsed")}
        className="m-0 mt-auto flex h-8 shrink-0 items-center gap-2 border-0 bg-transparent p-0 text-xs font-medium text-text-muted"
      >
        <span aria-hidden="true" className="text-base">
          {collapsed ? "›" : "‹"}
        </span>
        {!collapsed && "Collapse rail"}
      </button>
    </nav>
  );
}
