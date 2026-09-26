# Project Analysis: `HTTPX` (encode/httpx)

## 1. Project Overview
- **Repository**: `https://github.com/encode/httpx`
- **Documentation Type**: High-traffic Python HTTP client library.
- **Doc Generator**: MkDocs + MkDocs Material.

---

## 2. Configuration & Features Inventory (`mkdocs.yml`)

### A. Theme & Navigation
- **Theme**: `material`
  - Font settings (Roboto / Roboto Mono)
  - Color palettes (dark/light toggle)
  - Features: `navigation.instant`, `navigation.tracking`, `content.code.copy`
- **Navigation Structure (`nav`)**:
  - Multi-section navigation: User Guide (Async, Advanced, Environment Variables), API Reference (Client, Request, Response, Status Codes), Community & Contributing.

### B. Plugins & Markdown Extensions
- `search` plugin
- `markdown_extensions`:
  - `admonition`
  - `pymdownx.highlight`: `anchor_linenums=True`, `line_spans="__span"`
  - `pymdownx.superfences`
  - `pymdownx.inlinehilite`
  - `pymdownx.tabbed`: `alternate_style=True`
  - `toc`: `permalink=True`

---

## 3. Dependencies & Build Environment
- **Build Tool**: `hatch` / `uv` with `[tool.hatch.envs.docs]` or `docs` dependency groups.
- **Doc Dependencies**:
  - `mkdocs`
  - `mkdocs-material`
  - `mkautodoc` / custom docstring tools

---

## 4. CI/CD & Hosting
- **CI System**: GitHub Actions (`.github/workflows/docs.yml` testing `mkdocs build --strict`).
- **Hosting**: GitHub Pages (`mkdocs gh-deploy` action).

---

## 5. Analyzer Classification Summary for `HTTPX`

| Subsystem / Feature | Detected Pattern | Migration Strategy | Sphinx Equivalent |
| :--- | :--- | :--- | :--- |
| **Config** | `mkdocs.yml` + Material features | `TRANSFORM` | Generate `conf.py` + `sphinx-immaterial` |
| **Navigation** | Multi-level `nav:` | `TRANSFORM` | Generate root & section `toctree` in `index.md` |
| **Admonitions** | `!!! note` / `!!! tip` / `!!! warning` | `TRANSFORM` | MyST ````{note}```` / ````{tip}```` |
| **Code Tabs** | `=== "Sync"` / `=== "Async"` | `TRANSFORM` | MyST ````{tab-set}```` (`sphinx-design`) |
| **SuperFences** | Code highlighting & line anchors | `TRANSFORM` | MyST code-block options (`:emphasize-lines:`) |
| **Dependencies** | Hatch / pyproject.toml docs env | `TRANSFORM` (Manual Confirm)| Replace mkdocs stack with Sphinx + MyST stack |
| **CI / Hosting** | GitHub Actions build + deploy | `TRANSFORM` (Manual Confirm)| Change test to `sphinx-build -W` & Pages deploy |

**Overall Compatibility**: **~98% Deterministic Automatic Transformation**.
