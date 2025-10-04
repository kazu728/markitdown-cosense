"""Integration-level tests for the Cosense → Markdown plugin."""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from pathlib import Path

import pytest
from markitdown import MarkItDown, StreamInfo

from markitdown_cosense import register_converters
from markitdown_cosense._plugin import IMAGE_EXTENSIONS, MarkdownConverter
from markitdown_cosense.renderer import InlineProcessor, build_inline_rules

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def markitdown_with_cosense() -> MarkItDown:
    md = MarkItDown()
    register_converters(md)
    return md


@pytest.fixture()
def converter() -> MarkdownConverter:
    return MarkdownConverter()


@pytest.fixture()
def inline_processor() -> InlineProcessor:
    return InlineProcessor(build_inline_rules(IMAGE_EXTENSIONS))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _convert_stream(md: MarkItDown, text: str, extension: str = ".txt") -> str:
    stream = io.BytesIO(text.encode("utf-8"))
    result = md.convert_stream(stream, stream_info=StreamInfo(extension=extension))
    return result.text_content


def _bytes_stream(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            "[* Title]\n[tag]",
            "# Title\n<!-- tag: tag -->",
        ),
        (
            "code:python\nprint('hello')",
            "```python\nprint('hello')\n```",
        ),
        (
            "table:Data\n Name Age\n Alice 30\n Bob 25",
            "## Data\n\n| Name | Age |\n|---|---|\n| Alice | 30 |\n| Bob | 25 |",
        ),
    ],
    ids=["heading", "code", "table"],
)
def test_conversion_via_markitdown(
    markitdown_with_cosense: MarkItDown, source: str, expected: str
) -> None:
    output = _convert_stream(markitdown_with_cosense, source, ".txt")
    assert output == expected


# ---------------------------------------------------------------------------
# Converter accept heuristics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "snippet,expected",
    [
        ("[* Heading]\n[tag]", True),
        ("code:python\nprint()", True),
        ("table:Users\n Name", True),
        ("Plain text without markers", False),
        ("", False),
    ],
    ids=["heading", "code", "table", "plain", "empty"],
)
def test_accepts_heuristics(
    converter: MarkdownConverter, snippet: str, expected: bool
) -> None:
    stream = _bytes_stream(snippet)
    info = StreamInfo(extension=".md")
    assert converter.accepts(stream, info) is expected


def test_accepts_does_not_consume_stream(converter: MarkdownConverter) -> None:
    payload = "[* note]\n[tag]"
    stream = _bytes_stream(payload)
    info = StreamInfo(extension=".md")
    assert converter.accepts(stream, info)
    remaining = stream.read().decode("utf-8")
    assert remaining == payload


# ---------------------------------------------------------------------------
# Inline processor behaviour
# ---------------------------------------------------------------------------


def test_inline_rules_are_stable(inline_processor: InlineProcessor) -> None:
    assert inline_processor.apply("[tag]") == "<!-- tag: tag -->"
    assert inline_processor.apply("[/ text]") == "*text*"


def test_invalid_inline_pattern_raises() -> None:
    with pytest.raises(re.error):
        InlineProcessor([("[invalid(regex", "replacement")])


# ---------------------------------------------------------------------------
# Filesystem integration via MarkItDown API
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lines",
    [pytest.param(["[* File Heading]", "[img https://example.com/logo.png]"])],
)
def test_markitdown_convert_from_file(
    markitdown_with_cosense: MarkItDown, tmp_path: Path, lines: Iterable[str]
) -> None:
    payload = "\n".join(lines)
    path = tmp_path / "note.txt"
    path.write_text(payload, encoding="utf-8")

    result = markitdown_with_cosense.convert(path)
    assert "# File Heading" in result.text_content
    assert "![img](https://example.com/logo.png)" in result.text_content
