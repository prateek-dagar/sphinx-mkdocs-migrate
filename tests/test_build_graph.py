"""Tests for Generic DocumentationBuildGraph, Stage Topology, and Locale Overlay Models."""

from sphinx_mkdocs_migrate.parsing.doc_ir import (
    BuildStage,
    BuildStageType,
    BuildArtifact,
    ArtifactScope,
    ArtifactConsumerKind,
    LocaleOverlaySpec,
    LocaleDocumentSpec,
    DocumentationBuildGraph,
    DocumentationSiteGraph,
)


def test_build_graph_topological_execution_order_and_artifacts():
    """Verify build stages execute in strict topological dependency order with explicit BuildArtifacts."""
    stages = {
        "stage_source_variants": BuildStage(
            stage_id="stage_source_variants",
            stage_type=BuildStageType.GENERATED_SOURCE_VARIANT,
            scope=ArtifactScope.GLOBAL,
            inputs=["docs_src/**/*.py"],
            outputs=["docs_src/**/*_py39.py", "docs_src/**/*_py310.py"],
            depends_on=[],
            strategy="RUFF_TARGET_SYNTAX_TRANSFORM",
            consumer_kinds={
                ArtifactConsumerKind.SITE_ARTIFACT,
                ArtifactConsumerKind.TEST_ARTIFACT,
            },
            rationale="Generate backwards-compatible Python syntax variants for tutorial tabs.",
        ),
        "stage_data_sponsors": BuildStage(
            stage_id="stage_data_sponsors",
            stage_type=BuildStageType.DATA_DRIVEN_ARTIFACT,
            scope=ArtifactScope.GLOBAL,
            inputs=["docs/en/data/sponsors.yml"],
            outputs=["overrides/partials/sponsor.html"],
            depends_on=[],
            strategy="JINJA_TEMPLATE_RENDER",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            rationale="Synthesize banner sponsor partial from structured YAML data.",
        ),
        "stage_locale_overlay_de": BuildStage(
            stage_id="stage_locale_overlay_de",
            stage_type=BuildStageType.LOCALE_OVERLAY,
            scope=ArtifactScope.LOCALE,
            locale="de",
            inputs=["docs/en/docs/**", "docs/de/docs/**"],
            outputs=["staging/de/docs/**"],
            depends_on=["stage_source_variants", "stage_data_sponsors"],
            strategy="CANONICAL_OVERLAY_WITH_FALLBACK_NOTICE",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            rationale="Overlay German translations over English canonical tree with fallback notices.",
        ),
        "stage_config_synthesis_de": BuildStage(
            stage_id="stage_config_synthesis_de",
            stage_type=BuildStageType.CONFIG_SYNTHESIS,
            scope=ArtifactScope.LOCALE,
            locale="de",
            inputs=["docs/en/mkdocs.yml"],
            outputs=["staging/de/mkdocs.yml"],
            depends_on=["stage_locale_overlay_de"],
            strategy="LOCALE_CONFIG_DERIVATION",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            rationale="Synthesize German-specific configuration with locale URLs and language strings.",
        ),
        "stage_render_de": BuildStage(
            stage_id="stage_render_de",
            stage_type=BuildStageType.DOCUMENTATION_RENDERER,
            scope=ArtifactScope.LOCALE,
            locale="de",
            inputs=["staging/de/docs/**", "staging/de/mkdocs.yml"],
            outputs=["site/de/**"],
            depends_on=["stage_config_synthesis_de"],
            strategy="SPHINX_HTML_BUILD",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            rationale="Compile staged German documentation tree into HTML output.",
        ),
        "stage_site_assembly": BuildStage(
            stage_id="stage_site_assembly",
            stage_type=BuildStageType.SITE_ASSEMBLY,
            scope=ArtifactScope.GLOBAL,
            inputs=["site/en/**", "site/de/**"],
            outputs=["site/**"],
            depends_on=["stage_render_de"],
            strategy="ROOT_ASSET_AND_MULTILINGUAL_TOPOLOGY",
            consumer_kinds={
                ArtifactConsumerKind.SITE_ARTIFACT,
                ArtifactConsumerKind.DEPLOYMENT_ARTIFACT,
            },
            rationale="Assemble final root site tree with shared assets and locale directories.",
        ),
        "stage_deployment_assembly": BuildStage(
            stage_id="stage_deployment_assembly",
            stage_type=BuildStageType.DEPLOYMENT_ASSEMBLY,
            scope=ArtifactScope.GLOBAL,
            inputs=["site/**"],
            outputs=["site/sitemap.xml", "site/_redirects"],
            depends_on=["stage_site_assembly"],
            strategy="SITEMAP_AND_REDIRECT_ROUTING",
            consumer_kinds={ArtifactConsumerKind.DEPLOYMENT_ARTIFACT},
            rationale="Generate deployment routing, root index redirection, and search sitemaps.",
        ),
        "stage_readme_side_output": BuildStage(
            stage_id="stage_readme_side_output",
            stage_type=BuildStageType.SIDE_OUTPUT,
            scope=ArtifactScope.GLOBAL,
            inputs=["docs/en/docs/index.md"],
            outputs=["README.md"],
            depends_on=[],
            strategy="EXTRACT_INDEX_TO_README",
            consumer_kinds={ArtifactConsumerKind.REPOSITORY_ARTIFACT},
            rationale="Extract canonical introduction markdown to repository README.md.",
        ),
    }

    artifacts = {
        "art_variant_py39": BuildArtifact(
            artifact_id="art_variant_py39",
            path="docs_src/tutorial001_py39.py",
            artifact_kind="generated_variant",
            producer_stage="stage_source_variants",
            consumer_stages=["stage_locale_overlay_de"],
            consumer_kinds={
                ArtifactConsumerKind.SITE_ARTIFACT,
                ArtifactConsumerKind.TEST_ARTIFACT,
            },
            is_intermediate=True,
            provenance_source="docs_src/tutorial001.py",
        )
    }

    de_docs = {
        "index": LocaleDocumentSpec(
            logical_route="index",
            locale="de",
            canonical_source="docs/en/docs/index.md",
            localized_source="docs/de/docs/index.md",
            effective_source="docs/de/docs/index.md",
            is_fallback=False,
            translation_notice_required=False,
            translation_status="TRANSLATED",
        ),
        "tutorial/body": LocaleDocumentSpec(
            logical_route="tutorial/body",
            locale="de",
            canonical_source="docs/en/docs/tutorial/body.md",
            localized_source=None,
            effective_source="docs/en/docs/tutorial/body.md",
            is_fallback=True,
            translation_notice_required=True,
            translation_status="FALLBACK",
        ),
    }

    locales = {
        "en": LocaleOverlaySpec(
            locale="en",
            is_canonical=True,
            canonical_source_dir="docs/en/docs",
            fallback_locale=None,
            inject_missing_notice=False,
        ),
        "de": LocaleOverlaySpec(
            locale="de",
            is_canonical=False,
            canonical_source_dir="docs/en/docs",
            localized_source_dir="docs/de/docs",
            fallback_locale="en",
            inject_missing_notice=True,
            excluded_paths=["reference/", "release-notes.md"],
            documents=de_docs,
        ),
    }

    build_graph = DocumentationBuildGraph(
        stages=stages, artifacts=artifacts, locales=locales
    )
    site_graph = DocumentationSiteGraph(build_graph=build_graph)

    # Invariant 1: Topologically sorted execution order
    order = build_graph.execution_order()
    assert order.index("stage_source_variants") < order.index("stage_locale_overlay_de")
    assert order.index("stage_data_sponsors") < order.index("stage_locale_overlay_de")
    assert order.index("stage_locale_overlay_de") < order.index(
        "stage_config_synthesis_de"
    )
    assert order.index("stage_config_synthesis_de") < order.index("stage_render_de")
    assert order.index("stage_render_de") < order.index("stage_site_assembly")
    assert order.index("stage_site_assembly") < order.index("stage_deployment_assembly")

    # Invariant 2: Multi-consumer support
    assert (
        ArtifactConsumerKind.TEST_ARTIFACT
        in stages["stage_source_variants"].consumer_kinds
    )
    assert (
        ArtifactConsumerKind.REPOSITORY_ARTIFACT
        in stages["stage_readme_side_output"].consumer_kinds
    )
    assert (
        ArtifactConsumerKind.DEPLOYMENT_ARTIFACT
        in stages["stage_deployment_assembly"].consumer_kinds
    )

    # Invariant 3: Explicit Lineage and Fallback Tracking
    assert build_graph.locales["de"].documents["tutorial/body"].is_fallback is True
    assert (
        build_graph.locales["de"].documents["tutorial/body"].translation_status
        == "FALLBACK"
    )
    assert build_graph.locales["de"].documents["index"].is_fallback is False

    # Invariant 4: Graph Integrity & Locale Validation checks
    graph_errors = build_graph.validate_graph_invariants()
    assert graph_errors == [], f"Graph errors found: {graph_errors}"

    locale_errors = build_graph.validate_locale_invariants()
    assert locale_errors == [], f"Locale errors found: {locale_errors}"

    # Invariant 5: Canonical hashing covers the build graph and artifacts
    c_hash = site_graph.canonical_hash()
    assert len(c_hash) == 64


def test_multilingual_13_locale_pipeline_fidelity_and_invariants():
    """Verify the extracted multilingual BuildGraph meets all structural and lineage invariants dynamically."""
    from tests.fixtures.multilingual_pipeline_graph import (
        build_multilingual_pipeline_graph,
    )

    test_locales = [
        "en",
        "de",
        "es",
        "fa",
        "fr",
        "ja",
        "ko",
        "pt",
        "ru",
        "tr",
        "uk",
        "zh",
        "zh-hant",
    ]
    test_excluded = ["reference/", "release-notes.md"]

    graph = build_multilingual_pipeline_graph(
        locales=test_locales,
        excluded_paths=test_excluded,
        canonical_locale="en",
    )

    # 1. Exact Stage and Tracked Artifact Counts
    # 46 stages = 4 prep + 1 sponsor + 39 locale (13*3) + 1 site + 1 deployment
    # 44 artifacts = 2 variants (py39, py310) + 1 sponsor + 13 staged content + 13 configs + 13 rendered HTML + 1 site + 1 sitemap
    assert len(graph.stages) == 46
    assert len(graph.locales) == 13
    assert len(graph.artifacts) == 44

    # 2. Dynamic Parallel Locale Fan-Out & Fan-In
    render_stages = [f"build_render_locale_{lang}" for lang in test_locales]
    site_assembly = graph.stages["build_site_assembly"]
    assert set(site_assembly.depends_on) == set(render_stages)

    # 3. Sponsor Partial Lifted Provenance & Materialized Path
    sponsor_art = graph.artifacts["art_sponsor_partial"]
    assert sponsor_art.logical_role == "sponsor_banner_partial"
    assert (
        sponsor_art.materialized_path
        == "docs/en/overrides/partials/banner-sponsors.html"
    )
    assert len(sponsor_art.consumer_stages) == 13
    for lang in test_locales:
        assert f"build_locale_staging_{lang}" in sponsor_art.consumer_stages
        assert (
            "build_render_sponsor_partial"
            in graph.stages[f"build_locale_staging_{lang}"].depends_on
        )

    # 4. Source Variants: Explicit py39 and py310 Artifact Nodes & External Consumers
    var_stage = graph.stages["prep_generate_source_variants"]
    assert var_stage.workflow_kind.value == "PREPARATION_WORKFLOW"
    assert "docs_src/**/*_py39.py" in var_stage.outputs
    assert "docs_src/**/*_py310.py" in var_stage.outputs

    art_py39 = graph.artifacts["art_source_variants_py39"]
    assert art_py39.logical_role == "python39_syntax_variants"
    assert art_py39.consumer_stages == []
    assert "documentation_source_tree" in art_py39.external_consumers

    art_py310 = graph.artifacts["art_source_variants_py310"]
    assert art_py310.logical_role == "python310_syntax_variants"
    assert art_py310.consumer_stages == []
    assert "documentation_source_tree" in art_py310.external_consumers

    # 5. Pre-build Repository Synchronization
    update_lang_stage = graph.stages["prep_update_languages"]
    assert update_lang_stage.strategy == "SYNC_LANGUAGE_MATRIX"
    assert (
        update_lang_stage.source_provenance_symbol == "scripts/docs.py:update_languages"
    )

    # 6. Source Renderer Strategy (Pure ZENSICAL, not target Sphinx)
    for lang in test_locales:
        render_stage = graph.stages[f"build_render_locale_{lang}"]
        assert render_stage.strategy == "ZENSICAL_COMPILATION"
        assert f"build_locale_staging_{lang}" in render_stage.depends_on
        assert f"build_config_synthesis_{lang}" in render_stage.depends_on

    # 7. Assembled Site and Deployment Artifacts
    assembled_art = graph.artifacts["art_assembled_site"]
    assert assembled_art.producer_stage == "build_site_assembly"
    assert assembled_art.consumer_stages == ["build_deployment_assembly"]

    sitemap_art = graph.artifacts["art_sitemap"]
    assert sitemap_art.producer_stage == "build_deployment_assembly"
    assert "search_engines" in sitemap_art.external_consumers

    # 8. Structural Invariant Validation (Zero DAG errors, zero cycle errors, 100% bi-directional artifact consistency)
    graph_errors = graph.validate_graph_invariants()
    assert graph_errors == [], f"Graph errors found: {graph_errors}"

    locale_errors = graph.validate_locale_invariants()
    assert locale_errors == [], f"Locale errors found: {locale_errors}"

    # 9. Topological Execution Order Verification
    exec_order = graph.execution_order()
    assert len(exec_order) == 46
    assert exec_order.index("build_render_sponsor_partial") < exec_order.index(
        "build_locale_staging_en"
    )
    for lang in test_locales:
        assert exec_order.index(f"build_locale_staging_{lang}") < exec_order.index(
            f"build_config_synthesis_{lang}"
        )
        assert exec_order.index(f"build_config_synthesis_{lang}") < exec_order.index(
            f"build_render_locale_{lang}"
        )
        assert exec_order.index(f"build_render_locale_{lang}") < exec_order.index(
            "build_site_assembly"
        )
    assert exec_order.index("build_site_assembly") < exec_order.index(
        "build_deployment_assembly"
    )
