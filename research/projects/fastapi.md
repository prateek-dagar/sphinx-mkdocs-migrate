# Project Analysis: `FastAPI` (tiangolo/fastapi)

## 1. Project Overview
- **Repository**: `https://github.com/tiangolo/fastapi`
- **Documentation Type**: High-concurrency web framework with multi-language translations.
- **Doc Generator**: MkDocs + MkDocs Material.

---

## 2. Configuration & Features Inventory
- **Translations / Internationalization**: Dozens of language subtrees (`docs/en/docs/`, `docs/es/docs/`, `docs/zh/docs/`).
- **Markdown Extensions**:
  - `pymdownx.superfences` (Custom nested fences)
  - `pymdownx.tabbed` (Content tabs for Python versions, e.g., Python 3.10+ vs 3.9)
  - `pymdownx.inlinehilite`
  - `pymdownx.snippets` (Including external code examples from `docs_src/`)
  - `admonition`
- **Theme**: Custom Material with sponsor badges and custom header components.

---

## 3. Analyzer Classification Summary for `FastAPI`

| Feature | Detection | Migration Strategy | Sphinx Equivalent |
| :--- | :--- | :--- | :--- |
| **Snippet Includes** | `--8<-- "docs_src/..."` | `TRANSFORM` | MyST ````{include} docs_src/...```` / `literalinclude` |
| **Translations** | Language directories | `TRANSFORM / MANUAL` | Sphinx `gettext` / `sphinx-intl` or directory builds |
| **Version Tabs** | `=== "Python 3.10+"` | `TRANSFORM` | `sphinx-design` `tab-set` |
| **Custom Assets** | `docs/css/custom.css` | `TRANSFORM` | `html_css_files` in `conf.py` |

**Overall Compatibility**: **~92% Deterministic Transformation + Internationalization setup**.
