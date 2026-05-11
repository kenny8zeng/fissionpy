from __future__ import annotations

from pathlib import Path

from fissionpy.analysis.database import (
    get_connection,
    get_or_create_file,
    init_db,
    insert_symbol,
    save_analysis,
)
from fissionpy.analysis.import_resolver import FileImport, resolve_imports
from fissionpy.analysis.parser import parse_file


def test_import_star(tmp_path: Path) -> None:
    source = "from models import *\n"
    imports = resolve_imports(source)
    assert len(imports) >= 1
    star_imp = imports[0]
    assert isinstance(star_imp, FileImport)
    assert star_imp.is_star_import is True
    assert star_imp.module_path == "models"


def test_same_name_symbols(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"
    file_a.write_text(
        "from __future__ import annotations\n\n\nclass Helper:\n    x: int\n",
        encoding="utf-8",
    )
    file_b.write_text(
        "from __future__ import annotations\n\n\nclass Helper:\n    y: str\n",
        encoding="utf-8",
    )

    syms_a = parse_file(str(file_a))
    syms_b = parse_file(str(file_b))

    assert len(syms_a) == 1
    assert len(syms_b) == 1
    assert syms_a[0].name == "Helper"
    assert syms_b[0].name == "Helper"

    db_dir = tmp_path / ".fission"
    db_dir.mkdir(exist_ok=True)
    db_path = str(db_dir / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        from fissionpy.analysis.database import compute_file_hash

        hash_a = compute_file_hash(str(file_a))
        hash_b = compute_file_hash(str(file_b))
        file_id_a = get_or_create_file(conn, str(file_a), hash_a)
        file_id_b = get_or_create_file(conn, str(file_b), hash_b)
        insert_symbol(conn, file_id_a, "Helper", "class", 4, 5, "class Helper:\n    x: int\n")
        insert_symbol(conn, file_id_b, "Helper", "class", 4, 5, "class Helper:\n    y: str\n")
        conn.commit()

        helpers = conn.execute(
            "SELECT id, file_id, name FROM symbols WHERE name = 'Helper'"
        ).fetchall()
        assert len(helpers) == 2
        file_ids = {r["file_id"] for r in helpers}
        assert file_id_a in file_ids
        assert file_id_b in file_ids
        assert file_id_a != file_id_b
    finally:
        conn.close()


def test_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("", encoding="utf-8")

    symbols = parse_file(str(empty_file))
    assert symbols == []


def test_init_only_file(tmp_path: Path) -> None:
    init_file = tmp_path / "__init__.py"
    init_file.write_text('"""Package init."""\n\n__all__ = ["foo"]\n', encoding="utf-8")

    symbols = parse_file(str(init_file))
    assert isinstance(symbols, list)


def test_class_with_decorator(tmp_path: Path) -> None:
    source = "from dataclasses import dataclass\n\n@dataclass\nclass Foo:\n    x: int = 0\n"
    source_file = tmp_path / "decorated.py"
    source_file.write_text(source, encoding="utf-8")

    symbols = parse_file(str(source_file))
    assert len(symbols) == 1
    assert symbols[0].name == "Foo"
    assert symbols[0].kind == "class"
    assert "@dataclass" in symbols[0].source_text


def test_class_with_base_class(tmp_path: Path) -> None:
    source = "class Foo(Bar):\n    pass\n"
    source_file = tmp_path / "with_base.py"
    source_file.write_text(source, encoding="utf-8")

    symbols = parse_file(str(source_file))
    assert len(symbols) == 1
    assert symbols[0].name == "Foo"
    assert symbols[0].kind == "class"
    assert "Bar" in symbols[0].source_text


def test_nested_import_from() -> None:
    source = "from a.b.c import X\n"
    imports = resolve_imports(source)
    assert len(imports) == 1
    imp = imports[0]
    assert imp.module_path == "a.b.c"
    assert imp.imported_names == ["X"]
    assert imp.import_type == "from_import"


def test_relative_import() -> None:
    source = "from . import sibling\n"
    imports = resolve_imports(source)
    assert len(imports) == 1
    imp = imports[0]
    assert imp.module_path == "" or imp.module_path == "."
    assert "sibling" in imp.imported_names
