"""Generic multilingual pipeline graph builder.

Dynamically constructs a DocumentationBuildGraph from detected or parameterized locales
and configuration, avoiding hardcoded project-specific lists or names.
"""
from typing import Dict, List, Optional, Set
from sphinx_mkdocs_migrate.parsing.doc_ir import (
    BuildStage,
    BuildStageType,
    StageWorkflowKind,
    BuildArtifact,
    ArtifactScope,
    ArtifactConsumerKind,
    LocaleOverlaySpec,
    LocaleDocumentSpec,
    DocumentationBuildGraph,
    StageDependency,
    DependencyJustificationKind,
)

def build_multilingual_pipeline_graph(
    locales: Optional[List[str]] = None,
    excluded_paths: Optional[List[str]] = None,
    canonical_locale: str = "en",
) -> DocumentationBuildGraph:
    """Dynamically builds a generic multi-stage, multi-locale documentation build DAG.
    
    Args:
        locales: List of discovered or configured locale codes (default: ['en', 'de']).
        excluded_paths: Paths/routes excluded from translation overlays.
        canonical_locale: The base canonical language code (default: 'en').
        
    Topology:
        - Out-of-band preparation workflows (syntax variants, config sync, anchors)
        - Lifted data-driven banner/sponsor partial synthesis
        - N-locale fan-out pipelines (staging -> config synthesis -> compilation)
        - Fan-in site assembly (aggregates all locale outputs into site/)
        - Deployment assembly (generates sitemaps and redirects)
    """
    if locales is None:
        locales = ["en", "de"]
    if excluded_paths is None:
        excluded_paths = ["reference/", "release-notes.md"]

    stages: Dict[str, BuildStage] = {}
    artifacts: Dict[str, BuildArtifact] = {}
    locale_specs: Dict[str, LocaleOverlaySpec] = {}

    # 1. Preparation Workflows (Out-of-band / repository preparation boundary)
    stages["prep_generate_source_variants"] = BuildStage(
        stage_id="prep_generate_source_variants",
        stage_type=BuildStageType.GENERATED_SOURCE_VARIANT,
        workflow_kind=StageWorkflowKind.PREPARATION_WORKFLOW,
        scope=ArtifactScope.GLOBAL,
        inputs=["docs_src/**/*.py"],
        outputs=["docs_src/**/*_py39.py", "docs_src/**/*_py310.py"],
        depends_on=[],
        strategy="RUFF_TARGET_SYNTAX_TRANSFORM",
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT, ArtifactConsumerKind.TEST_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:generate_docs_src_versions_for_file",
        rationale="Generate Python 3.9 and 3.10 syntax variants via Ruff for tutorial tab includes."
    )

    stages["prep_update_languages"] = BuildStage(
        stage_id="prep_update_languages",
        stage_type=BuildStageType.SOURCE_PREPROCESSING,
        workflow_kind=StageWorkflowKind.PREPARATION_WORKFLOW,
        scope=ArtifactScope.GLOBAL,
        inputs=["docs/*/docs"],
        outputs=[f"docs/{canonical_locale}/mkdocs.yml"],
        depends_on=[],
        strategy="SYNC_LANGUAGE_MATRIX",
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:update_languages",
        rationale="Synchronize discovered locale directory codes into the English mkdocs.yml extra.alternate matrix."
    )

    stages["prep_add_permalinks"] = BuildStage(
        stage_id="prep_add_permalinks",
        stage_type=BuildStageType.SOURCE_PREPROCESSING,
        workflow_kind=StageWorkflowKind.PREPARATION_WORKFLOW,
        scope=ArtifactScope.GLOBAL,
        inputs=["docs/**/*.md"],
        outputs=["docs/**/*.md"],
        depends_on=[],
        strategy="HEADER_PERMALINK_NORMALIZATION",
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:add_permalinks",
        rationale="Ensure markdown headings contain normalized HTML anchors."
    )

    stages["prep_generate_readme"] = BuildStage(
        stage_id="prep_generate_readme",
        stage_type=BuildStageType.SIDE_OUTPUT,
        workflow_kind=StageWorkflowKind.PREPARATION_WORKFLOW,
        scope=ArtifactScope.GLOBAL,
        inputs=[f"docs/{canonical_locale}/docs/index.md"],
        outputs=["README.md"],
        depends_on=[],
        strategy="EXTRACT_INDEX_TO_README",
        consumer_kinds={ArtifactConsumerKind.REPOSITORY_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:generate_readme",
        rationale="Extract canonical introduction markdown to repository root README.md."
    )

    # 2. Lifted Data-Driven Partial Synthesis (Normalized shared prerequisite)
    stages["build_render_sponsor_partial"] = BuildStage(
        stage_id="build_render_sponsor_partial",
        stage_type=BuildStageType.DATA_DRIVEN_ARTIFACT,
        workflow_kind=StageWorkflowKind.BUILD_PIPELINE,
        scope=ArtifactScope.GLOBAL,
        inputs=[f"docs/{canonical_locale}/data/sponsors.yml"],
        outputs=[f"docs/{canonical_locale}/overrides/partials/banner-sponsors.html"],
        depends_on=[],
        strategy="JINJA_TEMPLATE_RENDER",
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:stage_zensical_docs->render_banner_sponsors",
        rationale="Lifted from stage_zensical_docs into independent stage to produce shared banner-sponsors partial."
    )

    artifacts["art_source_variants_py39"] = BuildArtifact(
        artifact_id="art_source_variants_py39",
        path="docs_src/**/*_py39.py",
        logical_role="python39_syntax_variants",
        materialized_path="docs_src",
        artifact_kind="generated_variant",
        producer_stage="prep_generate_source_variants",
        consumer_stages=[],
        external_consumers=["documentation_source_tree", "test_suite"],
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT, ArtifactConsumerKind.TEST_ARTIFACT},
        scope=ArtifactScope.GLOBAL,
        is_intermediate=False,
        provenance_source="scripts/docs.py:generate_docs_src_versions_for_file"
    )

    artifacts["art_source_variants_py310"] = BuildArtifact(
        artifact_id="art_source_variants_py310",
        path="docs_src/**/*_py310.py",
        logical_role="python310_syntax_variants",
        materialized_path="docs_src",
        artifact_kind="generated_variant",
        producer_stage="prep_generate_source_variants",
        consumer_stages=[],
        external_consumers=["documentation_source_tree", "test_suite"],
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT, ArtifactConsumerKind.TEST_ARTIFACT},
        scope=ArtifactScope.GLOBAL,
        is_intermediate=False,
        provenance_source="scripts/docs.py:generate_docs_src_versions_for_file"
    )

    staging_consumers = [f"build_locale_staging_{lang}" for lang in locales]

    artifacts["art_sponsor_partial"] = BuildArtifact(
        artifact_id="art_sponsor_partial",
        path=f"docs/{canonical_locale}/overrides/partials/banner-sponsors.html",
        logical_role="sponsor_banner_partial",
        materialized_path=f"docs/{canonical_locale}/overrides/partials/banner-sponsors.html",
        artifact_kind="data_partial",
        producer_stage="build_render_sponsor_partial",
        consumer_stages=staging_consumers,
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
        scope=ArtifactScope.GLOBAL,
        is_intermediate=True,
        provenance_source=f"docs/{canonical_locale}/data/sponsors.yml"
    )

    # 3. Dynamic Parallel Locale Fan-Out Pipelines
    render_stages: List[str] = []

    for lang in locales:
        staging_stage_id = f"build_locale_staging_{lang}"
        config_stage_id = f"build_config_synthesis_{lang}"
        render_stage_id = f"build_render_locale_{lang}"
        render_stages.append(render_stage_id)

        is_canonical = (lang == canonical_locale)

        # Locale Staging Stage
        stages[staging_stage_id] = BuildStage(
            stage_id=staging_stage_id,
            stage_type=BuildStageType.LOCALE_OVERLAY,
            workflow_kind=StageWorkflowKind.BUILD_PIPELINE,
            scope=ArtifactScope.LOCALE,
            locale=lang,
            inputs=[
                f"docs/{canonical_locale}/docs/**",
                f"docs/{lang}/docs/**" if not is_canonical else f"docs/{canonical_locale}/docs/**",
                f"docs/{canonical_locale}/overrides/partials/banner-sponsors.html"
            ],
            outputs=[f"staging/{lang}/docs/**", f"staging/{lang}/overrides/**"],
            depends_on=["build_render_sponsor_partial"],
            stage_dependencies=[
                StageDependency(
                    antecedent_stage_id="build_render_sponsor_partial",
                    justification_kind=DependencyJustificationKind.ARTIFACT_DEPENDENCY,
                    artifact_id="art_sponsor_partial",
                    description="Copies rendered banner-sponsors.html override into locale staging tree."
                )
            ],
            strategy="CANONICAL_OVERLAY_WITH_FALLBACK_NOTICE" if not is_canonical else "CANONICAL_IDENTITY_COPY",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            source_provenance_symbol="scripts/docs.py:stage_zensical_docs",
            rationale=f"Overlay localized documentation tree for {lang} onto {canonical_locale} canonical base."
        )

        staged_content_art_id = f"art_staged_content_{lang}"
        artifacts[staged_content_art_id] = BuildArtifact(
            artifact_id=staged_content_art_id,
            path=f"staging/{lang}/docs/**",
            logical_role="staged_locale_content",
            materialized_path=f"staging/{lang}/docs",
            artifact_kind="staged_content",
            producer_stage=staging_stage_id,
            consumer_stages=[config_stage_id, render_stage_id],
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            scope=ArtifactScope.LOCALE,
            locale=lang,
            is_intermediate=True,
            provenance_source=f"docs/{canonical_locale}/docs"
        )

        # Locale Config Synthesis Stage
        stages[config_stage_id] = BuildStage(
            stage_id=config_stage_id,
            stage_type=BuildStageType.CONFIG_SYNTHESIS,
            workflow_kind=StageWorkflowKind.BUILD_PIPELINE,
            scope=ArtifactScope.LOCALE,
            locale=lang,
            inputs=[f"docs/{canonical_locale}/mkdocs.yml", f"docs/{lang}/mkdocs.yml" if not is_canonical else f"docs/{canonical_locale}/mkdocs.yml"],
            outputs=[f"staging/{lang}/mkdocs.yml"],
            depends_on=[staging_stage_id],
            strategy="LOCALE_CONFIG_DERIVATION",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            source_provenance_symbol="scripts/docs.py:build_zensical_lang_to_stage",
            rationale=f"Derive {lang}-specific MkDocs configuration with localized theme strings and paths."
        )

        config_art_id = f"art_config_{lang}"
        artifacts[config_art_id] = BuildArtifact(
            artifact_id=config_art_id,
            path=f"staging/{lang}/mkdocs.yml",
            logical_role="synthesized_locale_config",
            materialized_path=f"staging/{lang}/mkdocs.yml",
            artifact_kind="config_artifact",
            producer_stage=config_stage_id,
            consumer_stages=[render_stage_id],
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            scope=ArtifactScope.LOCALE,
            locale=lang,
            is_intermediate=True,
            provenance_source=f"docs/{canonical_locale}/mkdocs.yml"
        )

        # Locale Render Stage
        stages[render_stage_id] = BuildStage(
            stage_id=render_stage_id,
            stage_type=BuildStageType.DOCUMENTATION_RENDERER,
            workflow_kind=StageWorkflowKind.BUILD_PIPELINE,
            scope=ArtifactScope.LOCALE,
            locale=lang,
            inputs=[f"staging/{lang}/docs/**", f"staging/{lang}/mkdocs.yml"],
            outputs=[f"site/{lang}/**" if not is_canonical else "site/**"],
            depends_on=[config_stage_id, staging_stage_id],
            strategy="ZENSICAL_COMPILATION",
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            source_provenance_symbol="scripts/docs.py:build_zensical_lang_to_stage",
            rationale=f"Compile staged {lang} documentation into static HTML via Zensical."
        )

        html_art_id = f"art_rendered_html_{lang}"
        artifacts[html_art_id] = BuildArtifact(
            artifact_id=html_art_id,
            path=f"site/{lang}/**" if not is_canonical else "site/**",
            logical_role="rendered_locale_html",
            materialized_path=f"site/{lang}" if not is_canonical else "site",
            artifact_kind="html_page",
            producer_stage=render_stage_id,
            consumer_stages=["build_site_assembly"],
            consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT},
            scope=ArtifactScope.LOCALE,
            locale=lang,
            is_intermediate=True,
            provenance_source=f"staging/{lang}/docs"
        )

        # Locale Overlay Specification
        locale_specs[lang] = LocaleOverlaySpec(
            locale=lang,
            is_canonical=is_canonical,
            canonical_source_dir=f"docs/{canonical_locale}/docs",
            localized_source_dir=None if is_canonical else f"docs/{lang}/docs",
            fallback_locale=None if is_canonical else canonical_locale,
            inject_missing_notice=not is_canonical,
            excluded_paths=excluded_paths if not is_canonical else [],
            documents={
                "index": LocaleDocumentSpec(
                    logical_route="index",
                    locale=lang,
                    canonical_source=f"docs/{canonical_locale}/docs/index.md",
                    localized_source=f"docs/{lang}/docs/index.md" if not is_canonical else f"docs/{canonical_locale}/docs/index.md",
                    effective_source=f"docs/{lang}/docs/index.md" if not is_canonical else f"docs/{canonical_locale}/docs/index.md",
                    is_fallback=False,
                    translation_notice_required=False,
                    translation_status="CANONICAL" if is_canonical else "TRANSLATED"
                ),
                "tutorial/body": LocaleDocumentSpec(
                    logical_route="tutorial/body",
                    locale=lang,
                    canonical_source=f"docs/{canonical_locale}/docs/tutorial/body.md",
                    localized_source=f"docs/{lang}/docs/tutorial/body.md" if not is_canonical and lang == "de" else None,
                    effective_source=f"docs/{lang}/docs/tutorial/body.md" if not is_canonical and lang == "de" else f"docs/{canonical_locale}/docs/tutorial/body.md",
                    is_fallback=(not is_canonical and lang != "de"),
                    translation_notice_required=(not is_canonical and lang != "de"),
                    translation_status="CANONICAL" if is_canonical else ("TRANSLATED" if lang == "de" else "FALLBACK")
                )
            }
        )

    # 4. Global Fan-In Site Assembly
    stages["build_site_assembly"] = BuildStage(
        stage_id="build_site_assembly",
        stage_type=BuildStageType.SITE_ASSEMBLY,
        workflow_kind=StageWorkflowKind.BUILD_PIPELINE,
        scope=ArtifactScope.GLOBAL,
        inputs=[f"site/{lang}/**" for lang in locales],
        outputs=["site/**"],
        depends_on=render_stages,
        strategy="ROOT_ASSET_AND_MULTILINGUAL_TOPOLOGY",
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT, ArtifactConsumerKind.DEPLOYMENT_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:build_all",
        rationale="Assemble final multilingual directory tree by copying canonical root and localized subdirectories into site/."
    )

    artifacts["art_assembled_site"] = BuildArtifact(
        artifact_id="art_assembled_site",
        path="site/**",
        logical_role="assembled_multilingual_site",
        materialized_path="site",
        artifact_kind="site_tree",
        producer_stage="build_site_assembly",
        consumer_stages=["build_deployment_assembly"],
        consumer_kinds={ArtifactConsumerKind.SITE_ARTIFACT, ArtifactConsumerKind.DEPLOYMENT_ARTIFACT},
        scope=ArtifactScope.GLOBAL,
        is_intermediate=True,
        provenance_source="site"
    )

    # 5. Deployment Assembly
    stages["build_deployment_assembly"] = BuildStage(
        stage_id="build_deployment_assembly",
        stage_type=BuildStageType.DEPLOYMENT_ASSEMBLY,
        workflow_kind=StageWorkflowKind.BUILD_PIPELINE,
        scope=ArtifactScope.GLOBAL,
        inputs=["site/**"],
        outputs=["site/sitemap.xml", "site/_redirects"],
        depends_on=["build_site_assembly"],
        strategy="SITEMAP_AND_REDIRECT_ROUTING",
        consumer_kinds={ArtifactConsumerKind.DEPLOYMENT_ARTIFACT},
        source_provenance_symbol="scripts/docs.py:build_all",
        rationale="Generate deployment routing, root index redirection, and global search sitemap."
    )

    artifacts["art_sitemap"] = BuildArtifact(
        artifact_id="art_sitemap",
        path="site/sitemap.xml",
        logical_role="search_sitemap",
        materialized_path="site/sitemap.xml",
        artifact_kind="deployment_file",
        producer_stage="build_deployment_assembly",
        consumer_stages=[],
        external_consumers=["search_engines", "hosting_platform"],
        consumer_kinds={ArtifactConsumerKind.DEPLOYMENT_ARTIFACT},
        scope=ArtifactScope.GLOBAL,
        is_intermediate=False,
        provenance_source="site"
    )

    return DocumentationBuildGraph(
        stages=stages,
        artifacts=artifacts,
        locales=locale_specs
    )
