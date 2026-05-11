"""fission plan command implementation."""

from __future__ import annotations

import typer

from fissionpy.analysis.database import get_connection
from fissionpy.extraction.planner import (
    generate_plan,
    validate_plan,
    write_plan_yaml,
)


def run_plan(
    target: str,
    db: str,
    output: str,
    verbose: bool,
) -> None:
    """Generate a YAML migration plan for the target file."""
    conn = get_connection(db)
    try:
        plan = generate_plan(conn, target)

        errors = validate_plan(plan, conn)
        if errors:
            for err in errors:
                typer.echo(f"校验错误: {err}", err=True)

        write_plan_yaml(plan, output)

        n_symbols = sum(len(m.get("symbols", [])) for m in plan.get("modules", []))
        n_symbols += len(plan.get("retain", []))
        n_modules = len(plan.get("modules", []))
        n_impacts = len(plan.get("import_impact", []))

        typer.echo(f"目标文件: {plan['target_file']}")
        typer.echo(f"符号: {n_symbols}, 模块: {n_modules}, import 影响: {n_impacts}")
        typer.echo(f"计划已写入: {output}")

        if verbose:
            for mod in plan.get("modules", []):
                symbols_str = ", ".join(mod["symbols"])
                typer.echo(f"  {mod['name']}: {symbols_str}")
            if plan.get("retain"):
                typer.echo(f"  retain: {', '.join(plan['retain'])}")
            if plan.get("import_impact"):
                typer.echo("  import 影响:")
                for impact in plan["import_impact"]:
                    typer.echo(f"    {impact['file']}: {impact['old_import']} → {impact['new_import']}")
    finally:
        conn.close()
