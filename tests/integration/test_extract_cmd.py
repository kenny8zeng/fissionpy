from __future__ import annotations

import sqlite3
from pathlib import Path

from fissionpy.analysis.database import get_connection, init_db
from fissionpy.cli.analyze_cmd import run_analyze
from fissionpy.cli.extract_cmd import run_extract
from fissionpy.extraction.planner import write_plan_yaml


def _make_project(tmp_path: Path) -> Path:
    proj = tmp_path / "myproject"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    (proj / "models.py").write_text(
        "from __future__ import annotations\n\n\nclass User:\n    name: str\n    age: int\n\n\nclass Product:\n    title: str\n    price: float\n\n\ndef _helper() -> str:\n    return \"helper\"\n",
        encoding="utf-8",
    )
    (proj / "views.py").write_text(
        "from __future__ import annotations\n\nfrom models import User\n\n\ndef get_user(name: str) -> User:\n    return User(name=name, age=0)\n",
        encoding="utf-8",
    )
    return proj


def _db_path(tmp_path: Path) -> str:
    db_dir = tmp_path / ".fission"
    db_dir.mkdir(exist_ok=True)
    return str(db_dir / "fission.db")


def _write_plan(proj: Path, plan_file: Path, modules: list[dict]) -> None:
    plan = {
        "project_root": str(proj),
        "target_file": "models.py",
        "modules": modules,
        "retain": [],
    }
    write_plan_yaml(plan, str(plan_file))


def test_extract_full_workflow(tmp_path: Path, capsys) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    run_analyze(str(proj), db, [], False, False)

    plan_file = tmp_path / "plan.yaml"
    _write_plan(proj, plan_file, [{"name": "entities", "symbols": ["User", "Product"]}])

    run_extract(str(plan_file), db, False, False)

    extracted_file = proj / "entities.py"
    assert extracted_file.exists()
    content = extracted_file.read_text(encoding="utf-8")
    assert "class User" in content
    assert "class Product" in content
    assert "_helper" not in content

    captured = capsys.readouterr()
    assert "提取完成" in captured.out


def test_extract_with_subdirectory(tmp_path: Path, capsys) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    run_analyze(str(proj), db, [], False, False)

    plan_file = tmp_path / "plan.yaml"
    _write_plan(proj, plan_file, [{"name": "sub/entities", "symbols": ["User", "Product"]}])

    run_extract(str(plan_file), db, False, False)

    extracted_file = proj / "sub" / "entities.py"
    assert extracted_file.exists()
    content = extracted_file.read_text(encoding="utf-8")
    assert "class User" in content
    assert "class Product" in content


def test_extract_progress_tracking(tmp_path: Path, capsys) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    run_analyze(str(proj), db, [], False, False)

    plan_file = tmp_path / "plan.yaml"
    _write_plan(proj, plan_file, [{"name": "entities", "symbols": ["User", "Product"]}])

    run_extract(str(plan_file), db, False, False)

    conn = get_connection(db)
    try:
        rows = conn.execute(
            "SELECT mp.status, s.name FROM migration_progress mp "
            "JOIN symbols s ON mp.symbol_id = s.id "
            "WHERE s.name IN ('User', 'Product')"
        ).fetchall()
        status_map = {r["name"]: r["status"] for r in rows}
        assert status_map.get("User") == "extracted"
        assert status_map.get("Product") == "extracted"
    finally:
        conn.close()
