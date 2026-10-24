import type { CitationResponse } from "@/generated/knora-openapi";
import { routes } from "@/lib/navigation/routes";

function escapeMarkdownLabel(label: string): string {
  return label.replace(/\[/g, "\\[").replace(/\]/g, "\\]");
}

function formatCitationLabel(citation: CitationResponse): string {
  if (citation.page_start != null) {
    return `${citation.source_name}, p.${citation.page_start}`;
  }
  const lastHeading = citation.heading_path?.at(-1);
  if (lastHeading) {
    return `${citation.source_name}, ${lastHeading}`;
  }
  return citation.source_name;
}

export function validateAnswerCitations(
  answer: string,
  citations: CitationResponse[],
): boolean {
  if (!answer || typeof answer !== "string" || !answer.trim()) {
    return false;
  }
  const markers = Array.from(answer.matchAll(/\[\[([^]*?)\]\]/g));
  const indexes = markers.map((marker) =>
    citations.findIndex((citation) => citation.evidence_id === marker[1]),
  );

  // A missing projection is an explicit contract failure, never a hidden citation.
  if (
    answer.replace(/\[\[([^]*?)\]\]/g, "").includes("[[") ||
    markers.some((marker) => !/^E[1-9][0-9]*$/.test(marker[1])) ||
    indexes.some((index) => index < 0) ||
    new Set(indexes).size !== indexes.length
  ) {
    return false;
  }
  return true;
}

/**
 * Transforms an answered message markdown into a copyable Markdown string
 * replacing validated citation markers [[E#]] with canonical markdown links.
 * Returns null if the answer is empty or violates citation projection contracts.
 */
export function copyableAnswerMarkdown(
  answer: string,
  citations: CitationResponse[],
  workspaceId: string,
  origin: string,
): string | null {
  if (!validateAnswerCitations(answer, citations)) {
    return null;
  }

  const baseUrl = origin ? origin.replace(/\/+$/, "") : "";
  return answer.replace(/\[\[([^]*?)\]\]/g, (_match, evidenceId) => {
    const citation = citations.find((c) => c.evidence_id === evidenceId);
    if (!citation) {
      return "";
    }
    const label = formatCitationLabel(citation);
    const escapedLabel = escapeMarkdownLabel(label);
    const docUrl = `${baseUrl}${routes.document(workspaceId, citation.document_id)}`;
    return `[${escapedLabel}](${docUrl})`;
  });
}
