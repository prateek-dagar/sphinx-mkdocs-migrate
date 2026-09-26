"""Subsystem analyzer for mkdocs.yml configuration with robust YAML tag handling."""
import re
import yaml
from pathlib import Path
from typing import Optional, List, Any, Dict
from .models import ConfigAnalysis

class SafeMkDocsLoader(yaml.SafeLoader):
    """Custom YAML loader ignoring python-specific tags and environment constructors in mkdocs.yml."""
    pass

# Ignore all unknown custom YAML tags like !!python/name, !ENV, !relative, etc.
def _ignore_unknown_tags(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None

SafeMkDocsLoader.add_multi_constructor("!", _ignore_unknown_tags)
SafeMkDocsLoader.add_multi_constructor("tag:yaml.org,2002:python/", _ignore_unknown_tags)

class MkDocsConfigAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def _find_config_file(self) -> Optional[Path]:
        """Discovers mkdocs.yml in root or common documentation subdirectories."""
        for candidate in ["mkdocs.yml", "mkdocs.yaml", "docs/en/mkdocs.yml", "docs/mkdocs.yml", ".mkdocs.yml", "mkdocs.template.yml"]:
            path = self.project_root / candidate
            if path.exists():
                return path
        # Fallback search
        all_ymls = list(self.project_root.glob("*mkdocs*.yml")) + list(self.project_root.glob("*mkdocs*.yaml"))
        if all_ymls:
            return all_ymls[0]
        return None

    def analyze(self) -> ConfigAnalysis:
        mkdocs_file = self._find_config_file()
        if not mkdocs_file or not mkdocs_file.exists():
            return ConfigAnalysis()

        try:
            content = mkdocs_file.read_text(encoding="utf-8")
            data = yaml.load(content, Loader=SafeMkDocsLoader) or {}
        except Exception:
            try:
                # Fallback simple load
                data = yaml.safe_load(mkdocs_file.read_text(encoding="utf-8")) or {}
            except Exception:
                return ConfigAnalysis()

        theme_data = data.get("theme", {})
        if isinstance(theme_data, str):
            theme_name = theme_data
            features = []
        elif isinstance(theme_data, dict):
            theme_name = theme_data.get("name", "mkdocs")
            features = theme_data.get("features", [])
        else:
            theme_name = "mkdocs"
            features = []

        plugins = [p if isinstance(p, str) else list(p.keys())[0] for p in data.get("plugins", []) if isinstance(p, (str, dict))]
        hooks = data.get("hooks", [])

        # Normalize markdown_extensions list (strings or {name: dict_options})
        raw_md_exts = data.get("markdown_extensions", [])
        normalized_md_exts: List[str] = []
        if isinstance(raw_md_exts, list):
            for ext in raw_md_exts:
                if isinstance(ext, str):
                    normalized_md_exts.append(ext)
                elif isinstance(ext, dict):
                    normalized_md_exts.extend(list(ext.keys()))

        # Determine docs_dir: if config is in a subdirectory (e.g. docs/en/mkdocs.yml), adjust relative path
        raw_docs_dir = data.get("docs_dir", "docs")
        if mkdocs_file.parent != self.project_root:
            rel_parent = str(mkdocs_file.parent.relative_to(self.project_root))
            if raw_docs_dir == "docs":
                adjusted_docs_dir = f"{rel_parent}/docs" if (self.project_root / rel_parent / "docs").exists() else rel_parent
            else:
                adjusted_docs_dir = f"{rel_parent}/{raw_docs_dir}"
        else:
            adjusted_docs_dir = raw_docs_dir

        site_name = data.get("site_name") or self.project_root.name.replace("-", " ").title()

        return ConfigAnalysis(
            site_name=site_name,
            docs_dir=adjusted_docs_dir,
            theme_name=theme_name,
            theme_features=features,
            plugins=plugins,
            markdown_extensions=normalized_md_exts,
            nav_raw=data.get("nav"),
            custom_hooks=hooks
        )
