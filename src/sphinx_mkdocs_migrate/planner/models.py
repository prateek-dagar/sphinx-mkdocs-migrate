from __future__ import annotations
"""Data models for deterministic repository-wide MigrationPlan and aggregated inventories."""
import hashlib
import json
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from ..parsing.markdown_ir import NodeKind
from ..analyzer.models import (
    Classification,
    ConfigAnalysis,
    DependencyAnalysis,
    CIAnalysis,
    NavigationAnalysis,
    VersionEnvironment
)
from ..rules.models import MigrationAction

class RequirementProvenance(str, Enum):
    TARGET_BASELINE = "TARGET_BASELINE"             # Core runtime requirement (e.g. Sphinx, MyST)
    DOCUMENT_CONSTRUCT = "DOCUMENT_CONSTRUCT"       # Triggered by parsed document nodes (e.g. tabs)
    THEME_POLICY = "THEME_POLICY"                   # Derived from source theme mapping rule
    EXTENSION_POLICY = "EXTENSION_POLICY"           # Derived from MkDocs plugin/markdown_extension mapping
    FEATURE_POLICY = "FEATURE_POLICY"               # Derived from MkDocs theme feature mapping
    GENERATED_PIPELINE = "GENERATED_PIPELINE"       # Derived from build-time documentation generation pipelines (e.g. gen-files, mkdocstrings)

class GeneratedDocumentProposal(BaseModel):
    """Proposal for synthesizing generated documentation files (e.g., API reference stubs from gen-files/mkdocstrings)."""
    target_path: str                                # e.g. "docs/reference/pythonjsonlogger/jsonlogger.md"
    title: str                                      # e.g. "jsonlogger"
    content: str                                    # MyST / autodoc content
    generator_plugin: str                           # e.g. "gen-files"
    generator_script: Optional[str] = None          # e.g. "scripts/gen_ref_nav.py"
    provenance: RequirementProvenance = RequirementProvenance.GENERATED_PIPELINE
    rationale: str
    flow_actions: List[DocumentFlowAction] = Field(default_factory=list)

class RequirementItem(BaseModel):
    """Traceable dependency requirement (extension or package) with provenance."""
    name: str                                       # e.g. "sphinx_design", "sphinx-design>=0.5.0"
    kind: str                                       # "extension" or "package"
    provenance: RequirementProvenance
    rationale: str
    sources: List[str] = Field(default_factory=list) # e.g. ["docs/tabs.md:12", "target_baseline"]

class PlanActionSummary(BaseModel):
    """Aggregate count and categorized inventory of construct actions."""
    total_actions: int = 0
    transform_count: int = 0
    preserve_count: int = 0
    manual_count: int = 0
    unsupported_count: int = 0
    construct_counts: Dict[str, int] = Field(default_factory=dict)

class ThemeMigrationProposal(BaseModel):
    """Explicit theme migration mapping with source theme, classification, and rationale."""
    source_theme: str
    target_theme: Optional[str] = None
    target_package: Optional[str] = None
    classification: Classification = Classification.TRANSFORM
    rationale: str

class ConfigMigrationProposal(BaseModel):
    """Proposed Sphinx configuration updates derived strictly from source evidence."""
    project_name: str
    theme: ThemeMigrationProposal
    extensions_to_add: List[str] = Field(default_factory=list)
    myst_enable_extensions: List[str] = Field(default_factory=list)
    custom_options: Dict[str, Any] = Field(default_factory=dict)
    rationale: Dict[str, str] = Field(default_factory=dict)

class ManualReviewItem(BaseModel):
    """Traceable manual migration action item."""
    item_id: str
    source_file: str
    line_number: int
    construct_type: str
    instruction: str
    rationale: str

class MigrationPlanMetadata(BaseModel):
    """Metadata about the generation session (separated to guarantee plan determinism)."""
    generated_at: str
    planner_version: str = "0.1.0b1"

class ApiDirectiveKind(str, Enum):
    AUTOMODULE = "AUTOMODULE"
    AUTOCLASS = "AUTOCLASS"
    AUTOFUNCTION = "AUTOFUNCTION"
    AUTOMETHOD = "AUTOMETHOD"
    AUTOATTRIBUTE = "AUTOATTRIBUTE"
    AUTOEXCEPTION = "AUTOEXCEPTION"
    AUTOSUMMARY = "AUTOSUMMARY"
    GENERATED_API_PAGE = "GENERATED_API_PAGE"
    MANUAL = "MANUAL"
    UNSUPPORTED = "UNSUPPORTED"

class ApiGenerationStrategy(BaseModel):
    """Explicit strategy for realizing an ApiDocumentationRequest in Sphinx."""
    object_path: str
    directive_kind: ApiDirectiveKind
    options: Dict[str, Any] = Field(default_factory=dict)
    summary_entries: List[str] = Field(default_factory=list)
    target_toctree: Optional[str] = None
    members: Optional[List[str]] = None
    inherited_members: Optional[str] = None
    show_inheritance: bool = True
    module_first: bool = False
    source_construct_id: Optional[str] = None
    rationale: str = ""

class DocumentFlowAction(BaseModel):
    """Ordered semantic flow action planned for a target document."""
    action_id: str
    order_index: int
    source_construct_id: Optional[str] = None
    element_type: str  # HEADING, PARAGRAPH, TABLE, CODE_BLOCK, API_REQUEST, AUTOSUMMARY, etc.
    strategy: str      # TRANSFORM, PRESERVE, AUTODOC, AUTOSUMMARY, MANUAL, etc.
    content_summary: str
    target_directive: Optional[str] = None
    rationale: str

class ArtifactProvenance(BaseModel):
    """Traceable provenance and verification expectation for a planned artifact."""
    source_construct_ids: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)
    generated_from_pipeline: Optional[str] = None
    required_extensions: List[str] = Field(default_factory=list)
    required_packages: List[str] = Field(default_factory=list)
    verification_expectation: Optional[str] = None

class DocumentationArtifact(BaseModel):
    """Planned document artifact with ordered semantic flow and traceable provenance."""
    artifact_id: str
    target_path: str
    source_file: Optional[str] = None
    title: str
    artifact_kind: str  # markdown_doc, api_reference, generated_stub, toctree_index
    provenance: RequirementProvenance
    rationale: str
    flow_actions: List[DocumentFlowAction] = Field(default_factory=list)
    artifact_provenance: Optional[ArtifactProvenance] = None

class NavigationPlan(BaseModel):
    """Synthesized navigation hierarchy and Sphinx toctree layout."""
    root_toctrees: List[str] = Field(default_factory=list)
    sub_toctrees: Dict[str, List[str]] = Field(default_factory=dict)
    hidden_routes: List[str] = Field(default_factory=list)

class GeneratedPipelinePlan(BaseModel):
    """Traceable transformation plan for build-time generated document pipelines."""
    pipeline_id: str
    source_plugin: str
    generator_script: Optional[str] = None
    target_strategy: str  # AUTODOC_AUTOSUMMARY_STUBS, MANUAL, PRESERVE_SCRIPTS
    target_artifacts: List[str] = Field(default_factory=list)
    rationale: str

class ReferenceKind(str, Enum):
    INTERNAL_REFERENCE = "INTERNAL_REFERENCE"
    API_REFERENCE = "API_REFERENCE"
    EXTERNAL_INVENTORY_REFERENCE = "EXTERNAL_INVENTORY_REFERENCE"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"

class CrossReferenceAction(BaseModel):
    """Traceable link transformation from MkDocs syntax/paths to Sphinx targets."""
    source_construct_id: str
    source_file: str
    source_target: str
    transformed_target: str
    reference_kind: ReferenceKind = ReferenceKind.INTERNAL_REFERENCE
    is_doc_ref: bool = True
    target_inventory: Optional[str] = None  # e.g. "https://docs.python.org/3"
    rationale: str

class ExternalInventoryConfig(BaseModel):
    """Configuration mapping for sphinx.ext.intersphinx external inventories."""
    inventory_id: str  # e.g. "python"
    url: str           # e.g. "https://docs.python.org/3"
    objects_inv: str   # e.g. "https://docs.python.org/3/objects.inv"
    provenance: RequirementProvenance = RequirementProvenance.EXTENSION_POLICY
    rationale: str

class VersioningDeploymentPlan(BaseModel):
    """Explicit accountability separating build-time document generation from deployment/versioning (e.g. mike)."""
    source_tool: str  # e.g. "mike"
    canonical_version: Optional[str] = None
    target_strategy: str  # e.g. "SPHINX_VERSIONING_DEPLOYMENT_WORKFLOW"
    status: str = "ACCOUNTED"
    rationale: str

class CapabilityDisposition(str, Enum):
    PRESERVE = "PRESERVE"
    TRANSFORM = "TRANSFORM"
    MANUAL = "MANUAL"
    UNSUPPORTED = "UNSUPPORTED"
    ACCOUNTED_NO_DIRECT_EQUIVALENT = "ACCOUNTED_NO_DIRECT_EQUIVALENT"

class ImplementationStrategy(str, Enum):
    NATIVE_SPHINX = "NATIVE_SPHINX"
    SPHINX_EXTENSION = "SPHINX_EXTENSION"
    AUTODOC = "AUTODOC"
    AUTOSUMMARY = "AUTOSUMMARY"
    AUTODOC_AUTOSUMMARY_STUBS = "AUTODOC_AUTOSUMMARY_STUBS"
    GENERATED_PIPELINE = "GENERATED_PIPELINE"
    TOCTREE = "TOCTREE"
    INTERSPHINX = "INTERSPHINX"
    DEPLOYMENT_WORKFLOW = "DEPLOYMENT_WORKFLOW"
    MYST_DIRECTIVE = "MYST_DIRECTIVE"
    NONE = "NONE"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_YET_VERIFIED = "NOT_YET_VERIFIED"
    PENDING_HTML_COMPARISON = "PENDING_HTML_COMPARISON"

class SystemCapabilityAccountability(BaseModel):
    """Complete accountability item ensuring no source capability or plugin silently disappears."""
    capability_name: str
    source_category: str  # plugin, markdown_extension, theme_feature, external_inventory
    disposition: CapabilityDisposition
    implementation_strategy: ImplementationStrategy
    verification_status: VerificationStatus = VerificationStatus.NOT_YET_VERIFIED
    target_equivalent: Optional[str] = None
    rationale: str

class AssetAction(BaseModel):
    """Traceable asset copying/referencing action."""
    source_construct_id: Optional[str] = None
    source_path: str
    target_path: str
    asset_kind: str
    rationale: str

class DocumentationPlan(BaseModel):
    """Structured documentation synthesis contract derived from the DocumentationSiteGraph."""
    schema_version: str = "1.0.0"
    pages: List[DocumentationArtifact] = Field(default_factory=list)
    api_strategies: List[ApiGenerationStrategy] = Field(default_factory=list)
    navigation: NavigationPlan = Field(default_factory=NavigationPlan)
    generated_pipelines: List[GeneratedPipelinePlan] = Field(default_factory=list)
    cross_references: List[CrossReferenceAction] = Field(default_factory=list)
    external_inventories: List[ExternalInventoryConfig] = Field(default_factory=list)
    versioning_deployment: Optional[VersioningDeploymentPlan] = None
    capability_accountability: List[SystemCapabilityAccountability] = Field(default_factory=list)
    asset_actions: List[AssetAction] = Field(default_factory=list)
    required_extensions: List[str] = Field(default_factory=list)
    required_packages: List[str] = Field(default_factory=list)
    manual_items: List[ManualReviewItem] = Field(default_factory=list)
    unsupported_items: List[MigrationAction] = Field(default_factory=list)
    
    # Backward compatibility properties
    artifacts: List[DocumentationArtifact] = Field(default_factory=list)
    api_generation_strategy: Dict[str, str] = Field(default_factory=dict)
    toctree_hierarchies: Dict[str, List[str]] = Field(default_factory=dict)
    cross_reference_mappings: Dict[str, str] = Field(default_factory=dict)

class MigrationPlan(BaseModel):
    """Comprehensive, deterministic repository-wide migration plan without mutating disk."""
    project_root: str
    metadata: MigrationPlanMetadata
    
    # Subsystem Inspection Evidence
    source_mkdocs_config: Optional[ConfigAnalysis] = None
    version_environment: Optional[VersionEnvironment] = None
    navigation_analysis: Optional[NavigationAnalysis] = None
    dependency_analysis: Optional[DependencyAnalysis] = None
    ci_analysis: Optional[CIAnalysis] = None
    
    # Documentation Plan IR
    documentation_plan: Optional[DocumentationPlan] = None
    
    # Traceable Actions
    document_actions: List[MigrationAction] = Field(default_factory=list)
    generated_documents: List[GeneratedDocumentProposal] = Field(default_factory=list)
    
    # Aggregated & Deduplicated Repositories Requirements with Provenance
    summary: PlanActionSummary = Field(default_factory=PlanActionSummary)
    requirements: List[RequirementItem] = Field(default_factory=list)
    packages_to_remove: List[str] = Field(default_factory=list)
    
    # Concrete Subsystem Proposals
    proposed_sphinx_config: Optional[ConfigMigrationProposal] = None
    manual_action_items: List[ManualReviewItem] = Field(default_factory=list)
    unsupported_constructs: List[MigrationAction] = Field(default_factory=list)

    def canonical_dict(self) -> Dict[str, Any]:
        """Returns the canonical deterministic content dictionary excluding ephemeral metadata."""
        data = self.model_dump()
        data.pop("metadata", None)
        return data

    def canonical_hash(self) -> str:
        """Returns a stable SHA256 hash of the canonical plan content."""
        canonical_json = json.dumps(self.canonical_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def get_required_extensions(self) -> List[str]:
        return sorted(list({r.name for r in self.requirements if r.kind == "extension"}))

    def get_required_packages(self) -> List[str]:
        return sorted(list({r.name for r in self.requirements if r.kind == "package"}))
