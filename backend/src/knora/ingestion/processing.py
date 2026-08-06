from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True, slots=True)
class ChunkingConfiguration:
    id: str
    parser_version: str
    chunker_version: str
    tokenizer_name: str
    tokenizer_version: str
    target_tokens: int
    overlap_tokens: int
    max_tokens: int

    @classmethod
    def milestone_one(cls) -> ChunkingConfiguration:
        return cls(
            id="chunking-m1-v1",
            parser_version="markdown-text-v1",
            chunker_version="heading-paragraph-v1",
            tokenizer_name="cl100k_base",
            tokenizer_version="tiktoken-0.12.0",
            target_tokens=500,
            overlap_tokens=75,
            max_tokens=650,
        )



@dataclass(frozen=True, slots=True)
class PreparedChunk:
    ordinal: int
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    content: str
    content_checksum: str
    token_count: int


@dataclass(frozen=True, slots=True)
class ProcessedDocument:
    normalized_content: str
    normalized_content_checksum: str
    normalized_token_count: int
    chunks: tuple[PreparedChunk, ...]


class DocumentProcessor:
    _heading = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def process(
        self,
        *,
        raw_content: bytes,
        media_type: str,
        configuration: ChunkingConfiguration,
    ) -> ProcessedDocument:
        if media_type not in {"text/markdown", "text/plain"}:
            raise ValueError("UNSUPPORTED_DOCUMENT_TYPE")

        normalized = raw_content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        tokenizer = tiktoken.get_encoding(configuration.tokenizer_name)
        heading_path: list[str] = []
        paragraphs: list[tuple[tuple[str, ...], int, int, str]] = []
        paragraph_lines: list[str] = []
        paragraph_start = 0

        def flush(end_line: int) -> None:
            nonlocal paragraph_lines, paragraph_start
            content = "\n".join(paragraph_lines).strip()
            if content:
                paragraphs.append((tuple(heading_path), paragraph_start, end_line, content))
            paragraph_lines = []
            paragraph_start = 0

        for line_number, line in enumerate(normalized.splitlines(), start=1):
            heading = self._heading.match(line) if media_type == "text/markdown" else None
            if heading:
                flush(line_number - 1)
                level = len(heading.group(1))
                heading_path[level - 1 :] = [heading.group(2)]
                continue
            if not line.strip():
                flush(line_number - 1)
                continue
            if not paragraph_lines:
                paragraph_start = line_number
            paragraph_lines.append(line)
        flush(len(normalized.splitlines()))

        prepared: list[PreparedChunk] = []
        for headings, start_line, end_line, content in paragraphs:
            tokens = tokenizer.encode(content)
            if len(tokens) <= configuration.max_tokens:
                pieces = [tokens]
            else:
                step = configuration.target_tokens - configuration.overlap_tokens
                pieces = [
                    tokens[offset : offset + configuration.target_tokens]
                    for offset in range(0, len(tokens), step)
                ]
                if len(pieces) > 1 and len(pieces[-1]) <= configuration.overlap_tokens:
                    pieces.pop()
            for piece in pieces:
                piece_content = tokenizer.decode(piece)
                prepared.append(
                    PreparedChunk(
                        ordinal=len(prepared),
                        heading_path=headings,
                        start_line=start_line,
                        end_line=end_line,
                        content=piece_content,
                        content_checksum=hashlib.sha256(piece_content.encode("utf-8")).hexdigest(),
                        token_count=len(piece),
                    )
                )
        chunks = tuple(prepared)
        return ProcessedDocument(
            normalized_content=normalized,
            normalized_content_checksum=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            normalized_token_count=len(tokenizer.encode(normalized)),
            chunks=chunks,
        )
