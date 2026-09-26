"""Transformation Engine executing MigrationPlan actions deterministically to produce MyST docs and conf.py."""
import difflib
import hashlib
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
            # Universal YAML frontmatter date object sanitizer
            if transformed_content.startswith("---"):
                parts = transformed_content.split("---", 2)
                if len(parts) >= 3:
                    import re
                    sanitized_header = re.sub(r"(:\s*)(\d{4}-\d{2}-\d{2})\b", r"\1\"\2\"", parts[1])
                    transformed_content = "---" + sanitized_header + "---" + parts[2]
            # If this is the main index.md and nav items exist, append semantic toctree directive
            if md_file.name == "index.md" and "```{toctree}" not in transformed_content:
                toctree_block = self._generate_semantic_toctree(nav_entries, all_md_files, docs_dir)
                if toctree_block:
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

    def _generate_semantic_toctree(self, nav_entries: List[NavigationItem], all_files: List[Path], docs_dir: Path) -> Optional[str]:
        """Generates a root MyST toctree directive strictly following semantic MkDocs navigation hierarchy."""
        ordered_docnames: List[str] = []

        def collect_nav_docs(items: List[NavigationItem]):
            for item in items:
                if item.path and not item.path.startswith("http"):
                    clean_p = item.path
                    if clean_p.endswith(".md"):
                        clean_p = clean_p[:-3]
                    if clean_p != "index" and clean_p not in ordered_docnames:
                        ordered_docnames.append(clean_p)
                if item.children:
                    collect_nav_docs(item.children)

        if nav_entries:
            collect_nav_docs(nav_entries)
        else:
            # Completeness fallback if no nav defined: preserve discovered documents
            for f in all_files:
                rel = f.relative_to(docs_dir)
                if rel.name != "index.md":
                    docname = str(rel.with_suffix(""))
                    if docname not in ordered_docnames:
                        ordered_docnames.append(docname)

        if not ordered_docnames:
            return None

        lines = [
            "```{toctree}",
            ":maxdepth: 2",
            ":caption: Contents:",
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

        lines = [
            f"# Configuration file for Sphinx documentation generator.",
            f"# Generated automatically by sphinx-mkdocs-migrate from plan: {self.plan.canonical_hash()[:12]}",
            f"",
            f"project = {repr(project_name)}",
            f"copyright = 'Documentation Authors'",
            f"author = 'Documentation Authors'",
            f"",
            f"extensions = [",
        ]
        for ext in sorted(extensions):
            lines.append(f"    {repr(ext)},")
        lines.extend([
            f"]",
            f"",
            f"source_suffix = {{",
            f"    '.md': 'markdown',",
            f"}}",
            f"",
            f"html_theme = {repr(theme)}",
        ])

        if theme == "sphinx_immaterial":
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
            f""
        ])
        return "\n".join(lines)
