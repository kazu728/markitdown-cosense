"""Unified test file for markitdown-cosense plugin."""

import io
import tempfile

import pytest
from markitdown import MarkItDown, StreamInfo

from markitdown_cosense import TagHandling, register_converters
from markitdown_cosense._plugin import (
    ConfigurationError,
    DocumentConversionError,
    EncodingError,
    MarkdownConverter,
    PatternCompilationError,
    PatternProcessor,
    TableProcessingError,
    convert_code_blocks,
    convert_lists,
    convert_tables,
    protect_code_blocks,
    restore_code_blocks,
)


@pytest.fixture
def pattern_processor():
    """Create a basic pattern processor for testing."""
    return PatternProcessor(
        TagHandling.KEEP, ["png", "jpg", "jpeg", "gif", "svg", "webp"]
    )


@pytest.fixture
def markdown_converter():
    """Create a markdown converter for testing."""
    return MarkdownConverter(TagHandling.KEEP)


class TestPatternProcessor:
    """Test pattern processing functionality."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("[* Heading]", "# Heading"),
            ("[** Heading]", "## Heading"),
            ("[*** Heading]", "### Heading"),
            ("[**** Heading]", "#### Heading"),
            ("[***** Heading]", "##### Heading"),
            ("[/ italic text]", "*italic text*"),
            ("[- strikethrough text]", "~~strikethrough text~~"),
            ("[** bold text **]", "**bold text**"),
            ("[*** bold text ***]", "**bold text**"),
            ("[*/ bold italic]", "***bold italic***"),
            ("[*- bold strikethrough]", "**~~bold strikethrough~~**"),
            ("[/- italic strikethrough]", "*~~italic strikethrough~~*"),
            ("[$ E = mc^2 $]", "$E = mc^2$"),
            (
                "[YouTube https://www.youtube.com/watch?v=dQw4w9WgXcQ]",
                "[YouTube Video](https://www.youtube.com/watch?v=dQw4w9WgXcQ)",
            ),
            (
                "[Twitter https://twitter.com/user/status/123456789]",
                "[Twitter Post](https://twitter.com/user/status/123456789)",
            ),
            ("[Link Title https://example.com]", "[Link Title](https://example.com)"),
            ("[https://example.com Link Title]", "[Link Title](https://example.com)"),
            ("[https://example.com/image.jpg]", "![](https://example.com/image.jpg)"),
            (
                "[img https://example.com/image.jpg]",
                "![img](https://example.com/image.jpg)",
            ),
            ("Check https://example.com", "Check <https://example.com>"),
            ("> This is a quote", "> This is a quote"),
        ],
    )
    def test_basic_conversions(self, pattern_processor, input_text, expected):
        result = pattern_processor.apply_conversions(input_text)
        assert result == expected

    @pytest.mark.parametrize(
        "tag_handling,input_text,expected",
        [
            (TagHandling.KEEP, "[tag]", "[tag]"),
            (TagHandling.HASHTAG, "[tag]", "#tag"),
            (TagHandling.LINK, "[tag]", "[tag](#tag)"),
            (TagHandling.COMMENT, "[tag]", "<!-- tag: tag -->"),
            (TagHandling.CODE, "[tag]", "`tag`"),
            (TagHandling.REMOVE, "[tag]", ""),
        ],
    )
    def test_tag_handling_options(self, tag_handling, input_text, expected):
        processor = PatternProcessor(tag_handling, [])
        result = processor.apply_conversions(input_text)
        assert result == expected


class TestCodeBlockProcessor:
    """Test code block processing functionality."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("code:example.py\nprint('Hello')", "```python\nprint('Hello')\n```"),
            (
                "code:test.js\nconsole.log('test');",
                "```javascript\nconsole.log('test');\n```",
            ),
            ("code:styles.css", "```css\n```"),
        ],
    )
    def test_basic_code_block_conversions(self, input_text, expected):
        result = convert_code_blocks(input_text)
        assert result == expected

    def test_latex_code_block_conversion(self):
        input_text = "code:tex\nE = mc^2\nV(X) = \\sigma^2"
        result = convert_code_blocks(input_text)
        assert "$E = mc^2$" in result
        assert "$V(X) = \\sigma^2$" in result

    def test_protect_and_restore_code_blocks(self):
        content = "Text before\n```python\ncode here\n```\nText after"
        protected, blocks = protect_code_blocks(content)

        assert "<<<CODEBLOCK0>>>" in protected
        assert "```python\ncode here\n```" not in protected
        assert len(blocks) == 1

        restored = restore_code_blocks(protected, blocks)
        assert restored == content


class TestListProcessor:
    """Test list processing functionality."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            (" Test", "- Test"),
            ("  Indented", "  - Indented"),
            ("   Further indented", "    - Further indented"),
            ("\tTab indented", "- Tab indented"),
            ("　Full-width space", "- Full-width space"),
        ],
    )
    def test_list_conversions(self, input_text, expected):
        result = convert_lists(input_text)
        assert result == expected

    def test_nested_list_indentation(self):
        input_text = (
            " Item 1\n  Sub-item 1.1\n   Sub-sub-item 1.1.1\n  Sub-item 1.2\n Item 2"
        )
        result = convert_lists(input_text)

        expected_lines = [
            "- Item 1",
            "  - Sub-item 1.1",
            "    - Sub-sub-item 1.1.1",
            "  - Sub-item 1.2",
            "- Item 2",
        ]
        assert result == "\n".join(expected_lines)


class TestTableProcessor:
    """Test table processing functionality."""

    def test_basic_table_conversion(self):
        input_text = "table:User Data\n Name Age City\n Alice 25 Tokyo\n Bob 30 Osaka"
        result = convert_tables(input_text)

        assert "## User Data" in result
        assert "| Name | Age | City |" in result
        assert "|---|---|---|" in result
        assert "| Alice | 25 | Tokyo |" in result
        assert "| Bob | 30 | Osaka |" in result

    def test_table_without_name(self):
        input_text = "table:\n Col1 Col2\n A B"
        result = convert_tables(input_text)

        assert "| Col1 | Col2 |" in result
        assert "| A | B |" in result


class TestMarkdownConverterIntegration:
    """Test full converter integration."""

    def test_mime_type_acceptance(self, markdown_converter):
        """Test that converter accepts correct file types."""
        stream = io.BytesIO(b"test")

        stream_info = StreamInfo(extension=".txt")
        assert markdown_converter.accepts(stream, stream_info)

        stream_info = StreamInfo(extension=".pdf")
        assert not markdown_converter.accepts(stream, stream_info)

    def test_comprehensive_conversion(self, markdown_converter):
        """Test comprehensive conversion of various Scrapbox notations."""
        content = """[* Main Heading]
[** Sub Heading]
[/ italic] and [- strikethrough]
[*/ bold italic] and [*- bold strikethrough]

Links and Images:
[Google https://google.com]
[https://example.com/image.png]
[img https://example.com/logo.png]

Lists:
 Item 1
  Nested 1-1
   Deep nested
 Item 2

Code:
code:python
def hello():
    print("world")

Math:
[$ E = mc^2 $]

code:tex
V(X) = E[(X-\\mu)^2]

Table:
table:Data
 Name Score
 Alice 95
 Bob 87"""

        result = markdown_converter._convert_content(content)

        assert "# Main Heading" in result
        assert "## Sub Heading" in result

        assert "*italic*" in result
        assert "~~strikethrough~~" in result
        assert "***bold italic***" in result
        assert "**~~bold strikethrough~~**" in result

        assert "[Google](https://google.com)" in result
        assert "![](https://example.com/image.png)" in result
        assert "![img](https://example.com/logo.png)" in result

        assert "- Item 1" in result
        assert "  - Nested 1-1" in result
        assert "    - Deep nested" in result

        assert "```python" in result
        assert "def hello():" in result
        assert 'print("world")' in result

        assert "E = mc^2" in result
        assert "$V(X) = E[(X-\\mu)^2]$" in result

        assert "## Data" in result
        assert "| Name | Score |" in result
        assert "| Alice | 95 |" in result


class TestPluginInterface:
    """Test plugin interface functionality."""

    def test_register_converters_success(self):
        """Test successful converter registration."""
        md = MarkItDown()

        register_converters(md, tag_handling="hashtag")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("[* Test] and [tag]")
            temp_path = f.name

        try:
            result = md.convert(temp_path)
            assert "# Test" in result.text_content
            assert "#tag" in result.text_content
        finally:
            import os

            os.unlink(temp_path)

    def test_register_converters_invalid_markitdown(self):
        """Test error handling for invalid markitdown instance."""
        with pytest.raises(ConfigurationError):
            register_converters("not_markitdown", tag_handling="keep")

    def test_tag_handling_options(self):
        """Test different tag handling options."""
        md = MarkItDown()

        test_cases = [
            ("keep", "[tag]"),
            ("hashtag", "#tag"),
            ("link", "[tag](#tag)"),
            ("comment", "<!-- tag: tag -->"),
            ("code", "`tag`"),
            ("remove", ""),
        ]

        for tag_option, expected in test_cases:
            md = MarkItDown()
            register_converters(md, tag_handling=tag_option)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                f.write("[tag]")
                temp_path = f.name

            try:
                result = md.convert(temp_path)
                if expected:
                    assert expected in result.text_content
                else:
                    assert (
                        "tag" not in result.text_content
                        or "[tag]" in result.text_content
                    )
            finally:
                import os

                os.unlink(temp_path)


class TestExceptions:
    """Test exception handling."""

    def test_all_exceptions_accessible(self):
        """Test that all exceptions are accessible and work correctly."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("test")

        with pytest.raises(DocumentConversionError):
            raise DocumentConversionError("test")

        with pytest.raises(PatternCompilationError):
            raise PatternCompilationError("test")

        with pytest.raises(EncodingError):
            raise EncodingError("test")

        with pytest.raises(TableProcessingError):
            raise TableProcessingError("test")

    def test_pattern_compilation_error(self):
        """Test pattern compilation error handling."""
        processor = PatternProcessor(TagHandling.KEEP, [])
        processor.conversion_steps = [
            {"pattern": "[invalid(regex", "replacement": "test"}
        ]

        with pytest.raises(PatternCompilationError):
            processor._compile_conversion_patterns()


class TestModuleAttributes:
    """Test module attributes and constants."""

    def test_module_has_all_attributes(self):
        """Test that the module has all expected attributes."""
        from markitdown_cosense import _plugin

        assert hasattr(_plugin, "MarkdownConverter")
        assert hasattr(_plugin, "PatternProcessor")

        assert hasattr(_plugin, "register_converters")
        assert hasattr(_plugin, "convert_code_blocks")
        assert hasattr(_plugin, "convert_lists")
        assert hasattr(_plugin, "convert_tables")

        assert hasattr(_plugin, "__plugin_interface_version__")
        assert _plugin.__plugin_interface_version__ == 1

    def test_important_constants(self):
        """Test that important constants are defined correctly."""
        from markitdown_cosense._plugin import (
            ACCEPTED_FILE_EXTENSIONS,
            CODE_BLOCK_PREFIX,
            DEFAULT_ENCODING,
            IMAGE_EXTENSIONS,
            LANGUAGE_MAPPING,
        )

        assert ".txt" in ACCEPTED_FILE_EXTENSIONS
        assert DEFAULT_ENCODING == "utf-8"
        assert "png" in IMAGE_EXTENSIONS
        assert CODE_BLOCK_PREFIX == "code:"
        assert LANGUAGE_MAPPING["py"] == "python"
