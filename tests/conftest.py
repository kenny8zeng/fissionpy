"""共享 fixtures——临时项目目录、临时 SQLite 数据库。"""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """创建临时多文件 Python 项目目录。"""
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    (app_dir / "__init__.py").write_text("")
    (app_dir / "models.py").write_text(
        'from __future__ import annotations\n\n\nclass User:\n    name: str\n    age: int\n\n\nclass Product:\n    title: str\n    price: float\n\n\ndef _helper() -> str:\n    return "helper"\n',
        encoding="utf-8",
    )
    (app_dir / "views.py").write_text(
        'from __future__ import annotations\n\nfrom app.models import User\n\n\ndef get_user(name: str) -> User:\n    return User(name=name, age=0)\n\n\ndef list_users() -> list[User]:\n    return []\n',
        encoding="utf-8",
    )
    (app_dir / "utils.py").write_text(
        'from __future__ import annotations\n\n\ndef format_name(name: str) -> str:\n    return name.strip().title()\n\n\nMAX_RETRIES = 3\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def tmp_db(tmp_path):
    """创建临时 SQLite 数据库路径。"""
    return str(tmp_path / ".fission" / "fission.db")
