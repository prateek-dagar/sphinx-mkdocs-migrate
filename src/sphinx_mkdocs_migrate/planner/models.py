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
    
    # Traceable Actions
    document_actions: List[MigrationAction] = Field(default_factory=list)
    
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
