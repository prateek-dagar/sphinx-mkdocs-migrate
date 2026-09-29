"""Consolidated scenario-based documentation migration validation tests.

Tests deterministic migration across all key structural and configuration scenarios:
1. Scenario Material Full: Material theme, navigation sections, code copy, admonitions, tabs, dropdowns, mermaid, snippets, API directive.
2. Scenario RTD Minimal: ReadTheDocs theme, sync/async sections, snippet includes.
3. Scenario Material Tabs & Validation: Material theme, validation tabs, details dropdowns, API symbol.
4. Scenario Math & Multi-language: dollarmath, multi-language tabs, mermaid diagram.
5. Scenario Rule Tabs & Config: Rule tabs, admonitions, code highlight sections.
6. Scenario Core Definitions: def_list mapping, readthedocs theme, plugin manual review.
7. Scenario Material Reference: dropdowns, tabs, overrides directory.
8. Scenario RTD Functions: ReadTheDocs theme, snippets, manual function symbols.
9. Scenario Multi-version Tabs: Multi-version tabs, external snippets, dropdowns.
"""

from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.validator.verifier import TransformationValidator


def create_synthetic_project(
    tmp_path: Path, config_yaml: str, files: dict[str, str]
) -> Path:
    """Helper to build a self-contained in-memory documentation project."""
    (tmp_path / "mkdocs.yml").write_text(config_yaml, encoding="utf-8")
    for rel_path, content in files.items():
        file_p = tmp_path / rel_path
        file_p.parent.mkdir(parents=True, exist_ok=True)
        file_p.write_text(content, encoding="utf-8")
    return tmp_path


def test_scenario_material_full_pipeline(tmp_path):
    """Scenario 1: Material theme, sections, copy button, admonitions, tabs, dropdowns, mermaid, snippets, API directive."""
    cfg = """site_name: sample-material-doc
site_description: Synthetic documentation project for migration testing
theme:
  name: material
  features:
    - navigation.sections
    - content.code.copy
markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.snippets
  - pymdownx.arithmatex:
      generic: true
nav:
  - Home: index.md
  - Guide:
      - Quickstart: guide/quickstart.md
      - Customizing: guide/customizing.md
  - API Reference: api.md
"""
    files = {
        "docs/index.md": """# Sample Project

Documentation project for structured pipelines.

!!! info "Overview"
    Outputs structured content.

=== "Option A"
    ```python
    import sample
    ```

=== "Option B"
    ```python
    import legacy_sample
    ```

See our [Quickstart Guide](guide/quickstart.md).
""",
        "docs/guide/quickstart.md": """# Quickstart

Get up and running in minutes.

???+ tip "Configuration Tip"
    You can specify custom fields easily.

--8<-- "examples/demo.py"
""",
        "docs/guide/customizing.md": """# Customizing

Customize pipeline behavior.

```mermaid
graph TD;
    A[Source]-->B[Formatter];
    B-->C[Output];
```
""",
        "docs/api.md": """# API Reference

::: sample.formatter.PipelineFormatter
""",
        "docs/examples/demo.py": """print('hello')\n""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-material-doc"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_immaterial"
    assert "dollarmath" in plan.proposed_sphinx_config.myst_enable_extensions
    assert "colon_fence" in plan.proposed_sphinx_config.myst_enable_extensions

    assert plan.summary.transform_count >= 4
    assert plan.summary.manual_count == 1

    req_exts = plan.get_required_extensions()
    assert "sphinx_design" in req_exts
    assert "sphinxcontrib.mermaid" in req_exts
    assert "myst_parser" in req_exts

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 4
    assert report.documents_changed == 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(
        report, run_sphinx_build=True, strict_warnings=False
    )
    assert v_report.passed is True
    assert v_report.commonmark_parse_successful is True


def test_scenario_rtd_theme_pipeline(tmp_path):
    """Scenario 2: ReadTheDocs theme mapping, sync/async sections, snippet includes."""
    cfg = """site_name: sample-rtd-doc
theme:
  name: readthedocs
markdown_extensions:
  - admonition
  - pymdownx.superfences
  - pymdownx.snippets
nav:
  - Overview: index.md
  - Async Support: async.md
  - Compatibility: compatibility.md
"""
    files = {
        "docs/index.md": """# Sample RTD

Client library for HTTP requests.

!!! note "Installation"
    Install with pip.
""",
        "docs/async.md": """# Async Support

Support for asynchronous operations.

!!! tip "Concurrency"
    Async is fast.
""",
        "docs/compatibility.md": """# Compatibility

Compatibility matrices across runtimes.
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-rtd-doc"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_rtd_theme"
    assert plan.summary.transform_count == 2
    assert plan.summary.manual_count == 0

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 3
    assert report.documents_changed == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(
        report, run_sphinx_build=True, strict_warnings=False
    )
    assert v_report.passed is True


def test_scenario_material_tabs_and_api(tmp_path):
    """Scenario 3: Material theme, tabs, dropdowns, and API symbol review."""
    cfg = """site_name: sample-validation-doc
theme:
  name: material
markdown_extensions:
  - admonition
  - pymdownx.tabbed
  - pymdownx.details
  - pymdownx.snippets
  - pymdownx.superfences
nav:
  - Concepts: index.md
  - Validation: validation.md
  - API: api.md
"""
    files = {
        "docs/index.md": """# Concepts

Data validation and settings management.

!!! tip "Performance"
    Compiled core for high speed.
""",
        "docs/validation.md": """# Validation

Validate types and data structures.

=== "Standard"
    ```python
    def check(): pass
    ```

=== "Strict"
    ```python
    def strict_check(): pass
    ```
""",
        "docs/api.md": """# API Reference

::: sample.models.BaseModel
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-validation-doc"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_immaterial"
    assert plan.summary.transform_count >= 2
    assert plan.summary.manual_count == 1

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(
        report, run_sphinx_build=True, strict_warnings=False
    )
    assert v_report.passed is True


def test_scenario_math_and_multilang_tabs(tmp_path):
    """Scenario 4: dollarmath detection, multi-language tabs, mermaid diagram."""
    cfg = """site_name: sample-math-doc
theme:
  name: material
markdown_extensions:
  - admonition
  - pymdownx.tabbed
  - pymdownx.superfences
  - pymdownx.arithmatex:
      generic: true
nav:
  - Introduction: index.md
  - Expressions: expressions.md
"""
    files = {
        "docs/index.md": """# User Guide

High performance dataframe library.

$$
f(x) = x^2 + 2x + 1
$$

=== "Python"
    ```python
    x = 1
    ```

=== "Rust"
    ```rust
    let x = 1;
    ```
""",
        "docs/expressions.md": """# Expressions

Expression syntax and evaluation.

```mermaid
graph LR;
    A-->B;
```
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-math-doc"
    assert "dollarmath" in plan.proposed_sphinx_config.myst_enable_extensions

    req_exts = plan.get_required_extensions()
    assert "sphinx_design" in req_exts
    assert "sphinxcontrib.mermaid" in req_exts

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2
    assert report.total_transforms_executed >= 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True


def test_scenario_rule_tabs_and_config(tmp_path):
    """Scenario 5: rule tabs, admonitions, inline highlight configuration."""
    cfg = """site_name: sample-linter-doc
theme:
  name: material
markdown_extensions:
  - admonition
  - pymdownx.tabbed
  - pymdownx.superfences
  - pymdownx.inlinehilite
nav:
  - Overview: index.md
  - Rules: rules.md
  - Configuration: configuration.md
"""
    files = {
        "docs/index.md": """# Linter Guide

Extremely fast Python linter.

!!! note "Performance"
    Written in Rust.
""",
        "docs/rules.md": """# Rules

=== "CLI"
    ```bash
    lint check
    ```

=== "Config"
    ```toml
    [lint]
    select = ["E"]
    ```
""",
        "docs/configuration.md": """# Configuration

Configure via pyproject.toml.

!!! warning "Deprecated Flags"
    Avoid legacy flags.
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-linter-doc"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_immaterial"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 3
    assert report.total_transforms_executed >= 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True


def test_scenario_definition_lists_and_plugins(tmp_path):
    """Scenario 6: def_list extension mapping, readthedocs theme, plugin manual review."""
    cfg = """site_name: sample-core-doc
theme:
  name: readthedocs
markdown_extensions:
  - admonition
  - def_list
nav:
  - User Guide: index.md
  - Plugins: plugins.md
"""
    files = {
        "docs/index.md": """# Project Guide

Project documentation.

Term 1
: Definition 1

!!! note "Important"
    Read carefully.
""",
        "docs/plugins.md": """# Plugins

Plugin interfaces.
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-core-doc"
    assert "deflist" in plan.proposed_sphinx_config.myst_enable_extensions
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_rtd_theme"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True


def test_scenario_theme_overrides_and_tabs(tmp_path):
    """Scenario 7: dropdowns, tabs, theme overrides detection."""
    cfg = """site_name: sample-theme-ref
theme:
  name: material
  custom_dir: overrides
markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.tabbed
  - pymdownx.snippets
  - pymdownx.superfences
nav:
  - Reference: index.md
  - Customization: customization.md
"""
    files = {
        "docs/index.md": """# Reference

Technical documentation that simply works.

???+ tip "Dark Mode"
    Supports instant color palette switching.

=== "HTML"
    ```html
    <div>Content</div>
    ```

=== "Markdown"
    ```markdown
    # Title
    ```
""",
        "docs/customization.md": """# Customization

Override theme templates via Jinja2.

!!! note "Overrides"
    Check overrides directory.
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-theme-ref"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_immaterial"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True


def test_scenario_rtd_functions_and_snippets(tmp_path):
    """Scenario 8: ReadTheDocs theme, snippets, manual function symbols."""
    cfg = """site_name: sample-rtd-functions
theme:
  name: readthedocs
markdown_extensions:
  - admonition
  - pymdownx.snippets
nav:
  - Welcome: index.md
  - Functions: functions.md
"""
    files = {
        "docs/index.md": """# Function Reference Sample

Clean helper APIs for data processing pipelines.

!!! note "Method Pipeline"
    Extends generic processing pipelines with function utilities.
""",
        "docs/functions.md": """# Functions

API references for helper utilities.

::: sample.functions.clean_names
""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-rtd-functions"
    assert plan.summary.manual_count == 1
    assert plan.summary.transform_count == 1

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True


def test_scenario_multiversion_tabs_and_snippets(tmp_path):
    """Scenario 9: Multi-version tabs, external snippets inclusion, dropdowns."""
    cfg = """site_name: sample-multiversion-app
theme:
  name: material
markdown_extensions:
  - admonition
  - pymdownx.tabbed
  - pymdownx.details
  - pymdownx.snippets
  - pymdownx.superfences
nav:
  - Tutorial: index.md
  - Query Parameters: query.md
"""
    files = {
        "docs/index.md": """# App Guide

High performance, easy to learn, fast to code.

!!! tip "Interactive Docs"
    Automatic UI documentation.

=== "Python 3.10+"
    ```python
    app = make_app()
    ```

=== "Python 3.8+"
    ```python
    from typing import Optional
    app = make_app()
    ```
""",
        "docs/query.md": """# Parameters

Define optional parameters with default values.

??? info "Default Values"
    Parameters without default values are required.

--8<-- "docs_src/quickstart/demo.py"
""",
        "docs_src/quickstart/demo.py": """app = make_app()\n""",
    }
    project_dir = create_synthetic_project(tmp_path, cfg, files)
    planner = MigrationPlanner(project_dir)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "sample-multiversion-app"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_immaterial"

    req_exts = plan.get_required_extensions()
    assert "sphinx_design" in req_exts

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2
    assert report.total_transforms_executed >= 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True
