"""Backup, reorganization, and re-export for migrated target files."""

from __future__ import annotations

import pathlib
import shutil

import libcst as cst

from fissionpy.common.paths import (
    file_path_to_module_path,
    module_path_to_python_import,
)
from fissionpy.extraction.extractor import remove_symbols_from_source
from fissionpy.extraction.imports import _cst_dotted_name


def backup_file(file_path: str) -> str:
    backup_path = file_path + ".bak"
    shutil.copy2(file_path, backup_path)
    return backup_path


def _compute_new_module_path(target_module_path: str, module_name: str) -> str:
    if "/" in target_module_path:
        parent_path = "/".join(target_module_path.split("/")[:-1])
        return f"{parent_path}/{module_name}"
    return str(module_name)


def reorganize_target_file(
    target_file: str,
    plan: dict,
    project_root: str,
    no_reexport: bool = False,
) -> None:
    source_code = pathlib.Path(target_file).read_text(encoding="utf-8")

    all_symbol_names: list[str] = []
    for module in plan.get("modules", []):
        all_symbol_names.extend(module.get("symbols", []))

    remaining_code = remove_symbols_from_source(source_code, all_symbol_names)

    if not no_reexport:
        target_module_path = file_path_to_module_path(target_file, project_root)
        reexport_lines: list[str] = []
        for module in plan.get("modules", []):
            module_name = module.get("name", "")
            symbols = module.get("symbols", [])
            if not symbols:
                continue
            new_module_path = _compute_new_module_path(target_module_path, module_name)
            python_import = module_path_to_python_import(new_module_path)
            symbol_str = ", ".join(symbols)
            reexport_lines.append(
                f"from {python_import} import {symbol_str}"
            )

        if reexport_lines:
            reexport_block = "\n".join(reexport_lines)
            module = cst.parse_module(remaining_code)
            future_stmts: list[cst.BaseStatement] = []
            other_stmts: list[cst.BaseStatement] = []
            for stmt in module.body:
                if isinstance(stmt, cst.SimpleStatementLine):
                    has_future = False
                    for node in stmt.body:
                        if isinstance(node, cst.ImportFrom) and node.module is not None:
                            if _cst_dotted_name(node.module) == "__future__":
                                has_future = True
                    if has_future:
                        future_stmts.append(stmt)
                        continue
                other_stmts.append(stmt)

            reexport_module = cst.parse_module(reexport_block + "\n")
            combined = cst.Module(body=[*future_stmts, *reexport_module.body, *other_stmts])
            remaining_code = combined.code

    pathlib.Path(target_file).write_text(remaining_code, encoding="utf-8")


def ensure_init_files(target_file: str, plan: dict) -> list[str]:
    created: list[str] = []
    target_dir = pathlib.Path(target_file).parent

    for module in plan.get("modules", []):
        module_name = module.get("name", "")
        if "/" not in module_name:
            continue
        parts = module_name.split("/")
        current = target_dir
        for part in parts[:-1]:
            current = current / part
            init_file = current / "__init__.py"
            if not init_file.exists():
                current.mkdir(parents=True, exist_ok=True)
                init_file.touch()
                created.append(str(init_file))

    target_init = target_dir / "__init__.py"
    if not target_init.exists():
        target_init.touch()
        created.append(str(target_init))

    return created


def restore_from_backup(file_path: str) -> bool:
    backup_path = file_path + ".bak"
    if not pathlib.Path(backup_path).exists():
        return False
    shutil.copy2(backup_path, file_path)
    pathlib.Path(backup_path).unlink()
    return True
