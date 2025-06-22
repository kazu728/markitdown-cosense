# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
markitdown-cosense is a Python plugin for the markitdown library that converts Scrapbox notation to standard Markdown. Scrapbox is a Japanese collaborative documentation platform with its own notation system.

## Technology Stack
- Python 3.10+
- uv (package manager and tool runner)
- pytest (testing)
- ruff (linting and formatting)
- pyright (type checking)
- markitdown (base library)

## Development Commands

### Setup
```bash
# Install all dependencies including dev tools
uv sync
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test class
uv run pytest tests/test_plugin.py::TestPatternProcessor
```

### Linting and Formatting
```bash
# Check code style and format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Format code
uv run ruff format src/ tests/

# Fix auto-fixable issues
uv run ruff check --fix src/ tests/
```

### Type Checking
```bash
# Run type checking with pyright
uv run pyright src/markitdown_cosense
```

### Building
```bash
# Build package
uv build

# Build specific formats
uv build --wheel
uv build --sdist
```

## Architecture

The project follows a **unified single-file architecture** for simplicity:

1. **Main File** (`src/markitdown_cosense/_plugin.py`): Contains all functionality:
   - `MarkdownConverter`: Main converter implementing markitdown's `DocumentConverter`
   - `PatternProcessor`: Handles regex-based pattern conversions
   - Processing functions: `convert_code_blocks`, `convert_lists`, `convert_tables`
   - Utility functions and error handling

2. **Export Module** (`src/markitdown_cosense/__init__.py`):
   - Simple exports for public API
   - Plugin interface registration

3. **Unified Tests** (`tests/test_plugin.py`):
   - All tests consolidated into a single comprehensive file
   - Tests for patterns, code blocks, lists, tables, and integration

## Conversion Pipeline

The conversion follows a **7-step pipeline**:

1. Protect existing markdown code blocks
2. Convert Scrapbox code blocks to markdown format  
3. Protect newly created code blocks
4. Convert tables and lists (order matters)
5. Apply pattern-based conversions (formatting, links, etc.)
6. Restore all protected code blocks
7. Check for unsupported notations and log warnings

## Scrapbox to Markdown Mappings

Key conversions:
- `[* heading]` → `# heading`
- `[** heading]` → `## heading`
- `[/ italic]` → `*italic*`
- `[- strikethrough]` → `~~strikethrough~~`
- `[** bold **]` → `**bold**`
- `[$ math $]` → `$math$`
- `[text https://url]` → `[text](https://url)`
- `[img https://image.jpg]` → `![img](https://image.jpg)`
- Code blocks: `code:lang` → ````markdown```lang````
- Tables: `table:name` → Markdown tables with `## name` header
- Lists: Indented lines → Markdown nested lists

## Development Guidelines

1. **Single File Approach**: All source code in `_plugin.py` for simplicity
2. **Function-Based**: Use functions instead of classes where possible
3. **Type Hints**: Maintain comprehensive type annotations
4. **Error Handling**: Use custom exceptions with clear error messages
5. **No Inline Comments**: Keep code self-documenting
6. **Early Returns**: Use early returns to reduce nesting

## Configuration

All tool configurations are in `pyproject.toml`:

- **uv**: Dependencies in `[tool.uv]`
- **ruff**: Linting/formatting rules in `[tool.ruff]`
- **pyright**: Type checking config in `[tool.pyright]`
- **pytest**: Test configuration in `[tool.pytest.ini_options]`

## CI/CD

GitHub Actions workflow (`check.yml`) runs:
- **lint**: Format and style checking (no dependencies needed)
- **test**: Multi-Python version testing (3.10, 3.11, 3.12)
- **typecheck**: Pyright static analysis

## Verification Commands

### Run All Tests
```bash
uv run pytest
```

### Test Plugin Integration
```bash
# Convert test file using the plugin
uv run markitdown --use-plugins tests/test_scrapbox_notation.txt

# Save output to file
uv run markitdown --use-plugins tests/test_scrapbox_notation.txt > output.md
```

### Run CI Checks Locally
```bash
# Same as CI lint job
uv run --no-project ruff format --check src/ tests/
uv run --no-project ruff check src/ tests/

# Same as CI test job  
uv run pytest

# Same as CI typecheck job
uv run pyright src/markitdown_cosense
```

## Common Tasks

### Adding New Conversion Patterns
1. Add pattern to `PatternProcessor._create_conversion_steps()`
2. Test with examples in `tests/test_plugin.py`
3. Update `test_scrapbox_notation.txt` if needed

### Debugging Conversions
1. Use `test_scrapbox_notation.txt` for comprehensive testing
2. Check conversion pipeline step by step in `_convert_content()`
3. Enable verbose pytest output: `uv run pytest -v -s`

### Performance Optimization
- Pattern compilation is cached globally
- Protected code blocks prevent recursive processing
- Early returns reduce unnecessary processing