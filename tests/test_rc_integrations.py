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

def test_generated_package_navigation_stays_nested_under_its_index():
    """A literate-nav package wildcard must not flatten modules into root navigation."""
    from sphinx_mkdocs_migrate.planner.models import GeneratedDocumentProposal, RequirementProvenance

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")

        nav_tree = [
            NavigationItem(title="Home", path="index.md"),
            NavigationItem(
                title="API Reference",
                children=[NavigationItem(title="...", path="... | reference/pythonjsonlogger/*")],
            ),
        ]
        package_index = GeneratedDocumentProposal(
            target_path="docs/reference/pythonjsonlogger/index.md",
            title="pythonjsonlogger",
            content="# pythonjsonlogger\n\n```{toctree}\n:hidden:\n:maxdepth: 1\n\ncore\ndefaults\n```\n",
            generator_plugin="gen-files",
            rationale="test fixture",
            provenance=RequirementProvenance.GENERATED_PIPELINE,
        )
        theme = ThemeMigrationProposal(source_theme="material", target_theme="furo", rationale="test")
        plan = MigrationPlan(
            project_root=str(tmp_path),
            source_mkdocs_config=None,
            navigation_analysis=NavigationAnalysis(has_nav=True, tree=nav_tree),
            generated_documents=[package_index],
            proposed_sphinx_config=ConfigMigrationProposal(project_name="Test", theme=theme),
            metadata=MigrationPlanMetadata(generated_at="2026-09-27T00:00:00Z"),
        )

        report = TransformationEngine(plan).execute(write_to_disk=False)
        root = next(doc for doc in report.transformed_documents if doc.target_file == "docs/index.md")
        generated = next(doc for doc in report.transformed_documents if doc.target_file == package_index.target_path)

        assert "API Reference <reference/pythonjsonlogger/index>" in root.transformed_content
        assert "core" not in root.transformed_content
        assert "defaults" not in root.transformed_content
        assert "core" in generated.transformed_content
        assert "defaults" in generated.transformed_content

def test_nested_index_keeps_its_local_toctree():
    """Site navigation must never replace a package index's child navigation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        package_dir = docs_dir / "reference" / "pkg"
        package_dir.mkdir(parents=True)
        (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")
        package_index = package_dir / "index.md"
        package_index.write_text(
            "# pkg\n\n```{toctree}\n:hidden:\n:maxdepth: 1\n\ncore\n```\n",
            encoding="utf-8",
        )
        (package_dir / "core.md").write_text("# core\n", encoding="utf-8")

        nav_tree = [
            NavigationItem(title="Home", path="index.md"),
            NavigationItem(title="API Reference", path="reference/pkg/index.md"),
        ]
        theme = ThemeMigrationProposal(source_theme="material", target_theme="furo", rationale="test")
        plan = MigrationPlan(
            project_root=str(tmp_path),
            source_mkdocs_config=None,
            navigation_analysis=NavigationAnalysis(has_nav=True, tree=nav_tree),
            proposed_sphinx_config=ConfigMigrationProposal(project_name="Test", theme=theme),
            metadata=MigrationPlanMetadata(generated_at="2026-09-27T00:00:00Z"),
        )

        report = TransformationEngine(plan).execute(write_to_disk=False)
        root = next(doc for doc in report.transformed_documents if doc.target_file == "docs/index.md")
        nested = next(doc for doc in report.transformed_documents if doc.target_file == "docs/reference/pkg/index.md")

        assert "API Reference <reference/pkg/index>" in root.transformed_content
        assert nested.transformed_content == package_index.read_text(encoding="utf-8")

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

def test_theme_properties_and_palette_migration():
    """Verify MkDocs theme palette, colors, logo, favicon, repo info, and extra CSS/JS are migrated into Sphinx conf.py."""
    from sphinx_mkdocs_migrate.analyzer.project import ProjectAnalyzer
    from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "index.md").write_text("# Home\n\nDocs with custom theme properties.\n", encoding="utf-8")

        mkdocs_yml = tmp_path / "mkdocs.yml"
        mkdocs_yml.write_text(
            "site_name: Themed Project\n"
            "site_author: Test Author\n"
            "copyright: 'Copyright 2026 Test Team'\n"
            "repo_url: https://github.com/my-org/my-docs\n"
            "extra_css:\n"
            "  - stylesheets/custom.css\n"
            "extra_javascript:\n"
            "  - javascripts/extra.js\n"
            "theme:\n"
            "  name: material\n"
            "  logo: assets/logo.svg\n"
            "  favicon: assets/favicon.ico\n"
            "  language: en\n"
            "  palette:\n"
            "    - scheme: default\n"
            "      primary: indigo\n"
            "      accent: deep-purple\n"
            "    - scheme: slate\n"
            "      primary: slate\n"
            "      accent: amber\n",
            encoding="utf-8"
        )

        analyzer = ProjectAnalyzer(tmp_path)
        analysis = analyzer.analyze()
        assert analysis.mkdocs_config is not None
        assert analysis.mkdocs_config.theme_logo == "assets/logo.svg"
        assert analysis.mkdocs_config.theme_favicon == "assets/favicon.ico"
        assert len(analysis.mkdocs_config.theme_palette) == 2
        assert analysis.mkdocs_config.extra_css == ["stylesheets/custom.css"]

        planner = MigrationPlanner(tmp_path)
        plan = planner.create_plan()
        opts = plan.proposed_sphinx_config.custom_options
        assert opts["html_logo"] == "assets/logo.svg"
        assert opts["html_favicon"] == "assets/favicon.ico"
        assert opts["html_css_files"] == ["stylesheets/custom.css"]
        assert opts["html_js_files"] == ["javascripts/extra.js"]
        assert opts["copyright"] == "Copyright 2026 Test Team"
        assert opts["author"] == "Test Author"

        theme_opts = opts["html_theme_options"]
        assert theme_opts["repo_url"] == "https://github.com/my-org/my-docs"
        assert theme_opts["repo_name"] == "my-org/my-docs"
        assert len(theme_opts["palette"]) == 2
        assert theme_opts["palette"][0]["primary"] == "indigo"
        assert theme_opts["palette"][0]["accent"] == "deep-purple"
        assert theme_opts["palette"][1]["primary"] == "slate"
        assert theme_opts["palette"][1]["accent"] == "amber"

        engine = TransformationEngine(plan)
        report = engine.execute(write_to_disk=True)
        conf_content = (docs_dir / "conf.py").read_text(encoding="utf-8")
        assert "html_logo = 'assets/logo.svg'" in conf_content
        assert "html_favicon = 'assets/favicon.ico'" in conf_content
        assert "https://github.com/my-org/my-docs" in conf_content

def test_construct_accountability_lifecycle_and_invariants():
    """Verify Construct Accountability lifecycle: non-disappearance, orthogonal dimensions, and manual verification invariant."""
    from sphinx_mkdocs_migrate.planner.accountability import (
        ConstructRecord,
        AccountabilityInventory,
        ConstructDisposition,
        ConstructVerification,
        SourceOccurrence,
        TargetStrategy,
        ManualActionSpec
    )

    inventory = AccountabilityInventory(records=[
        ConstructRecord(
            record_id="rec_001",
            source=SourceOccurrence(kind="admonition", file="docs/index.md", span=(5, 6), occurrence="!!! note"),
            disposition=ConstructDisposition.TRANSFORM,
            target=TargetStrategy(strategy="myst_admonition", emitted="```{note} Title\nbody\n```", target_reference="note"),
            verification=ConstructVerification.VERIFIED,
            manual_action=ManualActionSpec(required=False)
        ),
        ConstructRecord(
            record_id="rec_002",
            source=SourceOccurrence(kind="code_fence", file="docs/async.md", span=(5, 9), occurrence="```python"),
            disposition=ConstructDisposition.PRESERVE,
            target=TargetStrategy(strategy="direct_code_fence", emitted="```python\n...\n```"),
            verification=ConstructVerification.VERIFIED,
            manual_action=ManualActionSpec(required=False)
        ),
        ConstructRecord(
            record_id="rec_003",
            source=SourceOccurrence(kind="api_directive", file="docs/api.md", span=(10, 11), occurrence="::: my_pkg.Client"),
            disposition=ConstructDisposition.MANUAL,
            target=TargetStrategy(strategy="autodoc_directive", emitted=None),
            verification=ConstructVerification.ACCOUNTED,
            manual_action=ManualActionSpec(
                required=True,
                instruction="Review API docstring and select Sphinx autodoc directive.",
                rationale="No automated 1-to-1 mapping exists."
            )
        ),
        ConstructRecord(
            record_id="rec_004",
            source=SourceOccurrence(kind="custom_plugin_tag", file="docs/special.md", span=(20, 22), occurrence="{% special %}"),
            disposition=ConstructDisposition.UNSUPPORTED,
            target=TargetStrategy(strategy="unsupported_fallback", emitted=None),
            verification=ConstructVerification.ACCOUNTED,
            manual_action=ManualActionSpec(
                required=True,
                instruction="Migrate custom template tag manually.",
                rationale="Unsupported plugin construct."
            )
        )
    ])

    # 1. Non-Disappearance Invariant: All 4 constructs accounted for
    assert inventory.total_count == 4
    assert inventory.accounted_count == 4
    assert inventory.verified_count == 2
    assert inventory.manual_count == 2

    # 2. Orthogonal Dispositions
    by_disp = inventory.by_disposition()
    assert by_disp["TRANSFORM"] == 1
    assert by_disp["PRESERVE"] == 1
    assert by_disp["MANUAL"] == 1
    assert by_disp["UNSUPPORTED"] == 1

    # 3. Invariant: MANUAL and UNSUPPORTED constructs remain ACCOUNTED (not magically VERIFIED)
    manual_rec = next(r for r in inventory.records if r.disposition == ConstructDisposition.MANUAL)
    assert manual_rec.verification == ConstructVerification.ACCOUNTED
    assert manual_rec.manual_action.required is True

def test_accountability_failure_paths_and_safety_invariants():
    """Verify all 6 critical safety and failure paths of the Construct Accountability model."""
    from sphinx_mkdocs_migrate.planner.accountability import (
        ConstructRecord,
        AccountabilityInventory,
        ConstructDisposition,
        ConstructVerification,
        SourceOccurrence,
        TargetStrategy,
        ManualActionSpec
    )

    records = [
        # 1. Unknown / Unsupported construct: must exist in inventory with explicit limitation
        ConstructRecord(
            record_id="rec_unsupported_01",
            source=SourceOccurrence(kind="unknown_macro", file="docs/macros.md", span=(15, 17), occurrence="{{ render_macro() }}"),
            disposition=ConstructDisposition.UNSUPPORTED,
            target=TargetStrategy(strategy="unsupported_fallback", emitted=None),
            verification=ConstructVerification.ACCOUNTED,
            manual_action=ManualActionSpec(
                required=True,
                instruction="Unsupported jinja macro requires manual template migration.",
                rationale="Dynamic macro evaluation is not supported in MyST."
            )
        ),
        # 2. Manual construct: ACCOUNTED, can NEVER be automatically marked VERIFIED
        ConstructRecord(
            record_id="rec_manual_01",
            source=SourceOccurrence(kind="api_symbol", file="docs/api.md", span=(4, 5), occurrence="::: mylib.Service"),
            disposition=ConstructDisposition.MANUAL,
            target=TargetStrategy(strategy="autodoc_directive", emitted=None),
            verification=ConstructVerification.ACCOUNTED,
            manual_action=ManualActionSpec(
                required=True,
                instruction="Select sphinx.ext.autodoc directive.",
                rationale="Ambiguous docstring type."
            )
        ),
        # 3. Multiple occurrences of the same kind: each retains independent provenance
        ConstructRecord(
            record_id="rec_fence_01",
            source=SourceOccurrence(kind="code_fence", file="docs/guide.md", span=(10, 15), occurrence="```python"),
            disposition=ConstructDisposition.PRESERVE,
            target=TargetStrategy(strategy="direct_code_fence", emitted="```python\n...\n```"),
            verification=ConstructVerification.VERIFIED,
            manual_action=ManualActionSpec(required=False)
        ),
        ConstructRecord(
            record_id="rec_fence_02",
            source=SourceOccurrence(kind="code_fence", file="docs/guide.md", span=(25, 30), occurrence="```bash"),
            disposition=ConstructDisposition.PRESERVE,
            target=TargetStrategy(strategy="direct_code_fence", emitted="```bash\n...\n```"),
            verification=ConstructVerification.VERIFIED,
            manual_action=ManualActionSpec(required=False)
        ),
        # 4. Configuration construct: seamlessly tracked in same inventory
        ConstructRecord(
            record_id="rec_conf_theme_01",
            source=SourceOccurrence(kind="theme_config", file="mkdocs.yml", span=(2, 3), occurrence="theme: readthedocs"),
            disposition=ConstructDisposition.TRANSFORM,
            target=TargetStrategy(strategy="theme_policy", emitted="html_theme = 'sphinx_rtd_theme'", target_reference="html_theme"),
            verification=ConstructVerification.VERIFIED,
            manual_action=ManualActionSpec(required=False)
        ),
        # 5. Nav Configuration construct
        ConstructRecord(
            record_id="rec_conf_nav_01",
            source=SourceOccurrence(kind="nav_config", file="mkdocs.yml", span=(8, 12), occurrence="nav: [...]"),
            disposition=ConstructDisposition.TRANSFORM,
            target=TargetStrategy(strategy="root_toctree", emitted="```{toctree}\n...\n```", target_reference="toctree"),
            verification=ConstructVerification.VERIFIED,
            manual_action=ManualActionSpec(required=False)
        )
    ]

    inventory = AccountabilityInventory(records=records)

    # Invariant 1: Total detected count strictly matches length
    assert inventory.total_count == 6
    assert inventory.accounted_count == 6
    assert inventory.verified_count == 4
    assert inventory.manual_count == 2

    # Invariant 2: Independent provenance preserved across same construct kinds
    fences = [r for r in inventory.records if r.source.kind == "code_fence"]
    assert len(fences) == 2
    assert fences[0].source.span == (10, 15)
    assert fences[1].source.span == (25, 30)
    assert fences[0].record_id != fences[1].record_id

    # Invariant 3: Unified inventory covers both document AST and config provenance
    by_k = inventory.by_kind()
    assert by_k["code_fence"] == 2
    assert by_k["theme_config"] == 1
    assert by_k["nav_config"] == 1
    assert by_k["unknown_macro"] == 1
    assert by_k["api_symbol"] == 1

    # Invariant 4: Manual construct cannot silently become verified
    manual_records = [r for r in inventory.records if r.manual_action.required]
    for m_rec in manual_records:
        assert m_rec.verification == ConstructVerification.ACCOUNTED
        assert m_rec.verification != ConstructVerification.VERIFIED

