"""Structured manifest and dependency parsing."""
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

class NormalizedDependency(BaseModel):
    name: str
    raw_spec: str
    source_location: str  # e.g., "project.dependencies", "dependency-groups.docs", "requirements.txt"

class NormalizedManifest(BaseModel):
    manifest_type: str  # "pyproject.toml", "requirements.txt"
    manifest_path: str
    python_requirement: Optional[str] = None
    dependencies: List[NormalizedDependency] = Field(default_factory=list)

def _normalize_package_name(spec: str) -> Tuple[str, str]:
    clean = spec.strip()
    match = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[[^\]]+\])?", clean)
    name = match.group(1).lower().replace("_", "-") if match else clean.lower()
    return name, clean

def parse_pyproject_toml(pyproject_path: Path) -> Optional[NormalizedManifest]:
    if not pyproject_path.exists():
        return None
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None

    deps: List[NormalizedDependency] = []
    py_req = None

    # 1. PEP 621 [project]
    project_table = data.get("project", {})
    if isinstance(project_table, dict):
        py_req = project_table.get("requires-python")
        for dep in project_table.get("dependencies", []):
            name, raw = _normalize_package_name(dep)
            deps.append(NormalizedDependency(name=name, raw_spec=raw, source_location="project.dependencies"))
        
        # Optional dependencies (e.g. [project.optional-dependencies.docs])
        opt_deps = project_table.get("optional-dependencies", {})
        if isinstance(opt_deps, dict):
            for group, group_deps in opt_deps.items():
                if isinstance(group_deps, list):
                    for dep in group_deps:
                        if isinstance(dep, str):
                            name, raw = _normalize_package_name(dep)
                            deps.append(NormalizedDependency(name=name, raw_spec=raw, source_location=f"project.optional-dependencies.{group}"))

    # 2. PEP 735 [dependency-groups]
    dep_groups = data.get("dependency-groups", {})
    if isinstance(dep_groups, dict):
        for group, group_deps in dep_groups.items():
            if isinstance(group_deps, list):
                for dep in group_deps:
                    if isinstance(dep, str):
                        name, raw = _normalize_package_name(dep)
                        deps.append(NormalizedDependency(name=name, raw_spec=raw, source_location=f"dependency-groups.{group}"))

    # 3. Poetry [tool.poetry]
    tool_poetry = data.get("tool", {}).get("poetry", {})
    if isinstance(tool_poetry, dict):
        poetry_deps = tool_poetry.get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for pkg_name, spec in poetry_deps.items():
                if pkg_name != "python":
                    raw = f"{pkg_name} {spec}" if isinstance(spec, str) else pkg_name
                    deps.append(NormalizedDependency(name=pkg_name.lower().replace("_", "-"), raw_spec=raw, source_location="tool.poetry.dependencies"))
        
        # Poetry group dependencies [tool.poetry.group.docs.dependencies]
        poetry_groups = tool_poetry.get("group", {})
        if isinstance(poetry_groups, dict):
            for group, g_data in poetry_groups.items():
                g_deps = g_data.get("dependencies", {})
                if isinstance(g_deps, dict):
                    for pkg_name, spec in g_deps.items():
                        raw = f"{pkg_name} {spec}" if isinstance(spec, str) else pkg_name
                        deps.append(NormalizedDependency(name=pkg_name.lower().replace("_", "-"), raw_spec=raw, source_location=f"tool.poetry.group.{group}.dependencies"))

    return NormalizedManifest(
        manifest_type="pyproject.toml",
        manifest_path=str(pyproject_path),
        python_requirement=py_req,
        dependencies=deps
    )

def parse_requirements_txt(req_path: Path) -> Optional[NormalizedManifest]:
    if not req_path.exists():
        return None
    try:
        content = req_path.read_text(encoding="utf-8")
    except Exception:
        return None

    deps: List[NormalizedDependency] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        name, raw = _normalize_package_name(line)
        deps.append(NormalizedDependency(name=name, raw_spec=raw, source_location=str(req_path.name)))

    return NormalizedManifest(
        manifest_type="requirements.txt",
        manifest_path=str(req_path),
        dependencies=deps
    )
