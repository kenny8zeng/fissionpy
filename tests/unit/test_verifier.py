from __future__ import annotations

from pathlib import Path

from fissionpy.migration.verifier import (
    run_full_verification,
    verify_format_lossless,
    verify_import_reachability,
    verify_symbol_integrity,
)


def test_verify_symbol_integrity(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    module_file = app_dir / "user_types.py"
    module_file.write_text("class User:\n pass\n", encoding="utf-8")
    plan = {
        "target_file": "app/models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    passed, errors = verify_symbol_integrity([], plan, str(tmp_path))
    assert passed is True
    assert errors == []


def test_verify_symbol_integrity_missing(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    module_file = app_dir / "user_types.py"
    module_file.write_text("class Product:\n pass\n", encoding="utf-8")
    plan = {
        "target_file": "app/models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    passed, errors = verify_symbol_integrity([], plan, str(tmp_path))
    assert passed is False
    assert any("User" in e for e in errors)


def test_verify_format_lossless(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    backup_source = "class User:\n pass\n\n\nclass Product:\n pass\n"
    backup_path = str(app_dir / "models.py.bak")
    Path(backup_path).write_text(backup_source, encoding="utf-8")
    module_file = app_dir / "user_types.py"
    module_file.write_text("class User:\n pass\n", encoding="utf-8")
    plan = {
        "target_file": "app/models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    passed, errors = verify_format_lossless(
        "app/models.py", backup_path, plan, str(tmp_path),
    )
    assert passed is True
    assert errors == []


def test_verify_import_reachability(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    module_file = app_dir / "user_types.py"
    module_file.write_text("class User:\n pass\n", encoding="utf-8")
    plan = {
        "target_file": "app/models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    passed, errors, warnings = verify_import_reachability(str(tmp_path), plan)
    assert passed is True
    assert errors == []


def test_verify_import_reachability_missing(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    plan = {
        "target_file": "app/models.py",
        "modules": [{"name": "missing_mod", "symbols": ["User"]}],
    }
    passed, errors, warnings = verify_import_reachability(str(tmp_path), plan)
    assert passed is False
    assert len(errors) > 0
