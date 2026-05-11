"""LibCST-based top-level symbol collector for fissionpy."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import libcst as cst
import libcst.metadata as cst_meta


@dataclasses.dataclass
class TopLevelSymbol:
    """A top-level symbol extracted from a Python source file."""

    name: str
    kind: str
    line_start: int
    line_end: int
    source_text: str


def _extract_assignment_name(stmt: cst.SimpleStatementLine) -> str | None:
    """Extract the target name from the first Assign or AnnAssign in a SimpleStatementLine."""
    for node in stmt.body:
        if isinstance(node, cst.Assign):
            for target in node.targets:
                if isinstance(target.target, cst.Name):
                    return target.target.value
        elif isinstance(node, cst.AnnAssign):
            if isinstance(node.target, cst.Name):
                return node.target.value
    return None


def _statement_source(stmt: cst.BaseStatement) -> str:
    """Reconstruct source text from a single top-level CST statement."""
    return cst.parse_module("").with_changes(body=[stmt]).code


def _count_lines(text: str) -> int:
    """Count the number of lines in text, treating trailing newline as part of last line."""
    if not text:
        return 1
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def parse_file(file_path: str) -> list[TopLevelSymbol]:
    """Parse a Python file and return its top-level symbols."""
    source = Path(file_path).read_text(encoding="utf-8")
    module = cst.parse_module(source)
    wrapper = cst_meta.MetadataWrapper(module)

    positions: dict[cst.CSTNode, cst_meta.CodeRange] = {}
    try:
        positions = wrapper.resolve(cst_meta.PositionProvider)
    except Exception:
        positions = {}

    symbols: list[TopLevelSymbol] = []

    for stmt in module.body:
        name: str | None = None
        kind: str | None = None

        if isinstance(stmt, cst.FunctionDef):
            name = stmt.name.value
            kind = "function"
        elif isinstance(stmt, cst.ClassDef):
            name = stmt.name.value
            kind = "class"
        elif isinstance(stmt, cst.SimpleStatementLine):
            name = _extract_assignment_name(stmt)
            if name is not None:
                kind = "assignment"

        if name is None or kind is None:
            continue

        source_text = _statement_source(stmt)

        pos = positions.get(stmt)
        if pos is not None:
            line_start = pos.start.line
            line_end = pos.end.line
        else:
            line_start = 1
            line_end = _count_lines(source_text)
            for prev in symbols:
                line_start = max(line_start, prev.line_end + 1)
            line_end = line_start + _count_lines(source_text) - 1

        symbols.append(
            TopLevelSymbol(
                name=name,
                kind=kind,
                line_start=line_start,
                line_end=line_end,
                source_text=source_text,
            )
        )

    return symbols
