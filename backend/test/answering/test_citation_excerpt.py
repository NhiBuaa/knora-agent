from knora.answering.excerpt import citation_excerpt


def test_long_excerpt_ends_at_a_whole_word_and_marks_omission():
    content = "Tài liệu " * 80
    result = citation_excerpt(content)
    assert result.endswith(" …")
    assert len(result) <= 500
    assert content.startswith(result.removesuffix(" …"))


def test_pdf_interior_range_omits_unverified_edge_words_without_inventing_text():
    content = "ục gợi ý dành cho báo cáo - Tài liệu t"
    assert (
        citation_excerpt(content, start_offset=125, end_offset=180)
        == "… gợi ý dành cho báo cáo - Tài liệu …"
    )


def test_complete_short_text_is_preserved():
    assert citation_excerpt("Một báo cáo gồm bảy chương.") == "Một báo cáo gồm bảy chương."
    assert (
        citation_excerpt("Một báo cáo gồm bảy chương.", start_offset=0, end_offset=27)
        == "Một báo cáo gồm bảy chương."
    )


def test_no_boundary_does_not_display_a_fragment_as_a_word():
    assert citation_excerpt("x" * 700) == "…"
