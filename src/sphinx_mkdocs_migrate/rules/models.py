"""Data models for declarative migration rules, requirements, and preservation constraints."""
import hashlib
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from ..parsing.markdown_ir import NodeKind, BaseIRNode
from ..analyzer.models import Classification

class RuleKind(str, Enum):
    """How the mapping rule is determined and evaluated."""
    DETERMINISTIC = "DETERMINISTIC"             # 1-to-1 unambiguous structural transformation
    EXTENSION_DEPENDENT = "EXTENSION_DEPENDENT" # Relies on target Sphinx extensions (e.g. sphinx-design)
    RULE_DEPENDENT = "RULE_DEPENDENT"           # Requires semantic inspection of symbol/environment
    MANUAL_FALLBACK = "MANUAL_FALLBACK"         # Fallback when no automated mapping exists

class MigrationTarget(BaseModel):
    """Target Sphinx/MyST construct specification."""
    framework: str = "MyST"                 # e.g., "MyST", "sphinx-design", "sphinx.ext.autodoc", "sphinxcontrib-mermaid"
    directive_name: str                     # e.g., "note", "tab-set", "tab-item", "dropdown", "literalinclude", "mermaid"
    syntax_template: Optional[str] = None   # e.g. "```{directive_name} {title}\n{body}\n```"
    required_extensions: List[str] = Field(default_factory=list) # e.g. ["sphinx_design", "myst_parser"]
    required_py_packages: List[str] = Field(default_factory=list) # e.g. ["sphinx-design", "myst-parser"]

class MigrationRule(BaseModel):
    """Declarative specification defining how a source IR construct maps to a Sphinx target."""
    rule_id: str
    source_kind: NodeKind
    rule_kind: RuleKind
    target: MigrationTarget
    classification: Classification = Classification.TRANSFORM
    
    # Declarative constraints and semantics
    preserves: List[str] = Field(default_factory=list)  # Contract promises
    changes: List[str] = Field(default_factory=list)    # Expected changes
    conditions: Dict[str, Any] = Field(default_factory=dict) # Evaluation conditions
    manual_if: List[str] = Field(default_factory=list)  # Trigger conditions for manual classification
    description: str

    def matches(self, node: BaseIRNode) -> bool:
        """Determines if this rule applies to the given IR node."""
        return node.kind == self.source_kind

    def evaluate(self, node: BaseIRNode) -> "RuleEvaluation":
        """Generically evaluates the node against this rule's declarations without engine hardcoding."""
        is_manual = False
        manual_reasons: List[str] = []
        applied_changes = list(self.changes)
        resolved_target = self.target.model_copy(deep=True)

        # Dynamic target resolution based on node metadata
        if self.source_kind == NodeKind.ADMONITION:
            adm_type = (node.metadata.get("admonition_type") or "note").lower()
            supported_map = self.conditions.get("type_map", {})
            if supported_map:
                if adm_type in supported_map:
                    resolved_target.directive_name = supported_map[adm_type]
                    applied_changes.append(f"map_admonition_{adm_type}_to_{resolved_target.directive_name}")
                else:
                    is_manual = True
                    manual_reasons.append(f"Unsupported custom admonition type '{adm_type}'")

        elif self.source_kind == NodeKind.API_DIRECTIVE:
            symbol = node.metadata.get("symbol", "<unknown>")
            if self.classification == Classification.MANUAL:
                is_manual = True
                manual_reasons.append(f"Manual review required for API symbol '{symbol}'.")
            elif not symbol or symbol == "<unknown>":
                is_manual = True
                manual_reasons.append(f"Review API symbol '{symbol}' docstring convention and select autodoc directive.")
            else:
                applied_changes.append(f"map_api_directive_{symbol}")

        elif self.source_kind == NodeKind.LINK_REF:
            href = node.metadata.get("href", "")
            is_ext = node.metadata.get("is_external", False)
            if is_ext:
                applied_changes = ["preserve_external_url"]
            elif href.endswith(".md") or ".md#" in href:
                applied_changes = ["resolve_internal_doc_ref"]
            else:
                applied_changes = ["preserve_standard_link"]

        # Derive truthful observed preservation for this specific node
        observed_preservation: List[str] = []
        for attr in self.preserves:
            if attr in node.metadata:
                observed_preservation.append(attr)
            elif attr == "raw_text" and bool(node.raw_text):
                observed_preservation.append(attr)
            elif attr in ("tab_titles", "child_contents", "nesting") and bool(node.children):
                observed_preservation.append(attr)
            elif attr == "body" and (bool(node.children) or bool(node.raw_text)):
                observed_preservation.append(attr)
            elif attr in ("diagram_source", "line_mapping", "link_text", "target_url"):
                observed_preservation.append(attr)

        # Determine final classification
        final_class = Classification.MANUAL if is_manual else self.classification
        action_item = "; ".join(manual_reasons) if manual_reasons else None
        
        return RuleEvaluation(
            rule_id=self.rule_id,
            matched=True,
            classification=final_class,
            target=resolved_target if not is_manual else None,
            applied_changes=applied_changes,
            preserved_attributes=observed_preservation,
            required_extensions=list(resolved_target.required_extensions),
            required_packages=list(resolved_target.required_py_packages),
            action_item=action_item,
            rationale=self.description
        )

class RuleEvaluation(BaseModel):
    """Result of evaluating a MigrationRule against a specific DocumentIR node."""
    rule_id: str
    matched: bool
    classification: Classification
    target: Optional[MigrationTarget] = None
    applied_changes: List[str] = Field(default_factory=list)
    preserved_attributes: List[str] = Field(default_factory=list)
    required_extensions: List[str] = Field(default_factory=list)
    required_packages: List[str] = Field(default_factory=list)
    action_item: Optional[str] = None
    rationale: str

class MigrationAction(BaseModel):
    """Normalized, source-span-derived migration action for inventory aggregation and transformation."""
    action_id: str
    rule_id: str
    source_file: str
    start_line: int
    end_line: int
    classification: Classification
    source_kind: NodeKind
    source_span_fingerprint: str = "" # SHA256 of the exact original raw text in [start_line, end_line]
    target_directive: Optional[str] = None
    required_extensions: List[str] = Field(default_factory=list)
    required_packages: List[str] = Field(default_factory=list)
    preserves: List[str] = Field(default_factory=list)
    manual_instruction: Optional[str] = None
    description: str
