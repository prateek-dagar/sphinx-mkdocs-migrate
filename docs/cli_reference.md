# CLI Reference

The `sphinx-migrate` CLI provides the following subcommands:

## `sphinx-migrate analyze`

Factual inspection of an MkDocs documentation project.

```bash
sphinx-migrate analyze [PROJECT_PATH] [OPTIONS]
```

**Options:**
* `--json-output`: Output factual analysis report as JSON to stdout.

---

## `sphinx-migrate plan`

Generates a deterministic, read-only `MigrationPlan` without mutating source files.

```bash
sphinx-migrate plan [PROJECT_PATH] [OPTIONS]
```

**Options:**
* `--output-json PATH`: Write canonical machine-readable migration plan JSON to file.
* `--json-output`: Print canonical machine-readable migration plan JSON to stdout.

---

## `sphinx-migrate migrate`

Executes deterministic MyST transformation, Sphinx scaffolding, and validation.

```bash
sphinx-migrate migrate [PROJECT_PATH] [OPTIONS]
```

**Options:**
* `--apply`: Write transformed files and `conf.py` to disk (default is dry-run).
* `--force-conf`: Overwrite existing conflicting `conf.py` if present on disk.
* `--diff`: Display unified diff of document transformations.
* `--validate / --no-validate`: Validate transformed Markdown structure and Sphinx config (default is enabled).
* `--build / --no-build`: Run an actual isolated Sphinx HTML build during validation (default is enabled).
* `--strict`: Fail validation if Sphinx produces any warnings (`-W`).

---

## `sphinx-migrate validate`

Validates existing or migrated Sphinx configuration and documents.

```bash
sphinx-migrate validate [PROJECT_PATH] [OPTIONS]
```

**Options:**
* `--build / --no-build`: Run an actual isolated Sphinx HTML build during validation.
* `--strict`: Fail validation if Sphinx produces any warnings (`-W`).
