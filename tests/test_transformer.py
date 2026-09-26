"""Comprehensive unit and integration tests for Milestone 3.4 & 3.4-hardening."""
import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind
from sphinx_mkdocs_migrate.rules.models import MigrationAction
from sphinx_mkdocs_migrate.analyzer.models import Classification
from sphinx_mkdocs_migrate.transformer.myst_transformer import MySTDocumentTransformer
from sphinx_mkdocs_migrate.transformer.models import TransformationStatus
from sphinx_mkdocs_migrate.rules.engine import MigrationRuleEngine

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
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = transformer.transform_document(doc_ir, doc_text)

    assert transformed == doc_text
    assert applied == 0
    assert stale_cnt == 0

def test_safe_nested_fence_allocation():
    """Ensure nested tab-sets, tab-items, dropdowns, and code blocks use strictly valid backtick lengths."""
    doc_text = (
        "=== \"Tab Alpha\"\n"
        "    !!! note \"Inner Note\"\n"
        "        ```python\n"
        "        print('nested code')\n"
        "        ```\n"
        "=== \"Tab Beta\"\n"
        "    Simple text.\n"
    )
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "nested_tabs.md")

    # Generate actions using rule engine to ensure exact line span matching
    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, _, _, _, _, _ = transformer.transform_document(doc_ir, doc_text)

    assert applied >= 1
    # Outer tab-set must use 4 backticks (````) because it contains nested code blocks (```)
    assert "````{tab-set}" in transformed
    assert "```{tab-item} Tab Alpha" in transformed
    assert "```python" in transformed
    assert "````" in transformed.splitlines()[-1]

def test_manual_and_unsupported_actions_retain_original_source():
    """Verify that MANUAL and UNSUPPORTED constructs are NOT transformed and retain original source verbatim."""
    doc_text = (
        "# API Guide\n"
        "\n"
        "::: my_package.core.Client\n"
        "\n"
        "Paragraph after symbol.\n"
    )
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "api_manual.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = transformer.transform_document(doc_ir, doc_text)

    # Must NOT transform ::: my_package.core.Client
    assert transformed == doc_text
    assert applied == 0
    assert manual == 1
    assert "::: my_package.core.Client" in transformed

def test_transformation_idempotence():
    """Ensure running the transformer over already migrated MyST Markdown produces zero new transformations."""
    doc_text = (
        "# Header\n"
        "\n"
        "!!! note \"Note Title\"\n"
        "    Note body.\n"
    )
    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "idempotent.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    first_run, applied1, _, _, _, _, _ = transformer.transform_document(doc_ir, doc_text)
    assert applied1 == 1
    assert "```{note} Note Title" in first_run

    # Second run on the transformed text
    doc_ir_second = parser.parse_text(first_run, "idempotent.md")
    actions_second = rule_engine.create_actions(doc_ir_second, raw_lines=first_run.splitlines())
    transformer_second = MySTDocumentTransformer(actions_second)
    second_run, applied2, _, _, _, _, _ = transformer_second.transform_document(doc_ir_second, first_run)

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
    assert report.documents_changed == 1 # only index.md changes, api.md has manual action
    assert report.files_written_to_disk == 0 # dry run
    assert report.total_transforms_executed == 3
    assert report.total_stale_actions == 0

    # Check api.md status
    api_doc = next(d for d in report.transformed_documents if "api.md" in d.source_file)
    assert api_doc.status == TransformationStatus.MANUAL_REQUIRED
    assert api_doc.transforms_applied == 0
    assert api_doc.manual_items_reported == 1
    assert api_doc.is_modified is False

    # Check index.md status
    index_doc = next(d for d in report.transformed_documents if "index.md" in d.source_file)
    assert index_doc.status == TransformationStatus.APPLIED
    assert index_doc.transforms_applied == 3
    assert index_doc.is_modified is True
    assert index_doc.diff is not None

def test_byte_preservation_outside_transformed_span():
    """Explicitly assert that untouched lines surrounding a transformed construct remain 100% byte-for-byte identical."""
    header = "# Top Level Header\n\nSome lead paragraph with `inline code` and [links](https://example.com).\n\n"
    admonition = "!!! tip \"Transform me\"\n    Tip body text here.\n"
    footer = "\n\n## Footer Heading\n\n- Bullet 1\n- Bullet 2\n\nFinal untouched paragraph.\n"
    doc_text = f"{header}{admonition}{footer}"

    parser = MarkdownParser()
    doc_ir = parser.parse_text(doc_text, "mixed_preservation.md")

    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = transformer.transform_document(doc_ir, doc_text)

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
    report_forced = engine.execute(write_to_disk=True, overwrite_conf=True)
    assert conf_path.read_text(encoding="utf-8") != custom_conf  # Overwritten!
    assert "myst_parser" in conf_path.read_text(encoding="utf-8")
