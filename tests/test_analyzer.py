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
        all_warnings = [
            n
            for n in all_nodes
            if n.kind == NodeKind.ADMONITION
            and n.metadata.get("admonition_type") == "warning"
        ]
        self.assertEqual(len(all_warnings), 0)

        all_symbols = [n for n in all_nodes if n.kind == NodeKind.API_DIRECTIVE]
        self.assertEqual(len(all_symbols), 0)

        # 3. Exactly one real note should exist, properly nested under Python Tab
        all_notes = [
            n
            for n in all_nodes
            if n.kind == NodeKind.ADMONITION
            and n.metadata.get("admonition_type") == "note"
        ]
        self.assertEqual(len(all_notes), 1)
        self.assertEqual(all_notes[0].metadata["title"], "Real Nested Note")

    def test_navigation_missing_references_and_orphans(self):
        nav_analyzer = NavigationAnalyzer(self.fixture_dir)
        raw_nav = [
            {"Home": "./index.md#intro"},
            {
                "Guides": [
                    {"Getting Started": "./guide/start.md"},
                    {"Missing Page": "guide/missing.md"},
                ]
            },
        ]
        discovered_files = [
            self.fixture_dir / "docs" / "index.md",
            self.fixture_dir / "docs" / "guide" / "start.md",
            self.fixture_dir / "docs" / "unlisted_orphan.md",
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

        # Verify effective configuration resolution
        self.assertIn("theme.name", report.effective_config.properties)
        self.assertEqual(report.effective_config.get("theme.name"), "material")

        # Verify document flows extracted in authored sequence
        self.assertGreater(len(report.document_flows), 0)

        # Verify migration requirements derived
        self.assertGreater(len(report.migration_requirements), 0)

        # Verify canonical hashing
        c_hash = report.canonical_hash()
        self.assertEqual(len(c_hash), 64)

    def test_canonical_identity_source_invariance_contract(self):
        """Verify contract:

        source change -> canonical identity changes
        environment-only change -> canonical identity unchanged & environment fingerprint changes
        """
        from sphinx_mkdocs_migrate.analyzer.models import (
            ProjectAnalysisReport,
            VersionEnvironment,
            PackageVersionInfo,
        )

        # Report A: mkdocs-material >=8.5, resolved 9.7.7
        env_a = VersionEnvironment(
            python_constraint=">=3.10",
            python_resolved_version="3.12.7",
            python_resolution_status="INSTALLED_RESOLVED",
            packages={
                "mkdocs-material": PackageVersionInfo(
                    package_name="mkdocs-material",
                    declared_spec=">=8.5",
                    resolved_version="9.7.7",
                    resolution_status="INSTALLED_RESOLVED",
                    resolution_source="CURRENT_PYTHON_ENVIRONMENT",
                    satisfies_declared_constraint=True,
                )
            },
        )
        report_a = ProjectAnalysisReport(project_root="/dummy/repo", version_env=env_a)

        # Report B: mkdocs-material >=8.5, resolved 9.8.0 under Python 3.11
        env_b = VersionEnvironment(
            python_constraint=">=3.10",
            python_resolved_version="3.11.9",
            python_resolution_status="INSTALLED_RESOLVED",
            packages={
                "mkdocs-material": PackageVersionInfo(
                    package_name="mkdocs-material",
                    declared_spec=">=8.5",
                    resolved_version="9.8.0",
                    resolution_status="INSTALLED_RESOLVED",
                    resolution_source="CURRENT_PYTHON_ENVIRONMENT",
                    satisfies_declared_constraint=True,
                )
            },
        )
        report_b = ProjectAnalysisReport(project_root="/dummy/repo", version_env=env_b)

        # Invariant 1: Source identity MUST match despite environment difference
        self.assertEqual(report_a.canonical_hash(), report_b.canonical_hash())

        # Invariant 2: Observed environment fingerprint MUST differ
        self.assertNotEqual(
            report_a.environment_fingerprint(), report_b.environment_fingerprint()
        )

        # Report C: Alter the source declaration itself: >=8.5 -> >=9.0
        env_c = VersionEnvironment(
            python_constraint=">=3.10",
            python_resolved_version="3.12.7",
            python_resolution_status="INSTALLED_RESOLVED",
            packages={
                "mkdocs-material": PackageVersionInfo(
                    package_name="mkdocs-material",
                    declared_spec=">=9.0",
                    resolved_version="9.7.7",
                    resolution_status="INSTALLED_RESOLVED",
                    resolution_source="CURRENT_PYTHON_ENVIRONMENT",
                    satisfies_declared_constraint=True,
                )
            },
        )
        report_c = ProjectAnalysisReport(project_root="/dummy/repo", version_env=env_c)

        # Invariant 3: Source declaration change MUST alter canonical hash
        self.assertNotEqual(report_a.canonical_hash(), report_c.canonical_hash())

    def test_unresolved_package_canonical_invariance(self):
        """Verify that transitioning an installed package to UNRESOLVED status

        does not alter the source repository canonical hash.
        """
        from sphinx_mkdocs_migrate.analyzer.models import (
            ProjectAnalysisReport,
            VersionEnvironment,
            PackageVersionInfo,
        )

        # Report Installed
        env_installed = VersionEnvironment(
            packages={
                "mkdocstrings": PackageVersionInfo(
                    package_name="mkdocstrings",
                    declared_spec=">=0.24",
                    resolved_version="0.25.1",
                    resolution_status="INSTALLED_RESOLVED",
                    resolution_source="CURRENT_PYTHON_ENVIRONMENT",
                    satisfies_declared_constraint=True,
                )
            }
        )
        report_installed = ProjectAnalysisReport(
            project_root="/dummy/repo", version_env=env_installed
        )

        # Report Unresolved
        env_unresolved = VersionEnvironment(
            packages={
                "mkdocstrings": PackageVersionInfo(
                    package_name="mkdocstrings",
                    declared_spec=">=0.24",
                    resolved_version=None,
                    resolution_status="UNRESOLVED",
                    resolution_source=None,
                    satisfies_declared_constraint=None,
                )
            }
        )
        report_unresolved = ProjectAnalysisReport(
            project_root="/dummy/repo", version_env=env_unresolved
        )

        # Source canonical hash remains strictly invariant
        self.assertEqual(
            report_installed.canonical_hash(), report_unresolved.canonical_hash()
        )
        self.assertNotEqual(
            report_installed.environment_fingerprint(),
            report_unresolved.environment_fingerprint(),
        )

    def test_comprehensive_ci_analyzer(self):
        """Verify CIAnalyzer discovers GitHub Actions, tox, RTD, Makefile, nox, and GitLab CI."""
        import tempfile
        from sphinx_mkdocs_migrate.analyzer.ci import CIAnalyzer

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)

            # Setup GitHub Actions
            wf_dir = tmp / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            (wf_dir / "docs.yml").write_text(
                "jobs:\n  deploy:\n    steps:\n      - uses: actions/checkout@v4\n"
                "      - uses: astral-sh/setup-uv@v3\n      - run: uvx tox -e docs\n"
                "      - run: mkdocs gh-deploy\n",
                encoding="utf-8",
            )

            # Setup tox.ini
            (tmp / "tox.ini").write_text(
                "[tox]\nenvlist = py312\n[testenv:docs]\ndependency_groups = dev\ncommands =\n    mkdocs build\n",
                encoding="utf-8",
            )

            # Setup .readthedocs.yaml
            (tmp / ".readthedocs.yaml").write_text(
                "version: 2\nmkdocs:\n  configuration: mkdocs.yml\n", encoding="utf-8"
            )

            # Setup Makefile
            (tmp / "Makefile").write_text("docs:\n\tmkdocs build\n", encoding="utf-8")

            # Setup noxfile.py
            (tmp / "noxfile.py").write_text(
                "import nox\n@nox.session\ndef docs(session):\n    pass\n",
                encoding="utf-8",
            )

            # Setup .gitlab-ci.yml
            (tmp / ".gitlab-ci.yml").write_text(
                "pages:\n  script:\n    - mkdocs build\n", encoding="utf-8"
            )

            from unittest.mock import patch

            with patch(
                "sphinx_mkdocs_migrate.analyzer.ci.resolve_github_action_ref",
                return_value=("v7.0.1", "3d3c42e5aac5ba805825da76410c181273ba90b1"),
            ):
                ci_analysis = CIAnalyzer(tmp).analyze()

            self.assertEqual(ci_analysis.ci_system, "github_actions")
            self.assertTrue(ci_analysis.github_actions_detected)
            self.assertTrue(ci_analysis.has_mkdocs_deploy)
            self.assertTrue(ci_analysis.has_tox_in_ci)
            self.assertTrue(ci_analysis.has_uv_in_ci)
            self.assertEqual(ci_analysis.checkout_action_ref, "v4")
            self.assertEqual(ci_analysis.setup_uv_action_ref, "v3")
            self.assertIn(".github/workflows/docs.yml", ci_analysis.docs_workflow_files)

            self.assertTrue(ci_analysis.has_tox)
            self.assertTrue(ci_analysis.tox_has_docs_env)
            self.assertEqual(ci_analysis.tox_dependency_spec, "dependency_groups = dev")

            self.assertTrue(ci_analysis.readthedocs_detected)
            self.assertEqual(ci_analysis.rtd_config_file, ".readthedocs.yaml")

            self.assertTrue(ci_analysis.has_makefile)
            self.assertTrue(ci_analysis.has_nox)
            self.assertTrue(ci_analysis.gitlab_ci_detected)

    def test_mkdocs_config_path_and_obsolete_files_detection(self):
        import tempfile
        from sphinx_mkdocs_migrate.analyzer.mkdocs import (
            MkDocsConfigAnalyzer,
            detect_obsolete_mkdocs_files,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            cfg = tmp / "mkdocs.yml"
            cfg.write_text("site_name: TestProject\n", encoding="utf-8")
            analyzer = MkDocsConfigAnalyzer(tmp)
            analysis = analyzer.analyze()

            self.assertEqual(analysis.config_file_path, "mkdocs.yml")
            self.assertEqual(analysis.site_name, "TestProject")

            obsolete = detect_obsolete_mkdocs_files(tmp, analysis)
            self.assertIn("mkdocs.yml", obsolete)


if __name__ == "__main__":
    unittest.main()
