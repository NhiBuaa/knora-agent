"use client";
import React from "react";
import Link from "next/link";
import type { CitationResponse } from "@/generated/knora-openapi";
import { routes } from "@/lib/navigation/routes";

export function CitationViewer({
  citations,
  workspaceId,
}: {
  citations: CitationResponse[];
  workspaceId?: string;
}) {
  if (!citations.length) return null;
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
