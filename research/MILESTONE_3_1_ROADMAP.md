# Milestone 3.1: Structured Markdown IR & Navigation Subsystem Roadmap

## 🎯 Objective
Upgrade Milestone 3 from a preliminary block recognizer into a structured Markdown Intermediate Representation (IR) and extract a dedicated Navigation Analyzer.

---

## 🛠️ Work Items

### 1. Dedicated `NavigationAnalyzer` (`src/sphinx_mkdocs_migrate/analyzer/navigation.py`)
- Parse the recursive `nav:` tree from `mkdocs.yml`.
- Model navigation nodes (`NavigationItem`, `NavigationSection`, `NavigationTree`).
- Detect document ordering, section hierarchies, and potential orphan documents not registered in `nav`.

### 2. Separation of Findings from Migration Rules (`models.py`)
- Refactor `ConstructFinding` to describe **what exists** (construct type, location, raw token representation, metadata) without coupling it to `target_action`.
- Introduce `MigrationRule` / `TargetAction` mappings as a distinct abstraction layer.

### 3. Structured Markdown IR (`src/sphinx_mkdocs_migrate/parsing/markdown_ir.py`)
- Define an internal, destination-neutral Document IR (`DocumentNode`, `BlockNode`, `InlineNode`).
- Implement an adapter that converts raw Markdown into structured nodes with preserved parent-child hierarchy (e.g. `AdmonitionBlock` $\rightarrow$ children blocks, `TabSetBlock` $\rightarrow$ `TabItemBlock`s).
- Ensure lines inside code fences (` ``` `) are never falsely identified as Markdown headings, admonitions, or directives.

### 4. Comprehensive Nesting & Multi-Line Test Fixtures (`tests/`)
- Test cases for nested admonitions inside tabs.
- Test cases for code blocks containing `!!! note` or `::: symbol` strings.
- Test cases for complex, multi-level navigation trees.
