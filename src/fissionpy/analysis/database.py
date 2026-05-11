"""SQLite database layer for fissionpy project-level code fission tool."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL UNIQUE,
    hash        TEXT NOT NULL,
    last_parsed REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS symbols (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id      INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    line_start   INTEGER NOT NULL,
    line_end     INTEGER NOT NULL,
    source_text  TEXT NOT NULL,
    UNIQUE(file_id, name, line_start)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id  INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    target_id  INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    dep_type   TEXT NOT NULL DEFAULT 'call',
    cross_file INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS file_imports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id  INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    import_type     TEXT NOT NULL,
    module_path     TEXT NOT NULL,
    imported_names  TEXT NOT NULL,
    aliases         TEXT,
    is_star_import  INTEGER NOT NULL DEFAULT 0,
    line_number     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_progress (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id      INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    target_module  TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    started_at     REAL,
    completed_at   REAL,
    UNIQUE(symbol_id, target_module)
);

CREATE TABLE IF NOT EXISTS import_updates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_file_id  INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    old_module_path TEXT NOT NULL,
    new_module_path TEXT NOT NULL,
    symbol_name     TEXT NOT NULL,
    alias           TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    applied_at      REAL
);
"""

_INDEXES = """\
CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_dependencies_source_id ON dependencies(source_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_target_id ON dependencies(target_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_dep_type ON dependencies(dep_type);
CREATE INDEX IF NOT EXISTS idx_dependencies_cross_file ON dependencies(cross_file);
CREATE INDEX IF NOT EXISTS idx_file_imports_source_file_id ON file_imports(source_file_id);
CREATE INDEX IF NOT EXISTS idx_file_imports_module_path ON file_imports(module_path);
CREATE INDEX IF NOT EXISTS idx_migration_progress_symbol_id ON migration_progress(symbol_id);
CREATE INDEX IF NOT EXISTS idx_migration_progress_status ON migration_progress(status);
CREATE INDEX IF NOT EXISTS idx_import_updates_target_file_id ON import_updates(target_file_id);
CREATE INDEX IF NOT EXISTS idx_import_updates_status ON import_updates(status);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a connection with foreign keys enabled and Row factory."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Create all tables and indexes."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.executescript(_INDEXES)
        conn.commit()
    finally:
        conn.close()


def get_or_create_file(conn: sqlite3.Connection, path: str, file_hash: str) -> int:
    """Return file_id for the given path, creating a new row if needed."""
    row = conn.execute(
        "SELECT id, hash FROM files WHERE path = ?", (path,)
    ).fetchone()
    if row is not None:
        file_id: int = row["id"]
        conn.execute(
            "UPDATE files SET hash = ?, last_parsed = CAST(strftime('%s','now') AS REAL), status = 'pending' WHERE id = ?",
            (file_hash, file_id),
        )
        return file_id
    import time
    cur = conn.execute(
        "INSERT INTO files (path, hash, last_parsed, status) VALUES (?, ?, ?, 'pending')",
        (path, file_hash, time.time()),
    )
    return cur.lastrowid  # type: ignore[return-value]


def clear_file_data(conn: sqlite3.Connection, file_id: int) -> None:
    """Delete symbols, dependencies, file_imports, and migration_progress for a file."""
    symbol_ids = conn.execute(
        "SELECT id FROM symbols WHERE file_id = ?", (file_id,)
    ).fetchall()
    symbol_id_list = [r["id"] for r in symbol_ids]
    if symbol_id_list:
        placeholders = ",".join("?" * len(symbol_id_list))
        conn.execute(
            f"DELETE FROM dependencies WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})",
            symbol_id_list + symbol_id_list,
        )
        conn.execute(
            f"DELETE FROM migration_progress WHERE symbol_id IN ({placeholders})",
            symbol_id_list,
        )
    conn.execute("DELETE FROM file_imports WHERE source_file_id = ?", (file_id,))
    conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))


def insert_symbol(
    conn: sqlite3.Connection,
    file_id: int,
    name: str,
    kind: str,
    line_start: int,
    line_end: int,
    source_text: str,
) -> int:
    """Insert a symbol row and return its id."""
    cur = conn.execute(
        "INSERT INTO symbols (file_id, name, kind, line_start, line_end, source_text) VALUES (?, ?, ?, ?, ?, ?)",
        (file_id, name, kind, line_start, line_end, source_text),
    )
    return cur.lastrowid  # type: ignore[return-value]


def insert_dependency(
    conn: sqlite3.Connection,
    source_id: int,
    target_id: int,
    dep_type: str,
    cross_file: int = 0,
) -> int:
    """Insert a dependency row and return its id."""
    cur = conn.execute(
        "INSERT INTO dependencies (source_id, target_id, dep_type, cross_file) VALUES (?, ?, ?, ?)",
        (source_id, target_id, dep_type, cross_file),
    )
    return cur.lastrowid  # type: ignore[return-value]


def insert_file_import(
    conn: sqlite3.Connection,
    source_file_id: int,
    import_type: str,
    module_path: str,
    imported_names: str,
    aliases: str | None,
    is_star_import: int,
    line_number: int,
) -> int:
    """Insert a file_import row and return its id."""
    cur = conn.execute(
        "INSERT INTO file_imports (source_file_id, import_type, module_path, imported_names, aliases, is_star_import, line_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source_file_id, import_type, module_path, imported_names, aliases, is_star_import, line_number),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a Row to a dict, returning None if row is None."""
    if row is None:
        return None
    return dict(row)


def get_symbols_by_file(conn: sqlite3.Connection, file_id: int) -> list[dict[str, Any]]:
    """Return all symbols for a given file as dicts."""
    rows = conn.execute(
        "SELECT * FROM symbols WHERE file_id = ?", (file_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_dependencies_by_file(conn: sqlite3.Connection, file_id: int) -> list[dict[str, Any]]:
    """Return all dependencies where source or target symbol belongs to the given file."""
    rows = conn.execute(
        """SELECT d.* FROM dependencies d
           JOIN symbols s ON d.source_id = s.id
           JOIN symbols t ON d.target_id = t.id
           WHERE s.file_id = ? OR t.file_id = ?""",
        (file_id, file_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_file_imports_by_file(conn: sqlite3.Connection, file_id: int) -> list[dict[str, Any]]:
    """Return all file_imports for a given file as dicts."""
    rows = conn.execute(
        "SELECT * FROM file_imports WHERE source_file_id = ?", (file_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_symbol_by_name(conn: sqlite3.Connection, file_id: int, name: str) -> dict[str, Any] | None:
    """Return the first symbol matching name in the given file, or None."""
    row = conn.execute(
        "SELECT * FROM symbols WHERE file_id = ? AND name = ? LIMIT 1",
        (file_id, name),
    ).fetchone()
    return _row_to_dict(row)


def get_file_by_path(conn: sqlite3.Connection, path: str) -> dict[str, Any] | None:
    """Return the file row for the given path, or None."""
    row = conn.execute(
        "SELECT * FROM files WHERE path = ?", (path,)
    ).fetchone()
    return _row_to_dict(row)


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_analysis(
    conn: sqlite3.Connection,
    file_path: str,
    file_hash: str,
    symbols: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    file_imports: list[dict[str, Any]],
    force: bool = False,
) -> int:
    """Full save: upsert file, clear old data, insert symbols/dependencies/file_imports.

    If force is False and the file hash matches the stored hash, skip re-parsing
    and return the existing file_id immediately.
    """
    existing = get_file_by_path(conn, file_path)
    if existing is not None and not force and existing["hash"] == file_hash:
        return existing["id"]

    file_id = get_or_create_file(conn, file_path, file_hash)
    clear_file_data(conn, file_id)

    symbol_id_map: dict[int, int] = {}
    for sym in symbols:
        old_id = sym.get("id")
        new_id = insert_symbol(
            conn,
            file_id,
            sym["name"],
            sym["kind"],
            sym["line_start"],
            sym["line_end"],
            sym["source_text"],
        )
        if old_id is not None:
            symbol_id_map[old_id] = new_id

    for dep in dependencies:
        raw_source = dep.get("source_id")
        raw_target = dep.get("target_id")
        source_id = symbol_id_map.get(raw_source, raw_source) if raw_source is not None else None
        target_id = symbol_id_map.get(raw_target, raw_target) if raw_target is not None else None
        if source_id is not None and target_id is not None:
            insert_dependency(conn, source_id, target_id, dep["dep_type"], dep.get("cross_file", 0))

    for imp in file_imports:
        insert_file_import(
            conn,
            file_id,
            imp["import_type"],
            imp["module_path"],
            imp["imported_names"],
            imp.get("aliases"),
            imp.get("is_star_import", 0),
            imp["line_number"],
        )

    conn.commit()
    return file_id


def mark_file_deleted(conn: sqlite3.Connection, file_id: int) -> None:
    """Set a file's status to 'deleted'."""
    conn.execute("UPDATE files SET status = 'deleted' WHERE id = ?", (file_id,))
    conn.commit()


def get_all_symbols_across_project(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all symbols from all parsed (non-deleted) files."""
    rows = conn.execute(
        """SELECT s.*, f.path AS file_path FROM symbols s
           JOIN files f ON s.file_id = f.id
           WHERE f.status = 'parsed'""",
    ).fetchall()
    return [dict(r) for r in rows]


def get_files_importing_symbol(
    conn: sqlite3.Connection,
    symbol_name: str,
    source_file_id: int,
) -> list[dict[str, Any]]:
    """Find all file_imports that reference a symbol from a specific source file.

    Matches file_imports where the module_path corresponds to the source file
    and the symbol_name appears in the imported_names JSON array or is a star import.
    """
    source_file = conn.execute(
        "SELECT path FROM files WHERE id = ?", (source_file_id,)
    ).fetchone()
    if source_file is None:
        return []

    from fissionpy.common.paths import file_path_to_module_path
    from fissionpy.common.paths import find_project_root

    project_root = find_project_root(source_file["path"])
    if project_root is None:
        module_path = ""
    else:
        module_path = file_path_to_module_path(source_file["path"], project_root)

    python_import = module_path.replace("/", ".")
    import_candidates = {module_path, python_import}
    for candidate in list(import_candidates):
        parts = candidate.replace("/", ".").split(".")
        for i in range(1, len(parts)):
            import_candidates.add(".".join(parts[i:]))
    placeholders = ",".join("?" * len(import_candidates))
    like_pattern = f'%"{symbol_name}"%'
    module_suffix_like = f"%.{python_import}" if python_import else None
    extra_sql = ""
    extra_params: list[str] = []
    if module_suffix_like and module_suffix_like not in import_candidates:
        extra_sql = f" OR fi.module_path LIKE ?"
        extra_params = [module_suffix_like]
    rows = conn.execute(
        f"""SELECT fi.*, f.path AS source_file_path FROM file_imports fi
        JOIN files f ON fi.source_file_id = f.id
        WHERE (fi.module_path IN ({placeholders}){extra_sql})
        AND (fi.is_star_import = 1
        OR fi.imported_names LIKE ?)""",
        list(import_candidates) + extra_params + [like_pattern],
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if not d["is_star_import"]:
            try:
                names = json.loads(d["imported_names"])
            except (json.JSONDecodeError, TypeError):
                names = []
            if symbol_name not in names:
                continue
        results.append(d)
    return results
