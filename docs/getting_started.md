# Getting Started

## Installation

Install `sphinx-mkdocs-migrate` via `pip`:

```bash
pip install sphinx-mkdocs-migrate
```

## Quick Start Workflow

The migration lifecycle consists of 4 distinct commands:

```text
sphinx-migrate analyze   # 1. Subsystem inspection
       ↓
sphinx-migrate plan      # 2. Deterministic planning
       ↓
sphinx-migrate migrate   # 3. Code transformation
       ↓
sphinx-migrate validate  # 4. Sandbox Sphinx build
```

### Step 1: Analyze
Inspect an existing MkDocs project to detect themes, extensions, and plugins:

```bash
sphinx-migrate analyze path/to/project
```

### Step 2: Plan
Generate a deterministic migration plan:

```bash
# View summary with Rich tables:
sphinx-migrate plan path/to/project

# Export canonical machine-readable JSON plan:
sphinx-migrate plan path/to/project --output-json plan.json
```

### Step 3: Migrate
Transform documentation files, scaffold Sphinx `conf.py`, and manage dependencies:

```bash
# Dry-run with unified diffs (no disk changes):
sphinx-migrate migrate path/to/project --diff

# Apply transformations with interactive review & dependency prompts:
sphinx-migrate migrate path/to/project --apply

# Apply non-interactively (e.g. in CI/CD or scripts):
sphinx-migrate migrate path/to/project --apply -y
```

> [!TIP]
> When constructs require manual review (such as unmapped custom directives or macros), `sphinx-migrate migrate` interactively prompts you to either keep original content, comment out the block (`<!-- MANUAL_REVIEW: ... -->`), or enter a custom MyST replacement. In CI/CD pipelines, pass `-y` to safely default to keeping original content without prompting.

### Step 4: Validate
Validate the converted Sphinx project in an isolated sandbox build:

```bash
sphinx-migrate validate path/to/project --build
```
