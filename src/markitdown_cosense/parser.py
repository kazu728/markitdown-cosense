from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

HEADING_START_PATTERN = re.compile(r"^\[(\*{1,5})\s+(.*?)\]")
CODE_DIRECTIVE = "code:"
TABLE_DIRECTIVE = "table:"
FENCE = "```"
WHITESPACE_CHARS = (" ", "\t", "　")


@dataclass
class Block:
    pass


@dataclass
class Document:
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Heading(Block):
    level: int
    text: str


@dataclass
class Paragraph(Block):
    text: str


@dataclass
class BlankLine(Block):
    pass


@dataclass
class CodeBlock(Block):
    language: str
    lines: list[str] = field(default_factory=list)
    indent: str = ""


@dataclass
class MathBlock(Block):
    lines: list[str] = field(default_factory=list)
    indent: str = ""


@dataclass
class ListItem:
    text: str
    children: list[ListItem] = field(default_factory=list)


@dataclass
class BulletList(Block):
    items: list[ListItem] = field(default_factory=list)


@dataclass
class Table(Block):
    title: str | None
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass(frozen=True)
class Token:
    raw: str
    indent: int

    @property
    def stripped(self) -> str:
        return self.raw[self.indent :]

    @property
    def content(self) -> str:
        return self.raw.strip()

    def is_blank(self) -> bool:
        return not self.content


@dataclass(frozen=True)
class BlankToken(Token):
    pass


@dataclass(frozen=True)
class HeadingToken(Token):
    level: int
    text: str


@dataclass(frozen=True)
class FenceToken(Token):
    language: str


@dataclass(frozen=True)
class CodeDirectiveToken(Token):
    descriptor: str


@dataclass(frozen=True)
class TableDirectiveToken(Token):
    title: str | None


@dataclass(frozen=True)
class TextToken(Token):
    pass


class CosenseParser:
    def parse(self, text: str) -> Document:
        tokens = self._tokenize(text)
        blocks: list[Block] = []
        paragraph_buffer: list[str] = []
        index = 0

        def flush_paragraph() -> None:
            if paragraph_buffer:
                blocks.append(Paragraph("\n".join(paragraph_buffer)))
                paragraph_buffer.clear()

        while index < len(tokens):
            token = tokens[index]

            match token:
                case BlankToken():
                    flush_paragraph()
                    blocks.append(BlankLine())
                    index += 1
                case HeadingToken(level=level, text=text):
                    flush_paragraph()
                    blocks.append(Heading(level=level, text=text))
                    index += 1
                case FenceToken():
                    flush_paragraph()
                    block, index = self._parse_fenced_code(tokens, index)
                    blocks.append(block)
                case CodeDirectiveToken():
                    flush_paragraph()
                    block, index = self._parse_code_block(tokens, index)
                    blocks.append(block)
                case TableDirectiveToken(indent=0):
                    flush_paragraph()
                    block, index = self._parse_table(tokens, index)
                    if block:
                        blocks.append(block)
                case TextToken() if token.indent > 0:
                    flush_paragraph()
                    block, index = self._parse_list(tokens, index)
                    blocks.append(block)
                case TextToken():
                    paragraph_buffer.append(token.raw)
                    index += 1
                case _:
                    index += 1

        flush_paragraph()
        return Document(self._collapse_trailing_blanks(blocks))

    def _tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        for raw_line in text.splitlines():
            indent = self._leading_whitespace_count(raw_line)
            stripped = raw_line[indent:]

            if not stripped:
                tokens.append(BlankToken(raw_line, indent))
                continue

            heading = HEADING_START_PATTERN.match(raw_line)
            if heading:
                stars, heading_text = heading.groups()
                trailing = raw_line[heading.end() :]
                combined = f"{heading_text.strip()}{trailing}".strip()
                tokens.append(
                    HeadingToken(raw_line, indent, level=len(stars), text=combined)
                )
                continue

            if stripped.startswith(FENCE):
                language = stripped[len(FENCE) :].strip()
                tokens.append(FenceToken(raw_line, indent, language=language))
                continue

            if stripped.startswith(CODE_DIRECTIVE):
                descriptor = stripped[len(CODE_DIRECTIVE) :].strip()
                tokens.append(
                    CodeDirectiveToken(raw_line, indent, descriptor=descriptor)
                )
                continue

            if stripped.startswith(TABLE_DIRECTIVE) and indent == 0:
                title = stripped[len(TABLE_DIRECTIVE) :].strip() or None
                tokens.append(TableDirectiveToken(raw_line, indent, title=title))
                continue

            tokens.append(TextToken(raw_line, indent))

        return tokens

    def _parse_fenced_code(
        self, tokens: Sequence[Token], start_index: int
    ) -> tuple[CodeBlock, int]:
        start_token = tokens[start_index]
        assert isinstance(start_token, FenceToken)
        collected: list[str] = []
        index = start_index + 1

        while index < len(tokens):
            current = tokens[index]
            if isinstance(current, FenceToken) and current.indent == start_token.indent:
                index += 1
                break
            if current.raw.startswith(start_token.raw[: start_token.indent]):
                collected.append(current.raw[start_token.indent :])
            else:
                collected.append(current.raw)
            index += 1

        return (
            CodeBlock(
                language=start_token.language,
                lines=collected,
                indent=start_token.raw[: start_token.indent],
            ),
            index,
        )

    def _parse_code_block(
        self, tokens: Sequence[Token], start_index: int
    ) -> tuple[CodeBlock | MathBlock, int]:
        directive_token = tokens[start_index]
        assert isinstance(directive_token, CodeDirectiveToken)
        collected: list[str] = []
        index = start_index + 1

        while index < len(tokens):
            current = tokens[index]
            if isinstance(current, CodeDirectiveToken) or isinstance(
                current, TableDirectiveToken
            ):
                break

            if current.is_blank():
                next_index = index + 1
                while next_index < len(tokens) and tokens[next_index].is_blank():
                    next_index += 1
                if next_index >= len(tokens):
                    collected.extend(token.raw for token in tokens[index:next_index])
                    index = next_index
                    break

                next_token = tokens[next_index]
                if isinstance(next_token, CodeDirectiveToken) or isinstance(
                    next_token, TableDirectiveToken
                ):
                    break
                if next_token.indent <= directive_token.indent:
                    break

                collected.append(current.raw)
                index += 1
                continue

            collected.append(current.raw)
            index += 1

        trimmed_lines = self._normalize_code_lines(collected)

        if directive_token.descriptor.lower() == "tex":
            return (
                MathBlock(
                    lines=trimmed_lines,
                    indent=directive_token.raw[: directive_token.indent],
                ),
                index,
            )

        language = self._infer_language(directive_token.descriptor)
        return (
            CodeBlock(
                language=language,
                lines=trimmed_lines,
                indent=directive_token.raw[: directive_token.indent],
            ),
            index,
        )

    def _parse_table(
        self, tokens: Sequence[Token], start_index: int
    ) -> tuple[Table | None, int]:
        directive_token = tokens[start_index]
        assert isinstance(directive_token, TableDirectiveToken)
        rows: list[list[str]] = []
        index = start_index + 1

        while index < len(tokens):
            current = tokens[index]
            if current.indent == 0 or current.is_blank():
                break
            rows.append(current.content.split())
            index += 1

        if not rows:
            return None, index

        header = rows[0]
        data = rows[1:]
        return (Table(title=directive_token.title, header=header, rows=data), index)

    def _parse_list(
        self, tokens: Sequence[Token], start_index: int
    ) -> tuple[BulletList, int]:
        items: list[tuple[int, str]] = []
        index = start_index

        while index < len(tokens):
            current = tokens[index]
            if current.indent == 0 or current.is_blank():
                break
            depth = max(0, current.indent - 1)
            text = current.stripped.strip()
            items.append((depth, text))
            index += 1

        return BulletList(items=self._build_list_tree(items)), index

    def _build_list_tree(self, items: Sequence[tuple[int, str]]) -> list[ListItem]:
        stack: list[tuple[int, list[ListItem]]] = [(-1, [])]

        for depth, text in items:
            while len(stack) > 1 and depth <= stack[-1][0]:
                stack.pop()

            parent_children = stack[-1][1]
            new_item = ListItem(text=text)
            parent_children.append(new_item)
            stack.append((depth, new_item.children))

        return stack[0][1]

    def _normalize_code_lines(self, lines: Sequence[str]) -> list[str]:
        meaningful = [line for line in lines if line.strip()]
        if not meaningful:
            return []
        indent_width = min(self._leading_whitespace_count(line) for line in meaningful)
        normalized = [line[indent_width:] if line.strip() else "" for line in lines]
        while normalized and normalized[-1] == "":
            normalized.pop()
        return normalized

    def _leading_whitespace_count(self, line: str) -> int:
        count = 0
        for char in line:
            if char in (" ", "\t", "　"):
                count += 1
            else:
                break
        return count

    def _infer_language(self, descriptor: str) -> str:
        if not descriptor:
            return ""
        if "." in descriptor:
            return descriptor.rsplit(".", 1)[1]
        return descriptor

    def _collapse_trailing_blanks(self, blocks: Iterable[Block]) -> list[Block]:
        result = list(blocks)
        while result and isinstance(result[-1], BlankLine):
            result.pop()
        return result
