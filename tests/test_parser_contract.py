"""Adversarial and contract-hardening tests for Milestone 3.1d.

Tests explicitly proving the DocumentIR parser contract across 10 key boundary scenarios:
1. Exact start_line and end_line for deeply nested constructs.
2. Nested lists inside admonitions and tabs.
3. Blockquotes containing nested lists and inline links.
4. Tabs containing Admonition -> Details -> Code block hierarchy.
5. Multiple independent tab groups separated by headings/paragraphs.
6. Code fences containing fake MkDocs constructs (no spurious nodes created).
7. 4-backtick code fences enclosing 3-backtick code fences.
8. Unclosed / malformed fences (graceful degradation to end of document).
9. Links nested deeply inside lists/blockquotes retaining relative/absolute metadata.
10. MkDocs constructs in invalid contexts (e.g. inline text, inside code spans).
"""

import pytest
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind


@pytest.fixture
def parser():
    return MarkdownParser()


def test_1_exact_line_ranges_deeply_nested(parser):
    doc = (
        "# Heading 1\n"  # L1
        "\n"  # L2
        '=== "Tab Alpha"\n'  # L3
        "\n"  # L4
        '    !!! warning "Careful"\n'  # L5
        "\n"  # L6
        '        ???+ note "Expandable"\n'  # L7
        "\n"  # L8
        "            ```python\n"  # L9
        "            x = 1\n"  # L10
        "            ```\n"  # L11
        "\n"  # L12
        '=== "Tab Beta"\n'  # L13
        "    Final text.\n"  # L14
    )
    doc_ir = parser.parse_text(doc, "deep.md")

    # Root level
    nodes = doc_ir.nodes
    assert len(nodes) == 2
    assert nodes[0].kind == NodeKind.HEADING
    assert nodes[0].start_line == 1
    assert nodes[0].end_line == 1

    tab_set = nodes[1]
    assert tab_set.kind == NodeKind.TAB_SET
    assert tab_set.start_line == 3
    assert tab_set.end_line == 14
    assert len(tab_set.children) == 2

    # Tab Alpha
    tab_a = tab_set.children[0]
    assert tab_a.kind == NodeKind.TAB_ITEM
    assert tab_a.start_line == 3
    assert tab_a.end_line == 11

    # Warning Admonition
    assert len(tab_a.children) == 1
    adm = tab_a.children[0]
    assert adm.kind == NodeKind.ADMONITION
    assert adm.start_line == 5
    assert adm.end_line == 11
    assert adm.metadata["admonition_type"] == "warning"

    # Details Dropdown
    assert len(adm.children) == 1
    det = adm.children[0]
    assert det.kind == NodeKind.DETAILS_DROPDOWN
    assert det.start_line == 7
    assert det.end_line == 11

    # Code Block
    assert len(det.children) == 1
    code = det.children[0]
    assert code.kind == NodeKind.CODE_BLOCK
    assert code.start_line == 9
    assert code.end_line == 11

    # Tab Beta
    tab_b = tab_set.children[1]
    assert tab_b.kind == NodeKind.TAB_ITEM
    assert tab_b.start_line == 13
    assert tab_b.end_line == 14


def test_2_nested_lists_inside_admonitions_and_tabs(parser):
    doc = (
        '!!! note "List Container"\n'
        "    - Item 1\n"
        "        * Sub-item A\n"
        "        * Sub-item B\n"
        "    - Item 2\n"
    )
    doc_ir = parser.parse_text(doc, "nested_lists.md")
    all_nodes = list(doc_ir.walk())

    adm = doc_ir.nodes[0]
    assert adm.kind == NodeKind.ADMONITION

    lists = [n for n in all_nodes if n.kind == NodeKind.LIST]
    items = [n for n in all_nodes if n.kind == NodeKind.LIST_ITEM]
    assert len(lists) >= 1
    assert len(items) >= 2


def test_3_blockquotes_containing_nested_lists_and_links(parser):
    doc = (
        "> Quote title\n"
        ">\n"
        "> 1. First step: see [Docs](https://example.com/guide)\n"
        "> 2. Second step: see [Local](../intro.md)\n"
    )
    doc_ir = parser.parse_text(doc, "quote_lists.md")
    all_nodes = list(doc_ir.walk())

    assert any(n.kind == NodeKind.BLOCK_QUOTE for n in all_nodes)
    links = [n for n in all_nodes if n.kind == NodeKind.LINK_REF]
    assert len(links) == 2

    ext_link = next(lnk for lnk in links if lnk.raw_text == "Docs")
    assert ext_link.metadata["is_external"] is True
    assert ext_link.metadata["href"] == "https://example.com/guide"

    int_link = next(lnk for lnk in links if lnk.raw_text == "Local")
    assert int_link.metadata["is_external"] is False
    assert int_link.metadata["href"] == "../intro.md"


def test_4_tab_admonition_details_code_hierarchy(parser):
    doc = (
        '=== "Python"\n'
        '    !!! tip "Tip Box"\n'
        '        ??? info "Details Inside"\n'
        "            ```bash\n"
        "            pip install sphinx\n"
        "            ```\n"
    )
    doc_ir = parser.parse_text(doc, "hierarchy.md")
    tab_set = doc_ir.nodes[0]
    tab_item = tab_set.children[0]
    adm = tab_item.children[0]
    det = adm.children[0]
    code = det.children[0]

    assert tab_item.kind == NodeKind.TAB_ITEM
    assert adm.kind == NodeKind.ADMONITION
    assert det.kind == NodeKind.DETAILS_DROPDOWN
    assert code.kind == NodeKind.CODE_BLOCK
    assert code.metadata["info_string"] == "bash"


def test_5_multiple_independent_tab_groups(parser):
    doc = (
        '=== "Group 1 - Tab 1"\n'
        "    Group 1 content\n"
        "\n"
        "## Section Heading\n"
        "\n"
        '=== "Group 2 - Tab 1"\n'
        "    Group 2 content\n"
    )
    doc_ir = parser.parse_text(doc, "multi_tabs.md")
    tab_sets = [n for n in doc_ir.nodes if n.kind == NodeKind.TAB_SET]
    assert len(tab_sets) == 2
    assert tab_sets[0].children[0].metadata["title"] == "Group 1 - Tab 1"
    assert tab_sets[1].children[0].metadata["title"] == "Group 2 - Tab 1"
    assert doc_ir.nodes[1].kind == NodeKind.HEADING


def test_6_code_fences_containing_fake_constructs(parser):
    doc = (
        "```python\n"
        "# This should NOT trigger any IR directive nodes\n"
        '!!! note "Fake Note"\n'
        '=== "Fake Tab"\n'
        '???+ details "Fake Details"\n'
        "::: fake.symbol.Directive\n"
        '--8<-- "fake_snippet.py"\n'
        "```\n"
    )
    doc_ir = parser.parse_text(doc, "code_isolation.md")
    all_nodes = list(doc_ir.walk())

    assert len(doc_ir.nodes) == 1
    assert doc_ir.nodes[0].kind == NodeKind.CODE_BLOCK
    assert not any(n.kind == NodeKind.ADMONITION for n in all_nodes)
    assert not any(n.kind == NodeKind.TAB_SET for n in all_nodes)
    assert not any(n.kind == NodeKind.DETAILS_DROPDOWN for n in all_nodes)
    assert not any(n.kind == NodeKind.API_DIRECTIVE for n in all_nodes)
    assert not any(n.kind == NodeKind.SNIPPET_INCLUDE for n in all_nodes)


def test_7_four_backtick_fence_enclosing_three_backtick_fence(parser):
    doc = (
        "````markdown\n"
        "Here is an example markdown code block:\n"
        "```python\n"
        "def hello():\n"
        "    return 'world'\n"
        "```\n"
        "````\n"
    )
    doc_ir = parser.parse_text(doc, "nested_fence.md")
    nodes = doc_ir.nodes

    assert len(nodes) == 1
    assert nodes[0].kind == NodeKind.CODE_BLOCK
    assert nodes[0].start_line == 1
    assert nodes[0].end_line == 7
    assert "```python" in nodes[0].raw_text


def test_8_unclosed_code_fence_graceful_handling(parser):
    doc = "```python\ndef unclosed():\n    pass\n"
    doc_ir = parser.parse_text(doc, "unclosed.md")
    assert len(doc_ir.nodes) == 1
    assert doc_ir.nodes[0].kind == NodeKind.CODE_BLOCK
    assert doc_ir.nodes[0].start_line == 1


def test_9_links_in_deep_container_structures(parser):
    doc = '=== "Tab"\n    - Item with [Nested Link](./sub/page.md#anchor)\n'
    doc_ir = parser.parse_text(doc, "container_link.md")
    all_nodes = list(doc_ir.walk())
    link_nodes = [n for n in all_nodes if n.kind == NodeKind.LINK_REF]

    assert len(link_nodes) == 1
    link = link_nodes[0]
    assert link.raw_text == "Nested Link"
    assert link.metadata["href"] == "./sub/page.md#anchor"
    assert link.metadata["is_external"] is False


def test_10_inline_mkdocs_syntax_not_recognized_as_blocks(parser):
    doc = (
        'Here is some text with `!!! note "inline code"` and `::: symbol` inside code spans.\n'
        "\n"
        'Also sentence containing === "Not A Tab" in the middle of a paragraph.\n'
    )
    doc_ir = parser.parse_text(doc, "inline_text.md")
    all_nodes = list(doc_ir.walk())

    # Only paragraphs / text, no block constructs
    assert not any(n.kind == NodeKind.ADMONITION for n in all_nodes)
    assert not any(n.kind == NodeKind.TAB_SET for n in all_nodes)
    assert not any(n.kind == NodeKind.API_DIRECTIVE for n in all_nodes)
    assert all(n.kind in (NodeKind.PARAGRAPH, NodeKind.LINK_REF) for n in all_nodes)
