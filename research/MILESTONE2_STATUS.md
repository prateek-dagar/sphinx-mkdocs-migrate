# Milestone 2: Research Dataset & Analyzer Prototype Review

## Current Status: Prototype Complete (Ready for Architecture Refinement)

### 1. What is Completed:
- **Research Dataset (9 Repositories Analyzed)**: `python-json-logger`, `HTTPX`, `Pydantic`, `FastAPI`, `Polars`, `Ruff`, `MkDocs`, `Material for MkDocs`, `pyjanitor`.
- **Subsystem-based Reporting**: Replaced quantitative `compatibility_score` with structured statuses (`AUTOMATIC`, `PRESERVED`, `REVIEW`, `MANUAL`).
- **Initial Multi-Surface Scanner**: Working prototype scanning config, doc files, dependency manifests, and CI workflows.
- **Compatibility Specifications**: Added documentation for Markdown, Navigation, and API Documentation mappings.

---

### 2. Known Limitations & Technical Debt in Prototype:

1. **Manifest Parsing**:
   - *Current*: Quick regexes over raw `pyproject.toml` / `requirements.txt`.
   - *Target*: Proper TOML parsing (`tomllib` / `tomli`) traversing PEP 621 `project.dependencies`, `dependency-groups.docs`, and Poetry sections.
2. **Markdown Parsing & AST**:
   - *Current*: Line-by-line regex scanning.
   - *Target*: Block-aware token/AST parser (e.g. `markdown-it-py` / `mistletoe`) capable of understanding indented fence blocks, nested admonitions, and multiline table structures without regex fragility.
3. **Subsystem Modularity**:
   - *Current*: Monolithic `scanner.py`.
   - *Target*: Independent analyzers (`dependencies.py`, `markdown.py`, `navigation.py`, `ci.py`, `api.py`).

---

### 3. Immediate Next Steps:
- Refactor `scanner.py` into dedicated subsystem analyzers.
- Upgrade `pyproject.toml` inspection to use standard TOML parsing.
- Implement AST-aware block scanner for Markdown files.
