"""fission extract <plan> command implementation."""

from __future__ import annotations

import time

import typer
from ruamel.yaml import YAML

from fissionpy.analysis.database import (
    get_connection,
    get_file_by_path,
    get_symbols_by_file,
)
from fissionpy.common.paths import file_path_to_module_path, find_project_root
from fissionpy.extraction.extractor import (
    ExtractionResult,
    extract_module,
    remove_symbols_from_source,
)
from fissionpy.extraction.imports import (
    build_module_imports,
    cache_original_source,
    compute_required_imports,
    update_imports_in_source,
)
from fissionpy.extraction.planner import validate_plan
from fissionpy.extraction.progress import (
    get_progress_summary,
    init_progress,
    is_module_complete,
    mark_extracted,
    mark_extracting,
    mark_failed,
)


def _load_plan(plan_file: str) -> dict:
    yaml = YAML()
    with open(plan_file, encoding="utf-8") as f:
        return dict(yaml.load(f))


def _check_circular_deps(modules: list[dict], target_file_symbols: dict) -> list[str]:
    warnings: list[str] = []
    return warnings


def run_extract(
    plan_file: str,
    db: str,
    resume: bool,
    verbose: bool,
) -> None:
    start_time = time.time()
    plan = _load_plan(plan_file)

    conn = get_connection(db)
    try:
        errors = validate_plan(plan, conn)
        if errors:
            for err in errors:
                typer.echo(f"校验错误: {err}", err=True)
            raise typer.Exit(code=1)

        project_root = plan.get("project_root", "")
        target_file = plan.get("target_file", "")

        if project_root:
            abs_target = str(project_root) + "/" + str(target_file)
        else:
            abs_target = str(target_file)

        target_row = get_file_by_path(conn, abs_target)
        if target_row is None:
            target_row = get_file_by_path(conn, str(target_file))
        if target_row is None:
            typer.echo(f"目标文件未索引: {target_file}", err=True)
            raise typer.Exit(code=1)

        target_file_id = target_row["id"]

        init_progress(conn, plan)

        source_code = open(abs_target, encoding="utf-8").read()
        cache_original_source(abs_target, source_code)

        modules = plan.get("modules", [])
        total_modules = len(modules)
        success_count = 0
        fail_count = 0

        replacements: dict[str, str] = {}
        all_moved_symbols: set[str] = set()

        if project_root:
            target_module_path = file_path_to_module_path(abs_target, project_root)
        else:
            target_module_path = str(target_file).replace(".py", "").replace("/", ".")

        for i, mod in enumerate(modules):
            module_name = str(mod.get("name", ""))
            symbol_names = [str(s) for s in mod.get("symbols", [])]
            all_moved_symbols.update(symbol_names)

            if verbose:
                typer.echo(f"  提取模块 [{i+1}/{total_modules}]: {module_name} ({', '.join(symbol_names)})")

            for sym_name in symbol_names:
                sym_row = conn.execute(
                    "SELECT id FROM symbols WHERE file_id = ? AND name = ? LIMIT 1",
                    (target_file_id, sym_name),
                ).fetchone()
                if sym_row is not None:
                    mark_extracting(conn, sym_row["id"], module_name)

            required_imports = []
            has_future = False
            try:
                import libcst as cst
                orig_mod = cst.parse_module(source_code)
                for stmt in orig_mod.body:
                    if isinstance(stmt, cst.SimpleStatementLine):
                        for node in stmt.body:
                            if (isinstance(node, cst.ImportFrom)
                                    and node.module is not None):
                                from fissionpy.extraction.imports import _cst_dotted_name
                                mp = _cst_dotted_name(node.module)
                                if mp == "__future__" and not isinstance(node.names, cst.ImportStar) and node.names:
                                    if any(a.name.value == "annotations" for a in node.names):
                                        has_future = True
            except Exception:
                pass

            if has_future:
                required_imports.append("from __future__ import annotations")

            required_imports.extend(
                compute_required_imports(source_code, symbol_names, conn, target_file_id)
            )

            result: ExtractionResult = extract_module(
                abs_target, module_name, symbol_names, project_root, required_imports
            )

            if result.success:
                for sym_name in symbol_names:
                    sym_row = conn.execute(
                        "SELECT id FROM symbols WHERE file_id = ? AND name = ? LIMIT 1",
                        (target_file_id, sym_name),
                    ).fetchone()
                    if sym_row is not None:
                        mark_extracted(conn, sym_row["id"], module_name)

                if project_root:
                    new_module_path = f"{target_module_path}/{module_name}"
                else:
                    new_module_path = f"{target_module_path}.{module_name}"
                replacements[target_module_path] = new_module_path

                success_count += 1
                if verbose:
                    typer.echo(f"    ✓ 写入: {result.output_path}")
            else:
                for sym_name in symbol_names:
                    sym_row = conn.execute(
                        "SELECT id FROM symbols WHERE file_id = ? AND name = ? LIMIT 1",
                        (target_file_id, sym_name),
                    ).fetchone()
                    if sym_row is not None:
                        mark_failed(conn, sym_row["id"], module_name)

                fail_count += 1
                for err in result.errors:
                    typer.echo(f"    ✗ {err}", err=True)

        summary = get_progress_summary(conn)
        elapsed = time.time() - start_time

        typer.echo(
            f"\n提取完成: {success_count}/{total_modules} 模块成功, "
            f"{fail_count} 失败 | "
            f"进度: {summary.get('extracted', 0)}/{summary.get('total', 0)} 符号"
        )
        typer.echo(f"耗时: {elapsed:.2f}s")

    finally:
        conn.close()
