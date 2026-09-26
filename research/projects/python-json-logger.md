# Project Analysis: `python-json-logger` (madzak/python-json-logger)

## 1. Project Overview
- **Repository**: `https://github.com/madzak/python-json-logger`
- **Documentation Type**: Python library documentation (guides, API reference, change log).
- **Doc Generator**: MkDocs + MkDocs Material.

---

## 2. Configuration & Features Inventory (`mkdocs.yml`)

### A. Theme & Navigation
- **Theme**: `material`
  - Palette / Dark Mode toggle
  - Header navigation / repository links
- **Navigation Structure (`nav`)**:
  - Simple 2-level hierarchy: Home (`index.md`), Usage (`usage.md`), Customization (`customization.md`), API Reference (`api.md`), Changelog (`changelog.md`).

### B. Plugins
- `search` (MkDocs core search)
- `mkdocstrings` with `python` handler:
  - Generates API reference docs directly from Python docstrings in `src/pythonjsonlogger`.
  - Uses Google-style / Sphinx-style docstrings with type annotations.

### C. Markdown Extensions (`markdown_extensions`)
- `admonition` (Standard Python-Markdown `!!! note`, `!!! warning`)
- `pymdownx.details` (Collapsible details `??? note`)
- `pymdownx.superfences` (Fenced code blocks, syntax highlighting)
- `pymdownx.tabbed` (Content tabs `=== "Tab"`)
- `pymdownx.highlight` (Code block line numbers and highlighting)
- `toc`: Permalinks enabled

---

## 3. Dependencies & Build Environment
- **Dependency Specification**: `pyproject.toml` using `dependency-groups` / optional dependencies (`docs` extra).
- **Doc Dependencies**:
  - `mkdocs`
  - `mkdocs-material`
  - `mkdocstrings[python]`
- **Target Replacement in Sphinx**:
  - `sphinx`
  - `myst-parser`
  - `sphinx-immaterial` (or `furo` / `sphinx-rtd-theme`)
  - `sphinx-design` (for tabs and dropdowns)

---

## 4. CI/CD & Hosting
- **CI System**: GitHub Actions (`.github/workflows/docs.yml` or publish workflow).
- **Hosting**: GitHub Pages via `mkdocs gh-deploy` or standard static upload.
- **Migration Action**:
  - Update workflow to run `sphinx-build -W -b html docs docs/_build/html`.
  - Update deployment artifact path from `site/` to `docs/_build/html/`.

---

## 5. Analyzer Classification Summary for `python-json-logger`

| Subsystem / Feature | Detected Pattern | Migration Strategy | Sphinx Equivalent |
| :--- | :--- | :--- | :--- |
| **Config** | `mkdocs.yml` | `TRANSFORM` | Generate `conf.py` + `sphinx-migrate.toml` |
| **Navigation** | `nav:` in `mkdocs.yml` | `TRANSFORM` | Generate `toctree` in `index.md` |
| **Admonitions** | `!!! note` / `!!! warning` | `TRANSFORM` | MyST ````{note}```` directives |
| **Details** | `??? note` | `TRANSFORM` | MyST ````{dropdown}```` (`sphinx-design`) |
| **Tabs** | `=== "Title"` | `TRANSFORM` | MyST ````{tab-set}```` (`sphinx-design`) |
| **API Reference** | `::: pythonjsonlogger.jsonlogger` | `TRANSFORM` | `.. automodule:: pythonjsonlogger` via `autodoc` |
| **Dependencies** | `pyproject.toml` docs group | `TRANSFORM` (Manual Confirm)| Replace mkdocs packages with Sphinx stack |
| **CI / Hosting** | GitHub Actions Pages | `TRANSFORM` (Manual Confirm)| Update build & artifact paths |

**Overall Compatibility**: **~95% Deterministic Automatic Transformation**.
