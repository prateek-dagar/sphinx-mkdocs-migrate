"""Tests for Phase 5: DocumentationPlan Synthesis, Flow Ordering, and Provenance."""

import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.planner.models import ApiDirectiveKind, DocumentationPlan


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures" / "sample_mkdocs"


def test_documentation_plan_synthesis_and_flow_order(fixture_dir):
    """Invariant: MigrationPlanner produces a fully structured DocumentationPlan with ordered flow actions and traceability."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()

    assert plan.documentation_plan is not None
    doc_plan: DocumentationPlan = plan.documentation_plan

    # 1. Pages and Artifacts
    assert len(doc_plan.pages) > 0

    # Check that each page has ordered flow actions
    for page in doc_plan.pages:
        assert len(page.flow_actions) > 0
        for idx, act in enumerate(page.flow_actions):
            assert act.order_index == idx
            assert act.source_construct_id is not None
            assert act.source_construct_id.startswith("doc:")

        # Verify provenance attached
        assert page.artifact_provenance is not None
        assert len(page.artifact_provenance.source_construct_ids) == len(
            page.flow_actions
        )

    # 2. API Generation Strategies
    assert len(doc_plan.api_strategies) >= 1
    first_api = doc_plan.api_strategies[0]
    assert "sample.client.Client" in first_api.object_path
    assert first_api.directive_kind == ApiDirectiveKind.AUTOCLASS
    assert first_api.source_construct_id is not None

    # 3. Navigation Plan & Toctrees
    assert len(doc_plan.navigation.root_toctrees) > 0
    assert "index.md" in doc_plan.navigation.root_toctrees

    # 4. Cross References & Assets
    assert len(doc_plan.cross_references) > 0

    # 5. System Capability Accountability Audit
    assert len(doc_plan.capability_accountability) > 0
    cap_names = {c.capability_name for c in doc_plan.capability_accountability}
    assert "material" in cap_names

    # 6. Deterministic canonical hash includes documentation_plan
    plan_dict = plan.canonical_dict()
    assert "documentation_plan" in plan_dict
    assert len(plan_dict["documentation_plan"]["pages"]) == len(doc_plan.pages)


def test_defaults_semantic_flow_preservation(tmp_path: Path):
    """Verify Phase 6A: defaults.md preserves exact semantic sequence (H1 -> Prose -> Prose -> Prose -> API)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    defaults_content = (
        "# defaults\n\n"
        "Collection of functions for building custom `json_default` functions.\n\n"
        "In general functions come in pairs: a `*_default` function that handles decoding.\n\n"
        "And a `use_*_default` function that creates a wrapper function.\n\n"
        "::: pythonjsonlogger.defaults\n"
    )
    (docs_dir / "defaults.md").write_text(defaults_content, encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Test\nplugins:\n  - mkdocstrings\n", encoding="utf-8"
    )

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    doc_plan = plan.documentation_plan
    assert doc_plan is not None
    defaults_page = next(p for p in doc_plan.pages if "defaults" in p.target_path)

    # Invariant: Flow actions strictly match authored element sequence
    flow_acts = defaults_page.flow_actions
    assert len(flow_acts) == 5
    assert flow_acts[0].element_type == "HEADING"
    assert flow_acts[1].element_type == "PARAGRAPH"
    assert flow_acts[2].element_type == "PARAGRAPH"
    assert flow_acts[3].element_type == "PARAGRAPH"
    assert flow_acts[4].element_type == "API_REQUEST"

    # Verify order indices are sequential
    for idx, act in enumerate(flow_acts):
        assert act.order_index == idx


def test_core_api_hierarchy_preservation(tmp_path: Path):
    """Verify Phase 6A: core.md preserves class/method/attribute hierarchy and introductory prose."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    core_content = (
        "# core\n\n"
        "Core functionality shared by all JSON loggers\n\n"
        "::: pythonjsonlogger.core\n"
    )
    (docs_dir / "core.md").write_text(core_content, encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Test\nplugins:\n  - mkdocstrings\n", encoding="utf-8"
    )

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    doc_plan = plan.documentation_plan
    assert doc_plan is not None
    core_page = next(p for p in doc_plan.pages if "core" in p.target_path)

    # Invariant 1: Flow actions sequence (H1 -> Prose -> API)
    flow_acts = core_page.flow_actions
    assert len(flow_acts) == 3
    assert flow_acts[0].element_type == "HEADING"
    assert flow_acts[1].element_type == "PARAGRAPH"
    assert flow_acts[2].element_type == "API_REQUEST"

    # Invariant 2: API Strategy correctly synthesized from API request
    api_strat = next(
        s for s in doc_plan.api_strategies if s.object_path == "pythonjsonlogger.core"
    )
    assert api_strat.directive_kind == ApiDirectiveKind.AUTOMODULE
    assert api_strat.source_construct_id == flow_acts[2].source_construct_id


def test_generated_reference_document_flow_ordering(tmp_path: Path):
    """Universal Invariant: Generated reference documents must preserve exact MkDocs flow across both cases:

    Case 1: Module WITH docstring -> Heading -> Docstring -> Autosummary Rubric -> Automodule
    Case 2: Module WITHOUT docstring -> Heading -> Autosummary Rubric -> Automodule (no extraneous/empty paragraph)
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    src_dir = tmp_path / "src" / "samplepkg"
    src_dir.mkdir(parents=True)

    # Case 1: Python module WITH docstring and function
    mod_with_doc = (
        '"""Utilities for Sample Package."""\n\n'
        "def helper_func():\n"
        '    """Helper docstring."""\n'
        "    return True\n"
    )
    (src_dir / "with_doc.py").write_text(mod_with_doc, encoding="utf-8")

    # Case 2: Python module WITHOUT docstring
    mod_no_doc = "def bare_func():\n    return False\n"
    (src_dir / "no_doc.py").write_text(mod_no_doc, encoding="utf-8")
    (src_dir / "__init__.py").write_text("", encoding="utf-8")

    mkdocs_yml = (
        "site_name: FlowTest\n"
        "plugins:\n"
        "  - gen-files:\n"
        "      scripts:\n"
        "        - scripts/gen_nav.py\n"
    )
    (tmp_path / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    assert len(plan.generated_documents) >= 2

    # --- Verify Case 1: Module WITH docstring ---
    doc1 = next(d for d in plan.generated_documents if "with_doc.md" in d.target_path)
    lines1 = doc1.content.strip().splitlines()
    assert lines1[0] == "# with_doc"
    assert lines1[2] == "Utilities for Sample Package."
    assert ".. rubric:: Functions" in doc1.content
    assert ".. autosummary::" in doc1.content

    # Docstring MUST precede the autosummary rubric
    docstring_pos = doc1.content.index("Utilities for Sample Package.")
    rubric_pos = doc1.content.index(".. rubric:: Functions")
    automodule_pos = doc1.content.index(".. automodule:: samplepkg.with_doc")
    assert docstring_pos < rubric_pos < automodule_pos

    # --- Verify Case 2: Module WITHOUT docstring ---
    doc2 = next(d for d in plan.generated_documents if "no_doc.md" in d.target_path)
    lines2 = doc2.content.strip().splitlines()
    assert lines2[0] == "# no_doc"
    # Immediately transitions to eval-rst code block without phantom or empty docstring lines
    assert lines2[2] == "```{eval-rst}"
    assert ".. rubric:: Functions" in doc2.content
    assert ".. autosummary::" in doc2.content
    assert "None" not in doc2.content


def test_html_flow_three_block_architecture_and_ordering(tmp_path: Path):
    """Verify 3-block architecture when built HTML is available:
    Block 1: automodule with :no-members:
    Block 2: autosummaries with rubrics and ~Symbol
    Block 3: individual member directives in exact empirical DOM sequence
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    src_dir = tmp_path / "src" / "samplepkg"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "core.py").write_text('"""Core module docstring."""\n', encoding="utf-8")

    # Create built site HTML matching MkDocs output
    site_ref_dir = tmp_path / "site" / "reference" / "samplepkg" / "core"
    site_ref_dir.mkdir(parents=True)
    mock_html = """
    <article class="md-content__inner md-typeset">
      <div class="doc doc-object doc-module">
        <h1 id="samplepkg.core" class="doc doc-heading">samplepkg.core</h1>
        <div class="doc doc-contents first">
          <p>Core module docstring.</p>
          <table>
            <thead><tr><th>Class</th><th>Description</th></tr></thead>
            <tbody><tr><td>BaseClass</td><td>Desc</td></tr></tbody>
          </table>
          <table>
            <thead><tr><th>Function</th><th>Description</th></tr></thead>
            <tbody><tr><td>helper_func</td><td>Desc</td></tr></tbody>
          </table>
          <table>
            <thead><tr><th>Attribute</th><th>Description</th></tr></thead>
            <tbody>
              <tr><td>LogData</td><td>Desc</td></tr>
              <tr><td>RESERVED_ATTRS</td><td>Desc</td></tr>
            </tbody>
          </table>
          <div class="doc doc-children">
            <div class="doc doc-object doc-attribute">
              <h2 id="samplepkg.core.LogData" class="doc doc-heading">LogData</h2>
            </div>
            <div class="doc doc-object doc-attribute">
              <h2 id="samplepkg.core.RESERVED_ATTRS" class="doc doc-heading">RESERVED_ATTRS</h2>
            </div>
            <div class="doc doc-object doc-class">
              <h2 id="samplepkg.core.BaseClass" class="doc doc-heading">BaseClass</h2>
            </div>
            <div class="doc doc-object doc-function">
              <h2 id="samplepkg.core.helper_func" class="doc doc-heading">helper_func</h2>
            </div>
          </div>
        </div>
      </div>
    </article>
    """
    (site_ref_dir / "index.html").write_text(mock_html, encoding="utf-8")

    mkdocs_yml = (
        "site_name: BlockTest\n"
        "plugins:\n"
        "  - gen-files:\n"
        "      scripts:\n"
        "        - scripts/gen_nav.py\n"
    )
    (tmp_path / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    core_doc = next(d for d in plan.generated_documents if "core.md" in d.target_path)
    content = core_doc.content

    # Block 1 verification
    assert ".. automodule:: samplepkg.core\n   :no-members:" in content

    # Block 2 verification (~ prefix on symbols in autosummary)
    assert (
        ".. rubric:: Classes\n\n.. autosummary::\n   :nosignatures:\n\n   ~BaseClass"
        in content
    )
    assert (
        ".. rubric:: Functions\n\n.. autosummary::\n   :nosignatures:\n\n   ~helper_func"
        in content
    )
    assert (
        ".. rubric:: Attributes\n\n.. autosummary::\n   :nosignatures:\n\n   ~LogData\n   ~RESERVED_ATTRS"
        in content
    )

    # Block 3 verification (exact empirical order: LogData -> RESERVED_ATTRS -> BaseClass -> helper_func)
    pos_data = content.index(".. autodata:: LogData")
    pos_reserved = content.index(".. autodata:: RESERVED_ATTRS")
    pos_class = content.index(".. autoclass:: BaseClass")
    pos_func = content.index(".. autofunction:: helper_func")

    assert pos_data < pos_reserved < pos_class < pos_func


def test_copyright_html_normalization(tmp_path: Path):
    """Verify that raw HTML anchors and entities in copyright are normalized to clean text for Sphinx."""
    mkdocs_yml = (
        "site_name: CopyTest\n"
        "copyright: \"<a href='https://github.com/org/repo'> Copyright &copy; Contributors</a>\"\n"
    )
    (tmp_path / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    assert plan.proposed_sphinx_config is not None
    assert plan.proposed_sphinx_config.custom_options["copyright"] == "Contributors"


def test_inherited_members_config_and_ast_resolution(tmp_path: Path):
    """Verify that MkDocs inherited_members: true generates Sphinx native :inherited-members: stopping at external bases."""
    src_dir = tmp_path / "src" / "pkg"
    src_dir.mkdir(parents=True)
    code = (
        "import logging\n\n"
        "class BaseClass(logging.Formatter):\n"
        "    def base_method(self): pass\n\n"
        "class SubClass(BaseClass):\n"
        "    def sub_method(self): pass\n\n"
        "class CustomError(Exception):\n"
        "    pass\n"
    )
    (src_dir / "mod.py").write_text(code, encoding="utf-8")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    doc_content = "# API\n\n::: pkg.mod.SubClass\n\n::: pkg.mod.CustomError\n"
    (docs_dir / "api.md").write_text(doc_content, encoding="utf-8")

    mkdocs_yml = (
        "site_name: InheritTest\n"
        "plugins:\n"
        "  - mkdocstrings:\n"
        "      handlers:\n"
        "        python:\n"
        "          options:\n"
        "            inherited_members: true\n"
        "            merge_init_into_class: true\n"
    )
    (tmp_path / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    assert plan.proposed_sphinx_config is not None
    assert plan.documentation_plan is not None

    # Verify autoclass_content mapped
    assert plan.proposed_sphinx_config.custom_options.get("autoclass_content") == "both"

    # Verify api_strategies have inherited_members stopping at external bases
    subclass_strat = next(
        s for s in plan.documentation_plan.api_strategies if "SubClass" in s.object_path
    )
    assert subclass_strat.inherited_members == "Formatter"

    error_strat = next(
        s
        for s in plan.documentation_plan.api_strategies
        if "CustomError" in s.object_path
    )
    assert error_strat.inherited_members == "Exception"

    # Verify flow action rendered directive text
    api_page = next(
        p for p in plan.documentation_plan.pages if "api.md" in p.target_path
    )
    rendered_directives = [
        a.target_directive for a in api_page.flow_actions if a.target_directive
    ]
    assert any(":inherited-members: Formatter" in d for d in rendered_directives)
    assert any(":inherited-members: Exception" in d for d in rendered_directives)


def test_inherited_members_override_and_disabled(tmp_path: Path):
    """Verify that inherited_members: false suppresses the property, and directive-level option overrides global."""
    src_dir = tmp_path / "src" / "pkg"
    src_dir.mkdir(parents=True)
    code = "class BaseClass:\n    pass\nclass SubClass(BaseClass):\n    pass\n"
    (src_dir / "mod.py").write_text(code, encoding="utf-8")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    # Explicitly disable in one directive while global is true
    doc_content = (
        "# API\n\n::: pkg.mod.SubClass\n    options:\n      inherited_members: false\n"
    )
    (docs_dir / "api.md").write_text(doc_content, encoding="utf-8")

    mkdocs_yml = (
        "site_name: OverrideTest\n"
        "plugins:\n"
        "  - mkdocstrings:\n"
        "      handlers:\n"
        "        python:\n"
        "          options:\n"
        "            inherited_members: true\n"
    )
    (tmp_path / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")

    planner = MigrationPlanner(tmp_path)
    plan = planner.create_plan()

    assert plan.documentation_plan is not None
    subclass_strat = next(
        s for s in plan.documentation_plan.api_strategies if "SubClass" in s.object_path
    )
    assert subclass_strat.inherited_members is None

    api_page = next(
        p for p in plan.documentation_plan.pages if "api.md" in p.target_path
    )
    rendered_directives = [
        a.target_directive for a in api_page.flow_actions if a.target_directive
    ]
    assert not any(":inherited-members:" in d for d in rendered_directives)
