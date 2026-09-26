# Dependency Management Migration Specification

This specification defines how the analyzer detects existing documentation tooling in the project's dependency manifests and plans the transition to Sphinx.

---

## 1. Supported Manifest Formats

| Format | Detection Path | Target Section |
| :--- | :--- | :--- |
| **PEP 621 / uv / Hatch** | `pyproject.toml` | `[dependency-groups.docs]` or `[project.optional-dependencies.docs]` |
| **Poetry** | `pyproject.toml` | `[tool.poetry.group.docs.dependencies]` |
| **Pip Requirements** | `requirements*.txt` / `docs/requirements.txt` | File entries |
| **Tox / Nox** | `tox.ini` / `noxfile.py` | Doc environment definitions |

---

## 2. Package Replacement Matrix

| MkDocs Package to Remove | Sphinx Ecosystem Replacement | Purpose |
| :--- | :--- | :--- |
| `mkdocs` | `sphinx` | Core documentation engine |
| `mkdocs-material` | `sphinx-immaterial` (or `furo`) | Theme & Material design system |
| `mkdocstrings` / `mkdocstrings-python` | `sphinx.ext.autodoc` + `sphinx.ext.napoleon` | Python API docstring extraction |
| `pymdown-extensions` (tabbed, details) | `sphinx-design` + `myst-parser` | Content tabs, dropdowns, badges, grids |
| `mkdocs-mermaid2-plugin` | `sphinxcontrib-mermaid` | Mermaid diagram rendering |
| `mike` | `sphinx-multiversion` / Read the Docs | Multi-version documentation builds |
| *(None - New Requirement)* | `myst-parser` | Native CommonMark/MyST markdown support |

---

## 3. Safe Mutation Policy

The analyzer **never automatically mutates dependency files**. It outputs:
- A clear list of detected packages to be pruned.
- The corresponding replacement dependency specification.
- Requires explicit user confirmation during the `plan`/`migrate` phase.
