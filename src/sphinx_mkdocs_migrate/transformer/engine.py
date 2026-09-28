"""Transformation Engine executing MigrationPlan actions deterministically to produce MyST docs and conf.py."""
import difflib
import hashlib
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..planner.models import MigrationPlan
from ..analyzer.models import NavigationItem
from ..parsing.markdown import MarkdownParser
from .models import (
    ProjectTransformationReport,
    DocumentTransformationResult,
    TransformationStatus,
    ConfPyStatus
)
from .myst_transformer import MySTDocumentTransformer

class TransformationEngine:
    """Consumes a MigrationPlan to transform documentation and generate Sphinx artifacts via source-preserving patching."""

    def __init__(self, plan: MigrationPlan):
        self.plan = plan
        self.parser = MarkdownParser()
        self.project_root = Path(plan.project_root)

    def execute(self, write_to_disk: bool = False, overwrite_conf: bool = False) -> ProjectTransformationReport:
        """Executes document transformations and Sphinx scaffolding derived strictly from the plan."""
        doc_results: List[DocumentTransformationResult] = []
        actions_by_file: Dict[str, List] = {}
        for act in self.plan.document_actions:
            actions_by_file.setdefault(act.source_file, []).append(act)

        # 1. Discover all documentation files in plan
        docs_dir_name = self.plan.source_mkdocs_config.docs_dir if self.plan.source_mkdocs_config else "docs"
        docs_dir = self.project_root / docs_dir_name
        all_md_files: List[Path] = sorted(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else []

        documents_examined = len(all_md_files)
        documents_changed = 0
        files_written = 0

        # Discover root index file to append semantic toctree if needed for Sphinx navigation
        nav_entries = self.plan.navigation_analysis.tree if (self.plan.navigation_analysis and self.plan.navigation_analysis.has_nav) else []
        autorefs_targets = self._autorefs_target_documents()

        for md_file in all_md_files:
            source_file_rel = str(md_file.relative_to(self.project_root))
            orig_content = md_file.read_text(encoding="utf-8")
            source_fp = hashlib.sha256(orig_content.encode("utf-8")).hexdigest()[:16]

            actions = actions_by_file.get(source_file_rel, [])
            doc_ir = self.parser.parse_text(orig_content, file_path=source_file_rel)
            
            transformer = MySTDocumentTransformer(actions)
            transformed_content, applied_cnt, preserved_cnt, manual_cnt, unsupported_cnt, stale_cnt, stale_details = transformer.transform_document(
                doc_ir, orig_content
            )
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
                    import re
                    sanitized_header = re.sub(r"(:\s*)(\d{4}-\d{2}-\d{2})\b", r"\1\"\2\"", parts[1])
                    transformed_content = "---" + sanitized_header + "---" + parts[2]
            # Only the documentation root owns the site-level toctree.  Nested
            # ``index.md`` files are section/package landing pages and must keep
            # their own child toctrees (for example generated API modules).
            if md_file == docs_dir / "index.md":
                toctree_block = self._generate_semantic_toctree(nav_entries, all_md_files, docs_dir)
                if toctree_block:
                    if "```{toctree}" in transformed_content:
                        import re
                        transformed_content = re.sub(r"```\{toctree\}[\s\S]*?```", toctree_block, transformed_content)
                    else:
                        transformed_content = transformed_content.rstrip() + "\n\n" + toctree_block + "\n"

            is_modified = (orig_content != transformed_content)
            if is_modified:
                documents_changed += 1

            if manual_cnt > 0 and applied_cnt == 0:
                doc_status = TransformationStatus.MANUAL_REQUIRED
            elif is_modified:
                doc_status = TransformationStatus.APPLIED
            else:
                doc_status = TransformationStatus.UNCHANGED

            diff_str = None
            if is_modified:
                diff_lines = list(difflib.unified_diff(
                    orig_content.splitlines(keepends=True),
                    transformed_content.splitlines(keepends=True),
                    fromfile=f"a/{source_file_rel}",
                    tofile=f"b/{source_file_rel}"
                ))
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
                is_modified=is_modified
            )
            doc_results.append(result)

            if write_to_disk and is_modified:
                md_file.write_text(transformed_content, encoding="utf-8")
                files_written += 1

        generated_files: Dict[str, str] = {}
        # Check if root index.md exists; if not, create one
        root_index_path = docs_dir / "index.md"
        root_index_rel = f"{docs_dir_name}/index.md" if docs_dir_name else "index.md"
        has_root_index = any(Path(doc.target_file).as_posix() in (Path(root_index_rel).as_posix(), "index.md", f"{docs_dir_name}/index.md") for doc in doc_results)
        
        if not has_root_index:
            toctree_block = self._generate_semantic_toctree(nav_entries, all_md_files, docs_dir)
            index_title = self.plan.proposed_sphinx_config.project_name if self.plan.proposed_sphinx_config else "Documentation"
            generated_index_content = f"# {index_title}\n\n"
            if toctree_block:
                generated_index_content += toctree_block + "\n"
            
            generated_files[root_index_rel] = generated_index_content
            if write_to_disk:
                root_index_path.parent.mkdir(parents=True, exist_ok=True)
                root_index_path.write_text(generated_index_content, encoding="utf-8")
                files_written += 1
            
            doc_results.append(DocumentTransformationResult(
                source_file=root_index_rel,
                target_file=root_index_rel,
                original_content="",
                transformed_content=generated_index_content,
                source_fingerprint="generated_root_index",
                transforms_applied=1,
                status=TransformationStatus.APPLIED,
                is_modified=True
            ))
            documents_changed += 1

        # 1b. Materialize Planned Generated Documents (e.g. API reference stubs from gen-files/mkdocstrings)
        for gen_doc in self.plan.generated_documents:
            target_disk_path = self.project_root / gen_doc.target_path
            generated_files[gen_doc.target_path] = gen_doc.content
            
            orig_doc_content = target_disk_path.read_text(encoding="utf-8") if target_disk_path.exists() else ""
            is_mod = (orig_doc_content != gen_doc.content)
            
            if write_to_disk:
                target_disk_path.parent.mkdir(parents=True, exist_ok=True)
                target_disk_path.write_text(gen_doc.content, encoding="utf-8")
                files_written += 1
            
            if is_mod:
                documents_changed += 1

            doc_results.append(DocumentTransformationResult(
                source_file=gen_doc.target_path,
                target_file=gen_doc.target_path,
                original_content=orig_doc_content,
                transformed_content=gen_doc.content,
                source_fingerprint=f"generated_{gen_doc.generator_plugin}",
                transforms_applied=1,
                status=TransformationStatus.APPLIED if is_mod else TransformationStatus.UNCHANGED,
                is_modified=is_mod
            ))

        # 2. Generate Sphinx conf.py scaffolding purely derived from plan with collision policy
        conf_py_content = self._generate_conf_py()
        conf_target_key = f"{docs_dir_name}/conf.py"
        generated_files[conf_target_key] = conf_py_content

        conf_disk_path = self.project_root / docs_dir_name / "conf.py"
        conf_status = ConfPyStatus.CREATED
        conf_diff = None

        if conf_disk_path.exists():
            existing_conf = conf_disk_path.read_text(encoding="utf-8")
            if existing_conf == conf_py_content:
                conf_status = ConfPyStatus.UNCHANGED
            else:
                conf_status = ConfPyStatus.CONFLICT
                diff_lines = list(difflib.unified_diff(
                    existing_conf.splitlines(keepends=True),
                    conf_py_content.splitlines(keepends=True),
                    fromfile=f"a/{docs_dir_name}/conf.py (existing)",
                    tofile=f"b/{docs_dir_name}/conf.py (planned)"
                ))
                conf_diff = "".join(diff_lines)

        if write_to_disk:
            if not conf_disk_path.exists() or conf_status == ConfPyStatus.UNCHANGED or overwrite_conf:
                conf_disk_path.parent.mkdir(parents=True, exist_ok=True)
                conf_disk_path.write_text(conf_py_content, encoding="utf-8")
                files_written += 1

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
            dry_run=not write_to_disk
        )

    def _autorefs_target_documents(self) -> Dict[str, Path]:
        """Map known Python module identities to generated documentation paths."""
        if not self.plan.source_mkdocs_config or "autorefs" not in self.plan.source_mkdocs_config.plugins:
            return {}

        targets: Dict[str, Path] = {}
        currentmodule_re = re.compile(r"^\.\. currentmodule::\s+(?P<name>[\w.]+)\s*$", re.MULTILINE)
        for proposal in self.plan.generated_documents:
            match = currentmodule_re.search(proposal.content)
            if match:
                targets[match.group("name")] = self.project_root / proposal.target_path
        return targets

    @staticmethod
    def _transform_autorefs_links(
        content: str,
        source_path: Path,
        docs_dir: Path,
        targets: Dict[str, Path],
    ) -> Tuple[str, int]:
        """Rewrite resolvable MkDocs autorefs compact links to relative MyST links."""
        reference_re = re.compile(r"(?<!!)\[(?P<label>[^\]\n]+)\]\[(?P<target>[A-Za-z_]\w*(?:\.\w+)+)\]")
        source_dir = source_path.parent
        changes = 0

        def replace(match: re.Match) -> str:
            nonlocal changes
            target_doc = targets.get(match.group("target"))
            if target_doc is None:
                return match.group(0)
            relative = Path(os.path.relpath(target_doc, source_dir)).as_posix()
            changes += 1
            return f"[{match.group('label')}]({relative})"

        return reference_re.sub(replace, content), changes

    def _generate_semantic_toctree(self, nav_entries: List[NavigationItem], all_files: List[Path], docs_dir: Path) -> Optional[str]:
        """Generate the root toctree without flattening section landing pages.

        A MkDocs section with a generated/package index must point at that
        index from the root.  Its descendants are rendered by the index's own
        toctree, allowing Sphinx to retain the same expandable hierarchy.
        """
        ordered_docnames: List[str] = []

        docs_prefix = docs_dir.relative_to(self.project_root)
        generated_targets = set()
        for proposal in self.plan.generated_documents:
            try:
                generated_targets.add(
                    Path(proposal.target_path).relative_to(docs_prefix).with_suffix("").as_posix()
                )
            except ValueError:
                continue

        def resolve_path(raw_path: str) -> Optional[str]:
            """Resolve a page or a literate-nav wildcard to a Sphinx docname."""
            clean_p = raw_path.strip()
            if clean_p.startswith("http"):
                return None

            if "|" in clean_p:
                wildcard_parts = [part.strip() for part in clean_p.split("|") if "*" in part]
                if wildcard_parts:
                    wildcard = wildcard_parts[0]
                    base_dir = wildcard.replace("/*", "").replace("*", "").strip("/")
                    index_doc = f"{base_dir}/index" if base_dir else "index"
                    if (docs_dir / f"{index_doc}.md").exists() or index_doc in generated_targets:
                        return index_doc
                    target_dir = docs_dir / base_dir
                    if target_dir.is_dir():
                        # No landing page exists.  Keep the legacy fallback for
                        # callers that cannot express a nested section.
                        return None
                    return None
                clean_p = next((part.strip() for part in clean_p.split("|") if part.strip() != "..."), "")

            clean_p = clean_p.split("#", 1)[0].replace("\\", "/").strip("/")
            if clean_p.endswith(".md"):
                clean_p = clean_p[:-3]
            if not clean_p:
                return None
            if (docs_dir / clean_p / "index.md").exists():
                return f"{clean_p}/index"
            if clean_p in generated_targets:
                return clean_p
            if f"{clean_p}/index" in generated_targets:
                return f"{clean_p}/index"
            return clean_p

        def add_doc(title: Optional[str], docname: str) -> None:
            if docname == "index":
                entry = f"{title or 'Home'} <self>"
            elif title and title.lower() != Path(docname).stem.lower():
                entry = f"{title} <{docname}>"
            else:
                entry = docname
            if entry not in ordered_docnames:
                ordered_docnames.append(entry)

        def section_landing(item: NavigationItem) -> Optional[str]:
            """Find the page that represents a section in the target tree."""
            if item.path:
                return resolve_path(item.path)
            for child in item.children:
                candidate = section_landing(child)
                if candidate:
                    return candidate
            return None

        def expand_wildcard(raw_path: str) -> None:
            """Compatibility fallback for a wildcard with no index/landing page."""
            wildcard = next((part.strip() for part in raw_path.split("|") if "*" in part), "")
            base_dir = wildcard.replace("/*", "").replace("*", "").strip("/")
            target_dir = docs_dir / base_dir
            if not target_dir.is_dir():
                return
            for path in sorted(target_dir.rglob("*.md")):
                if path.name != "index.md":
                    add_doc(None, path.relative_to(docs_dir).with_suffix("").as_posix())

        def collect_nav_docs(items: List[NavigationItem]):
            for item in items:
                target = resolve_path(item.path) if item.path else None
                if target:
                    add_doc(item.title, target)
                    continue
                if item.path and "*" in item.path:
                    expand_wildcard(item.path)
                    continue
                if item.children:
                    landing = section_landing(item)
                    if landing:
                        add_doc(item.title, landing)
                    else:
                        # A section without a landing document cannot be nested
                        # in a Sphinx toctree, so retain its explicitly listed
                        # pages rather than inventing an untraceable page.
                        collect_nav_docs(item.children)

        if nav_entries:
            collect_nav_docs(nav_entries)
        else:
            # Fallback if no nav defined: preserve discovered documents deterministically
            for f in all_files:
                rel = f.relative_to(docs_dir)
                if rel.name != "index.md":
                    docname = rel.with_suffix("").as_posix()
                    if docname not in ordered_docnames:
                        ordered_docnames.append(docname)

        if not ordered_docnames:
            return None

        lines = [
            "```{toctree}",
            ":hidden:",
            ":maxdepth: 2",
            ""
        ]
        for docname in ordered_docnames:
            lines.append(docname)
        lines.append("```")
        return "\n".join(lines)

    def _generate_conf_py(self) -> str:
        """Generates a clean Sphinx conf.py based strictly on MigrationPlan requirements."""
        cfg = self.plan.proposed_sphinx_config
        project_name = cfg.project_name if cfg else "Documentation"
        theme = cfg.theme.target_theme if cfg and cfg.theme.target_theme else "sphinx_rtd_theme"
        extensions = cfg.extensions_to_add if cfg else ["myst_parser"]
        myst_exts = cfg.myst_enable_extensions if cfg else ["colon_fence"]
        custom_opts = cfg.custom_options if cfg else {}

        copyright_val = custom_opts.get("copyright", "Documentation Authors")
        author_val = custom_opts.get("author", "Documentation Authors")

        lines = [
            f"# Configuration file for Sphinx documentation generator.",
            f"# Generated automatically by sphinx-mkdocs-migrate from plan: {self.plan.canonical_hash()[:12]}",
            f"import os",
            f"import sys",
        ]

        has_autodoc = any("autodoc" in ext for ext in extensions) or bool(self.plan.generated_documents)
        if has_autodoc:
            src_candidate = self.project_root / "src"
            if src_candidate.exists() and src_candidate.is_dir():
                lines.append("sys.path.insert(0, os.path.abspath('../src'))")
            lines.append("sys.path.insert(0, os.path.abspath('..'))")

        lines.extend([
            "",
            f"project = {repr(project_name)}",
            f"copyright = {repr(copyright_val)}",
            f"author = {repr(author_val)}",
            "",
            "extensions = [",
        ])
        for ext in sorted(extensions):
            lines.append(f"    {repr(ext)},")
        lines.append("]")
        lines.extend([
            "",
            "source_suffix = {",
            "    '.md': 'markdown',",
            "}",
            "",
            f"html_theme = {repr(theme)}",
        ])

        # Standard scalar and list Sphinx configuration keys
        standard_settings = [
            "html_logo",
            "html_favicon",
            "language",
            "html_css_files",
            "html_js_files",
            "html_title",
            "html_baseurl",
            "version",
            "release",
            "autosummary_generate",
        ]
        for key in standard_settings:
            if key in custom_opts and custom_opts[key] is not None:
                lines.append(f"{key} = {repr(custom_opts[key])}")

        if "html_theme_options" in custom_opts:
            import pprint
            formatted_opts = pprint.pformat(custom_opts["html_theme_options"], indent=4)
            lines.extend([
                f"",
                f"html_theme_options = {formatted_opts}",
            ])
        elif theme == "sphinx_immaterial":
            lines.extend([
                f"",
                f"html_theme_options = {{",
                f"    'font': False,",
                f"    'globaltoc_collapse': False,",
                f"}}",
            ])

        lines.extend([
            f"",
            f"myst_enable_extensions = [",
        ])
        for m_ext in sorted(myst_exts):
            lines.append(f"    {repr(m_ext)},")
        lines.extend([
            f"]",
            f"",
            f"myst_heading_anchors = 3",
            f"",
            f"autodoc_mock_imports = ['msgspec', 'orjson']",
            f""
        ])
        return "\n".join(lines)
