from __future__ import annotations

from pathlib import Path

from fissionpy.analysis.database import get_connection, init_db
from fissionpy.cli.analyze_cmd import run_analyze
from fissionpy.cli.extract_cmd import run_extract
from fissionpy.cli.migrate_cmd import run_migrate
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


def _run_full_pipeline(proj: Path, db: str, plan_file: Path, modules: list[dict], no_reexport: bool = False) -> None:
    run_analyze(str(proj), db, [], False, False)
    _write_plan(proj, plan_file, modules)
    run_extract(str(plan_file), db, False, False)
    run_migrate(str(plan_file), db, no_reexport, False, False)


def test_migrate_full_workflow(tmp_path: Path, capsys) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    plan_file = tmp_path / "plan.yaml"
    modules = [{"name": "entities", "symbols": ["User", "Product"]}]

    _run_full_pipeline(proj, db, plan_file, modules, no_reexport=False)

    views_content = (proj / "views.py").read_text(encoding="utf-8")
    assert "from entities import User" in views_content
    assert "from models import User" not in views_content

    assert (proj / "models.py.bak").exists()

    assert (proj / "__init__.py").exists()

    models_content = (proj / "models.py").read_text(encoding="utf-8")
    assert "from entities import" in models_content
    assert "User" in models_content or "Product" in models_content

    captured = capsys.readouterr()
    assert "迁移完成" in captured.out


def test_migrate_no_reexport(tmp_path: Path, capsys) -> None:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    plan_file = tmp_path / "plan.yaml"
    modules = [{"name": "entities", "symbols": ["User", "Product"]}]

    _run_full_pipeline(proj, db, plan_file, modules, no_reexport=True)

    models_content = (proj / "models.py").read_text(encoding="utf-8")
    assert "from entities import" not in models_content

    captured = capsys.readouterr()
    assert "迁移完成" in captured.out
