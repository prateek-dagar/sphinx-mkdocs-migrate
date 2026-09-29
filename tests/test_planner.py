"""Unit and integration tests for Milestone 3.3 & 3.3a: Deterministic MigrationPlan, Provenance, and Traceability."""

import time
import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.planner.models import RequirementProvenance


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures" / "sample_mkdocs"


def test_migration_planner_aggregation_and_deduplication(fixture_dir):
    """Test full repository inventory aggregation into a deterministic MigrationPlan with provenance."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()

    assert plan.project_root == str(fixture_dir)
    assert plan.source_mkdocs_config is not None
    assert plan.source_mkdocs_config.site_name == "Sample Project Docs"

    # 1. Summary validation (Counts without percentages)
    assert plan.summary.total_actions > 0
    assert plan.summary.transform_count >= 1
    assert plan.summary.manual_count >= 1

    # 2. Traceability: Document actions reflect source locations
    assert len(plan.document_actions) > 0
    first_action = plan.document_actions[0]
    assert first_action.start_line >= 1
    assert first_action.source_file.endswith(".md")
    assert first_action.rule_id.startswith("rule.")

    # 3. Requirement Items with Provenance
    req_names = {r.name for r in plan.requirements}
    assert "myst_parser" in req_names
    assert "sphinx_design" in req_names
    assert "myst-parser>=2.0.0" in req_names
    assert "sphinx-design>=0.5.0" in req_names
    assert "Sphinx>=7.0.0" in req_names

    # Check provenance
    sphinx_req = next(r for r in plan.requirements if r.name == "Sphinx>=7.0.0")
    assert sphinx_req.provenance == RequirementProvenance.TARGET_BASELINE
    assert "target_baseline" in sphinx_req.sources

    design_req = next(r for r in plan.requirements if r.name == "sphinx_design")
    assert design_req.provenance == RequirementProvenance.DOCUMENT_CONSTRUCT
    assert any("tabs.md" in src or "index.md" in src for src in design_req.sources)

    # 4. Explicit Theme Migration Proposal (Material -> sphinx_immaterial)
    assert plan.proposed_sphinx_config is not None
    assert plan.proposed_sphinx_config.theme.source_theme == "material"
    assert plan.proposed_sphinx_config.theme.target_theme == "sphinx_immaterial"
    assert "sphinx-immaterial" in plan.proposed_sphinx_config.theme.target_package

    # 5. Evidence-based MyST Syntax Extensions (Only colon_fence and detected extensions, not random defaults)
    assert "colon_fence" in plan.proposed_sphinx_config.myst_enable_extensions
    assert "dollarmath" not in plan.proposed_sphinx_config.myst_enable_extensions

    # 6. Manual review items traceable to files
    assert len(plan.manual_action_items) >= 1
    manual_api = next(
        item
        for item in plan.manual_action_items
        if item.construct_type == "API_DIRECTIVE"
    )
    assert manual_api.source_file.endswith("api.md")
    assert "sample.client.Client" in manual_api.instruction


def test_planner_default_canonical_hash_determinism(fixture_dir):
    """Ensure two default plan runs at different timestamps produce IDENTICAL canonical hashes and content."""
    planner = MigrationPlanner(fixture_dir)

    plan_a = planner.create_plan()
    time.sleep(0.01)
    plan_b = planner.create_plan()

    # The generated_at timestamps naturally differ
    assert plan_a.metadata.generated_at != plan_b.metadata.generated_at
    # But the canonical identity and hashes are strictly identical!
    assert plan_a.canonical_hash() == plan_b.canonical_hash()
    assert plan_a.canonical_dict() == plan_b.canonical_dict()


def test_generated_api_pages_use_autosummary_without_stub_generation(tmp_path):
    """Generated API pages provide summary tables while retaining owned Markdown pages."""
    docs = tmp_path / "docs"
    package = tmp_path / "src" / "example"
    docs.mkdir()
    package.mkdir(parents=True)
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Example\nplugins:\n  - gen-files\n  - mkdocstrings:\n"
        "      handlers:\n        python:\n          paths: [src]\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text('"""Example package."""\n', encoding="utf-8")
    (package / "core.py").write_text(
        '"""Core helpers."""\n\nVALUE = 1\n\nclass Client:\n    pass\n\ndef connect():\n    pass\n',
        encoding="utf-8",
    )

    plan = MigrationPlanner(tmp_path).create_plan(
        deterministic_timestamp="2026-09-27T00:00:00Z"
    )
    package_doc = next(
        d
        for d in plan.generated_documents
        if d.target_path.endswith("example/index.md")
    )
    core_doc = next(
        d for d in plan.generated_documents if d.target_path.endswith("example/core.md")
    )

    assert "sphinx.ext.autosummary" in plan.get_required_extensions()
    assert plan.proposed_sphinx_config.custom_options["autosummary_generate"] is False
    assert ".. autosummary::" in package_doc.content
    assert "   core" in package_doc.content
    assert ".. rubric:: Classes" in core_doc.content
    assert "   Client" in core_doc.content
    assert ".. rubric:: Functions" in core_doc.content
    assert "   connect" in core_doc.content
    assert ".. rubric:: Attributes" in core_doc.content
    assert "   VALUE" in core_doc.content


def test_planner_read_only_invariant(fixture_dir):
    """Ensure that calling MigrationPlanner does not create or modify any files on disk."""
    docs_before = set(fixture_dir.rglob("*"))

    planner = MigrationPlanner(fixture_dir)
    _ = planner.create_plan()

    docs_after = set(fixture_dir.rglob("*"))
    assert docs_before == docs_after


def test_conf_builder_generates_valid_conf_py():
    """Verify that build_conf_py synthesizes expected Sphinx settings and docstring hooks."""
    from sphinx_mkdocs_migrate.planner.conf_builder import build_conf_py
    from sphinx_mkdocs_migrate.planner.models import (
        ConfigMigrationProposal,
        ThemeMigrationProposal,
    )

    cfg = ConfigMigrationProposal(
        project_name="MyLib",
        theme=ThemeMigrationProposal(
            source_theme="material", target_theme="sphinx_immaterial", rationale="test"
        ),
        extensions_to_add=["sphinx.ext.autodoc", "myst_parser"],
        myst_enable_extensions=["colon_fence", "deflist"],
        custom_options={"html_title": "MyLib Docs", "version": "1.0.0"},
    )
    conf_text = build_conf_py(cfg=cfg, plan_hash="abc123hash", has_generated_docs=True)

    assert "project = 'MyLib'" in conf_text
    assert "html_theme = 'sphinx_immaterial'" in conf_text
    assert "sphinx.ext.autodoc" in conf_text
    assert "html_title = 'MyLib Docs'" in conf_text
    assert "version = '1.0.0'" in conf_text
    assert "def process_docstrings" in conf_text
    assert "def setup(app):" in conf_text


def test_semantic_toctree_planner_resolution(tmp_path):
    """Verify resolve_navigation_docnames and build_semantic_toctree resolve headings and paths."""
    from sphinx_mkdocs_migrate.planner.toctree import (
        resolve_navigation_docnames,
        build_semantic_toctree,
    )
    from sphinx_mkdocs_migrate.analyzer.models import NavigationItem

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n")
    (docs / "guide.md").write_text("# Guide\n")

    items = [
        NavigationItem(title="Home", path="index.md"),
        NavigationItem(title="User Guide", path="guide.md"),
    ]
    docnames = resolve_navigation_docnames(
        nav_entries=items,
        all_files=[docs / "index.md", docs / "guide.md"],
        docs_dir=docs,
        project_root=tmp_path,
    )
    assert docnames == ["Home <self>", "User Guide <guide>"]

    toctree_block = build_semantic_toctree(
        nav_entries=items,
        all_files=[docs / "index.md", docs / "guide.md"],
        docs_dir=docs,
        project_root=tmp_path,
    )
    assert "```{toctree}" in toctree_block
    assert "Home <self>" in toctree_block
    assert "User Guide <guide>" in toctree_block


def test_ci_planner_tox_and_github_actions():
    """Verify CI workflow planning produces clean tox [testenv:docs] and GitHub Action job."""
    from sphinx_mkdocs_migrate.planner.ci import (
        determine_tox_dependency_line,
        build_tox_docs_env,
        build_github_docs_job,
    )
    from sphinx_mkdocs_migrate.analyzer.models import DependencyAnalysis

    dep_analysis = DependencyAnalysis(
        source_group_type="dependency-groups", source_group_name="docs"
    )
    dep_line = determine_tox_dependency_line(dep_analysis)
    assert dep_line == "dependency_groups = docs"

    tox_env = build_tox_docs_env(dep_line)
    assert "[testenv:docs]" in tox_env
    assert "dependency_groups = docs" in tox_env
    assert "sphinx-build -b html docs site/_build/html" in tox_env

    from sphinx_mkdocs_migrate.analyzer.ci import (
        DEFAULT_CHECKOUT_TAG,
        DEFAULT_CHECKOUT_SHA,
        DEFAULT_SETUP_UV_TAG,
        DEFAULT_SETUP_UV_SHA,
    )
    from sphinx_mkdocs_migrate.planner.ci import plan_ci_workflow

    chk_pinned = f"{DEFAULT_CHECKOUT_SHA} # {DEFAULT_CHECKOUT_TAG}"
    uv_pinned = f"{DEFAULT_SETUP_UV_SHA} # {DEFAULT_SETUP_UV_TAG}"

    gh_job = build_github_docs_job(
        checkout_ref=chk_pinned,
        uv_ref=uv_pinned,
    )
    assert f"actions/checkout@{chk_pinned}" in gh_job
    assert f"astral-sh/setup-uv@{uv_pinned}" in gh_job
    assert "uvx tox -e docs" in gh_job

    # Verify default fallback in plan_ci_workflow
    plan = plan_ci_workflow(ci_analysis=None, dep_analysis=dep_analysis)
    assert plan.checkout_pinned_ref == chk_pinned
    assert plan.setup_uv_pinned_ref == uv_pinned


def test_planner_includes_mkdocs_yml_in_obsolete_files(tmp_path: Path):
    """Ensure mkdocs.yml is added to plan.obsolete_files for removal upon migration."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: TestSite\n", encoding="utf-8")

    plan = MigrationPlanner(tmp_path).create_plan(
        deterministic_timestamp="2026-09-30T00:00:00Z"
    )

    assert "mkdocs.yml" in plan.obsolete_files


def test_planner_heading_anchors_only_when_referenced(tmp_path: Path):
    """Ensure rule_heading_anchor actions are only planned when explicitly referenced by a link."""
    docs = tmp_path / "docs"
    docs.mkdir()
    # Unreferenced heading with markdown link URL
    (docs / "changelog.md").write_text(
        "## [4.2.1](https://github.com/example/repo) - UNRELEASED\n\nRelease notes.\n",
        encoding="utf-8",
    )
    # Referenced heading with slash
    (docs / "guide.md").write_text(
        "## Request / Trace IDs\n\nDetails.\n", encoding="utf-8"
    )
    (docs / "index.md").write_text(
        "# Home\n\nSee [Traces](guide.md#request-trace-ids) for info.\n",
        encoding="utf-8",
    )
    (tmp_path / "mkdocs.yml").write_text("site_name: TestSite\n", encoding="utf-8")

    plan = MigrationPlanner(tmp_path).create_plan(
        deterministic_timestamp="2026-09-30T00:00:00Z"
    )

    heading_anchor_actions = [
        a for a in plan.document_actions if a.rule_id == "rule_heading_anchor"
    ]
    assert len(heading_anchor_actions) == 1
    assert heading_anchor_actions[0].source_file == "docs/guide.md"
    assert heading_anchor_actions[0].target_directive == "request-trace-ids"
