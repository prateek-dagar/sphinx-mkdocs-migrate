# Project Analysis: `Polars` (pola-rs/polars)

## 1. Project Overview
- **Repository**: `https://github.com/pola-rs/polars`
- **Documentation Type**: Fast multi-language DataFrame library (Python & Rust user guides).
- **Doc Generator**: MkDocs Material (User Guide) + Sphinx / Rustdoc (API).

---

## 2. Configuration & Features Inventory
- **Multi-language Tabs**: `=== "Python"` and `=== "Rust"` on almost every page.
- **Interactive Tables & Math**: MathJax / KaTeX equations (`pymdownx.arithmatex`).
- **Diagrams**: Mermaid.js diagram code blocks (`pymdownx.superfences` mermaid custom fence).

---

## 3. Analyzer Classification Summary for `Polars`

| Feature | Detection | Migration Strategy | Sphinx Equivalent |
| :--- | :--- | :--- | :--- |
| **Math / KaTeX** | `$$...$$` / `$math$` | `PRESERVE / TRANSFORM` | MyST `amsmath` / `dollarmath` extension |
| **Mermaid Diagrams**| ```` ```mermaid ```` | `TRANSFORM` | `sphinxcontrib-mermaid` |
| **Code Tabs** | Multi-language code blocks | `TRANSFORM` | `sphinx-design` `tab-set` |

**Overall Compatibility**: **~96% Deterministic Transformation**.
