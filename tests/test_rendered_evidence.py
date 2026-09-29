"""Tests for Phase 3: Rendered Evidence Extraction (Lossless DOM + Semantic Flow Projection)."""

from research.html_parity.rendered_evidence import (
    RenderedEvidenceExtractor,
    RenderedHeading,
    RenderedParagraph,
    RenderedTable,
    RenderedCodeBlock,
    RenderedAdmonition,
)
from sphinx_mkdocs_migrate.parsing.doc_ir import DocumentElementType


def test_rendered_evidence_extracts_lossless_dom_and_flow():
    """Invariant: Phase 3 extracts both the lossless DOM tree and the chronological semantic flow."""
    html_text = """<!DOCTYPE html>
<html>
<head><title>API Docs</title></head>
<body>
  <article class="md-content">
    <h1 id="api-reference">API Reference</h1>
    <p>Introduction to the API.</p>
    <h2>Configuration</h2>
    <div class="admonition note">
      <p class="admonition-title">Note</p>
      <p>Please configure your environment.</p>
    </div>
    <table class="docutils">
      <thead><tr><th>Param</th><th>Default</th></tr></thead>
      <tbody><tr><td>timeout</td><td>30</td></tr></tbody>
    </table>
    <pre><code class="lang-python">import api\napi.init()</code></pre>
  </article>
</body>
</html>"""

    extractor = RenderedEvidenceExtractor()
    evidence = extractor.extract_from_html(html_text, source_path="site/api/index.html")

    # 1. Lossless DOM Verification
    assert evidence.lossless_dom_root is not None
    assert evidence.lossless_dom_root.tag == "html"
    assert len(evidence.lossless_dom_root.children) >= 1

    # 2. Semantic Flow Chronology Verification
    flow = evidence.semantic_flow
    assert len(flow) == 6

    expected_types = [
        DocumentElementType.HEADING,
        DocumentElementType.PARAGRAPH,
        DocumentElementType.HEADING,
        DocumentElementType.ADMONITION,
        DocumentElementType.TABLE,
        DocumentElementType.CODE_BLOCK,
    ]
    actual_types = [f.element_type for f in flow]
    assert actual_types == expected_types

    # 3. Flow index and typed content verification
    h1 = flow[0].content
    assert isinstance(h1, RenderedHeading)
    assert h1.text == "API Reference"
    assert h1.level == 1

    p = flow[1].content
    assert isinstance(p, RenderedParagraph)
    assert "Introduction to the API" in p.text

    adm = flow[3].content
    assert isinstance(adm, RenderedAdmonition)
    assert adm.kind == "note"
    assert adm.title == "Note"

    tbl = flow[4].content
    assert isinstance(tbl, RenderedTable)
    assert [c.text for c in tbl.headers] == ["Param", "Default"]
    assert len(tbl.rows) == 1
    assert [c.text for c in tbl.rows[0]] == ["timeout", "30"]

    code = flow[5].content
    assert isinstance(code, RenderedCodeBlock)
    assert "api.init()" in code.code
