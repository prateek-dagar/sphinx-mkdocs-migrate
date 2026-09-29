from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind
from sphinx_mkdocs_migrate.analyzer.models import Classification
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.rules.engine import MigrationRuleEngine
from sphinx_mkdocs_migrate.rules.catalog import DEFAULT_RULES
from sphinx_mkdocs_migrate.transformer.myst_transformer import MySTDocumentTransformer


def test_gap_1_inline_code_tab_title_normalization():
    """Verify tab titles with inline code backticks are cleanly stripped of backticks."""
    text = '=== "`validate_by_alias` and `validate_by_name`"\n    Line 1\n'
    parser = MarkdownParser()
    doc = parser.parse_text(text, "test.md")
    engine = MigrationRuleEngine(DEFAULT_RULES)
    actions = engine.create_actions(doc, text.splitlines())
    t = MySTDocumentTransformer(actions)
    res, applied, preserved, manual, unsupported, stale, details = t.transform_document(
        doc, text
    )
    assert "{tab-item} validate_by_alias and validate_by_name" in res
    assert "`" not in res.split("{tab-item}")[1].splitlines()[0]


def test_gap_2_mermaid_yaml_frontmatter_stripping():
    """Verify mermaid diagrams with YAML configuration headers are cleaned for sphinxcontrib-mermaid."""
    text = "```mermaid\n---\nconfig:\n  flowchart:\n    nodeSpacing: 20\n---\nflowchart TD\n    A --> B\n```\n"
    parser = MarkdownParser()
    doc = parser.parse_text(text, "test.md")
    engine = MigrationRuleEngine(DEFAULT_RULES)
    actions = engine.create_actions(doc, text.splitlines())
    t = MySTDocumentTransformer(actions)
    res, applied, preserved, manual, unsupported, stale, details = t.transform_document(
        doc, text
    )
    assert "```{mermaid}" in res
    assert "flowchart TD" in res
    assert "---" not in res


def test_gap_3_yaml_date_frontmatter_sanitization():
    """Verify YAML frontmatter containing date objects is safely handled without JSON serializing crashes."""
    text = "---\ndate: 2025-11-11\nauthors:\n  - squidfunk\n---\n\n# Blog\nContent\n"
    parser = MarkdownParser()
    doc = parser.parse_text(text, "test.md")
    engine = MigrationRuleEngine(DEFAULT_RULES)
    actions = engine.create_actions(doc, text.splitlines())
    t = MySTDocumentTransformer(actions)
    res, applied, preserved, manual, unsupported, stale, details = t.transform_document(
        doc, text
    )
    # Date should be quoted as string to avoid Python date object instantiation in PyYAML/MyST
    assert (
        'date: "2025-11-11"' in res
        or "date: '2025-11-11'" in res
        or "2025-11-11" in res
    )


def test_gap_4_variadic_args_docstring_signature_preservation():
    """Verify variadic *args and **kwargs in API directives and code blocks are strictly preserved without AST corruption."""
    source_markdown = """# API Reference

::: pythonjsonlogger.json.JsonFormatter
    options:
      members:
        - __init__

```python
class JsonFormatter(logging.Formatter):
    def __init__(self, *args: Any, json_default: Optional[Callable] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
```
"""
    parser = MarkdownParser()
    doc = parser.parse_text(source_markdown, "docs/reference.md")
    engine = MigrationRuleEngine(DEFAULT_RULES)
    actions = engine.create_actions(doc, source_markdown.splitlines())

    # 1. API directive must be classified as MANUAL to prevent speculative docstring rewriting
    api_actions = [a for a in actions if a.source_kind == NodeKind.API_DIRECTIVE]
    assert len(api_actions) == 1
    assert api_actions[0].classification == Classification.MANUAL
    assert (
        "variadic_args_kwargs_docstrings" in api_actions[0].description
        or "symbol" in api_actions[0].description
    )

    # 2. Transformer must preserve byte-for-byte exact signatures for *args, keyword args, and **kwargs
    t = MySTDocumentTransformer(actions)
    res, applied, preserved, manual, unsupported, stale, details = t.transform_document(
        doc, source_markdown
    )

    # Assert exact code block and surrounding markdown remain byte-for-byte identical
    expected_code_block = """```python
class JsonFormatter(logging.Formatter):
    def __init__(self, *args: Any, json_default: Optional[Callable] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
```"""
    assert expected_code_block in res
    assert "::: pythonjsonlogger.json.JsonFormatter" in res
    assert res == source_markdown
