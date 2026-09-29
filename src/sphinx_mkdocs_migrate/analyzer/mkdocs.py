"""Subsystem analyzer for mkdocs.yml configuration with robust YAML tag handling."""

import yaml
from pathlib import Path
from typing import Optional, List, Any, Dict
from .models import ConfigAnalysis, ThemePalette, ThemeFont


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
SafeMkDocsLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/", _ignore_unknown_tags
)


class MkDocsConfigAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def _find_config_file(self) -> Optional[Path]:
        """Discovers mkdocs.yml in root or common documentation subdirectories."""
        for candidate in [
            "mkdocs.yml",
            "mkdocs.yaml",
            "docs/en/mkdocs.yml",
            "docs/mkdocs.yml",
            ".mkdocs.yml",
            "mkdocs.template.yml",
        ]:
            path = self.project_root / candidate
            if path.exists():
                return path
        # Fallback search
        all_ymls = list(self.project_root.glob("*mkdocs*.yml")) + list(
            self.project_root.glob("*mkdocs*.yaml")
        )
        if all_ymls:
            return all_ymls[0]
        return None

    def analyze(self) -> ConfigAnalysis:
        mkdocs_file = self._find_config_file()
        if not mkdocs_file or not mkdocs_file.exists():
            return ConfigAnalysis()

        try:
            rel_config_path = str(mkdocs_file.relative_to(self.project_root))
        except ValueError:
            rel_config_path = str(mkdocs_file)

        try:
            content = mkdocs_file.read_text(encoding="utf-8")
            data = yaml.load(content, Loader=SafeMkDocsLoader) or {}
        except Exception:
            try:
                # Fallback simple load
                data = yaml.safe_load(mkdocs_file.read_text(encoding="utf-8")) or {}
            except Exception:
                return ConfigAnalysis(config_file_path=rel_config_path)

        theme_data = data.get("theme", {})
        theme_logo = None
        theme_icon = None
        theme_favicon = None
        theme_language = None
        theme_custom_dir = None
        theme_font = None
        theme_palette: List[ThemePalette] = []

        if isinstance(theme_data, str):
            theme_name = theme_data
            features = []
        elif isinstance(theme_data, dict):
            theme_name = theme_data.get("name", "mkdocs")
            features = theme_data.get("features", [])
            theme_logo = theme_data.get("logo")
            theme_icon = (
                theme_data.get("icon")
                if isinstance(theme_data.get("icon"), dict)
                else None
            )
            theme_favicon = theme_data.get("favicon")
            theme_language = theme_data.get("language")
            theme_custom_dir = theme_data.get("custom_dir")

            # Palette parsing (can be a dict or list of dicts in Material for MkDocs)
            pal = theme_data.get("palette")
            if isinstance(pal, dict):
                theme_palette.append(
                    ThemePalette(
                        scheme=pal.get("scheme"),
                        primary=pal.get("primary"),
                        accent=pal.get("accent"),
                        toggle_icon=pal.get("toggle", {}).get("icon")
                        if isinstance(pal.get("toggle"), dict)
                        else None,
                        toggle_name=pal.get("toggle", {}).get("name")
                        if isinstance(pal.get("toggle"), dict)
                        else None,
                    )
                )
            elif isinstance(pal, list):
                for p in pal:
                    if isinstance(p, dict):
                        theme_palette.append(
                            ThemePalette(
                                scheme=p.get("scheme"),
                                primary=p.get("primary"),
                                accent=p.get("accent"),
                                toggle_icon=p.get("toggle", {}).get("icon")
                                if isinstance(p.get("toggle"), dict)
                                else None,
                                toggle_name=p.get("toggle", {}).get("name")
                                if isinstance(p.get("toggle"), dict)
                                else None,
                            )
                        )

            # Font parsing
            font_data = theme_data.get("font")
            if isinstance(font_data, dict):
                theme_font = ThemeFont(
                    text=font_data.get("text"), code=font_data.get("code")
                )
        else:
            theme_name = "mkdocs"
            features = []

        plugins: List[str] = []
        plugins_config: Dict[str, Any] = {}
        for p in data.get("plugins", []):
            if isinstance(p, str):
                plugins.append(p)
                plugins_config[p] = {}
            elif isinstance(p, dict):
                for k, v in p.items():
                    plugins.append(k)
                    plugins_config[k] = v if isinstance(v, dict) else {}
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
            rel_parent = mkdocs_file.parent.relative_to(self.project_root).as_posix()
            if raw_docs_dir == "docs":
                adjusted_docs_dir = (
                    f"{rel_parent}/docs"
                    if (self.project_root / rel_parent / "docs").exists()
                    else rel_parent
                )
            else:
                adjusted_docs_dir = f"{rel_parent}/{raw_docs_dir}"
        else:
            adjusted_docs_dir = raw_docs_dir

        site_name = (
            data.get("site_name") or self.project_root.name.replace("-", " ").title()
        )

        # Extra CSS & JS
        extra_css = data.get("extra_css", [])
        if isinstance(extra_css, str):
            extra_css = [extra_css]
        extra_js = data.get("extra_javascript", [])
        if isinstance(extra_js, str):
            extra_js = [extra_js]
        extra = data.get("extra", {}) if isinstance(data.get("extra"), dict) else {}

        raw_exclude = data.get("exclude_docs", [])
        if isinstance(raw_exclude, str):
            exclude_docs = [s.strip() for s in raw_exclude.splitlines() if s.strip()]
        elif isinstance(raw_exclude, list):
            exclude_docs = [str(s) for s in raw_exclude]
        else:
            exclude_docs = []

        raw_use_dir = data.get("use_directory_urls")
        use_dir_urls = bool(raw_use_dir) if raw_use_dir is not None else None

        return ConfigAnalysis(
            config_file_path=rel_config_path,
            site_name=site_name,
            site_description=data.get("site_description"),
            site_author=data.get("site_author"),
            site_url=data.get("site_url"),
            repo_url=data.get("repo_url"),
            repo_name=data.get("repo_name"),
            edit_uri=data.get("edit_uri"),
            copyright=data.get("copyright"),
            docs_dir=adjusted_docs_dir,
            theme_name=theme_name,
            theme_logo=theme_logo,
            theme_icon=theme_icon,
            theme_favicon=theme_favicon,
            theme_language=theme_language,
            theme_custom_dir=theme_custom_dir,
            theme_palette=theme_palette,
            theme_font=theme_font,
            theme_features=features,
            plugins=plugins,
            plugins_config=plugins_config,
            markdown_extensions=normalized_md_exts,
            nav_raw=data.get("nav"),
            custom_hooks=hooks,
            extra_css=extra_css,
            extra_javascript=extra_js,
            extra=extra,
            exclude_docs=exclude_docs,
            use_directory_urls=use_dir_urls,
            raw_config_keys=list(data.keys()) if isinstance(data, dict) else [],
        )


def detect_obsolete_mkdocs_files(
    project_root: Path,
    mkdocs_config: Optional[ConfigAnalysis],
    additional_scripts: Optional[List[str]] = None,
) -> List[str]:
    """Detect obsolete MkDocs configuration files, generator scripts, and hooks that should be removed upon migration.

    1. MkDocs configuration files (e.g. mkdocs.yml, mkdocs.yaml) which are superseded by Sphinx conf.py.
    2. Generator scripts and hooks (e.g. scripts/gen_ref_nav.py) that run at build time under MkDocs
       (e.g., mkdocs-gen-files) to generate virtual stubs. Once Sphinx autodoc/autosummary is configured
       and MkDocs dependencies are removed, these scripts become obsolete, broken, and trigger repo lint failures.
    """
    obsolete: List[str] = []

    # 1. MkDocs configuration files
    if mkdocs_config and mkdocs_config.config_file_path:
        cfg_path = project_root / mkdocs_config.config_file_path
        if cfg_path.is_file() and mkdocs_config.config_file_path not in obsolete:
            obsolete.append(mkdocs_config.config_file_path)

    # Check common root configuration candidates if not already detected
    for candidate in ["mkdocs.yml", "mkdocs.yaml", ".mkdocs.yml", ".mkdocs.yaml"]:
        cand_path = project_root / candidate
        if cand_path.is_file() and candidate not in obsolete:
            obsolete.append(candidate)

    if not mkdocs_config:
        return sorted(obsolete)

    # 2. Generator scripts and hooks
    candidate_scripts: set[str] = set()
    gen_cfg = mkdocs_config.plugins_config.get("gen-files", {})
    if isinstance(gen_cfg, dict):
        for s in gen_cfg.get("scripts", []):
            if isinstance(s, str):
                candidate_scripts.add(s)

    if additional_scripts:
        for s in additional_scripts:
            if isinstance(s, str):
                candidate_scripts.add(s)

    for hook in mkdocs_config.custom_hooks or []:
        if isinstance(hook, str):
            candidate_scripts.add(hook)

    for s_rel in sorted(candidate_scripts):
        s_path = project_root / s_rel
        if s_path.is_file():
            try:
                content = s_path.read_text(encoding="utf-8")
            except Exception:
                content = ""
            if (
                "mkdocs" in content
                or "mkdocstrings" in content
                or (isinstance(gen_cfg, dict) and s_rel in gen_cfg.get("scripts", []))
            ):
                if s_rel not in obsolete:
                    obsolete.append(s_rel)

    return sorted(obsolete)


detect_obsolete_generator_scripts = detect_obsolete_mkdocs_files
