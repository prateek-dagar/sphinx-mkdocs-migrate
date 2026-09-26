"""Declarative Policy Engine mapping detected source features to Sphinx extensions, packages, MyST extensions, and configs."""
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from ..analyzer.models import Classification

class SourceFeatureCategory(str, Enum):
    THEME_FEATURE = "THEME_FEATURE"             # MkDocs theme feature (e.g. content.code.copy)
    MARKDOWN_EXTENSION = "MARKDOWN_EXTENSION"   # Markdown extension (e.g. pymdownx.tabbed, def_list)
    PLUGIN = "PLUGIN"                           # MkDocs plugin (e.g. search, autorefs, mkdocstrings)
    DOCUMENT_SYNTAX = "DOCUMENT_SYNTAX"         # In-doc syntax construct (e.g. math dollar, tasklist)

class FeaturePolicyRule(BaseModel):
    """Declarative, multi-faceted policy rule mapping an empirical source feature to migration requirements and actions."""
    feature_id: str
    category: SourceFeatureCategory
    classification: Classification = Classification.PRESERVE
    
    # Requirements
    required_packages: List[str] = Field(default_factory=list)      # Third-party PyPI packages only (e.g. ['sphinx-copybutton>=0.5.2'])
    required_extensions: List[str] = Field(default_factory=list)    # Sphinx extensions (built-in or third-party, e.g. ['sphinx.ext.autodoc'])
    myst_extensions: List[str] = Field(default_factory=list)        # MyST syntax extensions (e.g. ['dollarmath'])
    
    # Configuration
    conf_settings: Dict[str, Any] = Field(default_factory=dict)     # Sphinx conf.py settings to generate
    
    # Transformation / Manual action
    requires_document_transform: bool = False
    rationale: str
    manual_instruction: Optional[str] = None
    
    # Lineage / Empirical provenance
    observed_in_corpus: bool = True
    observed_in_corpus_repos: List[str] = Field(default_factory=list)

class FeaturePolicyCatalog:
    """Catalog of empirical policies derived strictly from real-world corpus observations across 9 repositories."""

    RULES: Dict[str, FeaturePolicyRule] = {
        # --- Theme Features ---
        "content.code.copy": FeaturePolicyRule(
            feature_id="content.code.copy",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.TRANSFORM,
            required_packages=["sphinx-copybutton>=0.5.2"],
            required_extensions=["sphinx_copybutton"],
            rationale="Provides code-block copy button behavior in Sphinx matching MkDocs Material content.code.copy.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "polars", "pydantic", "pyjanitor"]
        ),
        "content.tabs.link": FeaturePolicyRule(
            feature_id="content.tabs.link",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.TRANSFORM,
            required_packages=["sphinx-design>=0.5.0"],
            required_extensions=["sphinx_design"],
            rationale="Provides synchronized tab switching in Sphinx matching MkDocs Material content.tabs.link.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "polars", "pydantic"]
        ),
        "content.code.annotate": FeaturePolicyRule(
            feature_id="content.code.annotate",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.MANUAL,
            rationale="Code annotations '(1)' in code blocks require manual conversion to Sphinx callouts or inline comments.",
            manual_instruction="Review code annotations (1), (2) and convert to Sphinx callouts or inline comments.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "pydantic"]
        ),
        "navigation.instant": FeaturePolicyRule(
            feature_id="navigation.instant",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: single-page instant navigation is an SPA interaction model not required for static Sphinx HTML correctness.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "polars", "pydantic", "pyjanitor"]
        ),
        "navigation.top": FeaturePolicyRule(
            feature_id="navigation.top",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: back-to-top button is handled natively by modern Sphinx HTML theme templates.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "pydantic", "pyjanitor"]
        ),
        "toc.follow": FeaturePolicyRule(
            feature_id="toc.follow",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: scrollspy table of contents tracking is built-in across standard Sphinx HTML themes.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "pydantic", "pyjanitor"]
        ),
        "navigation.tabs": FeaturePolicyRule(
            feature_id="navigation.tabs",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: header navigation tabs are rendered by Sphinx theme layout based on toctree hierarchy.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "polars", "pydantic"]
        ),
        "navigation.tracking": FeaturePolicyRule(
            feature_id="navigation.tracking",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: active URL tracking in sidebar navigation is handled by theme template logic.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "polars", "pydantic"]
        ),
        "navigation.sections": FeaturePolicyRule(
            feature_id="navigation.sections",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: collapsible sidebar sections are governed by theme sidebar toctree depth.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material", "polars", "pydantic"]
        ),
        "navigation.footer": FeaturePolicyRule(
            feature_id="navigation.footer",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: previous/next navigation footer links are generated automatically by Sphinx.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "polars"]
        ),
        "navigation.indexes": FeaturePolicyRule(
            feature_id="navigation.indexes",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: section index pages are represented as index.md in Sphinx toctree.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "polars"]
        ),
        "search.suggest": FeaturePolicyRule(
            feature_id="search.suggest",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: search auto-complete is provided by theme client search integration.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material", "pydantic"]
        ),
        "search.highlight": FeaturePolicyRule(
            feature_id="search.highlight",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.PRESERVE,
            rationale="No equivalent required: search term highlighting is built into Sphinx doctools.js.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material"]
        ),
        "search.share": FeaturePolicyRule(
            feature_id="search.share",
            category=SourceFeatureCategory.THEME_FEATURE,
            classification=Classification.UNSUPPORTED,
            rationale="Unsupported: MkDocs Material deep search query URL sharing has no static Sphinx equivalent.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs-material"]
        ),

        # --- Markdown Extensions ---
        "pymdownx.tabbed": FeaturePolicyRule(
            feature_id="pymdownx.tabbed",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.TRANSFORM,
            required_packages=["sphinx-design>=0.5.0"],
            required_extensions=["sphinx_design"],
            requires_document_transform=True,
            rationale="Tabbed blocks require transformation to sphinx-design {tab-set} / {tab-item} directives.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material", "polars", "pydantic"]
        ),
        "pymdownx.details": FeaturePolicyRule(
            feature_id="pymdownx.details",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.TRANSFORM,
            required_packages=["sphinx-design>=0.5.0"],
            required_extensions=["sphinx_design"],
            requires_document_transform=True,
            rationale="Collapsible details blocks require transformation to sphinx-design {dropdown} directives.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material", "polars", "pydantic"]
        ),
        "pymdownx.superfences": FeaturePolicyRule(
            feature_id="pymdownx.superfences",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["colon_fence"],
            rationale="Allows nested code fences and ::: directive syntax via MyST colon_fence.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["httpx", "mkdocs", "mkdocs-material", "polars", "pydantic", "pyjanitor"]
        ),
        "pymdownx.arithmatex": FeaturePolicyRule(
            feature_id="pymdownx.arithmatex",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["dollarmath"],
            rationale="Enables LaTeX math rendering with $ and 22323 delimiters via MyST dollarmath extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material", "polars", "pydantic"]
        ),
        "pymdownx.snippets": FeaturePolicyRule(
            feature_id="pymdownx.snippets",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.TRANSFORM,
            requires_document_transform=True,
            rationale="File snippet includes (--8<--) require document transformation to MyST {include} or literalinclude directives.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "mkdocs-material", "polars"]
        ),
        "pymdownx.emoji": FeaturePolicyRule(
            feature_id="pymdownx.emoji",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.MANUAL,
            rationale="Emoji shortcodes (:smile:) and Twemoji icon syntax require manual conversion to Unicode or Sphinx custom roles.",
            manual_instruction="Inspect documents for emoji shortcodes (:icon-name:) and convert to Unicode characters or Sphinx roles.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material", "polars", "pydantic"]
        ),
        "pymdownx.tasklist": FeaturePolicyRule(
            feature_id="pymdownx.tasklist",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["tasklist"],
            rationale="Enables task list checkbox rendering via MyST tasklist extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material"]
        ),
        "def_list": FeaturePolicyRule(
            feature_id="def_list",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["deflist"],
            rationale="Enables definition list parsing via MyST deflist extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "mkdocs-material"]
        ),
        "attr_list": FeaturePolicyRule(
            feature_id="attr_list",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["attrs_block"],
            rationale="Enables block attribute parsing via MyST attrs_block extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "mkdocs-material", "polars"]
        ),
        "admonition": FeaturePolicyRule(
            feature_id="admonition",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["colon_fence"],
            rationale="Admonitions map cleanly to standard MyST / Sphinx admonition directives.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "httpx", "mkdocs-material", "polars", "pydantic", "pyjanitor"]
        ),
        "mdx_gh_links": FeaturePolicyRule(
            feature_id="mdx_gh_links",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.TRANSFORM,
            required_packages=[],  # Built-in Sphinx extension
            required_extensions=["sphinx.ext.extlinks"],
            conf_settings={"extlinks": {"gh-issue": ("https://github.com/%s", "#%s")}},
            rationale="GitHub issue/PR shortcuts map to Sphinx built-in extlinks extension with repository configuration.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs"]
        ),
        "mkdocs-click": FeaturePolicyRule(
            feature_id="mkdocs-click",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.TRANSFORM,
            required_packages=["sphinx-click>=6.0.0"],
            required_extensions=["sphinx_click"],
            rationale="Click CLI documentation maps to sphinx-click extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs"]
        ),
        "callouts": FeaturePolicyRule(
            feature_id="callouts",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            myst_extensions=["colon_fence"],
            rationale="Callout boxes map to standard MyST / Sphinx admonitions.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs"]
        ),
        "tables": FeaturePolicyRule(
            feature_id="tables",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            rationale="GFM tables are natively parsed and supported by MyST Parser.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "pydantic"]
        ),
        "footnotes": FeaturePolicyRule(
            feature_id="footnotes",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            rationale="Footnote references are natively parsed and supported by MyST Parser.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material", "polars"]
        ),
        "toc": FeaturePolicyRule(
            feature_id="toc",
            category=SourceFeatureCategory.MARKDOWN_EXTENSION,
            classification=Classification.PRESERVE,
            rationale="Table of contents is natively constructed by Sphinx toctree.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "mkdocs-material", "pydantic", "pyjanitor"]
        ),

        # --- Plugins ---
        "search": FeaturePolicyRule(
            feature_id="search",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.PRESERVE,
            rationale="Search index generation is built-in natively into all standard Sphinx HTML builders.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "mkdocs-material", "polars", "pydantic", "pyjanitor"]
        ),
        "autorefs": FeaturePolicyRule(
            feature_id="autorefs",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.TRANSFORM,
            required_packages=[],  # Built-in Sphinx extension
            required_extensions=["sphinx.ext.autodoc"],
            rationale="Cross-referencing Python API objects maps to Sphinx built-in autodoc domain roles.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "pyjanitor"]
        ),
        "mkdocstrings": FeaturePolicyRule(
            feature_id="mkdocstrings",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.TRANSFORM,
            required_packages=[],  # Built-in Sphinx extensions
            required_extensions=["sphinx.ext.autodoc", "sphinx.ext.napoleon"],
            rationale="Python docstrings extraction maps to Sphinx built-in autodoc and napoleon extensions with AST symbol resolution.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["fastapi", "mkdocs", "pydantic", "pyjanitor"]
        ),
        "redirects": FeaturePolicyRule(
            feature_id="redirects",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.TRANSFORM,
            required_packages=["sphinx-reredirects>=0.1.5"],
            required_extensions=["sphinx_reredirects"],
            rationale="HTML redirects map to the sphinx-reredirects extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs", "polars", "pydantic"]
        ),
        "blog": FeaturePolicyRule(
            feature_id="blog",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.TRANSFORM,
            required_packages=["ablog>=0.11.0"],
            required_extensions=["ablog"],
            rationale="MkDocs Material blog plugin maps to the standard Sphinx ABlog extension.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material"]
        ),
        "markdown-exec": FeaturePolicyRule(
            feature_id="markdown-exec",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.MANUAL,
            rationale="Live markdown execution during build requires manual migration to jupyter-sphinx or myst-nb.",
            manual_instruction="Review markdown-exec code execution blocks and evaluate myst-nb or jupyter-sphinx.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["polars"]
        ),
        "macros": FeaturePolicyRule(
            feature_id="macros",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.MANUAL,
            rationale="Jinja macros in markdown files require manual migration to custom Sphinx directives or docutils roles.",
            manual_instruction="Review jinja macros and migrate to custom Sphinx directives or conf.py rst_prolog / myst substitutions.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["polars"]
        ),
        "literate-nav": FeaturePolicyRule(
            feature_id="literate-nav",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.PRESERVE,
            rationale="Navigation trees are derived directly by Sphinx toctree directives across document indices.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs"]
        ),
        "minify": FeaturePolicyRule(
            feature_id="minify",
            category=SourceFeatureCategory.PLUGIN,
            classification=Classification.PRESERVE,
            rationale="HTML/CSS minification is handled at the deployment stage in Sphinx workflows.",
            observed_in_corpus=True,
            observed_in_corpus_repos=["mkdocs-material"]
        ),
    }

    @classmethod
    def lookup(cls, feature_id: str) -> Optional[FeaturePolicyRule]:
        """Look up policy for a feature identifier."""
        return cls.RULES.get(feature_id)


class PolicyEngine:
    """Policy evaluation engine translating detected source features into deterministic migration outputs."""

    def __init__(self, catalog: Optional[FeaturePolicyCatalog] = None):
        self.catalog = catalog or FeaturePolicyCatalog()

    def evaluate_feature(self, feature_id: str) -> Optional[FeaturePolicyRule]:
        """Evaluates a single feature against the policy catalog."""
        return self.catalog.lookup(feature_id)
