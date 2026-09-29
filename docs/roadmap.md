# Roadmap & Future Vision

`sphinx-mkdocs-migrate` is built around a compiler architecture: parsing documentation suites into syntax-neutral Intermediate Representation (`DocumentIR` and `DocumentFlow`), applying policy rules, and generating target documentation structures.

This design enables a structured, multi-phase roadmap towards universal documentation translation.

---

## Phase 1: MkDocs to Sphinx + MyST (Current Focus)

- [x] Static AST inspection of `mkdocs.yml`, theme configuration, and plugins.
- [x] Syntax-preserving transform rules for PyMdown Extensions (tabs, dropdowns, code blocks, math).
- [x] Static Python symbol extraction without executing arbitrary repository code.
- [x] Deterministic, declarative `MigrationPlan` with provenance tracking.
- [x] Dual validation engine with isolated sandbox Sphinx HTML builds.

---

## Phase 2: Bi-Directional Conversion (Sphinx ➔ MkDocs)

- [ ] **Reverse Migration Engine**: Translate Sphinx `conf.py` and MyST / RST documentation back into `mkdocs.yml` and Material for MkDocs.
- [ ] Bidirectional CLI support:
  ```bash
  sphinx-migrate plan --from sphinx --to mkdocs
  sphinx-migrate migrate --apply
  ```
- [ ] Direct conversion of Sphinx directives (`{tab-set}`, `{dropdown}`, autodoc) into PyMdown and `mkdocstrings` equivalents.
