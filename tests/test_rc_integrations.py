"""Dedicated regression tests for Release Candidate integration edge cases discovered in fresh clones."""
import tempfile
from pathlib import Path
import pytest
from sphinx_mkdocs_migrate.analyzer.models import NavigationItem, NavigationAnalysis
from sphinx_mkdocs_migrate.planner.models import MigrationPlan, ConfigMigrationProposal, ThemeMigrationProposal, MigrationPlanMetadata
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.validator.verifier import TransformationValidator

def test_literate_nav_wildcard_with_existing_index():
    """Verify literate-nav '... | reference/pkg/*' resolves to 'reference/pkg/index' when index.md exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")
        ref_dir = docs_dir / "reference" / "pkg"
        ref_dir.mkdir(parents=True)
        (ref_dir / "index.md").write_text("# Reference Index\n", encoding="utf-8")
        (ref_dir / "module_a.md").write_text("# Module A\n", encoding="utf-8")

        nav_tree = [
            NavigationItem(title="Home", path="index.md"),
            NavigationItem(title="Reference", path="... | reference/pkg/*")
        ]
        nav_analysis = NavigationAnalysis(has_nav=True, raw_nav_entries=[], tree=nav_tree)
        theme = ThemeMigrationProposal(
            source_theme="material",
            target_theme="furo",
            target_package="furo>=2024.1.0",
            rationale="Modern theme mapping"
        )
        plan = MigrationPlan(
            project_root=str(tmp_path),
            source_mkdocs_config=None,
            navigation_analysis=nav_analysis,
            proposed_sphinx_config=ConfigMigrationProposal(project_name="TestProject", theme=theme),
            metadata=MigrationPlanMetadata(generated_at="2026-09-27T00:00:00Z")
        )

        engine = TransformationEngine(plan)
        toctree = engine._generate_semantic_toctree(nav_tree, list(docs_dir.rglob("*.md")), docs_dir)
        assert toctree is not None
        assert "reference/pkg/index" in toctree
        assert "... |" not in toctree

def test_literate_nav_wildcard_without_index_expands_children():
    """Verify literate-nav '... | api/*' expands alphabetical child documents when no index.md exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")
        api_dir = docs_dir / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "beta.md").write_text("# Beta\n", encoding="utf-8")
        (api_dir / "alpha.md").write_text("# Alpha\n", encoding="utf-8")

        nav_tree = [
            NavigationItem(title="Home", path="index.md"),
            NavigationItem(title="API", path="... | api/*")
        ]
        nav_analysis = NavigationAnalysis(has_nav=True, raw_nav_entries=[], tree=nav_tree)
        theme = ThemeMigrationProposal(
            source_theme="material",
            target_theme="furo",
            target_package="furo>=2024.1.0",
            rationale="Modern theme mapping"
        )
        plan = MigrationPlan(
            project_root=str(tmp_path),
            source_mkdocs_config=None,
            navigation_analysis=nav_analysis,
            proposed_sphinx_config=ConfigMigrationProposal(project_name="TestProject", theme=theme),
            metadata=MigrationPlanMetadata(generated_at="2026-09-27T00:00:00Z")
        )

        engine = TransformationEngine(plan)
        toctree = engine._generate_semantic_toctree(nav_tree, list(docs_dir.rglob("*.md")), docs_dir)
        assert toctree is not None
        # Must expand sorted children
        assert "api/alpha" in toctree
        assert "api/beta" in toctree
        assert "... |" not in toctree

def test_heading_anchors_and_cross_reference_resolution():
    """Verify that MyST heading anchors allow cross-document header links to compile without xref_missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.md").write_text(
            "# Home\n\n"
            "Check [Step 2](guide.md#step-two-details).\n",
            encoding="utf-8"
        )
        (docs_dir / "guide.md").write_text(
            "# Guide\n\n"
            "## Step One\n\n"
            "First step text.\n\n"
            "## Step Two Details\n\n"
            "Second step details.\n",
            encoding="utf-8"
        )

        nav_tree = [
            NavigationItem(title="Home", path="index.md"),
            NavigationItem(title="Guide", path="guide.md")
        ]
        nav_analysis = NavigationAnalysis(has_nav=True, raw_nav_entries=[], tree=nav_tree)
        theme = ThemeMigrationProposal(
            source_theme="material",
            target_theme="furo",
            target_package="furo>=2024.1.0",
            rationale="Modern theme mapping"
        )
        plan = MigrationPlan(
            project_root=str(tmp_path),
            source_mkdocs_config=None,
            navigation_analysis=nav_analysis,
            proposed_sphinx_config=ConfigMigrationProposal(
                project_name="HeadingTest",
                theme=theme,
                extensions_to_add=["myst_parser"],
                myst_enable_extensions=["colon_fence"]
            ),
            metadata=MigrationPlanMetadata(generated_at="2026-09-27T00:00:00Z")
        )

        engine = TransformationEngine(plan)
        report = engine.execute(write_to_disk=True)

        validator = TransformationValidator()
        v_report = validator.validate_transformation_report(report, run_sphinx_build=True, strict_warnings=True)
        assert v_report.passed is True
        assert v_report.sphinx_build_successful is True
        assert v_report.sphinx_warning_count == 0

def test_end_to_end_wildcard_migration_and_build():
    """Verify full public migration path (analyze -> plan -> migrate -> strict Sphinx build) with wildcard nav."""
    from sphinx_mkdocs_migrate.analyzer.project import ProjectAnalyzer
    from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.md").write_text("# Home\n\nWelcome to docs.\n", encoding="utf-8")
        
        api_dir = docs_dir / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "alpha.md").write_text("# Alpha API\n\nAlpha details.\n", encoding="utf-8")
        (api_dir / "beta.md").write_text("# Beta API\n\nBeta details.\n", encoding="utf-8")

        mkdocs_yml = tmp_path / "mkdocs.yml"
        mkdocs_yml.write_text(
            "site_name: E2E Wildcard Project\n"
            "theme:\n"
            "  name: material\n"
            "nav:\n"
            "  - Home: index.md\n"
            "  - API:\n"
            "      - ... | api/*\n",
            encoding="utf-8"
        )

        # 1. Analyze
        analyzer = ProjectAnalyzer(tmp_path)
        analysis = analyzer.analyze()
        assert analysis.mkdocs_config is not None
        assert analysis.mkdocs_config.site_name == "E2E Wildcard Project"

        # 2. Plan
        planner = MigrationPlanner(tmp_path)
        plan = planner.create_plan()

        # 3. Migrate
        engine = TransformationEngine(plan)
        report = engine.execute(write_to_disk=True)
        assert report.files_written_to_disk > 0

        # 4. Validate (Strict Sphinx build)
        validator = TransformationValidator()
        v_report = validator.validate_transformation_report(report, run_sphinx_build=True, strict_warnings=True)
        assert v_report.passed is True
        assert v_report.sphinx_build_successful is True
        assert v_report.sphinx_warning_count == 0

