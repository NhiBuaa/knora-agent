"use client";

import React, { useEffect, useState } from "react";
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
    <main className="workspace-shell-main operator-surface mx-auto w-full max-w-[1200px] px-0 pt-11 pb-10 text-text-primary max-[1248px]:px-6 max-md:px-4">
      <div className="w-[220px] max-w-full">
        <WorkspaceSelector
          workspaceId={workspaceId}
          workspaceName={workspaceName}
        />
      </div>
      <h1 className="mt-3.5 mb-0 font-display text-[32px] leading-[42px] font-semibold">
        {SECTIONS[active].title}
      </h1>
      <p className="mt-1 mb-0 text-base leading-6 text-text-muted">
        {SECTIONS[active].description}
      </p>
      <nav
        aria-label="Operator navigation"
        className="mt-6 mb-0 flex h-[43px] items-center gap-7 border-b border-border text-sm"
      >
        {Object.entries(SECTIONS).map(([key]) => (
          <Link
            key={key}
            href={`/operator/${key}${target ? `?workspaceId=${encodeURIComponent(target)}` : ""}`}
            aria-current={key === active ? "page" : undefined}
            className={`border-b-2 pt-1 pb-2 no-underline ${key === active ? "border-action font-semibold text-action-text" : "border-transparent text-text-muted"}`}
          >
            {key[0].toUpperCase() + key.slice(1)}
          </Link>
        ))}
      </nav>
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
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setValue(identifier);
    setTarget(workspaceId ?? "");
    setPending(false);
    setError(null);
  }, [identifier, workspaceId, pathname, query]);
  const label = kind === "trace" ? "Trace ID" : "Report ID";
  return (
    <form
      className="mt-[18px] mb-0"
      aria-label={`${kind === "trace" ? "Trace" : "Report"} lookup`}
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim() || pending) return;
        setPending(true);
        setError(null);
        try {
          router.push(
            `/operator/${kind === "trace" ? "traces" : "evaluations"}/${encodeURIComponent(value.trim())}${target.trim() ? `?workspaceId=${encodeURIComponent(target.trim())}` : ""}`,
          );
        } catch {
          setPending(false);
          setError(`Unable to open ${kind}. Retry.`);
        }
      }}
    >
      <label
        htmlFor={`operator-${kind}-id`}
        className="block text-[11px] leading-[13px] font-semibold text-text-muted uppercase"
      >
        {label}
      </label>
      <div className="mt-[5px] flex flex-wrap items-center gap-3">
        <input
          id={`operator-${kind}-id`}
          name={kind === "trace" ? "traceId" : "reportId"}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          required
          disabled={pending}
          className="h-9 w-[360px] max-w-full rounded-lg border border-control-border bg-surface px-[11px] text-sm text-text-primary"
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={pending || !value.trim()}
          className="min-h-9 py-1.5"
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
