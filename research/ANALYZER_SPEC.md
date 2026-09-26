# Milestone 1: Migration Analyzer (`sphinx-migrate analyze`) Specification

The **Analyzer** is the foundational subsystem of `sphinx-mkdocs-migrate`. Its purpose is to scan an existing repository, deterministically detect all documentation features, dependencies, CI/CD, and hosting configurations, and produce a structured, actionable migration report without making destructive file edits.

---

## 🔍 Analyzer Subsystems

```text
                             Repository Root
                                    │
          ┌─────────────────────────┼────────────────────────┐
          ▼                         ▼                        ▼
  1. Config & Project        2. Docs AST / Content      3. CI/CD & Hosting
     - mkdocs.yml               - Markdown files (*.md)    - .github/workflows/
     - pyproject.toml           - Admonitions / Directives - .readthedocs.yaml
     - uv.lock / requirements   - pymdownx extensions      - GitHub Pages configs
     - plugins & theme info     - mkdocstrings usages      - Makefile / scripts
          │                         │                        │
          └─────────────────────────┼────────────────────────┘
                                    ▼
                         Deterministic Classifier
                                    │
                                    ▼
                     Migration Report / Plan (CLI/JSON)
```

---

## 🏷️ Deterministic Classifications

Every detected item is classified into one of four states:

1. `PRESERVE`: Compatible as-is with MyST/Sphinx without structural changes (e.g. Standard CommonMark, standard tables, code blocks).
2. `TRANSFORM`: Can be deterministically converted by our engine (e.g. `nav:` $\rightarrow$ `toctree`, `!!! note` $\rightarrow$ MyST `{note}`, `=== "Tab"` $\rightarrow$ MyST `{tab-item}`).
3. `MANUAL`: Requires explicit developer decision/intervention (e.g. custom MkDocs plugins with no Sphinx counterpart, complex dynamic hooks).
4. `UNSUPPORTED`: Not supported in Sphinx/MyST ecosystem.

---

## 📋 Research Deliverables Needed for Analyzer Implementation

1. **Project Analyses (`research/projects/`)**:
   Analyze 10 representative MkDocs repositories across different sizes and plugin ecosystems.
2. **Construct Mapping Rules (`research/constructs/`)**:
   Regex patterns, AST tokens, and exact syntax signatures for all Markdown/MkDocs constructs to feed into the scanner engine.
3. **Dependency & CI Heuristics (`research/dependencies.md`, `research/ci.md`)**:
   Detection rules for docs dependencies across `uv`, `poetry`, `pip`, `nox`, and deployment workflows.
