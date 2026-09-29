"""Tests for HtmlFlowParser: empirical DOM flow extraction, docstrings, and summary tables."""

from sphinx_mkdocs_migrate.parsing.html_flow_parser import HtmlFlowParser, HtmlFlowRole

SAMPLE_MODULE_HTML = """
<article class="md-content__inner md-typeset">
  <div class="doc doc-object doc-module">
    <h1 id="sample.core" class="doc doc-heading">
      <code>sample.core</code>
      <a href="#sample.core" class="headerlink" title="Permanent link">🔗</a>
    </h1>
    <div class="doc doc-contents first">
      <p>Core functionality for the sample logger.</p>
      <table>
        <thead>
          <tr>
            <th>Class</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>BaseFormatter</code></td>
            <td>Base formatter class.</td>
          </tr>
        </tbody>
      </table>
      <table>
        <thead>
          <tr>
            <th>Function</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>format_time</code></td>
            <td>Format a timestamp into ISO format.</td>
          </tr>
        </tbody>
      </table>
      <div class="doc doc-children">
        <div class="doc doc-object doc-class">
          <h2 id="sample.core.BaseFormatter" class="doc doc-heading">BaseFormatter</h2>
        </div>
      </div>
    </div>
  </div>
</article>
"""

SAMPLE_MULTI_PARAGRAPH_HTML = """
<article class="md-content__inner md-typeset">
  <div class="doc doc-object doc-module">
    <h1 id="sample.multi" class="doc doc-heading">sample.multi</h1>
    <div class="doc doc-contents first">
      <p>First paragraph explaining the module purpose.</p>
      <p>Second paragraph with additional context.</p>
      <p>Third paragraph acting as a TypeGuard note.</p>
      <table>
        <thead>
          <tr>
            <th>Function</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>func_a</code></td>
            <td>Does thing A.</td>
          </tr>
        </tbody>
      </table>
      <div class="doc doc-children">
      </div>
    </div>
  </div>
</article>
"""

SAMPLE_NO_DOCSTRING_HTML = """
<article class="md-content__inner md-typeset">
  <div class="doc doc-object doc-module">
    <h1 id="sample.exceptions" class="doc doc-heading">sample.exceptions</h1>
    <div class="doc doc-contents first">
      <table>
        <thead>
          <tr>
            <th>Exception</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>SampleError</code></td>
            <td>Generic error.</td>
          </tr>
        </tbody>
      </table>
      <div class="doc doc-children">
      </div>
    </div>
  </div>
</article>
"""

SAMPLE_GENERIC_PAGE_HTML = """
<article class="md-content__inner md-typeset">
  <h1 id="quick-start">Quick Start</h1>
  <p>Welcome to the quick start guide.</p>
  <div class="highlight"><pre><span></span><code>pip install sample</code></pre></div>
  <div class="admonition note">
    <p class="admonition-title">Note</p>
    <p>This is an important note.</p>
  </div>
  <ul>
    <li>Feature 1</li>
    <li>Feature 2</li>
  </ul>
</article>
"""


def test_html_flow_parser_module_with_docstring_and_tables():
    parser = HtmlFlowParser()
    flow = parser.parse_html(SAMPLE_MODULE_HTML, rel_route="reference/sample/core.md")

    assert flow.title == "sample.core"
    assert len(flow.elements) == 5

    # Sequence Invariant: 0 -> 1 -> 2 -> 3 -> 4
    for idx, el in enumerate(flow.elements):
        assert el.order_index == idx

    # Element 0: HEADING
    assert flow.elements[0].role == HtmlFlowRole.HEADING
    assert flow.elements[0].text == "sample.core"
    assert flow.elements[0].level == 1

    # Element 1: PROSE (Module docstring before tables)
    assert flow.elements[1].role == HtmlFlowRole.PROSE
    assert flow.elements[1].text == "Core functionality for the sample logger."

    # Element 2: AUTOSUMMARY (Classes table)
    assert flow.elements[2].role == HtmlFlowRole.AUTOSUMMARY
    assert "BaseFormatter" in flow.elements[2].symbols
    assert flow.elements[2].options.get("nosignatures") is True

    # Element 3: AUTOSUMMARY (Functions table)
    assert flow.elements[3].role == HtmlFlowRole.AUTOSUMMARY
    assert "format_time" in flow.elements[3].symbols

    # Element 4: API_CLASS (Autoclass directive from observed child class)
    assert flow.elements[4].role == HtmlFlowRole.API_CLASS
    assert flow.elements[4].directive == "autoclass"
    assert flow.elements[4].qname == "sample.core.BaseFormatter"
    assert flow.elements[4].options.get("members") is True
    assert flow.elements[4].options.get("show-inheritance") is True


def test_html_flow_parser_multi_paragraph_docstrings():
    parser = HtmlFlowParser()
    flow = parser.parse_html(
        SAMPLE_MULTI_PARAGRAPH_HTML, rel_route="reference/sample/multi.md"
    )

    assert len(flow.elements) == 6
    assert flow.elements[0].role == HtmlFlowRole.HEADING
    assert flow.elements[1].role == HtmlFlowRole.PROSE
    assert flow.elements[2].role == HtmlFlowRole.PROSE
    assert flow.elements[3].role == HtmlFlowRole.PROSE
    assert flow.elements[4].role == HtmlFlowRole.AUTOSUMMARY
    assert flow.elements[5].role == HtmlFlowRole.API_MODULE

    # Verify paragraph contents are preserved in exact sequence
    assert "First paragraph" in flow.elements[1].text
    assert "Second paragraph" in flow.elements[2].text
    assert "Third paragraph" in flow.elements[3].text


def test_html_flow_parser_no_docstring_module():
    parser = HtmlFlowParser()
    flow = parser.parse_html(
        SAMPLE_NO_DOCSTRING_HTML, rel_route="reference/sample/exceptions.md"
    )

    assert len(flow.elements) == 3
    # Heading -> Summary Table -> Automodule (No empty prose inserted)
    assert flow.elements[0].role == HtmlFlowRole.HEADING
    assert flow.elements[1].role == HtmlFlowRole.AUTOSUMMARY
    assert flow.elements[2].role == HtmlFlowRole.API_MODULE
    assert "SampleError" in flow.elements[1].symbols


def test_html_flow_parser_generic_markdown_page():
    parser = HtmlFlowParser()
    flow = parser.parse_html(SAMPLE_GENERIC_PAGE_HTML, rel_route="quickstart.md")

    assert flow.title == "Quick Start"
    assert len(flow.elements) == 5

    assert flow.elements[0].role == HtmlFlowRole.HEADING
    assert flow.elements[0].level == 1
    assert flow.elements[1].role == HtmlFlowRole.PROSE
    assert flow.elements[2].role == HtmlFlowRole.CODE_BLOCK
    assert flow.elements[3].role == HtmlFlowRole.ADMONITION
    assert flow.elements[4].role == HtmlFlowRole.LIST
