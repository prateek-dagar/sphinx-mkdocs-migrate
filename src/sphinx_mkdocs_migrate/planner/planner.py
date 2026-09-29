"""Migration Planner synthesizing findings, declarative rules, policy engine, and provenance into a deterministic MigrationPlan."""

import ast
import datetime
import html
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from ..analyzer.models import Classification
from .models import (
    MigrationPlan,
    MigrationPlanMetadata,
    PlanActionSummary,
    RequirementProvenance,
    RequirementItem,
    ThemeMigrationProposal,
    ConfigMigrationProposal,
    ManualReviewItem,
    GeneratedDocumentProposal,
    DocumentationPlan,
    DocumentationArtifact,
    DocumentFlowAction,
    ArtifactProvenance,
    ApiGenerationStrategy,
    ApiDirectiveKind,
    NavigationPlan,
    GeneratedPipelinePlan,
    CrossReferenceAction,
    AssetAction,
    ExternalInventoryConfig,
    VersioningDeploymentPlan,
    SystemCapabilityAccountability,
    CapabilityDisposition,
    ImplementationStrategy,
    VerificationStatus,
)
from .conf_builder import build_conf_py
from .toctree import resolve_navigation_docnames
from .ci import plan_ci_workflow
from .policy import PolicyEngine
from ..analyzer.mkdocs import detect_obsolete_generator_scripts
from ..analyzer.project import ProjectAnalyzer
from ..rules.engine import MigrationRuleEngine
from ..rules.models import MigrationAction
from ..parsing.markdown import MarkdownParser
from ..parsing.flow_extractor import DocumentFlowExtractor
from ..parsing.html_flow_parser import HtmlFlowParser, HtmlFlowRole
from ..parsing.doc_ir import (
    DocumentElementType,
    HeadingElement,
    ParagraphElement,
    ListElement,
    CodeBlockElement,
    AdmonitionElement,
    SnippetElement,
    ApiDocumentationRequest,
    DocumentationPage,
)


class MigrationPlanner:
    """Orchestrates deterministic planning from ProjectAnalysisReport, FeaturePolicyCatalog, and MigrationRuleEngine."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.analyzer = ProjectAnalyzer(project_root)
        self.parser = MarkdownParser()
        self.rule_engine = MigrationRuleEngine()
        self.policy_engine = PolicyEngine()
        self.flow_extractor = DocumentFlowExtractor()

    def create_plan(
        self, deterministic_timestamp: Optional[str] = None
    ) -> MigrationPlan:
        """Generates a canonical, read-only MigrationPlan without mutating repository files."""
        # 1. Analyze repository subsystems
        report = self.analyzer.analyze()

        # Pass MkDocs config to flow extractor if available
        mkdocs_dict = {}
        if report.mkdocs_config:
            mkdocs_dict["markdown_extensions"] = [
                ext if isinstance(ext, str) else getattr(ext, "name", str(ext))
                for ext in (report.mkdocs_config.markdown_extensions or [])
            ]
        self.flow_extractor.mkdocs_config = mkdocs_dict

        # 2. Extract DocumentIRs, DocumentationPages, and evaluate declarative rules per file
        all_actions: List[MigrationAction] = []
        action_counter = 1

        # Track detected extensions from markdown inspection
        detected_markdown_extensions: Set[str] = set()
        for c in report.construct_findings:
            if c.construct_type == "tab_group":
                detected_markdown_extensions.add("pymdownx.tabbed")
            elif c.construct_type == "admonition":
                detected_markdown_extensions.add("admonition")
            elif c.construct_type == "details":
                detected_markdown_extensions.add("pymdownx.details")
            elif c.construct_type == "snippet":
                detected_markdown_extensions.add("pymdownx.snippets")
            elif c.construct_type == "mermaid":
                detected_markdown_extensions.add("pymdownx.superfences")

        docs_dir_name = (
            report.mkdocs_config.docs_dir if report.mkdocs_config else "docs"
        )
        docs_dir = self.project_root / docs_dir_name
        md_files = sorted(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else []

        # Check MkDocs mkdocstrings inherited_members configuration
        has_inherited_members = False
        global_inherited_members_list: Optional[List[str]] = None
        if report.mkdocs_config:
            mkdocstrings_cfg = report.mkdocs_config.plugins_config.get(
                "mkdocstrings", {}
            )
            if isinstance(mkdocstrings_cfg, dict):
                py_opts = (
                    mkdocstrings_cfg.get("handlers", {})
                    .get("python", {})
                    .get("options", {})
                )
                if not isinstance(py_opts, dict):
                    py_opts = mkdocstrings_cfg.get("options", {})
                if isinstance(py_opts, dict) and "inherited_members" in py_opts:
                    val = py_opts["inherited_members"]
                    if isinstance(val, list):
                        has_inherited_members = True
                        global_inherited_members_list = [str(x) for x in val]
                    else:
                        has_inherited_members = bool(val)

        # Statically analyze all project class hierarchies using AST to distinguish
        # internal base classes (which should have members documented) from external/stdlib base classes.
        src_paths: List[Path] = []
        if report.mkdocs_config:
            mkdocstrings_cfg = report.mkdocs_config.plugins_config.get(
                "mkdocstrings", {}
            )
            if isinstance(mkdocstrings_cfg, dict):
                py_paths = (
                    mkdocstrings_cfg.get("handlers", {})
                    .get("python", {})
                    .get("paths", [])
                )
                for p in py_paths:
                    candidate = self.project_root / p
                    if candidate.exists() and candidate.is_dir():
                        src_paths.append(candidate)
        if not src_paths:
            default_src = self.project_root / "src"
            if default_src.exists() and default_src.is_dir():
                src_paths.append(default_src)
            else:
                src_paths.append(self.project_root)

        class_bases: Dict[str, List[str]] = {}
        for src_dir in src_paths:
            for py_f in src_dir.rglob("*.py"):
                if any(
                    p.startswith(".") or p in ("venv", ".tox", "site-packages")
                    for p in py_f.parts
                ):
                    continue
                try:
                    m_ast = ast.parse(
                        py_f.read_text(encoding="utf-8"), filename=str(py_f)
                    )
                    for n in m_ast.body:
                        if isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
                            b_list = []
                            for b in n.bases:
                                if isinstance(b, ast.Name):
                                    b_list.append(b.id)
                                elif isinstance(b, ast.Attribute):
                                    b_list.append(b.attr)
                            class_bases[n.name] = b_list
                except Exception:
                    pass

        project_classes = set(class_bases.keys())

        def get_ext_bases(cls_name: str, visited: Set[str]) -> Set[str]:
            if cls_name in visited:
                return set()
            visited.add(cls_name)
            ext = set()
            for base in class_bases.get(cls_name, []):
                leaf = base.split(".")[-1]
                if leaf in project_classes:
                    ext.update(get_ext_bases(leaf, visited))
                else:
                    ext.add(leaf)
            return ext

        class_external_bases: Dict[str, Set[str]] = {
            c: get_ext_bases(c, set()) for c in class_bases
        }

        planned_pages: List[DocumentationArtifact] = []
        planned_api_strategies: List[ApiGenerationStrategy] = []
        planned_cross_refs: List[CrossReferenceAction] = []
        planned_assets: List[AssetAction] = []
        site_pages: Dict[str, DocumentationPage] = {}

        for md_file in md_files:
            rel_file = str(md_file.relative_to(self.project_root))
            raw_text = md_file.read_text(encoding="utf-8")
            raw_lines = raw_text.splitlines()

            doc_ir = self.parser.parse_text(raw_text, file_path=rel_file)
            file_actions = self.rule_engine.create_actions(doc_ir, raw_lines=raw_lines)

            # Ensure stable, ordered action IDs
            for act in file_actions:
                act.action_id = f"act_{action_counter:04d}"
                action_counter += 1
                all_actions.append(act)

            # Flow extraction for DocumentFlowSpec
            page_ir = self.flow_extractor.extract_from_text(
                raw_text, file_path=rel_file
            )
            site_pages[page_ir.logical_route] = page_ir

            # Build planned flow actions preserving source order
            flow_actions: List[DocumentFlowAction] = []
            page_construct_ids: List[str] = []
            for elem in page_ir.flow.elements:
                page_construct_ids.append(elem.construct_id)
                summary_text = ""
                strategy_name = "PRESERVE"
                target_dir = None

                if elem.element_type == DocumentElementType.HEADING and isinstance(
                    elem.content, HeadingElement
                ):
                    summary_text = f"H{elem.content.level}: {elem.content.text}"
                    strategy_name = "TRANSFORM"
                elif elem.element_type == DocumentElementType.PARAGRAPH and isinstance(
                    elem.content, ParagraphElement
                ):
                    summary_text = elem.content.text[:50]
                    strategy_name = "TRANSFORM"
                elif (
                    elem.element_type == DocumentElementType.API_REQUEST
                    and isinstance(elem.content, ApiDocumentationRequest)
                ):
                    api_req = elem.content
                    summary_text = f"API Request: {api_req.object_path}"
                    strategy_name = "AUTODOC"

                    if api_req.object_kind.value == "module":
                        kind = ApiDirectiveKind.AUTOMODULE
                        directive_name = "automodule"
                    elif api_req.object_kind.value == "function":
                        kind = ApiDirectiveKind.AUTOFUNCTION
                        directive_name = "autofunction"
                    elif api_req.object_kind.value == "exception":
                        kind = ApiDirectiveKind.AUTOEXCEPTION
                        directive_name = "autoexception"
                    else:
                        kind = ApiDirectiveKind.AUTOCLASS
                        directive_name = "autoclass"

                    dir_lines = [f".. {directive_name}:: {api_req.object_path}"]
                    if (
                        api_req.member_selection.value == "EXPLICIT"
                        and api_req.explicit_members
                    ):
                        dir_lines.append(
                            f"    :members: {', '.join(api_req.explicit_members)}"
                        )
                    elif api_req.member_selection.value == "ALL_PUBLIC":
                        dir_lines.append("    :members:")

                    inh_prop_str = None
                    if api_req.object_kind.value in ("class", "exception"):
                        dir_lines.append("    :show-inheritance:")
                        raw_inh = api_req.normalized_options.get("inherited_members")
                        if raw_inh is None:
                            raw_inh = api_req.raw_options.get("inherited_members")

                        if raw_inh is not None:
                            should_inh = bool(raw_inh)
                            allowed_bases = (
                                raw_inh if isinstance(raw_inh, list) else None
                            )
                        else:
                            should_inh = has_inherited_members
                            allowed_bases = global_inherited_members_list

                        if should_inh:
                            cls_leaf = api_req.object_path.split(".")[-1]
                            ext_bases = set(class_external_bases.get(cls_leaf, set()))
                            if allowed_bases:
                                all_superclasses = (
                                    set(class_bases.get(cls_leaf, [])) | ext_bases
                                )
                                excluded = (
                                    all_superclasses - set(allowed_bases)
                                ) | ext_bases
                                if excluded:
                                    inh_prop_str = ", ".join(sorted(excluded))
                                    dir_lines.append(
                                        f"    :inherited-members: {inh_prop_str}"
                                    )
                                else:
                                    dir_lines.append("    :inherited-members:")
                            elif ext_bases:
                                inh_prop_str = ", ".join(sorted(ext_bases))
                                dir_lines.append(
                                    f"    :inherited-members: {inh_prop_str}"
                                )
                            else:
                                dir_lines.append("    :inherited-members:")

                    target_dir = "\n".join(dir_lines)

                    api_strat = ApiGenerationStrategy(
                        object_path=api_req.object_path,
                        directive_kind=kind,
                        options=api_req.normalized_options,
                        members=api_req.explicit_members
                        if api_req.explicit_members
                        else None,
                        inherited_members=inh_prop_str,
                        source_construct_id=elem.construct_id,
                        rationale=f"Synthesized from source {api_req.handler} API request for {api_req.object_path}.",
                    )
                    planned_api_strategies.append(api_strat)
                elif elem.element_type == DocumentElementType.LIST and isinstance(
                    elem.content, ListElement
                ):
                    summary_text = f"List ({len(elem.content.items)} items, {'ordered' if elem.content.ordered else 'unordered'})"
                    strategy_name = "PRESERVE"
                elif elem.element_type == DocumentElementType.CODE_BLOCK and isinstance(
                    elem.content, CodeBlockElement
                ):
                    summary_text = f"Code block ({elem.content.language or 'text'})"
                    strategy_name = "TRANSFORM"
                elif elem.element_type == DocumentElementType.ADMONITION and isinstance(
                    elem.content, AdmonitionElement
                ):
                    summary_text = f"Admonition ({elem.content.kind})"
                    strategy_name = "TRANSFORM"
                elif elem.element_type == DocumentElementType.SNIPPET and isinstance(
                    elem.content, SnippetElement
                ):
                    summary_text = f"Snippet include: {elem.content.snippet_path}"
                    strategy_name = "TRANSFORM"
                    target_dir = f"```{{include}} {elem.content.snippet_path}\n```"
                else:
                    summary_text = elem.element_type.value
                    strategy_name = "PRESERVE"

                flow_actions.append(
                    DocumentFlowAction(
                        action_id=f"flow_{elem.construct_id}",
                        order_index=elem.source_order_index,
                        source_construct_id=elem.construct_id,
                        element_type=elem.element_type.value,
                        strategy=strategy_name,
                        content_summary=summary_text,
                        target_directive=target_dir,
                        rationale=f"Realize source element {elem.construct_id} in target document.",
                    )
                )

            # Cross references and asset actions
            for link in page_ir.outgoing_links:
                planned_cross_refs.append(
                    CrossReferenceAction(
                        source_construct_id=link.source_construct_id,
                        source_file=rel_file,
                        source_target=link.target,
                        transformed_target=link.target.replace(".md", ".html")
                        if link.target.endswith(".md")
                        else link.target,
                        is_doc_ref=link.link_kind == "internal_page",
                        rationale="Transformed MkDocs relative doc link to Sphinx target reference.",
                    )
                )

            for asset in page_ir.referenced_assets:
                planned_assets.append(
                    AssetAction(
                        source_construct_id=asset.source_construct_id,
                        source_path=asset.source_path,
                        target_path=f"_static/{Path(asset.source_path).name}",
                        asset_kind=asset.asset_kind,
                        rationale="Static asset copy to Sphinx _static directory.",
                    )
                )

            planned_pages.append(
                DocumentationArtifact(
                    artifact_id=f"art_{page_ir.logical_route.replace('/', '_') or 'index'}",
                    target_path=rel_file,
                    source_file=rel_file,
                    title=page_ir.title or Path(rel_file).stem,
                    artifact_kind="markdown_doc",
                    provenance=RequirementProvenance.DOCUMENT_CONSTRUCT,
                    rationale="Transformed source markdown document preserving ordered semantic flow.",
                    flow_actions=flow_actions,
                    artifact_provenance=ArtifactProvenance(
                        source_construct_ids=page_construct_ids,
                        source_files=[rel_file],
                        required_extensions=[],
                        required_packages=[],
                    ),
                )
            )

        # 3. Categorize Summary & Collect Requirements with Source Tracking
        summary = PlanActionSummary(total_actions=len(all_actions))
        manual_items: List[ManualReviewItem] = []
        unsupported_items: List[MigrationAction] = []

        ext_sources: Dict[str, List[str]] = {}
        pkg_sources: Dict[str, List[str]] = {}
        provenance_map: Dict[str, RequirementProvenance] = {}
        rationale_map: Dict[str, str] = {}

        for action in all_actions:
            loc_str = f"{action.source_file}:{action.start_line}"
            if action.classification == Classification.TRANSFORM:
                summary.transform_count += 1
            elif action.classification == Classification.PRESERVE:
                summary.preserve_count += 1
            elif action.classification == Classification.MANUAL:
                summary.manual_count += 1
                manual_items.append(
                    ManualReviewItem(
                        item_id=f"manual_{action.action_id}",
                        source_file=action.source_file,
                        line_number=action.start_line,
                        construct_type=action.source_kind.value,
                        instruction=action.manual_instruction
                        or "Manual review required.",
                        rationale=action.description,
                    )
                )
            elif action.classification == Classification.UNSUPPORTED:
                summary.unsupported_count += 1
                unsupported_items.append(action)

            # Map extensions & packages from construct actions
            for ext in action.required_extensions:
                ext_sources.setdefault(ext, []).append(loc_str)
                provenance_map[ext] = RequirementProvenance.DOCUMENT_CONSTRUCT
                rationale_map[ext] = (
                    "Required by document construct(s) in project Markdown files."
                )
            for pkg in action.required_packages:
                pkg_sources.setdefault(pkg, []).append(loc_str)
                provenance_map[pkg] = RequirementProvenance.DOCUMENT_CONSTRUCT
                rationale_map[pkg] = (
                    "Required by document construct(s) in project Markdown files."
                )

        # 4. Automatic Source Theme Identification & Sphinx Equivalent Mapping
        source_theme = (
            report.mkdocs_config.theme_name if report.mkdocs_config else "mkdocs"
        )

        # Declarative theme translation matrix
        THEME_EQUIVALENTS: Dict[str, Dict[str, Any]] = {
            "material": {
                "target_theme": "sphinx_immaterial",
                "target_package": "sphinx-immaterial>=0.11.0",
                "target_extension": "sphinx_immaterial",
                "rationale": "Source uses Material for MkDocs; maps automatically to sphinx_immaterial for exact header, palette, and navigation chrome fidelity.",
            },
            "readthedocs": {
                "target_theme": "sphinx_rtd_theme",
                "target_package": "sphinx-rtd-theme>=2.0.0",
                "target_extension": None,
                "rationale": "Source uses ReadTheDocs theme; maps automatically to sphinx_rtd_theme.",
            },
            "mkdocs": {
                "target_theme": "sphinx_rtd_theme",
                "target_package": "sphinx-rtd-theme>=2.0.0",
                "target_extension": None,
                "rationale": "Source uses standard mkdocs theme; maps automatically to sphinx_rtd_theme.",
            },
        }

        matched_spec: Optional[Dict[str, Any]] = None
        for k, spec in THEME_EQUIVALENTS.items():
            if k in source_theme.lower():
                matched_spec = spec
                break

        if matched_spec:
            theme_proposal = ThemeMigrationProposal(
                source_theme=source_theme,
                target_theme=matched_spec["target_theme"],
                target_package=matched_spec["target_package"],
                classification=Classification.TRANSFORM,
                rationale=matched_spec["rationale"],
            )
            pkg_sources.setdefault(matched_spec["target_package"], []).append(
                f"theme_policy:{source_theme}"
            )
            provenance_map[matched_spec["target_package"]] = (
                RequirementProvenance.THEME_POLICY
            )
            rationale_map[matched_spec["target_package"]] = theme_proposal.rationale

            if matched_spec.get("target_extension"):
                ext_sources.setdefault(matched_spec["target_extension"], []).append(
                    f"theme_policy:{source_theme}"
                )
                provenance_map[matched_spec["target_extension"]] = (
                    RequirementProvenance.THEME_POLICY
                )
                rationale_map[matched_spec["target_extension"]] = (
                    theme_proposal.rationale
                )
        else:
            # Custom or unrecognized theme requires MANUAL decision
            theme_proposal = ThemeMigrationProposal(
                source_theme=source_theme,
                target_theme=None,
                target_package=None,
                classification=Classification.MANUAL,
                rationale=f"Custom/unrecognized theme '{source_theme}' has no automated Sphinx equivalent. Manual theme selection required.",
            )
            manual_items.append(
                ManualReviewItem(
                    item_id="manual_theme_selection",
                    source_file="mkdocs.yml",
                    line_number=1,
                    construct_type="theme",
                    instruction=f"Select an appropriate Sphinx theme (e.g. Furo, PyData Sphinx Theme, or sphinx-rtd-theme) for '{source_theme}'.",
                    rationale=theme_proposal.rationale,
                )
            )

        # 5. Declarative Policy Evaluation for Theme Features, Extensions, and Plugins
        myst_enabled: Set[str] = {"colon_fence"}
        custom_conf_options: Dict[str, Any] = {}

        if report.mkdocs_config:
            # 5a. Theme Features
            for feat in report.mkdocs_config.theme_features or []:
                rule = self.policy_engine.evaluate_feature(feat)
                if rule:
                    for ext in rule.required_extensions:
                        ext_sources.setdefault(ext, []).append(f"theme_feature:{feat}")
                        provenance_map[ext] = RequirementProvenance.FEATURE_POLICY
                        rationale_map[ext] = rule.rationale
                    for pkg in rule.required_packages:
                        pkg_sources.setdefault(pkg, []).append(f"theme_feature:{feat}")
                        provenance_map[pkg] = RequirementProvenance.FEATURE_POLICY
                        rationale_map[pkg] = rule.rationale
                    for m_ext in rule.myst_extensions:
                        myst_enabled.add(m_ext)
                    if rule.conf_settings:
                        custom_conf_options.update(rule.conf_settings)
                    if rule.classification == Classification.MANUAL:
                        manual_items.append(
                            ManualReviewItem(
                                item_id=f"manual_feat_{feat.replace('.', '_')}",
                                source_file="mkdocs.yml",
                                line_number=1,
                                construct_type="theme_feature",
                                instruction=rule.manual_instruction
                                or "Manual review required.",
                                rationale=rule.rationale,
                            )
                        )

            # 5b. Markdown Extensions
            for ext_entry in report.mkdocs_config.markdown_extensions or []:
                ext_name = (
                    ext_entry
                    if isinstance(ext_entry, str)
                    else getattr(ext_entry, "name", str(ext_entry))
                )
                rule = self.policy_engine.evaluate_feature(ext_name)
                if rule:
                    for ext in rule.required_extensions:
                        ext_sources.setdefault(ext, []).append(
                            f"markdown_extension:{ext_name}"
                        )
                        provenance_map.setdefault(
                            ext, RequirementProvenance.EXTENSION_POLICY
                        )
                        rationale_map.setdefault(ext, rule.rationale)
                    for pkg in rule.required_packages:
                        pkg_sources.setdefault(pkg, []).append(
                            f"markdown_extension:{ext_name}"
                        )
                        provenance_map.setdefault(
                            pkg, RequirementProvenance.EXTENSION_POLICY
                        )
                        rationale_map.setdefault(pkg, rule.rationale)
                    for m_ext in rule.myst_extensions:
                        myst_enabled.add(m_ext)
                    if rule.conf_settings:
                        custom_conf_options.update(rule.conf_settings)
                    if rule.classification == Classification.MANUAL:
                        manual_items.append(
                            ManualReviewItem(
                                item_id=f"manual_ext_{ext_name.replace('.', '_')}",
                                source_file="mkdocs.yml",
                                line_number=1,
                                construct_type="markdown_extension",
                                instruction=rule.manual_instruction
                                or "Manual review required.",
                                rationale=rule.rationale,
                            )
                        )

            # 5c. Plugins
            for plg_entry in report.mkdocs_config.plugins or []:
                plg_name = (
                    plg_entry
                    if isinstance(plg_entry, str)
                    else getattr(plg_entry, "name", str(plg_entry))
                )
                rule = self.policy_engine.evaluate_feature(plg_name)
                if rule:
                    for ext in rule.required_extensions:
                        ext_sources.setdefault(ext, []).append(f"plugin:{plg_name}")
                        provenance_map.setdefault(
                            ext, RequirementProvenance.EXTENSION_POLICY
                        )
                        rationale_map.setdefault(ext, rule.rationale)
                    for pkg in rule.required_packages:
                        pkg_sources.setdefault(pkg, []).append(f"plugin:{plg_name}")
                        provenance_map.setdefault(
                            pkg, RequirementProvenance.EXTENSION_POLICY
                        )
                        rationale_map.setdefault(pkg, rule.rationale)
                    for m_ext in rule.myst_extensions:
                        myst_enabled.add(m_ext)
                    if rule.conf_settings:
                        custom_conf_options.update(rule.conf_settings)
                    if rule.classification == Classification.MANUAL:
                        manual_items.append(
                            ManualReviewItem(
                                item_id=f"manual_plugin_{plg_name.replace('.', '_')}",
                                source_file="mkdocs.yml",
                                line_number=1,
                                construct_type="plugin",
                                instruction=rule.manual_instruction
                                or "Manual review required.",
                                rationale=rule.rationale,
                            )
                        )

        # Check in-document detected extensions
        if "tasklist" in detected_markdown_extensions:
            myst_enabled.add("tasklist")
        if "attrs_block" in detected_markdown_extensions:
            myst_enabled.add("attrs_block")

        # 6. Generated Documentation Pipeline Planning (e.g. gen-files, mkdocstrings, literate-nav)
        # In MkDocs, dynamic generator scripts (e.g. `scripts/gen_ref_nav.py`) run at build time
        # to construct in-memory virtual markdown documents (`mkdocs_gen_files.open(...)`).
        # Sphinx builds from permanent filesystem files. We statically inspect the generator
        # scripts via AST to deduce the source directories, output prefix, and literate nav files,
        # then synthesize concrete MyST reference stubs directly into the documentation tree.
        # This replaces the need for build-time Python generation and allows the obsolete script
        # to be deleted during post-migration cleanup.
        generated_doc_proposals: List[GeneratedDocumentProposal] = []
        api_reference_mappings: Dict[str, str] = {}
        if report.mkdocs_config and "gen-files" in report.mkdocs_config.plugins:
            gen_cfg = report.mkdocs_config.plugins_config.get("gen-files", {})
            scripts = gen_cfg.get("scripts", [])

            # Statically analyze declared generator scripts (e.g. scripts/gen_ref_nav.py)
            script_meta: Dict[str, Any] = {
                "source_dir": "src",
                "output_dir": "reference",
                "literate_nav": None,
                "pattern": "::: {ident}",
            }
            for s_path_str in scripts:
                s_file = self.project_root / s_path_str
                if s_file.exists():
                    try:
                        s_tree = ast.parse(
                            s_file.read_text(encoding="utf-8"), filename=str(s_file)
                        )
                        for node in ast.walk(s_tree):
                            if isinstance(node, ast.Call):
                                if (
                                    isinstance(node.func, ast.Name)
                                    and node.func.id == "Path"
                                ):
                                    for arg in node.args:
                                        if isinstance(arg, ast.Constant) and isinstance(
                                            arg.value, str
                                        ):
                                            if (self.project_root / arg.value).is_dir():
                                                script_meta["source_dir"] = arg.value
                                            elif arg.value in (
                                                "reference",
                                                "api",
                                                "docs",
                                            ):
                                                script_meta["output_dir"] = arg.value
                                elif (
                                    isinstance(node.func, ast.Attribute)
                                    and node.func.attr == "open"
                                ):
                                    for arg in node.args:
                                        if isinstance(arg, ast.Constant) and isinstance(
                                            arg.value, str
                                        ):
                                            if "SUMMARY" in arg.value:
                                                script_meta["literate_nav"] = arg.value
                                            elif "/" in arg.value:
                                                script_meta["output_dir"] = (
                                                    arg.value.split("/")[0]
                                                )
                    except Exception:
                        pass

            output_prefix = script_meta.get("output_dir", "reference")

            # Discover Python packages & modules to materialize deterministic reference documentation
            package_modules: Dict[str, List[str]] = {}
            module_members: Dict[str, Dict[str, List[str]]] = {}
            for src_dir in src_paths:
                py_files = sorted(list(src_dir.rglob("*.py")))
                for py_f in py_files:
                    rel_mod = py_f.relative_to(src_dir).with_suffix("")
                    parts = list(rel_mod.parts)

                    is_pkg_index = False
                    if parts[-1] == "__init__":
                        parts = parts[:-1]
                        is_pkg_index = True
                    elif parts[-1].startswith("_"):
                        continue

                    if not parts:
                        continue

                    # Inspect source statically; never import the project being
                    # migrated merely to create an API index.
                    members: Dict[str, List[str]] = {
                        "classes": [],
                        "functions": [],
                        "attributes": [],
                    }
                    module_docstring = None
                    try:
                        module_ast = ast.parse(
                            py_f.read_text(encoding="utf-8"), filename=str(py_f)
                        )
                        module_docstring = ast.get_docstring(module_ast)
                        for node in module_ast.body:
                            if isinstance(
                                node, ast.ClassDef
                            ) and not node.name.startswith("_"):
                                members["classes"].append(node.name)
                            elif isinstance(
                                node, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ) and not node.name.startswith("_"):
                                members["functions"].append(node.name)
                            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                                targets = (
                                    node.targets
                                    if isinstance(node, ast.Assign)
                                    else [node.target]
                                )
                                for target in targets:
                                    if isinstance(
                                        target, ast.Name
                                    ) and not target.id.startswith("_"):
                                        members["attributes"].append(target.id)
                    except (OSError, SyntaxError, UnicodeDecodeError):
                        pass

                    pkg_key = (
                        "/".join(parts[:-1]) if not is_pkg_index else "/".join(parts)
                    )
                    if not is_pkg_index:
                        package_modules.setdefault(pkg_key, []).append(parts[-1])

                    module_qualname = ".".join(parts)
                    module_members[module_qualname] = members
                    if is_pkg_index:
                        target_rel = f"{docs_dir_name}/{output_prefix}/{'/'.join(parts)}/index.md"
                    else:
                        target_rel = (
                            f"{docs_dir_name}/{output_prefix}/{'/'.join(parts)}.md"
                        )

                    # Generate summary tables from the same names that will be
                    # rendered by autodoc.  ``autosummary_generate`` remains
                    # disabled because these migration proposals already own
                    # the destination pages and their local navigation.
                    doc_title = parts[-1]
                    flow_actions = []
                    order_idx = 0

                    # Check if rendered HTML from mkdocs build exists
                    site_dir_cand = self.project_root / "site"
                    cand_html_paths = [
                        site_dir_cand / "reference" / ("/".join(parts)) / "index.html",
                        site_dir_cand / "reference" / f"{'/'.join(parts)}.html",
                    ]

                    found_html = None
                    for cand in cand_html_paths:
                        if cand.exists():
                            found_html = cand
                            break

                    if found_html:
                        html_parser = HtmlFlowParser()
                        html_flow = html_parser.parse_file(
                            found_html, rel_route=target_rel
                        )
                        if html_flow.title:
                            doc_title = html_flow.title

                        summary_elems = [
                            el
                            for el in html_flow.elements
                            if el.role == HtmlFlowRole.AUTOSUMMARY
                        ]
                        api_member_elems = [
                            el
                            for el in html_flow.elements
                            if el.role
                            in (
                                HtmlFlowRole.API_CLASS,
                                HtmlFlowRole.API_FUNCTION,
                                HtmlFlowRole.API_ATTRIBUTE,
                            )
                        ]
                        mod_elems = [
                            el
                            for el in html_flow.elements
                            if el.role == HtmlFlowRole.API_MODULE
                        ]

                        flow_actions.append(
                            DocumentFlowAction(
                                action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                order_index=order_idx,
                                source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                element_type="HEADING",
                                strategy="PRESERVE",
                                content_summary=doc_title,
                                rationale="API reference document heading.",
                            )
                        )
                        order_idx += 1

                        if is_pkg_index:
                            lines = [f"# {doc_title}\n"]
                            if summary_elems:
                                lines.append(
                                    f"```{{eval-rst}}\n.. currentmodule:: {module_qualname}\n\n.. autosummary::\n   :nosignatures:\n\n"
                                )
                                for sm in summary_elems:
                                    flow_actions.append(
                                        DocumentFlowAction(
                                            action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                            order_index=order_idx,
                                            source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                            element_type="AUTOSUMMARY",
                                            strategy="AUTOSUMMARY",
                                            content_summary=(
                                                ", ".join(sm.symbols)
                                                if sm.symbols
                                                else ""
                                            )[:50],
                                            target_directive="autosummary",
                                            rationale="Package index module summary table.",
                                        )
                                    )
                                    order_idx += 1
                                    for s in sm.symbols:
                                        lines.append(f"   {s}\n")
                                lines.append("```\n")
                            doc_content = "\n".join(lines).rstrip() + "\n"
                        else:
                            blocks: list[str] = [f"# {doc_title}\n"]

                            # Block 1: automodule with :no-members: to render module docstring & register module
                            blocks.append(
                                f"```{{eval-rst}}\n.. automodule:: {module_qualname}\n   :no-members:\n```\n"
                            )
                            flow_actions.append(
                                DocumentFlowAction(
                                    action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                    order_index=order_idx,
                                    source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                    element_type="API_MODULE",
                                    strategy="AUTODOC",
                                    content_summary=f"automodule::{module_qualname}",
                                    target_directive=f".. automodule:: {module_qualname}",
                                    rationale="Module registration and docstring presentation without dumping members.",
                                )
                            )
                            order_idx += 1

                            # Block 2: Autosummary tables grouped under currentmodule with rubrics and ~Symbol
                            if summary_elems:
                                summary_lines = [
                                    f"```{{eval-rst}}\n.. currentmodule:: {module_qualname}"
                                ]
                                for sm in summary_elems:
                                    rubric = None
                                    if sm.headers:
                                        h = sm.headers[0].upper()
                                        if "CLASS" in h:
                                            rubric = "Classes"
                                        elif "FUNC" in h:
                                            rubric = "Functions"
                                        elif "ATTR" in h:
                                            rubric = "Attributes"
                                        elif "EXCEPT" in h:
                                            rubric = "Exceptions"
                                    if rubric:
                                        summary_lines.append(f"\n.. rubric:: {rubric}")
                                    nosig = (
                                        "\n   :nosignatures:"
                                        if sm.options.get("nosignatures", True)
                                        else ""
                                    )
                                    summary_lines.append(f"\n.. autosummary::{nosig}\n")
                                    for s in sm.symbols:
                                        s_clean = s.split("(")[0].strip()
                                        s_fmt = (
                                            s_clean
                                            if s_clean.startswith("~")
                                            else f"~{s_clean}"
                                        )
                                        summary_lines.append(f"   {s_fmt}")
                                    flow_actions.append(
                                        DocumentFlowAction(
                                            action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                            order_index=order_idx,
                                            source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                            element_type="AUTOSUMMARY",
                                            strategy="AUTOSUMMARY",
                                            content_summary=(
                                                ", ".join(sm.symbols)
                                                if sm.symbols
                                                else ""
                                            )[:50],
                                            target_directive="autosummary",
                                            rationale="Summary table mapped to Sphinx autosummary.",
                                        )
                                    )
                                    order_idx += 1
                                summary_lines.append("```\n")
                                blocks.append("\n".join(summary_lines))

                            # Block 3: Individual member directives in exact parsed DOM sequence
                            if api_member_elems:
                                member_lines = [
                                    f"```{{eval-rst}}\n.. currentmodule:: {module_qualname}"
                                ]
                                for el in api_member_elems:
                                    target_name = (
                                        el.qname.split(".")[-1]
                                        if el.qname
                                        else module_qualname
                                    )
                                    if el.role == HtmlFlowRole.API_ATTRIBUTE:
                                        directive = el.directive or "autodata"
                                        member_lines.append(
                                            f"\n.. {directive}:: {target_name}"
                                        )
                                    elif el.role == HtmlFlowRole.API_CLASS:
                                        raw_inh = el.options.get("inherited_members")
                                        if raw_inh is None:
                                            raw_inh = el.options.get(
                                                "inherited-members"
                                            )

                                        if raw_inh is not None:
                                            should_inh = bool(raw_inh)
                                            allowed_bases = (
                                                raw_inh
                                                if isinstance(raw_inh, list)
                                                else None
                                            )
                                        else:
                                            should_inh = has_inherited_members
                                            allowed_bases = (
                                                global_inherited_members_list
                                            )

                                        if should_inh:
                                            ext_bases = set(
                                                class_external_bases.get(
                                                    target_name, set()
                                                )
                                            )
                                            if allowed_bases:
                                                all_superclasses = (
                                                    set(
                                                        class_bases.get(target_name, [])
                                                    )
                                                    | ext_bases
                                                )
                                                excluded = (
                                                    all_superclasses
                                                    - set(allowed_bases)
                                                ) | ext_bases
                                                if excluded:
                                                    inh_str = f"\n   :inherited-members: {', '.join(sorted(excluded))}"
                                                else:
                                                    inh_str = "\n   :inherited-members:"
                                            elif ext_bases:
                                                inh_str = f"\n   :inherited-members: {', '.join(sorted(ext_bases))}"
                                            else:
                                                inh_str = "\n   :inherited-members:"
                                        else:
                                            inh_str = ""
                                        member_lines.append(
                                            f"\n.. autoclass:: {target_name}\n   :members:\n   :undoc-members:\n   :show-inheritance:{inh_str}"
                                        )
                                    elif el.role == HtmlFlowRole.API_FUNCTION:
                                        directive = el.directive or "autofunction"
                                        member_lines.append(
                                            f"\n.. {directive}:: {target_name}"
                                        )
                                    flow_actions.append(
                                        DocumentFlowAction(
                                            action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                            order_index=order_idx,
                                            source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                            element_type=el.role.value,
                                            strategy="AUTODOC",
                                            content_summary=(el.qname or "")[:50],
                                            target_directive=el.directive,
                                            rationale=f"Ordered API element {el.role.value} mapped to Sphinx {el.directive}.",
                                        )
                                    )
                                    order_idx += 1
                                member_lines.append("```\n")
                                blocks.append("\n".join(member_lines))
                            elif not summary_elems and mod_elems:
                                # Stub or memberless module
                                pass

                            doc_content = "\n".join(blocks).rstrip() + "\n"
                    else:
                        # Deterministic fallback to Python AST analysis
                        flow_actions.append(
                            DocumentFlowAction(
                                action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                order_index=order_idx,
                                source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                element_type="HEADING",
                                strategy="PRESERVE",
                                content_summary=doc_title,
                                rationale="API reference document heading.",
                            )
                        )
                        order_idx += 1

                        if is_pkg_index:
                            doc_content = f"# {doc_title}\n\n"
                            if module_docstring:
                                for p_txt in module_docstring.strip().split("\n\n"):
                                    p_clean = p_txt.strip()
                                    if p_clean:
                                        flow_actions.append(
                                            DocumentFlowAction(
                                                action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                                order_index=order_idx,
                                                source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                                element_type="PARAGRAPH",
                                                strategy="PRESERVE",
                                                content_summary=p_clean[:50],
                                                rationale="Module docstring overview prose.",
                                            )
                                        )
                                        order_idx += 1
                                doc_content += f"{module_docstring.strip()}\n\n"
                            doc_content += f"```{{eval-rst}}\n.. currentmodule:: {module_qualname}\n\n.. autosummary::\n   :nosignatures:\n\n"
                            flow_actions.append(
                                DocumentFlowAction(
                                    action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                    order_index=order_idx,
                                    source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                    element_type="AUTOSUMMARY",
                                    strategy="AUTOSUMMARY",
                                    content_summary="Package index summary table",
                                    target_directive="autosummary",
                                    rationale="Summary table for package index.",
                                )
                            )
                            order_idx += 1
                        else:
                            doc_content = f"# {doc_title}\n\n"
                            if module_docstring:
                                for p_txt in module_docstring.strip().split("\n\n"):
                                    p_clean = p_txt.strip()
                                    if p_clean:
                                        flow_actions.append(
                                            DocumentFlowAction(
                                                action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                                order_index=order_idx,
                                                source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                                element_type="PARAGRAPH",
                                                strategy="PRESERVE",
                                                content_summary=p_clean[:50],
                                                rationale="Module docstring overview prose.",
                                            )
                                        )
                                        order_idx += 1
                                doc_content += f"{module_docstring.strip()}\n\n"
                            doc_content += f"```{{eval-rst}}\n.. currentmodule:: {module_qualname}\n"
                            for heading, key in (
                                ("Classes", "classes"),
                                ("Functions", "functions"),
                                ("Attributes", "attributes"),
                            ):
                                if members[key]:
                                    doc_content += f"\n.. rubric:: {heading}\n\n.. autosummary::\n   :nosignatures:\n\n"
                                    doc_content += "".join(
                                        f"   {name}\n" for name in members[key]
                                    )
                                    flow_actions.append(
                                        DocumentFlowAction(
                                            action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                            order_index=order_idx,
                                            source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                            element_type="AUTOSUMMARY",
                                            strategy="AUTOSUMMARY",
                                            content_summary=f"Summary table for {heading}",
                                            target_directive="autosummary",
                                            rationale=f"Summary table for {heading}.",
                                        )
                                    )
                                    order_idx += 1
                            doc_content += f"\n.. automodule:: {module_qualname}\n   :members:\n   :undoc-members:\n   :show-inheritance:\n"
                            flow_actions.append(
                                DocumentFlowAction(
                                    action_id=f"flow_doc_{target_rel.replace('/', '_').replace('.', '_')}_{order_idx}",
                                    order_index=order_idx,
                                    source_construct_id=f"doc:{target_rel}:elem:{order_idx:04d}",
                                    element_type="API_REQUEST",
                                    strategy="AUTODOC",
                                    content_summary=f"automodule::{module_qualname}",
                                    target_directive=f".. automodule:: {module_qualname}",
                                    rationale="Full module autodoc expansion.",
                                )
                            )
                            order_idx += 1
                        doc_content += "```\n"

                    generated_doc_proposals.append(
                        GeneratedDocumentProposal(
                            target_path=target_rel,
                            title=doc_title,
                            content=doc_content,
                            generator_plugin="gen-files",
                            generator_script=scripts[0] if scripts else None,
                            provenance=RequirementProvenance.GENERATED_PIPELINE,
                            rationale=f"Synthesized API reference documentation for {module_qualname} matching MkDocs gen-files/mkdocstrings pipeline.",
                            flow_actions=flow_actions,
                        )
                    )
                    api_reference_mappings[module_qualname] = target_rel

            # If package index exists, append toctree of child modules so Sphinx tree is complete
            for gen_prop in generated_doc_proposals:
                if gen_prop.target_path.endswith("/index.md"):
                    # Find package key
                    rel_no_prefix = gen_prop.target_path[
                        len(f"{docs_dir_name}/{output_prefix}/") : -len("/index.md")
                    ]
                    child_mods = package_modules.get(rel_no_prefix, [])
                    if child_mods:
                        if ".. autosummary::" in gen_prop.content and not any(
                            f"   {cm}" in gen_prop.content for cm in child_mods
                        ):
                            summary_lines = [
                                f"   {child}" for child in sorted(child_mods)
                            ]
                            insertion = "\n".join(summary_lines) + "\n```\n"
                            gen_prop.content = gen_prop.content.replace(
                                "```\n", insertion, 1
                            )
                        toc_lines = ["\n```{toctree}", ":hidden:", ":maxdepth: 1", ""]
                        for cm in sorted(child_mods):
                            short_title = cm.split(".")[-1]
                            toc_lines.append(f"{short_title} <{cm}>")
                        toc_lines.append("```\n")
                        gen_prop.content += "\n".join(toc_lines)

            if generated_doc_proposals:
                # Ensure API rendering and its summary tables are enabled.
                for ext in [
                    "sphinx.ext.autodoc",
                    "sphinx.ext.autosummary",
                    "sphinx.ext.napoleon",
                ]:
                    ext_sources.setdefault(ext, []).append(
                        "pipeline:gen-files+mkdocstrings"
                    )
                    provenance_map.setdefault(
                        ext, RequirementProvenance.GENERATED_PIPELINE
                    )
                    rationale_map.setdefault(
                        ext, "Required for generated API reference documentation."
                    )

        # 7. Build Traceable RequirementItems
        requirements: List[RequirementItem] = []

        # Target Baseline
        requirements.append(
            RequirementItem(
                name="Sphinx>=7.0.0",
                kind="package",
                provenance=RequirementProvenance.TARGET_BASELINE,
                rationale="Core target documentation engine.",
                sources=["target_baseline"],
            )
        )
        requirements.append(
            RequirementItem(
                name="myst-parser>=2.0.0",
                kind="package",
                provenance=RequirementProvenance.TARGET_BASELINE,
                rationale="Required for CommonMark and MyST Markdown parsing in Sphinx.",
                sources=["target_baseline"],
            )
        )
        requirements.append(
            RequirementItem(
                name="myst_parser",
                kind="extension",
                provenance=RequirementProvenance.TARGET_BASELINE,
                rationale="Sphinx extension for MyST Parser.",
                sources=["target_baseline"],
            )
        )

        # Theme Package Requirement
        if theme_proposal.target_package:
            requirements.append(
                RequirementItem(
                    name=theme_proposal.target_package,
                    kind="package",
                    provenance=RequirementProvenance.THEME_POLICY,
                    rationale=theme_proposal.rationale,
                    sources=pkg_sources.get(
                        theme_proposal.target_package, [f"theme_policy:{source_theme}"]
                    ),
                )
            )

        # Extensions & Packages with Traceable Provenance
        for ext, sources in sorted(ext_sources.items()):
            if ext != "myst_parser":
                requirements.append(
                    RequirementItem(
                        name=ext,
                        kind="extension",
                        provenance=provenance_map.get(
                            ext, RequirementProvenance.DOCUMENT_CONSTRUCT
                        ),
                        rationale=rationale_map.get(
                            ext, f"Required by {len(sources)} source item(s)."
                        ),
                        sources=sources,
                    )
                )

        for pkg, sources in sorted(pkg_sources.items()):
            if pkg not in (
                "Sphinx>=7.0.0",
                "myst-parser>=2.0.0",
                theme_proposal.target_package,
            ):
                requirements.append(
                    RequirementItem(
                        name=pkg,
                        kind="package",
                        provenance=provenance_map.get(
                            pkg, RequirementProvenance.DOCUMENT_CONSTRUCT
                        ),
                        rationale=rationale_map.get(
                            pkg, f"Required by {len(sources)} source item(s)."
                        ),
                        sources=sources,
                    )
                )

        site_name = (
            report.mkdocs_config.site_name if report.mkdocs_config else "Documentation"
        )
        all_ext_names = sorted(
            list({r.name for r in requirements if r.kind == "extension"})
        )

        conf_opts: Dict[str, Any] = {
            "project": site_name,
            "html_title": site_name,
            "html_theme": theme_proposal.target_theme or "sphinx_rtd_theme",
            "add_module_names": False,
        }

        # Map MkDocs metadata & theme properties to Sphinx conf options
        if report.mkdocs_config:
            cfg = report.mkdocs_config
            CONFIG_FIELD_MAP = {
                "copyright": "copyright",
                "site_author": "author",
                "theme_language": "language",
                "theme_logo": "html_logo",
                "theme_favicon": "html_favicon",
                "extra_css": "html_css_files",
                "extra_javascript": "html_js_files",
            }
            for attr, conf_key in CONFIG_FIELD_MAP.items():
                val = getattr(cfg, attr, None)
                if val:
                    if (
                        attr == "copyright"
                        and isinstance(val, str)
                        and ("<" in val or "&" in val)
                    ):
                        clean_c = html.unescape(val)
                        clean_c = re.sub(r"<[^>]+>", "", clean_c)
                        clean_c = re.sub(
                            r"^(?:copyright|\(c\)|©|\s)+",
                            "",
                            clean_c,
                            flags=re.IGNORECASE,
                        ).strip()
                        val = clean_c or val
                    conf_opts[conf_key] = val

            # Theme-specific options (e.g. Furo / Immaterial / RTD)
            theme_opts: Dict[str, Any] = {}
            target_t = theme_proposal.target_theme or "sphinx_rtd_theme"

            if target_t == "sphinx_immaterial":
                # Declarative attribute-to-option mapping
                DIRECT_FIELD_MAPPING = {
                    "theme_icon": "icon",
                    "site_url": "site_url",
                    "repo_url": "repo_url",
                    "edit_uri": "edit_uri",
                    "theme_features": "features",
                }
                for attr, opt_key in DIRECT_FIELD_MAPPING.items():
                    val = getattr(cfg, attr, None)
                    if val:
                        theme_opts[opt_key] = val

                if cfg.repo_url and "github.com/" in cfg.repo_url:
                    theme_opts["repo_name"] = cfg.repo_url.rstrip("/").split(
                        "github.com/"
                    )[1]

                # Material palette mapping
                immaterial_palettes = [
                    {
                        **(
                            {
                                "scheme": p.scheme.value
                                if hasattr(p.scheme, "value")
                                else p.scheme
                            }
                            if p.scheme
                            else {}
                        ),
                        **({"primary": p.primary} if p.primary else {}),
                        **({"accent": p.accent} if p.accent else {}),
                        **(
                            {
                                "toggle": {
                                    k: v
                                    for k, v in [
                                        ("icon", p.toggle_icon),
                                        ("name", p.toggle_name),
                                    ]
                                    if v
                                }
                            }
                            if (p.toggle_icon or p.toggle_name)
                            else {}
                        ),
                    }
                    for p in cfg.theme_palette
                ]
                if immaterial_palettes:
                    theme_opts["palette"] = immaterial_palettes
                # Version selector mapping
                if cfg.extra and "version" in cfg.extra:
                    theme_opts["version_dropdown"] = True
                    v_val = cfg.extra["version"]
                    if isinstance(v_val, dict) and "default" in v_val:
                        conf_opts["version"] = str(v_val["default"])
                    elif isinstance(v_val, str):
                        conf_opts["version"] = v_val

                theme_opts["globaltoc_collapse"] = False

            elif target_t == "furo":
                if cfg.repo_url:
                    # Parse repo info for Furo
                    clean_repo = cfg.repo_url.rstrip("/")
                    if "github.com/" in clean_repo:
                        repo_path = clean_repo.split("github.com/")[1]
                        theme_opts["source_repository"] = (
                            f"https://github.com/{repo_path}"
                        )
                        theme_opts["source_branch"] = "main"
                        theme_opts["source_directory"] = cfg.docs_dir

                from .theme_constants import resolve_material_color, ThemeScheme

                light_vars = {}
                dark_vars = {}

                for p in cfg.theme_palette:
                    primary_hex = (
                        resolve_material_color(p.primary) if p.primary else None
                    )
                    accent_hex = (
                        resolve_material_color(p.accent, is_accent=True)
                        if p.accent
                        else None
                    )

                    if p.scheme in (
                        ThemeScheme.SLATE,
                        ThemeScheme.DARK,
                        "slate",
                        "dark",
                    ):
                        if primary_hex:
                            dark_vars["color-brand-primary"] = primary_hex
                        if accent_hex:
                            dark_vars["color-brand-content"] = accent_hex
                    else:
                        if primary_hex:
                            light_vars["color-brand-primary"] = primary_hex
                        if accent_hex:
                            light_vars["color-brand-content"] = accent_hex

                if light_vars:
                    theme_opts["light_css_variables"] = light_vars
                if dark_vars:
                    theme_opts["dark_css_variables"] = dark_vars

            elif target_t == "sphinx_rtd_theme":
                if cfg.theme_logo:
                    theme_opts["logo_only"] = False
                if cfg.repo_url:
                    theme_opts["vcs_pageview_mode"] = "blob"

            if theme_opts:
                conf_opts["html_theme_options"] = theme_opts

        # Check mkdocstrings options to set native Sphinx conf.py properties
        if report.mkdocs_config:
            mkdocstrings_cfg = report.mkdocs_config.plugins_config.get(
                "mkdocstrings", {}
            )
            if isinstance(mkdocstrings_cfg, dict):
                py_opts = (
                    mkdocstrings_cfg.get("handlers", {})
                    .get("python", {})
                    .get("options", {})
                )
                if not isinstance(py_opts, dict):
                    py_opts = mkdocstrings_cfg.get("options", {})
                if isinstance(py_opts, dict):
                    if py_opts.get("merge_init_into_class"):
                        conf_opts["autoclass_content"] = "both"

        # Statically inspect pyproject.toml for optional dependencies to mock in autodoc if needed
        mock_imports: List[str] = []
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib

                pyproj_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
                opt_deps = pyproj_data.get("project", {}).get(
                    "optional-dependencies", {}
                )
                for group_name in opt_deps:
                    if group_name != "all":
                        mock_imports.append(group_name)
            except Exception:
                pass
        if mock_imports:
            conf_opts["autodoc_mock_imports"] = sorted(list(set(mock_imports)))

        conf_opts.update(custom_conf_options)
        if generated_doc_proposals:
            conf_opts["autosummary_generate"] = False

        sphinx_config_proposal = ConfigMigrationProposal(
            project_name=site_name or self.project_root.name,
            theme=theme_proposal,
            extensions_to_add=all_ext_names,
            myst_enable_extensions=sorted(list(myst_enabled)),
            custom_options=conf_opts,
            rationale={
                "extensions": "Derived from declarative policy engine across document actions, plugins, and theme features.",
                "myst_syntax": f"Derived from MkDocs extensions config and document syntax ({', '.join(sorted(list(myst_enabled)))}).",
            },
        )
        sphinx_config_proposal.rendered_content = build_conf_py(
            cfg=sphinx_config_proposal,
            project_root=self.project_root,
            has_generated_docs=bool(generated_doc_proposals),
        )

        # 8. Synthesize DocumentationPlan from parsed pages and generated proposals
        doc_plan_artifacts: List[DocumentationArtifact] = list(planned_pages)
        for gen_prop in generated_doc_proposals:
            doc_plan_artifacts.append(
                DocumentationArtifact(
                    artifact_id=f"art_gen_{gen_prop.target_path.replace('/', '_').replace('.', '_')}",
                    target_path=gen_prop.target_path,
                    source_file=None,
                    title=gen_prop.title,
                    artifact_kind="generated_stub",
                    provenance=gen_prop.provenance,
                    rationale=gen_prop.rationale,
                    flow_actions=gen_prop.flow_actions,
                    artifact_provenance=ArtifactProvenance(
                        source_construct_ids=[
                            act.source_construct_id
                            for act in gen_prop.flow_actions
                            if act.source_construct_id
                        ],
                        source_files=[],
                        generated_from_pipeline=gen_prop.generator_plugin,
                        required_extensions=[
                            "sphinx.ext.autodoc",
                            "sphinx.ext.autosummary",
                        ],
                        required_packages=[],
                    ),
                )
            )

        docs_dir = self.project_root / docs_dir_name
        all_md_files: List[Path] = (
            sorted(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else []
        )
        nav_entries = (
            report.navigation_analysis.tree
            if (report.navigation_analysis and report.navigation_analysis.has_nav)
            else []
        )

        gen_targets: Set[str] = set()
        for gen_doc in generated_doc_proposals:
            try:
                gen_targets.add(
                    Path(gen_doc.target_path)
                    .relative_to(docs_dir_name)
                    .with_suffix("")
                    .as_posix()
                )
            except ValueError:
                pass

        root_toctrees: List[str] = []
        if report.navigation_analysis and report.navigation_analysis.tree:

            def extract_nav_paths(items: List[Any]) -> List[str]:
                paths = []
                for item in items:
                    if getattr(item, "path", None):
                        paths.append(item.path)
                    if getattr(item, "children", None):
                        paths.extend(extract_nav_paths(item.children))
                return paths

            root_toctrees = extract_nav_paths(report.navigation_analysis.tree)

        resolved_root_toctrees = resolve_navigation_docnames(
            nav_entries=nav_entries,
            all_files=all_md_files,
            docs_dir=docs_dir,
            project_root=self.project_root,
            generated_targets=gen_targets,
        )

        nav_plan = NavigationPlan(
            root_toctrees=root_toctrees, sub_toctrees={}, hidden_routes=[]
        )

        gen_pipelines_plan: List[GeneratedPipelinePlan] = []
        if generated_doc_proposals:
            first_script = (
                scripts[0]
                if (
                    report.mkdocs_config
                    and "gen-files" in report.mkdocs_config.plugins
                    and scripts
                )
                else None
            )
            gen_pipelines_plan.append(
                GeneratedPipelinePlan(
                    pipeline_id="pipe_gen_files_mkdocstrings",
                    source_plugin="gen-files",
                    generator_script=first_script,
                    target_strategy="AUTODOC_AUTOSUMMARY_STUBS",
                    target_artifacts=[p.target_path for p in generated_doc_proposals],
                    rationale=(
                        f"Automated synthesis of API reference stubs replacing mkdocstrings/gen-files build step. "
                        f"Analyzed generator script '{first_script}': scanned '{script_meta.get('source_dir', 'src')}', "
                        f"output to '{output_prefix}', literate nav: '{script_meta.get('literate_nav', 'reference/SUMMARY.txt')}'."
                    )
                    if first_script
                    else "Automated synthesis of API reference stubs replacing mkdocstrings/gen-files build step.",
                )
            )

        # External Inventory Configuration (e.g. docs.python.org/3 objects.inv)
        external_invs: List[ExternalInventoryConfig] = []
        if report.mkdocs_config and "mkdocstrings" in report.mkdocs_config.plugins:
            mkd_cfg = report.mkdocs_config.plugins_config.get("mkdocstrings", {})
            import_invs = (
                mkd_cfg.get("handlers", {}).get("python", {}).get("import", [])
                if isinstance(mkd_cfg, dict)
                else []
            )
            for inv_url in import_invs:
                if "docs.python.org" in inv_url:
                    base_url = inv_url.rsplit("/objects.inv", 1)[0]
                    external_invs.append(
                        ExternalInventoryConfig(
                            inventory_id="python",
                            url=base_url,
                            objects_inv=inv_url,
                            provenance=RequirementProvenance.EXTENSION_POLICY,
                            rationale="Maps external Python documentation inventory to sphinx.ext.intersphinx.",
                        )
                    )
                    # Ensure intersphinx is added
                    if "sphinx.ext.intersphinx" not in all_ext_names:
                        all_ext_names.append("sphinx.ext.intersphinx")
                    conf_opts.setdefault("intersphinx_mapping", {})["python"] = (
                        base_url,
                        None,
                    )

        # Versioning / Deployment Strategy (e.g. mike)
        versioning_plan: Optional[VersioningDeploymentPlan] = None
        if report.mkdocs_config and "mike" in report.mkdocs_config.plugins:
            mike_cfg = (
                report.mkdocs_config.plugins_config.get("mike", {})
                if isinstance(report.mkdocs_config.plugins_config, dict)
                else {}
            )
            canon_v = mike_cfg.get("canonical_version", "latest")
            versioning_plan = VersioningDeploymentPlan(
                source_tool="mike",
                canonical_version=canon_v,
                target_strategy="SPHINX_VERSIONING_DEPLOYMENT_WORKFLOW",
                status="ACCOUNTED",
                rationale="Separated documentation generation from deployment/versioning. Handled via CI multi-version Sphinx deployment.",
            )

        # Complete System Capability Accountability Audit
        capability_accountability: List[SystemCapabilityAccountability] = []
        if report.mkdocs_config:
            # Theme
            capability_accountability.append(
                SystemCapabilityAccountability(
                    capability_name=report.mkdocs_config.theme_name,
                    source_category="theme",
                    disposition=CapabilityDisposition.TRANSFORM,
                    implementation_strategy=ImplementationStrategy.SPHINX_EXTENSION,
                    verification_status=VerificationStatus.VERIFIED,
                    target_equivalent=theme_proposal.target_theme,
                    rationale=theme_proposal.rationale,
                )
            )
            # Plugins
            for p_name in report.mkdocs_config.plugins:
                if p_name == "autorefs":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.PRESERVE,
                            implementation_strategy=ImplementationStrategy.NATIVE_SPHINX,
                            verification_status=VerificationStatus.NOT_YET_VERIFIED,
                            target_equivalent="sphinx_immaterial / stdlib crossrefs",
                            rationale="Autorefs cross-referencing is natively provided by Sphinx domain references.",
                        )
                    )
                elif p_name == "awesome-pages":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.ACCOUNTED_NO_DIRECT_EQUIVALENT,
                            implementation_strategy=ImplementationStrategy.TOCTREE,
                            verification_status=VerificationStatus.VERIFIED,
                            target_equivalent="NavigationNode graph / toctree",
                            rationale="Effective navigation structure synthesized into Sphinx toctrees; no runtime Sphinx extension needed.",
                        )
                    )
                elif p_name == "gen-files":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.TRANSFORM,
                            implementation_strategy=ImplementationStrategy.AUTODOC_AUTOSUMMARY_STUBS,
                            verification_status=VerificationStatus.VERIFIED,
                            target_equivalent="AUTODOC_AUTOSUMMARY_STUBS",
                            rationale="Transformed build-time generated file pipeline into deterministic API reference stubs.",
                        )
                    )
                elif p_name == "mkdocstrings":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.TRANSFORM,
                            implementation_strategy=ImplementationStrategy.AUTODOC,
                            verification_status=VerificationStatus.VERIFIED,
                            target_equivalent="sphinx.ext.autodoc + sphinx.ext.autosummary",
                            rationale="Migrated mkdocstrings Python handler to Sphinx autodoc/autosummary directives.",
                        )
                    )
                elif p_name == "literate-nav":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.ACCOUNTED_NO_DIRECT_EQUIVALENT,
                            implementation_strategy=ImplementationStrategy.TOCTREE,
                            verification_status=VerificationStatus.VERIFIED,
                            target_equivalent="Sphinx toctrees",
                            rationale="Nav files compiled into deterministic hierarchical toctrees.",
                        )
                    )
                elif p_name == "mike":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.ACCOUNTED_NO_DIRECT_EQUIVALENT,
                            implementation_strategy=ImplementationStrategy.DEPLOYMENT_WORKFLOW,
                            verification_status=VerificationStatus.NOT_YET_VERIFIED,
                            target_equivalent="Sphinx versioning deployment",
                            rationale="Multi-version hosting decoupled from documentation compilation.",
                        )
                    )
                elif p_name == "search":
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.PRESERVE,
                            implementation_strategy=ImplementationStrategy.NATIVE_SPHINX,
                            verification_status=VerificationStatus.VERIFIED,
                            target_equivalent="Sphinx built-in search",
                            rationale="Search is natively built into Sphinx HTML builder.",
                        )
                    )
                else:
                    capability_accountability.append(
                        SystemCapabilityAccountability(
                            capability_name=p_name,
                            source_category="plugin",
                            disposition=CapabilityDisposition.ACCOUNTED_NO_DIRECT_EQUIVALENT,
                            implementation_strategy=ImplementationStrategy.NONE,
                            verification_status=VerificationStatus.NOT_YET_VERIFIED,
                            target_equivalent=None,
                            rationale=f"Evaluated plugin {p_name}.",
                        )
                    )

        documentation_plan = DocumentationPlan(
            pages=doc_plan_artifacts,
            api_strategies=planned_api_strategies,
            navigation=nav_plan,
            generated_pipelines=gen_pipelines_plan,
            cross_references=planned_cross_refs,
            external_inventories=external_invs,
            versioning_deployment=versioning_plan,
            capability_accountability=capability_accountability,
            asset_actions=planned_assets,
            required_extensions=all_ext_names,
            required_packages=[r.name for r in requirements if r.kind == "package"],
            manual_items=manual_items,
            unsupported_items=unsupported_items,
            # Backward compatibility properties
            artifacts=doc_plan_artifacts,
            api_generation_strategy={
                s.object_path: s.directive_kind.value for s in planned_api_strategies
            },
            toctree_hierarchies={"root": resolved_root_toctrees},
            cross_reference_mappings={
                **{c.source_target: c.transformed_target for c in planned_cross_refs},
                **api_reference_mappings,
            },
        )

        ci_plan = plan_ci_workflow(
            ci_analysis=report.ci_analysis,
            dep_analysis=report.dependency_analysis,
            project_root=self.project_root,
        )

        pkgs_to_remove = (
            report.dependency_analysis.detected_packages_to_remove
            if report.dependency_analysis
            else []
        )
        ts = (
            deterministic_timestamp
            if deterministic_timestamp is not None
            else datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        # Planned obsolete files to clean up post-migration (e.g. generator scripts and MkDocs hooks)
        pipe_scripts = [
            pipe.generator_script
            for pipe in gen_pipelines_plan
            if pipe.generator_script
        ]
        planned_obsolete_files = detect_obsolete_generator_scripts(
            project_root=self.project_root,
            mkdocs_config=report.mkdocs_config,
            additional_scripts=pipe_scripts,
        )

        return MigrationPlan(
            project_root=str(self.project_root),
            metadata=MigrationPlanMetadata(generated_at=ts),
            source_mkdocs_config=report.mkdocs_config,
            version_environment=report.version_env,
            navigation_analysis=report.navigation_analysis,
            dependency_analysis=report.dependency_analysis,
            ci_analysis=report.ci_analysis,
            documentation_plan=documentation_plan,
            document_actions=all_actions,
            generated_documents=generated_doc_proposals,
            summary=summary,
            requirements=requirements,
            packages_to_remove=pkgs_to_remove,
            proposed_sphinx_config=sphinx_config_proposal,
            ci_plan=ci_plan,
            manual_action_items=manual_items,
            unsupported_constructs=unsupported_items,
            obsolete_files=planned_obsolete_files,
        )
