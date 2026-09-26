import unittest
from pathlib import Path
from sphinx_mkdocs_migrate.analyzer import ProjectAnalyzer
from sphinx_mkdocs_migrate.analyzer.navigation import NavigationAnalyzer
from sphinx_mkdocs_migrate.parsing.markdown import MarkdownParser
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind

class TestMilestone31Hardened(unittest.TestCase):
    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "sample_mkdocs"

    def test_recursive_ir_walker_and_fence_isolation(self):
        # Comprehensive test covering 4-backtick fences, tilde fences, and recursive tree walking
        sample_doc = """# Header

````markdown
Inside four backtick fence:
```python
fake nested code
!!! warning "Fake Warning inside Code"
::: fake.symbol
```
````

~~~~python
# Inside tilde fence:
!!! note "Fake Note inside Tilde"
~~~~

=== "Python Tab"

    !!! note "Real Nested Note"

        Note content.

        ```bash
        echo "real code block"
        ```
"""
        parser = MarkdownParser()
        doc_ir = parser.parse_text(sample_doc, "doc.md")

        # Use the recursive walk iterator
        all_nodes = list(doc_ir.walk())
        node_kinds = [n.kind for n in all_nodes]

        # 1. Verify exact real construct presence
        self.assertIn(NodeKind.HEADING, node_kinds)
        self.assertIn(NodeKind.TAB_SET, node_kinds)
        self.assertIn(NodeKind.TAB_ITEM, node_kinds)
        self.assertIn(NodeKind.ADMONITION, node_kinds)
        self.assertIn(NodeKind.CODE_BLOCK, node_kinds)

        # 2. Strict isolation check: NO warning or fake symbol should exist anywhere in the entire walked tree
        all_warnings = [n for n in all_nodes if n.kind == NodeKind.ADMONITION and n.metadata.get("admonition_type") == "warning"]
        self.assertEqual(len(all_warnings), 0)

        all_symbols = [n for n in all_nodes if n.kind == NodeKind.API_DIRECTIVE]
        self.assertEqual(len(all_symbols), 0)

        # 3. Exactly one real note should exist, properly nested under Python Tab
        all_notes = [n for n in all_nodes if n.kind == NodeKind.ADMONITION and n.metadata.get("admonition_type") == "note"]
        self.assertEqual(len(all_notes), 1)
        self.assertEqual(all_notes[0].metadata["title"], "Real Nested Note")

    def test_navigation_missing_references_and_orphans(self):
        nav_analyzer = NavigationAnalyzer(self.fixture_dir)
        raw_nav = [
            {"Home": "./index.md#intro"},
            {"Guides": [
                {"Getting Started": "./guide/start.md"},
                {"Missing Page": "guide/missing.md"}
            ]}
        ]
        discovered_files = [
            self.fixture_dir / "docs" / "index.md",
            self.fixture_dir / "docs" / "guide" / "start.md",
            self.fixture_dir / "docs" / "unlisted_orphan.md"
        ]
        docs_dir = self.fixture_dir / "docs"

        nav_analysis = nav_analyzer.analyze(raw_nav, discovered_files, docs_dir)

        self.assertTrue(nav_analysis.has_nav)
        self.assertEqual(nav_analysis.total_nav_entries, 4)
        
        # Missing reference validation (guide/missing.md is in nav but not on disk)
        self.assertIn("guide/missing.md", nav_analysis.missing_references)
        
        # Orphan detection (unlisted_orphan.md is on disk but not in nav)
        self.assertIn("unlisted_orphan.md", nav_analysis.orphan_documents)

    def test_full_project_analysis_orchestration(self):
        analyzer = ProjectAnalyzer(self.fixture_dir)
        report = analyzer.analyze()

        self.assertEqual(report.mkdocs_config.site_name, "Sample Project Docs")
        self.assertIsNotNone(report.navigation_analysis)
        self.assertIsNotNone(report.dependency_analysis)
        self.assertGreater(len(report.construct_findings), 0)

if __name__ == "__main__":
    unittest.main()
