"use client";

import React, { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { Button } from "@/components/ui/Button";

const SECTIONS = {
  operations: {
    title: "Operations",
    description:
      "Workspace-scoped runtime observations. Read-only operational evidence from the backend.",
  },
  traces: {
    title: "Question trace",
    description:
      "Inspect one question from retrieval through validation, answer/refusal, citations, and candidate provenance.",
  },
  evaluations: {
    title: "Evaluation report",
    description:
      "Inspect a persisted evaluation report for this workspace when one is available.",
  },
} as const;

export function OperatorFrame({
  children,
  workspaceId,
  workspaceName,
}: {
  children: React.ReactNode;
  workspaceId: string | null;
  workspaceName: string | null;
}) {
  const pathname = usePathname() ?? "/operator";
  const search = useSearchParams();
  const section = pathname.split("/")[2];
  const active =
    section === "traces" || section === "evaluations" ? section : "operations";
  const target = search.get("workspaceId");
  return (
    <main className="workspace-shell-main operator-surface mx-auto w-full max-w-[1200px] px-0 pt-[45px] pb-10 text-text-primary max-[1248px]:px-6 max-md:px-4">
      <div className="w-[220px] max-w-full">
        <WorkspaceSelector
          workspaceId={workspaceId}
          workspaceName={workspaceName}
          presentation={
            active === "operations" ? "operator-operations" : "operator-detail"
          }
        />
      </div>
      <h1 className="mt-3.5 mb-0 font-display text-[32px] leading-[42px] font-semibold">
        {SECTIONS[active].title}
      </h1>
      <p
        className={`mt-[5px] mb-0 text-base text-text-muted ${active === "evaluations" ? "leading-6" : "leading-[19px]"} ${active === "traces" ? "max-w-[870px]" : ""}`}
      >
        {SECTIONS[active].description}
      </p>
      <nav
        aria-label="Operator navigation"
        className={`mb-0 flex min-h-[42px] flex-wrap items-center gap-7 text-sm ${active === "evaluations" ? "mt-[22px]" : "mt-[27px]"}`}
      >
        {Object.entries(SECTIONS).map(([key]) => (
          <Link
            key={key}
            href={`/operator/${key}${target ? `?workspaceId=${encodeURIComponent(target)}` : ""}`}
            aria-current={key === active ? "page" : undefined}
            className={`min-h-[27px] shrink-0 border-b-2 no-underline ${key === "operations" ? "min-w-[76px]" : key === "traces" ? "min-w-[50px]" : "min-w-[82px]"} ${active === "operations" ? "pt-0 pb-2 leading-[17px]" : active === "evaluations" ? "pt-[5px] pb-0 leading-5" : "pt-[5px] pb-[3px] leading-[17px]"} ${key === active ? `border-action text-action-text ${active === "evaluations" ? "font-medium" : "font-semibold"}` : `border-transparent text-text-muted ${active === "evaluations" ? "font-normal" : "font-medium"}`}`}
          >
            <span className="block">{key[0].toUpperCase() + key.slice(1)}</span>
          </Link>
        ))}
      </nav>
      <div aria-hidden="true" className="h-px bg-border" />
      {children}
    </main>
  );
}

export function OperatorLookup({
  kind,
  identifier = "",
  workspaceId,
}: {
  kind: "trace" | "report";
  identifier?: string;
  workspaceId?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const query = search.toString();
  const [value, setValue] = useState(identifier);
  const [target, setTarget] = useState(workspaceId ?? "");
  const [pending, startNavigation] = useTransition();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setValue(identifier);
    setTarget(workspaceId ?? "");
    setError(null);
  }, [identifier, workspaceId, pathname, query]);
  const label = kind === "trace" ? "Trace ID" : "Report ID";
  return (
    <form
      className="mt-[17px] mb-0 min-h-[56px]"
      aria-label={`${kind === "trace" ? "Trace" : "Report"} lookup`}
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim() || pending) return;
        setError(null);
        const destination = `/operator/${kind === "trace" ? "traces" : "evaluations"}/${encodeURIComponent(value.trim())}${target.trim() ? `?workspaceId=${encodeURIComponent(target.trim())}` : ""}`;
        const [destinationPath, destinationQuery = ""] = destination.split("?");
        startNavigation(() => {
          try {
            if (
              destinationPath === pathname &&
              new URLSearchParams(destinationQuery).toString() === query
            )
              router.refresh();
            else router.push(destination);
          } catch {
            setError(`Unable to open ${kind}. Retry.`);
          }
        });
      }}
    >
      <label
        htmlFor={`operator-${kind}-id`}
        className={`block text-[11px] leading-[13px] text-text-muted uppercase ${kind === "trace" ? "font-semibold" : "font-medium"}`}
      >
        {label}
      </label>
      <div className="mt-[5px] flex flex-wrap items-start gap-3">
        <input
          id={`operator-${kind}-id`}
          name={kind === "trace" ? "traceId" : "reportId"}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          required
          disabled={pending}
          className={`w-[360px] max-w-full rounded-lg border border-control-border bg-surface px-[11px] text-text-primary ${kind === "trace" ? "h-[34px] text-[13px]" : "h-9 text-sm"}`}
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={pending || !value.trim()}
          className={`min-h-9! px-2! py-1.5! ${kind === "trace" ? "w-[104px]" : "w-[124px]"}`}
        >
          {pending ? `Opening ${kind}…` : `Open ${kind}`}
        </Button>
      </div>
      <details className="operator-workspace-override mt-2 text-xs text-text-muted">
        <summary>Exact Workspace ID (optional)</summary>
        <label htmlFor={`operator-${kind}-workspace`} className="mt-2 block">
          Workspace ID
        </label>
        <input
          id={`operator-${kind}-workspace`}
          name="workspaceId"
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          disabled={pending}
          className="mt-1 h-9 w-[360px] max-w-full rounded-lg border border-control-border bg-surface px-3 text-sm"
        />
      </details>
      {error && (
        <p role="alert" className="mt-2 text-sm text-signature">
          {error}
        </p>
      )}
    </form>
  );
}
