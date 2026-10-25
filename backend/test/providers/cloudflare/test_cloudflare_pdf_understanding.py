from __future__ import annotations

import base64
import json

import httpx
import pytest

from knora.ingestion.pdf import PdfExtractionError
from knora.providers.cloudflare.pdf_understanding import (
    CloudflarePdfUnderstandingProvider,
)


@pytest.mark.parametrize(
    "image,mime",
    [
        (b"\x89PNG\r\n\x1a\nexample", "image/png"),
        (b"\xff\xd8\xffexample", "image/jpeg"),
    ],
)
def test_moondream_ocr_uses_json_data_uri_and_reads_answer(image, mime):
    def endpoint(request):
        assert request.headers["content-type"].startswith("application/json")
        payload = json.loads(request.content)
        assert payload["task"] == "query"
        assert payload["question"] == "Extract text exactly"
        assert payload["image"] == f"data:{mime};base64," + base64.b64encode(image).decode("ascii")
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "answer": "Teacher Manh",
                    "finish_reason": "stop",
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(endpoint), trust_env=False) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test",
            client=client,
        )
        result = provider.ocr_page_image(image, instruction="Extract text exactly")
    assert result.text == "Teacher Manh"


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "errors": [{"code": 6003}], "result": {"answer": "untrusted"}},
        {"success": True, "result": {"answer": 123}},
        {"success": True, "result": {"answer": "partial", "finish_reason": "length"}},
    ],
)
def test_moondream_does_not_accept_failed_malformed_or_truncated_text(payload):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test",
            client=client,
        )
        with pytest.raises(PdfExtractionError):
            provider.ocr_page_image(b"image")


@pytest.mark.parametrize(
    "status,retryable", [(400, False), (401, False), (403, False), (429, True), (503, True)]
)
def test_moondream_does_not_retry_permanent_http_failures(status, retryable):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status))) as client:
        provider = CloudflarePdfUnderstandingProvider(
            account_id="0123456789abcdef0123456789abcdef",
            api_token="test",
            client=client,
        )
        with pytest.raises(PdfExtractionError) as error:
            provider.ocr_page_image(b"image")
        assert error.value.retryable is retryable


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
