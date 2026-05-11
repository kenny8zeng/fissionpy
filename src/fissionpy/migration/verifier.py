"""Final consistency verification after migration."""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import libcst as cst


@dataclasses.dataclass
class VerificationResult:
    """Aggregated result of all post-migration verification checks."""

    symbol_integrity_passed: bool
    format_lossless_passed: bool
    import_reachability_passed: bool
    errors: list[str]
    warnings: list[str]


def _extract_symbol_text_with_libcst(source: str, symbol_name: str) -> str:
    """Extract the source text of a top-level symbol definition using LibCST."""
    module = cst.parse_module(source)
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef) and stmt.name.value == symbol_name:
            return cst.Module(body=[stmt.with_changes(leading_lines=[])]).code
        if isinstance(stmt, cst.ClassDef) and stmt.name.value == symbol_name:
            return cst.Module(body=[stmt.with_changes(leading_lines=[])]).code
        if isinstance(stmt, cst.SimpleStatementLine):
            for node in stmt.body:
                if isinstance(node, cst.Assign) and node.targets:
                    for target in node.targets:
                        if (
                            isinstance(target.target, cst.Name)
                            and target.target.value == symbol_name
                        ):
                            return cst.Module(
                                body=[stmt.with_changes(leading_lines=[])]
                            ).code
                if isinstance(node, cst.AnnAssign) and node.target:
                    if (
                        isinstance(node.target, cst.Name)
                        and node.target.value == symbol_name
                    ):
                        return cst.Module(
                            body=[stmt.with_changes(leading_lines=[])]
                        ).code
    return ""


def verify_symbol_integrity(
    original_symbols: list[dict],
    plan: dict,
    project_root: str,
) -> tuple[bool, list[str]]:
    """Verify all original symbols exist in their expected locations after migration."""
    errors: list[str] = []
    root = pathlib.Path(project_root)

    for module in plan.get("modules", []):
        module_name = module.get("name", "")
        symbol_names = module.get("symbols", [])
        target_file = plan.get("target_file", "")
        module_file = root / pathlib.Path(target_file).parent / f"{module_name}.py"

        if not module_file.exists():
            errors.append(f"模块文件不存在: {module_file}")
            continue

        try:
            source = module_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            errors.append(f"无法解析模块文件 {module_file}: {exc}")
            continue

        defined_names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined_names.add(node.target.id)

        for sym_name in symbol_names:
            if sym_name not in defined_names:
                errors.append(f"符号 '{sym_name}' 未在模块文件 {module_file} 中找到")

    for sym_name in plan.get("retain", []):
        target_file = plan.get("target_file", "")
        reorganized_file = root / target_file

        if not reorganized_file.exists():
            errors.append(f"重组目标文件不存在: {reorganized_file}")
            continue

        try:
            source = reorganized_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            errors.append(f"无法解析重组目标文件 {reorganized_file}: {exc}")
            continue

        defined_names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined_names.add(node.target.id)

        if sym_name not in defined_names:
            errors.append(f"保留符号 '{sym_name}' 未在重组目标文件 {reorganized_file} 中找到")

    return len(errors) == 0, errors


def verify_format_lossless(
    target_file: str,
    backup_path: str,
    plan: dict,
    project_root: str,
) -> tuple[bool, list[str]]:
    """Verify extracted symbol code matches the original character-by-character."""
    errors: list[str] = []
    root = pathlib.Path(project_root)

    try:
        backup_source = pathlib.Path(backup_path).read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"无法读取备份文件 {backup_path}: {exc}")
        return False, errors

    for module in plan.get("modules", []):
        module_name = module.get("name", "")
        symbol_names = module.get("symbols", [])
        plan_target = plan.get("target_file", "")
        module_file = root / pathlib.Path(plan_target).parent / f"{module_name}.py"

        if not module_file.exists():
            errors.append(f"模块文件不存在: {module_file}")
            continue

        try:
            module_source = module_file.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"无法读取模块文件 {module_file}: {exc}")
            continue

        for sym_name in symbol_names:
            original_text = _extract_symbol_text_with_libcst(backup_source, sym_name)
            if not original_text:
                errors.append(f"无法从备份文件提取符号 '{sym_name}' 的源码")
                continue

            new_text = _extract_symbol_text_with_libcst(module_source, sym_name)
            if not new_text:
                errors.append(f"无法从模块文件 {module_file} 提取符号 '{sym_name}' 的源码")
                continue

            if original_text != new_text:
                errors.append(
                    f"符号 '{sym_name}' 格式不一致: 备份与提取结果逐字符比对失败"
                )

    return len(errors) == 0, errors


def verify_import_reachability(
    project_root: str,
    plan: dict,
) -> tuple[bool, list[str], list[str]]:
    """Verify all import statements in the plan resolve to valid existing files."""
    errors: list[str] = []
    warnings: list[str] = []
    root = pathlib.Path(project_root)

    for module in plan.get("modules", []):
        module_name = module.get("name", "")
        plan_target = plan.get("target_file", "")
        module_file = root / pathlib.Path(plan_target).parent / f"{module_name}.py"

        if not module_file.exists():
            errors.append(f"模块文件不存在: {module_file}")

    for impact in plan.get("import_impact", []):
        new_import = impact.get("new_import", "")
        if not new_import:
            continue

        parts = new_import.split()
        module_part = ""
        if len(parts) >= 2 and parts[0] == "from":
            module_part = parts[1]

        if not module_part:
            warnings.append(f"无法解析 import 语句: '{new_import}'")
            continue

        module_path = module_part.replace(".", "/")
        expected_file = root / f"{module_path}.py"

        if not expected_file.exists():
            errors.append(f"import 目标文件不存在: {expected_file} (from '{new_import}')")
            continue

        rel_to_root = expected_file.relative_to(root) if expected_file.is_relative_to(root) else None
        if rel_to_root is not None:
            current = expected_file.parent
            while True:
                try:
                    current.relative_to(root)
                except ValueError:
                    break
                if current == root:
                    break
                init_file = current / "__init__.py"
                if not init_file.exists():
                    warnings.append(f"中间目录缺少 __init__.py: {current}")
                current = current.parent

    return len(errors) == 0, errors, warnings


def run_full_verification(
    target_file: str,
    backup_path: str,
    original_symbols: list[dict],
    plan: dict,
    project_root: str,
) -> VerificationResult:
    """Run all verification checks and aggregate results."""
    si_passed, si_errors = verify_symbol_integrity(
        original_symbols, plan, project_root,
    )

    fl_passed, fl_errors = verify_format_lossless(
        target_file, backup_path, plan, project_root,
    )

    ir_passed, ir_errors, ir_warnings = verify_import_reachability(
        project_root, plan,
    )

    all_errors = si_errors + fl_errors + ir_errors
    all_warnings = ir_warnings

    return VerificationResult(
        symbol_integrity_passed=si_passed,
        format_lossless_passed=fl_passed,
        import_reachability_passed=ir_passed,
        errors=all_errors,
        warnings=all_warnings,
    )
