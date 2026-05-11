from __future__ import annotations

import json
from pathlib import Path

from fissionpy.analysis.database import get_connection, init_db
from fissionpy.cli.analyze_cmd import run_analyze
from fissionpy.cli.extract_cmd import run_extract
from fissionpy.cli.migrate_cmd import run_migrate
from fissionpy.cli.plan_cmd import run_plan
from fissionpy.cli.show_cmd import run_show
from fissionpy.extraction.planner import write_plan_yaml


def _make_full_project(tmp_path: Path) -> Path:
    proj = tmp_path / "fullproject"
    proj.mkdir()
    fission_dir = proj / ".fission"
    fission_dir.mkdir()
    (proj / "models.py").write_text(
        "from __future__ import annotations\n\n\nclass User:\n    name: str\n    age: int\n\n\nclass Product:\n    title: str\n    price: float\n\n\ndef _helper() -> str:\n    return \"helper\"\n\n\nMAX_ITEMS = 100\n",
        encoding="utf-8",
    )
    (proj / "views.py").write_text(
        "from __future__ import annotations\n\nfrom models import User\n\n\ndef get_user(name: str) -> User:\n    return User(name=name, age=0)\n\n\ndef list_users() -> list[User]:\n    return []\n",
        encoding="utf-8",
    )
    (proj / "utils.py").write_text(
        "from __future__ import annotations\n\n\ndef format_name(name: str) -> str:\n    return name.strip().title()\n\n\nMAX_RETRIES = 3\n",
        encoding="utf-8",
    )
    return proj


def _db_path(tmp_path: Path) -> str:
    db_dir = tmp_path / ".fission"
    db_dir.mkdir(exist_ok=True)
    return str(db_dir / "fission.db")


def test_full_workflow_basic(tmp_path: Path, capsys) -> None:
    proj = _make_full_project(tmp_path)
    db = _db_path(tmp_path)
    plan_file = tmp_path / "plan.yaml"

    run_analyze(str(proj), db, [], False, False)

    capsys.readouterr()
    run_show(str(proj / "models.py"), None, db, False)
    show_out = capsys.readouterr().out
    assert "User" in show_out
    assert "Product" in show_out
    assert "_helper" in show_out
    assert "MAX_ITEMS" in show_out

    run_plan(str(proj / "models.py"), db, str(plan_file), False)

    plan_yaml = plan_file.read_text(encoding="utf-8")
    from ruamel.yaml import YAML
    yaml = YAML()
    plan = dict(yaml.load(plan_yaml))

    plan["modules"] = [{"name": "entities", "symbols": ["User", "Product"]}]
    plan["retain"] = ["_helper", "MAX_ITEMS"]

    write_plan_yaml(plan, str(plan_file))

    run_extract(str(plan_file), db, False, False)
    capsys.readouterr()

    run_migrate(str(plan_file), db, False, False, False)

    entities_py = proj / "entities.py"
    assert entities_py.exists()
    entities_content = entities_py.read_text(encoding="utf-8")
    assert "class User" in entities_content
    assert "class Product" in entities_content

    models_content = (proj / "models.py").read_text(encoding="utf-8")
    assert "def _helper" in models_content
    assert "MAX_ITEMS" in models_content
    assert "from entities import" in models_content

    views_content = (proj / "views.py").read_text(encoding="utf-8")
    assert "from entities import User" in views_content
    assert "from models import User" not in views_content

    captured = capsys.readouterr()
    assert "✓ 符号完整性" in captured.out
    assert "✓ 格式无损性" in captured.out
    assert "✓ import 可达性" in captured.out


def test_full_workflow_subdirectory(tmp_path: Path, capsys) -> None:
    proj = _make_full_project(tmp_path)
    db = _db_path(tmp_path)
    plan_file = tmp_path / "plan.yaml"

    run_analyze(str(proj), db, [], False, False)

    plan = {
        "project_root": str(proj),
        "target_file": "models.py",
        "modules": [{"name": "sub/entities", "symbols": ["User", "Product"]}],
        "retain": ["_helper", "MAX_ITEMS"],
    }
    write_plan_yaml(plan, str(plan_file))

    run_extract(str(plan_file), db, False, False)
    run_migrate(str(plan_file), db, False, False, False)

    entities_py = proj / "sub" / "entities.py"
    assert entities_py.exists()
    entities_content = entities_py.read_text(encoding="utf-8")
    assert "class User" in entities_content
    assert "class Product" in entities_content

    models_content = (proj / "models.py").read_text(encoding="utf-8")
    assert "def _helper" in models_content
    assert "MAX_ITEMS" in models_content

    views_content = (proj / "views.py").read_text(encoding="utf-8")
    assert "entities" in views_content

    captured = capsys.readouterr()
    assert "迁移完成" in captured.out


def test_full_workflow_multi_module(tmp_path: Path, capsys) -> None:
    proj = _make_full_project(tmp_path)
    db = _db_path(tmp_path)
    plan_file = tmp_path / "plan.yaml"

    run_analyze(str(proj), db, [], False, False)

    plan = {
        "project_root": str(proj),
        "target_file": "models.py",
        "modules": [
            {"name": "user_types", "symbols": ["User"]},
            {"name": "product_types", "symbols": ["Product"]},
        ],
        "retain": ["_helper", "MAX_ITEMS"],
    }
    write_plan_yaml(plan, str(plan_file))

    run_extract(str(plan_file), db, False, False)
    run_migrate(str(plan_file), db, False, False, False)

    user_types_py = proj / "user_types.py"
    product_types_py = proj / "product_types.py"
    assert user_types_py.exists()
    assert product_types_py.exists()

    user_content = user_types_py.read_text(encoding="utf-8")
    assert "class User" in user_content
    assert "class Product" not in user_content

    product_content = product_types_py.read_text(encoding="utf-8")
    assert "class Product" in product_content
    assert "class User" not in product_content

    models_content = (proj / "models.py").read_text(encoding="utf-8")
    assert "def _helper" in models_content
    assert "MAX_ITEMS" in models_content
    assert "from user_types import User" in models_content
    assert "from product_types import Product" in models_content

    views_content = (proj / "views.py").read_text(encoding="utf-8")
    assert "from models import User" not in views_content
    assert "User" in views_content
