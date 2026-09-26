"""Unit and integration tests for Milestone 3.3 & 3.3a: Deterministic MigrationPlan, Provenance, and Traceability."""
import time
import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.planner.models import RequirementProvenance
from sphinx_mkdocs_migrate.analyzer.models import Classification
from sphinx_mkdocs_migrate.parsing.markdown_ir import NodeKind

@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures" / "sample_mkdocs"

def test_migration_planner_aggregation_and_deduplication(fixture_dir):
    """Test full repository inventory aggregation into a deterministic MigrationPlan with provenance."""
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()

    assert plan.project_root == str(fixture_dir)
    assert plan.source_mkdocs_config is not None
    assert plan.source_mkdocs_config.site_name == "Sample Project Docs"

    # 1. Summary validation (Counts without percentages)
    assert plan.summary.total_actions > 0
    assert plan.summary.transform_count >= 1
    assert plan.summary.manual_count >= 1

    # 2. Traceability: Document actions reflect source locations
    assert len(plan.document_actions) > 0
    first_action = plan.document_actions[0]
    assert first_action.start_line >= 1
    assert first_action.source_file.endswith(".md")
    assert first_action.rule_id.startswith("rule.")

    # 3. Requirement Items with Provenance
    req_names = {r.name for r in plan.requirements}
    assert "myst_parser" in req_names
    assert "sphinx_design" in req_names
    assert "myst-parser>=2.0.0" in req_names
    assert "sphinx-design>=0.5.0" in req_names
    assert "Sphinx>=7.0.0" in req_names

    # Check provenance
    sphinx_req = next(r for r in plan.requirements if r.name == "Sphinx>=7.0.0")
    assert sphinx_req.provenance == RequirementProvenance.TARGET_BASELINE
    assert "target_baseline" in sphinx_req.sources

    design_req = next(r for r in plan.requirements if r.name == "sphinx_design")
    assert design_req.provenance == RequirementProvenance.DOCUMENT_CONSTRUCT
    assert any("tabs.md" in src or "index.md" in src for src in design_req.sources)

    # 4. Explicit Theme Migration Proposal (Material -> Furo for modern Sphinx)
    assert plan.proposed_sphinx_config is not None
    assert plan.proposed_sphinx_config.theme.source_theme == "material"
    assert plan.proposed_sphinx_config.theme.target_theme == "furo"
    assert "furo" in plan.proposed_sphinx_config.theme.target_package

    # 5. Evidence-based MyST Syntax Extensions (Only colon_fence and detected extensions, not random defaults)
    assert "colon_fence" in plan.proposed_sphinx_config.myst_enable_extensions
    assert "dollarmath" not in plan.proposed_sphinx_config.myst_enable_extensions

    # 6. Manual review items traceable to files
    assert len(plan.manual_action_items) >= 1
    manual_api = next(item for item in plan.manual_action_items if item.construct_type == "API_DIRECTIVE")
    assert manual_api.source_file.endswith("api.md")
    assert "sample.client.Client" in manual_api.instruction

def test_planner_default_canonical_hash_determinism(fixture_dir):
    """Ensure two default plan runs at different timestamps produce IDENTICAL canonical hashes and content."""
    planner = MigrationPlanner(fixture_dir)
    
    plan_a = planner.create_plan()
    time.sleep(0.01)
    plan_b = planner.create_plan()

    # The generated_at timestamps naturally differ
    assert plan_a.metadata.generated_at != plan_b.metadata.generated_at
    # But the canonical identity and hashes are strictly identical!
    assert plan_a.canonical_hash() == plan_b.canonical_hash()
    assert plan_a.canonical_dict() == plan_b.canonical_dict()

def test_planner_read_only_invariant(fixture_dir):
    """Ensure that calling MigrationPlanner does not create or modify any files on disk."""
    docs_before = set(fixture_dir.rglob("*"))
    
    planner = MigrationPlanner(fixture_dir)
    plan = planner.create_plan()

    docs_after = set(fixture_dir.rglob("*"))
    assert docs_before == docs_after
