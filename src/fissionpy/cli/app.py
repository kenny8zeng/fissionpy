"""fissionpy CLI——Python 工程目录裂变迁移工具。

Copyright (c) 2025 FissionPy Contributors
Licensed under the MIT License
"""

import typer

app = typer.Typer(
    name="fission",
    help="Python 工程目录裂变迁移工具——基于 LibCST 的无损代码拆分与迁移",
    no_args_is_help=True,
)


@app.command()
def analyze(
    directory: str = typer.Argument(help="Python 工程目录路径"),
    db: str = typer.Option("./.fission/fission.db", "--db", help="SQLite 数据库路径"),
    exclude: list[str] = typer.Option([], "--exclude", help="追加排除目录模式"),
    force: bool = typer.Option(False, "--force", help="强制重新解析所有文件"),
    verbose: bool = typer.Option(False, "--verbose", help="详细输出"),
):
    """分析工程目录，索引所有文件和符号到 SQLite。"""
    from fissionpy.cli.analyze_cmd import run_analyze
    run_analyze(directory, db, exclude, force, verbose)


@app.command()
def show(
    file: str = typer.Option(None, "--file", help="查看指定文件的顶层符号列表"),
    symbol: str = typer.Option(None, "--symbol", help="查看指定符号的详情"),
    db: str = typer.Option("./.fission/fission.db", "--db", help="SQLite 数据库路径"),
    verbose: bool = typer.Option(False, "--verbose", help="详细输出"),
):
    """浏览符号信息——文件符号列表、符号详情、依赖关系。"""
    from fissionpy.cli.show_cmd import run_show
    run_show(file, symbol, db, verbose)


@app.command()
def tree(
    file: str = typer.Option(..., "--file", help="目标文件路径"),
    symbol: str = typer.Option(None, "--symbol", help="仅展示指定符号的子树"),
    reverse: bool = typer.Option(False, "--reverse", help="反向视图：谁依赖了该符号"),
    db: str = typer.Option("./.fission/fission.db", "--db", help="SQLite 数据库路径"),
    verbose: bool = typer.Option(False, "--verbose", help="详细输出"),
):
    """打印指定文件的符号依赖树。"""
    from fissionpy.cli.tree_cmd import run_tree
    run_tree(file, symbol, reverse, db, verbose)


@app.command()
def plan(
    target: str = typer.Option(..., "--target", help="要拆分的目标文件路径"),
    db: str = typer.Option("./.fission/fission.db", "--db", help="SQLite 数据库路径"),
    output: str = typer.Option("./fission-plan.yaml", "--output", help="YAML 输出路径"),
    verbose: bool = typer.Option(False, "--verbose", help="详细输出"),
):
    """为目标文件生成 YAML 迁移计划模板。"""
    from fissionpy.cli.plan_cmd import run_plan
    run_plan(target, db, output, verbose)


@app.command()
def extract(
    plan_file: str = typer.Argument(help="YAML 迁移计划文件路径"),
    db: str = typer.Option("./.fission/fission.db", "--db", help="SQLite 数据库路径"),
    resume: bool = typer.Option(False, "--resume", help="从上次中断处继续提取"),
    verbose: bool = typer.Option(False, "--verbose", help="详细输出"),
):
    """执行代码提取——按计划将符号无损提取到新模块文件。"""
    from fissionpy.cli.extract_cmd import run_extract
    run_extract(plan_file, db, resume, verbose)


@app.command()
def migrate(
    plan_file: str = typer.Argument(help="YAML 迁移计划文件路径"),
    db: str = typer.Option("./.fission/fission.db", "--db", help="SQLite 数据库路径"),
    no_reexport: bool = typer.Option(False, "--no-reexport", help="不在原文件生成重导出 import"),
    resume: bool = typer.Option(False, "--resume", help="从上次中断处继续迁移"),
    verbose: bool = typer.Option(False, "--verbose", help="详细输出"),
):
    """完成项目级迁移——更新全项目 import 引用 + 备份重组 + 校验。"""
    from fissionpy.cli.migrate_cmd import run_migrate
    run_migrate(plan_file, db, no_reexport, resume, verbose)


def _version(value: bool):
    if value:
        typer.echo("fission 0.2.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="显示版本号"),
):
    pass
