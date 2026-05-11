"""Path utility functions for project-level fission tool."""

from __future__ import annotations

from pathlib import Path


def find_project_root(start_path: str) -> str | None:
    """Walk up from start_path looking for a .fission/ directory.

    Returns the directory containing .fission/, or None if not found.
    """
    current = Path(start_path).resolve()
    while True:
        if (current / ".fission").is_dir():
            return str(current)
        parent = current.parent
        if parent == current:
            return None
        current = parent


def module_path_to_file_path(module_path: str, project_root: str) -> str:
    """Convert a module path like 'app/_migrated/user_types' to an absolute file path.

    The module_path uses '/' as separator (from YAML plan).
    The result is '{project_root}/app/_migrated/user_types.py'.
    """
    return str(Path(project_root) / f"{module_path}.py")


def file_path_to_module_path(file_path: str, project_root: str) -> str:
    """Convert an absolute file path to a module path.

    E.g. '{project_root}/app/models.py' -> 'app/models' (without .py extension).
    """
    rel = Path(file_path).relative_to(project_root)
    return str(rel.with_suffix(""))


def module_path_to_python_import(module_path: str) -> str:
    """Convert 'app/_migrated/user_types' to 'app._migrated.user_types'.

    Used for generating Python import statements.
    """
    return module_path.replace("/", ".")


def python_import_to_module_path(python_import: str) -> str:
    """Convert 'app._migrated.user_types' back to 'app/_migrated/user_types'.

    Inverse of module_path_to_python_import.
    """
    return python_import.replace(".", "/")


def ensure_init_files(dir_path: str) -> list[str]:
    """Create __init__.py in every intermediate directory that lacks one.

    Returns list of created __init__.py paths.
    """
    created: list[str] = []
    target = Path(dir_path).resolve()
    parts = target.parts
    for i in range(1, len(parts) + 1):
        sub = Path(*parts[:i])
        init_file = sub / "__init__.py"
        if sub.is_dir() and not init_file.exists():
            init_file.touch()
            created.append(str(init_file))
    return created
