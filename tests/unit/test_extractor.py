from __future__ import annotations

from pathlib import Path

from fissionpy.extraction.extractor import (
    extract_module,
    extract_symbols,
    remove_symbols_from_source,
)


def test_extract_symbols_function():
    source = "def foo():\n    pass\n\n\ndef bar():\n    pass\n"
    result = extract_symbols(source, ["foo"])
    assert "def foo():" in result
    assert "bar" not in result


def test_extract_symbols_class():
    source = "class User:\n    pass\n\n\nclass Product:\n    pass\n"
    result = extract_symbols(source, ["User"])
    assert "class User:" in result


def test_extract_symbols_assignment():
    source = "MAX = 100\n\n\nMIN = 0\n"
    result = extract_symbols(source, ["MAX"])
    assert "MAX = 100" in result


def test_extract_symbols_lossless():
    source = "MAX = 100\n\n\n# calc\ndef compute(x: int) -> int:\n    return x * 2\n"
    result = extract_symbols(source, ["compute"])
    original_compute = "# calc\ndef compute(x: int) -> int:\n    return x * 2\n"
    assert result.strip() == original_compute.strip()


def test_extract_symbols_not_found():
    source = "def foo():\n    pass\n"
    result = extract_symbols(source, ["nonexistent"])
    assert result == ""


def test_extract_module_creates_file(tmp_path):
    src_file = tmp_path / "models.py"
    src_file.write_text("class User:\n    pass\n\n\nclass Product:\n    pass\n", encoding="utf-8")
    result = extract_module(str(src_file), "user_mod", ["User"], str(tmp_path))
    output_path = Path(result.output_path)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "class User:" in content
    assert "Product" not in content


def test_extract_module_subdirectory(tmp_path):
    src_file = tmp_path / "models.py"
    src_file.write_text("class User:\n    pass\n", encoding="utf-8")
    result = extract_module(str(src_file), "sub/types", ["User"], str(tmp_path))
    expected = tmp_path / "sub" / "types.py"
    assert Path(result.output_path) == expected
    assert expected.exists()
    assert expected.parent.is_dir()


def test_remove_symbols_from_source():
    source = "class User:\n    pass\n\n\nclass Product:\n    pass\n\n\ndef helper():\n    pass\n"
    result = remove_symbols_from_source(source, ["Product"])
    assert "class User:" in result
    assert "def helper" in result
    assert "Product" not in result
