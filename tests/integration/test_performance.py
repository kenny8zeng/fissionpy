from __future__ import annotations

import time
from pathlib import Path

from fissionpy.analysis.database import get_connection
from fissionpy.cli.analyze_cmd import run_analyze


def test_analyze_100_files_under_30s(tmp_path: Path) -> None:
    project_dir = tmp_path / "perf_project"
    project_dir.mkdir()
    (project_dir / ".fission").mkdir()

    for i in range(100):
        content = (
            f"from __future__ import annotations\n"
            f"class Model{i}:\n"
            f"    name: str\n\n"
            f"def func_{i}() -> int:\n"
            f"    return {i}\n\n"
            f"VAR_{i} = {i}\n"
        )
        (project_dir / f"module_{i:03d}.py").write_text(content, encoding="utf-8")

    db = str(project_dir / ".fission" / "fission.db")

    start = time.time()
    run_analyze(str(project_dir), db, [], False, False)
    elapsed = time.time() - start

    assert elapsed < 30, f"Analysis took {elapsed:.2f}s, exceeds 30s limit"

    conn = get_connection(db)
    try:
        file_count = conn.execute(
            "SELECT COUNT(*) AS c FROM files WHERE status = 'parsed'"
        ).fetchone()["c"]
        symbol_count = conn.execute(
            "SELECT COUNT(*) AS c FROM symbols"
        ).fetchone()["c"]
    finally:
        conn.close()

    assert file_count == 100, f"Expected 100 parsed files, got {file_count}"
    assert symbol_count > 0, "Expected non-zero symbol count"
