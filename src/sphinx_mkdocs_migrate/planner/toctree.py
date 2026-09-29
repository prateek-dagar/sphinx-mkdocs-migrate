"""Semantic navigation and Sphinx toctree layout planner."""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Set
from ..analyzer.models import NavigationItem
from ..constants import ROOT_DOC_CANDIDATE_STEMS


def resolve_navigation_docnames(
    nav_entries: List[NavigationItem],
    all_files: List[Path],
    docs_dir: Path,
    project_root: Optional[Path] = None,
    generated_targets: Optional[Set[str]] = None,
) -> List[str]:
    """Resolve ordered Sphinx document names from MkDocs navigation items and file discoveries."""
    ordered_docnames: List[str] = []
    generated_targets = generated_targets or set()

    def resolve_path(raw_path: str) -> Optional[str]:
        """Resolve a page or a literate-nav wildcard to a Sphinx docname."""
        clean_p = raw_path.strip()
        if clean_p.startswith("http"):
            return None

        if "|" in clean_p:
            wildcard_parts = [
                part.strip() for part in clean_p.split("|") if "*" in part
            ]
            if wildcard_parts:
                wildcard = wildcard_parts[0]
                base_dir = wildcard.replace("/*", "").replace("*", "").strip("/")
                index_doc = f"{base_dir}/index" if base_dir else "index"
                if (
                    docs_dir / f"{index_doc}.md"
                ).exists() or index_doc in generated_targets:
                    return index_doc
                target_dir = docs_dir / base_dir
                if target_dir.is_dir():
                    # No landing page exists. Keep legacy fallback.
                    return None
                return None
            clean_p = next(
                (part.strip() for part in clean_p.split("|") if part.strip() != "..."),
                "",
            )

        clean_p = clean_p.split("#", 1)[0].replace("\\", "/").strip("/")
        if clean_p.endswith(".md"):
            clean_p = clean_p[:-3]
        if not clean_p:
            return None
        for stem in ROOT_DOC_CANDIDATE_STEMS:
            if (docs_dir / clean_p / f"{stem}.md").exists():
                return f"{clean_p}/{stem}"
        if clean_p in generated_targets:
            return clean_p
        for stem in ROOT_DOC_CANDIDATE_STEMS:
            if f"{clean_p}/{stem}" in generated_targets:
                return f"{clean_p}/{stem}"
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
        wildcard = next(
            (part.strip() for part in raw_path.split("|") if "*" in part), ""
        )
        base_dir = wildcard.replace("/*", "").replace("*", "").strip("/")
        target_dir = docs_dir / base_dir
        if not target_dir.is_dir():
            return
        for path in sorted(target_dir.rglob("*.md")):
            if path.stem.lower() not in ROOT_DOC_CANDIDATE_STEMS:
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
                    # in a Sphinx toctree, so retain its explicitly listed pages.
                    collect_nav_docs(item.children)

    if nav_entries:
        collect_nav_docs(nav_entries)
    else:
        # Fallback if no nav defined: preserve discovered documents deterministically
        for f in all_files:
            rel = f.relative_to(docs_dir)
            if rel.stem.lower() not in ROOT_DOC_CANDIDATE_STEMS:
                docname = rel.with_suffix("").as_posix()
                if docname not in ordered_docnames:
                    ordered_docnames.append(docname)

    return ordered_docnames


def build_semantic_toctree(
    nav_entries: List[NavigationItem],
    all_files: List[Path],
    docs_dir: Path,
    project_root: Optional[Path] = None,
    generated_targets: Optional[Set[str]] = None,
    hidden: bool = True,
    maxdepth: int = 2,
) -> Optional[str]:
    """Generate the root toctree directive block without flattening section landing pages."""
    ordered_docnames = resolve_navigation_docnames(
        nav_entries=nav_entries,
        all_files=all_files,
        docs_dir=docs_dir,
        project_root=project_root,
        generated_targets=generated_targets,
    )

    if not ordered_docnames:
        return None

    lines = [
        "```{toctree}",
    ]
    if hidden:
        lines.append(":hidden:")
    if maxdepth > 0:
        lines.append(f":maxdepth: {maxdepth}")
    lines.append("")
    for docname in ordered_docnames:
        lines.append(docname)
    lines.append("```")
    return "\n".join(lines)
