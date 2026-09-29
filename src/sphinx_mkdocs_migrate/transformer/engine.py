"""Transformation Engine executing MigrationPlan actions deterministically to produce MyST docs and conf.py."""

import difflib
import hashlib
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..planner.models import MigrationPlan
from ..planner.conf_builder import build_conf_py
from ..planner.toctree import build_semantic_toctree
from ..planner.ci import (
    build_tox_docs_env,
    build_github_docs_job,
    determine_tox_dependency_line,
)
from ..analyzer.models import NavigationItem
from ..analyzer.dependencies import KNOWN_MKDOCS_PACKAGES
from ..analyzer.mkdocs import detect_obsolete_generator_scripts
from ..analyzer.ci import (
    resolve_github_action_ref,
    DEFAULT_CHECKOUT_TAG,
    DEFAULT_CHECKOUT_SHA,
    DEFAULT_SETUP_UV_TAG,
    DEFAULT_SETUP_UV_SHA,
)
from ..parsing.markdown import MarkdownParser
from .models import (
    ProjectTransformationReport,
    DocumentTransformationResult,
    TransformationStatus,
    ConfPyStatus,
)
from .myst_transformer import MySTDocumentTransformer


class TransformationEngine:
    """Consumes a MigrationPlan to transform documentation and generate Sphinx artifacts via source-preserving patching."""

    def __init__(
        self,
        plan: MigrationPlan,
        manual_overrides: Optional[Dict[str, str]] = None,
    ):
        self.plan = plan
        self.parser = MarkdownParser()
        self.project_root = Path(plan.project_root)
        self.manual_overrides = manual_overrides or {}

    def execute(
        self, write_to_disk: bool = False, overwrite_conf: bool = False
    ) -> ProjectTransformationReport:
        """Executes document transformations and Sphinx scaffolding derived strictly from the plan."""
        actions_by_file: Dict[str, List] = {}
        for act in self.plan.document_actions:
            actions_by_file.setdefault(act.source_file, []).append(act)

        # 1. Discover documentation files
        docs_dir_name = (
            self.plan.source_mkdocs_config.docs_dir
            if self.plan.source_mkdocs_config
            else "docs"
        )
        docs_dir = self.project_root / docs_dir_name
        all_md_files: List[Path] = (
            sorted(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else []
        )
        documents_examined = len(all_md_files)

        nav_entries = (
            self.plan.navigation_analysis.tree
            if (self.plan.navigation_analysis and self.plan.navigation_analysis.has_nav)
            else []
        )
        autorefs_targets = self._autorefs_target_documents()

        # 2. Transform existing markdown files
        (
            doc_results,
            documents_changed,
            files_written,
        ) = self._transform_all_documents(
            all_md_files=all_md_files,
            docs_dir=docs_dir,
            actions_by_file=actions_by_file,
            nav_entries=nav_entries,
            autorefs_targets=autorefs_targets,
            write_to_disk=write_to_disk,
        )

        generated_files: Dict[str, str] = {}

        # 3. Ensure root index.md exists
        (
            root_idx_files,
            root_idx_results,
            idx_written,
            idx_changed,
        ) = self._ensure_root_index(
            docs_dir=docs_dir,
            docs_dir_name=docs_dir_name,
            nav_entries=nav_entries,
            all_md_files=all_md_files,
            doc_results=doc_results,
            write_to_disk=write_to_disk,
        )
        generated_files.update(root_idx_files)
        doc_results.extend(root_idx_results)
        files_written += idx_written
        documents_changed += idx_changed

        # 4. Materialize Planned Generated Documents (e.g. API reference stubs from gen-files/mkdocstrings)
        (
            gen_files,
            gen_results,
            gen_written,
            gen_changed,
        ) = self._materialize_generated_documents(write_to_disk=write_to_disk)
        generated_files.update(gen_files)
        doc_results.extend(gen_results)
        files_written += gen_written
        documents_changed += gen_changed

        # 5. Generate Sphinx conf.py scaffolding
        (
            conf_content,
            conf_target_key,
            conf_status,
            conf_diff,
            conf_written,
        ) = self._manage_conf_py(
            docs_dir_name=docs_dir_name,
            overwrite_conf=overwrite_conf,
            write_to_disk=write_to_disk,
        )
        generated_files[conf_target_key] = conf_content
        files_written += conf_written

        # 6. Update dependencies, CI workflows, and clean up obsolete scripts
        dep_changes = self._migrate_dependencies(write_to_disk=write_to_disk)
        if write_to_disk and dep_changes:
            files_written += 1

        ci_changes = self._migrate_ci_workflows(write_to_disk=write_to_disk)
        if write_to_disk and ci_changes:
            files_written += len(ci_changes)

        cleaned_files = self._clean_obsolete_mkdocs_files(write_to_disk=write_to_disk)

        return ProjectTransformationReport(
            project_root=str(self.project_root),
            plan_hash=self.plan.canonical_hash(),
            transformed_documents=doc_results,
            generated_sphinx_files=generated_files,
            conf_py_status=conf_status,
            conf_py_conflict_diff=conf_diff,
            documents_examined=documents_examined,
            documents_changed=documents_changed,
            files_written_to_disk=files_written,
            total_transforms_executed=sum(d.transforms_applied for d in doc_results),
            total_stale_actions=sum(d.stale_actions_count for d in doc_results),
            cleaned_files=cleaned_files,
            dry_run=not write_to_disk,
        )

    def _transform_markdown_file(
        self,
        md_file: Path,
        actions: List,
        docs_dir: Path,
        nav_entries: List[NavigationItem],
        all_md_files: List[Path],
        autorefs_targets: Dict[str, Path],
    ) -> Tuple[DocumentTransformationResult, bool]:
        """Transforms a single Markdown file applying MyST actions, autorefs, and frontmatter sanitization."""
        source_file_rel = md_file.relative_to(self.project_root).as_posix()
        orig_content = md_file.read_text(encoding="utf-8")
        source_fp = hashlib.sha256(orig_content.encode("utf-8")).hexdigest()[:16]

        doc_ir = self.parser.parse_text(orig_content, file_path=source_file_rel)
        transformer = MySTDocumentTransformer(
            actions, manual_overrides=self.manual_overrides
        )
        (
            transformed_content,
            applied_cnt,
            preserved_cnt,
            manual_cnt,
            unsupported_cnt,
            stale_cnt,
            stale_details,
        ) = transformer.transform_document(doc_ir, orig_content)
        # MkDocs autorefs accepts compact reference links such as
        # ``[orjson][pythonjsonlogger.orjson]``.  They have no CommonMark
        # reference definition, so MyST would render them literally.  Only
        # rewrite targets we can resolve to a generated Sphinx document.
        if autorefs_targets:
            transformed_content, autorefs_count = self._transform_autorefs_links(
                transformed_content, md_file, docs_dir, autorefs_targets
            )
            applied_cnt += autorefs_count

        # Universal YAML frontmatter date object sanitizer
        if transformed_content.startswith("---"):
            parts = transformed_content.split("---", 2)
            if len(parts) >= 3:
                sanitized_header = re.sub(
                    r"(:\s*)(\d{4}-\d{2}-\d{2})\b", r'\1"\2"', parts[1]
                )
                transformed_content = "---" + sanitized_header + "---" + parts[2]
            # Only the documentation root owns the site-level toctree.  Nested
            # ``index.md`` files are section/package landing pages and must keep
            # their own child toctrees (for example generated API modules).
        if md_file == docs_dir / "index.md":
            toctree_block = self._generate_semantic_toctree(
                nav_entries, all_md_files, docs_dir
            )
            if toctree_block:
                if "```{toctree}" in transformed_content:
                    transformed_content = re.sub(
                        r"```\{toctree\}[\s\S]*?```",
                        toctree_block,
                        transformed_content,
                    )
                else:
                    transformed_content = (
                        transformed_content.rstrip() + "\n\n" + toctree_block + "\n"
                    )

        is_modified = orig_content != transformed_content
        if manual_cnt > 0 and applied_cnt == 0:
            doc_status = TransformationStatus.MANUAL_REQUIRED
        elif is_modified:
            doc_status = TransformationStatus.APPLIED
        else:
            doc_status = TransformationStatus.UNCHANGED

        diff_str = None
        if is_modified:
            diff_lines = list(
                difflib.unified_diff(
                    orig_content.splitlines(keepends=True),
                    transformed_content.splitlines(keepends=True),
                    fromfile=f"a/{source_file_rel}",
                    tofile=f"b/{source_file_rel}",
                )
            )
            diff_str = "".join(diff_lines)

        result = DocumentTransformationResult(
            source_file=source_file_rel,
            target_file=source_file_rel,
            original_content=orig_content,
            transformed_content=transformed_content,
            source_fingerprint=source_fp,
            transforms_applied=applied_cnt,
            constructs_preserved=preserved_cnt,
            manual_items_reported=manual_cnt,
            unsupported_items_reported=unsupported_cnt,
            stale_actions_count=stale_cnt,
            stale_action_details=stale_details,
            status=doc_status,
            diff=diff_str,
            is_modified=is_modified,
        )
        return result, is_modified

    def _transform_all_documents(
        self,
        all_md_files: List[Path],
        docs_dir: Path,
        actions_by_file: Dict[str, List],
        nav_entries: List[NavigationItem],
        autorefs_targets: Dict[str, Path],
        write_to_disk: bool,
    ) -> Tuple[List[DocumentTransformationResult], int, int]:
        """Processes all discovered Markdown documents."""
        doc_results: List[DocumentTransformationResult] = []
        documents_changed = 0
        files_written = 0

        for md_file in all_md_files:
            source_file_rel = md_file.relative_to(self.project_root).as_posix()
            actions = actions_by_file.get(source_file_rel, [])
            result, is_mod = self._transform_markdown_file(
                md_file=md_file,
                actions=actions,
                docs_dir=docs_dir,
                nav_entries=nav_entries,
                all_md_files=all_md_files,
                autorefs_targets=autorefs_targets,
            )
            doc_results.append(result)
            if is_mod:
                documents_changed += 1
                if write_to_disk:
                    md_file.write_text(result.transformed_content, encoding="utf-8")
                    files_written += 1

        return doc_results, documents_changed, files_written

    def _ensure_root_index(
        self,
        docs_dir: Path,
        docs_dir_name: str,
        nav_entries: List[NavigationItem],
        all_md_files: List[Path],
        doc_results: List[DocumentTransformationResult],
        write_to_disk: bool,
    ) -> Tuple[Dict[str, str], List[DocumentTransformationResult], int, int]:
        """Ensures a root index.md exists with site-level semantic toctree if needed."""
        generated: Dict[str, str] = {}
        added_results: List[DocumentTransformationResult] = []
        files_written = 0
        documents_changed = 0

        root_index_path = docs_dir / "index.md"
        root_index_rel = f"{docs_dir_name}/index.md" if docs_dir_name else "index.md"
        has_root_index = any(
            Path(doc.target_file).as_posix()
            in (
                Path(root_index_rel).as_posix(),
                "index.md",
                f"{docs_dir_name}/index.md",
            )
            for doc in doc_results
        )

        if not has_root_index:
            toctree_block = self._generate_semantic_toctree(
                nav_entries, all_md_files, docs_dir
            )
            index_title = (
                self.plan.proposed_sphinx_config.project_name
                if self.plan.proposed_sphinx_config
                else "Documentation"
            )
            generated_index_content = f"# {index_title}\n\n"
            if toctree_block:
                generated_index_content += toctree_block + "\n"

            generated[root_index_rel] = generated_index_content
            if write_to_disk:
                root_index_path.parent.mkdir(parents=True, exist_ok=True)
                root_index_path.write_text(generated_index_content, encoding="utf-8")
                files_written += 1

            added_results.append(
                DocumentTransformationResult(
                    source_file=root_index_rel,
                    target_file=root_index_rel,
                    original_content="",
                    transformed_content=generated_index_content,
                    source_fingerprint="generated_root_index",
                    transforms_applied=1,
                    status=TransformationStatus.APPLIED,
                    is_modified=True,
                )
            )
            documents_changed += 1

        return generated, added_results, files_written, documents_changed

    def _materialize_generated_documents(
        self, write_to_disk: bool
    ) -> Tuple[Dict[str, str], List[DocumentTransformationResult], int, int]:
        """Materializes planned generated documents (e.g. API reference stubs from gen-files/mkdocstrings)."""
        generated: Dict[str, str] = {}
        doc_results: List[DocumentTransformationResult] = []
        files_written = 0
        documents_changed = 0

        for gen_doc in self.plan.generated_documents:
            target_disk_path = self.project_root / gen_doc.target_path
            generated[gen_doc.target_path] = gen_doc.content

            orig_doc_content = (
                target_disk_path.read_text(encoding="utf-8")
                if target_disk_path.exists()
                else ""
            )
            is_mod = orig_doc_content != gen_doc.content

            if write_to_disk:
                target_disk_path.parent.mkdir(parents=True, exist_ok=True)
                target_disk_path.write_text(gen_doc.content, encoding="utf-8")
                files_written += 1

            if is_mod:
                documents_changed += 1

            doc_results.append(
                DocumentTransformationResult(
                    source_file=gen_doc.target_path,
                    target_file=gen_doc.target_path,
                    original_content=orig_doc_content,
                    transformed_content=gen_doc.content,
                    source_fingerprint=f"generated_{gen_doc.generator_plugin}",
                    transforms_applied=1,
                    status=TransformationStatus.APPLIED
                    if is_mod
                    else TransformationStatus.UNCHANGED,
                    is_modified=is_mod,
                )
            )

        return generated, doc_results, files_written, documents_changed

    def _manage_conf_py(
        self, docs_dir_name: str, overwrite_conf: bool, write_to_disk: bool
    ) -> Tuple[str, str, ConfPyStatus, Optional[str], int]:
        """Generates and writes Sphinx conf.py scaffolding with conflict detection."""
        conf_py_content = self._generate_conf_py()
        conf_target_key = f"{docs_dir_name}/conf.py"
        conf_disk_path = self.project_root / docs_dir_name / "conf.py"
        conf_status = ConfPyStatus.CREATED
        conf_diff = None
        files_written = 0

        if conf_disk_path.exists():
            existing_conf = conf_disk_path.read_text(encoding="utf-8")
            if existing_conf == conf_py_content:
                conf_status = ConfPyStatus.UNCHANGED
            else:
                conf_status = ConfPyStatus.CONFLICT
                diff_lines = list(
                    difflib.unified_diff(
                        existing_conf.splitlines(keepends=True),
                        conf_py_content.splitlines(keepends=True),
                        fromfile=f"a/{docs_dir_name}/conf.py (existing)",
                        tofile=f"b/{docs_dir_name}/conf.py (planned)",
                    )
                )
                conf_diff = "".join(diff_lines)

        if write_to_disk:
            if (
                not conf_disk_path.exists()
                or conf_status == ConfPyStatus.UNCHANGED
                or overwrite_conf
            ):
                conf_disk_path.parent.mkdir(parents=True, exist_ok=True)
                conf_disk_path.write_text(conf_py_content, encoding="utf-8")
                files_written = 1

        return conf_py_content, conf_target_key, conf_status, conf_diff, files_written

    def _autorefs_target_documents(self) -> Dict[str, Path]:
        """Map known Python module identities to generated documentation paths."""
        if (
            not self.plan.source_mkdocs_config
            or "autorefs" not in self.plan.source_mkdocs_config.plugins
        ):
            return {}

        targets: Dict[str, Path] = {}
        # 1. Prefer pre-planned cross reference mappings from documentation plan
        if (
            self.plan.documentation_plan
            and self.plan.documentation_plan.cross_reference_mappings
        ):
            for (
                name,
                rel_path,
            ) in self.plan.documentation_plan.cross_reference_mappings.items():
                if rel_path.endswith(".md"):
                    targets[name] = self.project_root / rel_path

        # 2. Fallback to scanning generated documents if not mapped
        if not targets:
            currentmodule_re = re.compile(
                r"^\.\. currentmodule::\s+(?P<name>[\w.]+)\s*$", re.MULTILINE
            )
            for proposal in self.plan.generated_documents:
                match = currentmodule_re.search(proposal.content)
                if match:
                    targets[match.group("name")] = (
                        self.project_root / proposal.target_path
                    )
        return targets

    @staticmethod
    def _transform_autorefs_links(
        content: str,
        source_path: Path,
        docs_dir: Path,
        targets: Dict[str, Path],
    ) -> Tuple[str, int]:
        """Rewrite resolvable MkDocs autorefs compact links to relative MyST links."""
        reference_re = re.compile(
            r"(?<!!)\[(?P<label>[^\]\n]+)\]\[(?P<target>[A-Za-z_]\w*(?:\.\w+)*)?\]"
        )
        source_dir = source_path.parent
        changes = 0

        def replace(match: re.Match) -> str:
            nonlocal changes
            label = match.group("label")
            target = match.group("target")
            effective_target = target if target else label
            target_doc = targets.get(effective_target)
            if not target_doc and "." in effective_target:
                target_doc = targets.get(effective_target.rsplit(".", 1)[0])
            if target_doc is None:
                return match.group(0)
            display_label = label.split(".")[-1] if not target else label
            relative = Path(os.path.relpath(target_doc, source_dir)).as_posix()
            changes += 1
            return f"[{display_label}]({relative})"

        return reference_re.sub(replace, content), changes

    def _generate_semantic_toctree(
        self, nav_entries: List[NavigationItem], all_files: List[Path], docs_dir: Path
    ) -> Optional[str]:
        """Generate the root toctree without flattening section landing pages."""
        docs_prefix = docs_dir.relative_to(self.project_root)
        generated_targets = set()
        for proposal in self.plan.generated_documents:
            try:
                generated_targets.add(
                    Path(proposal.target_path)
                    .relative_to(docs_prefix)
                    .with_suffix("")
                    .as_posix()
                )
            except ValueError:
                continue
        return build_semantic_toctree(
            nav_entries=nav_entries,
            all_files=all_files,
            docs_dir=docs_dir,
            project_root=self.project_root,
            generated_targets=generated_targets,
        )

    def _generate_conf_py(self) -> str:
        """Generates a clean Sphinx conf.py based strictly on MigrationPlan requirements."""
        if (
            self.plan.proposed_sphinx_config
            and self.plan.proposed_sphinx_config.rendered_content
        ):
            return self.plan.proposed_sphinx_config.rendered_content
        return build_conf_py(self.plan)

    def _migrate_dependencies(self, write_to_disk: bool) -> List[str]:
        """Update pyproject.toml or requirements.txt removing MkDocs packages and adding Sphinx packages."""
        changes: List[str] = []
        if not self.plan.dependency_analysis:
            return changes

        to_remove = set(
            p.lower().replace("_", "-") for p in (self.plan.packages_to_remove or [])
        )
        if self.plan.dependency_analysis:
            to_remove.update(
                p.lower().replace("_", "-")
                for p in self.plan.dependency_analysis.detected_packages_to_remove
            )
        to_remove.update({p.lower().replace("_", "-") for p in KNOWN_MKDOCS_PACKAGES})

        # Deduplicate packages to add by normalized name, keeping version constraints
        raw_candidates = list(self.plan.dependency_analysis.suggested_packages_to_add)
        if self.plan.documentation_plan:
            for req_pkg in self.plan.documentation_plan.required_packages or []:
                raw_candidates.append(req_pkg)
            if "sphinx_copybutton" in (
                self.plan.documentation_plan.required_extensions or []
            ):
                raw_candidates.append("sphinx-copybutton")

        seen_names = set()
        to_add: List[str] = []
        for candidate in sorted(raw_candidates, key=lambda s: len(s), reverse=True):
            m_pkg = re.match(r"^([a-zA-Z0-9_\-\.]+)", candidate)
            norm = (
                m_pkg.group(1).lower().replace("_", "-") if m_pkg else candidate.lower()
            )
            if norm not in seen_names:
                seen_names.add(norm)
                to_add.append(candidate)
        to_add.sort()

        # 1. Update pyproject.toml if present
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines: List[str] = []
            inserted = False
            i = 0
            while i < len(lines):
                line = lines[i]
                m = re.search(
                    r'["\']([a-zA-Z0-9_\-\.]+)(?:\[[^\]]+\])?(?:[<>=!~;].*)?["\']', line
                )
                if m:
                    pkg_name = m.group(1).lower().replace("_", "-")
                    if pkg_name in to_remove:
                        if not inserted:
                            m_indent = re.match(r"^\s*", line)
                            indent = m_indent.group(0) if m_indent else ""
                            for add_pkg in to_add:
                                new_lines.append(f'{indent}"{add_pkg}",')
                            inserted = True
                        changes.append(f"Removed {pkg_name} from pyproject.toml")
                        i += 1
                        continue
                new_lines.append(line)
                i += 1

            updated_content = "\n".join(new_lines) + (
                "\n" if content.endswith("\n") else ""
            )
            if updated_content != content:
                if write_to_disk:
                    pyproject_path.write_text(updated_content, encoding="utf-8")
                changes.append("Updated pyproject.toml with Sphinx dependencies")

        # 2. Update requirements.txt / docs-requirements.txt if present
        for req_name in [
            "requirements.txt",
            "docs-requirements.txt",
            "docs/requirements.txt",
        ]:
            req_path = self.project_root / req_name
            if req_path.exists():
                content = req_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                new_lines = []
                inserted = False
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        m = re.match(r"^([a-zA-Z0-9_\-\.]+)", stripped)
                        if m:
                            pkg_name = m.group(1).lower().replace("_", "-")
                            if pkg_name in to_remove:
                                if not inserted:
                                    for add_pkg in to_add:
                                        new_lines.append(add_pkg)
                                    inserted = True
                                changes.append(f"Removed {pkg_name} from {req_name}")
                                continue
                    new_lines.append(line)
                if not inserted and to_add:
                    new_lines.extend(to_add)
                updated_content = "\n".join(new_lines) + (
                    "\n" if content.endswith("\n") else ""
                )
                if updated_content != content:
                    if write_to_disk:
                        req_path.write_text(updated_content, encoding="utf-8")
                    changes.append(f"Updated {req_name} with Sphinx dependencies")

        return changes

    def _resolve_github_action_ref(
        self, action_repo: str, fallback_tag: str, fallback_sha: str
    ) -> Tuple[str, str]:
        """Resolves the latest release tag and commit SHA for a GitHub Action repository via git ls-remote."""
        return resolve_github_action_ref(action_repo, fallback_tag, fallback_sha)

    def _migrate_ci_workflows(self, write_to_disk: bool) -> List[str]:
        """Update CI workflows and configuration to build Sphinx documentation using the project's native tooling."""
        changes: List[str] = []
        github_workflows = self.project_root / ".github" / "workflows"
        tox_ini = self.project_root / "tox.ini"

        # 1. Update existing workflow files if they invoke mkdocs
        if github_workflows.exists():
            for yml_file in sorted(github_workflows.glob("*.y*ml")):
                try:
                    content = yml_file.read_text(encoding="utf-8")
                    if (
                        "mkdocs build" in content
                        or "mkdocs gh-deploy" in content
                        or "mkdocs" in content
                    ):
                        new_content = content.replace(
                            "mkdocs gh-deploy",
                            "sphinx-build -b html docs site/_build/html",
                        )
                        new_content = new_content.replace(
                            "mkdocs build", "sphinx-build -b html docs site/_build/html"
                        )
                        if new_content != content:
                            if write_to_disk:
                                yml_file.write_text(new_content, encoding="utf-8")
                            changes.append(
                                f"Updated {yml_file.name} to use sphinx-build"
                            )
                except Exception:
                    pass

        # 2. If the project uses tox (tox.ini exists), add or update [testenv:docs]
        if tox_ini.exists():
            try:
                tox_content = tox_ini.read_text(encoding="utf-8")

                # Use planned tox env or generate using planner helper
                if self.plan.ci_plan and self.plan.ci_plan.tox_docs_env:
                    docs_env = self.plan.ci_plan.tox_docs_env
                else:
                    dep_config_line = determine_tox_dependency_line(
                        self.plan.dependency_analysis, self.project_root
                    )
                    docs_env = build_tox_docs_env(dep_config_line)

                if "[testenv:docs]" not in tox_content:
                    updated_tox = tox_content.rstrip() + docs_env
                    if write_to_disk:
                        tox_ini.write_text(updated_tox, encoding="utf-8")
                    changes.append("Added [testenv:docs] to tox.ini")
                elif "mkdocs build" in tox_content:
                    new_tox = tox_content.replace(
                        "mkdocs build", "sphinx-build -b html docs site/_build/html"
                    )
                    if new_tox != tox_content:
                        if write_to_disk:
                            tox_ini.write_text(new_tox, encoding="utf-8")
                        changes.append(
                            "Updated [testenv:docs] in tox.ini to use sphinx-build"
                        )
            except Exception:
                pass

        # Also integrate docs job into existing GitHub workflow if it uses tox
        if github_workflows.exists():
            try:
                for yml_file in sorted(github_workflows.glob("*.y*ml")):
                    wf_content = yml_file.read_text(encoding="utf-8")
                    if "tox" in wf_content:
                        checkout_ref = (
                            self.plan.ci_plan.checkout_pinned_ref
                            if (
                                self.plan.ci_plan
                                and self.plan.ci_plan.checkout_pinned_ref
                            )
                            else (
                                self.plan.ci_analysis.checkout_pinned_ref
                                if (
                                    self.plan.ci_analysis
                                    and self.plan.ci_analysis.checkout_pinned_ref
                                )
                                else None
                            )
                        )
                        uv_ref = (
                            self.plan.ci_plan.setup_uv_pinned_ref
                            if (
                                self.plan.ci_plan
                                and self.plan.ci_plan.setup_uv_pinned_ref
                            )
                            else (
                                self.plan.ci_analysis.setup_uv_pinned_ref
                                if (
                                    self.plan.ci_analysis
                                    and self.plan.ci_analysis.setup_uv_pinned_ref
                                )
                                else None
                            )
                        )
                        if not checkout_ref or not uv_ref:
                            ch_tag, ch_sha = self._resolve_github_action_ref(
                                "actions/checkout",
                                DEFAULT_CHECKOUT_TAG,
                                DEFAULT_CHECKOUT_SHA,
                            )
                            u_tag, u_sha = self._resolve_github_action_ref(
                                "astral-sh/setup-uv",
                                DEFAULT_SETUP_UV_TAG,
                                DEFAULT_SETUP_UV_SHA,
                            )
                            checkout_ref = checkout_ref or (
                                f"{ch_sha} # {ch_tag}" if ch_sha else ch_tag
                            )
                            uv_ref = uv_ref or (
                                f"{u_sha} # {u_tag}" if u_sha else u_tag
                            )

                        docs_job = (
                            self.plan.ci_plan.github_docs_job
                            if (self.plan.ci_plan and self.plan.ci_plan.github_docs_job)
                            else build_github_docs_job(
                                checkout_ref=checkout_ref, uv_ref=uv_ref
                            )
                        )

                        if "tox -e docs" not in wf_content and "jobs:" in wf_content:
                            updated_wf = wf_content.rstrip() + "\n" + docs_job
                            updated_wf = re.sub(
                                r"uses:\s*actions/checkout@[^\s\n]+(?:\s*#[^\n]*)?",
                                f"uses: actions/checkout@{checkout_ref}",
                                updated_wf,
                            )
                            updated_wf = re.sub(
                                r"uses:\s*astral-sh/setup-uv@[^\s\n]+(?:\s*#[^\n]*)?",
                                f"uses: astral-sh/setup-uv@{uv_ref}",
                                updated_wf,
                            )
                            if write_to_disk:
                                yml_file.write_text(updated_wf, encoding="utf-8")
                            changes.append(
                                f"Added docs job with git-pinned action hashes to {yml_file.name}"
                            )
                            break
                        elif "tox -e docs" in wf_content:
                            updated_wf = re.sub(
                                r"uses:\s*actions/checkout@[^\s\n]+(?:\s*#[^\n]*)?",
                                f"uses: actions/checkout@{checkout_ref}",
                                wf_content,
                            )
                            updated_wf = re.sub(
                                r"uses:\s*astral-sh/setup-uv@[^\s\n]+(?:\s*#[^\n]*)?",
                                f"uses: astral-sh/setup-uv@{uv_ref}",
                                updated_wf,
                            )
                            if updated_wf != wf_content:
                                if write_to_disk:
                                    yml_file.write_text(updated_wf, encoding="utf-8")
                                changes.append(
                                    f"Pinned action versions and commit hashes in {yml_file.name}"
                                )
                            break
            except Exception:
                pass

        # 3. ReadTheDocs configuration (.readthedocs.yaml)
        for rtd_name in [".readthedocs.yaml", ".readthedocs.yml"]:
            rtd_path = self.project_root / rtd_name
            if rtd_path.exists():
                try:
                    content = rtd_path.read_text(encoding="utf-8")
                    new_content = re.sub(
                        r"mkdocs:\s*\n(\s+configuration:.*)?",
                        "sphinx:\n  configuration: docs/conf.py\n",
                        content,
                    )
                    if new_content != content:
                        if write_to_disk:
                            rtd_path.write_text(new_content, encoding="utf-8")
                        changes.append(f"Updated {rtd_name} for Sphinx")
                except Exception:
                    pass

        return changes

    def _clean_obsolete_mkdocs_files(self, write_to_disk: bool) -> List[str]:
        """Remove obsolete MkDocs-specific generator scripts and hooks (e.g. scripts/gen_ref_nav.py).

        Why this cleanup is necessary:
        1. In MkDocs, dynamic generator plugins like `mkdocs-gen-files` execute scripts at build
           time to generate in-memory virtual markdown stubs (`with mkdocs_gen_files.open(...)`).
        2. During migration to Sphinx, `sphinx-mkdocs-migrate` statically materializes permanent,
           checked-in MyST markdown documentation stubs (e.g., in `docs/reference/`) using native
           Sphinx autodoc/autosummary directives.
        3. Once MkDocs dependencies are removed from the project's dependency manifest (`pyproject.toml`),
           any remaining generator script importing `mkdocs_gen_files` becomes broken and unrunnable
           (`ModuleNotFoundError: No module named 'mkdocs_gen_files'`).
        4. Leaving these scripts behind also triggers false positive failures in repo linters and formatters.
        5. Therefore, after all permanent documentation artifacts are synthesized, this cleanup phase
           safely unlinks obsolete generator scripts and removes their enclosing directory if it becomes empty.
        """
        removed: List[str] = []
        if not self.plan.source_mkdocs_config:
            return removed

        candidate_scripts = (
            self.plan.obsolete_files
            if self.plan.obsolete_files
            else detect_obsolete_generator_scripts(
                self.project_root,
                self.plan.source_mkdocs_config,
                additional_scripts=[
                    p.generator_script
                    for p in (
                        self.plan.documentation_plan.generated_pipelines
                        if self.plan.documentation_plan
                        else []
                    )
                    if p.generator_script
                ],
            )
        )

        for script_rel in candidate_scripts:
            script_path = self.project_root / script_rel
            if script_path.is_file():
                if write_to_disk:
                    try:
                        script_path.unlink()
                        removed.append(script_rel)
                        # Remove parent directory if empty (e.g. scripts/)
                        parent_dir = script_path.parent
                        if parent_dir != self.project_root and parent_dir.is_dir():
                            if not any(parent_dir.iterdir()):
                                parent_dir.rmdir()
                    except Exception:
                        pass
                else:
                    removed.append(script_rel)

        return sorted(removed)
