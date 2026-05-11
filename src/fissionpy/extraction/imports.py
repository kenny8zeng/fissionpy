"""Metadata-driven import computation and CSTTransformer-based import updates."""

from __future__ import annotations

import dataclasses

import libcst as cst
from libcst import MaybeSentinel


def dotted_name_to_cst(dotted: str) -> cst.Attribute | cst.Name:
    """Convert a dotted or slash-separated name string to a libcst Attribute chain.

    'a.b.c' → cst.Attribute(cst.Attribute(cst.Name('a'), cst.Name('b')), cst.Name('c'))
    'a/b/c' → same (slashes are converted to dots first)
    'a' → cst.Name('a')
    """
    normalized = dotted.replace("/", ".")
    parts = normalized.split(".")
    node: cst.Attribute | cst.Name = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _cst_dotted_name(node: cst.Attribute | cst.Name) -> str:
    """Reconstruct a dotted name string from a libcst Attribute chain or Name."""
    if isinstance(node, cst.Name):
        return node.value
    return f"{_cst_dotted_name(node.value)}.{node.attr.value}"


def compute_required_imports(
    source_code: str,
    symbol_names: list[str],
    db_conn=None,
    source_file_id: int = 0,
) -> list[str]:
    """Collect import statements from source_code needed by the extracted symbols.

    Walks module.body for all import statements.  An ImportFrom is kept when
    any of its imported names appear in *symbol_names* or when a DB query
    indicates the extracted symbols depend on them.  Plain ``import X``
    statements are always included.
    """
    module = cst.parse_module(source_code)
    name_set = set(symbol_names)
    result: list[str] = []

    db_dep_names: set[str] = set()
    if db_conn is not None and source_file_id:
        try:
            rows = db_conn.execute(
                """SELECT DISTINCT s2.name FROM dependencies d
                   JOIN symbols s1 ON d.source_id = s1.id
                   JOIN symbols s2 ON d.target_id = s2.id
                   WHERE s1.file_id = ? AND s1.name IN ({})""".format(
                    ",".join("?" * len(symbol_names))
                ),
                [source_file_id] + list(symbol_names),
            ).fetchall()
            db_dep_names = {r[0] for r in rows}
        except Exception:
            db_dep_names = set()

    relevant_names = name_set | db_dep_names

    for stmt in module.body:
        if isinstance(stmt, cst.SimpleStatementLine):
            for node in stmt.body:
                if isinstance(node, cst.ImportFrom):
                    _collect_import_from(node, relevant_names, result)
                elif isinstance(node, cst.Import):
                    _collect_import(node, result)

    return result


def _collect_import_from(
    node: cst.ImportFrom,
    relevant_names: set[str],
    result: list[str],
) -> None:
    """Append a 'from X import ...' string to *result* if relevant."""
    if node.module is None:
        return
    module_path = _cst_dotted_name(node.module)

    if isinstance(node.names, cst.ImportStar):
        result.append(f"from {module_path} import *")
        return

    if node.names is None:
        return

    matched: list[str] = []
    for alias in node.names:
        name = alias.name.value
        if name in relevant_names:
            matched.append(name)

    if not matched:
        return

    parts = ", ".join(matched)
    result.append(f"from {module_path} import {parts}")


def _collect_import(node: cst.Import, result: list[str]) -> None:
    """Append an 'import X' string to *result*."""
    for alias in node.names:
        dotted = _cst_dotted_name(alias.name)
        result.append(f"import {dotted}")


def build_module_imports(
    target_module_path: str,
    symbol_names: list[str],
) -> str:
    """Build the import header for a newly extracted module file.

    Includes ``from __future__ import annotations`` when the original source
    had it, followed by required external imports for the extracted symbols.
    """
    original_source = _get_original_source_for(target_module_path)
    parts: list[str] = []

    has_future = False
    if original_source:
        try:
            module = cst.parse_module(original_source)
            for stmt in module.body:
                if isinstance(stmt, cst.SimpleStatementLine):
                    for node in stmt.body:
                        if (
                            isinstance(node, cst.ImportFrom)
                            and node.module is not None
                            and _cst_dotted_name(node.module) == "__future__"
                            and not isinstance(node.names, cst.ImportStar)
                            and node.names is not None
                            and any(
                                a.name.value == "annotations"
                                for a in node.names
                            )
                        ):
                            has_future = True
        except Exception:
            pass

    required = compute_required_imports(original_source, symbol_names)

    if has_future:
        parts.append("from __future__ import annotations")

    parts.extend(required)
    return "\n".join(parts)


_original_source_cache: dict[str, str] = {}


def _get_original_source_for(target_module_path: str) -> str:
    """Retrieve cached original source for the given module path."""
    return _original_source_cache.get(target_module_path, "")


def cache_original_source(module_path: str, source_code: str) -> None:
    """Store the original source code for later import header generation."""
    _original_source_cache[module_path] = source_code


def _clean_alias_comma(alias: cst.ImportAlias, is_last: bool) -> cst.ImportAlias:
    """Set an ImportAlias's comma to DEFAULT for the last item, or keep as-is."""
    if is_last:
        return alias.with_changes(comma=MaybeSentinel.DEFAULT)
    return alias


@dataclasses.dataclass
class ImportUpdater(cst.CSTTransformer):
    """CSTTransformer that rewrites import paths during module extraction.

    *replacements* maps old_module_path → new_module_path.
    *moved_symbols* is the set of symbol names being relocated.
    """

    replacements: dict[str, str] = dataclasses.field(default_factory=dict)
    moved_symbols: set[str] = dataclasses.field(default_factory=set)
    _pending_splits: list[tuple[cst.ImportFrom, cst.ImportFrom]] = dataclasses.field(
        default_factory=list, init=False, repr=False,
    )

    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom,
    ) -> cst.ImportFrom:
        """Classify ImportFrom nodes and prepare splits if needed.

        When an ImportFrom from a replaced module has both moved and remaining
        names, the moved names are stored in *_pending_splits* and the
        remaining names are returned in-place.  The actual statement split
        is performed in *leave_SimpleStatementLine*.
        """
        if updated_node.module is None or isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        old_module_path = _cst_dotted_name(updated_node.module)
        new_module_path = self.replacements.get(old_module_path)
        if new_module_path is None:
            return updated_node

        if updated_node.names is None:
            return updated_node

        moved: list[cst.ImportAlias] = []
        remaining: list[cst.ImportAlias] = []

        for alias in updated_node.names:
            name = alias.name.value
            if name in self.moved_symbols:
                moved.append(alias)
            else:
                remaining.append(alias)

        if not moved:
            return updated_node.with_changes(
                module=dotted_name_to_cst(new_module_path),
            )

        if not remaining:
            return updated_node.with_changes(
                module=dotted_name_to_cst(new_module_path),
            )

        cleaned_remaining = [
            _clean_alias_comma(a, i == len(remaining) - 1)
            for i, a in enumerate(remaining)
        ]
        cleaned_moved = [
            _clean_alias_comma(a, i == len(moved) - 1)
            for i, a in enumerate(moved)
        ]

        keep_node = updated_node.with_changes(names=cleaned_remaining)
        moved_node = updated_node.with_changes(
            module=dotted_name_to_cst(new_module_path),
            names=cleaned_moved,
        )

        self._pending_splits.append((keep_node, moved_node))
        return keep_node

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.FlattenSentinel[cst.SimpleStatementLine]:
        """Emit pending moved-import statements as separate SimpleStatementLines."""
        if not self._pending_splits:
            return updated_node

        extras: list[cst.SimpleStatementLine] = []
        for _, moved_imp in self._pending_splits:
            extras.append(
                cst.SimpleStatementLine(
                    body=[moved_imp],
                    leading_lines=[],
                )
            )
        self._pending_splits.clear()

        return cst.FlattenSentinel([updated_node] + extras)


def update_imports_in_source(
    source_code: str,
    replacements: dict[str, str],
    moved_symbols: set[str],
) -> str:
    """Parse *source_code*, apply ImportUpdater, and return the updated source."""
    module = cst.parse_module(source_code)
    updater = ImportUpdater(replacements=replacements, moved_symbols=moved_symbols)
    new_module = module.visit(updater)
    return new_module.code
