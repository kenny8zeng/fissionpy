"""Track extraction progress in the migration_progress SQLite table."""

from __future__ import annotations

import sqlite3
import time

from fissionpy.analysis.database import get_file_by_path


def init_progress(conn: sqlite3.Connection, plan: dict) -> None:
    """Insert pending migration_progress rows for every symbol in the plan."""
    target_file = plan.get("target_file", "")
    project_root = plan.get("project_root", "")
    abs_target = target_file
    if project_root:
        from pathlib import Path
        abs_target = str(Path(project_root) / target_file)

    file_row = get_file_by_path(conn, abs_target)
    if file_row is None:
        file_row = get_file_by_path(conn, target_file)
    if file_row is None:
        return

    file_id: int = file_row["id"]

    for module in plan.get("modules", []):
        module_name = module["name"]
        for symbol_name in module.get("symbols", []):
            row = conn.execute(
                "SELECT id FROM symbols WHERE file_id = ? AND name = ? LIMIT 1",
                (file_id, symbol_name),
            ).fetchone()
            if row is None:
                continue
            symbol_id: int = row["id"]
            conn.execute(
                "INSERT OR IGNORE INTO migration_progress (symbol_id, target_module, status) VALUES (?, ?, 'pending')",
                (symbol_id, module_name),
            )
    conn.commit()


def get_pending_modules(conn: sqlite3.Connection) -> list[dict]:
    """Return pending symbols grouped by target_module."""
    rows = conn.execute(
        """SELECT mp.target_module, mp.symbol_id, s.name AS symbol_name
           FROM migration_progress mp
           JOIN symbols s ON mp.symbol_id = s.id
           WHERE mp.status = 'pending'
           ORDER BY mp.target_module, s.name"""
    ).fetchall()

    modules: dict[str, dict] = {}
    for r in rows:
        mod_name = r["target_module"]
        if mod_name not in modules:
            modules[mod_name] = {"module_name": mod_name, "symbol_ids": [], "symbol_names": []}
        modules[mod_name]["symbol_ids"].append(r["symbol_id"])
        modules[mod_name]["symbol_names"].append(r["symbol_name"])

    return list(modules.values())


def mark_extracting(conn: sqlite3.Connection, symbol_id: int, target_module: str) -> None:
    """Set status to 'extracting' with current timestamp."""
    conn.execute(
        "UPDATE migration_progress SET status = 'extracting', started_at = ? WHERE symbol_id = ? AND target_module = ?",
        (time.time(), symbol_id, target_module),
    )
    conn.commit()


def mark_extracted(conn: sqlite3.Connection, symbol_id: int, target_module: str) -> None:
    """Set status to 'extracted' with current timestamp."""
    conn.execute(
        "UPDATE migration_progress SET status = 'extracted', completed_at = ? WHERE symbol_id = ? AND target_module = ?",
        (time.time(), symbol_id, target_module),
    )
    conn.commit()


def mark_failed(conn: sqlite3.Connection, symbol_id: int, target_module: str) -> None:
    """Set status to 'failed' with current timestamp."""
    conn.execute(
        "UPDATE migration_progress SET status = 'failed', completed_at = ? WHERE symbol_id = ? AND target_module = ?",
        (time.time(), symbol_id, target_module),
    )
    conn.commit()


def get_progress_summary(conn: sqlite3.Connection) -> dict:
    """Count symbols by status and return summary dict."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM migration_progress GROUP BY status"
    ).fetchall()

    counts: dict[str, int] = {"pending": 0, "extracting": 0, "extracted": 0, "failed": 0}
    total = 0
    for r in rows:
        status = r["status"]
        cnt = r["cnt"]
        total += cnt
        if status in counts:
            counts[status] = cnt

    counts["total"] = total
    return counts


def is_module_complete(conn: sqlite3.Connection, module_name: str) -> bool:
    """Return True if all symbols for the module have status 'extracted'."""
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM migration_progress WHERE target_module = ?",
        (module_name,),
    ).fetchone()
    if row is None or row["total"] == 0:
        return False

    incomplete = conn.execute(
        "SELECT COUNT(*) AS cnt FROM migration_progress WHERE target_module = ? AND status != 'extracted'",
        (module_name,),
    ).fetchone()

    return incomplete["cnt"] == 0
