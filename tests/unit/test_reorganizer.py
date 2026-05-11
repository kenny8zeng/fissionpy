from __future__ import annotations

from fissionpy.migration.reorganizer import (
    backup_file,
    ensure_init_files,
    reorganize_target_file,
    restore_from_backup,
)


def test_backup_file(tmp_path):
    original = tmp_path / "models.py"
    original.write_text("class User:\n pass\n", encoding="utf-8")
    backup_path = backup_file(str(original))
    assert (tmp_path / "models.py.bak").exists()
    assert (tmp_path / "models.py.bak").read_text(encoding="utf-8") == "class User:\n pass\n"
    assert backup_path == str(original) + ".bak"


def test_reorganize_removes_symbols(tmp_path):
    src = tmp_path / "models.py"
    src.write_text(
        "class User:\n pass\n\n\nclass Product:\n pass\n",
        encoding="utf-8",
    )
    plan = {
        "target_file": "models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    reorganize_target_file(str(src), plan, str(tmp_path), no_reexport=True)
    result = src.read_text(encoding="utf-8")
    assert "class User" not in result
    assert "class Product" in result


def test_reorganize_adds_reexport(tmp_path):
    src = tmp_path / "models.py"
    src.write_text(
        "class User:\n pass\n\n\nclass Product:\n pass\n",
        encoding="utf-8",
    )
    plan = {
        "target_file": "models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    reorganize_target_file(str(src), plan, str(tmp_path))
    result = src.read_text(encoding="utf-8")
    assert "from user_types import User" in result


def test_reorganize_adds_reexport_after_future(tmp_path):
    src = tmp_path / "models.py"
    src.write_text(
        "from __future__ import annotations\n\n\nclass User:\n pass\n",
        encoding="utf-8",
    )
    plan = {
        "target_file": "models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    reorganize_target_file(str(src), plan, str(tmp_path))
    result = src.read_text(encoding="utf-8")
    lines = [l for l in result.splitlines() if l.strip()]
    future_idx = next(i for i, l in enumerate(lines) if "__future__" in l)
    reexport_idx = next(i for i, l in enumerate(lines) if "user_types" in l)
    assert reexport_idx > future_idx


def test_reorganize_no_reexport(tmp_path):
    src = tmp_path / "models.py"
    src.write_text(
        "class User:\n pass\n\n\nclass Product:\n pass\n",
        encoding="utf-8",
    )
    plan = {
        "target_file": "models.py",
        "modules": [{"name": "user_types", "symbols": ["User"]}],
    }
    reorganize_target_file(str(src), plan, str(tmp_path), no_reexport=True)
    result = src.read_text(encoding="utf-8")
    assert "import User" not in result
    assert "from" not in result or "user_types" not in result


def test_ensure_init_files(tmp_path):
    src = tmp_path / "models.py"
    src.write_text("", encoding="utf-8")
    plan = {
        "modules": [{"name": "sub/types", "symbols": ["User"]}],
    }
    created = ensure_init_files(str(src), plan)
    assert (tmp_path / "sub" / "__init__.py").exists()
    assert any("sub" in p for p in created)


def test_restore_from_backup(tmp_path):
    original = tmp_path / "models.py"
    original.write_text("original content\n", encoding="utf-8")
    backup_file(str(original))
    original.write_text("modified content\n", encoding="utf-8")
    result = restore_from_backup(str(original))
    assert result is True
    assert original.read_text(encoding="utf-8") == "original content\n"
    assert not (tmp_path / "models.py.bak").exists()
