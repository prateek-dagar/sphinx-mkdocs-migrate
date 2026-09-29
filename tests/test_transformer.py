"""Comprehensive unit and integration tests for Milestone 3.4 & 3.4-hardening."""

import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.transformer.myst_transformer import MySTDocumentTransformer
from sphinx_mkdocs_migrate.transformer.models import TransformationStatus
from sphinx_mkdocs_migrate.rules.engine import MigrationRuleEngine
from sphinx_mkdocs_migrate.planner.models import (
    MigrationPlan,
    MigrationPlanMetadata,
    GeneratedDocumentProposal,
)
from sphinx_mkdocs_migrate.analyzer.models import ConfigAnalysis, Classification


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures" / "sample_mkdocs"


def test_source_preservation_invariant_on_untouched_markdown():
    """Ensure plain standard Markdown with no actions is preserved byte-for-byte identically."""
    doc_text = (
        "# Top Level Heading\n"
        "\n"
        "This is an ordinary paragraph with [a link](https://example.com) and `code`.\n"
        "\n"
        "- List item 1\n"
        "- List item 2\n"
        "    * Sub item A\n"
        "\n"
        "> A blockquote that should not be touched at all.\n"
    )
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "clean.md")

    # Empty actions
    transformer = MySTDocumentTransformer([])
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = (
        transformer.transform_document(doc_ir, doc_text)
    )

    assert transformed == doc_text
    assert applied == 0
    assert stale_cnt == 0


def test_resolved_mkdocs_autorefs_links_become_relative_myst_links(tmp_path):
    """Autorefs shorthand must not remain literal text in a MyST document."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text(
        "# Home\n\nUse [orjson][pythonjsonlogger.orjson].\n", encoding="utf-8"
    )
    generated = GeneratedDocumentProposal(
        target_path="docs/reference/pythonjsonlogger/orjson.md",
        title="pythonjsonlogger.orjson",
        content="# pythonjsonlogger.orjson\n\n```{eval-rst}\n.. currentmodule:: pythonjsonlogger.orjson\n```\n",
        generator_plugin="gen-files",
        rationale="test fixture",
    )
    plan = MigrationPlan(
        project_root=str(tmp_path),
        source_mkdocs_config=ConfigAnalysis(plugins=["autorefs"]),
        generated_documents=[generated],
        metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
    )

    report = TransformationEngine(plan).execute(write_to_disk=False)
    index = next(
        doc
        for doc in report.transformed_documents
        if doc.target_file == "docs/index.md"
    )

    assert "[orjson](reference/pythonjsonlogger/orjson.md)" in index.transformed_content
    assert "[orjson][pythonjsonlogger.orjson]" not in index.transformed_content


def test_safe_nested_fence_allocation():
    """Ensure nested tab-sets, tab-items, dropdowns, and code blocks use strictly valid backtick lengths."""
    doc_text = (
        '=== "Tab Alpha"\n'
        '    !!! note "Inner Note"\n'
        "        ```python\n"
        "        print('nested code')\n"
        "        ```\n"
        '=== "Tab Beta"\n'
        "    Simple text.\n"
    )
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "nested_tabs.md")

    # Generate actions using rule engine to ensure exact line span matching
    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, _, _, _, _, _ = transformer.transform_document(
        doc_ir, doc_text
    )

    assert applied >= 1
    # Outer tab-set must use 4 backticks (````) because it contains nested code blocks (```)
    assert "````{tab-set}" in transformed
    assert "```{tab-item} Tab Alpha" in transformed
    assert "```python" in transformed
    assert "````" in transformed.splitlines()[-1]


def test_manual_and_unsupported_actions_retain_original_source():
    """Verify that MANUAL and UNSUPPORTED constructs are NOT transformed and retain original source verbatim."""
    doc_text = "# API Guide\n\n::: my_package.core.Client\n\nParagraph after symbol.\n"
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "api_manual.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = (
        transformer.transform_document(doc_ir, doc_text)
    )

    # Must NOT transform ::: my_package.core.Client
    assert transformed == doc_text
    assert applied == 0
    assert manual == 1
    assert "::: my_package.core.Client" in transformed


def test_manual_overrides_transformer():
    """Verify that manual_overrides properly replaces Classification.MANUAL construct."""
    doc_text = "# API Guide\n\n::: my_package.core.Client\n\nParagraph after symbol.\n"
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "api_manual.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())
    manual_act = next(a for a in actions if a.classification == Classification.MANUAL)

    overrides = {manual_act.action_id: "<!-- CUSTOM_REPLACEMENT -->\n"}
    transformer = MySTDocumentTransformer(actions, manual_overrides=overrides)
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = (
        transformer.transform_document(doc_ir, doc_text)
    )
    assert applied == 1
    assert manual == 0
    assert "<!-- CUSTOM_REPLACEMENT -->" in transformed
    assert "::: my_package.core.Client" not in transformed


def test_transformation_idempotence():
    """Ensure running the transformer over already migrated MyST Markdown produces zero new transformations."""
    doc_text = '# Header\n\n!!! note "Note Title"\n    Note body.\n'
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "idempotent.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    first_run, applied1, _, _, _, _, _ = transformer.transform_document(
        doc_ir, doc_text
    )
    assert applied1 == 1
    assert "```{note} Note Title" in first_run

    # Second run on the transformed text
    doc_ir_second = parser.parse_text(first_run, "idempotent.md")
    actions_second = rule_engine.create_actions(
        doc_ir_second, raw_lines=first_run.splitlines()
    )
    transformer_second = MySTDocumentTransformer(actions_second)
    second_run, applied2, _, _, _, _, _ = transformer_second.transform_document(
        doc_ir_second, first_run
    )

    assert applied2 == 0
    assert second_run == first_run


def test_transformation_engine_full_report_and_metrics(fixture_dir):
    """Verify TransformationEngine accurate metrics (examined, changed, written) in dry-run mode."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)

    assert report.dry_run is True
    assert report.documents_examined == 2
    assert (
        report.documents_changed == 1
    )  # only index.md changes, api.md has manual action
    assert report.files_written_to_disk == 0  # dry run
    assert report.total_transforms_executed == 3
    assert report.total_stale_actions == 0

    # Check api.md status
    api_doc = next(d for d in report.transformed_documents if "api.md" in d.source_file)
    assert api_doc.status == TransformationStatus.MANUAL_REQUIRED
    assert api_doc.transforms_applied == 0
    assert api_doc.manual_items_reported == 1
    assert api_doc.is_modified is False

    # Check index.md status
    index_doc = next(
        d for d in report.transformed_documents if "index.md" in d.source_file
    )
    assert index_doc.status == TransformationStatus.APPLIED
    assert index_doc.transforms_applied == 3
    assert index_doc.is_modified is True
    assert index_doc.diff is not None


def test_byte_preservation_outside_transformed_span():
    """Explicitly assert that untouched lines surrounding a transformed construct remain 100% byte-for-byte identical."""
    header = "# Top Level Header\n\nSome lead paragraph with `inline code` and [links](https://example.com).\n\n"
    admonition = '!!! tip "Transform me"\n    Tip body text here.\n'
    footer = "\n\n## Footer Heading\n\n- Bullet 1\n- Bullet 2\n\nFinal untouched paragraph.\n"
    doc_text = f"{header}{admonition}{footer}"

    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "mixed_preservation.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = (
        transformer.transform_document(doc_ir, doc_text)
    )

    assert applied == 1
    # Check that transformed content begins with exact header and ends with exact footer
    assert transformed.startswith(header)
    assert transformed.endswith(footer)
    # Check the transformed middle
    assert "```{tip} Transform me\nTip body text here.\n```" in transformed


def test_conf_py_collision_and_preservation_policy(fixture_dir, tmp_path):
    """Verify that existing differing conf.py is NOT silently overwritten without explicit force flag."""
    # Copy fixture into tmp_path
    import shutil

    temp_project = tmp_path / "sample_mkdocs"
    shutil.copytree(fixture_dir, temp_project)

    planner = MigrationPlanner(temp_project)
    plan = planner.create_plan()

    # Pre-create a custom conf.py on disk
    conf_path = temp_project / "docs" / "conf.py"
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    custom_conf = "# Custom Existing Sphinx Conf\nproject = 'Custom'\n"
    conf_path.write_text(custom_conf, encoding="utf-8")

    # 1. Execute with write_to_disk=True, overwrite_conf=False
    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=True, overwrite_conf=False)

    assert report.conf_py_status.value == "CONFLICT"
    assert report.conf_py_conflict_diff is not None
    assert conf_path.read_text(encoding="utf-8") == custom_conf  # Unchanged!

    # 2. Execute with write_to_disk=True, overwrite_conf=True
    _ = engine.execute(write_to_disk=True, overwrite_conf=True)
    assert conf_path.read_text(encoding="utf-8") != custom_conf  # Overwritten!
    assert "myst_parser" in conf_path.read_text(encoding="utf-8")


def test_dynamic_tox_dependency_group_resolution(tmp_path):
    """Verify that tox.ini adopts the correct dependency group or extra dynamically."""
    tox_file = tmp_path / "tox.ini"
    tox_file.write_text("[tox]\nenvlist = py312\n", encoding="utf-8")

    from sphinx_mkdocs_migrate.analyzer.models import DependencyAnalysis
    from sphinx_mkdocs_migrate.planner.models import MigrationPlanMetadata

    # Case 1: PEP 735 dependency-groups with custom name "docs"
    plan_docs = MigrationPlan(
        project_root=str(tmp_path),
        source_mkdocs_config=ConfigAnalysis(site_name="Test"),
        dependency_analysis=DependencyAnalysis(
            source_group_type="dependency-groups",
            source_group_name="docs",
        ),
        metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
    )
    TransformationEngine(plan_docs).execute(write_to_disk=True)
    tox_text = tox_file.read_text(encoding="utf-8")
    assert "[testenv:docs]" in tox_text
    assert "dependency_groups = docs" in tox_text

    # Case 2: PEP 621 optional-dependencies (extras) with name "documentation"
    tox_file.write_text("[tox]\nenvlist = py312\n", encoding="utf-8")
    plan_extras = MigrationPlan(
        project_root=str(tmp_path),
        source_mkdocs_config=ConfigAnalysis(site_name="Test"),
        dependency_analysis=DependencyAnalysis(
            source_group_type="optional-dependencies",
            source_group_name="documentation",
        ),
        metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
    )
    TransformationEngine(plan_extras).execute(write_to_disk=True)
    tox_text = tox_file.read_text(encoding="utf-8")
    assert "[testenv:docs]" in tox_text
    assert "extras = documentation" in tox_text


def test_clean_obsolete_mkdocs_generator_scripts(tmp_path):
    """Verify that obsolete generator scripts (e.g. scripts/gen_ref_nav.py) are deleted on migration."""
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    gen_script = script_dir / "gen_ref_nav.py"
    gen_script.write_text(
        "import mkdocs_gen_files\nnav = mkdocs_gen_files.Nav()\n", encoding="utf-8"
    )

    from sphinx_mkdocs_migrate.planner.models import MigrationPlanMetadata

    plan = MigrationPlan(
        project_root=str(tmp_path),
        source_mkdocs_config=ConfigAnalysis(
            site_name="Test",
            plugins=["gen-files"],
            plugins_config={"gen-files": {"scripts": ["scripts/gen_ref_nav.py"]}},
        ),
        metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
    )

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=True)

    assert "scripts/gen_ref_nav.py" in report.cleaned_files
    assert not gen_script.exists()
    assert not script_dir.exists()  # Empty directory cleaned up


def test_inject_orphan_metadata():
    """Verify orphan: true frontmatter injection for standalone documents."""
    # Case 1: No frontmatter
    doc_raw = "# Style Guide\n\nSome text here.\n"
    res1 = TransformationEngine._inject_orphan_metadata(doc_raw)
    assert res1.startswith("---\norphan: true\n---\n\n# Style Guide")

    # Case 2: Existing frontmatter
    doc_fm = "---\ntitle: Style Guide\n---\n\n# Style Guide\n"
    res2 = TransformationEngine._inject_orphan_metadata(doc_fm)
    assert res2.startswith("---\norphan: true\ntitle: Style Guide\n---\n")

    # Case 3: Already has orphan: true
    doc_already = "---\norphan: true\ntitle: Style Guide\n---\n\n# Style Guide\n"
    res3 = TransformationEngine._inject_orphan_metadata(doc_already)
    assert res3 == doc_already


def test_harmonize_heading_anchors():
    """Verify heading anchor generation for Python-Markdown slug compatibility."""
    engine = TransformationEngine(
        MigrationPlan(
            project_root=".",
            metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
        )
    )

    # Case 1: Heading with slash / punctuation
    content = "## Request / Trace IDs\n\nSome content\n"
    harmonized = engine._harmonize_heading_anchors(content)
    assert "(request-trace-ids)=\n## Request / Trace IDs\n" in harmonized

    # Case 2: Standard heading with no slug divergence
    content_std = "## Standard Heading\n\nSome content\n"
    assert engine._harmonize_heading_anchors(content_std) == content_std

    # Case 3: Idempotence (anchor already present)
    content_already = "(request-trace-ids)=\n## Request / Trace IDs\n\nSome content\n"
    assert engine._harmonize_heading_anchors(content_already) == content_already

    # Case 4: Code block with comments not affected
    content_code = "```python\n# Request / Trace IDs\ncode = 1\n```\n"
    assert engine._harmonize_heading_anchors(content_code) == content_code

    # Case 5: Link rewriting to harmonized target
    link_content = "See [Cookbook: Request / Trace IDs](cookbook.md#request-trace-ids) for an example."
    rewritten, changes = engine._harmonize_anchor_links(
        link_content, {"request-trace-ids"}
    )
    assert changes == 1
    assert (
        rewritten
        == "See [Cookbook: Request / Trace IDs](request-trace-ids) for an example."
    )


def test_unlisted_documents_marked_as_orphan(tmp_path: Path):
    """Verify that documents in docs/ not listed in nav are marked as orphan."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")
    (docs_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (docs_dir / "orphan_page.md").write_text("# Unlisted Page\n", encoding="utf-8")

    from sphinx_mkdocs_migrate.analyzer.models import NavigationAnalysis, NavigationItem

    plan = MigrationPlan(
        project_root=str(tmp_path),
        source_mkdocs_config=ConfigAnalysis(site_name="Test"),
        navigation_analysis=NavigationAnalysis(
            has_nav=True,
            orphan_documents=["orphan_page.md"],
            tree=[
                NavigationItem(title="Home", path="index.md"),
                NavigationItem(title="Guide", path="guide.md"),
            ],
        ),
        metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
    )

    engine = TransformationEngine(plan)
    engine.execute(write_to_disk=True)

    # index.md is root document, so never marked as orphan
    index_text = (docs_dir / "index.md").read_text(encoding="utf-8")
    assert "orphan: true" not in index_text

    # guide.md is in nav, so no orphan
    guide_text = (docs_dir / "guide.md").read_text(encoding="utf-8")
    assert "orphan: true" not in guide_text

    # orphan_page.md is NOT in nav, so orphan: true must be injected
    orphan_text = (docs_dir / "orphan_page.md").read_text(encoding="utf-8")
    assert "orphan: true" in orphan_text


def test_root_document_resolution_and_orphan_handling(tmp_path: Path):
    """Verify that README.md as root document is correctly identified and not marked as orphan."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "README.md").write_text("# Root Readme\n", encoding="utf-8")
    (docs_dir / "tutorial.md").write_text("# Tutorial\n", encoding="utf-8")
    (docs_dir / "extra.md").write_text("# Extra\n", encoding="utf-8")

    from sphinx_mkdocs_migrate.analyzer.models import NavigationAnalysis, NavigationItem

    plan = MigrationPlan(
        project_root=str(tmp_path),
        source_mkdocs_config=ConfigAnalysis(site_name="Test"),
        navigation_analysis=NavigationAnalysis(
            has_nav=True,
            tree=[
                NavigationItem(title="Home", path="README.md"),
                NavigationItem(title="Tutorial", path="tutorial.md"),
            ],
        ),
        metadata=MigrationPlanMetadata(generated_at="2026-09-29T00:00:00Z"),
    )

    engine = TransformationEngine(plan)
    engine.execute(write_to_disk=True)

    readme_text = (docs_dir / "README.md").read_text(encoding="utf-8")
    assert "orphan: true" not in readme_text

    tutorial_text = (docs_dir / "tutorial.md").read_text(encoding="utf-8")
    assert "orphan: true" not in tutorial_text

    extra_text = (docs_dir / "extra.md").read_text(encoding="utf-8")
    assert "orphan: true" in extra_text
