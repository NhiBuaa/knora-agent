from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from knora.ingestion.pdf import PdfExtractionError

DEFAULT_OCR_INSTRUCTION = (
    "Perform verbatim OCR on this page image. Extract all text and tables accurately."
)


@dataclass(frozen=True, slots=True)
class CloudflareToMarkdownResponse:
    content: str
    format: str
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class CloudflareVisionOcrResponse:
    text: str
    confidence: float | None = None
    request_id: str | None = None


class CloudflarePdfUnderstandingProvider:
    """Cloudflare Workers AI client for document understanding, markdown conversion and OCR."""

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        client: httpx.Client | None = None,
        ocr_model: str = "@cf/moondream/moondream3.1-9B-A2B",
        timeout_seconds: float = 60.0,
    ) -> None:
        if re.fullmatch(r"[0-9a-fA-F]{32}", account_id) is None:
            raise ValueError("invalid provider configuration: invalid cloudflare_account_id")

        self._account_id = account_id
        self._api_token = api_token
        self._ocr_model = ocr_model
        self._tomarkdown_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/tomarkdown"
        )
        self._ocr_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{ocr_model}"
        )
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def convert_to_markdown(self, file_bytes: bytes) -> CloudflareToMarkdownResponse:
        """Call Cloudflare /ai/tomarkdown endpoint with multipart/form-data."""
        headers = {"Authorization": f"Bearer {self._api_token}"}
        files = {"file": ("document.pdf", file_bytes, "application/pdf")}
        data = {"conversionOptions": '{"output":{"format":"markdown"},"pdf":{"metadata":true}}'}

        try:
            response = self._client.post(
                self._tomarkdown_url,
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result", {})
            content = result.get("content", "")
            fmt = result.get("format", "markdown")
            request_id = response.headers.get("cf-ray") or response.headers.get("x-request-id")
            return CloudflareToMarkdownResponse(content=content, format=fmt, request_id=request_id)
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            if status_code == 429:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_RATE_LIMIT",
                    retryable=True,
                ) from error
            if status_code in (400, 422):
                raise PdfExtractionError(
                    "PDF_MALFORMED",
                    reason="CLOUDFLARE_BAD_REQUEST",
                    retryable=False,
                ) from error
            if status_code == 413:
                raise PdfExtractionError(
                    "PDF_RESOURCE_LIMIT_EXCEEDED",
                    reason="RAW_FILE_SIZE",
                    retryable=False,
                ) from error
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason=f"CLOUDFLARE_HTTP_{status_code}",
                retryable=True,
            ) from error
        except Exception as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error

    def ocr_page_image(
        self,
        image_bytes: bytes,
        instruction: str = DEFAULT_OCR_INSTRUCTION,
    ) -> CloudflareVisionOcrResponse:
        """Call Cloudflare Workers AI vision model for selective OCR."""
        headers = {"Authorization": f"Bearer {self._api_token}"}
        # Model accepts image bytes and prompt/instruction
        body = {
            "prompt": instruction,
            "max_tokens": 2048,
        }
        files = {"image": ("page.png", image_bytes, "image/png")}

        try:
            response = self._client.post(
                self._ocr_url,
                headers=headers,
                data=body,
                files=files,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result", {})
            # Responses vary by vision model (description, response, text)
            text = result.get("response") or result.get("description") or result.get("text") or ""
            request_id = response.headers.get("cf-ray") or response.headers.get("x-request-id")
            return CloudflareVisionOcrResponse(text=text, confidence=1.0, request_id=request_id)
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            if status_code == 429:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_RATE_LIMIT",
                    retryable=True,
                ) from error
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason=f"CLOUDFLARE_HTTP_{status_code}",
                retryable=True,
            ) from error
        except Exception as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error
