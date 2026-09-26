import unittest
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind

class TestMarkdownItAdapter(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def test_standard_markdown_constructs(self):
        doc_text = """# Main Heading

Here is a paragraph with [a relative link](docs/guide.md) and some text.

- List Item 1
- List Item 2
  - Sub Item A

> This is a blockquote quote.

```python
# Fenced code block
def hello():
    return "world"
```

~~~bash
# Tilde fence
echo "hello from tilde"
~~~
"""
        doc_ir = self.parser.parse_text(doc_text, "test_std.md")
        all_nodes = list(doc_ir.walk())
        node_kinds = [n.kind for n in all_nodes]

        self.assertIn(NodeKind.HEADING, node_kinds)
        self.assertIn(NodeKind.PARAGRAPH, node_kinds)
        self.assertIn(NodeKind.LIST, node_kinds)
        self.assertIn(NodeKind.LIST_ITEM, node_kinds)
        self.assertIn(NodeKind.BLOCK_QUOTE, node_kinds)
        self.assertIn(NodeKind.CODE_BLOCK, node_kinds)
        self.assertIn(NodeKind.LINK_REF, node_kinds)

        # Check link ref metadata
        link_nodes = [n for n in all_nodes if n.kind == NodeKind.LINK_REF]
        self.assertEqual(len(link_nodes), 1)
        self.assertEqual(link_nodes[0].metadata["target_path"], "docs/guide.md")

    def test_mkdocs_constructs_and_code_isolation(self):
        doc_text = """
=== "Python Tab"

    !!! note "Nested Admonition"

        Paragraph inside note.

        ```python
        # Code fence: fake directives must NOT create IR nodes
        !!! warning "Fake Warning"
        ::: fake.symbol
        ```

=== "Rust Tab"

    ??? tip "Rust Details"

        Details content.
"""
        doc_ir = self.parser.parse_text(doc_text, "test_mkdocs.md")
        all_nodes = list(doc_ir.walk())
        node_kinds = [n.kind for n in all_nodes]

        self.assertIn(NodeKind.TAB_SET, node_kinds)
        self.assertIn(NodeKind.TAB_ITEM, node_kinds)
        self.assertIn(NodeKind.ADMONITION, node_kinds)
        self.assertIn(NodeKind.DETAILS_DROPDOWN, node_kinds)
        self.assertIn(NodeKind.CODE_BLOCK, node_kinds)

        # Strict isolation check
        fake_warnings = [n for n in all_nodes if n.kind == NodeKind.ADMONITION and n.metadata.get("admonition_type") == "warning"]
        self.assertEqual(len(fake_warnings), 0)

        fake_symbols = [n for n in all_nodes if n.kind == NodeKind.API_DIRECTIVE]
        self.assertEqual(len(fake_symbols), 0)

if __name__ == "__main__":
    unittest.main()
