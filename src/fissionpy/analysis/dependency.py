"""Intra-file dependency analysis using LibCST ScopeProvider."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import libcst as cst
import libcst.metadata as cst_meta


@dataclasses.dataclass
class Dependency:
    """A dependency relationship between two top-level symbols in the same file."""

    source_name: str
    target_name: str
    dep_type: str


def _name_from_node(node: cst.BaseExpression) -> str | None:
    """Extract a simple name string from a CST expression node."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        if isinstance(node.value, cst.Name):
            return node.value.value
    return None


def _collect_names_from_annotation(node: cst.Annotation | cst.BaseExpression) -> set[str]:
    """Recursively collect all Name references from a type annotation."""
    names: set[str] = set()

    def _walk(expr: cst.BaseExpression) -> None:
        if isinstance(expr, cst.Name):
            names.add(expr.value)
        elif isinstance(expr, cst.Attribute):
            if isinstance(expr.value, cst.Name):
                names.add(expr.value.value)
        elif isinstance(expr, cst.Subscript):
            _walk(expr.value)
            for element in expr.slice:
                if isinstance(element, cst.SubscriptElement):
                    sl = element.slice
                    if isinstance(sl, cst.Index):
                        _walk(sl.value)
        elif isinstance(expr, cst.BinaryOperation):
            _walk(expr.left)
            _walk(expr.right)

    target = node.annotation if isinstance(node, cst.Annotation) else node
    _walk(target)
    return names


def _find_global_scope(scopes: dict[cst.CSTNode, cst_meta.Scope]) -> cst_meta.GlobalScope | None:
    """Locate the GlobalScope from the resolved scope map."""
    for scope in scopes.values():
        if isinstance(scope, cst_meta.GlobalScope):
            return scope
    return None


def _collect_param_annotations(func: cst.FunctionDef) -> set[str]:
    """Collect all name references from a function's parameter annotations."""
    names: set[str] = set()
    params = func.params
    for param in params.params:
        if param.annotation is not None:
            names |= _collect_names_from_annotation(param.annotation)
    for param in params.kwonly_params:
        if param.annotation is not None:
            names |= _collect_names_from_annotation(param.annotation)
    for param in params.posonly_params:
        if param.annotation is not None:
            names |= _collect_names_from_annotation(param.annotation)
    if isinstance(params.star_arg, cst.Param) and params.star_arg.annotation is not None:
        names |= _collect_names_from_annotation(params.star_arg.annotation)
    if params.star_kwarg is not None and params.star_kwarg.annotation is not None:
        names |= _collect_names_from_annotation(params.star_kwarg.annotation)
    return names


def _build_func_scope_map(
    global_scope: cst_meta.GlobalScope,
    scopes: dict[cst.CSTNode, cst_meta.Scope],
) -> dict[int, str]:
    """Map FunctionScope/ClassScope id to the function/class name.

    Uses the fact that FunctionDef.params maps to its FunctionScope
    in the scopes dict, and the assignment node carries the name.
    """
    result: dict[int, str] = {}
    for a in global_scope.assignments:
        if isinstance(a.node, cst.FunctionDef):
            params_scope = scopes.get(a.node.params)
            if params_scope is not None:
                result[id(params_scope)] = a.name
        elif isinstance(a.node, cst.ClassDef):
            body = a.node.body
            children = body if isinstance(body, list) else getattr(body, 'body', [])
            for child in children:
                child_scope = scopes.get(child)
                if child_scope is not None and isinstance(child_scope, cst_meta.ClassScope):
                    result[id(child_scope)] = a.name
                    break
    return result


def _resolve_source_name(
    scope: cst_meta.Scope,
    func_scope_map: dict[int, str],
    global_scope: cst_meta.GlobalScope,
) -> str | None:
    """Walk up from a scope to find the owning top-level function/class name."""
    current = scope
    while current is not None and not isinstance(current, cst_meta.GlobalScope):
        name = func_scope_map.get(id(current))
        if name is not None:
            return name
        current = getattr(current, 'parent', None)
    return None


def analyze_dependencies(source_code: str, top_level_names: set[str]) -> list[Dependency]:
    """Analyze intra-file dependencies between top-level symbols.

    Phase 1: Direct AST traversal for decorators, base classes, and annotations.
    Phase 2: Scope-based access resolution for calls and references.
    """
    module = cst.parse_module(source_code)
    wrapper = cst_meta.MetadataWrapper(module)
    scopes = wrapper.resolve(cst_meta.ScopeProvider)

    global_scope = _find_global_scope(scopes)
    if global_scope is None:
        return []

    deps: set[tuple[str, str, str]] = set()

    for stmt in module.body:
        source_name: str | None = None

        if isinstance(stmt, cst.FunctionDef):
            source_name = stmt.name.value
            for decorator in stmt.decorators:
                name = _name_from_node(decorator.decorator)
                if name and name in top_level_names:
                    deps.add((source_name, name, "decorator"))
            if stmt.returns is not None:
                for ann_name in _collect_names_from_annotation(stmt.returns):
                    if ann_name in top_level_names:
                        deps.add((source_name, ann_name, "annotation"))
            for ann_name in _collect_param_annotations(stmt):
                if ann_name in top_level_names:
                    deps.add((source_name, ann_name, "annotation"))

        elif isinstance(stmt, cst.ClassDef):
            source_name = stmt.name.value
            for decorator in stmt.decorators:
                name = _name_from_node(decorator.decorator)
                if name and name in top_level_names:
                    deps.add((source_name, name, "decorator"))
            for base in stmt.bases:
                name = _name_from_node(base.value)
                if name and name in top_level_names:
                    deps.add((source_name, name, "inherit"))
                if isinstance(base.value, cst.Call) and isinstance(base.value.func, cst.Name):
                    if base.value.func.value in top_level_names:
                        deps.add((source_name, base.value.func.value, "inherit"))

        elif isinstance(stmt, cst.SimpleStatementLine):
            for node in stmt.body:
                if isinstance(node, cst.AnnAssign) and isinstance(node.target, cst.Name):
                    source_name = node.target.value
                    if node.annotation is not None:
                        for ann_name in _collect_names_from_annotation(node.annotation):
                            if ann_name in top_level_names:
                                deps.add((source_name, ann_name, "annotation"))

    func_scope_map = _build_func_scope_map(global_scope, scopes)

    for a in global_scope.assignments:
        target_name = a.name
        if target_name not in top_level_names:
            continue
        for ref in a.references:
            source_name = _resolve_source_name(ref.scope, func_scope_map, global_scope)
            if source_name is None or source_name == target_name:
                continue
            if (source_name, target_name, "decorator") in deps:
                continue
            if (source_name, target_name, "inherit") in deps:
                continue
            if (source_name, target_name, "annotation") in deps:
                continue
            if ref.is_type_hint or ref.is_annotation:
                deps.add((source_name, target_name, "annotation"))
            else:
                deps.add((source_name, target_name, "call"))

    return [
        Dependency(source_name=s, target_name=t, dep_type=d)
        for s, t, d in sorted(deps)
    ]


def analyze_file_dependencies(file_path: str, top_level_names: set[str]) -> list[Dependency]:
    """Read a Python file and analyze its intra-file dependencies."""
    source = Path(file_path).read_text(encoding="utf-8")
    return analyze_dependencies(source, top_level_names)
