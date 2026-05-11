from __future__ import annotations

import json
from pathlib import Path

from fissionpy.analysis.database import get_connection, init_db
from fissionpy.cli.analyze_cmd import run_analyze


def _make_project(tmp_path: Path) -> Path:
    proj = tmp_path / "myproject"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    (proj / "models.py").write_text(
        "from __future__ import annotations\n\n\nclass User:\n    name: str\n    age: int\n",
        encoding="utf-8",
    )
    (proj / "views.py").write_text(
        "from __future__ import annotations\n\nfrom models import User\n\n\ndef get_user(name: str) -> User:\n    return User(name=name, age=0)\n",
        encoding="utf-8",
    )
    (proj / "utils.py").write_text(
        "from __future__ import annotations\n\nMAX_RETRIES = 3\n\n\ndef format_name(name: str) -> str:\n    return name.strip().title()\n",
        encoding="utf-8",
    )
    return proj


def _db_path(tmp_path: Path) -> str:
    db_dir = tmp_path / ".fission"
    db_dir.mkdir(exist_ok=True)
    return str(db_dir / "fission.db")


def _run(proj: Path, db: str) -> None:
    run_analyze(str(proj), db, [], False, False)


def test_analyze_basic(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    _run(proj, db)

    conn = get_connection(db)
    try:
        rows = conn.execute("SELECT id, path, status FROM files").fetchall()
        paths = {r["path"] for r in rows}
        for name in ("models.py", "views.py", "utils.py"):
            assert any(p.endswith(name) for p in paths), f"{name} not found in files"
        assert all(r["status"] == "parsed" for r in rows)

        model_file = next(r for r in rows if r["path"].endswith("models.py"))
        symbols = conn.execute(
            "SELECT name, kind FROM symbols WHERE file_id = ?", (model_file["id"],)
        ).fetchall()
        sym_map = {s["name"]: s["kind"] for s in symbols}
        assert "User" in sym_map
        assert sym_map["User"] == "class"

        view_file = next(r for r in rows if r["path"].endswith("views.py"))
        view_syms = conn.execute(
            "SELECT name, kind FROM symbols WHERE file_id = ?", (view_file["id"],)
        ).fetchall()
        view_sym_map = {s["name"]: s["kind"] for s in view_syms}
        assert "get_user" in view_sym_map
        assert view_sym_map["get_user"] == "function"

        utils_file = next(r for r in rows if r["path"].endswith("utils.py"))
        utils_syms = conn.execute(
            "SELECT name, kind FROM symbols WHERE file_id = ?", (utils_file["id"],)
        ).fetchall()
        utils_sym_map = {s["name"]: s["kind"] for s in utils_syms}
        assert "MAX_RETRIES" in utils_sym_map
        assert utils_sym_map["MAX_RETRIES"] == "assignment"
        assert "format_name" in utils_sym_map
        assert utils_sym_map["format_name"] == "function"

        fis = conn.execute(
            "SELECT imported_names FROM file_imports WHERE source_file_id = ?",
            (view_file["id"],),
        ).fetchall()
        imported = set()
        for fi in fis:
            try:
                for n in json.loads(fi["imported_names"]):
                    imported.add(n)
            except (json.JSONDecodeError, TypeError):
                pass
        assert "User" in imported
    finally:
        conn.close()


def test_analyze_incremental(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    _run(proj, db)

    conn = get_connection(db)
    first_count = conn.execute("SELECT COUNT(*) AS c FROM files WHERE status = 'parsed'").fetchone()["c"]
    conn.close()

    _run(proj, db)

    conn = get_connection(db)
    second_count = conn.execute("SELECT COUNT(*) AS c FROM files WHERE status = 'parsed'").fetchone()["c"]
    conn.close()
    assert second_count == first_count

    views_file = proj / "views.py"
    original = views_file.read_text(encoding="utf-8")
    views_file.write_text(original + "\n\ndef new_func() -> str:\n    return 'x'\n", encoding="utf-8")

    _run(proj, db)

    conn = get_connection(db)
    views_row = conn.execute(
        "SELECT id, status FROM files WHERE path LIKE '%views.py'"
    ).fetchone()
    views_syms = conn.execute(
        "SELECT name FROM symbols WHERE file_id = ?", (views_row["id"],)
    ).fetchall()
    sym_names = {s["name"] for s in views_syms}
    assert "new_func" in sym_names
    conn.close()


def test_analyze_syntax_error(tmp_path: Path) -> None:
    proj = tmp_path / "errproject"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    (proj / "good.py").write_text(
        "from __future__ import annotations\n\n\ndef ok() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (proj / "broken.py").write_text("def foo(\n", encoding="utf-8")

    db = _db_path(tmp_path)
    _run(proj, db)

    conn = get_connection(db)
    try:
        error_rows = conn.execute(
            "SELECT path, status FROM files WHERE status = 'error'"
        ).fetchall()
        assert len(error_rows) >= 1
        assert any(r["path"].endswith("broken.py") for r in error_rows)

        parsed_rows = conn.execute(
            "SELECT id, path, status FROM files WHERE status = 'parsed'"
        ).fetchall()
        assert any(r["path"].endswith("good.py") for r in parsed_rows)

        good_row = next(r for r in parsed_rows if r["path"].endswith("good.py"))
        syms = conn.execute(
            "SELECT name, kind FROM symbols WHERE file_id = ?", (good_row["id"],)
        ).fetchall()
        assert any(s["name"] == "ok" for s in syms)
    finally:
        conn.close()


def test_analyze_deleted_file(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    _run(proj, db)

    (proj / "utils.py").unlink()

    _run(proj, db)

    conn = get_connection(db)
    try:
        deleted = conn.execute(
            "SELECT path, status FROM files WHERE status = 'deleted'"
        ).fetchall()
        assert len(deleted) >= 1
        assert any(r["path"].endswith("utils.py") for r in deleted)
    finally:
        conn.close()


def test_analyze_cross_file_dependency(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    _run(proj, db)

    conn = get_connection(db)
    try:
        cross_deps = conn.execute(
            "SELECT d.cross_file, s.name AS source_name, t.name AS target_name "
            "FROM dependencies d "
            "JOIN symbols s ON d.source_id = s.id "
            "JOIN symbols t ON d.target_id = t.id "
            "WHERE d.cross_file = 1"
        ).fetchall()

        has_user_dep = any(r["target_name"] == "User" for r in cross_deps)
        assert has_user_dep, f"Expected cross-file dep on User, got: {[dict(r) for r in cross_deps]}"
        assert all(r["cross_file"] == 1 for r in cross_deps)
    finally:
        conn.close()
