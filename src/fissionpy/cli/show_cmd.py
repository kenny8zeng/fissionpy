"""fission show command implementation."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from fissionpy.analysis.database import (
    get_connection,
    get_file_by_path,
    get_file_imports_by_file,
    get_symbols_by_file,
)
from fissionpy.common.paths import normalize_path


def _show_project_overview(conn, verbose: bool) -> None:
    """List all files with status and symbol count."""
    rows = conn.execute(
        "SELECT f.path, f.status, COUNT(s.id) AS sym_count "
        "FROM files f LEFT JOIN symbols s ON f.id = s.file_id "
        "WHERE f.status != 'deleted' "
        "GROUP BY f.id ORDER BY f.path"
    ).fetchall()

    if not rows:
        typer.echo("暂无已索引文件，请先运行 fission analyze")
        return

    for row in rows:
        status = row["status"]
        sym_count = row["sym_count"]
        tag = f"[{status}]" if status != "parsed" else ""
        suffix = "symbol" if sym_count == 1 else "symbols"
        typer.echo(f"{row['path']} {tag} {sym_count} {suffix}")

    if verbose:
        typer.echo(f"\n共 {len(rows)} 个文件")


def _show_file_symbols(conn, file_path: str, verbose: bool) -> None:
    """List top-level symbols and imports for a specific file."""
    normalized = normalize_path(file_path)
    file_row = get_file_by_path(conn, normalized)
    if file_row is None:
        resolved = str(Path(normalized).resolve())
        file_row = get_file_by_path(conn, resolved)
    if file_row is None:
        file_row = get_file_by_path(conn, file_path)
    if file_row is None:
        typer.echo(f"文件未索引: {file_path}", err=True)
        raise typer.Exit(code=1)

    file_id: int = file_row["id"]
    symbols = get_symbols_by_file(conn, file_id)

    if symbols:
        typer.echo(f"符号 ({file_path}):")
        for sym in symbols:
            typer.echo(f"  {sym['name']}  {sym['kind']}  {sym['line_start']}-{sym['line_end']}")
    else:
        typer.echo(f"文件 {file_path} 无顶层符号")

    file_imports = get_file_imports_by_file(conn, file_id)
    if file_imports:
        typer.echo(f"\n导入 ({file_path}):")
        for fi in file_imports:
            line = fi["line_number"]
            module = fi["module_path"]
            if fi["is_star_import"]:
                typer.echo(f"  from {module} import *  (line {line})")
            elif fi["import_type"] == "from_import":
                try:
                    names = json.loads(fi["imported_names"])
                except (json.JSONDecodeError, TypeError):
                    names = []
                aliases_raw = fi.get("aliases")
                aliases: dict[str, str] = {}
                if aliases_raw:
                    try:
                        aliases = json.loads(aliases_raw)
                    except (json.JSONDecodeError, TypeError):
                        aliases = {}
                parts: list[str] = []
                for n in names:
                    if n in aliases:
                        parts.append(f"{n} as {aliases[n]}")
                    else:
                        parts.append(n)
                names_str = ", ".join(parts)
                typer.echo(f"  from {module} import {names_str}  (line {line})")
            else:
                typer.echo(f"  import {module}  (line {line})")

    if verbose:
        typer.echo(f"\n共 {len(symbols)} 符号, {len(file_imports)} 导入")


def _show_symbol_detail(conn, symbol_name: str, verbose: bool) -> None:
    """Show symbol detail with dependencies and dependents."""
    rows = conn.execute(
        "SELECT s.id, s.name, s.kind, s.line_start, s.line_end, f.path "
        "FROM symbols s JOIN files f ON s.file_id = f.id "
        "WHERE s.name = ? AND f.status != 'deleted' "
        "ORDER BY f.path",
        (symbol_name,),
    ).fetchall()

    if not rows:
        typer.echo(f"符号未找到: {symbol_name}", err=True)
        raise typer.Exit(code=1)

    sym = rows[0]
    symbol_id: int = sym["id"]

    typer.echo(f"名称:   {sym['name']}")
    typer.echo(f"类型:   {sym['kind']}")
    typer.echo(f"文件:   {sym['path']}")
    typer.echo(f"行号:   {sym['line_start']}-{sym['line_end']}")

    if len(rows) > 1:
        other_files = [r["path"] for r in rows[1:]]
        typer.echo(f"同名:   也存在于 {', '.join(other_files)}")

    dep_rows = conn.execute(
        "SELECT d.dep_type, d.cross_file, s.name, s.kind, f.path "
        "FROM dependencies d "
        "JOIN symbols s ON d.target_id = s.id "
        "JOIN files f ON s.file_id = f.id "
        "WHERE d.source_id = ?",
        (symbol_id,),
    ).fetchall()

    if dep_rows:
        typer.echo("\n依赖 (此符号依赖的其他符号):")
        for d in dep_rows:
            cross = " [跨文件]" if d["cross_file"] else ""
            typer.echo(f"  {d['dep_type']}  {d['name']} ({d['kind']}) @ {d['path']}{cross}")
    else:
        typer.echo("\n依赖: 无")

    dependent_rows = conn.execute(
        "SELECT d.dep_type, d.cross_file, s.name, s.kind, f.path "
        "FROM dependencies d "
        "JOIN symbols s ON d.source_id = s.id "
        "JOIN files f ON s.file_id = f.id "
        "WHERE d.target_id = ?",
        (symbol_id,),
    ).fetchall()

    if dependent_rows:
        typer.echo("\n被依赖 (依赖此符号的其他符号):")
        for d in dependent_rows:
            cross = " [跨文件]" if d["cross_file"] else ""
            typer.echo(f"  {d['dep_type']}  {d['name']} ({d['kind']}) @ {d['path']}{cross}")
    else:
        typer.echo("\n被依赖: 无")

    if verbose:
        typer.echo(f"\n依赖: {len(dep_rows)}, 被依赖: {len(dependent_rows)}")


def run_show(
    file: str | None,
    symbol: str | None,
    db: str,
    verbose: bool,
) -> None:
    """Browse symbol information—file symbol list, symbol detail, dependency info."""
    conn = get_connection(db)
    try:
        if file is not None:
            _show_file_symbols(conn, file, verbose)
        elif symbol is not None:
            _show_symbol_detail(conn, symbol, verbose)
        else:
            _show_project_overview(conn, verbose)
    finally:
        conn.close()
