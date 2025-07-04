import logging
import re
from enum import Enum
from typing import (
    BinaryIO,
    Dict,
    List,
    Tuple,
    TypeAlias,
    TypedDict,
)

from markitdown import (
    DocumentConverter,
    DocumentConverterResult,
    MarkItDown,
    StreamInfo,
)

__plugin_interface_version__ = 1

logger = logging.getLogger(__name__)


class MarkdownCosenseError(Exception):
    pass


class DocumentConversionError(MarkdownCosenseError):
    pass


class PatternCompilationError(MarkdownCosenseError):
    pass


class EncodingError(MarkdownCosenseError):
    pass


class ConfigurationError(MarkdownCosenseError):
    pass


class TableProcessingError(MarkdownCosenseError):
    pass


class TagHandling(Enum):
    """Options for handling Scrapbox tag notation [tag]."""

    KEEP = "keep"
    HASHTAG = "hashtag"
    LINK = "link"
    COMMENT = "comment"
    CODE = "code"
    REMOVE = "remove"


class ConversionStep(TypedDict):
    pattern: str
    replacement: str


class CompiledConversionStep(TypedDict):
    pattern: re.Pattern[str]
    replacement: str


class TableProcessingResult(TypedDict):
    content: List[str]
    next_index: int


UnsupportedPattern: TypeAlias = Tuple[re.Pattern[str], str]
FileExtension: TypeAlias = str
LanguageName: TypeAlias = str
LanguageMapping: TypeAlias = Dict[FileExtension, LanguageName]
ContentLines: TypeAlias = List[str]
EncodingName: TypeAlias = str
PatternCache: TypeAlias = Dict[str, re.Pattern[str]]
ProcessingResult: TypeAlias = Tuple[ContentLines, int]


ACCEPTED_FILE_EXTENSIONS = [".txt"]
DEFAULT_ENCODING = "utf-8"
IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "svg", "webp"]
MARKDOWN_INDENT_SIZE = 2
EMPTY_LINE = ""
CODE_BLOCK_PREFIX = "code:"
CODE_BLOCK_PLACEHOLDER = "<<<CODEBLOCK{}>>>"

LANGUAGE_MAPPING: Dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "rb": "ruby",
    "rs": "rust",
    "cs": "csharp",
    "kt": "kotlin",
    "sh": "bash",
    "yml": "yaml",
}

MATH_OPERATORS = ["=", "+", "-", "*", "/", "^", "(", ")"]
MATH_FUNCTIONS = ["E(", "V(", "Cov(", "σ", "μ", "√", "Φ", "\\"]

ERROR_MESSAGES = {
    "invalid_markitdown": "markitdown must be an instance of MarkItDown",
    "pattern_compilation": "Failed to compile regex pattern {index}: {pattern} - {error}",
    "pattern_compilation_unexpected": "Error compiling pattern {index}: {error}",
    "invalid_start_index": "Invalid start_index {start_index} for lines of length {length}",
    "table_no_columns": "No valid columns found in header row",
    "invalid_tag_handling": "Invalid tag_handling option '{option}': {error}, using 'keep'",
    "document_conversion_failed": "Failed to convert document: {error}",
    "register_converter_failed": "Failed to register converter: {error}",
}

CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
WHITESPACE_PATTERN = re.compile(r"[ \t\u3000]")
LINE_SPLIT_PATTERN = re.compile(r"\r?\n")
BRACKET_NOTATION_PATTERN = re.compile(r"\[(?!\*|img\s)([^\]]*)\]")

BASE_UNSUPPORTED_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\{([^\}]*)\}"), "brace notation"),
]

_image_extensions_pattern = None
_pattern_cache: PatternCache = {}


def get_image_extensions_pattern() -> re.Pattern[str]:
    """Get cached compiled pattern for image extensions."""
    global _image_extensions_pattern
    if _image_extensions_pattern is None:
        extensions = "|".join(IMAGE_EXTENSIONS)
        _image_extensions_pattern = re.compile(
            rf"\[(https?://[^\s\]]+\.(?:{extensions}))\]"
        )
    return _image_extensions_pattern


def calculate_indentation(line: str) -> Tuple[int, str]:
    """Calculate indentation level and extract content from a line."""
    if not line:
        return 0, line

    char_index = 0
    for char in line:
        if char in (" ", "\t", "　"):
            char_index += 1
        else:
            break

    indent_level = max(0, char_index - 1)
    content = line[char_index:]
    return indent_level, content


def create_markdown_indent(level: int) -> str:
    """Create markdown indentation string."""
    return " " * (MARKDOWN_INDENT_SIZE * level)


def calculate_base_indentation(line: str) -> int:
    """Calculate base indentation level for a line."""
    if not line:
        return 0

    char_count = 0
    for char in line:
        if char in (" ", "\t", "　"):
            char_count += 1
        else:
            break
    return char_count


def is_indented_line(line: str) -> bool:
    """Check if a line starts with indentation."""
    return bool(line and line[0] in (" ", "\t", "　"))


def split_content_safely(content: str) -> list[str]:
    """Safely split content into lines."""
    if not content:
        return []

    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.split("\n")


def extract_filename_extension(filename: str) -> Tuple[str, str]:
    """Extract name and extension from filename."""
    if not filename:
        return "", ""

    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return filename, ""


class PatternProcessor:
    """Handles regex pattern matching and replacement for Scrapbox notation."""

    def __init__(self, tag_handling: TagHandling, image_extensions: List[str]) -> None:
        self.tag_handling = tag_handling
        self.image_extensions = image_extensions

        self.conversion_steps = self._create_conversion_steps()

        if self.tag_handling != TagHandling.KEEP:
            self.conversion_steps.append(self._get_tag_conversion_step())

        self._compile_conversion_patterns()

    def _create_conversion_steps(self) -> List[ConversionStep]:
        """Create the list of conversion steps."""
        return [
            {"pattern": r"\[\*/\s*(.*?)\]", "replacement": r"***\1***"},
            {"pattern": r"\[\*-\s*(.*?)\]", "replacement": r"**~~\1~~**"},
            {"pattern": r"\[/-\s*(.*?)\]", "replacement": r"*~~\1~~*"},
            {"pattern": r"\[\*\*\*\s*(.*?)\s*\*\*\*\]", "replacement": r"**\1**"},
            {"pattern": r"\[\*\*\s*(.*?)\s*\*\*\]", "replacement": r"**\1**"},
            {"pattern": r"\[\*\*\*\*\*\s*(.*?)\]", "replacement": r"##### \1"},
            {"pattern": r"\[\*\*\*\*\s*(.*?)\]", "replacement": r"#### \1"},
            {"pattern": r"\[\*\*\*\s*(.*?)\]", "replacement": r"### \1"},
            {"pattern": r"\[\*\*\s*(.*?)\]", "replacement": r"## \1"},
            {"pattern": r"\[\*\s*(.*?)\]", "replacement": r"# \1"},
            {"pattern": r"\[/\s*(.*?)\]", "replacement": r"*\1*"},
            {"pattern": r"\[-\s*(.*?)\]", "replacement": r"~~\1~~"},
            {"pattern": r"\[\$\s*(.*?)\s*\$\]", "replacement": r"$\1$"},
            {"pattern": r"\[img\s+(https?://[^\s\]]+)\]", "replacement": r"![img](\1)"},
            {"pattern": "_DYNAMIC_IMAGE_PATTERN_", "replacement": r"![](\1)"},
            {
                "pattern": r"\[YouTube\s+(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|https?://youtu\.be/[\w-]+)\]",
                "replacement": r"[YouTube Video](\1)",
            },
            {
                "pattern": r"\[Twitter\s+(https?://(?:www\.)?twitter\.com/\w+/status/\d+|https?://x\.com/\w+/status/\d+)\]",
                "replacement": r"[Twitter Post](\1)",
            },
            {
                "pattern": r"\[([^/\-\*\]]+?)\s+(https?://[^\s\]]+)\]",
                "replacement": r"[\1](\2)",
            },
            {
                "pattern": r"\[(https?://[^\s\]]+)\s+([^/\-\*\]]+?)\]",
                "replacement": r"[\2](\1)",
            },
            {
                "pattern": r'(?<!\()(https?://[^\s<>"\']+(?:\([^\s<>"\']*\)|[^\s<>"\']*)*)',
                "replacement": r"<\1>",
            },
            {"pattern": r"^>\s*(.*)$", "replacement": r"> \1"},
        ]

    def apply_conversions(self, content: str) -> str:
        """Apply all regex pattern conversions to the content."""
        if not content:
            return content

        for i, step in enumerate(self.compiled_patterns):
            content = self._apply_single_pattern(content, step, i)
        return content

    def _apply_single_pattern(self, content: str, step: dict, index: int) -> str:
        """Apply a single pattern conversion to content."""
        try:
            return step["pattern"].sub(step["replacement"], content)
        except Exception as e:
            logger.error(f"Pattern substitution failed for step {index}: {e}")
            return content

    def _compile_conversion_patterns(self) -> None:
        """Precompile regex patterns for better performance with caching."""
        self.compiled_patterns = []
        for i, step in enumerate(self.conversion_steps):
            try:
                compiled_pattern = self._get_compiled_pattern(step["pattern"])
                self.compiled_patterns.append(
                    {"pattern": compiled_pattern, "replacement": step["replacement"]}
                )
            except (re.error, PatternCompilationError) as e:
                self._handle_pattern_error(i, step["pattern"], e)

    def _get_compiled_pattern(self, pattern_str: str) -> re.Pattern[str]:
        """Get compiled pattern, using cache when possible."""
        if pattern_str == "_DYNAMIC_IMAGE_PATTERN_":
            return get_image_extensions_pattern()

        if pattern_str not in _pattern_cache:
            _pattern_cache[pattern_str] = re.compile(pattern_str, re.MULTILINE)
        return _pattern_cache[pattern_str]

    def _handle_pattern_error(self, index: int, pattern: str, error: Exception) -> None:
        """Handle pattern compilation errors."""
        if isinstance(error, re.error):
            logger.error(
                ERROR_MESSAGES["pattern_compilation"].format(
                    index=index, pattern=pattern, error=error
                )
            )
            raise PatternCompilationError(
                f"Invalid regex pattern: {pattern}"
            ) from error
        else:
            logger.error(
                ERROR_MESSAGES["pattern_compilation_unexpected"].format(
                    index=index, error=error
                )
            )
            raise PatternCompilationError(
                f"Error compiling pattern {index}: {error}"
            ) from error

    def _get_tag_conversion_step(self) -> ConversionStep:
        """Get the conversion step for handling tags based on the selected option."""
        tag_pattern = r"\[(?!\*|img\s|/\s|-\s|https?://|\w+\s+https?://)([^/\-\*\s][^/\-\*\]]*?)(?!\s+https?://)\]"

        if self.tag_handling == TagHandling.HASHTAG:
            replacement = r"#\1"
        elif self.tag_handling == TagHandling.LINK:
            replacement = r"[\1](#\1)"
        elif self.tag_handling == TagHandling.COMMENT:
            replacement = r"<!-- tag: \1 -->"
        elif self.tag_handling == TagHandling.CODE:
            replacement = r"`\1`"
        elif self.tag_handling == TagHandling.REMOVE:
            replacement = r""
        else:
            replacement = r"\1"

        return {"pattern": tag_pattern, "replacement": replacement}


def convert_code_blocks(content: str) -> str:
    """Convert Scrapbox code blocks to Markdown format."""
    if not content:
        return content

    lines = split_content_safely(content)
    if not lines:
        return content

    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped_line = line.lstrip(" \t　")

        if stripped_line.startswith(CODE_BLOCK_PREFIX):
            i = _process_code_block(lines, i, result)
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


def _process_code_block(
    lines: ContentLines, line_index: int, result: ContentLines
) -> int:
    """Process a single code block and add it to result."""
    line = lines[line_index]
    stripped_line = line.lstrip(" \t　")
    leading_indent = line[: len(line) - len(stripped_line)]
    filename = stripped_line[len(CODE_BLOCK_PREFIX) :].strip()

    line_index += 1
    code_lines, next_index = _collect_code_block_lines(lines, line_index)

    if filename == "tex":
        _process_latex_block(code_lines, result, leading_indent)
    else:
        lang = _extract_language_from_filename(filename)
        _add_code_block(result, lang, code_lines, bool(leading_indent))

    return next_index


def _process_latex_block(
    code_lines: ContentLines, result: ContentLines, leading_indent: str
) -> None:
    """Process LaTeX code block and convert to math notation."""
    for code_line in code_lines:
        stripped_line = code_line.strip()

        if stripped_line:
            if _is_mathematical_expression(stripped_line):
                result.append(f"{leading_indent}${stripped_line}$")
            else:
                result.append(code_line.rstrip())
        else:
            result.append(EMPTY_LINE)


def _extract_language_from_filename(filename: str) -> LanguageName:
    """Extract programming language from filename or extension."""
    if not filename:
        return ""

    try:
        name, ext = extract_filename_extension(filename)
        if ext:
            return LANGUAGE_MAPPING.get(ext, ext)
        return LANGUAGE_MAPPING.get(filename, filename)
    except (AttributeError, IndexError) as e:
        logger.warning(f"Failed to extract language from filename '{filename}': {e}")
        return ""


def _collect_code_block_lines(
    lines: ContentLines, start_index: int
) -> ProcessingResult:
    """Collect lines belonging to a code block."""
    if not lines or start_index < 0 or start_index >= len(lines):
        logger.warning(
            ERROR_MESSAGES["invalid_start_index"].format(
                start_index=start_index, length=len(lines)
            )
        )
        return [], start_index

    code_lines = []
    base_indent = calculate_base_indentation(lines[start_index])

    for i in range(start_index, len(lines)):
        line = lines[i]

        if not line.strip():
            code_lines.append(line)
            continue

        current_indent = calculate_base_indentation(line)

        if current_indent < base_indent:
            return code_lines, i

        if line.lstrip(" \t　").startswith(CODE_BLOCK_PREFIX):
            return code_lines, i

        code_lines.append(line)

    return code_lines, len(lines)


def _is_mathematical_expression(text: str) -> bool:
    """Determine if a text line contains mathematical expressions."""
    has_math_symbols = _contains_math_symbols(text)
    is_excluded_content = _is_excluded_content(text, has_math_symbols)
    return has_math_symbols and not is_excluded_content


def _contains_math_symbols(text: str) -> bool:
    """Check if text contains mathematical operators or functions."""
    for char in MATH_OPERATORS:
        if char in text:
            return True
    for func in MATH_FUNCTIONS:
        if func in text:
            return True
    return False


def _is_excluded_content(text: str, has_math_symbols: bool) -> bool:
    """Check if text should be excluded from mathematical expression treatment."""
    excluded_prefixes = ("![", "http", "<http", "->")
    if text.startswith(excluded_prefixes) or text == "code:tex":
        return True

    for char in text:
        if (
            "\u3040" <= char <= "\u309f"
            or "\u30a0" <= char <= "\u30ff"
            or "\u4e00" <= char <= "\u9faf"
        ):
            return not has_math_symbols

    return False


def _add_code_block(
    result: ContentLines,
    lang: LanguageName,
    code_lines: ContentLines,
    has_leading_indent: bool = False,
) -> None:
    """Add a code block to the result list with proper formatting."""
    if has_leading_indent:
        result.append(EMPTY_LINE)

    result.append(f"```{lang}")
    _add_code_lines(result, code_lines)
    result.append("```")

    if has_leading_indent:
        result.append(EMPTY_LINE)


def _add_code_lines(result: ContentLines, code_lines: ContentLines) -> None:
    """Add code lines to result, stripping leading whitespace from each line."""
    for code_line in code_lines:
        if code_line.strip():
            result.append(code_line.lstrip(" \t　"))


def protect_code_blocks(content: str) -> Tuple[str, List[str]]:
    """Protect existing markdown code blocks from further processing."""
    code_blocks: List[str] = []
    for i, match in enumerate(CODE_BLOCK_PATTERN.findall(content)):
        code_blocks.append(match)
        content = content.replace(match, CODE_BLOCK_PLACEHOLDER.format(i), 1)
    return content, code_blocks


def restore_code_blocks(content: str, code_blocks: List[str]) -> str:
    """Restore protected code blocks."""
    for i, code_block in enumerate(code_blocks):
        placeholder = CODE_BLOCK_PLACEHOLDER.format(i)
        content = content.replace(placeholder, code_block)
    return content


def convert_lists(content: str) -> str:
    """Convert Scrapbox list notation to Markdown lists with proper indentation."""
    if not content:
        return content

    lines = split_content_safely(content)
    result = []

    for line in lines:
        if is_indented_line(line):
            indent_level, list_content = calculate_indentation(line)
            markdown_indent = create_markdown_indent(indent_level)
            result.append(f"{markdown_indent}- {list_content}")
        else:
            result.append(line)

    return "\n".join(result)


def convert_tables(content: str) -> str:
    """Convert Scrapbox table notation to Markdown tables."""
    if not content:
        return content

    lines = split_content_safely(content)
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("table:"):
            try:
                processed_table = _process_table_block(lines, i)
                result.extend(processed_table["content"])
                i = processed_table["next_index"]
                continue
            except TableProcessingError as e:
                logger.warning(f"Failed to process table at line {i}: {e}")

        result.append(line)
        i += 1

    return "\n".join(result)


def _process_table_block(lines, start_index):
    """Process a single table block starting at the given index."""
    if start_index >= len(lines):
        raise TableProcessingError(f"Invalid start index {start_index}")

    line = lines[start_index]
    if not line.startswith("table:"):
        raise TableProcessingError(f"Line does not start with 'table:': {line}")

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

        if not columns:
            raise TableProcessingError(ERROR_MESSAGES["table_no_columns"])

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


def register_converters(markitdown: MarkItDown, **kwargs) -> None:
    """
    Register Scrapbox to Markdown converters with the MarkItDown instance.

    Parameters
    ----------
    markitdown : MarkItDown
        The MarkItDown instance to register converters with.
    **kwargs : dict, optional
        Additional configuration options:
        tag_handling : str, default "comment"
            How to handle Scrapbox tag notation [tag].
    """

    tag_handling = kwargs.get("tag_handling", "comment")
    try:
        tag_handling_enum = TagHandling(tag_handling)
    except ValueError as e:
        logger.warning(
            ERROR_MESSAGES["invalid_tag_handling"].format(option=tag_handling, error=e)
        )
        tag_handling_enum = TagHandling.COMMENT

    markitdown.register_converter(MarkdownConverter(tag_handling=tag_handling_enum))


class MarkdownConverter(DocumentConverter):
    """Main converter class for Scrapbox to Markdown conversion."""

    def __init__(self, tag_handling: TagHandling = TagHandling.COMMENT):
        self.tag_handling = tag_handling
        self.pattern_processor = PatternProcessor(tag_handling, IMAGE_EXTENSIONS)

        self.unsupported_patterns = BASE_UNSUPPORTED_PATTERNS.copy()
        if self.tag_handling == TagHandling.KEEP:
            self.unsupported_patterns.append(
                (re.compile(r"\[(?!\*|img\s)([^\]]*)\]"), "bracket notation")
            )

    def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs) -> bool:
        extension = (stream_info.extension or "").lower()
        return extension in ACCEPTED_FILE_EXTENSIONS

    def convert(
        self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs
    ) -> DocumentConverterResult:
        try:
            content = self._read_file_content(file_stream, stream_info)
            markdown = self._convert_content(content)

            return DocumentConverterResult(
                title=None,
                markdown=markdown,
            )
        except Exception as e:
            logger.error(f"Document conversion failed: {e}")
            raise DocumentConversionError(
                ERROR_MESSAGES["document_conversion_failed"].format(error=e)
            ) from e

    def _convert_content(self, content: str) -> str:
        """Convert Scrapbox content to Markdown through a multi-step pipeline."""
        content, protected_blocks = protect_code_blocks(content)

        content = convert_code_blocks(content)

        content, new_protected_blocks = protect_code_blocks(content)
        protected_blocks.extend(new_protected_blocks)

        content = convert_tables(content)
        content = convert_lists(content)

        content = self.pattern_processor.apply_conversions(content)

        content = restore_code_blocks(content, protected_blocks)

        self._check_unsupported_notations(content)

        return content

    def _read_file_content(self, file_stream: BinaryIO, stream_info: StreamInfo) -> str:
        """Read file content with robust encoding handling."""
        encodings_to_try = [
            stream_info.charset or DEFAULT_ENCODING,
            "utf-8",
            "latin-1",
            "cp1252",
        ]

        encodings_to_try = list(dict.fromkeys(encodings_to_try))

        for encoding in encodings_to_try:
            try:
                file_stream.seek(0)
                return file_stream.read().decode(encoding)
            except UnicodeDecodeError as e:
                logger.warning(f"Failed to decode with {encoding}: {e}")
                continue
            except IOError as e:
                raise EncodingError(f"Failed to read file: {e}") from e

        file_stream.seek(0)
        logger.warning("Using UTF-8 with error replacement as last resort")
        return file_stream.read().decode("utf-8", errors="replace")

    def _check_unsupported_notations(self, content: str) -> None:
        """Check for unsupported notations and log warnings."""
        for pattern, notation_type in self.unsupported_patterns:
            for match in pattern.finditer(content):
                logger.warning(
                    f"Unsupported {notation_type} detected: "
                    f"'{match.group(0)}' at position {match.start()}"
                )
