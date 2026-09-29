# Configuration file for the Sphinx documentation builder.
import sys
from pathlib import Path

# Add src directory to sys.path for autodoc and dynamic metadata resolution
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from sphinx_mkdocs_migrate import __version__

# -- Project information -----------------------------------------------------
project = "sphinx-mkdocs-migrate"
copyright = "2026, Prateek Dagar"
author = "Prateek Dagar"
release = __version__
version = __version__

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_design",
    "sphinx_copybutton",
]

# MyST Parser Configuration
myst_enable_extensions = [
    "colon_fence",
    "dollarmath",
    "deflist",
    "attrs_block",
    "tasklist",
]
myst_heading_anchors = 3

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
root_doc = "index"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_title = "sphinx-mkdocs-migrate"
html_static_path = ["_static"]
