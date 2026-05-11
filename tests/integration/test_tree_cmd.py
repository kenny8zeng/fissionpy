from __future__ import annotations

from pathlib import Path

from click.exceptions import Exit

import pytest

from fissionpy.cli.analyze_cmd import run_analyze
from fissionpy.cli.tree_cmd import run_tree


def _make_project(tmp_path: Path) -> Path:
    proj = tmp_path / "myproject"
    proj.mkdir()
    (proj / "__init__.py").write_text("", encoding="utf-8")
    (proj / "models.py").write_text(
        "from __future__ import annotations\n\n\nclass User:\n name: str\n age: int\n",
        encoding="utf-8",
    )
    (proj / "views.py").write_text(
        "from __future__ import annotations\n\nfrom models import User\n\n\ndef get_user(name: str) -> User:\n return User(name=name, age=0)\n",
        encoding="utf-8",
    )
    (proj / "utils.py").write_text(
        "from __future__ import annotations\n\nMAX_RETRIES = 3\n\n\ndef format_name(name: str) -> str:\n return name.strip().title()\n",
        encoding="utf-8",
    )
    return proj


def _db_path(tmp_path: Path) -> str:
    db_dir = tmp_path / ".fission"
    db_dir.mkdir(exist_ok=True)
    return str(db_dir / "fission.db")


def _setup(tmp_path: Path) -> tuple[Path, str]:
    proj = _make_project(tmp_path)
    db = _db_path(tmp_path)
    run_analyze(str(proj), db, [], False, False)
    return proj, db


def test_tree_forward(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proj, db = _setup(tmp_path)

    views_path = str(proj / "views.py")
    run_tree(views_path, None, False, db, False)

    out = capsys.readouterr().out
    assert "跨文件" in out


def test_tree_symbol_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proj, db = _setup(tmp_path)

    views_path = str(proj / "views.py")
    run_tree(views_path, "get_user", False, db, False)

    out = capsys.readouterr().out
    assert "get_user" in out


def test_tree_reverse(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proj, db = _setup(tmp_path)

    models_path = str(proj / "models.py")
    run_tree(models_path, None, True, db, False)

    out = capsys.readouterr().out
    assert "被依赖" in out


def test_tree_nonexistent_file(tmp_path: Path) -> None:
    proj, db = _setup(tmp_path)

    with pytest.raises(Exit):
        run_tree("/nonexistent/path/missing.py", None, False, db, False)
