from __future__ import annotations

import base64
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

    def convert_to_markdown(
        self, file_bytes: bytes, timeout: float | None = None
    ) -> CloudflareToMarkdownResponse:
        """Call Cloudflare /ai/tomarkdown endpoint with multipart/form-data."""
        headers = {"Authorization": f"Bearer {self._api_token}"}
        files = {"files": ("document.pdf", file_bytes, "application/pdf")}
        data = {"conversionOptions": '{"output":{"format":"markdown"},"pdf":{"metadata":true}}'}

        try:
            response = self._client.post(
                self._tomarkdown_url,
                headers=headers,
                files=files,
                data=data,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_MALFORMED_OUTPUT",
                    retryable=False,
                )
            if payload.get("success") is not True:
                errors = payload.get("errors") or []
                err_msg = str(errors[0]) if errors else "UNKNOWN_ERROR"
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason=f"CLOUDFLARE_API_ERROR: {err_msg}",
                    retryable=True,
                )
            result = payload.get("result")
            if not isinstance(result, list) or len(result) != 1:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_MALFORMED_OUTPUT",
                    retryable=False,
                )
            item = result[0]
            if not isinstance(item, dict):
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_MALFORMED_OUTPUT",
                    retryable=False,
                )
            if item.get("name") != "document.pdf":
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_NAME_MISMATCH",
                    retryable=False,
                )
            if item.get("format") == "error" or "error" in item:
                err_msg = str(item.get("error") or "CONVERSION_FAILED")
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason=f"CLOUDFLARE_CONVERSION_FAILED: {err_msg}",
                    retryable=True,
                )
            fmt = item.get("format")
            if fmt != "markdown":
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_FORMAT_UNSUPPORTED",
                    retryable=False,
                )
            raw_content = item.get("data") if "data" in item else item.get("content")
            if not isinstance(raw_content, str):
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_MALFORMED_OUTPUT",
                    retryable=False,
                )
            content = raw_content

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
        except httpx.TimeoutException as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="TIMEOUT",
                retryable=True,
            ) from error
        except PdfExtractionError:
            raise
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
        timeout: float | None = None,
    ) -> CloudflareVisionOcrResponse:
        """Call Cloudflare Workers AI vision model for selective OCR."""
        headers = {"Authorization": f"Bearer {self._api_token}"}
        mime = "application/octet-stream"
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif image_bytes.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif image_bytes.startswith((b"GIF87a", b"GIF89a")):
            mime = "image/gif"
        elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"
        body = {
            "task": "query",
            "question": instruction,
            "image": f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii"),
            "reasoning": False,
            "max_tokens": 2048,
        }

        try:
            response = self._client.post(
                self._ocr_url,
                headers=headers,
                json=body,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE", reason="CLOUDFLARE_MALFORMED_OUTPUT"
                )
            result = payload.get("result")
            if not isinstance(result, dict) or result.get("finish_reason") == "length":
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE", reason="CLOUDFLARE_MALFORMED_OUTPUT"
                )
            text = (
                result.get("answer")
                or result.get("response")
                or result.get("description")
                or result.get("text")
                or ""
            )
            if not isinstance(text, str):
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE", reason="CLOUDFLARE_MALFORMED_OUTPUT"
                )
            conf = result.get("confidence")
            if conf is not None:
                try:
                    conf = float(conf)
                except (ValueError, TypeError):
                    conf = None
            request_id = response.headers.get("cf-ray") or response.headers.get("x-request-id")
            return CloudflareVisionOcrResponse(text=text, confidence=conf, request_id=request_id)
        except httpx.TimeoutException as error:
            raise PdfExtractionError(
                "PDF_RESOURCE_LIMIT_EXCEEDED",
                reason="TIMEOUT",
                retryable=True,
            ) from error
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
                retryable=status_code >= 500 or status_code == 408,
            ) from error
        except PdfExtractionError:
            raise
        except Exception as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error
