from __future__ import annotations

import httpx
import pytest

from knora.ingestion.pdf import PdfExtractionError
from knora.providers.cloudflare.pdf_understanding import (
    CloudflarePdfUnderstandingProvider,
)


def test_tomarkdown_parses_real_envelope() -> None:
    def endpoint(request: httpx.Request) -> httpx.Response:
        assert b'name="files"' in request.content
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "name": "document.pdf",
                        "format": "markdown",
                        "data": "# Policy Document\n\nContent here.",
                    }
                ],
            },
            headers={"cf-ray": "ray_abc123"},
        )

    with httpx.Client(transport=httpx.MockTransport(endpoint), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        resp = provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert resp.content == "# Policy Document\n\nContent here."
        assert resp.format == "markdown"
        assert resp.request_id == "ray_abc123"


def test_tomarkdown_rejects_dict_envelope_and_malformed() -> None:
    def endpoint_dict(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "name": "document.pdf",
                    "format": "markdown",
                    "data": "# Fallback Dict Content",
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(endpoint_dict), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert "CLOUDFLARE_MALFORMED_OUTPUT" in exc_info.value.reason


def test_tomarkdown_rejects_name_mismatch_and_non_string_data() -> None:
    def endpoint_wrong_name(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "name": "wrong_file.pdf",
                        "format": "markdown",
                        "data": "hello",
                    }
                ],
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(endpoint_wrong_name), trust_env=False
    ) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert "CLOUDFLARE_NAME_MISMATCH" in exc_info.value.reason

    def endpoint_dict_data(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "name": "document.pdf",
                        "format": "markdown",
                        "data": {"text": "hello"},
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(endpoint_dict_data), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert "CLOUDFLARE_MALFORMED_OUTPUT" in exc_info.value.reason


def test_tomarkdown_rejects_format_error_in_result() -> None:
    def endpoint_format_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "name": "document.pdf",
                        "format": "error",
                        "error": "conversion failed",
                    }
                ],
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(endpoint_format_error), trust_env=False
    ) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert "CLOUDFLARE_CONVERSION_FAILED" in exc_info.value.reason


def test_tomarkdown_handles_api_errors_and_malformed() -> None:
    def error_endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": False,
                "errors": ["Document processing failed"],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(error_endpoint), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert "CLOUDFLARE_API_ERROR" in exc_info.value.reason


def test_tomarkdown_handles_rate_limit_and_bad_request() -> None:
    def rate_limit_endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"success": False, "errors": ["Rate limited"]})

    with httpx.Client(
        transport=httpx.MockTransport(rate_limit_endpoint), trust_env=False
    ) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert exc_info.value.code == "PDF_EXTRACTOR_UNAVAILABLE"
        assert exc_info.value.reason == "CLOUDFLARE_RATE_LIMIT"
        assert exc_info.value.retryable is True


def test_tomarkdown_handles_per_file_error_result() -> None:
    def error_endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": [
                    {
                        "name": "document.pdf",
                        "format": "error",
                        "error": "conversion failed",
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(error_endpoint), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as exc_info:
            provider.convert_to_markdown(b"%PDF-1.4 test bytes")
        assert exc_info.value.code == "PDF_EXTRACTOR_UNAVAILABLE"
        assert "CLOUDFLARE_CONVERSION_FAILED" in exc_info.value.reason
        assert exc_info.value.retryable is True


def test_ocr_page_image_confidence_handling() -> None:
    def endpoint_with_confidence(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"response": "Detected text from scan", "confidence": 0.88},
            },
            headers={"cf-ray": "ray_ocr_123"},
        )

    def endpoint_without_confidence(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"response": "Detected text from scan"},
            },
            headers={"cf-ray": "ray_ocr_456"},
        )

    with httpx.Client(
        transport=httpx.MockTransport(endpoint_with_confidence), trust_env=False
    ) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        resp = provider.ocr_page_image(b"fake-image-bytes")
        assert resp.text == "Detected text from scan"
        assert resp.confidence == 0.88
        assert resp.request_id == "ray_ocr_123"

    with httpx.Client(
        transport=httpx.MockTransport(endpoint_without_confidence), trust_env=False
    ) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test-only-token",
            client=client,
        )
        resp2 = provider.ocr_page_image(b"fake-image-bytes")
        assert resp2.text == "Detected text from scan"
        assert resp2.confidence is None
        assert resp2.request_id == "ray_ocr_456"
