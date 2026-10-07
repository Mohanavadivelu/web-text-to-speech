"""Text handling: segmenting, cleanup, pronunciations, estimates and document extraction."""

from __future__ import annotations

import io
import re
import unicodedata

# ── Segmenting ───────────────────────────────────────────────────────────────
SEGMENT_CHARS = 800
_SENTENCE_END = re.compile(r"(?<=[.!?।॥…])\s+")
_CLAUSE_END = re.compile(r"(?<=[,;:—])\s+")


def split_segments(
    text: str, max_chars: int = SEGMENT_CHARS, first_segment_chars: int | None = None
) -> list[str]:
    """Split text into segments of at most max_chars, packing short paragraphs together.

    With first_segment_chars, the first segment is cut down to the first sentence
    (at most that many characters) so streaming can start quickly; the rest of it
    becomes the next segment.
    """
    segments = _split_paragraphs(text, max_chars)
    if first_segment_chars and segments and len(segments[0]) > first_segment_chars:
        head, rest = _split_head(segments[0], first_segment_chars)
        segments = [head] + ([rest] if rest else []) + segments[1:]
    return segments


def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # Break oversized paragraphs on sentence boundaries (hard-split overlong sentences)
    atomic: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            atomic.append(para)
            continue
        current = ""
        for sentence in _SENTENCE_END.split(para):
            if len(current) + len(sentence) + 1 <= max_chars:
                current = f"{current} {sentence}".strip()
                continue
            if current:
                atomic.append(current)
            while len(sentence) > max_chars:
                atomic.append(sentence[:max_chars])
                sentence = sentence[max_chars:]
            current = sentence
        if current:
            atomic.append(current)

    # Pack pieces into segments, so many short paragraphs don't become many tiny calls
    segments: list[str] = []
    bucket = ""
    for piece in atomic:
        sep = "\n\n" if bucket else ""
        if len(bucket) + len(sep) + len(piece) <= max_chars:
            bucket += sep + piece
        else:
            if bucket:
                segments.append(bucket)
            bucket = piece
    if bucket:
        segments.append(bucket)
    return segments


def _split_head(segment: str, limit: int) -> tuple[str, str]:
    """Split off the first sentence (cut at a clause or word boundary if over limit)."""
    first = _SENTENCE_END.split(segment, maxsplit=1)[0]
    if len(first) > limit:
        window = first[:limit]
        cut = max((m.end() for m in _CLAUSE_END.finditer(window)), default=0)
        if not cut:
            cut = window.rfind(" ") + 1
        first = first[: cut or limit]
    head = first.strip()
    return head, segment[len(first) :].strip()


def break_lines(text: str, max_chars: int = 200) -> str:
    """Put each sentence (or clause, or word group) on its own line of ≤ max_chars.

    Used for espeak languages: their G2P runs line by line, and a long Hindi
    sentence ending in "।" would otherwise reach the model as one oversized chunk.
    """
    lines: list[str] = []

    def pack(parts, splitter):
        cur = ""
        for part in parts:
            if len(part) > max_chars:
                if cur:
                    lines.append(cur)
                    cur = ""
                splitter(part)
            elif not cur:
                cur = part
            elif len(cur) + 1 + len(part) <= max_chars:
                cur = f"{cur} {part}"
            else:
                lines.append(cur)
                cur = part
        if cur:
            lines.append(cur)

    def by_words(part):
        pack(
            part.split(),
            lambda w: lines.extend(w[i : i + max_chars] for i in range(0, len(w), max_chars)),
        )

    def by_clause(part):
        pack(_CLAUSE_END.split(part), by_words)

    for para in text.splitlines():
        para = para.strip()
        if para:
            pack(_SENTENCE_END.split(para), by_clause)
    return "\n".join(lines)


# ── Estimates ────────────────────────────────────────────────────────────────
# Characters of speech per second at speed 1.0, measured with Kokoro-82M.
CHARS_PER_SECOND = {"a": 14.0, "b": 14.0, "h": 12.0, "f": 22.0, "e": 18.0, "i": 18.0, "p": 18.0}


def estimate_seconds(text: str, lang: str = "a", speed: float = 1.0) -> float:
    """Approximate length of the generated audio."""
    if not text.strip():
        return 0.0
    return len(text) / (CHARS_PER_SECOND.get(lang, 15.0) * max(0.1, speed))


def count_words(text: str) -> int:
    return len(text.split())


# ── Clean text ───────────────────────────────────────────────────────────────
_CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "′": "'", "″": '"', "«": '"', "»": '"',
    "–": " - ", "−": "-", "‐": "-", "‑": "-",
    " ": " ", " ": " ", " ": " ", " ": " ", "　": " ",
    "​": "", "‌": "", "‍": "", "﻿": "", "­": "",
    "…": "...", "•": "", "●": "", "▪": "", "‣": "",
}  # fmt: skip
# A URL never ends in sentence punctuation, so "see www.example.org." keeps its full stop
_URL = re.compile(r"(?:https?://|www\.)\S*[^\s.,;:!?)\"']", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# [text](url) -> text, but keep pronunciation markup [word](/phonemes/)
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?!/)[^)]*\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_MD_QUOTE = re.compile(r"^[ \t]*>+[ \t]?", re.MULTILINE)
_MD_BULLET = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+", re.MULTILINE)
_MD_RULE = re.compile(r"^[ \t]*(?:[-*_][ \t]*){3,}$", re.MULTILINE)
_MD_EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~|`+)(?=\S)(.+?)(?<=\S)\1")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_LINE_ENDS_SENTENCE = (".", "!", "?", ":", ";", '"', "'", ")", "।", "॥")


def clean_text(text: str) -> str:
    """Tidy pasted text so the voice reads it smoothly.

    Normalises quotes, dashes and invisible characters; removes links, e-mail
    addresses and markdown symbols; re-joins lines broken mid-sentence (common in
    PDFs); collapses extra spaces. Paragraph breaks are kept.
    """
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = "".join(_CHAR_MAP.get(ch, ch) for ch in text)

    text = _MD_IMAGE.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _EMAIL.sub("", text)
    text = _MD_RULE.sub("", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_QUOTE.sub("", text)
    text = _MD_BULLET.sub("", text)
    text = _MD_EMPHASIS.sub(r"\2", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in block.split("\n")]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue
        merged = lines[0]
        for ln in lines[1:]:
            # A line that ends a sentence, or a short heading-like line, stays on its own
            last = merged.rsplit("\n", 1)[-1]
            merged += (
                "\n" + ln if last.endswith(_LINE_ENDS_SENTENCE) or len(last) < 40 else " " + ln
            )
        paragraphs.append(merged)
    text = "\n\n".join(paragraphs)

    text = re.sub(r" +([,.!?;:])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ── Pronunciations ───────────────────────────────────────────────────────────
def apply_pronunciations(text: str, entries: list[dict], lang: str = "a") -> str:
    """Replace whole words (case-insensitive) with how they should be said.

    entries are {"word": ..., "say": ...}. A "say" value wrapped in slashes, like
    /kˈOkəɹO/, is phonemes and becomes [word](/phonemes/) markup, which only the
    English G2P understands; for other languages such entries are skipped.
    """
    if not entries:
        return text
    # Longest words first so "New York City" wins over "New York"
    for entry in sorted(entries, key=lambda e: -len(e["word"])):
        word, say = entry["word"].strip(), entry["say"].strip()
        if not word or not say:
            continue
        is_phonemes = len(say) > 2 and say.startswith("/") and say.endswith("/")
        if is_phonemes and lang not in ("a", "b"):
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)
        if is_phonemes:
            text = pattern.sub(lambda m, s=say: f"[{m.group(0)}]({s})", text)
        else:
            text = pattern.sub(lambda _m, s=say: s, text)
    return text


# ── Document extraction ──────────────────────────────────────────────────────
MAX_DOCUMENT_CHARS = 2_000_000
MAX_PDF_PAGES = 200
DOCUMENT_TYPES = (".txt", ".md", ".docx", ".pdf")


class ExtractError(ValueError):
    """The document can't be read; the message is safe to show to the user."""


def extract_text(
    data: bytes, filename: str, max_pdf_pages: int = MAX_PDF_PAGES
) -> tuple[str, bool]:
    """Return (text, was_cleaned) from an uploaded document.

    The file type comes from the extension and must match the content. PDF text
    is cleaned automatically because it is always hard-wrapped.
    """
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in DOCUMENT_TYPES:
        raise ExtractError("Only .txt, .md, .docx and .pdf files can be opened.")

    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ExtractError("This file isn't a real PDF.")
        text = _pdf_text(data, max_pdf_pages)
        cleaned = True
        text = clean_text(text)
    elif ext == ".docx":
        if not data.startswith(b"PK\x03\x04"):
            raise ExtractError("This file isn't a real Word document.")
        text, cleaned = _docx_text(data), False
    else:
        if b"\x00" in data[:8192] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise ExtractError("This file doesn't look like plain text.")
        text, cleaned = _decode(data), False

    if not text.strip():
        raise ExtractError("This document has no text.")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise ExtractError("This document is too long.")
    return text, cleaned


def _decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _docx_text(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractError("This Word document is damaged.") from exc
    return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())


def _pdf_text(data: bytes, max_pages: int) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
                _ = reader.pages[0]
            except Exception as exc:
                raise ExtractError("This PDF is password-protected.") from exc
        if len(reader.pages) > max_pages:
            raise ExtractError(f"This PDF has more than {max_pages} pages.")
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except ExtractError:
        raise
    except (PdfReadError, Exception) as exc:
        raise ExtractError("This PDF is damaged.") from exc
    if not text.strip():
        raise ExtractError("This PDF has no selectable text (it may be scanned images).")
    return text
