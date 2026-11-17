"use client";

import React, { createContext, useContext, useMemo } from "react";
import Markdown from "react-markdown";
import type { Element, Root, RootContent } from "hast";
import type { CitationResponse } from "@/generated/knora-openapi";
import { CitationChip } from "@/components/citations/CitationViewer";
import { validateAnswerCitations } from "@/lib/conversations/message-copy";

type CitationContextValue = {
  citations: CitationResponse[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
};

const CitationContext = createContext<CitationContextValue>({
  citations: [],
  selectedIndex: null,
  onSelect: () => {},
});

function CitationSpanChip({ node }: { node?: Element }) {
  const { citations, selectedIndex, onSelect } = useContext(CitationContext);
  const index = Number(node?.properties?.["data-citation-index"]);
  return (
    <CitationChip
      citation={citations[index]}
      index={index}
      selected={selectedIndex === index}
      onSelect={() => onSelect(index)}
    />
  );
}

const markdownComponents = {
  span: CitationSpanChip,
};

const allowedMarkdownElements = [
  "p",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "blockquote",
  "code",
  "pre",
  "br",
  "hr",
  "span",
];

export function AnswerContent({
  answer,
  citations,
  selectedIndex,
  onSelect,
}: {
  answer: string;
  citations: CitationResponse[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}) {
  const contextValue = useMemo<CitationContextValue>(
    () => ({ citations, selectedIndex, onSelect }),
    [citations, selectedIndex, onSelect],
  );

  const isValid = useMemo(
    () => validateAnswerCitations(answer, citations),
    [answer, citations],
  );

  const { markdown, citationPlugin } = useMemo(() => {
    if (!isValid) return { markdown: "", citationPlugin: null };
    const markers = Array.from(answer.matchAll(/\[\[([^]*?)\]\]/g));
    const indexes = markers.map((marker) =>
      citations.findIndex((citation) => citation.evidence_id === marker[1]),
    );

    // Protect validated markers before Markdown can consume bracket syntax.
    let prefix = "\uE000";
    while (answer.includes(prefix)) prefix += "\uE000";
    let markerIndex = 0;
    const transformedMarkdown = answer.replace(
      /\[\[([^]*?)\]\]/g,
      () => `${prefix}${indexes[markerIndex++]}\uE001`,
    );

    function createCitationPlugin() {
      return (tree: Root) => {
        let renderedMarkers = 0;
        let invalid = false;
        function visit(parent: Root | Element) {
          parent.children = parent.children.flatMap((node): RootContent[] => {
            if (node.type === "element") visit(node);
            if (node.type !== "text" && node.type !== "raw") return [node];
            // Keep source HTML inert, including any markers inside it.
            return node.value
              .split(new RegExp(`(${prefix}[0-9]+\uE001)`, "g"))
              .map((value) => {
                if (!value.startsWith(prefix)) {
                  if (value.includes("[[")) invalid = true;
                  return { type: "text", value };
                }
                const index = Number(value.slice(prefix.length, -1));
                if (!indexes.includes(index)) invalid = true;
                renderedMarkers++;
                return {
                  type: "element",
                  tagName: "span",
                  properties: { "data-citation-index": index },
                  children: [],
                };
              });
          }) as typeof parent.children;
        }
        visit(tree);
        if (invalid || renderedMarkers !== markers.length) {
          tree.children = [
            {
              type: "element",
              tagName: "p",
              properties: { role: "alert" },
              children: [{ type: "text", value: "GENERATION_OUTPUT_INVALID" }],
            },
          ];
        }
      };
    }

    return {
      markdown: transformedMarkdown,
      citationPlugin: createCitationPlugin,
    };
  }, [answer, citations, isValid]);

  const rehypePlugins = useMemo(
    () => (citationPlugin ? [citationPlugin] : []),
    [citationPlugin],
  );

  const memoizedMarkdownContent = useMemo(() => {
    if (!isValid) return null;
    return (
      <Markdown
        skipHtml
        allowedElements={allowedMarkdownElements}
        unwrapDisallowed
        rehypePlugins={rehypePlugins}
        components={markdownComponents}
      >
        {markdown}
      </Markdown>
    );
  }, [markdown, rehypePlugins, isValid]);

  if (!isValid) {
    return <p role="alert">GENERATION_OUTPUT_INVALID</p>;
  }

  return (
    <CitationContext.Provider value={contextValue}>
      <div className="space-y-3 break-words text-sm leading-[22px] [&_h1]:text-lg [&_h2]:text-base [&_h3]:text-base [&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold [&_ol]:list-decimal [&_ul]:list-disc [&_ol]:pl-6 [&_ul]:pl-6 [&_li]:my-1 [&_p]:whitespace-pre-wrap [&_pre]:whitespace-pre-wrap">
        {memoizedMarkdownContent}
      </div>
    </CitationContext.Provider>
  );
}
