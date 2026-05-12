# fissionpy

**Python Project Fission & Migration Tool** — A lossless code splitting and migration solution powered by LibCST.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Repository**: https://github.com/kenny8zeng/fissionpy

**Documentation**:
- [English](README.md) | [中文](docs/README.ch.md)

fissionpy is designed for refactoring large Python projects, safely and automatically splitting massive module files (thousands to tens of thousands of lines) into smaller, maintainable modules. Using LibCST (Concrete Syntax Tree) technology, it ensures all code changes are lossless — preserving original formatting, comments, and whitespace.

## Core Features

### 1. Project-Level Symbol Indexing
- Recursively scans entire Python projects, parsing all `.py` files
- Uses LibCST to extract top-level symbols (functions, classes, variable assignments)
- Analyzes inter-symbol dependencies via LibCST ScopeProvider
- Tracks cross-file import statements, automatically identifying symbol reference chains
- SQLite persistent storage with incremental analysis (file hash-based)

### 2. Symbol Browsing & Dependency Visualization
- `fission show`: View project file list, file symbol tables, symbol details
- `fission tree`: Display symbol dependency relationships in tree format
- Cross-file dependency annotations: Clearly mark which symbols are referenced by other files
- Reverse dependency queries: Find what depends on a given symbol

### 3. Intelligent Migration Plan Generation
- Automatic grouping based on connected components of the symbol dependency graph
- Generates YAML migration plans, supporting manual editing and adjustment
- Automatically calculates import impact scope (which files need import updates)
- Supports subdirectory modules (`module/deep/path` → `module/deep/path.py`)

### 4. Lossless Code Extraction
- Uses LibCST CST nodes for extraction, preserving original format character-by-character
- Preserves leading_lines (comments, blank lines), decorators, base classes
- Automatically prepends necessary imports like `from __future__ import annotations`
- Post-extraction verification: Compares extracted text with original

### 5. Project-Wide Import Propagation
- Uses LibCST CSTTransformer to precisely replace import statements
- Handles complex scenarios: `from X import Y, Z` splitting, aliased imports
- Automatically updates all affected import statements across the project
- Supports both relative and absolute imports

### 6. Reorganization & Re-Export
- Backs up original files (`.bak` suffix)
- Removes extracted symbols, retains remaining ones
- Automatically adds re-export imports (`from new_module import Symbol`)
- Creates subdirectory `__init__.py` files

### 7. Triple Consistency Verification
- **Symbol Integrity**: All original symbols found in split files
- **Format Losslessness**: Extracted text matches original character-by-character
- **Import Reachability**: All import statement target files exist

## AI Agent Skill

fissionpy provides a Skill file (`SKILL.md`) specifically designed for AI Agents, enabling AI programming assistants to autonomously complete large Python file splitting and migration workflows.

### Skill Triggers

When users issue commands like "split this Python file", "refactor large module", or when files exceed 1000 lines, the AI Agent automatically activates the fissionpy Skill and executes the complete 6-phase workflow:

1. **Analyze** → `fission analyze` indexes all symbols and dependencies
2. **Browse** → `fission show` / `fission tree` explores file structure
3. **Plan** → `fission plan` creates YAML migration plan
4. **Edit** → Intelligently assigns symbols to modules (user-adjustable)
5. **Extract** → `fission extract` performs lossless code extraction
6. **Migrate** → `fission migrate` updates project-wide imports and verifies

### Skill Capabilities

- **Autonomous Execution**: AI Agent can complete the full workflow from analysis to migration
- **Smart Grouping**: Automatically suggests module splits based on dependency connected components
- **Safe Verification**: Automatic validation after each step ensures code integrity
- **Best Practices**: Built-in module naming conventions, splitting strategies, edge case handling
- **Troubleshooting**: Common issue diagnostics and solutions included

## Installation

```bash
uv pip install -e .
```

Requires Python 3.11+.

## Quick Start

```bash
# Step 1: Navigate to project root directory
cd /path/to/my_project/

# Step 2: Analyze project (use relative paths from project root)
fission analyze ./backend/

# Step 3: Browse symbols
fission show
fission show --file ./backend/models.py
fission show --symbol User
fission tree --file ./backend/views.py

# Step 4: Generate migration plan
fission plan --target ./backend/models.py --output ./fission-plan.yaml

# Step 5: Edit plan.yaml (move symbols from retain to modules)
# Edit YAML to assign symbols to target modules

# Step 6: Extract symbols
fission extract ./fission-plan.yaml

# Step 7: Migrate (update project-wide imports)
fission migrate ./fission-plan.yaml
```

### ⚠️ Important: Path Consistency

**All commands must use relative paths from the project root directory.**

#### Why Use Relative Paths

- ✅ **Supports project directory movement**: Can continue and rollback after moving the project
- ✅ **Version control friendly**: Relative paths work better with Git and other VCS
- ✅ **Team collaboration**: Different developers may have different project directory locations
- ✅ **Easy rollback**: Can easily restore to previous state

#### Path Rules

1. **Always execute commands from the project root directory**:
   ```bash
   # ✅ Correct: Navigate to project root first
   cd /path/to/my_project/

   # Verify current directory (should contain .fission/ directory)
   ls -la .fission/

   # All commands use relative paths from project root
   fission analyze ./backend/
   fission plan --target ./backend/models.py
   fission extract ./fission-plan.yaml
   fission migrate ./fission-plan.yaml
   ```

2. **Use `./` prefix to clearly indicate relative paths**:
   ```bash
   # ✅ Correct: Use ./ prefix
   fission analyze ./backend/
   fission plan --target ./backend/models.py

   # ❌ Incorrect: No ./ prefix (confusing)
   fission analyze backend/
   fission plan --target backend/models.py
   ```

3. **❌ Do NOT use absolute paths**:
   ```bash
   # ❌ Incorrect: Using absolute paths
   fission analyze /home/user/project/backend/
   fission plan --target /home/user/project/backend/models.py

   # Problem: Cannot continue or rollback after moving project directory
   ```

#### Common Path Mistakes

**Mistake 1: Executing commands from different directories**
```bash
# ❌ Incorrect: Different directories
cd /home/user/project/
fission analyze ./backend/

cd /home/user/project/backend/
fission plan --target models.py  # Path base changed!

cd /home/user/project/
fission extract ./fission-plan.yaml  # File not found!
```

**Mistake 2: Using absolute paths**
```bash
# ❌ Incorrect: Using absolute paths
fission analyze /home/user/project/backend/
fission plan --target /home/user/project/backend/models.py

# Problem: Cannot continue or rollback after moving project
```

**Mistake 3: Mixing path types**
```bash
# ❌ Incorrect: Mixing absolute and relative paths
fission analyze /home/user/project/backend/
fission plan --target ./backend/models.py  # Mixed!
```

#### ✅ Correct Path Usage

**Complete workflow example**:
```bash
# 1. Navigate to project root
cd /path/to/my_project/

# 2. Verify current directory
echo "Project root: $(pwd)"
ls -la .fission/

# 3. Analyze (use relative paths)
fission analyze ./backend/ --verbose

# 4. Generate plan (use relative paths)
fission plan --target ./backend/models.py \
  --output ./fission-plan.yaml \
  --verbose

# 5. Verify plan file
cat ./fission-plan.yaml | grep project_root
cat ./fission-plan.yaml | grep target_file

# 6. Extract (use relative paths)
fission extract ./fission-plan.yaml --verbose

# 7. Migrate (use relative paths)
fission migrate ./fission-plan.yaml --verbose
```

**Supports project movement**:
```bash
# After moving project directory, can still continue and rollback
mv /path/to/my_project /new/path/to/my_project/

# Navigate to new project root
cd /new/path/to/my_project/

# All commands still work (because using relative paths)
fission extract ./fission-plan.yaml  # ✓ Still works
fission migrate ./fission-plan.yaml  # ✓ Still works

# Rollback
mv ./backend/models.py.bak ./backend/models.py  # ✓ Still works
rm -rf ./_migrated/  # ✓ Still works
```

## Command Reference

### `fission analyze`

Analyzes project directory, indexing all files and symbols into SQLite database.

```bash
fission analyze <directory> [--db PATH] [--exclude PATTERN] [--force] [--verbose]
```

| Option | Description |
|--------|-------------|
| `--db` | SQLite database path, default `./.fission/fission.db` |
| `--exclude` | Exclude directory patterns, repeatable |
| `--force` | Force re-parse all files (ignore incremental cache) |
| `--verbose` | Detailed output |

**⚠️ Path Note**: Always execute from project root and use relative paths:
```bash
# ✅ Correct
cd /path/to/project/
fission analyze ./backend/

# ❌ Incorrect
fission analyze /home/user/project/backend/
```

### `fission show`

Browse symbol information — project file list, file symbol list, symbol details and dependencies.

```bash
fission show [--file PATH] [--symbol NAME] [--db PATH] [--verbose]
```

| Option | Description |
|--------|-------------|
| `--file` | View top-level symbols and imports for specified file |
| `--symbol` | View symbol details, dependencies, and dependents |
| `--db` | SQLite database path |
| `--verbose` | Detailed output |

**⚠️ Path Note**: Use relative paths from project root:
```bash
# ✅ Correct
fission show --file ./backend/models.py

# ❌ Incorrect
fission show --file /home/user/project/backend/models.py
```

Without options, displays project file overview.

### `fission tree`

Prints symbol dependency tree for specified file.

```bash
fission tree --file PATH [--symbol NAME] [--reverse] [--db PATH] [--verbose]
```

| Option | Description |
|--------|-------------|
| `--file` | Target file path (required) |
| `--symbol` | Show only subtree for specified symbol |
| `--reverse` | Reverse view: show what depends on this symbol |
| `--db` | SQLite database path |
| `--verbose` | Detailed output |

**⚠️ Path Note**: Use relative paths from project root:
```bash
# ✅ Correct
fission tree --file ./backend/views.py

# ❌ Incorrect
fission tree --file /home/user/project/backend/views.py
```

### `fission plan`

Generates YAML migration plan template for target file. Auto-groups based on symbol dependencies, user-editable.

```bash
fission plan --target PATH [--db PATH] [--output PATH] [--verbose]
```

| Option | Description |
|--------|-------------|
| `--target` | Target file path to split (required) |
| `--db` | SQLite database path |
| `--output` | YAML output path, default `./fission-plan.yaml` |
| `--verbose` | Detailed output |

**⚠️ Path Note**: Use relative paths from project root:
```bash
# ✅ Correct
fission plan --target ./backend/models.py --output ./fission-plan.yaml

# ❌ Incorrect
fission plan --target /home/user/project/backend/models.py --output /home/user/project/fission-plan.yaml
```

### `fission extract`

Executes code extraction — losslessly extracts symbols into new module files per plan.

```bash
fission extract <plan_file> [--db PATH] [--resume] [--verbose]
```

| Option | Description |
|--------|-------------|
| `--db` | SQLite database path |
| `--resume` | Resume extraction from last interruption |
| `--verbose` | Detailed output |

**⚠️ Path Note**: Use relative paths from project root:
```bash
# ✅ Correct
fission extract ./fission-plan.yaml

# ❌ Incorrect
fission extract /home/user/project/fission-plan.yaml
```

### `fission migrate`

Completes project-level migration — updates project-wide imports, backs up and reorganizes original file, runs consistency checks.

```bash
fission migrate <plan_file> [--db PATH] [--no-reexport] [--resume] [--verbose]
```

| Option | Description |
|--------|-------------|
| `--db` | SQLite database path |
| `--no-reexport` | Don't generate re-export imports in original file |
| `--resume` | Resume migration from last interruption |
| `--verbose` | Detailed output |

**⚠️ Path Note**: Use relative paths from project root:
```bash
# ✅ Correct
fission migrate ./fission-plan.yaml

# ❌ Incorrect
fission migrate /home/user/project/fission-plan.yaml
```

Global option: `--version` displays version number.

## YAML Plan Format

The YAML file structure generated by `fission plan`:

```yaml
# fission migration plan - edit modules/symbols before running extract
project_root: .
target_file: backend/models.py
modules:
- name: _migrated/user_types
  symbols:
  - User
  - UserProfile
  - UserStatus
- name: _migrated/order_types
  symbols:
  - Order
  - OrderItem
retain:
- router
- app_config
import_impact:
- file: ./backend/views.py
  old_import: from backend.models import User
  new_import: from _migrated.user_types import User
- file: ./backend/services.py
  old_import: from backend.models import Order
  new_import: from _migrated.order_types import Order
```

| Field | Description |
|-------|-------------|
| `project_root` | Project root directory (should be `.` for relative paths) |
| `target_file` | Relative path to target file from project root |
| `modules` | List of modules to extract, each with `name` and `symbols` |
| `retain` | Symbols to keep in the original file |
| `import_impact` | List of import update impacts, showing affected files and old/new import pairs |

### How to Edit the Plan

**⚠️ Critical Rules** - Follow these rules to avoid extraction failures:

1. **Move symbols from `retain` to `modules`**:
   - Initially, all symbols are in `retain`
   - Move symbols you want to extract into `modules`
   - Each symbol can only appear in ONE place (either `modules` or `retain`)

2. **Verify symbol names**:
   ```bash
   # Check actual symbol names in the target file
   fission show --file models.py
   ```
   - Symbol names must match exactly (case-sensitive)
   - No typos or extra spaces

3. **Validate module names**:
   - Each path segment must be a valid Python identifier
   - Cannot be a Python keyword (e.g., `class`, `def`, `import`)
   - Cannot start with a number
   - Use `/` for subdirectories (e.g., `_migrated/models/user`)

4. **Do NOT modify `import_impact`**:
   - This section is auto-generated and read-only
   - Modifying it will cause incorrect import updates

### Common Mistakes

**❌ Mistake 1: Duplicate symbols**
```yaml
modules:
- name: models
  symbols:
  - User
- name: entities
  symbols:
  - User  # ERROR: User appears twice!
retain: []
```

**❌ Mistake 2: Non-existent symbols**
```yaml
modules:
- name: models
  symbols:
  - User
  - NonExistent  # ERROR: Symbol not in target file!
retain: []
```

**❌ Mistake 3: Invalid module names**
```yaml
modules:
- name: 123-bad-name  # ERROR: Cannot start with number
  symbols:
  - User
- name: class         # ERROR: Python keyword
  symbols:
  - Product
retain: []
```

**✅ Correct example**:
```yaml
modules:
- name: _migrated/models
  symbols:
  - User
  - Product
- name: _migrated/services
  symbols:
  - UserService
  - ProductService
retain:
- router
- app_config
```

### Editing Workflow

1. **Generate the plan**:
   ```bash
   cd /path/to/project/
   fission plan --target ./backend/models.py --output ./fission-plan.yaml
   ```

2. **Review the plan**:
   ```bash
   cat ./fission-plan.yaml
   ```

3. **Check symbol names**:
   ```bash
   fission show --file ./backend/models.py
   ```

4. **Edit the plan**:
   - Move symbols from `retain` to `modules`
   - Create new modules or adjust existing ones
   - Ensure no duplicates

5. **Validate YAML syntax**:
   ```bash
   python -c "import yaml; yaml.safe_load(open('./fission-plan.yaml'))"
   ```

6. **Run extraction**:
   ```bash
   fission extract ./fission-plan.yaml
   ```

## Subdirectory Support

Use `/` in module names to create subdirectory structures:

- `_migrated/types` → Output file `_migrated/types.py`, auto-creates `_migrated/` directory and `__init__.py`
- `_migrated/models/user` → Output file `_migrated/models/user.py`, auto-creates all intermediate `__init__.py` files

Each path segment must be a valid Python identifier, not a keyword. The corresponding Python import statement replaces `/` with `.`, e.g., `_migrated.types`.

### Multi-Level Directory Examples

**Example 1: Two-level directory**
```yaml
modules:
- name: _migrated/models
  symbols:
  - User
  - Product
- name: _migrated/services
  symbols:
  - UserService
  - ProductService
```

Output structure:
```
project/
├── _migrated/
│   ├── __init__.py
│   ├── models.py
│   └── services.py
└── backend/
    └── models.py (original file, reorganized)
```

**Example 2: Three-level directory**
```yaml
modules:
- name: _migrated/models/user
  symbols:
  - User
  - UserProfile
- name: _migrated/models/order
  symbols:
  - Order
  - OrderItem
- name: _migrated/services
  symbols:
  - UserService
  - OrderService
```

Output structure:
```
project/
├── _migrated/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── order.py
│   └── services.py
└── backend/
    └── models.py (original file, reorganized)
```

**Import statements after migration**:
```python
# In other files
from _migrated.models.user import User
from _migrated.models.order import Order
from _migrated.services import UserService
```

### Rules for Subdirectory Module Names

1. **Path segments must be valid Python identifiers**:
   - ✅ `_migrated/models/user`
   - ✅ `internal/utils`
   - ❌ `123-bad-name`
   - ❌ `my-module` (hyphens not allowed)

2. **Cannot use Python keywords**:
   - ✅ `models/classifier`
   - ❌ `models/class` (class is a keyword)

3. **Auto-creation of `__init__.py`**:
   - All intermediate directories get `__init__.py` automatically
   - Makes the directory a valid Python package

4. **Import path conversion**:
   - YAML: `_migrated/models/user`
   - Python import: `from _migrated.models.user import User`

## Key Features

- **LibCST Lossless Extraction**: CST-based code extraction preserves comments, formatting, and whitespace
- **CSTTransformer Import Updates**: Precise import modification using CSTTransformer, never regex
- **Incremental Analysis**: File hash-based incremental parsing, unchanged files auto-skipped
- **Cross-File Dependency Tracking**: Automatically identifies and records cross-file symbol dependencies
- **Triple Verification**: Post-migration automatic validation of symbol integrity, format losslessness, and import reachability

## Real-World Case: Splitting a 12,775-Line FastAPI File

fissionpy successfully processed a 12,775-line `presales_api.py` file (FastAPI router module), splitting it into 7 modules:

```bash
# Navigate to project root
cd /home/user/project/

# Analyze 158 files, 3190 symbols (65 seconds)
fission analyze ./backend/

# Generate plan, manually edit to distribute 454 symbols into 7 modules
fission plan --target ./app/presales_api.py --output ./fission-plan.yaml

# Extract 127 symbols into 6 new modules (21 seconds)
fission extract ./fission-plan.yaml

# Migrate and update imports in 2 dependent files (80 seconds)
fission migrate ./fission-plan.yaml
```

**Results**:

| File | Lines | Description |
|------|-------|-------------|
| `app/presales_api.py` | 8,783 | Reorganized (reduced 3,992 lines, 31%) |
| `app/_di.py` | 157 | DI config + router + providers |
| `app/case_api.py` | 2,171 | Case API endpoints |
| `app/knowledge_api.py` | 758 | Knowledge base API endpoints |
| `app/mailbox_api.py` | 462 | Mailbox sync API |
| `app/template_api.py` | 421 | Template & FAQ API |
| `app/misc_api.py` | 413 | Miscellaneous API |

**Total**: ~3 minutes to complete lossless splitting and migration of a 12,775-line large file, all verifications passed.

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests (63 tests, <1 second)
cd /path/to/project/
pytest ./tests/
```

## Tech Stack

- **LibCST**: Python concrete syntax tree parsing, supports lossless code operations
- **Typer**: CLI framework, type-safe wrapper around Click
- **SQLite**: Lightweight relational database, stores project symbol index
- **ruamel.yaml**: Round-trip YAML parser
- **pytest**: Testing framework, 63 unit + integration tests

## License

MIT License
