from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from knora.adapters.pdf.docling import (
    DoclingExtractionConfiguration,
    DoclingTextExtractor,
)
from knora.ingestion.pdf import PdfExtractionError
from knora.ingestion.pdf_structure import BlockType, SourceOrigin
from knora.providers.cloudflare.pdf_understanding import (
    CloudflarePdfUnderstandingProvider,
    CloudflareVisionOcrResponse,
)


def test_docling_config_defaults_and_pins() -> None:
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    assert config.parser_version == "docling-native-cf-v1"
    assert config.extraction_options_version == "cf-tomarkdown-moondream-v1"
    assert config.cloudflare_ocr_model == "@cf/moondream/moondream3.1-9B-A2B"
    assert config.enable_local_models is False
    assert config.derivation_identity is not None


def test_rejects_local_model_activation() -> None:
    with pytest.raises(
        ValueError, match="local models and weights downloads are strictly prohibited"
    ):
        DoclingExtractionConfiguration(
            parser_version="docling-test",
            extraction_options_version="test",
            normalizer_version="test",
            tokenizer_name="cl100k_base",
            tokenizer_version="tiktoken-0.12.0",
            chunking_policy_version="page-block-v1",
            target_tokens=500,
            overlap_tokens=75,
            max_tokens=650,
            max_raw_bytes=25 * 1024 * 1024,
            max_pages=500,
            max_page_stream_bytes=4 * 1024 * 1024,
            max_total_stream_bytes=64 * 1024 * 1024,
            extraction_timeout_seconds=30.0,
            extractor_memory_bytes=256 * 1024 * 1024,
            minimum_extracted_characters=1,
            enable_local_models=True,  # Prohibited!
        )


def test_cloudflare_provider_blocks_non_cloudflare_endpoints() -> None:
    with pytest.raises(ValueError, match="invalid cloudflare_account_id"):
        CloudflarePdfUnderstandingProvider(
            account_id="invalid_id_not_32_hex",
            api_token="test_token",
        )


def test_cloudflare_provider_parses_tomarkdown_response() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "result": [
            {
                "name": "document.pdf",
                "format": "markdown",
                "data": "# Document Title\n\nFirst paragraph.",
            }
        ],
    }
    mock_response.headers = {"cf-ray": "ray_123"}
    mock_client.post.return_value = mock_response

    provider = CloudflarePdfUnderstandingProvider(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret_token",
        client=mock_client,
    )
    result = provider.convert_to_markdown(b"%PDF-sample")
    assert result.content == "# Document Title\n\nFirst paragraph."
    assert result.format == "markdown"
    assert result.request_id == "ray_123"


def test_cloudflare_provider_handles_rate_limits() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = Exception("429 Too Many Requests")
    mock_client.post.return_value = mock_response

    provider = CloudflarePdfUnderstandingProvider(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret_token",
        client=mock_client,
    )
    with pytest.raises(PdfExtractionError) as exc_info:
        provider.convert_to_markdown(b"%PDF-sample")
    assert exc_info.value.code == "PDF_EXTRACTOR_UNAVAILABLE"
    assert exc_info.value.retryable is True


def test_docling_extractor_native_conversion_with_cf_provider() -> None:
    mock_provider = MagicMock(spec=CloudflarePdfUnderstandingProvider)
    sample_content = (
        "# Section 1\n\nThis is native text extracted cleanly.\n\n"
        "| H1 | H2 |\n| --- | --- |\n| A | B |"
    )
    mock_provider.convert_to_markdown.return_value = MagicMock(
        content=sample_content,
        format="markdown",
        request_id="cf_ray_001",
    )

    extractor = DoclingTextExtractor(cf_provider=mock_provider)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    pdf_bytes = b"%PDF-1.4 sample content with sufficient length for testing"

    result = extractor.extract(BytesIO(pdf_bytes), config)

    assert len(result.pages) >= 1
    assert result.structure is not None
    assert result.structure.is_complete is False
    assert result.structure.completeness_status == "INCOMPLETE"
    assert len(result.structure.pages[0].blocks) >= 2
    # Check that headings and paragraphs are recognized
    heading_blocks = [
        b for b in result.structure.pages[0].blocks if b.block_type == BlockType.HEADING
    ]
    assert len(heading_blocks) >= 1
    assert heading_blocks[0].text == "# Section 1"
    assert heading_blocks[0].heading_path == ("Section 1",)
    # Content matches slice
    for b in result.structure.pages[0].blocks:
        assert result.structure.pages[0].text[b.start_offset : b.end_offset] == b.text


def test_selective_ocr_only_triggers_on_scanned_or_insufficient_pages() -> None:
    mock_provider = MagicMock(spec=CloudflarePdfUnderstandingProvider)
    # Return OCR output for scanned page
    mock_provider.ocr_page_image.return_value = CloudflareVisionOcrResponse(
        text="Scanned text recovered by Cloudflare OCR.",
        confidence=0.95,
        request_id="cf_ocr_002",
    )

    extractor = DoclingTextExtractor(cf_provider=mock_provider)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    # For a page with zero native text, selective OCR should be invoked
    scanned_page = extractor._process_single_page(
        page_number=1,
        native_text="",
        page_image_bytes=b"fake_jpeg_image",
        config=config,
    )

    assert scanned_page.blocks[0].source_origin == SourceOrigin.OCR
    assert "Scanned text recovered" in scanned_page.text
    mock_provider.ocr_page_image.assert_called_once()


def _create_test_pdf(*pages: str) -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        commands = ["BT /F1 12 Tf"]
        for index, line in enumerate(text.splitlines()):
            line = line or " "
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"1 0 0 1 72 {720 - index * 18} Tm ({escaped}) Tj")
        commands.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_docling_extractor_multi_page_physical_extraction() -> None:
    pdf_bytes = _create_test_pdf(
        "Page 1 native text with information.\n\n# Section 1",
        "Page 2 independent text with another topic.\n\n# Section 2",
    )
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)

    assert len(result.pages) == 2
    assert result.structure is not None
    assert len(result.structure.pages) == 2

    page1 = result.structure.pages[0]
    page2 = result.structure.pages[1]
    assert page1.page_number == 1
    assert "Page 1 native text" in page1.text
    assert page2.page_number == 2
    assert "Page 2 independent text" in page2.text

    # Chunks on page 2 must have page_number 2 and never reference page 1
    p2_chunks = [c for c in result.chunks if c.page_number == 2]
    assert len(p2_chunks) >= 1
    for c in p2_chunks:
        assert c.page_start == 2
        assert c.page_end == 2
        assert "Page 1" not in c.content


def test_docling_resource_limits_max_raw_bytes() -> None:
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration(
        parser_version="docling-test",
        extraction_options_version="test",
        normalizer_version="test",
        tokenizer_name="cl100k_base",
        tokenizer_version="tiktoken-0.12.0",
        chunking_policy_version="page-block-v1",
        target_tokens=500,
        overlap_tokens=75,
        max_tokens=650,
        max_raw_bytes=100,  # small limit
        max_pages=500,
        max_page_stream_bytes=4 * 1024 * 1024,
        max_total_stream_bytes=64 * 1024 * 1024,
        extraction_timeout_seconds=30.0,
        extractor_memory_bytes=256 * 1024 * 1024,
        minimum_extracted_characters=1,
    )
    large_stream = BytesIO(b"x" * 200)
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(large_stream, config)
    assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert exc_info.value.reason == "RAW_FILE_SIZE"


def test_docling_resource_limits_max_pages() -> None:
    pdf_bytes = _create_test_pdf("P1 text", "P2 text", "P3 text")
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration(
        parser_version="docling-test",
        extraction_options_version="test",
        normalizer_version="test",
        tokenizer_name="cl100k_base",
        tokenizer_version="tiktoken-0.12.0",
        chunking_policy_version="page-block-v1",
        target_tokens=500,
        overlap_tokens=75,
        max_tokens=650,
        max_raw_bytes=25 * 1024 * 1024,
        max_pages=2,  # Limit is 2, but PDF has 3 pages
        max_page_stream_bytes=4 * 1024 * 1024,
        max_total_stream_bytes=64 * 1024 * 1024,
        extraction_timeout_seconds=30.0,
        extractor_memory_bytes=256 * 1024 * 1024,
        minimum_extracted_characters=1,
    )
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(BytesIO(pdf_bytes), config)
    assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert exc_info.value.reason == "PAGE_COUNT"


def test_three_newline_and_multiline_block_offsets() -> None:
    import hashlib

    from knora.ingestion.pdf_structure import (
        CanonicalDocument,
        CanonicalPage,
        validate_canonical_document,
    )

    extractor = DoclingTextExtractor()
    text = "First paragraph.\n\n\nSecond paragraph.\r\n\r\nThird paragraph."
    blocks = extractor._parse_page_blocks(1, text, SourceOrigin.NATIVE_TEXT)
    page = CanonicalPage(
        page_number=1,
        text=text,
        content_checksum=hashlib.sha256(text.encode()).hexdigest(),
        blocks=tuple(blocks),
    )
    doc = CanonicalDocument(
        raw_source_hash="a" * 64,
        derivation_identity="test-identity",
        parser_version="test-parser",
        pages=(page,),
    )
    # validate_canonical_document checks that page.text[b.start_offset : b.end_offset] == b.text
    validate_canonical_document(doc)
    assert len(blocks) == 3
    assert blocks[0].text == "First paragraph."
    assert blocks[1].text == "Second paragraph."
    assert blocks[2].text == "Third paragraph."
    for b in blocks:
        assert text[b.start_offset : b.end_offset] == b.text


def test_unparseable_pdf_conversion_is_incomplete() -> None:
    from knora.providers.cloudflare.pdf_understanding import CloudflareToMarkdownResponse

    class MockConversionProvider:
        def convert_to_markdown(self, raw: bytes) -> CloudflareToMarkdownResponse:
            return CloudflareToMarkdownResponse(
                content="Page one source\n\nPage two source",
                format="markdown",
            )

    extractor = DoclingTextExtractor(cf_provider=MockConversionProvider())  # type: ignore[arg-type]
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    result = extractor.extract(BytesIO(b"%PDF-invalid"), config)

    assert result.structure is not None
    assert result.structure.is_complete is False
    assert result.structure.completeness_status == "INCOMPLETE"
    assert all(p.completeness.is_complete is False for p in result.structure.pages)


def test_stream_caps_1byte_rejected() -> None:
    from dataclasses import replace

    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    capped_config = replace(config, max_page_stream_bytes=1, max_total_stream_bytes=1)

    pdf_bytes = _create_test_pdf("Content stream far greater than one byte.")
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(BytesIO(pdf_bytes), capped_config)
    assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert exc_info.value.reason in ("PAGE_STREAM_SIZE", "TOTAL_STREAM_SIZE")


def _create_test_pdf_with_images(native_text: str, num_images: int = 1) -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
        NumberObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    xobjects = DictionaryObject()
    for idx in range(num_images):
        img_stream = DecodedStreamObject()
        img_stream.set_data(b"\x00" * 100)
        img_stream[NameObject("/Type")] = NameObject("/XObject")
        img_stream[NameObject("/Subtype")] = NameObject("/Image")
        img_stream[NameObject("/Width")] = NumberObject(10)
        img_stream[NameObject("/Height")] = NumberObject(10)
        img_stream[NameObject("/ColorSpace")] = NameObject("/DeviceGray")
        img_stream[NameObject("/BitsPerComponent")] = NumberObject(8)
        xobjects[NameObject(f"/Im{idx + 1}")] = writer._add_object(img_stream)

    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)}),
            NameObject("/XObject"): xobjects,
        }
    )
    commands = ["BT /F1 12 Tf"]
    if native_text.strip():
        for index, line in enumerate(native_text.splitlines()):
            line = line or " "
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"1 0 0 1 72 {720 - index * 18} Tm ({escaped}) Tj")
    commands.append("ET")
    for idx in range(num_images):
        commands.append(f"/Im{idx + 1} Do")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_mixed_page_requires_ocr_and_marks_incomplete_without_provider() -> None:
    # Page with native header AND scanned image
    pdf_bytes = _create_test_pdf_with_images("Header only text for native layer", num_images=1)
    extractor = DoclingTextExtractor(cf_provider=None)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert len(result.pages) == 1
    assert result.structure is not None
    assert result.structure.is_complete is False
    assert result.structure.completeness_status == "INCOMPLETE"
    assert result.structure.pages[0].completeness.is_complete is False
    assert result.structure.pages[0].completeness.reason == "UNPROCESSED_PAGE_IMAGES"


def test_mixed_page_applies_ocr_to_images_and_completes() -> None:
    mock_provider = MagicMock(spec=CloudflarePdfUnderstandingProvider)
    mock_provider.ocr_page_image.return_value = CloudflareVisionOcrResponse(
        text="Scanned body content recovered by OCR.",
        confidence=0.98,
    )
    pdf_bytes = _create_test_pdf_with_images("Header only text for native layer", num_images=1)
    extractor = DoclingTextExtractor(cf_provider=mock_provider)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert result.structure is not None
    assert result.structure.is_complete is True
    assert result.structure.completeness_status == "COMPLETE"
    page = result.structure.pages[0]
    assert page.completeness.is_complete is True
    assert "Header only text" in page.text
    assert "Scanned body content recovered" in page.text
    mock_provider.ocr_page_image.assert_called_once()
    assert {block.origin.value for block in page.blocks} == {"native_text", "ocr"}
    assert all(block.confidence is None for block in page.blocks if block.origin.value == "ocr")
    for block in page.blocks:
        assert page.text[block.start_offset : block.end_offset] == block.text


def test_mixed_page_preserves_region_provenance() -> None:
    mock_provider = MagicMock(spec=CloudflarePdfUnderstandingProvider)
    mock_provider.ocr_page_image.return_value = CloudflareVisionOcrResponse(
        text="OCR extracted region content.",
        confidence=0.95,
    )
    pdf_bytes = _create_test_pdf_with_images("Native text paragraph here", num_images=1)
    extractor = DoclingTextExtractor(cf_provider=mock_provider)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert result.structure is not None
    page = result.structure.pages[0]

    assert {block.origin.value for block in page.blocks} == {"native_text", "ocr"}
    assert all(block.confidence is None for block in page.blocks if block.origin.value == "ocr")
    for block in page.blocks:
        assert page.text[block.start_offset : block.end_offset] == block.text


def test_tiled_scans_all_regions_ocred() -> None:
    mock_provider = MagicMock(spec=CloudflarePdfUnderstandingProvider)
    mock_provider.ocr_page_image.side_effect = [
        CloudflareVisionOcrResponse(text="Tile 1 content", confidence=0.9),
        CloudflareVisionOcrResponse(text="Tile 2 content", confidence=0.9),
    ]
    # No native text, 2 scanned tiles
    pdf_bytes = _create_test_pdf_with_images("", num_images=2)
    extractor = DoclingTextExtractor(cf_provider=mock_provider)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert result.structure is not None
    assert result.structure.is_complete is True
    page = result.structure.pages[0]
    assert "Tile 1 content" in page.text
    assert "Tile 2 content" in page.text
    assert mock_provider.ocr_page_image.call_count == 2


def test_markdown_table_parsing_creates_canonical_table() -> None:
    table_text = (
        "# Document Header\n\n"
        "| Header 1 | Header 2 |\n"
        "| --- | --- |\n"
        "| Cell A1 | Cell A2 |\n"
        "| Cell B1 | Cell B2 |"
    )
    pdf_bytes = _create_test_pdf(table_text)
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert result.structure is not None
    page = result.structure.pages[0]
    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.num_rows == 3  # Header row + 2 data rows
    assert table.num_columns == 2
    assert len(table.cells) == 6
    header_cells = [c for c in table.cells if c.is_header]
    assert len(header_cells) == 2
    assert header_cells[0].text == "Header 1"
    assert header_cells[1].text == "Header 2"


def test_extraction_timeout_enforced() -> None:
    import time
    from dataclasses import replace

    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    # 1 millisecond timeout
    timeout_config = replace(config, extraction_timeout_seconds=0.001)

    # Simulate delay in extract_text by monkeypatching
    from pypdf import PageObject

    original_extract = PageObject.extract_text

    def slow_extract(self: PageObject) -> str:
        time.sleep(0.01)  # 10ms > 1ms timeout
        return original_extract(self)

    pdf_bytes = _create_test_pdf("Some sample text content for page")
    with patch.object(PageObject, "extract_text", slow_extract):
        with pytest.raises(PdfExtractionError) as exc_info:
            extractor.extract(BytesIO(pdf_bytes), timeout_config)
        assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
        assert exc_info.value.reason == "TIMEOUT"


def test_cancellation_enforced() -> None:
    class DummyCancellation:
        def is_cancelled(self) -> bool:
            return True

    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    pdf_bytes = _create_test_pdf("Sample text")
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(BytesIO(pdf_bytes), config, cancellation=DummyCancellation())
    assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert exc_info.value.reason == "CANCELLED"


def test_r2_n02_identity_and_configuration_isolation() -> None:
    from knora.adapters.postgres.ingestion_jobs.coordination import (
        CoordinationInvariantError,
        PostgresIngestionJobCoordinationStore,
    )
    from knora.ingestion.jobs import PdfSubmissionConfiguration
    from knora.providers.embedding import EmbeddingConfiguration

    embed_cfg = EmbeddingConfiguration.cloudflare_qwen3_06b()
    docling_sub = PdfSubmissionConfiguration.docling_native(embedding_configuration=embed_cfg)

    # 1. Submission IDs must match docling native, not pypdf
    assert docling_sub.parser_configuration_id == "pdf-parser-docling-native-cloudflare-v1"
    assert docling_sub.chunking_configuration.id == "chunking-docling-native-cf-v1"
    assert docling_sub.chunking_configuration.parser_version == "docling-native-cf-v1"

    # 2. DoclingTextExtractor rejects pypdf configuration
    from knora.ingestion.pdf import PdfExtractionConfiguration

    pypdf_config = PdfExtractionConfiguration.layout_preserving()
    extractor = DoclingTextExtractor()
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(BytesIO(b"%PDF-1.4"), pypdf_config)  # type: ignore[arg-type]
    assert exc_info.value.code == "PDF_EXTRACTOR_UNAVAILABLE"
    assert exc_info.value.reason == "INCOMPATIBLE_EXTRACTION_CONFIGURATION"

    # 3. Coordination store resolves docling native correctly
    resolved = PostgresIngestionJobCoordinationStore._resolve_extraction_configuration(
        "pdf-parser-docling-native-cloudflare-v1"
    )
    assert isinstance(resolved, DoclingExtractionConfiguration)
    assert resolved.parser_version == "docling-native-cf-v1"

    # 4. Coordination store rejects unknown parser ID
    with pytest.raises(CoordinationInvariantError):
        PostgresIngestionJobCoordinationStore._resolve_extraction_configuration("unknown-parser-id")


def test_docling_extractor_enforces_memory_budget() -> None:
    from dataclasses import replace

    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    tiny_memory_config = replace(config, extractor_memory_bytes=1)
    pdf_bytes = _create_test_pdf("Sample text for memory test")

    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(BytesIO(pdf_bytes), tiny_memory_config)
    assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert exc_info.value.reason == "EXTRACTOR_MEMORY"


def test_docling_extractor_enforces_timeout_after_conversion() -> None:
    import time
    from dataclasses import replace

    from knora.providers.cloudflare.pdf_understanding import CloudflareToMarkdownResponse

    def slow_conversion(data: bytes) -> CloudflareToMarkdownResponse:
        time.sleep(0.05)
        return CloudflareToMarkdownResponse(
            content="# Converted Title\n\nBody here.", format="markdown"
        )

    mock_provider = MagicMock(spec=CloudflarePdfUnderstandingProvider)
    mock_provider.convert_to_markdown.side_effect = slow_conversion

    extractor = DoclingTextExtractor(cf_provider=mock_provider)
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    timeout_config = replace(config, extraction_timeout_seconds=0.01)

    # Trigger fallback path by providing non-pypdf bytes
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract(BytesIO(b"not-a-valid-pdf-stream"), timeout_config)
    assert exc_info.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert exc_info.value.reason == "TIMEOUT"


def test_docling_extractor_repeated_sections_have_distinct_offsets() -> None:
    repeated_text = "Standard clause.\n\nStandard clause.\n\nStandard clause."
    pdf_bytes = _create_test_pdf(repeated_text)
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert result.structure is not None
    page = result.structure.pages[0]
    blocks = page.blocks
    assert len(blocks) >= 3

    # Offsets must be strictly monotonically increasing
    for i in range(len(blocks) - 1):
        assert blocks[i].start_offset < blocks[i].end_offset
        assert blocks[i].end_offset <= blocks[i + 1].start_offset

    # Each block slice must exactly equal block text
    for b in blocks:
        assert page.text[b.start_offset : b.end_offset] == b.text


def test_r6_f24_extraction_over_memory_not_swallowed() -> None:
    from dataclasses import replace

    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()
    # Memory budget set to 10 bytes so current process RSS will definitely exceed it
    low_mem_config = replace(config, extractor_memory_bytes=10)
    pdf_bytes = _create_test_pdf("Sample text for budget test")

    succeeded = True
    try:
        extractor.extract(BytesIO(pdf_bytes), low_mem_config)
    except PdfExtractionError as exc:
        succeeded = False
        assert exc.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
        assert exc.reason in ("EXTRACTOR_MEMORY", "RAW_FILE_SIZE")

    assert succeeded is False


def test_r6_f03_canonical_native_table_cells_without_pipes() -> None:
    # Native table with tab/column spacing instead of markdown pipes
    native_table_text = "Metric\tQ1\tQ2\nRevenue\t100\t120\nProfit\t20\t30"
    pdf_bytes = _create_test_pdf(native_table_text)
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    assert result.structure is not None
    page = result.structure.pages[0]
    assert len(page.tables) >= 1
    canonical_native_table = page.tables[0]
    assert canonical_native_table.num_rows == 3
    assert canonical_native_table.num_columns == 3

    source_reviewed_cells = (
        ("Metric", True, 0, 0),
        ("Q1", True, 0, 1),
        ("Q2", True, 0, 2),
        ("Revenue", False, 1, 0),
        ("100", False, 1, 1),
        ("120", False, 1, 2),
        ("Profit", False, 2, 0),
        ("20", False, 2, 1),
        ("30", False, 2, 2),
    )
    extracted_cells = tuple(
        (c.text, c.is_header, c.row_index, c.column_index) for c in canonical_native_table.cells
    )
    assert extracted_cells == source_reviewed_cells


def _dummy_long_running_child() -> None:
    import time

    while True:
        time.sleep(0.1)


def test_r6_f24_owned_child_tree_after_timeout() -> None:
    import multiprocessing

    import psutil

    from knora.adapters.pdf._pypdf_process import _stop

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_dummy_long_running_child, daemon=True)
    proc.start()
    pid = proc.pid
    assert pid is not None

    # Verify process is running
    assert psutil.pid_exists(pid)

    # Stop process and clean tree
    _stop(proc)

    # Check owned child tree after stop
    owned_child_tree_after_timeout = tuple(c for c in psutil.process_iter() if c.pid == pid)
    assert owned_child_tree_after_timeout == ()


def test_r6_structure_serialization_and_chunk_bounds() -> None:
    import json

    from knora.ingestion.pdf_structure import (
        canonical_document_from_dict,
        canonical_document_to_dict,
    )

    text = "First section header\n\nBody of the document with sufficient content."
    pdf_bytes = _create_test_pdf(text)
    extractor = DoclingTextExtractor()
    config = DoclingExtractionConfiguration.cloudflare_native_v1()

    result = extractor.extract(BytesIO(pdf_bytes), config)
    extracted_structure = result.structure
    assert extracted_structure is not None

    # PG serialize and reload round-trip
    serialized = json.dumps(canonical_document_to_dict(extracted_structure))
    pg_reloaded_structure = canonical_document_from_dict(json.loads(serialized))
    assert pg_reloaded_structure == extracted_structure

    # Chunking token and page bounds
    assert all(c.page_start == c.page_end and c.token_count <= 650 for c in result.chunks)
