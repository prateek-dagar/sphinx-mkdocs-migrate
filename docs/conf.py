# Configuration file for the Sphinx documentation builder.
import os
import sys
from pathlib import Path

# -- Project information -----------------------------------------------------
project = "sphinx-mkdocs-migrate"
copyright = "2026, Prateek Dagar"
author = "Prateek Dagar"
release = "0.1.0b1"

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

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_title = "sphinx-mkdocs-migrate"
html_static_path = ["_static"]
