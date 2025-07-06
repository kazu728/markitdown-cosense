# markitdown-cosense

A [markitdown](https://github.com/microsoft/markitdown) plugin for converting Scrapbox notation to Markdown.

## Features

This plugin converts various Scrapbox notations to standard Markdown format:

- **Headings**: `[* Heading]` → `# Heading`
- **Text decorations**: `[/ italic]`, `[- strikethrough]`, `[** bold]`
- **Lists**: Indented lines with spaces, tabs, or full-width spaces
- **Code blocks**: `code:language` notation
- **Tables**: `table:name` notation
- **Links and images**: `[title url]`, `[img url]`
- **Math expressions**: `[$ formula $]` → `$formula$`
- **LaTeX blocks**: `code:tex` with mathematical content

## Installation

```bash
pip install markitdown-cosense
```

## Usage

### With markitdown CLI

```bash
# List available plugins
markitdown --list-plugins

# Convert a file using the plugin
markitdown --use-plugins your-file.txt
```

### Programmatic usage

```python
from markitdown import MarkItDown
from markitdown_cosense import register_converters

# Initialize markitdown
md = MarkItDown()

# Register the converter
register_converters(md)

# Convert a file
result = md.convert("your-scrapbox-file.txt")
print(result.text_content)
```

## Features

- Converts Scrapbox notation to standard Markdown
- Handles headings, formatting, links, images, lists, tables, code blocks, and math notation
- Converts tags `[tag]` to HTML comments `<!-- tag: tag -->` to preserve information while maintaining valid Markdown