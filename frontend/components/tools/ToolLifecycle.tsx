"use client";
export type ToolLifecycle = { proposal?: string; approval?: string; execution?: string; reconciliation?: string };
export function ToolLifecycleDisplay({ lifecycle }: { lifecycle: ToolLifecycle }) {
  return <section aria-label="Tool lifecycle"><h2>Tool lifecycle</h2><dl>{(["proposal", "approval", "execution", "reconciliation"] as const).map((key) => <div key={key}><dt>{key}</dt><dd>{lifecycle[key] ?? "not recorded"}</dd></div>)}</dl><p>Read-only display. Actions are controlled by the operator surface.</p></section>;
}
