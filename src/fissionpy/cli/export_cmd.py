"""fission export command implementation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from fissionpy.analysis.database import (
    get_all_dependencies,
    get_all_file_imports,
    get_all_files,
    get_all_symbols_across_project,
    get_connection,
    get_dependencies_by_file,
    get_file_by_path,
    get_file_imports_by_file,
    get_symbols_by_file,
)
from fissionpy.common.paths import normalize_path


def _find_file_record(conn, file_path: str) -> dict | None:
    """Resolve file record using normalize_path + fallback logic."""
    normalized = normalize_path(file_path)
    file_row = get_file_by_path(conn, normalized)
    if file_row is None:
        resolved = str(Path(normalized).resolve())
        file_row = get_file_by_path(conn, resolved)
    if file_row is None:
        file_row = get_file_by_path(conn, file_path)
    return file_row


def _build_file_entry(row: dict) -> dict:
    return {
        "id": row["id"],
        "path": row["path"],
        "hash": row["hash"],
        "status": row["status"],
        "symbol_count": row["symbol_count"],
    }


def _build_symbol_entry(row: dict, include_source: bool = False) -> dict:
    entry = {
        "id": row["id"],
        "file_id": row["file_id"],
        "name": row["name"],
        "kind": row["kind"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
    }
    if include_source:
        entry["source_text"] = row.get("source_text", "")
    return entry


def _build_dependency_entry(row: dict) -> dict:
    return {
        "source_id": row["source_id"],
        "target_id": row["target_id"],
        "dep_type": row["dep_type"],
        "cross_file": bool(row["cross_file"]),
    }


def _build_import_entry(row: dict) -> dict:
    imported_names = row["imported_names"]
    if isinstance(imported_names, str):
        try:
            imported_names = json.loads(imported_names)
        except (json.JSONDecodeError, TypeError):
            imported_names = []
    return {
        "file_id": row["source_file_id"],
        "import_type": row["import_type"],
        "module_path": row["module_path"],
        "imported_names": imported_names,
        "is_star_import": bool(row["is_star_import"]),
        "line_number": row["line_number"],
    }


def _export_full(conn, include_source: bool) -> dict:
    files = get_all_files(conn)
    symbols = get_all_symbols_across_project(conn)
    dependencies = get_all_dependencies(conn)
    file_imports = get_all_file_imports(conn)

    return {
        "files": [_build_file_entry(f) for f in files],
        "symbols": [_build_symbol_entry(s, include_source) for s in symbols],
        "dependencies": [_build_dependency_entry(d) for d in dependencies],
        "imports": [_build_import_entry(i) for i in file_imports],
    }


def _export_file(conn, file_path: str, include_source: bool) -> dict:
    file_row = _find_file_record(conn, file_path)
    if file_row is None:
        typer.echo(f"文件未索引: {file_path}", err=True)
        raise typer.Exit(code=1)

    file_id: int = file_row["id"]

    file_rows = get_all_files(conn)
    target_file = next((f for f in file_rows if f["id"] == file_id), None)
    if target_file is None:
        target_file = {
            "id": file_row["id"],
            "path": file_row["path"],
            "hash": file_row["hash"],
            "status": file_row["status"],
            "symbol_count": 0,
        }

    symbols = get_symbols_by_file(conn, file_id)
    target_file["symbol_count"] = len(symbols)

    symbol_ids = {s["id"] for s in symbols}
    all_deps = get_dependencies_by_file(conn, file_id)
    filtered_deps = [
        d for d in all_deps
        if d["source_id"] in symbol_ids or d["target_id"] in symbol_ids
    ]

    file_imports = get_file_imports_by_file(conn, file_id)

    return {
        "files": [_build_file_entry(target_file)],
        "symbols": [_build_symbol_entry(s, include_source) for s in symbols],
        "dependencies": [_build_dependency_entry(d) for d in filtered_deps],
        "imports": [_build_import_entry(i) for i in file_imports],
    }


def run_export(
    file: str | None,
    db: str,
    output: str,
    include_source: bool,
    verbose: bool,
) -> None:
    if not os.path.exists(db):
        typer.echo(f"数据库不存在: {db}", err=True)
        raise typer.Exit(code=1)

    conn = get_connection(db)
    try:
        existing_files = get_all_files(conn)
        if not existing_files:
            typer.echo("暂无已索引数据，请先运行 fission analyze", err=True)
            raise typer.Exit(code=1)

        if file is not None:
            data = _export_file(conn, file, include_source)
        else:
            data = _export_full(conn, include_source)
    finally:
        conn.close()

    output_dir = os.path.dirname(output)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError:
            typer.echo(f"无法写入: {output}", err=True)
            raise typer.Exit(code=1)

    try:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        typer.echo(f"无法写入: {output}", err=True)
        raise typer.Exit(code=1)

    n_files = len(data["files"])
    n_symbols = len(data["symbols"])
    n_deps = len(data["dependencies"])
    n_imports = len(data["imports"])

    typer.echo(f"导出完成: {n_files} 文件, {n_symbols} 符号, {n_deps} 依赖, {n_imports} import")
    typer.echo(f"写入: {output}")

    if verbose:
        if file is not None:
            typer.echo(f"筛选文件: {file}")
        if include_source:
            typer.echo("已包含符号源代码")
