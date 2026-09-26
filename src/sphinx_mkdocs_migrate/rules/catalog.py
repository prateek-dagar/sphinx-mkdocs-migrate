"""Comprehensive catalog of declarative migration rules with requirements and preservation constraints."""
from typing import List, Dict
from ..parsing.markdown_ir import NodeKind
from ..analyzer.models import Classification
from .models import MigrationRule, MigrationTarget, RuleKind

SUPPORTED_MYST_ADMONITIONS: Dict[str, str] = {
    "note": "note",
    "warning": "warning",
    "tip": "tip",
    "info": "note",
    "important": "important",
    "caution": "caution",
    "danger": "danger",
    "seealso": "seealso",
    "example": "admonition",
    "quote": "admonition",
    "abstract": "admonition",
    "bug": "admonition",
    "question": "admonition",
    "check": "admonition",
    "fail": "admonition",
    "success": "admonition",
}

DEFAULT_RULES: List[MigrationRule] = [
    # 1. Admonitions
    MigrationRule(
        rule_id="rule.admonition.myst",
        source_kind=NodeKind.ADMONITION,
        rule_kind=RuleKind.DETERMINISTIC,
        classification=Classification.TRANSFORM,
        target=MigrationTarget(
            framework="MyST",
            directive_name="note",
            required_extensions=["myst_parser"],
            required_py_packages=["myst-parser>=2.0.0"]
        ),
        preserves=["title", "body", "nesting", "admonition_type"],
        changes=["syntax", "fence_delimiters"],
        conditions={"type_map": SUPPORTED_MYST_ADMONITIONS},
        manual_if=["unsupported_custom_admonition_type"],
        description="Transforms MkDocs '!!! type' admonitions into MyST '{type}' or generic '{admonition}' directives."
    ),

    # 2. Content Tabs
    MigrationRule(
        rule_id="rule.tabs.sphinx_design",
        source_kind=NodeKind.TAB_SET,
        rule_kind=RuleKind.EXTENSION_DEPENDENT,
        classification=Classification.TRANSFORM,
        target=MigrationTarget(
            framework="sphinx-design",
            directive_name="tab-set",
            required_extensions=["sphinx_design"],
            required_py_packages=["sphinx-design>=0.5.0"]
        ),
        preserves=["tab_titles", "child_contents", "nesting"],
        changes=["syntax", "container_delimiters"],
        conditions={"has_tab_items": True},
        manual_if=[],
        description="Transforms PyMdown '=== \"Title\"' content tabs into sphinx-design '{tab-set}' and '{tab-item}' directives."
    ),

    # 3. Details / Dropdowns
    MigrationRule(
        rule_id="rule.details.sphinx_design",
        source_kind=NodeKind.DETAILS_DROPDOWN,
        rule_kind=RuleKind.EXTENSION_DEPENDENT,
        classification=Classification.TRANSFORM,
        target=MigrationTarget(
            framework="sphinx-design",
            directive_name="dropdown",
            required_extensions=["sphinx_design"],
            required_py_packages=["sphinx-design>=0.5.0"]
        ),
        preserves=["title", "open_state", "body", "nesting"],
        changes=["syntax", "container_delimiters"],
        conditions={},
        manual_if=[],
        description="Transforms PyMdown '???+ note \"Title\"' collapsible details into sphinx-design '{dropdown}' directives."
    ),

    # 4. mkdocstrings API Directives
    MigrationRule(
        rule_id="rule.api.autodoc",
        source_kind=NodeKind.API_DIRECTIVE,
        rule_kind=RuleKind.RULE_DEPENDENT,
        classification=Classification.MANUAL,
        target=MigrationTarget(
            framework="sphinx.ext.autodoc",
            directive_name="autoclass",
            required_extensions=["sphinx.ext.autodoc", "sphinx.ext.napoleon"],
            required_py_packages=["Sphinx>=7.0.0"]
        ),
        preserves=["symbol_path"],
        changes=["directive_syntax", "docstring_format_handling"],
        conditions={"symbol_format": "dotted_path"},
        manual_if=["unresolved_symbol_type", "custom_mkdocstrings_handler", "variadic_args_kwargs_docstrings"],
        description="Maps '::: symbol.path' to appropriate Sphinx autodoc directives with docstring convention review."
    ),

    # 5. Snippet Includes
    MigrationRule(
        rule_id="rule.snippet.literalinclude",
        source_kind=NodeKind.SNIPPET_INCLUDE,
        rule_kind=RuleKind.DETERMINISTIC,
        classification=Classification.TRANSFORM,
        target=MigrationTarget(
            framework="MyST",
            directive_name="literalinclude",
            required_extensions=["myst_parser"],
            required_py_packages=["myst-parser>=2.0.0"]
        ),
        preserves=["filepath"],
        changes=["include_syntax", "relative_root_resolution"],
        conditions={"filepath_specified": True},
        manual_if=["missing_target_file"],
        description="Transforms PyMdown '--8<-- \"path\"' snippet inclusions to MyST/Sphinx '{literalinclude}' or '{include}'."
    ),

    # 6. Mermaid Diagrams
    MigrationRule(
        rule_id="rule.mermaid.sphinxcontrib",
        source_kind=NodeKind.MERMAID_DIAGRAM,
        rule_kind=RuleKind.EXTENSION_DEPENDENT,
        classification=Classification.TRANSFORM,
        target=MigrationTarget(
            framework="sphinxcontrib-mermaid",
            directive_name="mermaid",
            required_extensions=["sphinxcontrib.mermaid"],
            required_py_packages=["sphinxcontrib-mermaid>=0.9.0"]
        ),
        preserves=["diagram_source", "line_mapping"],
        changes=["fence_name_to_directive"],
        conditions={"info_string": "mermaid"},
        manual_if=[],
        description="Maps '```mermaid' fenced code blocks to sphinxcontrib-mermaid '{mermaid}' directives."
    ),

    # 7. Document Links
    MigrationRule(
        rule_id="rule.link.myst_ref",
        source_kind=NodeKind.LINK_REF,
        rule_kind=RuleKind.DETERMINISTIC,
        classification=Classification.PRESERVE,
        target=MigrationTarget(
            framework="MyST",
            directive_name="doc_or_ref",
            required_extensions=["myst_parser"],
            required_py_packages=["myst-parser>=2.0.0"]
        ),
        preserves=["link_text", "target_url"],
        changes=["relative_md_extension_resolution"],
        conditions={},
        manual_if=["unresolved_internal_reference"],
        description="Preserves standard links and evaluates relative markdown links for cross-document reference resolution."
    ),
]
