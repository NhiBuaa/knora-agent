"use client";
import React from "react";
import Link from "next/link";
import type { CitationResponse } from "@/generated/knora-openapi";
import { routes } from "@/lib/navigation/routes";

export function CitationViewer({
  citations,
  workspaceId,
  onSelect,
  selectedIndex = null,
}: {
  citations: CitationResponse[];
  workspaceId?: string;
  onSelect?: (index: number) => void;
  selectedIndex?: number | null;
}) {
  if (!citations.length) return null;
  if (onSelect)
    return (
      <div aria-label="Citations" className="flex flex-wrap gap-[7px]">
        {citations.map((citation, index) => (
          <button
            type="button"
            key={`${index}:${citation.evidence_id}`}
            aria-label={`Citation ${index + 1}: ${citation.source_name}`}
            aria-pressed={selectedIndex === index}
            onClick={() => onSelect(index)}
            className={
              selectedIndex === index
                ? "m-0 rounded-full border border-action bg-action/10 px-2 py-1 text-[11px] font-medium text-action-text"
                : "m-0 rounded-full border border-border bg-surface-subtle px-2 py-1 text-[11px] font-medium text-text-muted"
            }
          >
            [{String(index + 1).padStart(2, "0")}]{" "}
            {citation.page_start != null
              ? `p.${citation.page_start}`
              : citation.heading_path.at(-1) || citation.source_name}
          </button>
        ))}
      </div>
    );
  return (
    <section aria-label="Citations">
      <h2>Sources</h2>
      <ol>
        {citations.map((citation) => (
          <li
            key={citation.evidence_id}
            data-testid={`citation-${citation.evidence_id}`}
          >
            <strong>
              {workspaceId ? (
                <Link href={routes.document(workspaceId, citation.document_id)}>
                  {citation.source_name}
                </Link>
              ) : (
                citation.source_name
              )}
            </strong>
            <span> ({citation.source_key})</span>
            <p>{citation.excerpt}</p>
            <small>
              {citation.heading_path.join(" / ")} · lines {citation.start_line}–
              {citation.end_line}
              {citation.page_start != null
                ? ` · page ${citation.page_start}${citation.page_end && citation.page_end !== citation.page_start ? `–${citation.page_end}` : ""}`
                : ""}
            </small>
            <details>
              <summary>Provenance</summary>
              <dl>
                <dt>Evidence</dt>
                <dd>{citation.evidence_id}</dd>
                <dt>Document version</dt>
                <dd>{citation.document_version_id}</dd>
                <dt>Checksum</dt>
                <dd>{citation.content_checksum}</dd>
                <dt>Offsets</dt>
                <dd>
                  {citation.start_offset ?? "—"}–{citation.end_offset ?? "—"}
                </dd>
              </dl>
            </details>
          </li>
        ))}
      </ol>
    </section>
  );
}
