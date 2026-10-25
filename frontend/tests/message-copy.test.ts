import { describe, expect, it } from "vitest";
import type { CitationResponse } from "@/generated/knora-openapi";
import { copyableAnswerMarkdown } from "@/lib/conversations/message-copy";

const mockCitation = (
  overrides: Partial<CitationResponse> = {},
): CitationResponse => ({
  evidence_id: "E1",
  document_id: "doc-123",
  document_version_id: "ver-456",
  source_name: "Hướng dẫn sử dụng",
  source_key: "manual.pdf",
  content_checksum: "sha256-abc",
  heading_path: ["Chương 1", "Mục 2"],
  page_start: 5,
  page_end: 5,
  start_line: 10,
  end_line: 25,
  excerpt: "Nội dung trích dẫn mẫu",
  ...overrides,
});

describe("copyableAnswerMarkdown", () => {
  it("keeps Vietnamese Markdown without citations unchanged", () => {
    const answer = "Tiếng Việt\n\n- Một\n- Hai\n\n```ts\nconst n = 1;\n```";
    expect(
      copyableAnswerMarkdown(answer, [], "ws", "http://localhost:3300"),
    ).toBe(answer);
  });

  it("returns null for empty answer", () => {
    expect(
      copyableAnswerMarkdown("", [], "ws", "http://localhost:3300"),
    ).toBeNull();
  });

  it("rejects an unprojected citation instead of hiding its marker", () => {
    expect(
      copyableAnswerMarkdown("Nguồn [[E1]]", [], "ws", "http://localhost:3300"),
    ).toBeNull();
  });

  it("rejects malformed citation markers", () => {
    expect(
      copyableAnswerMarkdown(
        "Nguồn [[invalid]]",
        [mockCitation()],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
    expect(
      copyableAnswerMarkdown(
        "Nguồn [[E0]]",
        [mockCitation()],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
    expect(
      copyableAnswerMarkdown(
        "Chưa đóng marker [[E1",
        [mockCitation()],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
  });

  it("rejects duplicate marker references to enforce AnswerContent parity", () => {
    const citation = mockCitation();
    expect(
      copyableAnswerMarkdown(
        "Đoạn một [[E1]] và đoạn hai [[E1]]",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
  });

  it("replaces valid citation marker with markdown link using source name and page", () => {
    const citation = mockCitation({
      evidence_id: "E1",
      document_id: "doc-123",
      source_name: "Tài liệu kỹ thuật",
      page_start: 12,
    });
    const answer = "Theo báo cáo [[E1]], hệ thống hoạt động ổn định.";
    const result = copyableAnswerMarkdown(
      answer,
      [citation],
      "ws-abc",
      "http://localhost:3300",
    );
    expect(result).toBe(
      "Theo báo cáo [Tài liệu kỹ thuật, p.12](http://localhost:3300/workspaces/ws-abc/documents/doc-123), hệ thống hoạt động ổn định.",
    );
  });

  it("replaces valid citation marker with heading when page is absent", () => {
    const citation = mockCitation({
      evidence_id: "E1",
      document_id: "doc-456",
      source_name: "Hướng dẫn cài đặt",
      page_start: null,
      page_end: null,
      heading_path: ["Cài đặt", "Bước 1"],
    });
    const answer = "Xem chi tiết tại [[E1]].";
    const result = copyableAnswerMarkdown(
      answer,
      [citation],
      "ws-abc",
      "http://localhost:3300",
    );
    expect(result).toBe(
      "Xem chi tiết tại [Hướng dẫn cài đặt, Bước 1](http://localhost:3300/workspaces/ws-abc/documents/doc-456).",
    );
  });

  it("falls back to source_name when neither page nor heading is present", () => {
    const citation = mockCitation({
      evidence_id: "E1",
      document_id: "doc-789",
      source_name: "Ghi chú nhanh",
      page_start: null,
      page_end: null,
      heading_path: [],
    });
    const answer = "Thông tin từ [[E1]].";
    const result = copyableAnswerMarkdown(
      answer,
      [citation],
      "ws-abc",
      "http://localhost:3300",
    );
    expect(result).toBe(
      "Thông tin từ [Ghi chú nhanh](http://localhost:3300/workspaces/ws-abc/documents/doc-789).",
    );
  });

  it("escapes markdown brackets and backslashes in citation labels", () => {
    const citation = mockCitation({
      evidence_id: "E1",
      document_id: "doc-1",
      source_name: "Guide \\[private]",
      page_start: null,
      page_end: null,
      heading_path: [],
    });
    const answer = "Dẫn xuất từ [[E1]].";
    const result = copyableAnswerMarkdown(
      answer,
      [citation],
      "ws-1",
      "http://localhost:3300",
    );
    expect(result).toBe(
      "Dẫn xuất từ [Guide \\\\\\[private\\]](http://localhost:3300/workspaces/ws-1/documents/doc-1).",
    );
  });

  it("fails closed on HTML entities that simulate brackets or markers", () => {
    const citation = mockCitation({ evidence_id: "E1" });
    expect(
      copyableAnswerMarkdown(
        "&#91;&#91;E99&#93;&#93; [[E1]]",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
  });

  it("fails closed on Private Use Area characters used by renderer", () => {
    const citation = mockCitation({ evidence_id: "E1" });
    expect(
      copyableAnswerMarkdown(
        "&#xE000;99&#xE001; [[E1]]",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
    expect(
      copyableAnswerMarkdown(
        "\uE00099\uE001 [[E1]]",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
  });

  it("fails closed on citation markers inside markdown links, images, or raw HTML tags", () => {
    const citation = mockCitation({ evidence_id: "E1" });
    expect(
      copyableAnswerMarkdown(
        "[text](https://example.com/[[E1]])",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
    expect(
      copyableAnswerMarkdown(
        "![alt](https://example.com/[[E1]])",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
    expect(
      copyableAnswerMarkdown(
        "<!-- [[E1]] --> [[E1]]",
        [citation],
        "ws",
        "http://localhost:3300",
      ),
    ).toBeNull();
  });

  it("transforms validated markers inside code fences into links according to renderer rules", () => {
    const citation = mockCitation({
      evidence_id: "E1",
      document_id: "doc-123",
      source_name: "Tài liệu",
      page_start: 5,
    });
    const answer = "```ts\nconst x = '[[E1]]';\n```";
    expect(
      copyableAnswerMarkdown(answer, [citation], "ws", "http://localhost:3300"),
    ).toBe(
      "```ts\nconst x = '[Tài liệu, p.5](http://localhost:3300/workspaces/ws/documents/doc-123)';\n```",
    );
  });

  it("fails closed if unvalidated marker appears inside code fence", () => {
    const citation = mockCitation({ evidence_id: "E1" });
    const answer = "```ts\nconst x = '[[E99]]';\n```";
    expect(
      copyableAnswerMarkdown(answer, [citation], "ws", "http://localhost:3300"),
    ).toBeNull();
  });
});
