from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

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
        "result": {
            "format": "markdown",
            "content": "# Document Title\n\nFirst paragraph.",
        }
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
    assert result.structure.is_complete is True
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
