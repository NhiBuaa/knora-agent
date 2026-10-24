import type { CitationResponse } from "@/generated/knora-openapi";
import { routes } from "@/lib/navigation/routes";

function escapeMarkdownLabel(label: string): string {
  return label
    .replace(/\\/g, "\\\\")
    .replace(/\[/g, "\\[")
    .replace(/\]/g, "\\]");
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

  // Reject Private Use Area characters used internally by the markdown citation plugin
  if (/[\uE000-\uF8FF]/.test(answer)) {
    return false;
  }

  // Reject markers embedded inside Markdown link URLs, images, or raw HTML
  if (/\[[^\]]*\]\([^)]*\[\[[^)]*\)/.test(answer)) {
    return false;
  }
  if (/!\[[^\]]*\]\([^)]*\[\[[^)]*\)/.test(answer)) {
    return false;
  }
  if (/<!--[^]*?\[\[[^]*?-->/.test(answer)) {
    return false;
  }
  if (/<[a-zA-Z0-9_-]+[^>]*\[\[[^>]*>/.test(answer)) {
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

  // Detect encoded entities that decode to bracket sequences or PUA markers
  if (/&(?:#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);/i.test(answer)) {
    const decoded = answer
      .replace(/&#x([0-9a-fA-F]+);/gi, (_, h) => {
        try {
          return String.fromCodePoint(parseInt(h, 16));
        } catch {
          return "";
        }
      })
      .replace(/&#([0-9]+);/g, (_, d) => {
        try {
          return String.fromCodePoint(parseInt(d, 10));
        } catch {
          return "";
        }
      })
      .replace(/&lsqb;/gi, "[")
      .replace(/&rsqb;/gi, "]");
    if (
      /[\uE000-\uF8FF]/.test(decoded) ||
      decoded.replace(/\[\[([^]*?)\]\]/g, "").includes("[[") ||
      Array.from(decoded.matchAll(/\[\[([^]*?)\]\]/g)).length !== markers.length
    ) {
      return false;
    }
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
