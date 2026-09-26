"""Subsystem analyzer for project dependencies and Python version environments."""
from pathlib import Path
from typing import List, Optional
from ..parsing.requirements import parse_pyproject_toml, parse_requirements_txt, NormalizedManifest
from .models import DependencyAnalysis, VersionEnvironment

KNOWN_MKDOCS_PACKAGES = {
    "mkdocs", "mkdocs-material", "mkdocstrings", "mkdocstrings-python",
    "mkdocs-material-extensions", "pymdown-extensions", "mkdocs-mermaid2-plugin",
    "mike", "mkdocs-autorefs", "mkdocs-literate-nav", "mkdocs-macros-plugin"
}

class DependencyAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def analyze(self) -> tuple[Optional[DependencyAnalysis], VersionEnvironment]:
        pyproject = self.project_root / "pyproject.toml"
        docs_req = self.project_root / "docs" / "requirements.txt"
        req = self.project_root / "requirements.txt"

        manifest: Optional[NormalizedManifest] = None
        if pyproject.exists():
            manifest = parse_pyproject_toml(pyproject)
        elif docs_req.exists():
            manifest = parse_requirements_txt(docs_req)
        elif req.exists():
            manifest = parse_requirements_txt(req)

        if not manifest:
            return None, VersionEnvironment()

        to_remove = []
        for dep in manifest.dependencies:
            if dep.name in KNOWN_MKDOCS_PACKAGES:
                to_remove.append(dep.name)

        suggested_to_add = ["sphinx", "myst-parser", "sphinx-design"]
        if "mkdocs-material" in to_remove:
            suggested_to_add.append("sphinx-immaterial")

        dep_analysis = DependencyAnalysis(
            manifest_type=manifest.manifest_type,
            detected_packages_to_remove=sorted(list(set(to_remove))),
            suggested_packages_to_add=suggested_to_add
        )

        mkdocs_ver = None
        for dep in manifest.dependencies:
            if dep.name == "mkdocs":
                mkdocs_ver = dep.raw_spec

        version_env = VersionEnvironment(
            python_version=manifest.python_requirement,
            detected_mkdocs_version=mkdocs_ver
        )

        return dep_analysis, version_env
