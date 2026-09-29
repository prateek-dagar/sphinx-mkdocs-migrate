"""Unit and integration tests for Milestone 3.2: Declarative Migration Rules and Compatibility Engine."""

import pytest
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind, BaseIRNode
from sphinx_mkdocs_migrate.analyzer.models import Classification
from sphinx_mkdocs_migrate.rules.engine import MigrationRuleEngine
from sphinx_mkdocs_migrate.rules.models import MigrationRule, MigrationTarget, RuleKind


@pytest.fixture
def parser():
    return MarkdownParser()


@pytest.fixture
def rule_engine():
    return MigrationRuleEngine()


def test_rule_catalog_completeness(rule_engine):
    """Verify that all target IR construct kinds have declarative rules with requirements."""
    registered_kinds = {r.source_kind for r in rule_engine.rules}
    assert NodeKind.ADMONITION in registered_kinds
    assert NodeKind.TAB_SET in registered_kinds
    assert NodeKind.DETAILS_DROPDOWN in registered_kinds
    assert NodeKind.API_DIRECTIVE in registered_kinds
    assert NodeKind.SNIPPET_INCLUDE in registered_kinds
    assert NodeKind.MERMAID_DIAGRAM in registered_kinds
    assert NodeKind.LINK_REF in registered_kinds


def test_admonition_rule_evaluation_and_preservation(parser, rule_engine):
    doc = """
!!! tip "Pro Tip"
    Body of the tip.
"""
    doc_ir = parser.parse_text(doc, "tip.md")
    evaluations = rule_engine.evaluate_document(doc_ir)

    tip_evals = [e for e in evaluations if e.rule_id == "rule.admonition.myst"]
    assert len(tip_evals) == 1
    ev = tip_evals[0]

    assert ev.matched is True
    assert ev.classification == Classification.TRANSFORM
    assert ev.target.directive_name == "tip"
    assert "myst_parser" in ev.required_extensions
    assert "myst-parser>=2.0.0" in ev.required_packages
    assert "title" in ev.preserved_attributes
    assert "body" in ev.preserved_attributes


def test_tabs_and_dropdowns_rules_preservation(parser, rule_engine):
    doc = """
=== "Python"
    ???+ note "Details Title"
        ```python
        print('hello')
        ```
"""
    doc_ir = parser.parse_text(doc, "tabs.md")
    evaluations = rule_engine.evaluate_document(doc_ir)

    tab_eval = next(e for e in evaluations if e.rule_id == "rule.tabs.sphinx_design")
    assert tab_eval.classification == Classification.TRANSFORM
    assert tab_eval.target.directive_name == "tab-set"
    assert "sphinx_design" in tab_eval.required_extensions
    assert "sphinx-design>=0.5.0" in tab_eval.required_packages
    assert "tab_titles" in tab_eval.preserved_attributes

    det_eval = next(e for e in evaluations if e.rule_id == "rule.details.sphinx_design")
    assert det_eval.classification == Classification.TRANSFORM
    assert det_eval.target.directive_name == "dropdown"
    assert "open_state" in det_eval.preserved_attributes


def test_api_directive_manual_review_and_rationale(parser, rule_engine):
    doc = """::: my_package.core.Client"""
    doc_ir = parser.parse_text(doc, "api.md")
    evaluations = rule_engine.evaluate_document(doc_ir)

    api_eval = next(e for e in evaluations if e.rule_id == "rule.api.autodoc")
    assert api_eval.classification == Classification.MANUAL
    assert "my_package.core.Client" in api_eval.action_item
    assert "sphinx.ext.autodoc" in api_eval.required_extensions
    assert "sphinx.ext.napoleon" in api_eval.required_extensions


def test_snippet_and_mermaid_rules(parser, rule_engine):
    doc = """
--8<-- "examples/snippet.py"

```mermaid
graph TD;
    A-->B;
```
"""
    doc_ir = parser.parse_text(doc, "snippet_mermaid.md")
    evaluations = rule_engine.evaluate_document(doc_ir)

    snip_eval = next(
        e for e in evaluations if e.rule_id == "rule.snippet.literalinclude"
    )
    assert snip_eval.target.directive_name == "literalinclude"
    assert "filepath" in snip_eval.preserved_attributes

    mermaid_eval = next(
        e for e in evaluations if e.rule_id == "rule.mermaid.sphinxcontrib"
    )
    assert mermaid_eval.target.directive_name == "mermaid"
    assert "sphinxcontrib.mermaid" in mermaid_eval.required_extensions


def test_custom_declarative_rule_extensibility_without_modifying_engine():
    """Prove that MigrationRuleEngine is purely declarative and requires zero engine changes for new constructs."""
    custom_rule = MigrationRule(
        rule_id="custom.html.raw",
        source_kind=NodeKind.HTML_BLOCK,
        rule_kind=RuleKind.DETERMINISTIC,
        classification=Classification.TRANSFORM,
        target=MigrationTarget(
            framework="MyST",
            directive_name="raw",
            required_extensions=["myst_parser"],
            required_py_packages=["myst-parser>=2.0.0"],
        ),
        preserves=["raw_text"],
        changes=["html_to_raw_directive"],
        conditions={},
        manual_if=[],
        description="Transforms raw HTML blocks into MyST {raw} directives.",
    )

    custom_engine = MigrationRuleEngine(custom_rules=[custom_rule])
    html_node = BaseIRNode(
        kind=NodeKind.HTML_BLOCK,
        start_line=10,
        end_line=12,
        raw_text="<div class='custom'>hello</div>",
    )

    evaluation = custom_engine.evaluate_node(html_node)
    assert evaluation is not None
    assert evaluation.rule_id == "custom.html.raw"
    assert evaluation.target.directive_name == "raw"
    assert evaluation.classification == Classification.TRANSFORM
    assert "raw_text" in evaluation.preserved_attributes


def test_unregistered_node_kind_yields_none_silently(rule_engine):
    """Verify that unsupported/unregistered IR node kinds do not trigger false transformations."""
    empty_engine = MigrationRuleEngine(custom_rules=[])
    dummy_node = BaseIRNode(
        kind=NodeKind.HTML_BLOCK, start_line=1, end_line=1, raw_text="<div></div>"
    )
    assert empty_engine.evaluate_node(dummy_node) is None


def test_migration_actions_generation(parser, rule_engine):
    """Test normalized MigrationAction generation from DocumentIR."""
    doc = """
# Header
!!! note "Take Note"
    Important info.
"""
    doc_ir = parser.parse_text(doc, "action_test.md")
    actions = rule_engine.create_actions(doc_ir)

    adm_actions = [a for a in actions if a.source_kind == NodeKind.ADMONITION]
    assert len(adm_actions) == 1
    action = adm_actions[0]
    assert action.rule_id == "rule.admonition.myst"
    assert action.target_directive == "note"
    assert action.classification == Classification.TRANSFORM
    assert action.start_line == 3
    assert action.end_line == 4
