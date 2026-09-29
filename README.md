# sphinx_mkdocs_migrate

[![PyPI version](https://img.shields.io/badge/pypi-0.0.1.dev0-blue.svg)](https://pypi.org/project/sphinx-mkdocs-migrate/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**`sphinx-mkdocs-migrate`** (`sphinx-migrate`) is a deterministic, evidence-driven analyzer and migration engine that safely converts MkDocs and Material for MkDocs documentation projects to Sphinx + MyST Parser.

---

## Key Principles & Design Boundaries

### What `sphinx-migrate` Does
* **Evidence-Driven Subsystem Analysis**: Inspects `mkdocs.yml`, directory structures, theme features, Markdown extensions, and plugins.
* **Deterministic, Read-Only Planning**: Generates a canonical `MigrationPlan` with stable hashes and provenance tracking for every extension and package.
* **Byte-Preserving Transformation**: Transforms only specific non-standard syntax spans (e.g. tabs, dropdowns, includes) into native MyST/Sphinx directives while guaranteeing byte-for-byte identity on untouched Markdown.
* **AST-Guided API Migration**: Resolves Python symbols statically (`ast.parse`) without executing untrusted repository code. Conservative manual boundary for re-exports and ambiguities.
* **Dual Validation Engine**: Performs structural Markdown AST validation and real isolated Sphinx HTML builds in an isolated sandbox.

### What `sphinx-migrate` Does NOT Do
* **No Speculative Heuristics**: If a syntax construct or custom plugin cannot be deterministically mapped, it is routed to `MANUAL` or `UNSUPPORTED` rather than guessed.
* **No Source Code Mutation**: Does not rewrite Python `.py` source code or docstrings.
* **Source-Faithful Theme Mapping**: Material for MkDocs maps to `sphinx_immaterial`; the planned target theme and its package are preserved in generated `conf.py` rather than being silently replaced during validation.
* **Build Success != Runtime Equivalence**: A successful Sphinx build proves structural and buildability correctness; it does not guarantee visual or JavaScript runtime identity with MkDocs Material.

---

## Installation

```bash
pip install sphinx-mkdocs-migrate
```

---

## CLI Workflow

The migration lifecycle consists of 4 distinct commands:

```text
sphinx-migrate analyze   # 1. Factual project & subsystem inspection
       ↓
sphinx-migrate plan      # 2. Deterministic, read-only MigrationPlan generation
       ↓
sphinx-migrate migrate   # 3. Dry-run diffing or atomic disk transformation
       ↓
sphinx-migrate validate  # 4. AST validation & isolated sandbox Sphinx build
```

### 1. Project Inspection (`analyze`)
```bash
sphinx-migrate analyze path/to/project
# Machine-readable JSON output:
sphinx-migrate analyze path/to/project --json-output
```

### 2. Migration Planning(`plan`)
```bash
# Human-readable summary with Rich tables:
sphinx-migrate plan path/to/project

# Export canonical plan JSON:
sphinx-migrate plan path/to/project --output-json plan.json
```

### 3. Transformation & Scaffolding (`migrate`)
```bash
# Dry-run with unified diff preview (no disk mutations):
sphinx-migrate migrate path/to/project --diff

# Apply changes to disk and scaffold conf.py:
sphinx-migrate migrate path/to/project --apply

# Overwrite conflicting existing conf.py:
sphinx-migrate migrate path/to/project --apply --force-conf
```

### 4. Build Validation(`validate`)
```bash
# Full isolated sandbox Sphinx build:
sphinx-migrate validate path/to/project --build

# Strict mode (fail on any Sphinx warnings):
sphinx-migrate validate path/to/project --build --strict
```

---

## Supported Feature Policies

| Source Feature | Category | Action | Target / Resolution | Provenance |
| :--- | :--- | :--- | :--- | :--- |
| `content.code.copy` | `THEME_FEATURE` | `ENABLE_EXTENSION` | `sphinx_copybutton` / `sphinx-copybutton>=0.5.2` | `FEATURE_POLICY` |
| `content.tabs.link` | `THEME_FEATURE` | `ENABLE_EXTENSION` | `sphinx_design` / `sphinx-design>=0.5.0` | `FEATURE_POLICY` |
| `pymdownx.tabbed` | `MARKDOWN_EXTENSION` | `TRANSFORM` | `sphinx-design` (`{tab-set}`, `{tab-item}`) | `EXTENSION_POLICY` |
| `pymdownx.details` | `MARKDOWN_EXTENSION` | `TRANSFORM` | `sphinx-design` (`{dropdown}`) | `EXTENSION_POLICY` |
| `pymdownx.superfences` | `MARKDOWN_EXTENSION` | `PRESERVE` | MyST `colon_fence` | `EXTENSION_POLICY` |
| `pymdownx.arithmatex` | `MARKDOWN_EXTENSION` | `PRESERVE` | MyST `dollarmath` | `EXTENSION_POLICY` |
| `pymdownx.snippets` | `MARKDOWN_EXTENSION` | `TRANSFORM` | MyST `{include}` / `literalinclude` | `EXTENSION_POLICY` |
| `pymdownx.emoji` | `MARKDOWN_EXTENSION` | `MANUAL` | Manual review of icon shortcodes (`:smile:`) | `MANUAL` |
| `mkdocstrings` | `PLUGIN` | `TRANSFORM` | `sphinx.ext.autodoc` + `sphinx.ext.napoleon` | `EXTENSION_POLICY` |
| `search.share` | `THEME_FEATURE` | `UNSUPPORTED` | No static Sphinx HTML equivalent | `UNSUPPORTED` |

---

## Roadmap & Future Evolution

While `sphinx-mkdocs-migrate` is currently focused on high-fidelity migration from **MkDocs to Sphinx + MyST**, our planned roadmap includes full bi-directional support:

* **Phase 1 (Current)**: Full-fidelity MkDocs & Material for MkDocs ➔ Sphinx + MyST migration with 100% AST byte preservation.
* **Phase 2 (Bi-Directional)**: Reverse migration (Sphinx + MyST ➔ MkDocs + Material).

See our full [**Roadmap Document**](docs/roadmap.md) for details.

---

## Contributors

Thank you to everyone who has contributed to `sphinx-mkdocs-migrate`!

Please see our [**Contributors List**](docs/contributors.md) for the full list of contributors.

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
