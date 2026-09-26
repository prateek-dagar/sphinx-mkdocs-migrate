# sphinx-migrate Migration Guide

This guide explains how `sphinx-migrate` converts MkDocs and Material for MkDocs projects into modern Sphinx + MyST Parser documentation suites, and outlines the deliberate boundaries between automated transformation, source preservation, and manual developer review.

---

## 1. Core Concepts & Equivalences

| MkDocs / Material Concept | Sphinx + MyST Equivalent | Automation Status |
| :--- | :--- | :--- |
| `mkdocs.yml` (Configuration) | `docs/conf.py` (Sphinx config) | Automated (new) / Preserved (if existing conflict) |
| `nav:` hierarchy | `{toctree}` directives in `index.md` | Automated (deterministic, order-preserving) |
| Tabs (`pymdownx.tabbed`) | `{tab-set}` & `{tab-item}` (sphinx-design) | Automated (byte-preserving transformation) |
| Dropdowns (`pymdownx.details`) | `{dropdown}` (sphinx-design) | Automated (byte-preserving transformation) |
| Nested fences (`pymdownx.superfences`) | MyST 4+ backticks or `:::` colon_fence | Automated / Native MyST |
| Math (`pymdownx.arithmatex`) | MyST `dollarmath` extension | Automated config enablement |
| File snippets (`pymdownx.snippets`) | MyST `{include}` / `literalinclude` | Document transformation required |
| API Reference (`mkdocstrings`) | `sphinx.ext.autodoc` + `sphinx.ext.napoleon` | Static AST resolved (see Section 3) |

---

## 2. Theme Migration Policy

The migration engine explicitly separates theme selection from feature-level dependency derivation:
* **Material for MkDocs** maps to a configurable Sphinx 8/9 compatible theme proposal (defaulting to `furo`), not an automatic bundle of `sphinx-immaterial`.
* **ReadTheDocs / MkDocs default** maps to `sphinx_rtd_theme`.
* **Custom Themes** route to `MANUAL` review.

Features (such as `content.code.copy`) are derived independently via the Declarative Policy Engine (e.g. `sphinx-copybutton`) if and only if explicitly present in the source config.

---

## 3. API Documentation & Static Symbol Resolution

Mkdocstrings directives (`::: package.module.Symbol`) are analyzed statically using Python AST inspection (zero untrusted code execution):

1. **MODULE, CLASS, FUNCTION, METHOD, ATTRIBUTE** (`STATICALLY_RESOLVED`):
   * Maps to Sphinx directive candidates:
     * `MODULE`    -> `automodule`
     * `CLASS`     -> `autoclass`
     * `FUNCTION`  -> `autofunction`
     * `METHOD`    -> `automethod`
     * `ATTRIBUTE` -> `autodata`
2. **REEXPORT, AMBIGUOUS, UNRESOLVED**:
   * Routes conservatively to `MANUAL` review. Source Markdown constructs are preserved byte-for-byte without speculative mutations.

---

## 4. Manual Review Items

Every manual review item generated in `plan.json` and CLI output explicitly answers:
1. **WHAT** was detected;
2. **WHERE** it was detected;
3. **WHY** it cannot be automated;
4. **WHAT REMEDIATION** is required;
5. **WHAT SOURCE** was preserved byte-for-byte.
