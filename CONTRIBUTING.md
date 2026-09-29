# Contributing Guidelines

Thank you for your interest in contributing to **`sphinx-mkdocs-migrate`**!

We welcome bug reports, documentation enhancements, construct transformation rules, and engine optimizations.

---

## Development Workflow

### 1. Setting Up the Local Environment

Ensure you have Python 3.10 or higher installed. Clone the repository and install it in editable mode with development dependencies:

```bash
git clone https://github.com/prateek-dagar/sphinx-mkdocs-migrate.git
cd sphinx-mkdocs-migrate

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

### 2. Running Tests

We maintain strict test coverage across unit tests, AST parsers, transformer engines, and real Sphinx builds:

```bash
# Run all tests
pytest tests/ -v

# Run with test coverage report
pytest tests/ --cov=sphinx_mkdocs_migrate --cov-report=term
```

### 3. Code Quality & Static Analysis

All code is strictly checked for formatting and typing before merging:

```bash
# Linting
ruff check src tests

# Code formatting check
ruff format --check src tests

# Apply formatting automatically
ruff format src tests

# Static type checking
mypy --explicit-package-bases --ignore-missing-imports src/ tests/
```

---

## Architecture Guide for Contributors

The engine operates in four distinct, deterministic phases:

1. **Analyzer (`src/sphinx_mkdocs_migrate/analyzer/`)**:
   - Inspects `mkdocs.yml`, plugins, Markdown syntax, navigation trees, and dependencies without modifying anything.
2. **Intermediate Representation (`src/sphinx_mkdocs_migrate/parsing/`)**:
   - Parses Markdown and HTML into syntax-neutral AST nodes (`DocumentIR` and `DocumentFlow`).
3. **Planner (`src/sphinx_mkdocs_migrate/planner/`)**:
   - Applies the policy matrix and produces a declarative, dry-runnable `MigrationPlan` with provenance for every requirement.
4. **Transformer & Engine (`src/sphinx_mkdocs_migrate/transformer/`)**:
   - Executes source-preserving span replacements, generates `conf.py`, synthesizes API modules, and updates CI/dependencies.

### Adding a New Markdown Construct Transformation

To support a new Markdown syntax or MkDocs plugin equivalent:
1. Define the rule in `src/sphinx_mkdocs_migrate/rules/catalog.py`.
2. Specify the source pattern, target Sphinx directive, and required extension.
3. Add a unit test in `tests/test_transformer.py` verifying byte preservation on surrounding text.

---

## Pull Request Guidelines

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-new-rule
   ```
2. Verify that `pytest`, `ruff check`, and `mypy` all pass locally before opening a pull request.
3. Ensure all new constructs or policy rules include test coverage.
4. Open a Pull Request on GitHub. Our automated CI and pre-commit formatting bot will inspect the PR and run test matrices across operating systems and Python versions.
