# CLAUDE.md

Guidelines for Claude Code when contributing to **markitdown-cosense**.

## Project Snapshot
- **Goal**: Convert Cosense notation into Markdown as a MarkItDown plugin
- **Languages & Tools**: Python 3.10+, uv, Ruff, Pyright, Pytest, MarkItDown
- **Repo Layout (core)**:
  - `src/markitdown_cosense/parser.py` — token-based Cosense parser → AST blocks
  - `src/markitdown_cosense/renderer.py` — block → Markdown renderer + inline rules + `CosenseEngine`
  - `src/markitdown_cosense/_plugin.py` — MarkItDown integration (`MarkdownConverter`, heuristics)
  - `tests/unit/…` — golden conversions powered by fixtures in `tests/fixtures/`
  - `tests/integration/…` — end-to-end MarkItDown behaviour & heuristics

## Development Workflow
```bash
# Install project + dev extras
uv sync

# Lint & auto-fix
uv run ruff check --fix
uv run ruff format

# Type check
uv run pyright

# Run tests
uv run pytest            # runs unit + integration suites
uv run pytest tests/unit
uv run pytest tests/integration
```

## Architectural Outline
1. **Tokenization (`CosenseParser`)**
   - `_tokenize` turns raw text into tokens (`HeadingToken`, `FenceToken`, etc.)
   - main loop pattern-matches tokens to build AST blocks; paragraph buffering is handled inline

2. **Rendering (`MarkdownRenderer`, `InlineProcessor`)**
   - `MarkdownRenderer.render()` pattern-matches block dataclasses and emits Markdown lines
   - Inline conversions are declared via `InlineRuleSpec`; renderer holds the `InlineProcessor`

3. **Plugin Layer (`MarkdownConverter`)**
   - `accepts()` peeks at the stream (4 KB) and looks for Cosense markers or headings
   - `.convert()` delegates to a shared `CosenseEngine`

4. **Testing Strategy**
   - Unit: decision-table fixtures ensure AST→Markdown stability (`tests/fixtures/cosense_decision_table.json`)
   - Integration: verifies conversion via MarkItDown, heuristics, inline behaviour, filesystem interaction

## Contribution Rules
- Prefer modern Python (`match` statements, dataclasses, type hints everywhere)
- Keep parser/renderer pure and deterministic; avoid hidden state
- Inline rules belong with the renderer so Markdown-specific logic stays together
- Tests should mirror the unit/integration split; update fixtures when adjusting behaviour
- Run `ruff`, `pyright`, and `pytest` before finishing any task

## Useful Snippets
```python
# Parse + render manually
from markitdown_cosense.parser import CosenseParser
from markitdown_cosense.renderer import CosenseEngine, IMAGE_EXTENSIONS

engine = CosenseEngine(IMAGE_EXTENSIONS)
markdown = engine.convert("[* Heading]\n[tag]")
print(markdown)  # -> "# Heading\n<!-- tag: tag -->"
```

```bash
# Invoke plugin via MarkItDown CLI (requires markitdown extras)
uv run markitdown --use-plugins path/to/note.txt
```

Follow these guardrails and keep responses scoped, precise, and test-backed.
