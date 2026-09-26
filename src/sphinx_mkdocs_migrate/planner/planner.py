"""Migration Planner synthesizing findings, declarative rules, policy engine, and provenance into a deterministic MigrationPlan."""
import hashlib
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from ..analyzer.models import (
    ProjectAnalysisReport,
    Classification,
    SubsystemSummary
)
from .models import (
    MigrationPlan,
    MigrationPlanMetadata,
    PlanActionSummary,
    RequirementProvenance,
    RequirementItem,
    ThemeMigrationProposal,
    ConfigMigrationProposal,
    ManualReviewItem
)
from .policy import (
    PolicyEngine,
    FeaturePolicyRule,
    SourceFeatureCategory
)
from ..analyzer.project import ProjectAnalyzer
from ..rules.engine import MigrationRuleEngine
from ..rules.models import MigrationAction
from ..parsing.markdown import MarkdownParser
from ..parsing.markdown_ir import DocumentIR

class MigrationPlanner:
    """Orchestrates deterministic planning from ProjectAnalysisReport, FeaturePolicyCatalog, and MigrationRuleEngine."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.analyzer = ProjectAnalyzer(project_root)
        self.parser = MarkdownParser()
        self.rule_engine = MigrationRuleEngine()
        self.policy_engine = PolicyEngine()

    def create_plan(self, deterministic_timestamp: Optional[str] = None) -> MigrationPlan:
        """Generates a canonical, read-only MigrationPlan without mutating repository files."""
        # 1. Analyze repository subsystems
        report = self.analyzer.analyze()

        # 2. Extract DocumentIRs and evaluate declarative rules per file
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

        docs_dir_name = report.mkdocs_config.docs_dir if report.mkdocs_config else "docs"
        docs_dir = self.project_root / docs_dir_name
        md_files = sorted(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else []

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
                manual_items.append(ManualReviewItem(
                    item_id=f"manual_{action.action_id}",
                    source_file=action.source_file,
                    line_number=action.start_line,
                    construct_type=action.source_kind.value,
                    instruction=action.manual_instruction or "Manual review required.",
                    rationale=action.description
                ))
            elif action.classification == Classification.UNSUPPORTED:
                summary.unsupported_count += 1
                unsupported_items.append(action)

            # Map extensions & packages from construct actions
            for ext in action.required_extensions:
                ext_sources.setdefault(ext, []).append(loc_str)
                provenance_map[ext] = RequirementProvenance.DOCUMENT_CONSTRUCT
                rationale_map[ext] = f"Required by document construct(s) in project Markdown files."
            for pkg in action.required_packages:
                pkg_sources.setdefault(pkg, []).append(loc_str)
                provenance_map[pkg] = RequirementProvenance.DOCUMENT_CONSTRUCT
                rationale_map[pkg] = f"Required by document construct(s) in project Markdown files."

        # 4. Explicit Theme Migration Policy
        source_theme = report.mkdocs_config.theme_name if report.mkdocs_config else "mkdocs"
        if "material" in source_theme:
            theme_proposal = ThemeMigrationProposal(
                source_theme=source_theme,
                target_theme="furo",
                target_package="furo>=2024.1.0",
                classification=Classification.TRANSFORM,
                rationale="Source uses Material for MkDocs; maps directly to modern Furo theme for full Sphinx 8/9 compatibility."
            )
            pkg_sources.setdefault("furo>=2024.1.0", []).append("theme_policy:material")
            provenance_map["furo>=2024.1.0"] = RequirementProvenance.THEME_POLICY
            rationale_map["furo>=2024.1.0"] = theme_proposal.rationale
        elif source_theme in ("readthedocs", "mkdocs"):
            theme_proposal = ThemeMigrationProposal(
                source_theme=source_theme,
                target_theme="sphinx_rtd_theme",
                target_package="sphinx-rtd-theme>=2.0.0",
                classification=Classification.TRANSFORM,
                rationale=f"Source uses standard '{source_theme}'; maps to sphinx_rtd_theme."
            )
            pkg_sources.setdefault("sphinx-rtd-theme>=2.0.0", []).append(f"theme_policy:{source_theme}")
            provenance_map["sphinx-rtd-theme>=2.0.0"] = RequirementProvenance.THEME_POLICY
            rationale_map["sphinx-rtd-theme>=2.0.0"] = theme_proposal.rationale
        else:
            # Custom or unrecognized theme requires MANUAL decision
            theme_proposal = ThemeMigrationProposal(
                source_theme=source_theme,
                target_theme=None,
                target_package=None,
                classification=Classification.MANUAL,
                rationale=f"Custom/unrecognized theme '{source_theme}' has no automated Sphinx equivalent. Manual theme selection required."
            )
            manual_items.append(ManualReviewItem(
                item_id="manual_theme_selection",
                source_file="mkdocs.yml",
                line_number=1,
                construct_type="theme",
                instruction=f"Select an appropriate Sphinx theme (e.g. Furo, PyData Sphinx Theme, or sphinx-rtd-theme) for '{source_theme}'.",
                rationale=theme_proposal.rationale
            ))

        # 5. Declarative Policy Evaluation for Theme Features, Extensions, and Plugins
        myst_enabled: Set[str] = {"colon_fence"}
        custom_conf_options: Dict[str, Any] = {}

        if report.mkdocs_config:
            # 5a. Theme Features
            for feat in (report.mkdocs_config.theme_features or []):
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
                        manual_items.append(ManualReviewItem(
                            item_id=f"manual_feat_{feat.replace('.', '_')}",
                            source_file="mkdocs.yml",
                            line_number=1,
                            construct_type="theme_feature",
                            instruction=rule.manual_instruction or "Manual review required.",
                            rationale=rule.rationale
                        ))

            # 5b. Markdown Extensions
            for ext_entry in (report.mkdocs_config.markdown_extensions or []):
                ext_name = ext_entry if isinstance(ext_entry, str) else getattr(ext_entry, 'name', str(ext_entry))
                rule = self.policy_engine.evaluate_feature(ext_name)
                if rule:
                    for ext in rule.required_extensions:
                        ext_sources.setdefault(ext, []).append(f"markdown_extension:{ext_name}")
                        provenance_map.setdefault(ext, RequirementProvenance.EXTENSION_POLICY)
                        rationale_map.setdefault(ext, rule.rationale)
                    for pkg in rule.required_packages:
                        pkg_sources.setdefault(pkg, []).append(f"markdown_extension:{ext_name}")
                        provenance_map.setdefault(pkg, RequirementProvenance.EXTENSION_POLICY)
                        rationale_map.setdefault(pkg, rule.rationale)
                    for m_ext in rule.myst_extensions:
                        myst_enabled.add(m_ext)
                    if rule.conf_settings:
                        custom_conf_options.update(rule.conf_settings)
                    if rule.classification == Classification.MANUAL:
                        manual_items.append(ManualReviewItem(
                            item_id=f"manual_ext_{ext_name.replace('.', '_')}",
                            source_file="mkdocs.yml",
                            line_number=1,
                            construct_type="markdown_extension",
                            instruction=rule.manual_instruction or "Manual review required.",
                            rationale=rule.rationale
                        ))

            # 5c. Plugins
            for plg_entry in (report.mkdocs_config.plugins or []):
                plg_name = plg_entry if isinstance(plg_entry, str) else getattr(plg_entry, 'name', str(plg_entry))
                rule = self.policy_engine.evaluate_feature(plg_name)
                if rule:
                    for ext in rule.required_extensions:
                        ext_sources.setdefault(ext, []).append(f"plugin:{plg_name}")
                        provenance_map.setdefault(ext, RequirementProvenance.EXTENSION_POLICY)
                        rationale_map.setdefault(ext, rule.rationale)
                    for pkg in rule.required_packages:
                        pkg_sources.setdefault(pkg, []).append(f"plugin:{plg_name}")
                        provenance_map.setdefault(pkg, RequirementProvenance.EXTENSION_POLICY)
                        rationale_map.setdefault(pkg, rule.rationale)
                    for m_ext in rule.myst_extensions:
                        myst_enabled.add(m_ext)
                    if rule.conf_settings:
                        custom_conf_options.update(rule.conf_settings)
                    if rule.classification == Classification.MANUAL:
                        manual_items.append(ManualReviewItem(
                            item_id=f"manual_plugin_{plg_name.replace('.', '_')}",
                            source_file="mkdocs.yml",
                            line_number=1,
                            construct_type="plugin",
                            instruction=rule.manual_instruction or "Manual review required.",
                            rationale=rule.rationale
                        ))

        # Check in-document detected extensions
        if "tasklist" in detected_markdown_extensions:
            myst_enabled.add("tasklist")
        if "attrs_block" in detected_markdown_extensions:
            myst_enabled.add("attrs_block")

        # 6. Build Traceable RequirementItems
        requirements: List[RequirementItem] = []
        
        # Target Baseline
        requirements.append(RequirementItem(
            name="Sphinx>=7.0.0",
            kind="package",
            provenance=RequirementProvenance.TARGET_BASELINE,
            rationale="Core target documentation engine.",
            sources=["target_baseline"]
        ))
        requirements.append(RequirementItem(
            name="myst-parser>=2.0.0",
            kind="package",
            provenance=RequirementProvenance.TARGET_BASELINE,
            rationale="Required for CommonMark and MyST Markdown parsing in Sphinx.",
            sources=["target_baseline"]
        ))
        requirements.append(RequirementItem(
            name="myst_parser",
            kind="extension",
            provenance=RequirementProvenance.TARGET_BASELINE,
            rationale="Sphinx extension for MyST Parser.",
            sources=["target_baseline"]
        ))

        # Theme Package Requirement
        if theme_proposal.target_package:
            requirements.append(RequirementItem(
                name=theme_proposal.target_package,
                kind="package",
                provenance=RequirementProvenance.THEME_POLICY,
                rationale=theme_proposal.rationale,
                sources=pkg_sources.get(theme_proposal.target_package, [f"theme_policy:{source_theme}"])
            ))

        # Extensions & Packages with Traceable Provenance
        for ext, sources in sorted(ext_sources.items()):
            if ext != "myst_parser":
                requirements.append(RequirementItem(
                    name=ext,
                    kind="extension",
                    provenance=provenance_map.get(ext, RequirementProvenance.DOCUMENT_CONSTRUCT),
                    rationale=rationale_map.get(ext, f"Required by {len(sources)} source item(s)."),
                    sources=sources
                ))

        for pkg, sources in sorted(pkg_sources.items()):
            if pkg not in ("Sphinx>=7.0.0", "myst-parser>=2.0.0", theme_proposal.target_package):
                requirements.append(RequirementItem(
                    name=pkg,
                    kind="package",
                    provenance=provenance_map.get(pkg, RequirementProvenance.DOCUMENT_CONSTRUCT),
                    rationale=rationale_map.get(pkg, f"Required by {len(sources)} source item(s)."),
                    sources=sources
                ))

        site_name = report.mkdocs_config.site_name if report.mkdocs_config else "Documentation"
        all_ext_names = sorted(list({r.name for r in requirements if r.kind == "extension"}))

        conf_opts = {
            "project": site_name,
            "html_theme": theme_proposal.target_theme or "sphinx_rtd_theme"
        }
        conf_opts.update(custom_conf_options)

        sphinx_config_proposal = ConfigMigrationProposal(
            project_name=site_name,
            theme=theme_proposal,
            extensions_to_add=all_ext_names,
            myst_enable_extensions=sorted(list(myst_enabled)),
            custom_options=conf_opts,
            rationale={
                "extensions": f"Derived from declarative policy engine across document actions, plugins, and theme features.",
                "myst_syntax": f"Derived from MkDocs extensions config and document syntax ({', '.join(sorted(list(myst_enabled)))})."
            }
        )

        pkgs_to_remove = report.dependency_analysis.detected_packages_to_remove if report.dependency_analysis else []
        ts = deterministic_timestamp if deterministic_timestamp is not None else datetime.datetime.now(datetime.timezone.utc).isoformat()

        return MigrationPlan(
            project_root=str(self.project_root),
            metadata=MigrationPlanMetadata(generated_at=ts),
            source_mkdocs_config=report.mkdocs_config,
            version_environment=report.version_env,
            navigation_analysis=report.navigation_analysis,
            dependency_analysis=report.dependency_analysis,
            ci_analysis=report.ci_analysis,
            document_actions=all_actions,
            summary=summary,
            requirements=requirements,
            packages_to_remove=pkgs_to_remove,
            proposed_sphinx_config=sphinx_config_proposal,
            manual_action_items=manual_items,
            unsupported_constructs=unsupported_items
        )
