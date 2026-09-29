"""Data models for deterministic, plan-driven document transformations and patch reporting."""

from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class TransformationStatus(str, Enum):
    APPLIED = "APPLIED"  # Successfully transformed targeted construct spans
    UNCHANGED = "UNCHANGED"  # No transform actions; byte-for-byte source preserved
    MANUAL_REQUIRED = "MANUAL_REQUIRED"  # Document contains manual action items (retained original source)
    SKIPPED = "SKIPPED"  # Plan mismatch or skipped document


class ConfPyStatus(str, Enum):
    CREATED = "CREATED"  # conf.py did not exist and was generated
    UNCHANGED = "UNCHANGED"  # Existing conf.py was already identical to generated plan
    CONFLICT = "CONFLICT"  # Existing conf.py differs; skipped to prevent overwrite without --force


class DocumentTransformationResult(BaseModel):
    """Result of transforming a single Markdown source document via plan-driven source-span patching."""

    source_file: str
    target_file: str
    original_content: str
    transformed_content: str
    source_fingerprint: str
    transforms_applied: int = 0
    constructs_preserved: int = 0
    manual_items_reported: int = 0
    unsupported_items_reported: int = 0
    stale_actions_count: int = 0
    stale_action_details: List[str] = Field(default_factory=list)
    status: TransformationStatus = TransformationStatus.APPLIED
    diff: Optional[str] = None
    is_modified: bool = False


class ProjectTransformationReport(BaseModel):
    """Aggregate result of executing a MigrationPlan across the entire repository."""

    project_root: str
    plan_hash: str
    transformed_documents: List[DocumentTransformationResult] = Field(
        default_factory=list
    )
    generated_sphinx_files: Dict[str, str] = Field(
        default_factory=dict
    )  # e.g. "docs/conf.py"
    conf_py_status: ConfPyStatus = ConfPyStatus.CREATED
    conf_py_conflict_diff: Optional[str] = None
    documents_examined: int = 0
    documents_changed: int = 0
    files_written_to_disk: int = 0
    total_transforms_executed: int = 0
    total_stale_actions: int = 0
    cleaned_files: List[str] = Field(default_factory=list)
    dry_run: bool = True
