from __future__ import annotations

from fissionpy.migration.propagator import propagate_import_updates


def test_propagate_updates_import(tmp_path):
    file_path = tmp_path / "consumer.py"
    file_path.write_text("from models import User\n", encoding="utf-8")
    propagate_import_updates(
        [str(file_path)],
        {"models": "user_types"},
        {"User"},
    )
    result = file_path.read_text(encoding="utf-8")
    assert "from user_types import User" in result
    assert "from models import" not in result


def test_propagate_split_import(tmp_path):
    file_path = tmp_path / "consumer.py"
    file_path.write_text("from models import User, Product\n", encoding="utf-8")
    propagate_import_updates(
        [str(file_path)],
        {"models": "user_types"},
        {"User"},
    )
    result = file_path.read_text(encoding="utf-8")
    assert "from models import Product" in result
    assert "from user_types import User" in result


def test_propagate_unchanged(tmp_path):
    original = "from services import Product\n"
    file_path = tmp_path / "consumer.py"
    file_path.write_text(original, encoding="utf-8")
    propagate_import_updates(
        [str(file_path)],
        {"models": "user_types"},
        {"User"},
    )
    result = file_path.read_text(encoding="utf-8")
    assert result == original


def test_propagate_alias_import(tmp_path):
    file_path = tmp_path / "consumer.py"
    file_path.write_text("from models import User as U\n", encoding="utf-8")
    propagate_import_updates(
        [str(file_path)],
        {"models": "user_types"},
        {"User"},
    )
    result = file_path.read_text(encoding="utf-8")
    assert "from user_types import User as U" in result
    assert "from models import" not in result
