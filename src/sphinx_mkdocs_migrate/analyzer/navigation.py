"""Subsystem analyzer for MkDocs declarative navigation trees with path normalization and missing file detection."""

import fnmatch
from pathlib import Path, PurePosixPath
from typing import List, Any, Optional, Set
from ..constants import ROOT_DOC_CANDIDATE_STEMS
from .models import NavigationItem, NavigationAnalysis


def is_root_document_path(rel_path: str) -> bool:
    """Returns True if the relative path represents a top-level root document."""
    p = Path(rel_path)
    return len(p.parts) == 1 and p.stem.lower() in ROOT_DOC_CANDIDATE_STEMS


def _normalize_nav_path(raw_path: str) -> str:
    """Normalizes relative navigation paths (e.g. './guide/index.md#sec' -> 'guide/index.md')."""
    clean = raw_path.strip()
    if "#" in clean:
        clean = clean.split("#")[0]
    if clean.startswith("./"):
        clean = clean[2:]
    return str(PurePosixPath(clean))


class NavigationAnalyzer:
    """Parses, normalizes, and validates the raw nav tree from mkdocs.yml against discovered files."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def analyze(
        self, raw_nav: Optional[Any], discovered_md_files: List[Path], docs_dir: Path
    ) -> NavigationAnalysis:
        if raw_nav is None:
            return NavigationAnalysis(has_nav=False)

        parsed_items: List[NavigationItem] = []
        referenced_paths: Set[str] = set()

        def parse_node(node: Any) -> Optional[NavigationItem]:
            if isinstance(node, str):
                norm_p = _normalize_nav_path(node)
                referenced_paths.add(norm_p)
                title = Path(norm_p).stem.replace("-", " ").replace("_", " ").title()
                return NavigationItem(title=title, path=norm_p)
            elif isinstance(node, dict):
                for label, val in node.items():
                    if isinstance(val, str):
                        norm_p = _normalize_nav_path(val)
                        referenced_paths.add(norm_p)
                        return NavigationItem(title=str(label), path=norm_p)
                    elif isinstance(val, list):
                        child_items = [
                            c for c in (parse_node(item) for item in val) if c
                        ]
                        return NavigationItem(
                            title=str(label), path=None, children=child_items
                        )
            return None

        if isinstance(raw_nav, list):
            for entry in raw_nav:
                item = parse_node(entry)
                if item:
                    parsed_items.append(item)

        def count_and_depth(
            items: List[NavigationItem], current_depth: int = 1
        ) -> tuple[int, int]:
            total = 0
            max_d = current_depth
            for it in items:
                total += 1
                if it.children:
                    c_total, c_depth = count_and_depth(it.children, current_depth + 1)
                    total += c_total
                    max_d = max(max_d, c_depth)
            return total, max_d

        total_entries, depth = count_and_depth(parsed_items)

        # Build set of normalized discovered file paths relative to docs_dir
        discovered_rel_paths = set()
        for f in discovered_md_files:
            try:
                rel = str(f.relative_to(docs_dir)).replace("\\", "/")
                discovered_rel_paths.add(_normalize_nav_path(rel))
            except Exception:
                pass

        # Detect missing referenced files vs generated wildcard/pipeline navigation references
        missing_refs: List[str] = []
        generated_wildcard_refs: List[str] = []
        for ref in referenced_paths:
            if ref not in discovered_rel_paths and not ref.startswith("http"):
                if "..." in ref or "*" in ref or "|" in ref:
                    generated_wildcard_refs.append(ref)
                else:
                    missing_refs.append(ref)

        def is_covered_by_wildcard(disc_path: str) -> bool:
            for w_ref in generated_wildcard_refs:
                pat = w_ref.split("|", 1)[1].strip() if "|" in w_ref else w_ref.strip()
                pat = pat.replace("...", "").strip().lstrip("./").lstrip("/")
                if not pat:
                    continue
                if fnmatch.fnmatch(disc_path, pat):
                    return True
                if fnmatch.fnmatch(disc_path, f"{pat}.md"):
                    return True
                if pat.endswith("/*"):
                    base_prefix = pat[:-2]
                    if disc_path.startswith(f"{base_prefix}/"):
                        return True
            return False

        # Detect orphan documents (on disk, but not in nav, excluding root landing documents)
        orphans: List[str] = []
        for disc in discovered_rel_paths:
            if (
                disc not in referenced_paths
                and not is_root_document_path(disc)
                and not is_covered_by_wildcard(disc)
            ):
                orphans.append(disc)

        return NavigationAnalysis(
            has_nav=True,
            total_nav_entries=total_entries,
            max_depth=depth,
            missing_references=sorted(missing_refs),
            generated_wildcard_references=sorted(generated_wildcard_refs),
            orphan_documents=sorted(orphans),
            tree=parsed_items,
        )
