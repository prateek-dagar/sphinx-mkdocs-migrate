# Hardened Policy Engine Tests
from pathlib import Path
import pytest
from sphinx_mkdocs_migrate.planner.policy import (
    PolicyEngine,
    FeaturePolicyCatalog,
    FeaturePolicyRule,
    SourceFeatureCategory
)
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.planner.models import RequirementProvenance, Classification

def test_feature_policy_catalog_lookup_and_lineage():
    catalog = FeaturePolicyCatalog()
    # 1. content.code.copy
    rule = catalog.lookup("content.code.copy")
    assert rule is not None
    assert "sphinx_copybutton" in rule.required_extensions
    assert "sphinx-copybutton>=0.5.2" in rule.required_packages
    assert rule.observed_in_corpus is True
    assert "pydantic" in rule.observed_in_corpus_repos

    # 2. mkdocstrings -> Sphinx built-ins autodoc + napoleon (no target_package)
    rule_docs = catalog.lookup("mkdocstrings")
    assert rule_docs is not None
    assert "sphinx.ext.autodoc" in rule_docs.required_extensions
    assert "sphinx.ext.napoleon" in rule_docs.required_extensions
    assert rule_docs.required_packages == []

    # 3. pymdownx.snippets -> TRANSFORM and requires_document_transform
    rule_snip = catalog.lookup("pymdownx.snippets")
    assert rule_snip is not None
    assert rule_snip.classification == Classification.TRANSFORM
    assert rule_snip.requires_document_transform is True

    # 4. pymdownx.emoji -> MANUAL with instruction
    rule_emoji = catalog.lookup("pymdownx.emoji")
    assert rule_emoji is not None
    assert rule_emoji.classification == Classification.MANUAL
    assert rule_emoji.manual_instruction is not None

    # 5. search.share -> UNSUPPORTED
    rule_share = catalog.lookup("search.share")
    assert rule_share is not None
    assert rule_share.classification == Classification.UNSUPPORTED

    # 6. mdx_gh_links -> built-in extlinks + configuration
    rule_gh = catalog.lookup("mdx_gh_links")
    assert rule_gh is not None
    assert "sphinx.ext.extlinks" in rule_gh.required_extensions
    assert rule_gh.required_packages == []
    assert "extlinks" in rule_gh.conf_settings

    # 7. Non-existent feature
    assert catalog.lookup("non_existent_feature_xyz") is None

def test_evidence_driven_dependency_provenance(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    docs_a = repo_a / "docs"
    docs_a.mkdir()
    (docs_a / "index.md").write_text("# Hello Doc" + chr(10), encoding="utf-8")
    cfg_a = "site_name: Project A" + chr(10) + "theme:" + chr(10) + "  name: material" + chr(10) + "  features:" + chr(10) + "    - navigation.instant" + chr(10)
    (repo_a / "mkdocs.yml").write_text(cfg_a, encoding="utf-8")

    planner_a = MigrationPlanner(repo_a)
    plan_a = planner_a.create_plan()
    assert "sphinx_copybutton" not in plan_a.get_required_extensions()
    assert not any("sphinx-copybutton" in pkg for pkg in plan_a.get_required_packages())

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()
    docs_b = repo_b / "docs"
    docs_b.mkdir()
    (docs_b / "index.md").write_text("# Hello Doc" + chr(10), encoding="utf-8")
    cfg_b = "site_name: Project B" + chr(10) + "theme:" + chr(10) + "  name: material" + chr(10) + "  features:" + chr(10) + "    - content.code.copy" + chr(10)
    (repo_b / "mkdocs.yml").write_text(cfg_b, encoding="utf-8")

    planner_b = MigrationPlanner(repo_b)
    plan_b = planner_b.create_plan()
    assert "sphinx_copybutton" in plan_b.get_required_extensions()
    copy_req = next(r for r in plan_b.requirements if r.name == "sphinx_copybutton")
    assert copy_req.provenance == RequirementProvenance.FEATURE_POLICY
    assert "theme_feature:content.code.copy" in copy_req.sources

def test_theme_policy_boundary_separation(tmp_path):
    repo = tmp_path / "theme_test"
    repo.mkdir()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Hello Doc" + chr(10), encoding="utf-8")
    cfg = "site_name: Material Theme Test" + chr(10) + "theme:" + chr(10) + "  name: material" + chr(10)
    (repo / "mkdocs.yml").write_text(cfg, encoding="utf-8")

    planner = MigrationPlanner(repo)
    plan = planner.create_plan()
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"
    assert "furo>=2024.1.0" in plan.get_required_packages()
    assert "sphinx_immaterial" not in plan.get_required_extensions()

def test_myst_syntax_extensions_derived_from_features(tmp_path):
    repo = tmp_path / "myst_test"
    repo.mkdir()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Hello Doc" + chr(10), encoding="utf-8")
    cfg = "site_name: MyST Test" + chr(10) + "markdown_extensions:" + chr(10) + "  - pymdownx.arithmatex" + chr(10) + "  - def_list" + chr(10) + "  - attr_list" + chr(10)
    (repo / "mkdocs.yml").write_text(cfg, encoding="utf-8")

    planner = MigrationPlanner(repo)
    plan = planner.create_plan()
    myst_exts = plan.proposed_sphinx_config.myst_enable_extensions
    assert "dollarmath" in myst_exts
    assert "deflist" in myst_exts
    assert "attrs_block" in myst_exts
    assert "colon_fence" in myst_exts

def test_conf_settings_and_builtin_extension_isolation(tmp_path):
    repo = tmp_path / "gh_links_test"
    repo.mkdir()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Hello Doc" + chr(10), encoding="utf-8")
    cfg = "site_name: GH Links Test" + chr(10) + "markdown_extensions:" + chr(10) + "  - mdx_gh_links" + chr(10) + "plugins:" + chr(10) + "  - mkdocstrings" + chr(10)
    (repo / "mkdocs.yml").write_text(cfg, encoding="utf-8")

    planner = MigrationPlanner(repo)
    plan = planner.create_plan()

    # Builtins are extensions but NEVER added to packages
    assert "sphinx.ext.extlinks" in plan.get_required_extensions()
    assert "sphinx.ext.autodoc" in plan.get_required_extensions()
    assert "sphinx.ext.napoleon" in plan.get_required_extensions()
    assert not any("sphinx.ext" in pkg for pkg in plan.get_required_packages())

    # Config options populated from policy
    assert "extlinks" in plan.proposed_sphinx_config.custom_options
