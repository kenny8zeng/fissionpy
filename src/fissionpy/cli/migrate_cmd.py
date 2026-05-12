"""fission migrate <plan> command implementation."""

from __future__ import annotations

import time

import typer
from ruamel.yaml import YAML

from fissionpy.analysis.database import (
    get_connection,
    get_file_by_path,
    get_symbols_by_file,
)
from fissionpy.common.paths import file_path_to_module_path, normalize_path
from fissionpy.extraction.planner import validate_plan
from fissionpy.extraction.progress import get_progress_summary
from fissionpy.migration.propagator import (
    compute_affected_files,
    propagate_import_updates,
    record_import_updates,
)
from fissionpy.migration.reorganizer import (
    backup_file,
    ensure_init_files,
    reorganize_target_file,
)
from fissionpy.migration.verifier import run_full_verification


def _load_plan(plan_file: str) -> dict:
    yaml = YAML()
    with open(plan_file, encoding="utf-8") as f:
        return dict(yaml.load(f))


def run_migrate(
    plan_file: str,
    db: str,
    no_reexport: bool,
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

        summary = get_progress_summary(conn)
        extracted = summary.get("extracted", 0)
        total = summary.get("total", 0)
        if total > 0 and extracted < total:
            typer.echo(f"提取未完成: {extracted}/{total} 符号已提取，请先运行 fission extract", err=True)
            raise typer.Exit(code=1)

        project_root = str(plan.get("project_root", ""))
        target_file = str(plan.get("target_file", ""))
        normalized_target = normalize_path(target_file)

        if project_root:
            abs_target = project_root + "/" + normalized_target
        else:
            abs_target = normalized_target

        target_row = get_file_by_path(conn, abs_target)
        if target_row is None:
            target_row = get_file_by_path(conn, normalized_target)
        if target_row is None:
            target_row = get_file_by_path(conn, target_file)
        if target_row is None:
            typer.echo(f"目标文件未索引: {target_file}", err=True)
            raise typer.Exit(code=1)

        original_symbols = get_symbols_by_file(conn, target_row["id"])

        modules = plan.get("modules", [])
        if not modules:
            typer.echo("无模块需要迁移")
            raise typer.Exit(code=0)

        all_moved_symbols: set[str] = set()
        replacements: dict[str, str] = {}
        if project_root:
            target_module_path = file_path_to_module_path(abs_target, project_root)
        else:
            target_module_path = target_file.replace(".py", "").replace("/", ".")

        for mod in modules:
            module_name = str(mod.get("name", ""))
            for sym_name in mod.get("symbols", []):
                all_moved_symbols.add(str(sym_name))
            if project_root:
                if "/" in target_module_path:
                    parent_path = "/".join(target_module_path.split("/")[:-1])
                    new_module_path = f"{parent_path}/{module_name}"
                else:
                    new_module_path = module_name
            else:
                new_module_path = f"{target_module_path}.{module_name}"
            replacements[target_module_path] = new_module_path

        typer.echo("步骤 1: 传播 import 更新")
        affected_files = compute_affected_files(conn, plan)
        if verbose:
            for af in affected_files:
                typer.echo(f"  受影响文件: {af}")

        update_results = propagate_import_updates(affected_files, replacements, all_moved_symbols)
        updated_count = sum(1 for v in update_results.values() if v == "updated")
        typer.echo(f"  更新 {updated_count}/{len(affected_files)} 个文件")

        record_import_updates(conn, update_results, replacements, all_moved_symbols)

        typer.echo("步骤 2: 备份目标文件")
        backup_path = backup_file(abs_target)
        if verbose:
            typer.echo(f"  备份: {backup_path}")

        typer.echo("步骤 3: 重组目标文件")
        reorganize_target_file(abs_target, plan, project_root, no_reexport=no_reexport)

        typer.echo("步骤 4: 确保 __init__.py 存在")
        created_inits = ensure_init_files(abs_target, plan)
        if created_inits and verbose:
            for init_path in created_inits:
                typer.echo(f"  创建: {init_path}")

        typer.echo("步骤 5: 一致性校验")
        result = run_full_verification(
            abs_target, backup_path, original_symbols, plan, project_root
        )

        if result.symbol_integrity_passed:
            typer.echo("  ✓ 符号完整性")
        else:
            typer.echo("  ✗ 符号完整性", err=True)
            for err in result.errors:
                typer.echo(f"    {err}", err=True)

        if result.format_lossless_passed:
            typer.echo("  ✓ 格式无损性")
        else:
            typer.echo("  ✗ 格式无损性", err=True)
            for err in result.errors:
                typer.echo(f"    {err}", err=True)

        if result.import_reachability_passed:
            typer.echo("  ✓ import 可达性")
        else:
            typer.echo("  ✗ import 可达性", err=True)
            for err in result.errors:
                typer.echo(f"    {err}", err=True)

        for warn in result.warnings:
            typer.echo(f"  ⚠ {warn}")

        elapsed = time.time() - start_time
        all_passed = (
            result.symbol_integrity_passed
            and result.format_lossless_passed
            and result.import_reachability_passed
        )

        if all_passed:
            typer.echo(f"\n迁移完成 ✓ ({elapsed:.2f}s)")
        else:
            typer.echo(f"\n迁移完成 (有错误) ✗ ({elapsed:.2f}s)")

    finally:
        conn.close()
