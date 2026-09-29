# CLI Reference

`sphinx-migrate` is the primary command-line tool for analyzing, planning, executing, and validating MkDocs-to-Sphinx migrations.

## Synopsis

```bash
sphinx-migrate [GLOBAL_OPTIONS] COMMAND [ARGS]...
```

### Global Options

* `--version`: Show the version and exit.
* `--help`: Show the help message and exit.

---

## `sphinx-migrate analyze`

Performs factual inspection of an MkDocs documentation project, detecting theme features, Markdown extensions, plugins, and dependencies without modifying any files.

```bash
sphinx-migrate analyze [PROJECT_PATH] [OPTIONS]
```

### Arguments

* `PROJECT_PATH`: Path to the MkDocs project directory to inspect. *(Optional, default: `.`)*

### Options

* `--json-output`: Output the factual analysis report as JSON to `stdout` instead of rendering rich tables.
* `--help`: Show this message and exit.

### Example

```bash
# Analyze project in current directory
sphinx-migrate analyze

# Inspect a specific project and export JSON report
sphinx-migrate analyze /path/to/mkdocs-project --json-output > report.json
```

---

## `sphinx-migrate plan`

Generates a deterministic, read-only `MigrationPlan` with provenance tracking for all required dependencies, directive mappings, and configuration proposals without mutating source files.

```bash
sphinx-migrate plan [PROJECT_PATH] [OPTIONS]
```

### Arguments

* `PROJECT_PATH`: Path to the MkDocs project directory. *(Optional, default: `.`)*

### Options

* `--output-json PATH`: Write canonical machine-readable migration plan JSON to the specified file.
* `--json-output`: Print canonical machine-readable migration plan JSON directly to `stdout`.
* `--help`: Show this message and exit.

### Example

```bash
# Generate and display plan in terminal
sphinx-migrate plan

# Export plan to JSON file for CI or automated auditing
sphinx-migrate plan --output-json plan.json
```

---

## `sphinx-migrate migrate`

Executes deterministic MyST transformation, Sphinx scaffolding (`conf.py`, `index.md`, API references), and validation. By default, executes as a **safe dry-run**.

```bash
sphinx-migrate migrate [PROJECT_PATH] [OPTIONS]
```

### Arguments

* `PROJECT_PATH`: Path to the MkDocs project directory. *(Optional, default: `.`)*

### Options

* `--apply`: Write transformed files, scaffolds, and `conf.py` to disk. *(Default is dry-run mode)*
* `--force-conf`: Overwrite existing conflicting `conf.py` if present on disk.
* `--diff`: Display unified color diff of document transformations in terminal output.
* `--validate / --no-validate`: Validate transformed Markdown structure and Sphinx config. *(Default: `--validate`)*
* `--build / --no-build`: Run an actual isolated Sphinx HTML build in a sandbox during validation. *(Default: `--build`)*
* `--strict`: Fail validation if Sphinx produces any warnings (`-W`).
* `--help`: Show this message and exit.

### Examples

```bash
# Preview transformations as diff without modifying disk
sphinx-migrate migrate --diff

# Apply migration and write changes to disk
sphinx-migrate migrate --apply

# Overwrite existing conflicting conf.py and enforce zero warnings
sphinx-migrate migrate --apply --force-conf --strict
```

---

## `sphinx-migrate validate`

Validates existing or migrated Sphinx configuration, document structures, and directive syntax in an isolated sandbox environment.

```bash
sphinx-migrate validate [PROJECT_PATH] [OPTIONS]
```

### Arguments

* `PROJECT_PATH`: Path to the project directory to validate. *(Optional, default: `.`)*

### Options

* `--build / --no-build`: Run an actual isolated Sphinx HTML build during validation. *(Default: `--build`)*
* `--strict`: Fail validation if Sphinx produces any warnings (`-W`).
* `--show-warnings`: Display detailed Sphinx build warnings in the validation report.
* `--help`: Show this message and exit.

### Examples

```bash
# Validate documentation structure and verify Sphinx build
sphinx-migrate validate

# Validate strictly and show all warnings
sphinx-migrate validate --strict --show-warnings
```
