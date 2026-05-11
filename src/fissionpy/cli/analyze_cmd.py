"""fission analyze <dir> command implementation."""

from __future__ import annotations

import json
import time

import typer

from fissionpy.analysis.database import (
    clear_file_data,
    compute_file_hash as db_compute_hash,
    get_all_symbols_across_project,
    get_connection,
    get_file_by_path,
    get_file_imports_by_file,
    get_or_create_file,
    get_symbols_by_file,
    init_db,
    mark_file_deleted,
    save_analysis,
)
from fissionpy.analysis.dependency import analyze_file_dependencies
from fissionpy.analysis.import_resolver import resolve_file_imports
from fissionpy.analysis.parser import parse_file
from fissionpy.analysis.scanner import compute_file_hash, scan_directory


def _symbol_to_dict(sym) -> dict:
    return {
        "name": sym.name,
        "kind": sym.kind,
        "line_start": sym.line_start,
        "line_end": sym.line_end,
        "source_text": sym.source_text,
    }


def _dependency_to_dict(dep) -> dict:
    return {
        "source_name": dep.source_name,
        "target_name": dep.target_name,
        "dep_type": dep.dep_type,
        "cross_file": 0,
    }


def _file_import_to_dict(fi) -> dict:
    return {
        "import_type": fi.import_type,
        "module_path": fi.module_path,
        "imported_names": json.dumps(fi.imported_names),
        "aliases": json.dumps(fi.aliases) if fi.aliases else None,
        "is_star_import": 1 if fi.is_star_import else 0,
        "line_number": fi.line_number,
    }


def _build_symbol_file_map(symbols: list[dict]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for sym in symbols:
        mapping[sym["name"]] = sym["file_id"]
    return mapping


def _resolve_cross_file_deps(conn, symbol_file_map: dict[str, int]) -> int:
    count = 0
    all_files = conn.execute(
        "SELECT id, path FROM files WHERE status = 'parsed'"
    ).fetchall()

    for file_row in all_files:
        source_file_id: int = file_row["id"]
        file_imports = get_file_imports_by_file(conn, source_file_id)
        source_symbols = get_symbols_by_file(conn, source_file_id)
        seen: set[tuple[int, int]] = set()

        for fi in file_imports:
            try:
                imported_names = json.loads(fi["imported_names"])
            except (json.JSONDecodeError, TypeError):
                continue
            for name in imported_names:
                defining_file_id = symbol_file_map.get(name)
                if defining_file_id is None or defining_file_id == source_file_id:
                    continue
                target_sym = conn.execute(
                    "SELECT id FROM symbols WHERE file_id = ? AND name = ? LIMIT 1",
                    (defining_file_id, name),
                ).fetchone()
                if target_sym is None:
                    continue
                target_id = target_sym["id"]
                for src_sym in source_symbols:
                    key = (src_sym["id"], target_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    conn.execute(
                        "INSERT INTO dependencies (source_id, target_id, dep_type, cross_file) "
                        "VALUES (?, ?, 'import', 1)",
                        (src_sym["id"], target_id),
                    )
                    count += 1

    conn.commit()
    return count


def _handle_deleted_files(conn, current_paths: set[str]) -> int:
    existing = conn.execute(
        "SELECT id, path FROM files WHERE status != 'deleted'"
    ).fetchall()
    deleted_count = 0
    for row in existing:
        if row["path"] not in current_paths:
            mark_file_deleted(conn, row["id"])
            deleted_count += 1
    return deleted_count


def run_analyze(
    directory: str,
    db: str,
    exclude: list[str],
    force: bool,
    verbose: bool,
) -> None:
    start_time = time.time()

    typer.echo(f"扫描目录: {directory}")
    scan_result = scan_directory(directory, exclude)

    if scan_result.errors:
        for err in scan_result.errors:
            typer.echo(f"扫描错误: {err}", err=True)

    typer.echo(f"发现 {len(scan_result.files)} 个 .py 文件")

    init_db(db)
    conn = get_connection(db)

    try:
        file_count = 0
        symbol_count = 0
        dep_count = 0
        error_count = 0
        current_paths: set[str] = set()

        for py_file in scan_result.files:
            file_str = str(py_file)
            current_paths.add(file_str)
            file_hash = compute_file_hash(file_str)

            if not force:
                existing = get_file_by_path(conn, file_str)
                if existing is not None and existing["hash"] == file_hash:
                    if verbose:
                        typer.echo(f"  跳过(未修改): {file_str}")
                    continue

            if verbose:
                typer.echo(f"  解析: {file_str}")

            try:
                symbols = parse_file(file_str)
                symbol_names = {s.name for s in symbols}
                deps = analyze_file_dependencies(file_str, symbol_names)
                file_imports = resolve_file_imports(file_str)

                sym_dicts = [_symbol_to_dict(s) for s in symbols]
                dep_dicts = [_dependency_to_dict(d) for d in deps]
                fi_dicts = [_file_import_to_dict(fi) for fi in file_imports]

                save_analysis(conn, file_str, file_hash, sym_dicts, dep_dicts, fi_dicts, force=force)

                file_id = get_file_by_path(conn, file_str)["id"]
                conn.execute("UPDATE files SET status = 'parsed' WHERE id = ?", (file_id,))
                conn.commit()

                file_count += 1
                symbol_count += len(symbols)
                dep_count += len(deps)

            except Exception as exc:
                file_hash_fallback = db_compute_hash(file_str)
                file_id = get_or_create_file(conn, file_str, file_hash_fallback)
                clear_file_data(conn, file_id)
                conn.execute("UPDATE files SET status = 'error' WHERE id = ?", (file_id,))
                conn.commit()
                error_count += 1
                typer.echo(f"  警告: 解析失败 {file_str}: {exc}", err=True)

        all_symbols = get_all_symbols_across_project(conn)
        symbol_file_map = _build_symbol_file_map(all_symbols)
        cross_file_count = _resolve_cross_file_deps(conn, symbol_file_map)

        deleted_count = _handle_deleted_files(conn, current_paths)

        elapsed = time.time() - start_time

        typer.echo(
            f"\n分析完成: "
            f"{file_count} 文件, "
            f"{symbol_count} 符号, "
            f"{dep_count} 依赖, "
            f"{cross_file_count} 跨文件依赖, "
            f"{error_count} 错误"
        )
        if deleted_count > 0:
            typer.echo(f"标记 {deleted_count} 个已删除文件")
        typer.echo(f"耗时: {elapsed:.2f}s")

    finally:
        conn.close()
