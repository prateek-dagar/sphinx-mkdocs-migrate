"""Project-level orchestration analyzer producing complete, effective MigrationAnalysis."""

import ast
from pathlib import Path
from typing import List, Dict, Any, Optional

from .mkdocs import MkDocsConfigAnalyzer
from .dependencies import DependencyAnalyzer
from .navigation import NavigationAnalyzer
from .ci import CIAnalyzer
from .markdown import MarkdownAnalyzer
from ..parsing.flow_extractor import DocumentFlowExtractor
from ..parsing.doc_ir import (
    DocumentationSiteGraph,
    DocumentationPage,
    NavigationNode,
    DocumentFlowSpec,
    ApiDocumentationRequest,
    DocumentElementType,
)
from .models import (
    ProjectAnalysisReport,
    SubsystemSummary,
    ConstructFinding,
    Classification,
    ResolvedEffectiveConfig,
    ResolvedProperty,
    PropertyResolutionState,
    ResolutionProvenance,
    ResolvedApiModule,
    ResolvedApiSymbol,
    ResolvedCapabilityItem,
    ResolvedUnresolvedItem,
    MigrationRequirement,
    RequirementCategory,
    RequirementDisposition,
)


class ProjectAnalyzer:
    """Orchestrates comprehensive factual inspection, effective configuration, and migration requirement derivation."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_analyzer = MkDocsConfigAnalyzer(project_root)
        self.dep_analyzer = DependencyAnalyzer(project_root)
        self.nav_analyzer = NavigationAnalyzer(project_root)
        self.ci_analyzer = CIAnalyzer(project_root)
        self.markdown_analyzer = MarkdownAnalyzer(project_root)
        self.markdown_parser = self.markdown_analyzer.parser
        self.flow_extractor = DocumentFlowExtractor()

    def analyze(self) -> ProjectAnalysisReport:
        config = self.config_analyzer.analyze()
        deps, version_env = self.dep_analyzer.analyze()
        ci = self.ci_analyzer.analyze()

        # If project has no mkdocs.yml, fallback site_name from folder name
        if not config.site_name:
            config.site_name = self.project_root.name.replace("-", " ").title()

        # Discover all Markdown files in docs_dir
        docs_dir = self.project_root / config.docs_dir
        md_files: List[Path] = []
        if docs_dir.exists() and docs_dir.is_dir():
            md_files = sorted(list(docs_dir.rglob("*.md")))
        elif (self.project_root / "docs").exists():
            md_files = sorted(list((self.project_root / "docs").rglob("*.md")))
        else:
            md_files = sorted(list(self.project_root.glob("*.md")))

        # Navigation Analysis
        nav = self.nav_analyzer.analyze(config.nav_raw, md_files, docs_dir)

        # Markdown AST Construct Scanning
        findings: List[ConstructFinding] = []
        for md_file in md_files:
            file_findings = self.markdown_analyzer.analyze_file(md_file)
            findings.extend(file_findings)

        # 1. Effective Config Resolution
        effective_cfg = self._resolve_effective_config(config)

        # 2. Extract DocumentFlows in exact authored sequence
        flows: Dict[str, DocumentFlowSpec] = {}
        api_requests: List[ApiDocumentationRequest] = []
        site_pages: Dict[str, DocumentationPage] = {}

        md_exts = [
            ext if isinstance(ext, str) else getattr(ext, "name", str(ext))
            for ext in (config.markdown_extensions or [])
        ]
        self.flow_extractor.mkdocs_config = {"markdown_extensions": md_exts}

        for md_file in md_files:
            rel_path = str(md_file.relative_to(self.project_root))
            page = self.flow_extractor.extract_from_file(md_file, rel_path=rel_path)
            flows[rel_path] = page.flow

            for elem in page.flow.elements:
                if elem.element_type == DocumentElementType.API_REQUEST and isinstance(
                    elem.content, ApiDocumentationRequest
                ):
                    api_requests.append(elem.content)

            logical_route = (
                str(md_file.relative_to(docs_dir).with_suffix(""))
                if md_file.is_relative_to(docs_dir)
                else md_file.stem
            )
            site_pages[logical_route] = page

        # 3. Resolve API Objects (Symbol extraction from Python AST)
        resolved_modules = self._resolve_api_symbols(api_requests)

        # 4. Construct Site Graph
        nav_node = None
        if nav and nav.has_nav:
            nav_node = self._build_nav_node(nav.tree)

        site_graph = DocumentationSiteGraph(pages=site_pages, navigation=nav_node)

        # 5. Extract Capabilities and Unresolved Items
        capabilities, unresolved = self._resolve_capabilities(config)

        # 6. Derive Migration Requirements
        requirements = self._derive_migration_requirements(
            config, flows, api_requests, resolved_modules, capabilities
        )

        # 7. Subsystem Summaries
        summaries: List[SubsystemSummary] = []
        transform_cnt = sum(
            1 for f in findings if f.classification == Classification.TRANSFORM
        )
        summaries.append(
            SubsystemSummary(
                name="Markdown Content",
                status="AUTOMATIC" if transform_cnt > 0 else "PRESERVED",
                details=f"{len(md_files)} files, {transform_cnt} construct transformations identified",
            )
        )

        if nav.has_nav:
            nav_status = "AUTOMATIC" if not nav.missing_references else "REVIEW"
            summaries.append(
                SubsystemSummary(
                    name="Navigation (nav)",
                    status=nav_status,
                    details=f"{nav.total_nav_entries} entries, depth {nav.max_depth}",
                )
            )

        if deps and deps.manifest_type:
            summaries.append(
                SubsystemSummary(
                    name="Dependencies",
                    status="REVIEW",
                    details=f"{len(deps.detected_packages_to_remove)} packages to remove, {len(deps.suggested_packages_to_add)} to add",
                )
            )

        if ci.ci_system:
            summaries.append(
                SubsystemSummary(
                    name="CI/CD & Hosting",
                    status="REVIEW",
                    details=f"{ci.ci_system} ({len(ci.workflow_files)} workflows)",
                )
            )

        manual_items: List[str] = []
        for f in findings:
            if f.classification == Classification.MANUAL:
                manual_items.append(
                    f"{f.file_path}:{f.line_number} ({f.construct_type}) - Manual review required"
                )

        return ProjectAnalysisReport(
            project_root=str(self.project_root),
            mkdocs_config=config,
            effective_config=effective_cfg,
            version_env=version_env,
            dependency_analysis=deps,
            navigation_analysis=nav,
            ci_analysis=ci,
            total_markdown_files=len(md_files),
            construct_findings=findings,
            document_flows=flows,
            documentation_site_graph=site_graph,
            build_graph=None,
            api_requests=api_requests,
            resolved_api_modules=resolved_modules,
            capabilities=capabilities,
            migration_requirements=requirements,
            unresolved_items=unresolved,
            subsystem_summaries=summaries,
            manual_action_items=manual_items,
        )

    def _resolve_effective_config(self, cfg) -> ResolvedEffectiveConfig:
        props: Dict[str, ResolvedProperty] = {}
        if cfg:
            raw_keys = set(getattr(cfg, "raw_config_keys", []))

            # 1. Theme Name
            theme_configured = "theme" in raw_keys and cfg.theme_name is not None
            props["theme.name"] = ResolvedProperty(
                key="theme.name",
                configured_value=cfg.theme_name if theme_configured else None,
                default_value="mkdocs",
                effective_value=cfg.theme_name or "mkdocs",
                state=PropertyResolutionState.CONFIGURED
                if theme_configured
                else PropertyResolutionState.DEFAULTED,
                provenance=ResolutionProvenance(
                    source_type="mkdocs.yml" if theme_configured else "mkdocs_default"
                ),
            )

            # 2. Docs Dir
            docs_dir_configured = "docs_dir" in raw_keys
            props["docs_dir"] = ResolvedProperty(
                key="docs_dir",
                configured_value=cfg.docs_dir if docs_dir_configured else None,
                default_value="docs",
                effective_value=cfg.docs_dir or "docs",
                state=PropertyResolutionState.CONFIGURED
                if docs_dir_configured
                else PropertyResolutionState.DEFAULTED,
                provenance=ResolutionProvenance(
                    source_type="mkdocs.yml"
                    if docs_dir_configured
                    else "mkdocs_default"
                ),
            )

            # 3. Site Name & Metadata
            site_name_configured = "site_name" in raw_keys
            props["site_name"] = ResolvedProperty(
                key="site_name",
                configured_value=cfg.site_name if site_name_configured else None,
                default_value=None,
                effective_value=cfg.site_name,
                state=PropertyResolutionState.CONFIGURED
                if site_name_configured
                else PropertyResolutionState.DEFAULTED,
                provenance=ResolutionProvenance(
                    source_type="mkdocs.yml" if site_name_configured else "derived"
                ),
            )

            if cfg.site_url:
                props["site_url"] = ResolvedProperty(
                    key="site_url",
                    configured_value=cfg.site_url,
                    default_value=None,
                    effective_value=cfg.site_url,
                    state=PropertyResolutionState.CONFIGURED,
                    provenance=ResolutionProvenance(source_type="mkdocs.yml"),
                )

            if cfg.repo_url:
                props["repo_url"] = ResolvedProperty(
                    key="repo_url",
                    configured_value=cfg.repo_url,
                    default_value=None,
                    effective_value=cfg.repo_url,
                    state=PropertyResolutionState.CONFIGURED,
                    provenance=ResolutionProvenance(source_type="mkdocs.yml"),
                )

            # 4. Theme Features
            for feat in cfg.theme_features:
                props[f"theme.features.{feat}"] = ResolvedProperty(
                    key=f"theme.features.{feat}",
                    configured_value=True,
                    default_value=False,
                    effective_value=True,
                    state=PropertyResolutionState.CONFIGURED,
                    provenance=ResolutionProvenance(
                        source_type="mkdocs.yml", source_location="theme.features"
                    ),
                )

            # 5. Theme Palette
            if cfg.theme_palette:
                props["theme.palette"] = ResolvedProperty(
                    key="theme.palette",
                    configured_value=[p.model_dump() for p in cfg.theme_palette],
                    default_value=[],
                    effective_value=[p.model_dump() for p in cfg.theme_palette],
                    state=PropertyResolutionState.CONFIGURED,
                    provenance=ResolutionProvenance(
                        source_type="mkdocs.yml", source_location="theme.palette"
                    ),
                )

            # 6. Theme Icon & Logo
            if cfg.theme_icon:
                props["theme.icon"] = ResolvedProperty(
                    key="theme.icon",
                    configured_value=cfg.theme_icon,
                    default_value=None,
                    effective_value=cfg.theme_icon,
                    state=PropertyResolutionState.CONFIGURED,
                    provenance=ResolutionProvenance(
                        source_type="mkdocs.yml", source_location="theme.icon"
                    ),
                )

        return ResolvedEffectiveConfig(properties=props)

    def _resolve_api_symbols(
        self, requests: List[ApiDocumentationRequest]
    ) -> Dict[str, ResolvedApiModule]:
        modules: Dict[str, ResolvedApiModule] = {}
        for req in requests:
            mod_path = req.object_path
            src_file = self._find_module_source_file(mod_path)
            symbols = self._extract_symbols_from_ast(src_file) if src_file else {}
            modules[mod_path] = ResolvedApiModule(
                module_path=mod_path,
                symbols=symbols,
                summary_mode=req.summary_mode.value,
                explicit_members=req.explicit_members,
            )
        return modules

    def _find_module_source_file(self, module_path: str) -> Optional[Path]:
        parts = module_path.split(".")
        candidates = [
            self.project_root
            / "src"
            / "/".join(parts).replace("/", Path("/").name + ".py"),
            self.project_root / "/".join(parts).replace("/", Path("/").name + ".py"),
            self.project_root / "src" / Path(*parts).with_suffix(".py"),
            self.project_root / Path(*parts).with_suffix(".py"),
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return None

    def _extract_symbols_from_ast(
        self, file_path: Path
    ) -> Dict[str, ResolvedApiSymbol]:
        symbols: Dict[str, ResolvedApiSymbol] = {}
        try:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8"), filename=str(file_path)
            )
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Extract formatted signature from arguments
                    args = [a.arg for a in node.args.args]
                    sig = f"{node.name}({', '.join(args)})"
                    symbols[node.name] = ResolvedApiSymbol(
                        fully_qualified_name=node.name,
                        symbol_kind="function",
                        signature=sig,
                        docstring=ast.get_docstring(node),
                        source_file=str(file_path),
                        source_line=node.lineno,
                    )
                elif isinstance(node, ast.ClassDef):
                    method_names = [
                        n.name
                        for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    symbols[node.name] = ResolvedApiSymbol(
                        fully_qualified_name=node.name,
                        symbol_kind="class",
                        signature=f"class {node.name}",
                        docstring=ast.get_docstring(node),
                        source_file=str(file_path),
                        source_line=node.lineno,
                        member_names=method_names,
                    )
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            symbols[target.id] = ResolvedApiSymbol(
                                fully_qualified_name=target.id,
                                symbol_kind="attribute",
                                signature=target.id,
                                docstring=None,
                                source_file=str(file_path),
                                source_line=node.lineno,
                            )
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        symbols[node.target.id] = ResolvedApiSymbol(
                            fully_qualified_name=node.target.id,
                            symbol_kind="attribute",
                            signature=node.target.id,
                            docstring=None,
                            source_file=str(file_path),
                            source_line=node.lineno,
                        )
        except Exception:
            pass
        return symbols

    def _build_nav_node(self, items: List[Any]) -> Optional[NavigationNode]:
        if not items:
            return None
        root = NavigationNode(construct_id="nav_root", label="Root")
        for i, item in enumerate(items):
            child = NavigationNode(
                construct_id=f"nav_node_{i}",
                label=getattr(item, "title", "Page"),
                page_route=getattr(item, "path", None),
            )
            root.children.append(child)
        return root

    def _resolve_capabilities(
        self, cfg
    ) -> tuple[List[ResolvedCapabilityItem], List[ResolvedUnresolvedItem]]:
        caps: List[ResolvedCapabilityItem] = []
        unresolved: List[ResolvedUnresolvedItem] = []

        if cfg:
            for p in cfg.plugins:
                p_name = (
                    p
                    if isinstance(p, str)
                    else list(p.keys())[0]
                    if isinstance(p, dict)
                    else str(p)
                )
                if p_name in ("search", "mkdocstrings", "autorefs"):
                    caps.append(
                        ResolvedCapabilityItem(
                            capability_name=f"plugin:{p_name}",
                            source_feature=p_name,
                            state=PropertyResolutionState.CONFIGURED,
                            target_strategy="SPHINX_EXTENSION_MAPPING",
                        )
                    )
                else:
                    unresolved.append(
                        ResolvedUnresolvedItem(
                            item_id=f"plugin:{p_name}",
                            category="plugin_option",
                            rationale=f"Third-party plugin '{p_name}' requires explicit capability policy mapping.",
                        )
                    )
        return caps, unresolved

    def _derive_migration_requirements(
        self,
        cfg,
        flows: Dict[str, DocumentFlowSpec],
        api_requests: List[ApiDocumentationRequest],
        resolved_modules: Dict[str, ResolvedApiModule],
        capabilities: List[ResolvedCapabilityItem],
    ) -> List[MigrationRequirement]:
        reqs: List[MigrationRequirement] = []

        # 1. Document Flow Authored-Sequence Requirement
        for file_path, flow in flows.items():
            reqs.append(
                MigrationRequirement(
                    requirement_id=f"flow:{file_path}",
                    category=RequirementCategory.FLOW,
                    disposition=RequirementDisposition.PRESERVE,
                    source_construct=f"DocumentFlow({file_path})",
                    required_outcome="PRESERVE_AUTHORED_ELEMENT_SEQUENCE",
                    rationale="Preserve exact authored element ordering (prose before API summary/members).",
                    provenance_location=file_path,
                )
            )

        # 2. 1:1 API Symbol Parity Requirement
        for mod_path, mod_obj in resolved_modules.items():
            reqs.append(
                MigrationRequirement(
                    requirement_id=f"api:{mod_path}",
                    category=RequirementCategory.API,
                    disposition=RequirementDisposition.TRANSFORM,
                    source_construct=f"ApiModule({mod_path})",
                    required_outcome="PRESERVE_API_MODULE_DOCUMENTATION",
                    rationale=f"Represent all {len(mod_obj.symbols)} resolved symbols with 1:1 API identity.",
                    provenance_location=mod_path,
                )
            )

        # 3. Theme Features Requirements
        if cfg:
            for feat in cfg.theme_features:
                disposition = (
                    RequirementDisposition.ACCOUNT_NO_DIRECT_EQUIVALENT
                    if feat in ("navigation.instant", "navigation.top", "toc.follow")
                    else RequirementDisposition.TRANSFORM
                )
                reqs.append(
                    MigrationRequirement(
                        requirement_id=f"theme_feature:{feat}",
                        category=RequirementCategory.THEME_FEATURE,
                        disposition=disposition,
                        source_construct=f"theme.features.{feat}",
                        required_outcome="REALIZE_THEME_BEHAVIOR",
                        rationale=f"Realize theme feature {feat} via equivalent theme mechanism or account as chrome-only.",
                        provenance_location="mkdocs.yml:theme.features",
                    )
                )

        return reqs
