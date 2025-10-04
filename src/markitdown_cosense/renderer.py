from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .parser import (
    BlankLine,
    Block,
    BulletList,
    CodeBlock,
    CosenseParser,
    Document,
    Heading,
    ListItem,
    MathBlock,
    Paragraph,
    Table,
)


@dataclass
class MarkdownRenderer:
    inline_processor: InlineProcessor

    def render(self, document: Document) -> str:
        lines: list[str] = []
        for block in document.blocks:
            lines.extend(self._render_block(block))
        return "\n".join(lines).strip("\n")

    def _render_block(self, block: Block) -> list[str]:
        match block:
            case Heading(level=level, text=text):
                rendered = self.inline_processor.apply(text)
                return [f"{'#' * level} {rendered}".rstrip()]

            case Paragraph(text=text):
                rendered = self.inline_processor.apply(text)
                return rendered.splitlines() or [rendered]

            case BlankLine():
                return [""]

            case CodeBlock(language=language, lines=lines, indent=indent):
                fence = f"```{language}" if language else "```"
                body = [f"{indent}{fence}"]
                body.extend(f"{indent}{line}" for line in lines)
                body.append(f"{indent}```")
                return body

            case MathBlock(lines=lines, indent=indent):
                return [self._render_math_line(line, indent) for line in lines]

            case BulletList(items=items):
                return self._render_list_items(items, depth=0)

            case Table(title=title, header=header, rows=rows):
                return self._render_table(title, header, rows)

            case _:  # pragma: no cover - defensive
                return []

    def _render_list_items(self, items: Sequence[ListItem], depth: int) -> list[str]:
        lines: list[str] = []
        indent = "  " * depth
        for item in items:
            text = self.inline_processor.apply(item.text)
            lines.append(f"{indent}- {text}".rstrip())
            if item.children:
                lines.extend(self._render_list_items(item.children, depth + 1))
        return lines

    def _render_table(
        self, title: str | None, header: Sequence[str], rows: Sequence[Sequence[str]]
    ) -> list[str]:
        lines: list[str] = []
        if title:
            lines.append(f"## {self.inline_processor.apply(title)}")
            lines.append("")

        header_cells = [self.inline_processor.apply(cell) for cell in header]
        lines.append("| " + " | ".join(header_cells) + " |")
        lines.append("|" + "---|" * len(header_cells))

        for row in rows:
            cells = [self.inline_processor.apply(cell) for cell in row]
            missing = len(header_cells) - len(cells)
            if missing > 0:
                cells.extend([""] * missing)
            lines.append("| " + " | ".join(cells[: len(header_cells)]) + " |")

        return lines

    def _render_math_line(self, line: str, indent: str) -> str:
        stripped = line.strip()
        if not stripped:
            return ""

        math_chars = set("=+-*/^")
        math_indicators = ("E(", "V(", "Cov(", "σ", "μ", "√", "Φ", "\\", "^2", "_")
        excluded_prefixes = ("![", "http", "<http", "->")

        has_math = any(char in stripped for char in math_chars) or any(
            indicator in stripped for indicator in math_indicators
        )

        contains_japanese = any(
            "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9faf"
            for char in stripped
        )

        if (
            not has_math
            or stripped.startswith(excluded_prefixes)
            or stripped == "code:tex"
            or contains_japanese
        ):
            return f"{indent}{stripped}"

        return f"{indent}${stripped}$"


class CosenseEngine:
    def __init__(self, image_extensions: Sequence[str]) -> None:
        self._parser = CosenseParser()
        rules = build_inline_rules(tuple(image_extensions))
        self._inline = InlineProcessor(rules)
        self._renderer = MarkdownRenderer(self._inline)

    def convert(self, text: str) -> str:
        document = self._parser.parse(text)
        return self._renderer.render(document)


AUTO_LINK_PATTERN = re.compile(
    r'(?<![<(])(https?://[^\s<>"\']+(?:\([^\s<>"\']*\)|[^\s<>"\']*)*)'
)


@dataclass(frozen=True)
class InlineRuleSpec:
    pattern: str
    replacement: str
    needs_image_extensions: bool = False


INLINE_RULE_SPECS: tuple[InlineRuleSpec, ...] = (
    InlineRuleSpec(
        pattern=(
            r"\[(?!\*|img\s|/\s|-\s|\$|https?://|YouTube\s|Twitter\s|\w+\s+https?://)"
            r"([^\[\]/\-\*\s][^\[\]/\-\*\]]*?)(?!\s+https?://)\]"
        ),
        replacement=r"<!-- tag: \1 -->",
    ),
    InlineRuleSpec(pattern=r"\[\*/\s*(.*?)\]", replacement=r"***\1***"),
    InlineRuleSpec(pattern=r"\[\*-\s*(.*?)\]", replacement=r"**~~\1~~**"),
    InlineRuleSpec(pattern=r"\[/-\s*(.*?)\]", replacement=r"*~~\1~~*"),
    InlineRuleSpec(pattern=r"\[\*\*\*\s*(.*?)\s*\*\*\*\]", replacement=r"**\1**"),
    InlineRuleSpec(pattern=r"\[\*\*\s*(.*?)\s*\*\*\]", replacement=r"**\1**"),
    InlineRuleSpec(pattern=r"\[/\s*(.*?)\]", replacement=r"*\1*"),
    InlineRuleSpec(pattern=r"\[-\s*(.*?)\]", replacement=r"~~\1~~"),
    InlineRuleSpec(pattern=r"\[img\s+(https?://[^\s\]]+)\]", replacement=r"![img](\1)"),
    InlineRuleSpec(
        pattern=r"\[(https?://[^\s\]]+\.(?:{image_exts}))\]",
        replacement=r"![](\1)",
        needs_image_extensions=True,
    ),
    InlineRuleSpec(
        pattern=(
            r"\[YouTube\s+(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|"
            r"https?://youtu\.be/[\w-]+)\]"
        ),
        replacement=r"[YouTube Video](\1)",
    ),
    InlineRuleSpec(
        pattern=(
            r"\[Twitter\s+(https?://(?:www\.)?twitter\.com/\w+/status/\d+|"
            r"https?://x\.com/\w+/status/\d+)\]"
        ),
        replacement=r"[Twitter Post](\1)",
    ),
    InlineRuleSpec(
        pattern=r"\[([^/\-\*\]]+?)\s+(https?://[^\s\]]+)\]",
        replacement=r"[\1](\2)",
    ),
    InlineRuleSpec(
        pattern=r"\[(https?://[^\s\]]+)\s+([^/\-\*\]]+?)\]",
        replacement=r"[\2](\1)",
    ),
)


@dataclass(frozen=True)
class InlineRule:
    pattern: re.Pattern[str]
    replacement: str


class InlineProcessor:
    def __init__(self, rules: Sequence[tuple[str, str]]) -> None:
        self._rules: list[InlineRule] = [
            InlineRule(
                pattern=re.compile(pattern, re.MULTILINE), replacement=replacement
            )
            for pattern, replacement in rules
        ]

    def apply(self, text: str) -> str:
        for rule in self._rules:
            text = rule.pattern.sub(rule.replacement, text)
        return AUTO_LINK_PATTERN.sub(r"<\1>", text)


def build_inline_rules(image_extensions: Sequence[str]) -> list[tuple[str, str]]:
    image_pattern = "|".join(image_extensions)
    rules: list[tuple[str, str]] = []
    for spec in INLINE_RULE_SPECS:
        pattern = (
            spec.pattern.format(image_exts=image_pattern)
            if spec.needs_image_extensions
            else spec.pattern
        )
        rules.append((pattern, spec.replacement))
    return rules
