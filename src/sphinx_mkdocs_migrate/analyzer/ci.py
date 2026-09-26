"""Subsystem analyzer for CI/CD and deployment workflows."""
from pathlib import Path
from typing import Optional
from .models import CIAnalysis

class CIAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def analyze(self) -> CIAnalysis:
        github_workflows = self.project_root / ".github" / "workflows"
        rtd_config = self.project_root / ".readthedocs.yaml"
        if not rtd_config.exists():
            rtd_config = self.project_root / ".readthedocs.yml"

        workflow_files = []
        has_deploy = False
        ci_system = None

        if github_workflows.exists():
            ci_system = "github_actions"
            for yml_file in github_workflows.glob("*.y*ml"):
                rel = str(yml_file.relative_to(self.project_root))
                workflow_files.append(rel)
                try:
                    content = yml_file.read_text(encoding="utf-8")
                    if "mkdocs gh-deploy" in content or "mkdocs build" in content:
                        has_deploy = True
                except Exception:
                    pass

        has_rtd = rtd_config.exists()
        if has_rtd and not ci_system:
            ci_system = "readthedocs"

        return CIAnalysis(
            ci_system=ci_system,
            workflow_files=workflow_files,
            has_mkdocs_deploy=has_deploy,
            readthedocs_detected=has_rtd
        )
