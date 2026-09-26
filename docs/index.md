# sphinx-mkdocs-migrate Documentation

```{toctree}
:maxdepth: 2
:caption: User Guide

getting_started.md
migration_guide.md
cli_reference.md
```

```{toctree}
:maxdepth: 2
:caption: Architecture & Policies

architecture.md
policy_catalog.md
```

## Overview

**`sphinx-mkdocs-migrate`** (`sphinx-migrate`) is a deterministic, version-aware analyzer and migration engine that safely converts MkDocs and Material for MkDocs documentation projects into modern Sphinx + MyST Parser documentation suites.

```bash
pip install sphinx-mkdocs-migrate
```

### Core Features

* **Evidence-Driven Subsystem Analysis**: Inspects `mkdocs.yml`, theme features, Markdown extensions, and plugins.
* **Deterministic, Read-Only Planning**: Generates reproducible migration plans with provenance tracking for all required dependencies.
* **Byte-Preserving Transformation**: Transforms only non-standard construct spans while preserving exact byte-for-byte identity on untouched Markdown.
* **AST-Guided API Migration**: Resolves Python symbols statically without executing untrusted repository code.
* **Dual Validation Engine**: Performs AST structural validation and real isolated Sphinx HTML builds in a sandbox.
