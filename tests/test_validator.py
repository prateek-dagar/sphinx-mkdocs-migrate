"""Unit and integration tests for Milestone 3.5 & 3.5.2: Validation, Invariants, and Sphinx Verification."""

import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.transformer.myst_transformer import (
    MySTDocumentTransformer,
    StalePlanException,
    OverlappingSpanException,
)
from sphinx_mkdocs_migrate.rules.models import MigrationAction
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind
from sphinx_mkdocs_migrate.analyzer.models import Classification
from sphinx_mkdocs_migrate.validator.verifier import TransformationValidator
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.rules.engine import MigrationRuleEngine


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures" / "sample_mkdocs"


@pytest.fixture
def validator():
    return TransformationValidator()


def test_12_validation_scenarios(validator):
    """Test all 12 key validation scenarios to prove structural validity of generated MyST Markdown."""
    parser = MarkdownParser()
    rule_engine = MigrationRuleEngine()

    test_cases = [
        # 1. Plain Markdown preservation
        ("# Title\n\nParagraph with `code`.\n", "plain.md"),
        # 2. Admonition
        ('!!! note "Note Box"\n    Body text.\n', "admonition.md"),
        # 3. Dropdown
        ('???+ tip "Tip Dropdown"\n    Dropdown body.\n', "dropdown.md"),
        # 4. Tab-set
        ('=== "Tab A"\n    Content A\n=== "Tab B"\n    Content B\n', "tabs.md"),
        # 5. Tab-set + code block (Nested fence validation)
        (
            '=== "Tab A"\n    ```python\n    print(\'tab code\')\n    ```\n=== "Tab B"\n    Simple text\n',
            "tab_code.md",
        ),
        # 6. Tab-set + nested admonition
        ('=== "Tab A"\n    !!! note "Inner Note"\n        Note text\n', "tab_adm.md"),
        # 7. Nested admonition + dropdown + code
        (
            '!!! warning "Alert"\n    ???+ info "Details"\n        ```bash\n        echo 123\n        ```\n',
            "deep_nesting.md",
        ),
        # 8. Mermaid
        ("```mermaid\ngraph TD;\nA-->B;\n```\n", "mermaid.md"),
        # 9. Literalinclude snippet
        ('--8<-- "examples/demo.py"\n', "snippet.md"),
        # 10. Manual API construct (preserved as original)
        ("::: package.core.Client\n", "api.md"),
        # 11. Mixed transformed + untouched Markdown
        (
            '# Untouched Header\n\n!!! tip "Transform me"\n    Tip body\n\nUntouched footer paragraph.\n',
            "mixed.md",
        ),
        # 12. Multiple independent tab sets
        (
            '=== "Set 1 Tab"\n    Text 1\n\nMiddle paragraph.\n\n=== "Set 2 Tab"\n    Text 2\n',
            "multi_tab.md",
        ),
    ]

    for doc_text, filename in test_cases:
        doc_ir = parser.parse_text(doc_text, filename)
        actions = rule_engine.create_actions(doc_ir, raw_lines=doc_text.splitlines())
        transformer = MySTDocumentTransformer(actions)
        (
            transformed,
            applied,
            preserved,
            manual,
            unsupported,
            stale_cnt,
            stale_details,
        ) = transformer.transform_document(doc_ir, doc_text)

        issues = validator.validate_structural_syntax(filename, transformed)
        errors = [i for i in issues if i.severity.value == "ERROR"]
        assert len(errors) == 0, f"Validation errors for {filename}: {errors}"


def test_stale_plan_detection_and_reporting():
    """Verify stale-plan detection reports skips and details in non-strict mode, and raises in strict mode."""
    original_text = '!!! note "Old Title"\n    Original body.\n'
    modified_text = '!!! note "Altered Title on Disk"\n    Altered body.\n'

    parser = MarkdownParser()
    doc_ir = parser.parse_text(original_text, "stale_test.md")
    rule_engine = MigrationRuleEngine()

    actions = rule_engine.create_actions(doc_ir, raw_lines=original_text.splitlines())
    assert len(actions) == 1
    assert actions[0].source_span_fingerprint != ""

    doc_ir_modified = parser.parse_text(modified_text, "stale_test.md")

    # 1. Non-strict mode: reports stale action instead of silently skipping
    non_strict_transformer = MySTDocumentTransformer(actions, strict_fingerprint=False)
    transformed, applied, preserved, manual, unsupported, stale_cnt, stale_details = (
        non_strict_transformer.transform_document(doc_ir_modified, modified_text)
    )
    assert applied == 0
    assert stale_cnt == 1
    assert len(stale_details) == 1
    assert "STALE_PLAN" in stale_details[0]
    assert transformed == modified_text

    # 2. Strict mode: raises StalePlanException
    strict_transformer = MySTDocumentTransformer(actions, strict_fingerprint=True)
    with pytest.raises(StalePlanException) as excinfo:
        strict_transformer.transform_document(doc_ir_modified, modified_text)
    assert "STALE_PLAN" in str(excinfo.value) or "Stale plan detected" in str(
        excinfo.value
    )


def test_overlapping_span_invariant_and_deep_nesting():
    """Verify that transformation enforces disjoint root spans and parent-owned subtree rendering."""
    nested_text = (
        '=== "Tab Set"\n'
        '    !!! note "Inner Admonition"\n'
        '        ???+ tip "Nested Dropdown"\n'
        "            ```python\n"
        "            print('deep')\n"
        "            ```\n"
    )
    parser = MarkdownParser()
    doc_ir = parser.parse_text(nested_text, "nested.md")
    rule_engine = MigrationRuleEngine()
    actions = rule_engine.create_actions(doc_ir, raw_lines=nested_text.splitlines())

    transformer = MySTDocumentTransformer(actions)
    transformed, applied, preserved, manual, unsupported, _, _ = (
        transformer.transform_document(doc_ir, nested_text)
    )
    assert applied == 1  # Root TAB_SET owns entire rendering
    assert "```{tab-set}" in transformed
    assert "````{tab-item}" in transformed
    assert "```{dropdown}" in transformed

    # Now verify that conflicting overlapping actions trigger OverlappingSpanException
    conflicting_actions = [
        MigrationAction(
            action_id="act_1",
            rule_id="rule_admonition",
            source_file="conflict.md",
            start_line=1,
            end_line=5,
            classification=Classification.TRANSFORM,
            source_kind=NodeKind.ADMONITION,
            description="Conflicting Action 1",
        ),
        MigrationAction(
            action_id="act_2",
            rule_id="rule_tab_set",
            source_file="conflict.md",
            start_line=3,
            end_line=7,
            classification=Classification.TRANSFORM,
            source_kind=NodeKind.TAB_SET,
            description="Conflicting Action 2",
        ),
    ]
    conflicting_transformer = MySTDocumentTransformer(conflicting_actions)
    with pytest.raises(OverlappingSpanException):
        conflicting_transformer.transform_document(doc_ir, nested_text)


def test_semantic_navigation_toctree_ordering(fixture_dir):
    """Verify that the root toctree strictly follows MkDocs navigation order rather than filesystem sort."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()

    assert plan.navigation_analysis is not None
    assert plan.navigation_analysis.has_nav is True

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    index_res = next(
        d for d in report.transformed_documents if "index.md" in d.source_file
    )

    # In sample_mkdocs nav: Index -> api.md
    assert "```{toctree}" in index_res.transformed_content
    assert ":hidden:" in index_res.transformed_content
    assert "api" in index_res.transformed_content


def test_true_pipeline_idempotence(fixture_dir):
    """Proves True Pipeline Idempotence: MkDocs -> Plan1 -> Transform1 -> Plan2 -> Transform2 == Transform1."""
    planner = MigrationPlanner(fixture_dir)
    plan1 = planner.create_plan()

    engine1 = TransformationEngine(plan1)
    report1 = engine1.execute(write_to_disk=False)
    index_trans1 = next(
        d.transformed_content
        for d in report1.transformed_documents
        if "index.md" in d.source_file
    )

    parser = MarkdownParser()
    doc_ir2 = parser.parse_text(index_trans1, "docs/index.md")
    rule_engine = MigrationRuleEngine()
    actions2 = rule_engine.create_actions(doc_ir2, raw_lines=index_trans1.splitlines())

    transform_actions = [a for a in actions2 if a.classification == "TRANSFORM"]
    assert len(transform_actions) == 0

    transformer2 = MySTDocumentTransformer(actions2)
    index_trans2, applied2, _, _, _, _, _ = transformer2.transform_document(
        doc_ir2, index_trans1
    )
    assert applied2 == 0
    assert index_trans2 == index_trans1


def test_real_sphinx_build_execution_and_verification(fixture_dir):
    """Executes a REAL Sphinx build in an isolated sandbox with asset copying and warning tracking."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()
    # Explicitly test with installed Sphinx theme (e.g. furo or alabaster)
    plan.proposed_sphinx_config.theme.target_theme = "furo"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)

    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(
        report, run_sphinx_build=True, strict_warnings=False
    )

    assert v_report.passed is True
    assert v_report.commonmark_parse_successful is True
    assert v_report.structural_validation_successful is True
    assert v_report.sphinx_build_attempted is True
    assert v_report.sphinx_build_successful is True
    assert isinstance(v_report.sphinx_warning_count, int)
    assert isinstance(v_report.sphinx_warnings, list)
    assert (
        "build succeeded" in v_report.build_output.lower()
        or v_report.sphinx_build_successful is True
    )


def test_sphinx_build_strict_mode_warning_failure(fixture_dir):
    """Verify that --strict fails validation if Sphinx generates unresolved reference warnings."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()
    plan.proposed_sphinx_config.theme.target_theme = "furo"

    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)

    validator = TransformationValidator()
    # Strict mode on sample docs will catch cross-reference warnings and report failure cleanly
    v_report_strict = validator.validate_transformation_report(
        report, run_sphinx_build=True, strict_warnings=True
    )
    if v_report_strict.sphinx_warning_count > 0:
        assert v_report_strict.passed is False
        assert any(
            i.issue_type == "SPHINX_STRICT_WARNING_ERROR"
            for i in v_report_strict.issues
        )


def test_cli_runner_validation_matrix(fixture_dir):
    """Test CLI migrate combinations: --validate, --no-build, --strict, and --build."""
    from click.testing import CliRunner
    from sphinx_mkdocs_migrate.cli import main

    runner = CliRunner()

    # 1. migrate with structural validation only (--no-build)
    result_nobuild = runner.invoke(
        main, ["migrate", str(fixture_dir), "--validate", "--no-build"]
    )
    assert result_nobuild.exit_code == 0
    assert "Validation Passed" in result_nobuild.output
    assert "structural validation only" in result_nobuild.output

    # 2. migrate with full build validation (--build)
    result_build = runner.invoke(
        main, ["migrate", str(fixture_dir), "--validate", "--build"]
    )
    assert result_build.exit_code == 0
    assert "Validation Passed" in result_build.output

    # 3. migrate with strict mode (--build --strict)
    result_strict = runner.invoke(
        main, ["migrate", str(fixture_dir), "--validate", "--build", "--strict"]
    )
    # If cross-reference warnings exist, strict mode cleanly reports validation failure
    if "Sphinx Warnings" in result_build.output:
        assert "Validation Failed" in result_strict.output
