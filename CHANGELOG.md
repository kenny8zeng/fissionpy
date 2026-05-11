# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of FissionPy
- Project-level symbol indexing with LibCST
- Symbol browsing and dependency visualization
- Intelligent migration plan generation
- Lossless code extraction using LibCST CST nodes
- Project-wide import propagation with CSTTransformer
- File reorganization and re-export functionality
- Triple consistency verification (symbol integrity, format losslessness, import reachability)
- AI Agent Skill integration for autonomous code splitting
- Comprehensive test suite (63 tests)
- Bilingual documentation (English and Chinese)

### Features
- `fission analyze` - Analyze project directory and index symbols
- `fission show` - Browse symbol information and dependencies
- `fission tree` - Display symbol dependency trees
- `fission plan` - Generate YAML migration plans
- `fission extract` - Execute lossless code extraction
- `fission migrate` - Complete project-level migration

### Technical
- LibCST-based concrete syntax tree parsing
- SQLite persistent storage with incremental analysis
- Cross-file dependency tracking
- Support for subdirectory modules
- Automatic `__init__.py` creation
- Backup and restore functionality

## [0.2.0] - 2025-05-11

### Added
- MIT License declaration
- Project documentation (README.md, docs/README.ch.md)
- Contributing guidelines
- GitHub repository setup
- License file

### Changed
- Updated project metadata in pyproject.toml
- Added license information to CLI help text
- Enhanced documentation with project links

## [0.1.0] - 2025-05-10

### Added
- Initial project structure
- Core analysis, extraction, and migration modules
- CLI framework with Typer
- Basic test suite
- Project specifications