# Contributing to FissionPy

Thank you for your interest in FissionPy!

## Development Setup

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - Python package manager

### Installation

```bash
# Clone repository
git clone https://github.com/kenny8zeng/fissionpy.git
cd fissionpy

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

# Install project in development mode
uv pip install -e ".[dev]"
```

## Code Standards

### Python Code
- Follow PEP 8 coding standards
- Use type hints
- Add necessary docstrings
- Keep functions and classes concise

### Testing
- All new features must include tests
- Use pytest as the testing framework

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/unit/test_extractor.py

# View test coverage
pytest tests/ --cov=src/fissionpy --cov-report=html
```

## Project Structure

```
fissionpy/
├── src/fissionpy/          # Source code
│   ├── analysis/           # Code analysis modules
│   ├── extraction/         # Code extraction modules
│   ├── migration/          # Code migration modules
│   ├── cli/                # Command line interface
│   └── common/             # Common utilities
├── tests/                  # Test code
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── fixtures/          # Test data
├── docs/                   # Documentation
├── specs/                  # Specifications
└── pyproject.toml         # Project configuration
```

## Development Guide

### Adding New Commands

1. Create new command file in `src/fissionpy/cli/`
2. Register command in `src/fissionpy/cli/app.py`
3. Add corresponding tests
4. Update documentation

### Modifying Core Features

1. Understand existing code structure
2. Add or update tests
3. Run full test suite
4. Check performance impact

### Documentation Updates

- Update README.md (if needed)
- Update docs/README.ch.md (Chinese documentation)
- Update relevant command documentation
- Add usage examples

## Issue Reporting

### Bug Reports
Use GitHub Issues to report bugs, please include:
- Problem description
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment information (Python version, OS, etc.)
- Error logs (if available)

### Feature Requests
Use GitHub Issues to propose features, please describe:
- Feature description
- Use case
- Expected outcome

## Getting Help

- Check [README.md](README.md) for project overview
- Check [docs/README.ch.md](docs/README.ch.md) for detailed documentation
- Ask questions in GitHub Issues
- Check [SKILL.md](SKILL.md) for AI Agent skill information

## License

This project is licensed under the MIT License.