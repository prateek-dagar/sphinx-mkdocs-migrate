"""Tests for Phase 4: Deterministic Source IR <-> Rendered Evidence Correlation."""

import pytest

pytest.importorskip(
    "research.html_parity",
    reason="research module is local-only and not tracked in git",
)

from sphinx_mkdocs_migrate.parsing.flow_extractor import DocumentFlowExtractor
from research.html_parity.rendered_evidence import (
    RenderedEvidenceExtractor,
    RenderedApiObject,
)
from research.html_parity.correlator import (
    SourceRenderedCorrelator,
    CorrelationStatus,
    CorrelationCardinality,
    CorrelationMethod,
)


def test_source_rendered_correlation_deterministic():
    """Invariant: Correlates source Markdown IR with rendered HTML evidence with 1-to-many API expansion."""
    markdown_text = """# API Guide

Introduction to the API.

::: pythonjsonlogger.json.JsonFormatter

```python
formatter = JsonFormatter()
```
"""
    html_text = """<!DOCTYPE html>
<html>
<body>
  <article>
    <h1 id="api-guide">API Guide</h1>
    <p>Introduction to the API.</p>
    <dl class="py doc-object" id="pythonjsonlogger.json.JsonFormatter">
      <dt id="pythonjsonlogger.json.JsonFormatter">class JsonFormatter</dt>
    </dl>
    <dl class="py doc-object" id="pythonjsonlogger.json.JsonFormatter.format">
      <dt id="pythonjsonlogger.json.JsonFormatter.format">format()</dt>
    </dl>
    <pre><code class="lang-python">formatter = JsonFormatter()</code></pre>
  </article>
</body>
</html>"""

    src_extractor = DocumentFlowExtractor(file_path="docs/api.md")
    src_page = src_extractor.extract_from_text(markdown_text)

    rendered_extractor = RenderedEvidenceExtractor()
    rendered_evidence = rendered_extractor.extract_from_html(
        html_text, source_path="site/api/index.html"
    )

    correlator = SourceRenderedCorrelator()
    report = correlator.correlate_page(src_page, rendered_evidence)

    assert report.logical_route == "docs/api"
    assert len(report.records) == 4

    # 1. Heading correlated 1-to-1
    h_rec = report.records[0]
    assert h_rec.status == CorrelationStatus.CORRELATED
    assert h_rec.cardinality == CorrelationCardinality.ONE_TO_ONE
    assert h_rec.method == CorrelationMethod.HEADING

    # 2. Paragraph correlated 1-to-1
    p_rec = report.records[1]
    assert p_rec.status == CorrelationStatus.CORRELATED
    assert p_rec.method == CorrelationMethod.PARAGRAPH_FINGERPRINT

    # 3. API Request correlated 1-to-Many (JsonFormatter + JsonFormatter.format)
    api_rec = report.records[2]
    assert api_rec.status == CorrelationStatus.CORRELATED
    assert api_rec.cardinality == CorrelationCardinality.ONE_TO_MANY
    assert len(api_rec.rendered_evidence_ids) == 2
    assert api_rec.method == CorrelationMethod.API_QUALIFIED_NAME

    # 4. Code block correlated 1-to-1
    code_rec = report.records[3]
    assert code_rec.status == CorrelationStatus.CORRELATED
    assert code_rec.method == CorrelationMethod.CODE_FINGERPRINT

    # 5. Invariant: 0 unmapped source constructs
    assert len(report.uncorrelated_source_ids) == 0


def test_source_rendered_correlation_ambiguity_not_guessed():
    """Invariant: Multiple identical source paragraphs with duplicate rendered HTML are marked AMBIGUOUS rather than guessed."""
    markdown_text = """# Section

Duplicate content paragraph.

Duplicate content paragraph.
"""
    html_text = """<!DOCTYPE html>
<html>
<body>
  <article>
    <h1>Section</h1>
    <p>Duplicate content paragraph.</p>
    <p>Duplicate content paragraph.</p>
  </article>
</body>
</html>"""

    src_extractor = DocumentFlowExtractor(file_path="docs/ambig.md")
    src_page = src_extractor.extract_from_text(markdown_text)

    rendered_extractor = RenderedEvidenceExtractor()
    rendered_evidence = rendered_extractor.extract_from_html(
        html_text, source_path="site/ambig/index.html"
    )

    correlator = SourceRenderedCorrelator()
    report = correlator.correlate_page(src_page, rendered_evidence)

    # First paragraph encountered finds 2 candidates -> marked AMBIGUOUS
    p_rec = report.records[1]
    assert p_rec.status == CorrelationStatus.AMBIGUOUS
    assert p_rec.cardinality == CorrelationCardinality.ONE_TO_MANY


def test_defaults_rendered_semantic_flow_and_api_parity():
    """Verify Phase 6B: Flow ordering (100%), Module Request (1:N Accounted), and 1:1 API Symbol Contracts."""
    source_md = (
        "# defaults\n\n"
        "Collection of functions for building custom `json_default` functions.\n\n"
        "In general functions come in pairs: a `*_default` function that handles decoding.\n\n"
        "And a `use_*_default` function that creates a wrapper function.\n\n"
        "::: pythonjsonlogger.defaults\n"
    )

    rendered_html = """<!DOCTYPE html>
<html>
<body>
  <article>
    <h1 id="defaults">defaults</h1>
    <p>Collection of functions for building custom <code>json_default</code> functions.</p>
    <p>In general functions come in pairs: a <code>*_default</code> function that handles decoding.</p>
    <p>And a <code>use_*_default</code> function that creates a wrapper function.</p>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.bytes_default">
      <dt id="pythonjsonlogger.defaults.bytes_default">bytes_default(value)</dt>
      <dd><p>Default decoding for bytes.</p></dd>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.dataclass_default">
      <dt id="pythonjsonlogger.defaults.dataclass_default">dataclass_default(value)</dt>
      <dd><p>Default decoding for dataclasses.</p></dd>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.date_default">
      <dt id="pythonjsonlogger.defaults.date_default">date_default(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.datetime_any">
      <dt id="pythonjsonlogger.defaults.datetime_any">datetime_any(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.datetime_default">
      <dt id="pythonjsonlogger.defaults.datetime_default">datetime_default(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.enum_default">
      <dt id="pythonjsonlogger.defaults.enum_default">enum_default(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.iterable_default">
      <dt id="pythonjsonlogger.defaults.iterable_default">iterable_default(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.mapping_default">
      <dt id="pythonjsonlogger.defaults.mapping_default">mapping_default(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.timezone_default">
      <dt id="pythonjsonlogger.defaults.timezone_default">timezone_default(value)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.defaults.uuid_default">
      <dt id="pythonjsonlogger.defaults.uuid_default">uuid_default(value)</dt>
    </dl>
  </article>
</body>
</html>"""

    src_extractor = DocumentFlowExtractor(file_path="docs/defaults.md")
    src_page = src_extractor.extract_from_text(source_md)

    rendered_extractor = RenderedEvidenceExtractor()
    rendered_evidence = rendered_extractor.extract_from_html(
        rendered_html, source_path="site/defaults/index.html"
    )

    # 1. Flow Invariant: Title -> Prose 1 -> Prose 2 -> Prose 3 -> API
    flow = rendered_evidence.semantic_flow
    assert flow[0].element_type.value == "HEADING"
    assert flow[1].element_type.value == "PARAGRAPH"
    assert flow[2].element_type.value == "PARAGRAPH"
    assert flow[3].element_type.value == "PARAGRAPH"
    assert flow[4].element_type.value == "API_REQUEST"

    # 2. Correlate Module Request -> 1:N Expanded Representation
    correlator = SourceRenderedCorrelator()
    report = correlator.correlate_page(src_page, rendered_evidence)

    assert len(report.uncorrelated_source_ids) == 0
    api_rec = report.records[4]
    assert api_rec.status == CorrelationStatus.CORRELATED
    assert api_rec.cardinality == CorrelationCardinality.ONE_TO_MANY
    assert len(api_rec.rendered_evidence_ids) == 10

    # 3. Verify Exact 1:1 API Symbol Contract for all 10 symbols
    rendered_api_objects = [
        elem.content
        for elem in rendered_evidence.semantic_flow
        if isinstance(elem.content, RenderedApiObject)
    ]
    assert len(rendered_api_objects) == 10

    expected_symbols = [
        "pythonjsonlogger.defaults.bytes_default",
        "pythonjsonlogger.defaults.dataclass_default",
        "pythonjsonlogger.defaults.date_default",
        "pythonjsonlogger.defaults.datetime_any",
        "pythonjsonlogger.defaults.datetime_default",
        "pythonjsonlogger.defaults.enum_default",
        "pythonjsonlogger.defaults.iterable_default",
        "pythonjsonlogger.defaults.mapping_default",
        "pythonjsonlogger.defaults.timezone_default",
        "pythonjsonlogger.defaults.uuid_default",
    ]
    for sym_name, obj in zip(expected_symbols, rendered_api_objects):
        assert obj.qualified_name == sym_name
        assert obj.object_kind == "function"
        assert "(" in obj.signature


def test_core_rendered_api_hierarchy_and_flow_parity():
    """Verify Phase 6B: Flow ordering, 1:N Request expansion, and complete 1:1 API Symbol Hierarchy contracts (All 7 methods)."""
    source_md = (
        "# core\n\n"
        "Core functionality shared by all JSON loggers\n\n"
        "::: pythonjsonlogger.core\n"
    )

    rendered_html = """<!DOCTYPE html>
<html>
<body>
  <article>
    <h1 id="core">core</h1>
    <p>Core functionality shared by all JSON loggers</p>
    <dl class="py doc-object data" id="pythonjsonlogger.core.LogData">
      <dt id="pythonjsonlogger.core.LogData">LogData = dict[str, Any]</dt>
    </dl>
    <dl class="py doc-object data" id="pythonjsonlogger.core.RESERVED_ATTRS">
      <dt id="pythonjsonlogger.core.RESERVED_ATTRS">RESERVED_ATTRS = (...)</dt>
    </dl>
    <dl class="py doc-object class" id="pythonjsonlogger.core.BaseJsonFormatter">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter">class BaseJsonFormatter(logging.Formatter)</dt>
      <dd><p>Base class for json log formatters.</p></dd>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.__init__">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.__init__">__init__(fmt=None, datefmt=None, style='%')</dt>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.add_fields">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.add_fields">add_fields(log_record, record, message_dict)</dt>
      <dd><p>Override to add custom fields to log record.</p></dd>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.format">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.format">format(record)</dt>
      <dd><p>Format log record to json string.</p></dd>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.formatException">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.formatException">formatException(ei)</dt>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.formatMessage">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.formatMessage">formatMessage(record)</dt>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.formatStack">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.formatStack">formatStack(stack_info)</dt>
    </dl>
    <dl class="py doc-object method" id="pythonjsonlogger.core.BaseJsonFormatter.formatTime">
      <dt id="pythonjsonlogger.core.BaseJsonFormatter.formatTime">formatTime(record, datefmt=None)</dt>
    </dl>
    <dl class="py doc-object function" id="pythonjsonlogger.core.merge_record_extra">
      <dt id="pythonjsonlogger.core.merge_record_extra">merge_record_extra(record, target, reserved=None)</dt>
      <dd><p>Merge extra attributes from LogRecord into target dict.</p></dd>
    </dl>
  </article>
</body>
</html>"""

    src_extractor = DocumentFlowExtractor(file_path="docs/core.md")
    src_page = src_extractor.extract_from_text(source_md)

    rendered_extractor = RenderedEvidenceExtractor()
    rendered_evidence = rendered_extractor.extract_from_html(
        rendered_html, source_path="site/core/index.html"
    )

    # 1. Flow Invariant: Title -> Prose -> API
    flow = rendered_evidence.semantic_flow
    assert flow[0].element_type.value == "HEADING"
    assert flow[1].element_type.value == "PARAGRAPH"
    assert flow[2].element_type.value == "API_REQUEST"

    # 2. Correlate Module Request -> 1:N Expanded Representation (1 module -> 11 symbols)
    correlator = SourceRenderedCorrelator()
    report = correlator.correlate_page(src_page, rendered_evidence)

    assert len(report.uncorrelated_source_ids) == 0
    api_rec = report.records[2]
    assert api_rec.status == CorrelationStatus.CORRELATED
    assert api_rec.cardinality == CorrelationCardinality.ONE_TO_MANY
    assert len(api_rec.rendered_evidence_ids) == 11

    # 3. Verify Exact 1:1 API Symbol Contracts across the hierarchy
    api_map = {
        obj.qualified_name: obj
        for elem in rendered_evidence.semantic_flow
        if isinstance(elem.content, RenderedApiObject)
        for obj in [elem.content]
    }
    assert len(api_map) == 11

    # A. API Symbol Identity & Object Kinds
    assert api_map["pythonjsonlogger.core.LogData"].object_kind == "data"
    assert api_map["pythonjsonlogger.core.RESERVED_ATTRS"].object_kind == "data"
    assert api_map["pythonjsonlogger.core.BaseJsonFormatter"].object_kind == "class"
    assert api_map["pythonjsonlogger.core.merge_record_extra"].object_kind == "function"

    # B. API Structural Contract (All 7 Methods of BaseJsonFormatter parentage verified)
    expected_methods = [
        "__init__",
        "add_fields",
        "format",
        "formatException",
        "formatMessage",
        "formatStack",
        "formatTime",
    ]
    for m in expected_methods:
        method_qname = f"pythonjsonlogger.core.BaseJsonFormatter.{m}"
        assert method_qname in api_map
        assert api_map[method_qname].object_kind == "method"

    # C. API Callable Contract (Signatures present and valid)
    assert (
        "class BaseJsonFormatter"
        in api_map["pythonjsonlogger.core.BaseJsonFormatter"].signature
    )
    assert (
        "format(record)"
        in api_map["pythonjsonlogger.core.BaseJsonFormatter.format"].signature
    )
    assert (
        "add_fields("
        in api_map["pythonjsonlogger.core.BaseJsonFormatter.add_fields"].signature
    )
    assert (
        "merge_record_extra("
        in api_map["pythonjsonlogger.core.merge_record_extra"].signature
    )

    # D. API Documentation Contract (Normalized docstring presence)
    assert (
        api_map["pythonjsonlogger.core.BaseJsonFormatter"].docstring
        == "Base class for json log formatters."
    )
    assert (
        api_map["pythonjsonlogger.core.BaseJsonFormatter.add_fields"].docstring
        == "Override to add custom fields to log record."
    )
    assert (
        api_map["pythonjsonlogger.core.merge_record_extra"].docstring
        == "Merge extra attributes from LogRecord into target dict."
    )
