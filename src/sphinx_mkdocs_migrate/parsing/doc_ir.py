"""Semantic Documentation Intermediate Representation (IR) Models.

Schema Version: 1.0.0
Invariants:
1. Documentation IR is the migration authority.
2. Document flow is an ordered, heterogeneous, strongly-typed sequence with provenance (SourceSpan).
3. Discriminated unions prevent element_type and content drift.
4. Rendered HTML is verification evidence, not the migration source of truth.
"""

import hashlib
import json
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Set
from pydantic import BaseModel, Field

DOCUMENTATION_IR_SCHEMA_VERSION = "1.0.0"

# --- 1. Provenance & Source Spans ---


class SourceSpan(BaseModel):
    file: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_column: Optional[int] = None
    end_column: Optional[int] = None


# --- 2. API Documentation Request Models ---


class ApiObjectKind(str, Enum):
    MODULE = "module"
    PACKAGE = "package"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    ATTRIBUTE = "attribute"
    EXCEPTION = "exception"
    UNKNOWN = "unknown"


class MemberSelection(str, Enum):
    NOT_SPECIFIED = "NOT_SPECIFIED"
    ALL_PUBLIC = "ALL_PUBLIC"
    EXPLICIT = "EXPLICIT"
    DOCSTRING_ONLY = "DOCSTRING_ONLY"
    NONE = "NONE"


class SummaryMode(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    EXPLICIT = "EXPLICIT"
    HANDLER_DEFAULT = "HANDLER_DEFAULT"
    INFERRED = "INFERRED"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


class ApiDocumentationRequest(BaseModel):
    construct_id: str
    source_span: SourceSpan
    object_path: str
    object_kind: ApiObjectKind = ApiObjectKind.UNKNOWN
    handler: str = "mkdocstrings.python"
    raw_options: Dict[str, Any] = Field(default_factory=dict)
    normalized_options: Dict[str, Any] = Field(default_factory=dict)
    include_docstring: bool = True
    member_selection: MemberSelection = MemberSelection.NOT_SPECIFIED
    explicit_members: List[str] = Field(default_factory=list)
    summary_mode: SummaryMode = SummaryMode.NOT_REQUESTED
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED
    resolved_file: Optional[str] = None
    resolved_symbol: Optional[str] = None
    inheritance: List[str] = Field(default_factory=list)
    declared_members: List[str] = Field(default_factory=list)


# --- 3. Strongly-Typed Content Elements ---


class InlineElementKind(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"
    EMPHASIS = "EMPHASIS"
    STRONG = "STRONG"
    LINK = "LINK"


class InlineElement(BaseModel):
    kind: InlineElementKind
    text: str
    target: Optional[str] = None


class HeadingElement(BaseModel):
    level: int
    text: str
    anchor_id: Optional[str] = None
    inlines: List[InlineElement] = Field(default_factory=list)


class ParagraphElement(BaseModel):
    text: str
    inlines: List[InlineElement] = Field(default_factory=list)


class ListItemElement(BaseModel):
    text: str
    inlines: List[InlineElement] = Field(default_factory=list)
    children: List["ListItemElement"] = Field(default_factory=list)


class ListElement(BaseModel):
    ordered: bool = False
    items: List[ListItemElement] = Field(default_factory=list)


class TableCellElement(BaseModel):
    text: str
    inlines: List[InlineElement] = Field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1


class TableElement(BaseModel):
    caption: Optional[str] = None
    headers: List[TableCellElement] = Field(default_factory=list)
    rows: List[List[TableCellElement]] = Field(default_factory=list)


class CodeBlockElement(BaseModel):
    language: Optional[str] = None
    code: str
    title: Optional[str] = None
    linenums: bool = False
    highlight_lines: List[int] = Field(default_factory=list)


class AdmonitionElement(BaseModel):
    kind: str
    title: Optional[str] = None
    content_text: str
    collapsible: bool = False
    inlines: List[InlineElement] = Field(default_factory=list)


class ImageElement(BaseModel):
    src: str
    alt: Optional[str] = None
    title: Optional[str] = None
    resolved_path: Optional[str] = None


class LinkBlockElement(BaseModel):
    text: str
    target: str
    title: Optional[str] = None
    is_internal: bool = False


class SnippetElement(BaseModel):
    snippet_path: str
    resolved_path: Optional[str] = None
    raw_content: Optional[str] = None


class RawHtmlElement(BaseModel):
    raw_html: str


class UnknownElement(BaseModel):
    tag_or_type: str
    raw_content: str
    rationale: str


# --- 4. Discriminated Union for Document Elements ---

DocumentElementContent = Union[
    HeadingElement,
    ParagraphElement,
    ListElement,
    TableElement,
    CodeBlockElement,
    AdmonitionElement,
    ImageElement,
    LinkBlockElement,
    SnippetElement,
    ApiDocumentationRequest,
    RawHtmlElement,
    UnknownElement,
]


class DocumentElementType(str, Enum):
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    LIST = "LIST"
    TABLE = "TABLE"
    CODE_BLOCK = "CODE_BLOCK"
    ADMONITION = "ADMONITION"
    IMAGE = "IMAGE"
    LINK_BLOCK = "LINK_BLOCK"
    SNIPPET = "SNIPPET"
    API_REQUEST = "API_REQUEST"
    RAW_HTML = "RAW_HTML"
    UNKNOWN = "UNKNOWN"


class DocumentElement(BaseModel):
    construct_id: str
    element_type: DocumentElementType
    source_order_index: int
    source_span: SourceSpan
    content: DocumentElementContent


class DocumentFlowSpec(BaseModel):
    source_file: str
    elements: List[DocumentElement] = Field(default_factory=list)


# --- 5. Relationships, Links, & Navigation Graph ---


class DocumentationLink(BaseModel):
    source_construct_id: str
    target: str
    fragment: Optional[str] = None
    link_kind: str  # internal_page, internal_anchor, external_url, asset
    resolved: bool = False


class AssetReference(BaseModel):
    source_construct_id: str
    source_path: str
    resolved_path: Optional[str] = None
    asset_kind: str
    exists: bool = False


class DocumentationPage(BaseModel):
    source_file: str
    logical_route: str
    title: Optional[str] = None
    flow: DocumentFlowSpec
    outgoing_links: List[DocumentationLink] = Field(default_factory=list)
    referenced_assets: List[AssetReference] = Field(default_factory=list)


class NavigationNode(BaseModel):
    construct_id: str
    label: str
    page_route: Optional[str] = None
    children: List["NavigationNode"] = Field(default_factory=list)
    order_index: int = 0
    hidden: bool = False


class GeneratedPipeline(BaseModel):
    construct_id: str
    source_plugin: str
    source_configuration: Dict[str, Any] = Field(default_factory=dict)
    inputs: List[str] = Field(default_factory=list)
    generated_outputs: List[str] = Field(default_factory=list)
    navigation_effects: List[str] = Field(default_factory=list)
    generation_strategy: str
    verification_status: str


# --- 6. Generic Documentation Build Graph Models ---


class BuildStageType(str, Enum):
    SOURCE_PREPROCESSING = "SOURCE_PREPROCESSING"
    GENERATED_SOURCE_VARIANT = "GENERATED_SOURCE_VARIANT"
    DATA_DRIVEN_ARTIFACT = "DATA_DRIVEN_ARTIFACT"
    LOCALE_OVERLAY = "LOCALE_OVERLAY"
    CONFIG_SYNTHESIS = "CONFIG_SYNTHESIS"
    DOCUMENTATION_RENDERER = "DOCUMENTATION_RENDERER"
    SITE_ASSEMBLY = "SITE_ASSEMBLY"
    DEPLOYMENT_ASSEMBLY = "DEPLOYMENT_ASSEMBLY"
    ARTIFACT_COPY = "ARTIFACT_COPY"
    VALIDATION = "VALIDATION"
    SIDE_OUTPUT = "SIDE_OUTPUT"


class ArtifactScope(str, Enum):
    GLOBAL = "GLOBAL"
    LOCALE = "LOCALE"
    DOCUMENT = "DOCUMENT"


class ArtifactConsumerKind(str, Enum):
    SITE_ARTIFACT = "SITE_ARTIFACT"
    REPOSITORY_ARTIFACT = "REPOSITORY_ARTIFACT"
    DEPLOYMENT_ARTIFACT = "DEPLOYMENT_ARTIFACT"
    TEST_ARTIFACT = "TEST_ARTIFACT"
    TOOLING_ARTIFACT = "TOOLING_ARTIFACT"


class BuildArtifact(BaseModel):
    artifact_id: str
    path: str
    logical_role: Optional[str] = (
        None  # e.g., "sponsor_banner_partial", "python310_syntax_variant"
    )
    materialized_path: Optional[str] = (
        None  # e.g., "docs/en/overrides/partials/banner-sponsors.html"
    )
    artifact_kind: str  # source_file, generated_variant, data_partial, config_artifact, html_page, asset
    producer_stage: str
    consumer_stages: List[str] = Field(default_factory=list)
    external_consumers: List[str] = Field(
        default_factory=list
    )  # e.g., ["documentation_source_tree", "test_suite"]
    consumer_kinds: Set[ArtifactConsumerKind] = Field(
        default_factory=lambda: {ArtifactConsumerKind.SITE_ARTIFACT}
    )
    scope: ArtifactScope = ArtifactScope.GLOBAL
    locale: Optional[str] = None
    is_intermediate: bool = False
    provenance_source: Optional[str] = None


class StageWorkflowKind(str, Enum):
    PREPARATION_WORKFLOW = "PREPARATION_WORKFLOW"  # External / static preparation step (e.g. generate-docs-src-versions)
    BUILD_PIPELINE = "BUILD_PIPELINE"  # Core build DAG executed during site compilation
    MAINTENANCE_WORKFLOW = "MAINTENANCE_WORKFLOW"  # Auxiliary scripts (e.g. notify_translations, translation_fixer)


class DependencyJustificationKind(str, Enum):
    ARTIFACT_DEPENDENCY = "ARTIFACT_DEPENDENCY"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    CONTROL_DEPENDENCY = "CONTROL_DEPENDENCY"


class StageDependency(BaseModel):
    antecedent_stage_id: str
    justification_kind: DependencyJustificationKind
    artifact_id: Optional[str] = None
    description: Optional[str] = None


class BuildCondition(BaseModel):
    condition_id: str
    expression: str  # e.g., "locale != 'en'", "is_fallback == True"
    description: str


class BuildStage(BaseModel):
    stage_id: str
    stage_type: BuildStageType
    workflow_kind: StageWorkflowKind = StageWorkflowKind.BUILD_PIPELINE
    scope: ArtifactScope = ArtifactScope.GLOBAL
    locale: Optional[str] = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(
        default_factory=list
    )  # stage_ids that must complete before this
    stage_dependencies: List[StageDependency] = Field(default_factory=list)
    conditions: List[BuildCondition] = Field(default_factory=list)
    strategy: str
    consumer_kinds: Set[ArtifactConsumerKind] = Field(
        default_factory=lambda: {ArtifactConsumerKind.SITE_ARTIFACT}
    )
    source_provenance_symbol: Optional[str] = None  # e.g., "scripts/docs.py:build_all"
    rationale: str


class LocaleDocumentSpec(BaseModel):
    logical_route: str
    locale: str
    canonical_source: str
    localized_source: Optional[str] = None
    effective_source: str
    is_fallback: bool = False
    translation_notice_required: bool = False
    translation_status: str = "CANONICAL"  # CANONICAL, TRANSLATED, FALLBACK, EXCLUDED


class LocaleOverlaySpec(BaseModel):
    locale: str
    is_canonical: bool = False
    canonical_source_dir: str
    localized_source_dir: Optional[str] = None
    fallback_locale: Optional[str] = "en"
    inject_missing_notice: bool = True
    excluded_paths: List[str] = Field(default_factory=list)
    documents: Dict[str, LocaleDocumentSpec] = Field(default_factory=dict)


class DocumentationBuildGraph(BaseModel):
    schema_version: str = DOCUMENTATION_IR_SCHEMA_VERSION
    stages: Dict[str, BuildStage] = Field(default_factory=dict)
    artifacts: Dict[str, BuildArtifact] = Field(default_factory=dict)
    locales: Dict[str, LocaleOverlaySpec] = Field(default_factory=dict)

    def execution_order(self) -> List[str]:
        """Derives topological sort of build stages dynamically based on depends_on DAG."""
        visited: Set[str] = set()
        order: List[str] = []

        def visit(node_id: str, path: Set[str]):
            if node_id in path:
                raise ValueError(
                    f"Cyclic dependency detected in build stage: {node_id}"
                )
            if node_id not in visited:
                path.add(node_id)
                stage = self.stages.get(node_id)
                if stage:
                    for dep in stage.depends_on:
                        visit(dep, path)
                path.remove(node_id)
                visited.add(node_id)
                order.append(node_id)

        for s_id in self.stages:
            visit(s_id, set())
        return order

    def validate_graph_invariants(self) -> List[str]:
        """Validates structural integrity of the DAG, artifacts, and dependencies.

        Invariants:
        1. Every depends_on stage exists in stages.
        2. No stage depends on itself.
        3. Every BuildArtifact producer_stage exists.
        4. Every BuildArtifact consumer_stage exists.
        5. For every stage dependency A depends_on B, A != B.
        6. Bi-directional fidelity: If artifact X is produced by P and consumed by C, C must declare depends_on P (or external source).
        """
        errors: List[str] = []

        # 1. Validate Stage DAG
        for s_id, stage in self.stages.items():
            for dep in stage.depends_on:
                if dep not in self.stages:
                    errors.append(
                        f"Stage '{s_id}' depends on non-existent stage '{dep}'."
                    )
                if dep == s_id:
                    errors.append(f"Stage '{s_id}' cannot depend on itself.")

        # 2. Validate Artifact Producer / Consumer Consistency
        for a_id, art in self.artifacts.items():
            if art.producer_stage not in self.stages:
                errors.append(
                    f"Artifact '{a_id}' producer_stage '{art.producer_stage}' does not exist."
                )
            for c_stage in art.consumer_stages:
                if c_stage not in self.stages:
                    errors.append(
                        f"Artifact '{a_id}' consumer_stage '{c_stage}' does not exist."
                    )
                else:
                    # Bi-directional check: consuming stage must depend on producing stage
                    consumer_obj = self.stages[c_stage]
                    if (
                        art.producer_stage != c_stage
                        and art.producer_stage not in consumer_obj.depends_on
                    ):
                        errors.append(
                            f"Consuming stage '{c_stage}' consumes artifact '{a_id}' produced by '{art.producer_stage}', "
                            f"but '{c_stage}' does not declare depends_on '{art.producer_stage}'."
                        )

        # 3. Validate Cycle-free DAG
        try:
            self.execution_order()
        except ValueError as e:
            errors.append(str(e))

        return errors

    def validate_locale_invariants(self) -> List[str]:
        """Validates locale document lineage and fallback invariants.

        Invariants:
        1. TRANSLATED: effective_source == localized_source and is_fallback is False.
        2. FALLBACK: effective_source == canonical_source, is_fallback is True, translation_notice_required is True.
        3. CANONICAL: effective_source == canonical_source, is_fallback is False, translation_notice_required is False.
        """
        errors: List[str] = []
        for loc_id, spec in self.locales.items():
            for route, doc in spec.documents.items():
                if doc.translation_status == "TRANSLATED":
                    if doc.effective_source != doc.localized_source or doc.is_fallback:
                        errors.append(
                            f"Locale '{loc_id}' route '{route}' has TRANSLATED status but invalid effective_source or is_fallback."
                        )
                elif doc.translation_status == "FALLBACK":
                    if (
                        doc.effective_source != doc.canonical_source
                        or not doc.is_fallback
                        or not doc.translation_notice_required
                    ):
                        errors.append(
                            f"Locale '{loc_id}' route '{route}' has FALLBACK status but invalid canonical mapping or missing notice."
                        )
                elif doc.translation_status == "CANONICAL":
                    if (
                        doc.effective_source != doc.canonical_source
                        or doc.is_fallback
                        or doc.translation_notice_required
                    ):
                        errors.append(
                            f"Locale '{loc_id}' route '{route}' has CANONICAL status but invalid effective_source or notice flag."
                        )
        return errors


class DocumentationSiteGraph(BaseModel):
    schema_version: str = DOCUMENTATION_IR_SCHEMA_VERSION
    pages: Dict[str, DocumentationPage] = Field(default_factory=dict)
    navigation: Optional[NavigationNode] = None
    generated_pipelines: List[GeneratedPipeline] = Field(default_factory=list)
    build_graph: Optional[DocumentationBuildGraph] = None

    def canonical_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def canonical_hash(self) -> str:
        canonical_json = json.dumps(self.canonical_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
