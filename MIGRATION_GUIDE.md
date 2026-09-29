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
* **Material for MkDocs** maps to `sphinx_immaterial` together with its planned package and theme options. Build and validation paths must use that plan; they must not silently substitute another theme.
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

---

## 5. Build Pipelines, Obsolete Scripts, & Dependency Groups

### 5.1 Generator Script Lifecycle (`mkdocs-gen-files`)
In MkDocs projects, API reference pages and navigation structures were often generated dynamically at build time using the `gen-files` plugin and a script such as `scripts/gen_ref_nav.py`:
- **MkDocs Paradigm**: Relied on runtime generation of in-memory virtual files via `import mkdocs_gen_files` and `mkdocs_gen_files.open(...)`.
- **Sphinx Paradigm**: Sphinx natively builds from persistent filesystem documents using `sphinx.ext.autodoc` and `autosummary`. The migration planner analyzes generator scripts via AST and directly synthesizes deterministic, checked-in MyST markdown files in `docs/reference/`.
- **Post-Migration Cleanup**: Because `mkdocs-gen-files` is removed from project dependencies during migration, generator scripts importing it become broken dead code. The migration engine automatically deletes obsolete generator scripts declared in `mkdocs.yml` (and their enclosing directory if left empty) during `--apply`.
- **Single-Stage Build**: In `tox.ini` and CI workflows, the build command requires only the single standard command:
  ```ini
  commands =
      sphinx-build -b html docs site/_build/html
  ```
  No preceding `python scripts/...` execution step is needed or valid.

### 5.2 Dynamic Dependency Group & Extras Resolution
When configuring `[testenv:docs]` in `tox.ini`, the migration engine detects where documentation packages reside in the source project:
- **PEP 735 (`[dependency-groups]`)**: If dependencies were in a group (e.g. `docs`, `dev`, `documentation`), tox is configured with `dependency_groups = <group_name>`.
- **PEP 621 (`[project.optional-dependencies]`)**: If dependencies were declared as package extras (e.g. `[project.optional-dependencies] docs`), tox is configured with `extras = <extra_name>`.
- **Pip Requirements**: If dependencies are tracked via `docs/requirements.txt` or `requirements.txt`, tox is configured with `deps = -r <file_path>`.
