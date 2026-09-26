# Markdown & Construct Compatibility Specification

## Purpose
Catalog how individual Markdown constructs are parsed in MkDocs/Python-Markdown and how they map to Sphinx/MyST-Parser.

---

## 1. Core CommonMark Constructs

| Construct | Origin | Strategy | Sphinx/MyST Equivalent | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Heading H1..H6** | CommonMark | `PRESERVE` | `# Title` | Preserve heading depth |
| **Paragraph / Text** | CommonMark | `PRESERVE` | Plain text | No change |
| **Inline Code** | CommonMark | `PRESERVE` | `` `code` `` | No change |
| **Fenced Code Block**| GFM / CommonMark | `PRESERVE` | ```` ```python ```` | Check language lexer |
| **Markdown Tables** | GFM | `PRESERVE` | Markdown Tables | Supported natively |

---

## 2. Python-Markdown & PymdownX Extensions

| Construct | Origin | Strategy | Sphinx/MyST Equivalent | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Admonition** | `admonition` | `TRANSFORM` | ````{note}````, ````{warning}```` | Direct directive mapping |
| **Details / Dropdown**| `pymdownx.details` | `TRANSFORM` | ````{dropdown}```` (`sphinx-design`) | Maps `???` and `???+` |
| **Content Tabs** | `pymdownx.tabbed` | `TRANSFORM` | ````{tab-set}```` (`sphinx-design`) | Maps `=== "Tab"` syntax |
| **Snippet Includes**| `pymdownx.snippets`| `TRANSFORM` | ````{include}```` / `literalinclude` | Resolves external path |
| **Line Highlighting**| `pymdownx.superfences`| `TRANSFORM` | `:emphasize-lines:` option | Extracts line numbers |
| **Emoji / Icons** | `pymdownx.emoji` | `TRANSFORM/MANUAL` | `sphinx-design` icons or theme | Depends on icon font set |
