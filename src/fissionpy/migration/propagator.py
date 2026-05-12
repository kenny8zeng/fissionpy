"""Project-level import propagation using LibCST CSTTransformer."""

from __future__ import annotations

import pathlib

from fissionpy.extraction.imports import update_imports_in_source
from fissionpy.analysis.database import (
    get_file_by_path,
    get_files_importing_symbol,
)
from fissionpy.common.paths import normalize_path


def propagate_import_updates(
    target_files: list[str],
    replacements: dict[str, str],
    moved_symbols: set[str],
) -> dict[str, str]:
    """Apply import rewrites to each target file and return per-file status.

    For each path in *target_files*, read the source, apply
    :func:`~fissionpy.extraction.imports.update_imports_in_source`, write back
    if changed, and record ``"updated"`` or ``"unchanged"``.
    """
    results: dict[str, str] = {}
    for file_path in target_files:
        normalized = normalize_path(file_path)
        source = pathlib.Path(normalized).read_text(encoding="utf-8")
        updated = update_imports_in_source(source, replacements, moved_symbols)
        if updated != source:
            pathlib.Path(normalized).write_text(updated, encoding="utf-8")
            results[file_path] = "updated"
        else:
            results[file_path] = "unchanged"
    return results


def compute_affected_files(conn, plan: dict) -> list[str]:
    """Return deduplicated list of file paths that import symbols being moved.

    Uses :func:`~fissionpy.analysis.database.get_files_importing_symbol` for
    every symbol listed in the plan's ``modules`` section.
    """
    target_file = plan.get("target_file", "")
    project_root = plan.get("project_root", "")

    normalized_target = normalize_path(target_file)
    abs_target = normalized_target
    if project_root and not pathlib.Path(normalized_target).is_absolute():
        abs_target = str(pathlib.Path(project_root) / normalized_target)

    file_row = get_file_by_path(conn, abs_target)
    if file_row is None:
        file_row = get_file_by_path(conn, normalized_target)
    if file_row is None:
        file_row = get_file_by_path(conn, target_file)
    if file_row is None:
        return []

    target_file_id: int = file_row["id"]

    affected: set[str] = set()
    for module in plan.get("modules", []):
        for symbol_name in module.get("symbols", []):
            rows = get_files_importing_symbol(conn, symbol_name, target_file_id)
            for row in rows:
                path = row.get("source_file_path", "")
                if path and path != abs_target:
                    affected.add(path)

    return sorted(affected)


def record_import_updates(
    conn,
    updates: dict[str, str],
    replacements: dict[str, str],
    moved_symbols: set[str],
) -> None:
    """Insert rows into the import_updates table for every file that was updated.

    Each combination of updated file, replacement pair, and moved symbol
    produces one row with ``status='applied'``.
    """
    import time

    for file_path, status in updates.items():
        if status != "updated":
            continue
        file_row = get_file_by_path(conn, file_path)
        if file_row is None:
            continue
        target_file_id: int = file_row["id"]
        for old_module_path, new_module_path in replacements.items():
            for symbol_name in moved_symbols:
                conn.execute(
                    """INSERT INTO import_updates
                       (target_file_id, old_module_path, new_module_path,
                        symbol_name, status, applied_at)
                       VALUES (?, ?, ?, ?, 'applied', ?)""",
                    (target_file_id, old_module_path, new_module_path,
                     symbol_name, time.time()),
                )
    conn.commit()
