import io

import pytest

from server.engines.common import text

LONG_PARAGRAPH = (
    "The history of speech synthesis goes back centuries, to mechanical devices that "
    "imitated the human vocal tract. In the twentieth century, electronic systems made "
    "it possible to generate intelligible speech from text. Neural networks changed "
    "that, and today small open models can produce natural speech. "
) * 8


def _words(parts):
    return " ".join(parts).split()


# ── Segmenting ───────────────────────────────────────────────────────────────
def test_segments_respect_the_limit_and_keep_every_word():
    segments = text.split_segments(LONG_PARAGRAPH, max_chars=800)
    assert len(segments) > 1
    assert all(len(s) <= 800 for s in segments)
    assert _words(segments) == LONG_PARAGRAPH.split()


def test_short_paragraphs_are_packed_together():
    source = "\n\n".join(f"Line number {i}." for i in range(100))
    segments = text.split_segments(source, max_chars=800)
    assert len(segments) == 3  # 100 short paragraphs, ~1,800 chars → 3 calls, not 100
    assert all(len(s) <= 800 for s in segments)


def test_first_segment_is_one_short_sentence_when_requested():
    segments = text.split_segments(LONG_PARAGRAPH, first_segment_chars=150)
    assert len(segments[0]) <= 150
    assert segments[0].endswith("vocal tract.")
    assert _words(segments) == LONG_PARAGRAPH.split()


def test_overlong_first_sentence_is_cut_at_a_clause_or_word():
    sentence = "word " * 80 + "and then, finally, the end."
    head, *_ = text.split_segments(sentence, first_segment_chars=150)
    assert len(head) <= 150
    assert not head.endswith("wor")  # never cut mid-word
    assert _words(text.split_segments(sentence, first_segment_chars=150)) == sentence.split()


def test_first_segment_option_leaves_short_text_alone():
    assert text.split_segments("Hello there.", first_segment_chars=150) == ["Hello there."]


def test_break_lines_splits_hindi_sentences():
    hindi = "यह पहला वाक्य है। यह दूसरा वाक्य है। " * 10
    lines = text.break_lines(hindi, max_chars=60).splitlines()
    assert all(len(line) <= 60 for line in lines)
    assert " ".join(lines).split() == hindi.split()


# ── Estimates ────────────────────────────────────────────────────────────────
def test_estimate_scales_with_speed_and_language():
    sample = "x" * 1400
    assert text.estimate_seconds(sample, "a") == pytest.approx(100)
    assert text.estimate_seconds(sample, "a", speed=2.0) == pytest.approx(50)
    assert text.estimate_seconds(sample, "f") < text.estimate_seconds(sample, "a")
    assert text.estimate_seconds("   ") == 0


def test_count_words():
    assert text.count_words("  one two\nthree  ") == 3


# ── Clean text ───────────────────────────────────────────────────────────────
def test_clean_text_fixes_quotes_links_markdown_and_broken_lines():
    messy = (
        "# Title\n\n"
        "“Smart quotes” and a [link](https://example.com) to www.example.org.\n\n"
        "This line was broken in the middle of a sentence by the PDF\n"
        "converter and should be joined.\n\n"
        "- **bold** bullet"
    )
    assert text.clean_text(messy) == (
        "Title\n\n"
        '"Smart quotes" and a link to.\n\n'
        "This line was broken in the middle of a sentence by the PDF converter and should "
        "be joined.\n\n"
        "bold bullet"
    )


def test_clean_text_keeps_pronunciation_markup():
    assert text.clean_text("[Kokoro](/kˈOkəɹO/) speaks.") == "[Kokoro](/kˈOkəɹO/) speaks."


# ── Pronunciations ───────────────────────────────────────────────────────────
def test_pronunciations_replace_whole_words_longest_first():
    entries = [{"word": "New York", "say": "Newyork"}, {"word": "New York City", "say": "NYC"}]
    result = text.apply_pronunciations("I love new york city and New Yorkers.", entries)
    assert result == "I love NYC and New Yorkers."


def test_phoneme_pronunciations_only_apply_to_english():
    entries = [{"word": "Kokoro", "say": "/kˈOkəɹO/"}]
    assert text.apply_pronunciations("Kokoro!", entries, "a") == "[Kokoro](/kˈOkəɹO/)!"
    assert text.apply_pronunciations("Kokoro!", entries, "f") == "Kokoro!"


# ── Document extraction ──────────────────────────────────────────────────────
def _docx(paragraphs):
    import docx

    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_with_text(line: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({line}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


def _blank_pdf(password: str | None = None, pages: int = 1) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extract_plain_text_and_markdown():
    assert text.extract_text(b"Hello there.", "note.txt") == ("Hello there.", False)
    assert text.extract_text("﻿# Notes".encode(), "a.md")[0] == "# Notes"
    assert text.extract_text("café".encode("cp1252"), "old.txt")[0] == "café"


def test_extract_docx():
    data = _docx(["First paragraph.", "", "Second paragraph."])
    assert text.extract_text(data, "doc.docx") == ("First paragraph.\n\nSecond paragraph.", False)


def test_extract_pdf_text_is_cleaned():
    extracted, cleaned = text.extract_text(_pdf_with_text("Hello from a PDF"), "file.pdf")
    assert extracted == "Hello from a PDF"
    assert cleaned is True


@pytest.mark.parametrize(
    ("data", "name", "message"),
    [
        (b"MZ\x90\x00binary", "virus.exe", "Only .txt"),
        (b"not a pdf at all", "fake.pdf", "isn't a real PDF"),
        (b"plain text", "fake.docx", "isn't a real Word document"),
        (b"PK\x03\x04broken zip", "broken.docx", "damaged"),
        (b"%PDF-1.4 garbage", "broken.pdf", "damaged"),
        (b"\x00\x01\x02binary", "data.txt", "doesn't look like plain text"),
        (b"   \n ", "empty.txt", "no text"),
    ],
)
def test_extract_rejects_bad_files(data, name, message):
    with pytest.raises(text.ExtractError, match=message):
        text.extract_text(data, name)


def test_extract_rejects_password_protected_scanned_and_huge_pdfs():
    with pytest.raises(text.ExtractError, match="password-protected"):
        text.extract_text(_blank_pdf(password="secret"), "locked.pdf")
    with pytest.raises(text.ExtractError, match="no selectable text"):
        text.extract_text(_blank_pdf(), "scan.pdf")
    with pytest.raises(text.ExtractError, match="more than 3 pages"):
        text.extract_text(_blank_pdf(pages=4), "long.pdf", max_pdf_pages=3)
