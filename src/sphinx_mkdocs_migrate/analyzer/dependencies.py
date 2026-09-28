from pathlib import Path
from typing import List, Optional, Dict
import importlib.metadata
from ..parsing.requirements import parse_pyproject_toml, parse_requirements_txt, NormalizedManifest
from .models import DependencyAnalysis, VersionEnvironment, PackageVersionInfo

KNOWN_MKDOCS_PACKAGES = {
    "mkdocs", "mkdocs-material", "mkdocstrings", "mkdocstrings-python",
    "mkdocs-material-extensions", "pymdown-extensions", "mkdocs-mermaid2-plugin",
    "mike", "mkdocs-autorefs", "mkdocs-literate-nav", "mkdocs-macros-plugin",
    "mdx_truly_sane_lists", "mkdocs-awesome-pages-plugin", "mkdocs-gen-files"
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

        packages_info: Dict[str, PackageVersionInfo] = {}
        plugin_vers: Dict[str, str] = {}
        mkdocs_ver = None

        import sys
        current_py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        for dep in manifest.dependencies:
            if dep.name == "mkdocs" or dep.name in KNOWN_MKDOCS_PACKAGES:
                # Check if installed in active environment
                installed_ver = None
                status = "DECLARED_ONLY"
                res_source = "MANIFEST_DECLARATION"
                satisfies_constraint = None

                try:
                    installed_ver = importlib.metadata.version(dep.name)
                    status = "INSTALLED_RESOLVED"
                    res_source = "CURRENT_PYTHON_ENVIRONMENT"
                    # Basic constraint check if `>=` specified
                    if ">=" in dep.raw_spec:
                        req_ver = dep.raw_spec.split(">=")[-1].strip()
                        satisfies_constraint = (installed_ver >= req_ver)
                    else:
                        satisfies_constraint = True
                except Exception:
                    pass

                pkg_info = PackageVersionInfo(
                    package_name=dep.name,
                    declared_spec=dep.raw_spec,
                    resolved_version=installed_ver,
                    resolution_status=status,
                    resolution_source=res_source,
                    satisfies_declared_constraint=satisfies_constraint
                )
                packages_info[dep.name] = pkg_info

                if dep.name == "mkdocs":
                    mkdocs_ver = dep.raw_spec
                else:
                    plugin_vers[dep.name] = dep.raw_spec

        version_env = VersionEnvironment(
            python_version=manifest.python_requirement,
            python_constraint=manifest.python_requirement,
            python_resolved_version=current_py_ver,
            python_resolution_status="INSTALLED_RESOLVED",
            packages=packages_info,
            detected_mkdocs_version=mkdocs_ver,
            detected_plugin_versions=plugin_vers
        )

        return dep_analysis, version_env
