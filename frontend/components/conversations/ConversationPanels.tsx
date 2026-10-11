"use client";
import { ConversationView } from "./ConversationView";
import React, { useEffect, useRef, useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import {
  DEFAULT_PANEL_PREFERENCES,
  panelPreferenceKey,
  readPanelPreferences,
  writePanelPreferences,
  type PanelIdentityScope,
  type PanelPreferences,
  type EvidenceSelection,
} from "@/lib/conversations/panel-preferences";
import "./conversations.css";
import { ConversationRail } from "./ConversationRail";
import { EvidenceInspector } from "@/components/citations/EvidenceInspector";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { WorkspaceReadOnlyComposer } from "./ConversationComposer";
import type { ConversationResponse } from "@/generated/knora-openapi";
export function ConversationPanels(
  props: React.ComponentProps<typeof ConversationPanelLayout>,
) {
  return (
    <ConversationPanelLayout
      key={
        panelPreferenceKey(props.identityScope, props.workspaceId) ??
        props.workspaceId
      }
      {...props}
    />
  );
}

function ConversationPanelLayout({
  workspaceId,
  identityScope,
  rail,
  inspector,
  selection,
  children,
  composer,
}: {
  workspaceId: string;
  identityScope?: PanelIdentityScope;
  rail: (
    mode: PanelPreferences["rail"],
    change: (mode: PanelPreferences["rail"]) => void,
    overlay?: boolean,
  ) => React.ReactNode;
  inspector: React.ReactNode;
  selection?: EvidenceSelection | null;
  children: React.ReactNode;
  composer: React.ReactNode;
}) {
  const key = panelPreferenceKey(identityScope, workspaceId);
  const [stored, setStored] = useState<{
    key: string | null;
    value: PanelPreferences;
  }>(() => ({ key, value: { ...DEFAULT_PANEL_PREFERENCES } }));
  const preferences =
    stored.key === key ? stored.value : readPanelPreferences(key);
  const root = useRef<HTMLDivElement>(null);
  const evidence = useRef<HTMLDivElement>(null);
  const previousCitation = useRef<HTMLElement | null>(null);
  const [width, setWidth] = useState(1440);
  const [top, setTop] = useState(64);
  const narrow = width < 960;
  const [overlay, setOverlay] = useState<"rail" | "evidence" | null>(null);
  const drag = useRef<{
    panel: "rail" | "inspector";
    x: number;
    width: number;
    pointer: number;
  } | null>(null);
  const inspectorWidth = Math.max(
    280,
    Math.min(
      preferences.inspectorWidth,
      width -
        400 -
        (preferences.rail === "expanded"
          ? 200
          : preferences.rail === "collapsed"
            ? 72
            : 0) -
        16,
    ),
  );
  const railWidth =
    preferences.rail === "collapsed"
      ? 72
      : Math.max(
          200,
          Math.min(
            preferences.railWidth,
            width - 400 - (preferences.inspectorOpen ? inspectorWidth : 0) - 16,
          ),
        );
  function update(patch: Partial<PanelPreferences>) {
    const value = { ...preferences, ...patch };
    setStored({ key, value });
    writePanelPreferences(key, value);
  }
  useEffect(() => {
    setStored({ key, value: readPanelPreferences(key) });
    setOverlay(null);
  }, [key, workspaceId]);
  useEffect(() => {
    const measure = () => {
      setWidth(
        root.current?.getBoundingClientRect().width || window.innerWidth,
      );
      setTop(Math.max(0, root.current?.getBoundingClientRect().top ?? 64));
    };
    measure();
    window.addEventListener("resize", measure);
    const observer =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(measure)
        : null;
    if (root.current) observer?.observe(root.current);
    return () => {
      window.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, []);
  useEffect(() => {
    if (!selection) return;
    previousCitation.current = document.activeElement as HTMLElement;
    update({ inspectorOpen: true });
    if (narrow) setOverlay("evidence");
    else evidence.current?.focus();
    // A new selection opens evidence; resizing does not reopen a dismissed inspector.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);
  useEffect(() => {
    if (!narrow) setOverlay(null);
  }, [narrow]);
  useEffect(() => {
    if (selection && preferences.inspectorOpen && !narrow)
      evidence.current?.focus();
  }, [selection, preferences.inspectorOpen, narrow]);
  function closeEvidence() {
    update({ inspectorOpen: false });
    setOverlay(null);
    previousCitation.current?.focus();
  }
  function divider(panel: "rail" | "inspector") {
    const value = panel === "rail" ? railWidth : inspectorWidth;
    const minimum = panel === "rail" ? 200 : 280;
    const maximum = Math.max(
      minimum,
      Math.min(
        panel === "rail" ? 400 : 520,
        width -
          400 -
          (panel === "rail"
            ? preferences.inspectorOpen
              ? inspectorWidth
              : 0
            : preferences.rail === "expanded"
              ? railWidth
              : preferences.rail === "collapsed"
                ? 72
                : 0) -
          16,
      ),
    );
    const resize = (next: number) =>
      update(
        panel === "rail"
          ? { railWidth: Math.max(minimum, Math.min(maximum, next)) }
          : { inspectorWidth: Math.max(minimum, Math.min(maximum, next)) },
      );
    return (
      <div
        role="separator"
        aria-label={
          panel === "rail"
            ? "Resize conversation rail"
            : "Resize evidence inspector"
        }
        aria-orientation="vertical"
        aria-valuemin={minimum}
        aria-valuemax={maximum}
        aria-valuenow={value}
        tabIndex={0}
        className="conversation-divider"
        onDoubleClick={() =>
          update(
            panel === "rail" ? { railWidth: 252 } : { inspectorWidth: 376 },
          )
        }
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            resize(
              value +
                (event.key === "ArrowRight" ? 1 : -1) *
                  (panel === "rail" ? 1 : -1) *
                  (event.shiftKey ? 40 : 16),
            );
          }
          if (event.key === "Home") {
            event.preventDefault();
            resize(minimum);
          }
          if (event.key === "End") {
            event.preventDefault();
            resize(maximum);
          }
          if (event.key === "Enter") {
            event.preventDefault();
            update(
              panel === "rail" ? { railWidth: 252 } : { inspectorWidth: 376 },
            );
          }
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          drag.current = {
            panel,
            x: event.clientX,
            width: value,
            pointer: event.pointerId,
          };
          event.currentTarget.setPointerCapture?.(event.pointerId);
        }}
        onPointerMove={(event) => {
          const start = drag.current;
          if (start?.panel !== panel || start.pointer !== event.pointerId)
            return;
          resize(
            start.width +
              (event.clientX - start.x) * (panel === "rail" ? 1 : -1),
          );
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      >
        <span className="h-9 w-0.5 rounded-sm bg-control-border" />
      </div>
    );
  }
  const changeRail = (mode: PanelPreferences["rail"]) => {
    update({ rail: mode });
    if (narrow && mode === "hidden") setOverlay(null);
  };
  return (
    <div
      ref={root}
      className="conversation-panels"
      data-rail={preferences.rail}
      data-inspector={preferences.inspectorOpen}
      style={
        {
          "--rail-width": `${railWidth}px`,
          "--inspector-width": `${inspectorWidth}px`,
          "--conversation-top": `${top}px`,
        } as React.CSSProperties
      }
    >
      {!narrow && preferences.rail !== "hidden" && (
        <>
          <div className="conversation-rail-column">
            {rail(preferences.rail, changeRail)}
          </div>
          {preferences.rail === "expanded" ? (
            divider("rail")
          ) : (
            <div className="w-2 shrink-0 bg-page" />
          )}
        </>
      )}
      <section
        aria-label="Conversation workspace"
        className="conversation-center m-0 flex min-w-0 flex-1 flex-col rounded-none border-0 bg-surface p-0"
      >
        <div className="conversation-panel-tools flex shrink-0 items-center justify-end gap-2 px-4 py-1 text-[11px] text-text-muted">
          {(narrow || preferences.rail === "hidden") && (
            <button
              type="button"
              className="m-0 border-0 bg-transparent p-0 text-[11px]"
              onClick={() =>
                narrow ? setOverlay("rail") : changeRail("expanded")
              }
            >
              Show conversations
            </button>
          )}
          {!narrow && preferences.rail !== "hidden" && (
            <button
              className="m-0 border-0 bg-transparent p-0 text-[11px]"
              type="button"
              onClick={() => changeRail("hidden")}
            >
              Hide rail
            </button>
          )}
          <button
            type="button"
            className="m-0 border-0 bg-transparent p-0 text-[11px]"
            onClick={() =>
              narrow
                ? setOverlay("evidence")
                : preferences.inspectorOpen
                  ? closeEvidence()
                  : update({ inspectorOpen: true })
            }
          >
            {!narrow && preferences.inspectorOpen
              ? "Close evidence"
              : "Open evidence"}
          </button>
          <button
            type="button"
            className="m-0 border-0 bg-transparent p-0 text-[11px]"
            onClick={() => {
              update({ ...DEFAULT_PANEL_PREFERENCES });
              setOverlay(null);
            }}
          >
            Reset panels
          </button>
        </div>
        <div className="conversation-scroll flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-8 pt-5 min-[960px]:px-11">
          {children}
        </div>
        <div className="conversation-composer-region shrink-0">{composer}</div>
      </section>
      {!narrow && preferences.inspectorOpen && (
        <>
          {divider("inspector")}
          <div
            ref={evidence}
            tabIndex={-1}
            className="conversation-inspector-column overflow-y-auto bg-surface"
          >
            {inspector}
          </div>
        </>
      )}
      <Dialog
        open={narrow && overlay !== null}
        title={overlay === "rail" ? "Conversations" : "Evidence"}
        onClose={() => setOverlay(null)}
        className={
          overlay === "rail"
            ? "conversation-rail-drawer"
            : "conversation-evidence-sheet"
        }
      >
        {overlay === "rail" ? (
          rail("expanded", changeRail, true)
        ) : (
          <>
            <button
              type="button"
              className="m-0 mb-3 border-0 bg-transparent p-0 text-xs text-text-muted"
              onClick={closeEvidence}
            >
              Close evidence
            </button>
            {inspector}
          </>
        )}
      </Dialog>
    </div>
  );
}

export function ConversationHub({
  workspaceId,
  workspaceName,
  initialConversations,
  nextCursor = null,
  archived = false,
  workspaceArchived = false,
  workspaceRevision,
  identityScope,
}: {
  workspaceId: string;
  workspaceName: string;
  initialConversations: ConversationResponse[];
  nextCursor?: string | null;
  archived?: boolean;
  workspaceArchived?: boolean;
  workspaceRevision?: number;
  identityScope?: PanelIdentityScope;
}) {
  if (!archived && !workspaceArchived)
    return (
      <ConversationView
        workspaceId={workspaceId}
        draftMode
        conversation={{
          id: "",
          workspace_id: workspaceId,
          title: "New conversation",
          title_source: "auto",
          archived: false,
          revision: 0,
          updated_at: "",
        }}
        workspaceName={workspaceName}
        workspaceRevision={workspaceRevision}
        identityScope={identityScope}
        initialConversations={initialConversations}
        nextCursor={nextCursor}
        workspaceSelector={
          <WorkspaceSelector
            workspaceId={workspaceId}
            workspaceName={workspaceName}
          />
        }
      />
    );
  return (
    <ConversationPanels
      workspaceId={workspaceId}
      identityScope={identityScope}
      rail={(mode, onChange, overlay) => (
        <ConversationRail
          workspaceId={workspaceId}
          workspaceName={workspaceName}
          workspaceSelector={
            <WorkspaceSelector
              workspaceId={workspaceId}
              workspaceName={workspaceName}
              disabled={workspaceArchived}
            />
          }
          conversations={initialConversations}
          nextCursor={nextCursor}
          workspaceArchived={workspaceArchived}
          archived={archived}
          mode={mode}
          onChange={onChange}
          overlay={overlay}
        />
      )}
      inspector={
        <EvidenceInspector
          workspaceId={workspaceId}
          workspaceArchived={workspaceArchived}
        />
      }
      composer={
        workspaceArchived ? (
          <WorkspaceReadOnlyComposer
            key={`${workspaceId}:${workspaceRevision}`}
            workspaceId={workspaceId}
            workspaceRevision={workspaceRevision}
          />
        ) : null
      }
    >
      <div className="flex min-h-full flex-col items-center justify-center gap-4 text-center">
        <h1 className="font-display text-[27px] font-semibold leading-[34px]">
          {archived ? "Archived Conversations" : "Conversations"}
        </h1>
        <p className="text-sm text-text-muted">
          Select a conversation to read its history and evidence.
        </p>
      </div>
    </ConversationPanels>
  );
}
