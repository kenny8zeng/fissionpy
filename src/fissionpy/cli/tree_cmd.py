"""fission tree command implementation."""

from __future__ import annotations

from pathlib import Path

import typer

from fissionpy.analysis.database import (
    get_connection,
    get_file_by_path,
    get_symbols_by_file,
)

_MAX_DEPTH = 10

_CROSS_FILE_FMT = "\033[35m{}\033[0m"


def _build_dep_graph(conn, file_id: int) -> dict[int, list[tuple[int, str, str]]]:
    """Build symbol_id -> [(target_id, dep_type, cross_file_info)] mapping."""
    graph: dict[int, list[tuple[int, str, str]]] = {}
    rows = conn.execute(
        "SELECT d.source_id, d.target_id, d.dep_type, d.cross_file, "
        "t.name AS target_name, f.path AS target_path "
        "FROM dependencies d "
        "JOIN symbols s ON d.source_id = s.id "
        "JOIN symbols t ON d.target_id = t.id "
        "JOIN files f ON t.file_id = f.id "
        "WHERE s.file_id = ?",
        (file_id,),
    ).fetchall()

    for row in rows:
        source_id: int = row["source_id"]
        target_id: int = row["target_id"]
        dep_type: str = row["dep_type"]
        cross_info = ""
        if row["cross_file"]:
            cross_info = f"{row['target_name']} [跨文件: {row['target_path']}]"
        graph.setdefault(source_id, []).append((target_id, dep_type, cross_info))

    return graph


def _build_reverse_dep_graph(conn, file_id: int) -> dict[int, list[tuple[int, str, str]]]:
    """Build symbol_id -> [(source_id, dep_type, cross_file_info)] reverse mapping."""
    graph: dict[int, list[tuple[int, str, str]]] = {}
    rows = conn.execute(
        "SELECT d.source_id, d.target_id, d.dep_type, d.cross_file, "
        "s.name AS source_name, f.path AS source_path "
        "FROM dependencies d "
        "JOIN symbols t ON d.target_id = t.id "
        "JOIN symbols s ON d.source_id = s.id "
        "JOIN files f ON s.file_id = f.id "
        "WHERE t.file_id = ?",
        (file_id,),
    ).fetchall()

    for row in rows:
        target_id: int = row["target_id"]
        source_id: int = row["source_id"]
        dep_type: str = row["dep_type"]
        cross_info = ""
        if row["cross_file"]:
            cross_info = f"{row['source_name']} [跨文件: {row['source_path']}]"
        graph.setdefault(target_id, []).append((source_id, dep_type, cross_info))

    return graph


def _print_tree(
    conn,
    graph: dict[int, list[tuple[int, str, str]]],
    symbols: dict[int, dict],
    root_id: int,
    prefix: str,
    visited: set[int],
    reverse: bool = False,
    depth: int = 0,
) -> None:
    """Recursively print dependency tree."""
    if depth > _MAX_DEPTH:
        typer.echo(f"{prefix}...")
        return

    children = graph.get(root_id, [])
    for i, (child_id, dep_type, cross_info) in enumerate(children):
        is_last = i == len(children) - 1
        connector = "└── " if is_last else "├── "
        child_sym = symbols.get(child_id)
        if child_sym is None:
            name_row = conn.execute(
                "SELECT s.name, f.path FROM symbols s JOIN files f ON s.file_id = f.id WHERE s.id = ?",
                (child_id,),
            ).fetchone()
            if name_row is None:
                label = f"<unknown:{child_id}>"
            else:
                label = name_row["name"]
        else:
            label = child_sym["name"]

        if cross_info:
            display = _CROSS_FILE_FMT.format(cross_info)
        else:
            display = label

        dep_label = f"({dep_type}) " if dep_type else ""
        typer.echo(f"{prefix}{connector}{dep_label}{display}")

        if child_id in visited:
            typer.echo(f"{prefix}{'    ' if is_last else '│   '}└── ...")
            continue

        visited.add(child_id)
        extension = "    " if is_last else "│   "
        _print_tree(
            conn, graph, symbols, child_id,
            prefix + extension, visited, reverse, depth + 1,
        )
        visited.discard(child_id)


def run_tree(
    file: str,
    symbol: str | None,
    reverse: bool,
    db: str,
    verbose: bool,
) -> None:
    """Print dependency tree for symbols in the specified file."""
    conn = get_connection(db)
    try:
        resolved = str(Path(file).resolve())
        file_row = get_file_by_path(conn, resolved)
        if file_row is None:
            file_row = get_file_by_path(conn, file)
        if file_row is None:
            typer.echo(f"文件未索引: {file}", err=True)
            raise typer.Exit(code=1)

        file_id: int = file_row["id"]
        symbol_rows = get_symbols_by_file(conn, file_id)

        if not symbol_rows:
            typer.echo(f"文件 {file} 无顶层符号")
            return

        symbols: dict[int, dict] = {s["id"]: s for s in symbol_rows}

        if reverse:
            graph = _build_reverse_dep_graph(conn, file_id)
        else:
            graph = _build_dep_graph(conn, file_id)

        if symbol is not None:
            target_sym = next(
                (s for s in symbol_rows if s["name"] == symbol), None
            )
            if target_sym is None:
                typer.echo(f"符号未找到: {symbol}", err=True)
                raise typer.Exit(code=1)
            roots = [target_sym]
        else:
            roots = symbol_rows

        direction = "被依赖" if reverse else "依赖"
        typer.echo(f"{file} — {direction}树:")

        for root in roots:
            root_id: int = root["id"]
            typer.echo(f"{root['name']}")
            visited: set[int] = {root_id}
            _print_tree(conn, graph, symbols, root_id, "", visited, reverse)
            if root != roots[-1]:
                typer.echo("")

        if verbose:
            typer.echo(f"\n共 {len(roots)} 个符号, 最大深度 {_MAX_DEPTH}")
    finally:
        conn.close()
