import re
from typing import (
    Any,
    BinaryIO,
    Dict,
    List,
    Tuple,
)

from markitdown import (
    DocumentConverter,
    DocumentConverterResult,
    MarkItDown,
    StreamInfo,
)

__plugin_interface_version__ = 1


ACCEPTED_FILE_EXTENSIONS = [".txt"]
IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "svg", "webp"]
CODE_BLOCK_PREFIX = "code:"
CODE_BLOCK_PLACEHOLDER = "<<<CODEBLOCK{}>>>"
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)

_image_extensions_pattern = None


def register_converters(markitdown: MarkItDown, **kwargs) -> None:
    markitdown.register_converter(MarkdownConverter())


class MarkdownConverter(DocumentConverter):
    def accepts(
        self, _file_stream: BinaryIO, stream_info: StreamInfo, **kwargs
    ) -> bool:
        extension = (stream_info.extension or "").lower()
        return extension in ACCEPTED_FILE_EXTENSIONS

    def convert(
        self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs
    ) -> DocumentConverterResult:
        file_stream.seek(0)
        content = file_stream.read().decode("utf-8")

        return DocumentConverterResult(_convert_content(content))


def _convert_content(content: str) -> str:
    content = convert_code_blocks(content)
    content, protected_blocks = protect_code_blocks(content)

    content = convert_tables(content)
    content = convert_lists(content)
    content = apply_conversions(content)

    return restore_code_blocks(content, protected_blocks)


def convert_code_blocks(content: str) -> str:
    lines = content.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip(" \t　")

        if stripped.startswith(CODE_BLOCK_PREFIX):
            indent = line[: len(line) - len(stripped)]
            filename = stripped[len(CODE_BLOCK_PREFIX) :].strip()

            code_lines, next_i = _collect_code_block_lines(lines, i + 1)

            if filename == "tex":
                _process_latex_block(code_lines, result, indent)
            else:
                if filename:
                    parts = filename.rsplit(".", 1)
                    lang = parts[1] if len(parts) == 2 else filename
                else:
                    lang = ""
                _add_code_block(result, lang, code_lines, bool(indent))

            i = next_i
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


def _collect_code_block_lines(
    lines: List[str], start_index: int
) -> Tuple[List[str], int]:
    code_lines = []
    base_indent = (
        calculate_base_indentation(lines[start_index])
        if start_index < len(lines) and lines[start_index].strip()
        else 0
    )
    consecutive_empty_lines = 0

    for i in range(start_index, len(lines)):
        line = lines[i]

        # Count consecutive empty lines
        if not line.strip():
            consecutive_empty_lines += 1
            # End block after 2 consecutive empty lines
            if consecutive_empty_lines >= 2:
                return code_lines[:-1], i  # Remove the last empty line
        else:
            consecutive_empty_lines = 0

        # Check for block end conditions
        if line.strip() and (
            calculate_base_indentation(line) < base_indent
            or line.lstrip(" \t　").startswith(CODE_BLOCK_PREFIX)
        ):
            return code_lines, i

        code_lines.append(line)

    return code_lines, len(lines)


def protect_code_blocks(content: str) -> Tuple[str, List[str]]:
    code_blocks = CODE_BLOCK_PATTERN.findall(content)

    def replacer(match):
        index = replacer.counter
        replacer.counter += 1
        return CODE_BLOCK_PLACEHOLDER.format(index)

    replacer.counter = 0
    protected_content = CODE_BLOCK_PATTERN.sub(replacer, content)

    return protected_content, code_blocks


def restore_code_blocks(content: str, code_blocks: List[str]) -> str:
    for i, code_block in enumerate(code_blocks):
        content = content.replace(CODE_BLOCK_PLACEHOLDER.format(i), code_block)
    return content


def get_image_extensions_pattern() -> re.Pattern[str]:
    global _image_extensions_pattern
    if _image_extensions_pattern is None:
        extensions = "|".join(IMAGE_EXTENSIONS)
        _image_extensions_pattern = re.compile(
            rf"\[(https?://[^\s\]]+\.(?:{extensions}))\]"
        )
    return _image_extensions_pattern


def calculate_base_indentation(line: str) -> int:
    for i, char in enumerate(line):
        if char not in (" ", "\t", "　"):
            return i
    return len(line)


def is_indented_line(line: str) -> bool:
    return bool(line and line[0] in (" ", "\t", "　"))


CONVERSION_PATTERNS = [
    # Tag pattern - must come first to avoid conflicts
    (
        r"\[(?!\*|img\s|/\s|-\s|\$|https?://|YouTube\s|Twitter\s|\w+\s+https?://)([^\[\]/\-\*\s][^\[\]/\-\*\]]*?)(?!\s+https?://)\]",
        r"<!-- tag: \1 -->",
    ),
    # Formatting patterns
    (r"\[\*/\s*(.*?)\]", r"***\1***"),
    (r"\[\*-\s*(.*?)\]", r"**~~\1~~**"),
    (r"\[/-\s*(.*?)\]", r"*~~\1~~*"),
    (r"\[\*\*\*\s*(.*?)\s*\*\*\*\]", r"**\1**"),
    (r"\[\*\*\s*(.*?)\s*\*\*\]", r"**\1**"),
    # Heading patterns
    (r"\[\*\*\*\*\*\s*(.*?)\]", r"##### \1"),
    (r"\[\*\*\*\*\s*(.*?)\]", r"#### \1"),
    (r"\[\*\*\*\s*(.*?)\]", r"### \1"),
    (r"\[\*\*\s*(.*?)\]", r"## \1"),
    (r"\[\*\s*(.*?)\]", r"# \1"),
    # Basic formatting
    (r"\[/\s*(.*?)\]", r"*\1*"),
    (r"\[-\s*(.*?)\]", r"~~\1~~"),
    (r"\[\$\s*(.*?)\s*\$\]", r"$\1$"),
    # Images and media
    (r"\[img\s+(https?://[^\s\]]+)\]", r"![img](\1)"),
    ("_DYNAMIC_IMAGE_PATTERN_", r"![](\1)"),  # Special marker for dynamic pattern
    (
        r"\[YouTube\s+(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|https?://youtu\.be/[\w-]+)\]",
        r"[YouTube Video](\1)",
    ),
    (
        r"\[Twitter\s+(https?://(?:www\.)?twitter\.com/\w+/status/\d+|https?://x\.com/\w+/status/\d+)\]",
        r"[Twitter Post](\1)",
    ),
    # Links
    (r"\[([^/\-\*\]]+?)\s+(https?://[^\s\]]+)\]", r"[\1](\2)"),
    (r"\[(https?://[^\s\]]+)\s+([^/\-\*\]]+?)\]", r"[\2](\1)"),
    # URL auto-linking
    (r'(?<!\()(https?://[^\s<>"\']+(?:\([^\s<>"\']*\)|[^\s<>"\']*)*)', r"<\1>"),
    # Blockquotes
    (r"^>\s*(.*)$", r"> \1"),
]

_compiled_patterns: List[Tuple[re.Pattern[str], str]] | None = None


def _get_compiled_patterns() -> List[Tuple[re.Pattern[str], str]]:
    global _compiled_patterns
    if _compiled_patterns is None:
        compiled = []
        for pattern_str, replacement in CONVERSION_PATTERNS:
            if pattern_str == "_DYNAMIC_IMAGE_PATTERN_":
                pattern = get_image_extensions_pattern()
            else:
                pattern = re.compile(pattern_str, re.MULTILINE)
            compiled.append((pattern, replacement))
        _compiled_patterns = compiled
    return _compiled_patterns


def apply_conversions(content: str) -> str:
    for pattern, replacement in _get_compiled_patterns():
        content = pattern.sub(replacement, content)
    return content


def _process_latex_block(
    code_lines: List[str], result: List[str], leading_indent: str
) -> None:
    math_operators = set("=+-*/^")
    math_indicators = ["E(", "V(", "Cov(", "σ", "μ", "√", "Φ", "\\", "^2", "_"]
    excluded_prefixes = ("![", "http", "<http", "->")

    for code_line in code_lines:
        stripped_line = code_line.strip()
        if not stripped_line:
            result.append("")
            continue

        has_math = any(c in stripped_line for c in math_operators) or any(
            indicator in stripped_line for indicator in math_indicators
        )

        if (
            not has_math
            or stripped_line.startswith(excluded_prefixes)
            or stripped_line == "code:tex"
        ):
            result.append(code_line.rstrip())
            continue

        has_japanese = any(
            "\u3040" <= c <= "\u309f"
            or "\u30a0" <= c <= "\u30ff"
            or "\u4e00" <= c <= "\u9faf"
            for c in stripped_line
        )

        if has_japanese:
            result.append(code_line.rstrip())
        else:
            result.append(f"{leading_indent}${stripped_line}$")


def _add_code_block(
    result: List[str],
    lang: str,
    code_lines: List[str],
    has_leading_indent: bool = False,
) -> None:
    if has_leading_indent:
        result.append("")

    result.append(f"```{lang}")
    result.extend(line if line.strip() else "" for line in code_lines)
    result.append("```")

    if has_leading_indent:
        result.append("")


def convert_lists(content: str) -> str:
    lines = content.splitlines()
    result = []

    for line in lines:
        if is_indented_line(line):
            indent_chars = 0
            for char in line:
                if char in (" ", "\t", "　"):
                    indent_chars += 1
                else:
                    break

            indent_level = max(0, indent_chars - 1)
            content = line[indent_chars:]
            markdown_indent = " " * (2 * indent_level)
            result.append(f"{markdown_indent}- {content}")
        else:
            result.append(line)

    return "\n".join(result)


def convert_tables(content: str) -> str:
    lines = content.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("table:"):
            processed_table = _process_table_block(lines, i)
            result.extend(processed_table["content"])
            i = processed_table["next_index"]
            continue

        result.append(line)
        i += 1

    return "\n".join(result)


def _process_table_block(lines: List[str], start_index: int) -> Dict[str, Any]:
    line = lines[start_index]
    result_content = []

    table_name = line[6:].strip()
    if table_name:
        result_content.append(f"## {table_name}")
        result_content.append("")

    table_rows = []
    i = start_index + 1
    while i < len(lines) and lines[i].startswith((" ", "\t")):
        row_content = lines[i].strip()
        if row_content:
            table_rows.append(row_content)
        i += 1

    if table_rows:
        header_row = table_rows[0]
        columns = [col.strip() for col in header_row.split()]

        if columns:
            result_content.append("| " + " | ".join(columns) + " |")
            result_content.append("|" + "---|" * len(columns))

            for row in table_rows[1:]:
                data_columns = [col.strip() for col in row.split()]
                while len(data_columns) < len(columns):
                    data_columns.append("")
                data_columns = data_columns[: len(columns)]
                result_content.append("| " + " | ".join(data_columns) + " |")

            result_content.append("")

    return {"content": result_content, "next_index": i}
