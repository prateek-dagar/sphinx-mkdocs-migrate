"""Data models for migration analysis, findings, and deterministic reporting."""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Classification(str, Enum):
    PRESERVE = "PRESERVE"
    TRANSFORM = "TRANSFORM"
    MANUAL = "MANUAL"
    UNSUPPORTED = "UNSUPPORTED"

class ConstructFinding(BaseModel):
    category: str
    construct_type: str
    file_path: str
    line_number: int
    end_line_number: Optional[int] = None
    raw_snippet: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    classification: Classification = Classification.TRANSFORM

class MigrationRule(BaseModel):
    source_construct: str
    target_directive_or_construct: str
    required_sphinx_extensions: List[str] = Field(default_factory=list)
    description: str

class ConfigAnalysis(BaseModel):
    site_name: Optional[str] = None
    docs_dir: str = "docs"
    theme_name: str = "mkdocs"
    theme_features: List[str] = Field(default_factory=list)
    plugins: List[str] = Field(default_factory=list)
    markdown_extensions: List[str] = Field(default_factory=list)
    nav_raw: Optional[Any] = None
    custom_hooks: List[str] = Field(default_factory=list)

class NavigationItem(BaseModel):
    title: str
    path: Optional[str] = None
    children: List['NavigationItem'] = Field(default_factory=list)

class NavigationAnalysis(BaseModel):
    has_nav: bool = False
    total_nav_entries: int = 0
    max_depth: int = 0
    missing_references: List[str] = Field(default_factory=list)
    orphan_documents: List[str] = Field(default_factory=list)
    tree: List[NavigationItem] = Field(default_factory=list)

class VersionEnvironment(BaseModel):
    python_version: Optional[str] = None
    detected_mkdocs_version: Optional[str] = None
    detected_plugin_versions: Dict[str, str] = Field(default_factory=dict)
    target_sphinx_version: str = ">=7.0"
    target_myst_version: str = ">=2.0"

class DependencyAnalysis(BaseModel):
    manifest_type: Optional[str] = None
    detected_packages_to_remove: List[str] = Field(default_factory=list)
    suggested_packages_to_add: List[str] = Field(default_factory=list)

class CIAnalysis(BaseModel):
    ci_system: Optional[str] = None
    workflow_files: List[str] = Field(default_factory=list)
    has_mkdocs_deploy: bool = False
    readthedocs_detected: bool = False

class SubsystemSummary(BaseModel):
    name: str
    status: str
    details: str

class ProjectAnalysisReport(BaseModel):
    project_root: str
    mkdocs_config: Optional[ConfigAnalysis] = None
    version_env: Optional[VersionEnvironment] = None
    dependency_analysis: Optional[DependencyAnalysis] = None
    navigation_analysis: Optional[NavigationAnalysis] = None
    ci_analysis: Optional[CIAnalysis] = None
    total_markdown_files: int = 0
    construct_findings: List[ConstructFinding] = Field(default_factory=list)
    subsystem_summaries: List[SubsystemSummary] = Field(default_factory=list)
    manual_action_items: List[str] = Field(default_factory=list)
