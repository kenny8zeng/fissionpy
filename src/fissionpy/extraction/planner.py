"""YAML migration plan generation, validation, and import impact computation."""

from __future__ import annotations

import keyword
from pathlib import Path

from ruamel.yaml import YAML

from fissionpy.analysis.database import (
    get_dependencies_by_file,
    get_file_by_path,
    get_files_importing_symbol,
    get_symbols_by_file,
)
from fissionpy.common.paths import (
    file_path_to_module_path,
    find_project_root,
    module_path_to_python_import,
    normalize_path,
)


def _resolve_target_file(conn, target_file: str) -> tuple[int, str, str | None]:
    """Resolve target_file to (file_id, absolute_path, project_root).

    Tries normalized path first (./ prefix removed), then absolute path.
    """
    normalized = normalize_path(target_file)
    file_row = get_file_by_path(conn, normalized)
    if file_row is not None:
        project_root = find_project_root(file_row["path"])
        return file_row["id"], file_row["path"], project_root

    abs_path = str(Path(normalized).resolve())
    file_row = get_file_by_path(conn, abs_path)
    if file_row is not None:
        project_root = find_project_root(abs_path)
        return file_row["id"], abs_path, project_root

    file_row = get_file_by_path(conn, target_file)
    if file_row is not None:
        project_root = find_project_root(file_row["path"])
        return file_row["id"], file_row["path"], project_root

    raise FileNotFoundError(f"文件未索引: {target_file}")


def _connected_components(adj: dict[str, set[str]]) -> list[set[str]]:
    """Find connected components via BFS on the adjacency graph."""
    visited: set[str] = set()
    components: list[set[str]] = []

    for node in adj:
        if node in visited:
            continue
        component: set[str] = set()
        queue = [node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in adj[current]:
                if neighbor not in visited:
                    queue.append(neighbor)
        components.append(component)

    return components


def _build_symbol_adjacency(
    symbol_names: set[str],
    dependencies: list[dict],
    symbol_id_to_name: dict[int, str],
) -> dict[str, set[str]]:
    """Build undirected adjacency graph from intra-file dependency records."""
    adj: dict[str, set[str]] = {name: set() for name in symbol_names}
    for dep in dependencies:
        if dep.get("cross_file", 0):
            continue
        src_name = symbol_id_to_name.get(dep["source_id"])
        tgt_name = symbol_id_to_name.get(dep["target_id"])
        if src_name is None or tgt_name is None:
            continue
        if src_name in adj and tgt_name in adj:
            adj[src_name].add(tgt_name)
            adj[tgt_name].add(src_name)
    return adj


def generate_plan(conn, target_file: str) -> dict:
    """Generate a YAML migration plan dict for the target file.

    Resolves the file in the DB, gathers symbols/imports/dependencies,
    computes connected components for module grouping, and calculates
    import impact on other files.
    """
    file_id, abs_path, project_root = _resolve_target_file(conn, target_file)

    symbols = get_symbols_by_file(conn, file_id)
    dependencies = get_dependencies_by_file(conn, file_id)

    symbol_names = {sym["name"] for sym in symbols}
    symbol_id_to_name: dict[int, str] = {sym["id"]: sym["name"] for sym in symbols}

    adj = _build_symbol_adjacency(symbol_names, dependencies, symbol_id_to_name)
    components = _connected_components(adj)

    modules: list[dict] = []
    retain: list[str] = []

    for i, component in enumerate(components):
        if len(component) == 1:
            single_name = next(iter(component))
            if not adj[single_name]:
                retain.append(single_name)
                continue

        module_name = f"module_{i + 1}"
        modules.append({
            "name": module_name,
            "symbols": sorted(component),
        })

    all_assigned: set[str] = set()
    for mod in modules:
        all_assigned.update(mod["symbols"])

    import_impact = _compute_import_impact(
        conn, file_id, all_assigned, abs_path, project_root, modules,
    )

    if project_root is not None:
        rel_path = str(Path(abs_path).relative_to(project_root))
    else:
        rel_path = target_file

    plan = {
        "project_root": project_root or "",
        "target_file": rel_path,
        "modules": modules,
        "retain": sorted(retain),
        "import_impact": import_impact,
    }

    return plan


def _compute_import_impact(
    conn,
    target_file_id: int,
    symbol_names: set[str],
    target_abs_path: str,
    project_root: str | None,
    modules: list[dict],
) -> list[dict]:
    """Compute import impact on files that import symbols being moved.

    For each affected file, generates old/new import pairs.
    """
    if project_root is None:
        return []

    target_module_path = file_path_to_module_path(target_abs_path, project_root)
    target_python_import = module_path_to_python_import(target_module_path)

    symbol_to_module: dict[str, str] = {}
    for mod in modules:
        for sym_name in mod["symbols"]:
            symbol_to_module[sym_name] = mod["name"]

    impacts: list[dict] = []
    seen_files: set[str] = set()

    for sym_name in sorted(symbol_names):
        importing_rows = get_files_importing_symbol(conn, sym_name, target_file_id)
        mod_name = symbol_to_module.get(sym_name)
        if mod_name is None:
            continue

        new_module_path = f"{target_module_path}/{mod_name}"
        if "/" in target_module_path:
            parent_path = "/".join(target_module_path.split("/")[:-1])
            new_module_path = f"{parent_path}/{mod_name}"
        else:
            new_module_path = mod_name
        new_python_import = module_path_to_python_import(new_module_path)

        for row in importing_rows:
            affected_file = row.get("source_file_path", "")
            if not affected_file:
                continue

            key = (affected_file, sym_name)
            if key in seen_files:
                continue
            seen_files.add(key)

            impacts.append({
                "file": affected_file,
                "old_import": f"from {target_python_import} import {sym_name}",
                "new_import": f"from {new_python_import} import {sym_name}",
            })

    return impacts


def validate_plan(plan: dict, conn) -> list[str]:
    """Validate a migration plan dict, returning a list of error strings."""
    errors: list[str] = []

    target_file = plan.get("target_file", "")
    project_root = plan.get("project_root", "")

    if not target_file:
        errors.append("target_file 为空")

    abs_target = target_file
    if project_root:
        abs_target = str(Path(project_root) / target_file)

    file_row = get_file_by_path(conn, abs_target)
    if file_row is None:
        file_row = get_file_by_path(conn, target_file)
    if file_row is None:
        errors.append(f"目标文件未索引: {target_file}")
        return errors

    file_id: int = file_row["id"]
    db_symbols = get_symbols_by_file(conn, file_id)
    db_symbol_names = {sym["name"] for sym in db_symbols}

    all_plan_symbols: set[str] = set()
    for mod in plan.get("modules", []):
        mod_name = mod.get("name", "")
        if not _is_valid_module_name(mod_name):
            errors.append(f"无效模块名: '{mod_name}' (必须是合法 Python 标识符，可含 / 表示子目录)")

        for sym_name in mod.get("symbols", []):
            if sym_name in all_plan_symbols:
                errors.append(f"重复符号: '{sym_name}' 出现在多个模块中")
            all_plan_symbols.add(sym_name)

            if sym_name not in db_symbol_names:
                errors.append(f"符号不存在于目标文件: '{sym_name}'")

    for sym_name in plan.get("retain", []):
        if sym_name in all_plan_symbols:
            errors.append(f"重复符号: '{sym_name}' 同时在模块和 retain 中")
        all_plan_symbols.add(sym_name)

        if sym_name not in db_symbol_names:
            errors.append(f"符号不存在于目标文件: '{sym_name}'")

    return errors


def _is_valid_module_name(name: str) -> bool:
    """Check if a module name is a valid Python identifier, allowing '/' for subdirs."""
    if not name:
        return False
    parts = name.split("/")
    for part in parts:
        if not part:
            return False
        if part.isidentifier() and not keyword.iskeyword(part):
            continue
        return False
    return True


def write_plan_yaml(plan: dict, output_path: str) -> None:
    """Write the plan dict to a YAML file with a header comment."""
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        f.write("# fission migration plan - edit modules/symbols before running extract\n")

    with open(output, "a", encoding="utf-8") as f:
        yaml.dump(plan, f)
