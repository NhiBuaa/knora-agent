from __future__ import annotations

import ctypes
import hashlib
import multiprocessing
import os
import time
import zlib
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
    NumberObject,
)

from knora.adapters.pdf import pypdf as pypdf_adapter
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionError,
)


def pdf_with_pages(*pages: str) -> bytes:
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
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                )
            }
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


def encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def unsupported_filter_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = EncodedStreamObject()
    stream._data = b"BT ET"
    stream[NameObject("/Filter")] = NameObject("/UnsupportedDecode")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def malformed_contents_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Contents")] = NumberObject(1)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def dependency_filter_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = EncodedStreamObject()
    stream._data = b"JBIG2"
    stream[NameObject("/Filter")] = NameObject("/JBIG2Decode")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def difficult_layout_pdf(layout: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    base_font = "/Courier-Oblique" if layout == "unusual-font" else "/Helvetica"
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(base_font),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    commands = {
        "multi-column": (
            "BT /F1 12 Tf 1 0 0 1 72 720 Tm (left column) Tj "
            "1 0 0 1 320 720 Tm (right column) Tj ET"
        ),
        "table": (
            "BT /F1 12 Tf 1 0 0 1 72 720 Tm (name) Tj "
            "1 0 0 1 240 720 Tm (value) Tj "
            "1 0 0 1 72 700 Tm (alpha) Tj "
            "1 0 0 1 240 700 Tm (10) Tj ET"
        ),
        "rotated": "BT /F1 12 Tf 0 1 -1 0 100 600 Tm (rotated text) Tj ET",
        "unusual-font": "BT /F1 12 Tf 1 0 0 1 72 720 Tm (symbols baseline) Tj ET",
        "mixed-image-text": (
            "q 10 0 0 10 72 680 cm /Im1 Do Q "
            "BT /F1 12 Tf 1 0 0 1 72 720 Tm (extractable caption) Tj ET"
        ),
    }
    if layout == "mixed-image-text":
        image = DecodedStreamObject()
        image.set_data(b"\xff\xff\xff")
        image.update(
            {
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(1),
                NameObject("/Height"): NumberObject(1),
                NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                NameObject("/BitsPerComponent"): NumberObject(8),
            }
        )
        resources[NameObject("/XObject")] = DictionaryObject(
            {NameObject("/Im1"): writer._add_object(image)}
        )
    page[NameObject("/Resources")] = resources
    content = DecodedStreamObject()
    content.set_data(commands[layout].encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def nested_form_pdf(form_stream_size: int, *, page_count: int = 1) -> bytes:
    writer = PdfWriter()
    page_content = b"q /Fm1 Do Q BT /F1 12 Tf (nested budget) Tj ET"
    for _ in range(page_count):
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        form = EncodedStreamObject()
        form._data = zlib.compress(b" " * form_stream_size)
        form.update(
            {
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Form"),
                NameObject("/FormType"): NumberObject(1),
                NameObject("/BBox"): ArrayObject([NumberObject(0)] * 4),
                NameObject("/Filter"): NameObject("/FlateDecode"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                ),
                NameObject("/XObject"): DictionaryObject(
                    {NameObject("/Fm1"): writer._add_object(form)}
                ),
            }
        )
        content = DecodedStreamObject()
        content.set_data(page_content)
        page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def child_exits_without_sending(
    _pdf_path: str,
    _configuration: PdfExtractionConfiguration,
    _connection,
) -> None:
    os._exit(17)


def child_sleeps_past_timeout(
    _pdf_path: str,
    configuration: PdfExtractionConfiguration,
    _connection,
) -> None:
    time.sleep(configuration.extraction_timeout_seconds + 1)


def child_sends_after_timeout(
    _pdf_path: str,
    configuration: PdfExtractionConfiguration,
    connection,
) -> None:
    time.sleep(configuration.extraction_timeout_seconds + 0.005)
    connection.send(("ok", [SimpleNamespace(page_number=1, text="late output")]))
    connection.recv()


def child_sends_normalization_sample(
    _pdf_path: str,
    _configuration: PdfExtractionConfiguration,
    connection,
) -> None:
    text = "Cafe\u0301\u00a0  au\tlait\r\nsecond\rline\x00\n\n\nlast"
    connection.send(("ok_start", 1))
    connection.send(("page", 1, 0, text, True))
    connection.send(("ok_end",))
    connection.recv()


def child_allocates_past_memory_limit(
    _pdf_path: str,
    configuration: PdfExtractionConfiguration,
    _connection,
) -> None:
    payload = bytearray(configuration.extractor_memory_bytes + 8 * 1024 * 1024)
    for index in range(0, len(payload), 4096):
        payload[index] = 1
    time.sleep(5)


class SleepingExtractor(PypdfTextExtractor):
    _child_target = staticmethod(child_sleeps_past_timeout)


class LateOutputExtractor(PypdfTextExtractor):
    _child_target = staticmethod(child_sends_after_timeout)


class NormalizationFixtureExtractor(PypdfTextExtractor):
    _child_target = staticmethod(child_sends_normalization_sample)


class MemoryHungryExtractor(PypdfTextExtractor):
    _child_target = staticmethod(child_allocates_past_memory_limit)


def padded_pdf(target_size: int) -> bytes:
    source = pdf_with_pages("raw boundary")
    padding = target_size - len(source)
    assert padding >= 0
    return source + (b" " * padding)


def exact_page_stream_pdf(page_stream_size: int, *, page_count: int = 1) -> bytes:
    page_content_size = len(b"q /Fm1 Do Q BT /F1 12 Tf (nested budget) Tj ET")
    return nested_form_pdf(
        page_stream_size - page_content_size,
        page_count=page_count,
    )


def array_contents_pdf(stream_sizes: tuple[int, ...]) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    streams = []
    for size in stream_sizes:
        stream = DecodedStreamObject()
        if size:
            payload = b"BT /F1 12 Tf (array budget) Tj ET"
            assert size >= len(payload)
            stream.set_data(payload + (b" " * (size - len(payload))))
        else:
            stream.set_data(b"")
        streams.append(writer._add_object(stream))
    page[NameObject("/Contents")] = ArrayObject(streams)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def flated_contents_pdf(decoded_size: int) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = EncodedStreamObject()
    stream._data = zlib.compress(b"x" * decoded_size)
    stream[NameObject("/Filter")] = NameObject("/FlateDecode")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extracts_reproducible_normalized_pages_and_page_bounded_chunks() -> None:
    source = pdf_with_pages(
        "First paragraph.\n\nSecond paragraph.",
        "Third paragraph on page two.",
    )
    extractor = PypdfTextExtractor()
    configuration = PdfExtractionConfiguration.milestone_two()

    first = extractor.extract(BytesIO(source), configuration)
    second = extractor.extract(BytesIO(source), configuration)

    assert first == second
    assert [page.page_number for page in first.pages] == [1, 2]
    assert [page.text for page in first.pages] == [
        "First paragraph.\n\nSecond paragraph.",
        "Third paragraph on page two.",
    ]
    assert first.parser_version == "pypdf-6.14.2-plain-v1"
    assert first.normalizer_version == "pdf-normalizer-m2-v1"
    assert first.chunking_policy_version == "page-block-v1"
    assert first.chunks
    assert all(chunk.page_start == chunk.page_end == chunk.page_number for chunk in first.chunks)
    assert all(
        first.pages[chunk.page_number - 1].text[chunk.start_offset : chunk.end_offset]
        == chunk.content
        for chunk in first.chunks
    )


def test_packs_complete_blocks_with_overlap_and_hard_splits_only_oversized_blocks() -> None:
    source = pdf_with_pages(
        "alpha beta gamma\n\ndelta epsilon zeta\n\neta theta iota",
        "word " * 80,
        "",
    )
    configuration = replace(
        PdfExtractionConfiguration.milestone_two(),
        target_tokens=8,
        overlap_tokens=4,
        max_tokens=12,
    )

    result = PypdfTextExtractor().extract(BytesIO(source), configuration)

    page_one = [chunk for chunk in result.chunks if chunk.page_number == 1]
    assert [chunk.content for chunk in page_one] == [
        "alpha beta gamma\n\ndelta epsilon zeta",
        "delta epsilon zeta\n\neta theta iota",
    ]
    page_two = [chunk for chunk in result.chunks if chunk.page_number == 2]
    assert len(page_two) > 1
    assert all(chunk.token_count <= configuration.max_tokens for chunk in page_two)
    assert not [chunk for chunk in result.chunks if chunk.page_number == 3]


@pytest.mark.parametrize(
    ("source", "code", "reason"),
    [
        pytest.param(encrypted_pdf(), "PDF_ENCRYPTED", "ENCRYPTED", id="encrypted"),
        pytest.param(
            b"%PDF-1.7\nnot a valid PDF",
            "PDF_MALFORMED",
            "MALFORMED",
            id="malformed",
        ),
        pytest.param(
            unsupported_filter_pdf(),
            "PDF_UNSUPPORTED",
            "UNSUPPORTED_FEATURE",
            id="unsupported",
        ),
        pytest.param(
            malformed_contents_pdf(),
            "PDF_MALFORMED",
            "MALFORMED",
            id="malformed-contents-structure",
        ),
        pytest.param(
            dependency_filter_pdf(),
            "PDF_UNSUPPORTED",
            "UNSUPPORTED_FEATURE",
            id="unsupported-decoder-dependency",
        ),
        pytest.param(
            pdf_with_pages(""),
            "PDF_TEXT_INSUFFICIENT",
            "INSUFFICIENT_EXTRACTABLE_TEXT",
            id="text-insufficient",
        ),
    ],
)
def test_rejects_invalid_pdf_categories_without_partial_output(
    source: bytes,
    code: str,
    reason: str,
) -> None:
    with pytest.raises(PdfExtractionError) as raised:
        PypdfTextExtractor().extract(
            BytesIO(source),
            PdfExtractionConfiguration.milestone_two(),
        )

    assert raised.value.code == code
    assert raised.value.reason == reason
    assert not raised.value.retryable
    assert str(raised.value) == code


def test_enforces_inclusive_raw_page_and_decompressed_stream_budgets() -> None:
    extractor = PypdfTextExtractor()
    one_page = pdf_with_pages("within raw budget")
    baseline = PdfExtractionConfiguration.milestone_two()

    exact_raw = extractor.extract(
        BytesIO(one_page),
        replace(baseline, max_raw_bytes=len(one_page)),
    )
    assert exact_raw.pages[0].text == "within raw budget"

    cases = [
        (
            one_page,
            replace(baseline, max_raw_bytes=len(one_page) - 1),
            "RAW_FILE_SIZE",
        ),
        (pdf_with_pages("one", "two"), replace(baseline, max_pages=1), "PAGE_COUNT"),
        (
            one_page,
            replace(baseline, max_page_stream_bytes=1),
            "PAGE_STREAM_SIZE",
        ),
        (
            pdf_with_pages("one", "two"),
            replace(baseline, max_total_stream_bytes=1),
            "TOTAL_STREAM_SIZE",
        ),
    ]
    for source, configuration, reason in cases:
        with pytest.raises(PdfExtractionError) as raised:
            extractor.extract(BytesIO(source), configuration)
        assert raised.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
        assert raised.value.reason == reason


@pytest.mark.parametrize(
    ("configuration", "reason"),
    [
        (
            replace(
                PdfExtractionConfiguration.milestone_two(),
                extraction_timeout_seconds=0.0001,
            ),
            "EXTRACTION_TIMEOUT",
        ),
        (
            replace(
                PdfExtractionConfiguration.milestone_two(),
                extractor_memory_bytes=1,
            ),
            "EXTRACTOR_MEMORY",
        ),
    ],
)
def test_kills_over_budget_child_and_keeps_parent_healthy(
    configuration: PdfExtractionConfiguration,
    reason: str,
) -> None:
    source = pdf_with_pages("ordinary text")
    extractor = PypdfTextExtractor()

    with pytest.raises(PdfExtractionError) as raised:
        extractor.extract(BytesIO(source), configuration)

    assert raised.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert raised.value.reason == reason
    assert extractor.extract(
        BytesIO(source),
        PdfExtractionConfiguration.milestone_two(),
    ).pages[0].text == "ordinary text"


def test_rejects_child_output_sent_after_the_extraction_deadline() -> None:
    source = pdf_with_pages("ordinary text")
    configuration = replace(
        PdfExtractionConfiguration.milestone_two(),
        extraction_timeout_seconds=0.05,
    )

    with pytest.raises(PdfExtractionError) as raised:
        LateOutputExtractor().extract(BytesIO(source), configuration)

    assert raised.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert raised.value.reason == "EXTRACTION_TIMEOUT"


def test_normalization_contract_and_pinned_metadata_are_observable() -> None:
    configuration = PdfExtractionConfiguration.milestone_two()
    expected_text = "Café au lait\nsecond\nline\n\nlast"

    result = NormalizationFixtureExtractor().extract(BytesIO(b"fixture"), configuration)

    assert result.pages == (
        NormalizedPdfPage(
            page_number=1,
            text=expected_text,
            content_checksum=hashlib.sha256(expected_text.encode()).hexdigest(),
        ),
    )
    assert result.extraction_options_version == "pypdf-plain-layout-v1"
    assert result.tokenizer_name == "cl100k_base"
    assert result.tokenizer_version == "tiktoken-0.12.0"
    assert result.chunks[0].content == expected_text
    assert result.chunks[0].start_offset == 0
    assert result.chunks[0].end_offset == len(expected_text)


def test_child_start_failure_is_retryable_extractor_unavailable() -> None:
    def local_target(_pdf_path, _configuration, _connection):
        return None

    extractor = PypdfTextExtractor()
    extractor._child_target = local_target

    with pytest.raises(PdfExtractionError) as raised:
        extractor.extract(
            BytesIO(b"fixture"),
            PdfExtractionConfiguration.milestone_two(),
        )

    assert raised.value.code == "PDF_EXTRACTOR_UNAVAILABLE"
    assert raised.value.reason == "CHILD_CRASH"
    assert raised.value.retryable


@pytest.mark.parametrize(
    "layout",
    [
        "multi-column",
        "table",
        "rotated",
        "unusual-font",
        "mixed-image-text",
    ],
)
def test_difficult_layout_baselines_remain_deterministic(layout: str) -> None:
    source = difficult_layout_pdf(layout)
    extractor = PypdfTextExtractor()
    configuration = PdfExtractionConfiguration.milestone_two()

    first = extractor.extract(BytesIO(source), configuration)
    second = extractor.extract(BytesIO(source), configuration)

    assert first == second, layout
    assert first.pages[0].page_number == 1
    assert first.pages[0].text


def test_configuration_change_creates_new_derivation_identity_without_mutation() -> None:
    source = pdf_with_pages("same visible text")
    baseline = PdfExtractionConfiguration.milestone_two()
    changed = replace(baseline, normalizer_version="pdf-normalizer-m2-v2")
    extractor = PypdfTextExtractor()

    first = extractor.extract(BytesIO(source), baseline)
    changed_result = extractor.extract(BytesIO(source), changed)
    repeated = extractor.extract(BytesIO(source), baseline)

    assert first == repeated
    assert first.pages == changed_result.pages
    assert first.chunks == changed_result.chunks
    assert first.derivation_identity != changed_result.derivation_identity
    assert first.normalizer_version == "pdf-normalizer-m2-v1"
    assert changed_result.normalizer_version == "pdf-normalizer-m2-v2"


def test_hard_split_keeps_supplementary_unicode_under_the_token_cap() -> None:
    text = ("🏳️‍🌈 " * 1200).strip()
    page = NormalizedPdfPage(
        page_number=1,
        text=text,
        content_checksum=hashlib.sha256(text.encode()).hexdigest(),
    )

    chunks = PypdfTextExtractor._chunk_pages(
        (page,),
        PdfExtractionConfiguration.milestone_two(),
    )

    assert len(chunks) > 1
    assert all(chunk.token_count <= 650 for chunk in chunks)
    assert all(
        page.text[chunk.start_offset : chunk.end_offset] == chunk.content
        for chunk in chunks
    )


def test_hard_split_preserves_all_supplementary_unicode_text() -> None:
    text = ("🏳️‍🌈 " * 200).strip()
    page = NormalizedPdfPage(
        page_number=1,
        text=text,
        content_checksum=hashlib.sha256(text.encode()).hexdigest(),
    )

    chunks = PypdfTextExtractor._chunk_pages(
        (page,),
        PdfExtractionConfiguration.milestone_two(),
    )

    cursor = 0
    for chunk in sorted(chunks, key=lambda item: item.start_offset):
        assert chunk.start_offset <= cursor
        assert page.text[chunk.start_offset : chunk.end_offset] == chunk.content
        cursor = max(cursor, chunk.end_offset)
    assert cursor == len(text)


def test_chunking_accepts_literal_tokenizer_special_tokens() -> None:
    text = "A literal <|endoftext|> marker."
    page = NormalizedPdfPage(
        page_number=1,
        text=text,
        content_checksum=hashlib.sha256(text.encode()).hexdigest(),
    )

    chunks = PypdfTextExtractor._chunk_pages(
        (page,),
        PdfExtractionConfiguration.milestone_two(),
    )

    assert "<|endoftext|>" in "".join(chunk.content for chunk in chunks)


def test_compressed_content_stream_over_budget_returns_page_stream_limit() -> None:
    configuration = replace(
        PdfExtractionConfiguration.milestone_two(),
        max_page_stream_bytes=1024,
    )

    with pytest.raises(PdfExtractionError) as raised:
        PypdfTextExtractor().extract(
            BytesIO(flated_contents_pdf(4096)),
            configuration,
        )

    assert raised.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert raised.value.reason == "PAGE_STREAM_SIZE"


def test_nested_form_xobject_streams_count_toward_page_budget() -> None:
    source = nested_form_pdf(form_stream_size=200)
    configuration = replace(
        PdfExtractionConfiguration.milestone_two(),
        max_page_stream_bytes=200,
    )

    with pytest.raises(PdfExtractionError) as raised:
        PypdfTextExtractor().extract(BytesIO(source), configuration)

    assert raised.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert raised.value.reason == "PAGE_STREAM_SIZE"


def test_array_content_stream_budget_counts_each_decoded_stream_without_join_bytes() -> None:
    source = array_contents_pdf((64, 64))
    configuration = replace(
        PdfExtractionConfiguration.milestone_two(),
        max_page_stream_bytes=128,
    )

    result = PypdfTextExtractor().extract(BytesIO(source), configuration)

    assert result.pages[0].text == "array budgetarray budget"


def test_empty_stream_after_exact_page_and_total_budget_is_allowed() -> None:
    configuration = replace(
        PdfExtractionConfiguration.milestone_two(),
        max_page_stream_bytes=64,
        max_total_stream_bytes=64,
    )

    result = PypdfTextExtractor().extract(
        BytesIO(array_contents_pdf((64, 0))),
        configuration,
    )

    assert result.pages[0].text == "array budget"


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object contract")
def test_windows_job_object_peak_memory_is_classified_as_extractor_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeFunction:
        def __init__(self, callback) -> None:
            self.callback = callback

        def __call__(self, *args):
            return self.callback(*args)

    class FakeKernel32:
        def __init__(self) -> None:
            self.QueryInformationJobObject = FakeFunction(self.query_information)

        @staticmethod
        def query_information(_handle, _info_class, buffer, _size, returned) -> int:
            information = ctypes.cast(
                buffer,
                ctypes.POINTER(pypdf_adapter._JobObjectExtendedLimitInformation),
            ).contents
            information.peak_process_memory_used = 128
            returned._obj.value = ctypes.sizeof(information)
            return 1

    monkeypatch.setattr(
        pypdf_adapter.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: FakeKernel32(),
    )

    assert pypdf_adapter._hard_memory_limit_triggered(123, 128)


def test_child_eof_is_classified_as_retryable_extractor_failure() -> None:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(
        target=child_exits_without_sending,
        args=("unused", PdfExtractionConfiguration.milestone_two(), child),
    )
    process.start()
    child.close()
    process.join(timeout=5)
    try:
        with pytest.raises(PdfExtractionError) as raised:
            PypdfTextExtractor._receive_message(parent)
    finally:
        parent.close()

    assert raised.value.code == "PDF_EXTRACTOR_UNAVAILABLE"
    assert raised.value.reason == "CHILD_CRASH"
    assert raised.value.retryable


def test_receive_message_rejects_ready_message_after_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ReadyConnection:
        def poll(self, _timeout: float) -> bool:
            return True

        def recv(self) -> tuple[str]:
            return ("ok_end",)

    monotonic_values = iter((0.0, 2.0))
    monkeypatch.setattr(
        "knora.adapters.pdf.pypdf.time.monotonic",
        lambda: next(monotonic_values),
    )

    with pytest.raises(PdfExtractionError) as raised:
        PypdfTextExtractor._receive_message(ReadyConnection(), deadline=1.0)

    assert raised.value.code == "PDF_RESOURCE_LIMIT_EXCEEDED"
    assert raised.value.reason == "EXTRACTION_TIMEOUT"


@pytest.mark.skipif(
    os.getenv("KNORA_RUN_MANUAL_ACCEPTANCE") != "1",
    reason="locked baseline acceptance fixture; set KNORA_RUN_MANUAL_ACCEPTANCE=1",
)
def test_locked_baseline_raw_and_page_boundaries() -> None:
    extractor = PypdfTextExtractor()
    configuration = PdfExtractionConfiguration.milestone_two()
    raw_sizes = (
        configuration.max_raw_bytes - 1,
        configuration.max_raw_bytes,
        configuration.max_raw_bytes + 1,
    )
    for size in raw_sizes:
        source = padded_pdf(size)
        if size > configuration.max_raw_bytes:
            with pytest.raises(PdfExtractionError) as raised:
                extractor.extract(BytesIO(source), configuration)
            assert raised.value.reason == "RAW_FILE_SIZE"
        else:
            assert extractor.extract(BytesIO(source), configuration).pages[0].text == "raw boundary"

    for page_count in (configuration.max_pages - 1, configuration.max_pages):
        source = pdf_with_pages("page boundary", *([""] * (page_count - 1)))
        result = extractor.extract(BytesIO(source), configuration)
        assert len(result.pages) == page_count
    with pytest.raises(PdfExtractionError) as raised:
        extractor.extract(
            BytesIO(pdf_with_pages("page boundary", *([""] * configuration.max_pages))),
            configuration,
        )
    assert raised.value.reason == "PAGE_COUNT"


@pytest.mark.skipif(
    os.getenv("KNORA_RUN_MANUAL_ACCEPTANCE") != "1",
    reason="locked baseline acceptance fixture; set KNORA_RUN_MANUAL_ACCEPTANCE=1",
)
def test_locked_baseline_stream_boundaries() -> None:
    extractor = PypdfTextExtractor()
    configuration = PdfExtractionConfiguration.milestone_two()
    exact_page = exact_page_stream_pdf(configuration.max_page_stream_bytes)
    assert extractor.extract(BytesIO(exact_page), configuration).pages[0].text == "nested budget"

    above_page = exact_page_stream_pdf(configuration.max_page_stream_bytes + 1)
    with pytest.raises(PdfExtractionError) as page_raised:
        extractor.extract(BytesIO(above_page), configuration)
    assert page_raised.value.reason == "PAGE_STREAM_SIZE"

    exact_total = exact_page_stream_pdf(
        configuration.max_page_stream_bytes,
        page_count=configuration.max_total_stream_bytes // configuration.max_page_stream_bytes,
    )
    assert len(extractor.extract(BytesIO(exact_total), configuration).pages) == 16

    above_total = exact_page_stream_pdf(
        configuration.max_page_stream_bytes,
        page_count=(
            configuration.max_total_stream_bytes // configuration.max_page_stream_bytes
        )
        + 1,
    )
    with pytest.raises(PdfExtractionError) as total_raised:
        extractor.extract(BytesIO(above_total), configuration)
    assert total_raised.value.reason == "TOTAL_STREAM_SIZE"


@pytest.mark.skipif(
    os.getenv("KNORA_RUN_MANUAL_ACCEPTANCE") != "1",
    reason="locked baseline child-limit fixture; set KNORA_RUN_MANUAL_ACCEPTANCE=1",
)
def test_locked_baseline_timeout_and_memory_ceiling_keep_parent_healthy() -> None:
    source = pdf_with_pages("ordinary parent follow-up")
    configuration = PdfExtractionConfiguration.milestone_two()

    with pytest.raises(PdfExtractionError) as timeout_raised:
        SleepingExtractor().extract(BytesIO(source), configuration)
    assert timeout_raised.value.reason == "EXTRACTION_TIMEOUT"

    with pytest.raises(PdfExtractionError) as memory_raised:
        MemoryHungryExtractor().extract(BytesIO(source), configuration)
    assert memory_raised.value.reason == "EXTRACTOR_MEMORY"

    assert PypdfTextExtractor().extract(BytesIO(source), configuration).pages[0].text == (
        "ordinary parent follow-up"
    )
