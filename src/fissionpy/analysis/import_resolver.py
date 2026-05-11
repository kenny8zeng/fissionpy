"""LibCST-based import statement collector for fissionpy."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import libcst as cst
import libcst.metadata as cst_meta


@dataclasses.dataclass
class FileImport:
    """A single import statement extracted from a Python source file."""

    import_type: str
    module_path: str
    imported_names: list[str]
    aliases: dict[str, str]
    is_star_import: bool
    line_number: int


def _dotted_name(node: cst.Attribute | cst.Name) -> str:
    """Construct a dotted module path from a CST Attribute chain or Name."""
    if isinstance(node, cst.Name):
        return node.value
    value = _dotted_name(node.value)
    return f"{value}.{node.attr.value}"


class ImportCollector(cst.CSTVisitor):
    """CSTVisitor that collects import statements into FileImport instances."""

    METADATA_DEPENDENCIES = (cst_meta.PositionProvider,)

    def __init__(self) -> None:
        super().__init__()
        self._imports: list[FileImport] = []

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        module = _dotted_name(node.module) if node.module is not None else ""
        names: list[str] = []
        aliases: dict[str, str] = {}
        is_star = isinstance(node.names, cst.ImportStar)

        if not is_star and node.names is not None:
            for alias in node.names:
                name = alias.name.value
                names.append(name)
                if alias.asname is not None and alias.asname.name is not None:
                    aliases[name] = alias.asname.name.value

        line = self._resolve_line(node)

        self._imports.append(
            FileImport(
                import_type="from_import",
                module_path=module,
                imported_names=names,
                aliases=aliases,
                is_star_import=is_star,
                line_number=line,
            )
        )
        return True

    def visit_Import(self, node: cst.Import) -> bool:
        line = self._resolve_line(node)

        for alias in node.names:
            dotted = _dotted_name(alias.name)
            last = dotted.split(".")[-1]
            aliases: dict[str, str] = {}
            if alias.asname is not None and alias.asname.name is not None:
                aliases[last] = alias.asname.name.value

            self._imports.append(
                FileImport(
                    import_type="import",
                    module_path=dotted,
                    imported_names=[last],
                    aliases=aliases,
                    is_star_import=False,
                    line_number=line,
                )
            )
        return True

    def _resolve_line(self, node: cst.CSTNode) -> int:
        try:
            pos = self.get_metadata(cst_meta.PositionProvider, node)
            return pos.start.line
        except Exception:
            return 1

    @property
    def imports(self) -> list[FileImport]:
        return list(self._imports)


def resolve_imports(source_code: str) -> list[FileImport]:
    """Parse source code and return all import statements as FileImport instances."""
    module = cst.parse_module(source_code)
    wrapper = cst_meta.MetadataWrapper(module)
    collector = ImportCollector()
    wrapper.visit(collector)
    return collector.imports


def resolve_file_imports(file_path: str) -> list[FileImport]:
    """Read a Python file and return all import statements as FileImport instances."""
    source = Path(file_path).read_text(encoding="utf-8")
    return resolve_imports(source)
