"""LibCST lossless code extraction: extract symbols into new module files."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import libcst as cst


@dataclasses.dataclass
class ExtractionResult:
    """Result of extracting symbols into a new module file."""

    module_name: str
    symbols: list[str]
    output_path: str
    success: bool
    errors: list[str]


def _statement_defines_symbol(
    stmt: cst.BaseStatement,
    symbol_names: set[str],
) -> bool:
    """Return True if a top-level statement defines a symbol in symbol_names."""
    if isinstance(stmt, cst.FunctionDef):
        return stmt.name.value in symbol_names
    if isinstance(stmt, cst.ClassDef):
        return stmt.name.value in symbol_names
    if isinstance(stmt, cst.SimpleStatementLine):
        for node in stmt.body:
            if isinstance(node, cst.Assign) and node.targets:
                for target in node.targets:
                    if (
                        isinstance(target.target, cst.Name)
                        and target.target.value in symbol_names
                    ):
                        return True
            if isinstance(node, cst.AnnAssign) and node.target:
                if (
                    isinstance(node.target, cst.Name)
                    and node.target.value in symbol_names
                ):
                    return True
    return False


def _build_extracted_module(
    matched: list[cst.BaseStatement],
) -> cst.Module:
    """Build a new Module from matched statements with blank-line separation."""
    body: list[cst.BaseStatement] = []
    for i, stmt in enumerate(matched):
        if i > 0:
            new_leading: list[cst.EmptyLine] = [
                cst.EmptyLine(
                    indent=False,
                    whitespace=cst.SimpleWhitespace(""),
                    comment=None,
                )
            ]
            preserved = list(stmt.leading_lines)
            stmt = stmt.with_changes(leading_lines=new_leading + preserved)
        body.append(stmt)

    return cst.Module(body=body)


def extract_symbols(source_code: str, symbol_names: list[str]) -> str:
    """Extract top-level symbol definitions from source_code, preserving formatting.

    Parses with LibCST so the extracted text is character-for-character identical
    to the original source for every matched statement.
    """
    module = cst.parse_module(source_code)
    name_set = set(symbol_names)
    matched: list[cst.BaseStatement] = []

    for stmt in module.body:
        if _statement_defines_symbol(stmt, name_set):
            matched.append(stmt)

    if not matched:
        return ""

    new_module = _build_extracted_module(matched)
    return new_module.code


def extract_module(
    target_file: str,
    module_name: str,
    symbol_names: list[str],
    project_root: str,
    required_imports: list[str] | None = None,
) -> ExtractionResult:
    """Extract symbols from target_file into a new module file.

    The output path is ``<target_file_dir>/<module_name>.py`` where
    *module_name* may contain ``/`` for sub-directory modules.
    """
    errors: list[str] = []

    try:
        source_code = Path(target_file).read_text(encoding="utf-8")
    except OSError as exc:
        return ExtractionResult(
            module_name=module_name,
            symbols=symbol_names,
            output_path="",
            success=False,
            errors=[str(exc)],
        )

    original_module = cst.parse_module(source_code)

    extracted_code = extract_symbols(source_code, symbol_names)

    if not extracted_code and symbol_names:
        errors.append("未找到任何目标符号")
        return ExtractionResult(
            module_name=module_name,
            symbols=symbol_names,
            output_path="",
            success=False,
            errors=errors,
        )

    output_path = Path(target_file).parent / Path(module_name).with_suffix(".py")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(str(exc))
        return ExtractionResult(
            module_name=module_name,
            symbols=symbol_names,
            output_path=str(output_path),
            success=False,
            errors=errors,
        )

    parts: list[str] = []
    if required_imports:
        parts.append("\n".join(required_imports))
        parts.append("")
    parts.append(extracted_code)
    new_content = "\n".join(parts)
    if not new_content.endswith("\n"):
        new_content += "\n"

    try:
        output_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        errors.append(str(exc))
        return ExtractionResult(
            module_name=module_name,
            symbols=symbol_names,
            output_path=str(output_path),
            success=False,
            errors=errors,
        )

    new_module_tree = cst.parse_module(new_content)
    for sym_name in symbol_names:
        for stmt in new_module_tree.body:
            if not _statement_defines_symbol(stmt, {sym_name}):
                continue
            for orig_stmt in original_module.body:
                if not _statement_defines_symbol(orig_stmt, {sym_name}):
                    continue
                new_node = stmt.with_changes(leading_lines=[])
                orig_node = orig_stmt.with_changes(leading_lines=[])
                if new_node.deep_equals(orig_node):
                    break
                errors.append(f"符号 '{sym_name}' 提取后源码不一致")
                break
            break

    return ExtractionResult(
        module_name=module_name,
        symbols=symbol_names,
        output_path=str(output_path),
        success=len(errors) == 0,
        errors=errors,
    )


def remove_symbols_from_source(
    source_code: str,
    symbol_names: list[str],
) -> str:
    """Return source_code with top-level definitions of symbol_names removed."""
    module = cst.parse_module(source_code)
    name_set = set(symbol_names)

    filtered: list[cst.BaseStatement] = [
        stmt for stmt in module.body if not _statement_defines_symbol(stmt, name_set)
    ]

    new_module = module.with_changes(body=filtered)
    return new_module.code
