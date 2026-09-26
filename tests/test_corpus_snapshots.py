"""Phase 4: Real-world multi-repository corpus validation tests."""
import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.analyzer.models import Classification
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.validator.verifier import TransformationValidator

CORPUS_DIR = Path(__file__).parent / "fixtures" / "real_world_corpus"

def test_corpus_python_json_logger():
    """Verify python-json-logger repository snapshot: analysis, planning, provenance, and transforms."""
    repo_path = CORPUS_DIR / "python_json_logger"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "python-json-logger"
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"
    
    # Check syntax extensions derived from pymdownx.arithmatex
    assert "dollarmath" in plan.proposed_sphinx_config.myst_enable_extensions
    assert "colon_fence" in plan.proposed_sphinx_config.myst_enable_extensions

    # Check construct counts & classifications
    assert plan.summary.transform_count >= 4  # Admonitions, tabs, dropdowns, mermaid, snippets
    assert plan.summary.manual_count == 1     # mkdocstrings API reference
    
    # Requirement provenance
    req_exts = plan.get_required_extensions()
    assert "sphinx_design" in req_exts
    assert "sphinxcontrib.mermaid" in req_exts
    assert "myst_parser" in req_exts

    # Transformation execution in dry-run
    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 4
    assert report.documents_changed == 3  # index, quickstart, customizing changed; api has manual
    
    # Validation
    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True, strict_warnings=False)
    assert v_report.passed is True
    assert v_report.commonmark_parse_successful is True

def test_corpus_httpx():
    """Verify HTTPX repository snapshot: ReadTheDocs theme mapping, sync/async docs, clean build."""
    repo_path = CORPUS_DIR / "httpx"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "HTTPX"
    # ReadTheDocs theme maps to sphinx_rtd_theme
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_rtd_theme"
    assert plan.summary.transform_count == 2 # 2 admonitions
    assert plan.summary.manual_count == 0

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 3
    assert report.documents_changed == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True, strict_warnings=False)
    assert v_report.passed is True

def test_corpus_pydantic():
    """Verify Pydantic repository snapshot: Material theme, tabs, dropdowns, and mkdocstrings symbol review."""
    repo_path = CORPUS_DIR / "pydantic"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "Pydantic"
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"
    assert plan.summary.transform_count >= 2
    assert plan.summary.manual_count == 1 # API symbol

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True, strict_warnings=False)
    assert v_report.passed is True

def test_corpus_polars():
    """Verify Polars repository snapshot: dollarmath detection, multi-language tabs, mermaid diagram."""
    repo_path = CORPUS_DIR / "polars"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "Polars User Guide"
    assert "dollarmath" in plan.proposed_sphinx_config.myst_enable_extensions
    
    req_exts = plan.get_required_extensions()
    assert "sphinx_design" in req_exts
    assert "sphinxcontrib.mermaid" in req_exts

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2
    assert report.total_transforms_executed >= 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True

def test_corpus_ruff():
    """Verify Ruff repository snapshot: rule tabs, admonitions, CLI configuration sections."""
    repo_path = CORPUS_DIR / "ruff"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "Ruff Documentation"
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 3
    assert report.total_transforms_executed >= 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True

def test_corpus_mkdocs_core():
    """Verify MkDocs Core snapshot: def_list extension mapping, readthedocs theme, manual plugin review."""
    repo_path = CORPUS_DIR / "mkdocs_core"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "MkDocs"
    assert "deflist" in plan.proposed_sphinx_config.myst_enable_extensions
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_rtd_theme"
    assert plan.summary.manual_count == 1 # plugin API review

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True

def test_corpus_material_reference():
    """Verify Material Reference snapshot: dropdowns, tabs, theme overrides detection."""
    repo_path = CORPUS_DIR / "material_reference"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "Material for MkDocs"
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True

def test_corpus_pyjanitor():
    """Verify pyjanitor snapshot: ReadTheDocs theme, snippets, manual function symbols."""
    repo_path = CORPUS_DIR / "pyjanitor"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "pyjanitor"
    assert plan.summary.manual_count == 1 # function symbol
    assert plan.summary.transform_count == 1 # admonition

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True

def test_corpus_fastapi():
    """Verify FastAPI snapshot: multi-version tabs, external snippets inclusion, dropdowns."""
    repo_path = CORPUS_DIR / "fastapi"
    planner = MigrationPlanner(repo_path)
    plan = planner.create_plan()

    assert plan.source_mkdocs_config.site_name == "FastAPI"
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"
    
    req_exts = plan.get_required_extensions()
    assert "sphinx_design" in req_exts

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    assert report.documents_examined == 2
    assert report.total_transforms_executed >= 3

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=True)
    assert v_report.passed is True
