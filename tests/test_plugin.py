"""Unified test file for markitdown-cosense plugin."""

import io
import os
import re
import tempfile

import pytest
from markitdown import MarkItDown, StreamInfo

from markitdown_cosense import register_converters
from markitdown_cosense._plugin import (
    MarkdownConverter,
    apply_conversions,
    convert_code_blocks,
    convert_lists,
    convert_tables,
    protect_code_blocks,
    restore_code_blocks,
)


class TestPatternProcessor:
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
    def test_basic_conversions(self, input_text, expected):
        assert apply_conversions(input_text) == expected

    def test_tag_conversion(self):
        assert apply_conversions("[tag]") == "<!-- tag: tag -->"
        assert apply_conversions("[python]") == "<!-- tag: python -->"
        assert (
            apply_conversions("Text with [important] tag")
            == "Text with <!-- tag: important --> tag"
        )


class TestCodeBlockProcessor:
    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("code:example.py\nprint('Hello')", "```py\nprint('Hello')\n```"),
            (
                "code:test.js\nconsole.log('test');",
                "```js\nconsole.log('test');\n```",
            ),
            ("code:styles.css", "```css\n```"),
        ],
    )
    def test_basic_code_block_conversions(self, input_text, expected):
        result = convert_code_blocks(input_text)
        assert result == expected

    def test_latex_code_block_conversion(self):
        input_text = "code:tex\nE = mc^2\nV(X) = \\sigma^2"
        expected = "$E = mc^2$\n$V(X) = \\sigma^2$"

        assert convert_code_blocks(input_text) == expected

    def test_protect_and_restore_code_blocks(self):
        content = "Text before\n```python\ncode here\n```\nText after"
        protected, blocks = protect_code_blocks(content)
        restored = restore_code_blocks(protected, blocks)

        assert restored == content


class TestListProcessor:
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
    def test_basic_table_conversion(self):
        input_text = "table:User Data\n Name Age City\n Alice 25 Tokyo\n Bob 30 Osaka"
        expected = """## User Data

| Name | Age | City |
|---|---|---|
| Alice | 25 | Tokyo |
| Bob | 30 | Osaka |
"""

        assert convert_tables(input_text) == expected

    def test_table_without_name(self):
        input_text = "table:\n Col1 Col2\n A B"
        expected = """| Col1 | Col2 |
|---|---|
| A | B |
"""

        assert convert_tables(input_text) == expected


class TestMarkdownConverterIntegration:
    def test_mime_type_acceptance(self):
        converter = MarkdownConverter()
        stream = io.BytesIO(b"test")

        stream_info = StreamInfo(extension=".txt")
        assert converter.accepts(stream, stream_info)

        stream_info = StreamInfo(extension=".pdf")
        assert not converter.accepts(stream, stream_info)

    def test_comprehensive_conversion(self):
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

        from markitdown_cosense._plugin import _convert_content

        result = _convert_content(content)

        expected = """# Main Heading
## Sub Heading
*italic* and ~~strikethrough~~
***bold italic*** and **~~bold strikethrough~~**

Links and Images:
[Google](https://google.com)
![](https://example.com/image.png)
![img](https://example.com/logo.png)

Lists:
- Item 1
  - Nested 1-1
    - Deep nested
- Item 2

Code:
```python
def hello():
    print("world")

Math:
[$ E = mc^2 $]

```
$V(X) = E[(X-\\mu)^2]$

Table:
## Data

| Name | Score |
|---|---|
| Alice | 95 |
| Bob | 87 |"""

        assert result == expected


class TestPluginInterface:
    def test_register_converters_success(self):
        md = MarkItDown()

        register_converters(md)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("[* Test] and [tag]")
            temp_path = f.name

        try:
            result = md.convert(temp_path)
            expected = "# Test and <!-- tag: tag -->"
            assert result.text_content == expected
        finally:
            os.unlink(temp_path)


class TestExceptions:
    def test_pattern_compilation_error(self):
        from markitdown_cosense import _plugin

        original_patterns = _plugin.CONVERSION_PATTERNS
        _plugin.CONVERSION_PATTERNS = [("[invalid(regex", "test")]
        _plugin._compiled_patterns = None

        try:
            with pytest.raises(re.error):
                apply_conversions("test")
        finally:
            _plugin.CONVERSION_PATTERNS = original_patterns
            _plugin._compiled_patterns = None
