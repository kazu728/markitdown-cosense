"""Data-driven tests for Cosense → Markdown conversion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from markitdown_cosense._plugin import IMAGE_EXTENSIONS, CosenseEngine

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "cosense_decision_table.json"
)


class FixtureCase(TypedDict):
    id: str
    source: list[str]
    expected: list[str]


with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
    DECISION_TABLE = cast(dict[str, list[FixtureCase]], json.load(fixture_file))


DECISION_CASES = [
    pytest.param(case, id=f"{category}:{case['id']}")
    for category, cases in DECISION_TABLE.items()
    for case in cases
]


def convert_text(text: str) -> str:
    return CosenseEngine(image_extensions=IMAGE_EXTENSIONS).convert(text)


@pytest.mark.parametrize("case", DECISION_CASES)
def test_cosense_decision_table_cases(case: FixtureCase) -> None:
    source = "\n".join(case["source"])
    expected = "\n".join(case["expected"])

    assert convert_text(source) == expected
