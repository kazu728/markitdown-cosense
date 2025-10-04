# markitdown-cosense

A [MarkItDown](https://github.com/microsoft/markitdown) plugin that converts Cosense notation into Markdown.

## Features
- Headings: `[* Heading]` → `# Heading`
- Text styles: `[/ italic]`, `[** bold]`, `[*/ strong italic]`, `[- strikethrough]`
- Lists: indented bullets using spaces, tabs, or full-width spaces
- Code blocks: `code:language` and fenced ``` ``` sections
- Tables: `table:Title` directives with indented rows
- Links & media: `[Label https://example]`, `[img https://.../image.png]`
- Math: `code:tex` blocks and lightweight inline detection
- Tags: `[tag]` → `<!-- tag: tag -->`

## Installation
```bash
pip install markitdown markitdown-cosense
```

## CLI
```bash
markitdown --use-plugins note.txt > note.md
```

## Python
```python
from markitdown import MarkItDown, StreamInfo
from markitdown_cosense import register_converters

md = MarkItDown()
register_converters(md)

with open("note.txt", "rb") as fh:
    result = md.convert_stream(fh, stream_info=StreamInfo(extension=".txt"))

print(result.text_content)
```

## License
MIT © kazu728
