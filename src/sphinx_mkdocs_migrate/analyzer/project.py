"""Project-level orchestration analyzer."""
from pathlib import Path
from typing import List
from .mkdocs import MkDocsConfigAnalyzer
from .dependencies import DependencyAnalyzer
from .navigation import NavigationAnalyzer
from .ci import CIAnalyzer
from .markdown import MarkdownAnalyzer
from ..parsing.markdown import MarkdownParser
from .models import ProjectAnalysisReport, SubsystemSummary, ConstructFinding, Classification

class ProjectAnalyzer:
    """Orchestrates comprehensive factual inspection across all documentation subsystems."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_analyzer = MkDocsConfigAnalyzer(project_root)
        self.dep_analyzer = DependencyAnalyzer(project_root)
        self.nav_analyzer = NavigationAnalyzer(project_root)
        self.ci_analyzer = CIAnalyzer(project_root)
        self.markdown_analyzer = MarkdownAnalyzer(project_root)
        self.markdown_parser = self.markdown_analyzer.parser

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
            # Fallback: scan root .md files
            md_files = sorted(list(self.project_root.glob("*.md")))

        # Navigation Analysis
        nav = self.nav_analyzer.analyze(config.nav_raw, md_files, docs_dir)

        # Markdown AST Construct Scanning
        findings: List[ConstructFinding] = []
        for md_file in md_files:
            file_findings = self.markdown_analyzer.analyze_file(md_file)
            findings.extend(file_findings)

        # Build Subsystem Summaries
        summaries: List[SubsystemSummary] = []

        # 1. Markdown Content
        transform_cnt = sum(1 for f in findings if f.classification == Classification.TRANSFORM)
        summaries.append(SubsystemSummary(
            name="Markdown Content",
            status="AUTOMATIC" if transform_cnt > 0 else "PRESERVED",
            details=f"{len(md_files)} files, {transform_cnt} construct transformations identified"
        ))

        # 2. Navigation
        if nav.has_nav:
            nav_status = "AUTOMATIC" if not nav.missing_references else "REVIEW"
            summaries.append(SubsystemSummary(
                name="Navigation (nav)",
                status=nav_status,
                details=f"{nav.total_nav_entries} entries, depth {nav.max_depth}"
            ))

        # 3. Dependencies
        if deps and deps.manifest_type:
            summaries.append(SubsystemSummary(
                name="Dependencies",
                status="REVIEW",
                details=f"{len(deps.detected_packages_to_remove)} packages to remove, {len(deps.suggested_packages_to_add)} to add"
            ))

        # 4. CI/CD
        if ci.ci_system:
            summaries.append(SubsystemSummary(
                name="CI/CD & Hosting",
                status="REVIEW",
                details=f"{ci.ci_system} ({len(ci.workflow_files)} workflows)"
            ))

        manual_items: List[str] = []
        for f in findings:
            if f.classification == Classification.MANUAL:
                manual_items.append(f"{f.file_path}:{f.line_number} ({f.construct_type}) - Manual review required")

        return ProjectAnalysisReport(
            project_root=str(self.project_root),
            mkdocs_config=config,
            dependency_analysis=deps,
            navigation_analysis=nav,
            ci_analysis=ci,
            total_markdown_files=len(md_files),
            construct_findings=findings,
            subsystem_summaries=summaries,
            manual_action_items=manual_items
        )
