from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from fissionpy.analysis.database import (
    get_connection,
    get_or_create_file,
    init_db,
    insert_dependency,
    insert_file_import,
    insert_symbol,
)
from fissionpy.extraction.planner import generate_plan, validate_plan, write_plan_yaml


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _setup_project_root(tmp_path):
    fission_dir = tmp_path / ".fission"
    fission_dir.mkdir(exist_ok=True)
    return str(tmp_path)


def _insert_three_symbols(conn, file_path, project_root):
    file_id = get_or_create_file(conn, file_path, "abc123")
    user_id = insert_symbol(conn, file_id, "User", "class", 1, 10, "class User: ...")
    product_id = insert_symbol(
        conn, file_id, "Product", "class", 12, 20, "class Product: ..."
    )
    helper_id = insert_symbol(
        conn, file_id, "_helper", "function", 22, 25, "def _helper(): ..."
    )
    conn.commit()
    return file_id, user_id, product_id, helper_id


def test_generate_plan_basic(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    file_id, user_id, product_id, helper_id = _insert_three_symbols(
        db_conn, file_path, project_root
    )
    insert_dependency(db_conn, helper_id, user_id, "call", cross_file=0)
    db_conn.commit()

    plan = generate_plan(db_conn, file_path)

    assert "target_file" in plan
    assert "modules" in plan
    assert "retain" in plan
    assert "import_impact" in plan
    assert any(
        "User" in mod["symbols"] and "_helper" in mod["symbols"]
        for mod in plan["modules"]
    )
    assert "Product" in plan["retain"]


def test_generate_plan_no_deps(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    _insert_three_symbols(db_conn, file_path, project_root)

    plan = generate_plan(db_conn, file_path)

    assert plan["modules"] == []
    assert sorted(plan["retain"]) == ["Product", "User", "_helper"]


def test_validate_plan_valid(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    file_id, user_id, product_id, helper_id = _insert_three_symbols(
        db_conn, file_path, project_root
    )

    plan = {
        "target_file": str(Path(file_path).relative_to(project_root)),
        "project_root": project_root,
        "modules": [
            {"name": "module_1", "symbols": ["User", "_helper"]},
        ],
        "retain": ["Product"],
    }

    errors = validate_plan(plan, db_conn)

    assert errors == []


def test_validate_plan_invalid_symbol(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    _insert_three_symbols(db_conn, file_path, project_root)

    plan = {
        "target_file": str(Path(file_path).relative_to(project_root)),
        "project_root": project_root,
        "modules": [
            {"name": "module_1", "symbols": ["NonExistent"]},
        ],
        "retain": [],
    }

    errors = validate_plan(plan, db_conn)

    assert any("NonExistent" in e for e in errors)


def test_validate_plan_duplicate_symbol(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    _insert_three_symbols(db_conn, file_path, project_root)

    plan = {
        "target_file": str(Path(file_path).relative_to(project_root)),
        "project_root": project_root,
        "modules": [
            {"name": "module_1", "symbols": ["User"]},
            {"name": "module_2", "symbols": ["User"]},
        ],
        "retain": [],
    }

    errors = validate_plan(plan, db_conn)

    assert any("重复" in e for e in errors)


def test_validate_plan_invalid_module_name(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    _insert_three_symbols(db_conn, file_path, project_root)

    plan = {
        "target_file": str(Path(file_path).relative_to(project_root)),
        "project_root": project_root,
        "modules": [
            {"name": "123bad", "symbols": ["User"]},
        ],
        "retain": [],
    }

    errors = validate_plan(plan, db_conn)

    assert any("123bad" in e for e in errors)


def test_validate_plan_subdir_module_name(tmp_path, db_conn):
    project_root = _setup_project_root(tmp_path)
    file_path = str(tmp_path / "app" / "models.py")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch()
    _insert_three_symbols(db_conn, file_path, project_root)

    plan = {
        "target_file": str(Path(file_path).relative_to(project_root)),
        "project_root": project_root,
        "modules": [
            {"name": "sub/types", "symbols": ["User"]},
        ],
        "retain": [],
    }

    errors = validate_plan(plan, db_conn)

    assert errors == []


def test_write_plan_yaml(tmp_path):
    plan = {
        "project_root": "/fake/root",
        "target_file": "app/models.py",
        "modules": [{"name": "module_1", "symbols": ["User", "_helper"]}],
        "retain": ["Product"],
        "import_impact": [],
    }
    output_path = str(tmp_path / "plan.yaml")

    write_plan_yaml(plan, output_path)

    yaml = YAML()
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            break
    with open(output_path, "r", encoding="utf-8") as f:
        loaded = yaml.load(f)

    assert loaded["target_file"] == plan["target_file"]
    assert loaded["retain"] == plan["retain"]
    assert len(loaded["modules"]) == 1
    assert loaded["modules"][0]["name"] == "module_1"
    assert sorted(loaded["modules"][0]["symbols"]) == ["User", "_helper"]
    assert loaded["import_impact"] == []
