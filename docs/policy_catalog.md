# Declarative Policy Catalog

The policy catalog enforces evidence-driven dependency mappings derived from empirical observations across the real-world validation corpus:

| Source Feature | Category | Action | Target / Resolution | Provenance |
| :--- | :--- | :--- | :--- | :--- |
| `content.code.copy` | `THEME_FEATURE` | `ENABLE_EXTENSION` | `sphinx_copybutton` / `sphinx-copybutton>=0.5.2` | `FEATURE_POLICY` |
| `content.tabs.link` | `THEME_FEATURE` | `ENABLE_EXTENSION` | `sphinx_design` / `sphinx-design>=0.5.0` | `FEATURE_POLICY` |
| `pymdownx.tabbed` | `MARKDOWN_EXTENSION` | `TRANSFORM` | `sphinx-design` (`{tab-set}`, `{tab-item}`) | `EXTENSION_POLICY` |
| `pymdownx.details` | `MARKDOWN_EXTENSION` | `TRANSFORM` | `sphinx-design` (`{dropdown}`) | `EXTENSION_POLICY` |
| `pymdownx.superfences`| `MARKDOWN_EXTENSION` | `PRESERVE` | MyST `colon_fence` | `EXTENSION_POLICY` |
| `pymdownx.arithmatex` | `MARKDOWN_EXTENSION` | `PRESERVE` | MyST `dollarmath` | `EXTENSION_POLICY` |
| `pymdownx.snippets` | `MARKDOWN_EXTENSION` | `TRANSFORM` | MyST `{include}` / `literalinclude` | `EXTENSION_POLICY` |
| `pymdownx.emoji` | `MARKDOWN_EXTENSION` | `MANUAL` | Manual review of icon shortcodes (`:smile:`) | `MANUAL` |
| `mkdocstrings` | `PLUGIN` | `TRANSFORM` | `sphinx.ext.autodoc` + `sphinx.ext.napoleon` | `EXTENSION_POLICY` |
| `search.share` | `THEME_FEATURE` | `UNSUPPORTED` | No static Sphinx HTML equivalent | `UNSUPPORTED` |
