from __future__ import annotations

from pathlib import Path

from click.exceptions import Exit

import pytest

from fissionpy.cli.analyze_cmd import run_analyze
from fissionpy.cli.show_cmd import run_show


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


def test_show_project_overview(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proj, db = _setup(tmp_path)
    capsys.readouterr()

    run_show(None, None, db, False)

    out = capsys.readouterr().out
    for name in ("models.py", "views.py", "utils.py"):
        assert name in out
    assert "symbol" in out or "symbols" in out


def test_show_file_symbols(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proj, db = _setup(tmp_path)
    capsys.readouterr()

    models_path = str(proj / "models.py")
    run_show(models_path, None, db, False)

    out = capsys.readouterr().out
    assert "User" in out
    assert "class" in out
    assert "1-" in out


def test_show_symbol_detail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proj, db = _setup(tmp_path)
    capsys.readouterr()

    run_show(None, "User", db, False)

    out = capsys.readouterr().out
    assert "User" in out
    assert "class" in out
    assert "models.py" in out
    assert "依赖" in out or "被依赖" in out


def test_show_nonexistent_file(tmp_path: Path) -> None:
    proj, db = _setup(tmp_path)

    with pytest.raises(Exit):
        run_show("/nonexistent/path/missing.py", None, db, False)


def test_show_nonexistent_symbol(tmp_path: Path) -> None:
    proj, db = _setup(tmp_path)

    with pytest.raises(Exit):
        run_show(None, "NonExistent", db, False)
