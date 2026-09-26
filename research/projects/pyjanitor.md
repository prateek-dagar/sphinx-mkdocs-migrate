# Project Analysis: `pyjanitor` (pyjanitor-devs/pyjanitor) — Historical Migration Research

## 1. Project Overview
- **Repository**: `https://github.com/pyjanitor-devs/pyjanitor`
- **Context**: Historical discussion (Issue #1032) regarding migrating documentation style from Sphinx to Google/MkDocs and back.

---

## 2. Lessons Learned & Migration Friction Points
- **API Docstring Parsing (`mkdocstrings` vs `sphinx.ext.autodoc`)**:
  - Automated tools often break semantic meaning when converting docstring parameter lists and examples.
  - Return types, yield types, and variadic arguments (`*args`, `**kwargs`) require consistent docstring conventions.
- **Why Pure File Conversion Fails**:
  - Direct 1-to-1 Markdown-to-RST converters produce malformed references and broken cross-links.
  - Using **Sphinx with MyST-Parser** preserves source Markdown while leveraging Sphinx's superior autodoc and cross-referencing capabilities.
