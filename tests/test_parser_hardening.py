"""Comprehensive hardening tests for Milestone 3.1c:
1. Exact source line preservation across nested tab -> admonition -> details -> code.
2. Multiple tab sets in a single document.
3. Complex nested list and blockquote structures.
4. Generic destination-neutral link extraction in nested containers.
5. Markdown fence edge cases (info strings with attributes, variable length backticks/tildes).
"""

import unittest
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind


class TestMilestone31cHardening(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def test_exact_source_line_mapping_in_deep_nesting(self):
        # 1-indexed line test
        doc = (
            "# Top Heading\n"  # 1
            "\n"  # 2
            '=== "Tab 1"\n'  # 3
            "\n"  # 4
            '    !!! note "Nested Note"\n'  # 5
            "\n"  # 6
            '        ???+ details "Deep Details"\n'  # 7
            "\n"  # 8
            "            ```python {#my-id}\n"  # 9
            "            print('deep code')\n"  # 10
            "            ```\n"  # 11
            "\n"  # 12
            '=== "Tab 2"\n'  # 13
            "\n"  # 14
            "    Paragraph in Tab 2.\n"  # 15
        )
        doc_ir = self.parser.parse_text(doc, "nested.md")
        nodes = doc_ir.nodes

        # Root level: Heading (1) and TabSet (3-15)
        self.assertEqual(nodes[0].kind, NodeKind.HEADING)
        self.assertEqual(nodes[0].start_line, 1)

        tab_set = nodes[1]
        self.assertEqual(tab_set.kind, NodeKind.TAB_SET)
        self.assertEqual(tab_set.start_line, 3)
        self.assertEqual(tab_set.end_line, 15)
        self.assertEqual(len(tab_set.children), 2)

        tab1 = tab_set.children[0]
        self.assertEqual(tab1.kind, NodeKind.TAB_ITEM)
        self.assertEqual(tab1.metadata["title"], "Tab 1")
        self.assertEqual(tab1.start_line, 3)

        # Inside Tab 1: Admonition at line 5
        self.assertEqual(len(tab1.children), 1)
        adm = tab1.children[0]
        self.assertEqual(adm.kind, NodeKind.ADMONITION)
        self.assertEqual(adm.metadata["admonition_type"], "note")
        self.assertEqual(adm.start_line, 5)

        # Inside Admonition: Details Dropdown at line 7
        self.assertEqual(len(adm.children), 1)
        det = adm.children[0]
        self.assertEqual(det.kind, NodeKind.DETAILS_DROPDOWN)
        self.assertEqual(det.metadata["title"], "Deep Details")
        self.assertEqual(det.start_line, 7)

        # Inside Details: Code Block at line 9-11
        self.assertEqual(len(det.children), 1)
        code = det.children[0]
        self.assertEqual(code.kind, NodeKind.CODE_BLOCK)
        self.assertEqual(code.start_line, 9)
        self.assertEqual(code.end_line, 11)
        self.assertEqual(code.metadata["info_string"], "python {#my-id}")

        # Tab 2 at line 13
        tab2 = tab_set.children[1]
        self.assertEqual(tab2.kind, NodeKind.TAB_ITEM)
        self.assertEqual(tab2.metadata["title"], "Tab 2")
        self.assertEqual(tab2.start_line, 13)

    def test_multiple_independent_tab_sets(self):
        doc = (
            '=== "Set 1 Tab A"\n'  # 1
            "    Content A\n"  # 2
            '=== "Set 1 Tab B"\n'  # 3
            "    Content B\n"  # 4
            "\n"  # 5
            "Paragraph between sets.\n"  # 6
            "\n"  # 7
            '=== "Set 2 Tab X"\n'  # 8
            "    Content X\n"  # 9
            '=== "Set 2 Tab Y"\n'  # 10
            "    Content Y\n"  # 11
        )
        doc_ir = self.parser.parse_text(doc, "multi_tabs.md")

        tab_sets = [n for n in doc_ir.nodes if n.kind == NodeKind.TAB_SET]
        self.assertEqual(len(tab_sets), 2)

        # Set 1
        self.assertEqual(tab_sets[0].start_line, 1)
        self.assertEqual(len(tab_sets[0].children), 2)
        self.assertEqual(tab_sets[0].children[0].metadata["title"], "Set 1 Tab A")
        self.assertEqual(tab_sets[0].children[1].metadata["title"], "Set 1 Tab B")

        # Paragraph in middle
        middle_p = [n for n in doc_ir.nodes if n.kind == NodeKind.PARAGRAPH]
        self.assertEqual(len(middle_p), 1)
        self.assertEqual(middle_p[0].start_line, 6)

        # Set 2
        self.assertEqual(tab_sets[1].start_line, 8)
        self.assertEqual(len(tab_sets[1].children), 2)
        self.assertEqual(tab_sets[1].children[0].metadata["title"], "Set 2 Tab X")
        self.assertEqual(tab_sets[1].children[1].metadata["title"], "Set 2 Tab Y")

    def test_nested_lists_and_blockquotes_with_links(self):
        doc = (
            "> Blockquote containing list:\n"
            "> - Item 1 with [Relative Link](../api/client.md)\n"
            "> - Item 2 with [External Link](https://sphinx-doc.org)\n"
        )
        doc_ir = self.parser.parse_text(doc, "nested_containers.md")

        all_nodes = list(doc_ir.walk())
        link_nodes = [n for n in all_nodes if n.kind == NodeKind.LINK_REF]

        self.assertEqual(len(link_nodes), 2)
        rel_link = next(n for n in link_nodes if n.raw_text == "Relative Link")
        self.assertEqual(rel_link.metadata["href"], "../api/client.md")
        self.assertFalse(rel_link.metadata["is_external"])

        ext_link = next(n for n in link_nodes if n.raw_text == "External Link")
        self.assertEqual(ext_link.metadata["href"], "https://sphinx-doc.org")
        self.assertTrue(ext_link.metadata["is_external"])

    def test_fence_grammar_variations_and_attributes(self):
        doc = (
            "```python {hl_lines=[1, 3] linenums=1}\n"
            "def foo():\n"
            "    return 42\n"
            "```\n"
            "\n"
            "~~~json\n"
            '{"key": "val"}\n'
            "~~~\n"
        )
        doc_ir = self.parser.parse_text(doc, "fences.md")

        code_blocks = [n for n in doc_ir.nodes if n.kind == NodeKind.CODE_BLOCK]
        self.assertEqual(len(code_blocks), 2)

        self.assertEqual(
            code_blocks[0].metadata["info_string"],
            "python {hl_lines=[1, 3] linenums=1}",
        )
        self.assertEqual(code_blocks[1].metadata["info_string"], "json")


if __name__ == "__main__":
    unittest.main()
