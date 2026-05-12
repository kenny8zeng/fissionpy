"""Directory scanning for Python file discovery."""

from __future__ import annotations

import hashlib
from pathlib import Path

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "site-packages",
        ".fission",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".eggs",
        "*.egg-info",
    }
)


class ScanResult:
    """Result of a directory scan for Python files."""

    files: list[Path]
    skipped_dirs: list[str]
    errors: list[str]

    def __init__(
        self,
        files: list[Path] | None = None,
        skipped_dirs: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        self.files = files or []
        self.skipped_dirs = skipped_dirs or []
        self.errors = errors or []


def _normalize_path(path: Path) -> str:
    """Normalize path by removing ./ prefix and converting to relative path.

    This ensures consistency when storing and querying file paths in the database.
    """
    path_str = str(path)
    if path_str.startswith("./"):
        return path_str[2:]
    return path_str


def scan_directory(directory: str, exclude: list[str] | None = None) -> ScanResult:
    """Recursively scan a directory for .py files, skipping excluded directories.

    User-provided exclude patterns are appended to the default set.
    Returns a ScanResult with discovered files sorted by path.
    """
    root = Path(directory).resolve()
    if not root.is_dir():
        return ScanResult(errors=[f"Not a directory: {root}"])

    exclude_set = DEFAULT_EXCLUDE_DIRS | frozenset(exclude or [])
    files: list[Path] = []
    skipped_dirs: list[str] = []
    errors: list[str] = []

    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except PermissionError as exc:
            errors.append(str(exc))
            continue
        for entry in entries:
            if entry.is_dir():
                if _is_excluded(entry.name, exclude_set):
                    skipped_dirs.append(entry.name)
                else:
                    stack.append(entry)
            elif entry.name.endswith(".py"):
                files.append(entry)

    files.sort()
    normalized_files = [Path(_normalize_path(f)) for f in files]
    return ScanResult(files=normalized_files, skipped_dirs=skipped_dirs, errors=errors)


def compute_file_hash(file_path: str | Path) -> str:
    """Compute SHA256 hash of a file's content."""
    path = Path(file_path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_excluded(name: str, exclude_set: frozenset[str]) -> bool:
    """Check if a directory name matches any exclusion pattern."""
    if name in exclude_set:
        return True
    for pattern in exclude_set:
        if "*" in pattern and pattern.startswith("*") and name.endswith(pattern[1:]):
            return True
    return False
