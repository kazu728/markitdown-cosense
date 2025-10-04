from __future__ import annotations

from contextlib import suppress
from typing import BinaryIO

from markitdown import (
    DocumentConverter,
    DocumentConverterResult,
    MarkItDown,
    StreamInfo,
)

from .parser import HEADING_START_PATTERN
from .renderer import CosenseEngine

__plugin_interface_version__ = 1

IMAGE_EXTENSIONS: tuple[str, ...] = ("png", "jpg", "jpeg", "gif", "svg", "webp")
COSENSE_MARKERS: tuple[str, ...] = (
    "[img ",
    "[YouTube ",
    "[Twitter ",
    "[*/",
    "[*/ ",
    "[*-",
    "[/ ",
    "[- ",
    "code:",
    "table:",
)


DEFAULT_ENGINE = CosenseEngine(image_extensions=IMAGE_EXTENSIONS)


def register_converters(markitdown: MarkItDown, **_: object) -> None:
    markitdown.register_converter(MarkdownConverter(engine=DEFAULT_ENGINE))


class MarkdownConverter(DocumentConverter):
    def __init__(self, engine: CosenseEngine | None = None) -> None:
        self._engine = engine or CosenseEngine(image_extensions=IMAGE_EXTENSIONS)

    def accepts(
        self, _file_stream: BinaryIO, stream_info: StreamInfo, **_: object
    ) -> bool:
        text = self._peek_text(_file_stream)
        if not text:
            return False

        return self._looks_like_cosense(text)

    def convert(
        self, file_stream: BinaryIO, stream_info: StreamInfo, **_: object
    ) -> DocumentConverterResult:
        with suppress(OSError):
            file_stream.seek(0)
        content = file_stream.read().decode("utf-8")

        return DocumentConverterResult(self._engine.convert(content))

    def _peek_text(self, file_stream: BinaryIO, size: int = 4096) -> str:
        current_pos: int | None = None
        with suppress(AttributeError, OSError):
            current_pos = file_stream.tell()

        snippet = file_stream.read(size)
        if current_pos is not None:
            with suppress(OSError):
                file_stream.seek(current_pos)
        return snippet.decode("utf-8", errors="ignore") if snippet else ""

    def _looks_like_cosense(self, text: str) -> bool:
        stripped_lines = (line.strip() for line in text.splitlines())
        return any(
            stripped
            and (
                stripped.startswith(COSENSE_MARKERS)
                or HEADING_START_PATTERN.match(stripped)
            )
            for stripped in stripped_lines
        )
