"""Subsystem analyzer for CI/CD, local test runners, and deployment workflows."""

import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from .models import CIAnalysis

DEFAULT_CHECKOUT_TAG = "v7.0.1"
DEFAULT_CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
DEFAULT_SETUP_UV_TAG = "v10.2.0"
DEFAULT_SETUP_UV_SHA = "c18668ad3cf93ea998bef934396af7bb5c839dc7"


def resolve_github_action_ref(
    action_repo: str, fallback_tag: str, fallback_sha: str
) -> Tuple[str, str]:
    """Resolves the latest release tag and commit SHA for a GitHub Action repository via git ls-remote."""
    import subprocess

    try:
        url = f"https://github.com/{action_repo}.git"
        out = subprocess.check_output(
            ["git", "ls-remote", "--tags", url],
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tag_shas: Dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                sha, ref = parts[0], parts[1]
                m = re.match(r"^refs/tags/(v?[0-9]+(?:\.[0-9]+)*)(\^\{\})?$", ref)
                if m:
                    tag = m.group(1)
                    if ref.endswith("^{}"):
                        tag_shas[tag] = sha
                    elif tag not in tag_shas:
                        tag_shas[tag] = sha
        if tag_shas:

            def semver_key(t: str):
                return [int(x) for x in re.findall(r"[0-9]+", t)]

            sorted_tags = sorted(tag_shas.keys(), key=semver_key)
            latest_tag = sorted_tags[-1]
            return latest_tag, tag_shas[latest_tag]
    except Exception:
        pass
    return fallback_tag, fallback_sha


class CIAnalyzer:
    """Discovers and inspects project CI/CD workflows, runners (tox/nox/make), and hosted doc configs."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def analyze(self) -> CIAnalysis:
        # 1. GitHub Actions (.github/workflows/*.yml)
        github_workflows = self.project_root / ".github" / "workflows"
        workflow_files: List[str] = []
        docs_workflow_files: List[str] = []
        has_deploy = False
        has_tox_in_ci = False
        has_uv_in_ci = False
        has_gh_pages_action = False
        checkout_ref: Optional[str] = None
        setup_uv_ref: Optional[str] = None
        checkout_pinned_ref: Optional[str] = None
        setup_uv_pinned_ref: Optional[str] = None
        github_actions_detected = github_workflows.is_dir()

        if github_actions_detected:
            chk_tag, chk_sha = resolve_github_action_ref(
                "actions/checkout", DEFAULT_CHECKOUT_TAG, DEFAULT_CHECKOUT_SHA
            )
            uv_tag, uv_sha = resolve_github_action_ref(
                "astral-sh/setup-uv", DEFAULT_SETUP_UV_TAG, DEFAULT_SETUP_UV_SHA
            )
            checkout_pinned_ref = f"{chk_sha} # {chk_tag}" if chk_sha else chk_tag
            setup_uv_pinned_ref = f"{uv_sha} # {uv_tag}" if uv_sha else uv_tag

        if github_actions_detected:
            for yml_file in sorted(github_workflows.glob("*.y*ml")):
                rel = yml_file.relative_to(self.project_root).as_posix()
                workflow_files.append(rel)
                try:
                    content = yml_file.read_text(encoding="utf-8")
                    if (
                        "mkdocs gh-deploy" in content
                        or "mkdocs build" in content
                        or "mike deploy" in content
                    ):
                        has_deploy = True
                        docs_workflow_files.append(rel)
                    if "tox" in content or "uvx tox" in content:
                        has_tox_in_ci = True
                    if (
                        "astral-sh/setup-uv" in content
                        or "setup-uv" in content
                        or "uv run" in content
                    ):
                        has_uv_in_ci = True
                    if (
                        "peaceiris/actions-gh-pages" in content
                        or "actions/deploy-pages" in content
                    ):
                        has_gh_pages_action = True

                    # Extract current action version refs
                    m_chk = re.search(r"uses:\s*actions/checkout@([^\s\n]+)", content)
                    if m_chk and not checkout_ref:
                        checkout_ref = m_chk.group(1).split("#")[0].strip()
                    m_uv = re.search(r"uses:\s*astral-sh/setup-uv@([^\s\n]+)", content)
                    if m_uv and not setup_uv_ref:
                        setup_uv_ref = m_uv.group(1).split("#")[0].strip()
                except Exception:
                    pass

        # 2. Local test & doc runners: tox.ini
        tox_ini = self.project_root / "tox.ini"
        has_tox = tox_ini.is_file()
        tox_file = (
            tox_ini.relative_to(self.project_root).as_posix() if has_tox else None
        )
        tox_has_docs_env = False
        tox_docs_commands: List[str] = []
        tox_dependency_spec: Optional[str] = None

        if has_tox:
            try:
                tox_text = tox_ini.read_text(encoding="utf-8")
                if "[testenv:docs]" in tox_text:
                    tox_has_docs_env = True
                    # Extract section content
                    m_sec = re.search(
                        r"\[testenv:docs\](.*?)(?=\n\[|\Z)", tox_text, re.DOTALL
                    )
                    if m_sec:
                        sec_text = m_sec.group(1)
                        for line in sec_text.splitlines():
                            line_s = line.strip()
                            if (
                                line_s.startswith("dependency_groups")
                                or line_s.startswith("extras")
                                or line_s.startswith("deps")
                            ):
                                tox_dependency_spec = line_s
                            elif line_s.startswith("commands =") or (
                                line.startswith(" ")
                                and ("sphinx-build" in line_s or "mkdocs" in line_s)
                            ):
                                tox_docs_commands.append(line_s)
                elif "mkdocs" in tox_text:
                    tox_docs_commands.append("mkdocs")
            except Exception:
                pass

        # 3. ReadTheDocs (.readthedocs.yaml or .readthedocs.yml)
        rtd_config = self.project_root / ".readthedocs.yaml"
        if not rtd_config.exists():
            rtd_config = self.project_root / ".readthedocs.yml"
        has_rtd = rtd_config.is_file()
        rtd_file = (
            rtd_config.relative_to(self.project_root).as_posix() if has_rtd else None
        )

        # 4. Nox runner (noxfile.py)
        noxfile = self.project_root / "noxfile.py"
        has_nox = noxfile.is_file()
        nox_file = (
            noxfile.relative_to(self.project_root).as_posix() if has_nox else None
        )

        # 5. Makefile
        makefile = self.project_root / "Makefile"
        has_makefile = makefile.is_file()

        # 6. Pre-commit (.pre-commit-config.yaml)
        pre_commit = self.project_root / ".pre-commit-config.yaml"
        has_pre_commit = pre_commit.is_file()

        # 7. GitLab CI (.gitlab-ci.yml)
        gitlab_ci = self.project_root / ".gitlab-ci.yml"
        gitlab_ci_detected = gitlab_ci.is_file()

        # Primary CI system resolution
        ci_system = None
        if github_actions_detected:
            ci_system = "github_actions"
        elif gitlab_ci_detected:
            ci_system = "gitlab_ci"
        elif has_rtd:
            ci_system = "readthedocs"

        return CIAnalysis(
            ci_system=ci_system,
            workflow_files=workflow_files,
            docs_workflow_files=docs_workflow_files,
            has_mkdocs_deploy=has_deploy,
            readthedocs_detected=has_rtd,
            rtd_config_file=rtd_file,
            github_actions_detected=github_actions_detected,
            has_tox_in_ci=has_tox_in_ci,
            has_uv_in_ci=has_uv_in_ci,
            has_gh_pages_action=has_gh_pages_action,
            checkout_action_ref=checkout_ref,
            setup_uv_action_ref=setup_uv_ref,
            checkout_pinned_ref=checkout_pinned_ref,
            setup_uv_pinned_ref=setup_uv_pinned_ref,
            has_tox=has_tox,
            tox_file=tox_file,
            tox_has_docs_env=tox_has_docs_env,
            tox_docs_commands=tox_docs_commands,
            tox_dependency_spec=tox_dependency_spec,
            has_nox=has_nox,
            nox_file=nox_file,
            has_makefile=has_makefile,
            has_pre_commit=has_pre_commit,
            gitlab_ci_detected=gitlab_ci_detected,
        )
