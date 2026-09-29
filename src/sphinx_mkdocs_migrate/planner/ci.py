"""CI/CD and test runner migration planner."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from ..analyzer.ci import (
    DEFAULT_CHECKOUT_TAG,
    DEFAULT_CHECKOUT_SHA,
    DEFAULT_SETUP_UV_TAG,
    DEFAULT_SETUP_UV_SHA,
)
from ..analyzer.models import CIAnalysis, DependencyAnalysis


class CIWorkflowPlan(BaseModel):
    """Planned CI workflow updates for building Sphinx documentation."""

    tox_docs_env: Optional[str] = None
    github_docs_job: Optional[str] = None
    checkout_pinned_ref: Optional[str] = None
    setup_uv_pinned_ref: Optional[str] = None


def determine_tox_dependency_line(
    dep_analysis: Optional[DependencyAnalysis],
    project_root: Optional[Path] = None,
) -> str:
    """Determine the dependency configuration line for tox [testenv:docs]."""
    if (
        dep_analysis
        and dep_analysis.source_group_type
        and dep_analysis.source_group_name
    ):
        if dep_analysis.source_group_type == "dependency-groups":
            return f"dependency_groups = {dep_analysis.source_group_name}"
        elif dep_analysis.source_group_type == "optional-dependencies":
            return f"extras = {dep_analysis.source_group_name}"
        elif dep_analysis.source_group_type == "requirements":
            return f"deps = -r {dep_analysis.source_group_name}"

    if project_root is not None:
        pyproject_path = project_root / "pyproject.toml"
        if pyproject_path.exists():
            try:
                py_text = pyproject_path.read_text(encoding="utf-8")
                if "[dependency-groups]" in py_text:
                    if re.search(r"^\s*docs\s*=", py_text, re.MULTILINE):
                        return "dependency_groups = docs"
                    elif re.search(r"^\s*documentation\s*=", py_text, re.MULTILINE):
                        return "dependency_groups = documentation"
                    elif re.search(r"^\s*dev\s*=", py_text, re.MULTILINE):
                        return "dependency_groups = dev"
                elif "[project.optional-dependencies]" in py_text:
                    if re.search(r"^\s*docs\s*=", py_text, re.MULTILINE):
                        return "extras = docs"
                    elif re.search(r"^\s*doc\s*=", py_text, re.MULTILINE):
                        return "extras = doc"
                    elif re.search(r"^\s*dev\s*=", py_text, re.MULTILINE):
                        return "extras = dev"
            except Exception:
                pass
        if (project_root / "docs" / "requirements.txt").exists():
            return "deps = -r docs/requirements.txt"
        elif (project_root / "requirements.txt").exists():
            return "deps = -r requirements.txt"

    return "dependency_groups = dev"


def build_tox_docs_env(
    dep_config_line: str,
    build_command: str = "sphinx-build -b html docs site/_build/html",
) -> str:
    """Build the [testenv:docs] section string for tox.ini."""
    return f"""
[testenv:docs]
description = build documentation
{dep_config_line}
commands =
    {build_command}
"""


def build_github_docs_job(
    checkout_ref: str,
    uv_ref: str,
    tox_env: str = "docs",
) -> str:
    """Build the GitHub Actions documentation job block."""
    return f"""
  docs:
    name: "Python Docs"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{checkout_ref}

      - uses: astral-sh/setup-uv@{uv_ref}

      - name: Build docs with tox
        run: uvx tox -e {tox_env}
"""


def plan_ci_workflow(
    ci_analysis: Optional[CIAnalysis],
    dep_analysis: Optional[DependencyAnalysis],
    project_root: Optional[Path] = None,
) -> CIWorkflowPlan:
    """Plan concrete CI changes based on observed repository evidence."""
    dep_line = determine_tox_dependency_line(dep_analysis, project_root)
    tox_env = build_tox_docs_env(dep_line)

    default_chk = (
        f"{DEFAULT_CHECKOUT_SHA} # {DEFAULT_CHECKOUT_TAG}"
        if DEFAULT_CHECKOUT_SHA
        else DEFAULT_CHECKOUT_TAG
    )
    default_uv = (
        f"{DEFAULT_SETUP_UV_SHA} # {DEFAULT_SETUP_UV_TAG}"
        if DEFAULT_SETUP_UV_SHA
        else DEFAULT_SETUP_UV_TAG
    )
    ch_ref = (
        ci_analysis.checkout_pinned_ref
        if (ci_analysis and ci_analysis.checkout_pinned_ref)
        else default_chk
    )
    uv_ref = (
        ci_analysis.setup_uv_pinned_ref
        if (ci_analysis and ci_analysis.setup_uv_pinned_ref)
        else default_uv
    )
    gh_job = build_github_docs_job(checkout_ref=ch_ref, uv_ref=uv_ref)

    return CIWorkflowPlan(
        tox_docs_env=tox_env,
        github_docs_job=gh_job,
        checkout_pinned_ref=ch_ref,
        setup_uv_pinned_ref=uv_ref,
    )
