import tiktoken

from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor


def test_process_normalizes_content_and_preserves_citation_metadata() -> None:
    processor = DocumentProcessor()
    configuration = ChunkingConfiguration.milestone_one()

    result = processor.process(
        raw_content=(b"# Refund policy\r\n\r\nCustomers may request a refund within 30 days.\r\n"),
        media_type="text/markdown",
        configuration=configuration,
    )

    assert result.normalized_content == (
        "# Refund policy\n\nCustomers may request a refund within 30 days.\n"
    )
    assert result.normalized_content_checksum == (
        "18cef69f90d7833bbe27f6df61ca0842891a3d5e7b4177e847e6b296651d523c"
    )
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.ordinal == 0
    assert chunk.heading_path == ("Refund policy",)
    assert (chunk.start_line, chunk.end_line) == (3, 3)
    assert chunk.content == "Customers may request a refund within 30 days."
    assert chunk.token_count > 0
    assert len(chunk.content_checksum) == 64


def test_process_splits_oversized_paragraph_with_token_overlap() -> None:
    configuration = ChunkingConfiguration.milestone_one()
    processor = DocumentProcessor()

    result = processor.process(
        raw_content=("# Long section\n\n" + "word " * 800).encode(),
        media_type="text/markdown",
        configuration=configuration,
    )

    assert len(result.chunks) == 2
    assert all(chunk.token_count <= configuration.max_tokens for chunk in result.chunks)
    tokenizer = tiktoken.get_encoding(configuration.tokenizer_name)
    first_tokens = tokenizer.encode(result.chunks[0].content)
    second_tokens = tokenizer.encode(result.chunks[1].content)
    assert (
        first_tokens[-configuration.overlap_tokens :]
        == second_tokens[: configuration.overlap_tokens]
    )
    assert result.chunks[1].heading_path == ("Long section",)
