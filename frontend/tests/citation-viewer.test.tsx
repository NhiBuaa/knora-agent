import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CitationViewer } from "@/components/citations/CitationViewer";

describe("CitationViewer", () => {
  it("renders the exact citation projection fields", () => {
    render(
      <CitationViewer
        citations={[
          {
            evidence_id: "E1",
            document_id: "doc-1",
            document_version_id: "ver-1",
            source_key: "guide.pdf",
            source_name: "Guide",
            heading_path: ["Intro"],
            start_line: 2,
            end_line: 4,
            excerpt: "Evidence",
            content_checksum: "sha",
            page_start: 1,
            page_end: 1,
            start_offset: 3,
            end_offset: 11,
          },
        ]}
      />,
    );
    expect(screen.getByText("Guide")).toBeInTheDocument();
    expect(screen.getByText("Evidence", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/lines 2–4/)).toBeInTheDocument();
    expect(screen.getByText(/page 1/)).toBeInTheDocument();
  });
});
