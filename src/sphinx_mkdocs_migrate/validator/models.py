"""Data models for post-transformation validation and Sphinx build verification."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationIssue(BaseModel):
    """Validation finding reported during structural parsing or Sphinx build execution."""

    file_path: str
    line_number: Optional[int] = None
    severity: ValidationSeverity
    issue_type: str  # e.g. "UNCLOSED_FENCE", "STALE_PLAN", "SPHINX_BUILD_ERROR", "SPHINX_BUILD_WARNING"
    message: str
    context_snippet: Optional[str] = None


class ValidationReport(BaseModel):
    """Overall validation report checking CommonMark structural validity, Sphinx config, and build execution."""

    passed: bool
    total_issues: int = 0
    errors_count: int = 0
    warnings_count: int = 0
    issues: List[ValidationIssue] = Field(default_factory=list)
    commonmark_parse_successful: bool = False
    structural_validation_successful: bool = False
    sphinx_build_attempted: bool = False
    sphinx_build_successful: Optional[bool] = None
    sphinx_warning_count: int = 0
    sphinx_warnings: List[str] = Field(default_factory=list)
    sphinx_theme_status: Optional[str] = None
    build_output: Optional[str] = None
