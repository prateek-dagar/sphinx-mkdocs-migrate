"""Sphinx conf.py configuration builder and code synthesizer."""

from __future__ import annotations
import pprint
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import MigrationPlan, ConfigMigrationProposal


def build_conf_py(
    plan: Optional[MigrationPlan] = None,
    cfg: Optional[ConfigMigrationProposal] = None,
    project_root: Optional[Path] = None,
    plan_hash: Optional[str] = None,
    has_generated_docs: bool = False,
) -> str:
    """Generates a clean Sphinx conf.py based strictly on MigrationPlan requirements."""
    if plan is not None:
        cfg = cfg or plan.proposed_sphinx_config
        project_root = project_root or Path(plan.project_root)
        plan_hash = plan_hash or plan.canonical_hash()[:12]
        has_generated_docs = bool(plan.generated_documents)

    project_name = cfg.project_name if cfg else "Documentation"
    theme = (
        cfg.theme.target_theme
        if cfg and cfg.theme and cfg.theme.target_theme
        else "sphinx_rtd_theme"
    )
    extensions = list(cfg.extensions_to_add) if cfg else ["myst_parser"]
    myst_exts = list(cfg.myst_enable_extensions) if cfg else ["colon_fence"]
    custom_opts = cfg.custom_options if cfg else {}

    copyright_val = custom_opts.get("copyright", "Documentation Authors")
    author_val = custom_opts.get("author", "Documentation Authors")

    hash_str = plan_hash if plan_hash else "synthetic"
    lines = [
        "# Configuration file for Sphinx documentation generator.",
        f"# Generated automatically by sphinx-mkdocs-migrate from plan: {hash_str}",
        "import os",
        "import sys",
    ]

    has_autodoc = any("autodoc" in ext for ext in extensions) or has_generated_docs
    if has_autodoc:
        if project_root is not None:
            src_candidate = project_root / "src"
            if src_candidate.exists() and src_candidate.is_dir():
                lines.append("sys.path.insert(0, os.path.abspath('../src'))")
        else:
            lines.append("sys.path.insert(0, os.path.abspath('../src'))")
        lines.append("sys.path.insert(0, os.path.abspath('..'))")

    lines.extend(
        [
            "",
            f"project = {repr(project_name)}",
            f"copyright = {repr(copyright_val)}",
            f"author = {repr(author_val)}",
            "",
            "extensions = [",
        ]
    )
    for ext in sorted(extensions):
        lines.append(f"    {repr(ext)},")
    lines.append("]")
    lines.extend(
        [
            "",
            "source_suffix = {",
            "    '.md': 'markdown',",
            "}",
            "",
            f"html_theme = {repr(theme)}",
        ]
    )

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
        "add_module_names",
        "autoclass_content",
        "autodoc_mock_imports",
    ]
    for key in standard_settings:
        if key in custom_opts and custom_opts[key] is not None:
            lines.append(f"{key} = {repr(custom_opts[key])}")

    if "html_theme_options" in custom_opts:
        formatted_opts = pprint.pformat(custom_opts["html_theme_options"], indent=4)
        lines.extend(
            [
                "",
                f"html_theme_options = {formatted_opts}",
            ]
        )
    elif theme == "sphinx_immaterial":
        lines.extend(
            [
                "",
                "html_theme_options = {",
                "    'font': False,",
                "    'globaltoc_collapse': False,",
                "}",
            ]
        )

    if "object_description_options" in custom_opts:
        formatted_obj_opts = pprint.pformat(
            custom_opts["object_description_options"], indent=4
        )
        lines.extend(
            [
                "",
                f"object_description_options = {formatted_obj_opts}",
            ]
        )
    elif theme == "sphinx_immaterial":
        lines.extend(
            [
                "",
                "object_description_options = [",
                "    ('py:.*', dict(include_fields_in_toc=False)),",
                "    ('py:parameter', dict(include_in_toc=False)),",
                "]",
            ]
        )

    lines.extend(
        [
            "",
            "myst_enable_extensions = [",
        ]
    )
    for m_ext in sorted(myst_exts):
        lines.append(f"    {repr(m_ext)},")
    lines.extend(["]", "", "myst_heading_anchors = 3", ""])

    if cfg and "sphinx.ext.autodoc" in cfg.extensions_to_add:
        lines.extend(
            [
                "",
                "import re",
                "_re_md_link = re.compile(r'(?<![!])\\[(?P<text>[^\\]\\n]+?)\\]\\((?P<url>[^\\)\\s]+)\\)')",
                "_re_cross_ref = re.compile(r'(?<![!])\\[(?P<text>[^\\]\\n]+?)\\]\\[(?P<target>[a-zA-Z_0-9\\.]+)\\]')",
                "_re_empty_cross_ref = re.compile(r'(?<![!])\\[(?P<target>[a-zA-Z_0-9\\.]+)\\]\\[\\]')",
                "_re_md_code = re.compile(r'(?<![:`])`(?P<code>[^`\\n]+?)`(?!_|\\`)')",
                "",
                "def process_docstrings(app, what, name, obj, options, lines):",
                "    if what == 'module' and getattr(options, 'members', None):",
                "        lines.clear()",
                "        return",
                "    for i in range(len(lines)):",
                "        if '[' in lines[i] and '][' in lines[i]:",
                "            lines[i] = _re_empty_cross_ref.sub(r':py:obj:`\\g<target>`', lines[i])",
                "            lines[i] = _re_cross_ref.sub(r':py:obj:`\\g<text> <\\g<target>>`', lines[i])",
                "        if '[' in lines[i] and '](' in lines[i]:",
                "            def repl(m):",
                "                clean_text = m.group('text').replace('`', '').strip()",
                "                return f'`{clean_text} <{m.group(\"url\")}>`_'",
                "            lines[i] = _re_md_link.sub(repl, lines[i])",
                "        if '`' in lines[i]:",
                "            lines[i] = _re_md_code.sub(r'``\\g<code>``', lines[i])",
                "",
                "def setup(app):",
                "    app.connect('autodoc-process-docstring', process_docstrings)",
                "",
            ]
        )

    return "\n".join(lines)
