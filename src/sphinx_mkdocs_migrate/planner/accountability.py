"""Data models and inventory structures for Construct Accountability (Milestone 3.5 / 0.2.0).

Orthogonal Dimensions:
1. Source Occurrence: kind, file, span (start_line, end_line), occurrence text
2. Disposition: PRESERVE | TRANSFORM | MANUAL | UNSUPPORTED
3. Target Strategy: strategy name, emitted target directive/representation, target reference
4. Verification State: UNVERIFIED | ACCOUNTED | VERIFIED
5. Manual Action: required (bool), instruction, rationale
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field


class ConstructDisposition(str, Enum):
    """What should happen to the source construct during migration."""

    PRESERVE = "PRESERVE"  # Preserve source representation/content through migration
    TRANSFORM = "TRANSFORM"  # Automatically transform to target Sphinx/MyST construct
    MANUAL = "MANUAL"  # Requires human decision or manual migration action
    UNSUPPORTED = "UNSUPPORTED"  # Known limitation; not automatically supported


class ConstructVerification(str, Enum):
    """Has the construct outcome been verified?"""

    UNVERIFIED = "UNVERIFIED"  # Discovered in source but not yet accounted for in plan
    ACCOUNTED = "ACCOUNTED"  # Cataloged with explicit disposition and strategy in plan
    VERIFIED = "VERIFIED"  # Proven valid via post-migration parse, build, or human confirmation


class SourceOccurrence(BaseModel):
    """Exact source provenance and location of an observed construct."""

    kind: (
        str  # e.g., "admonition", "code_fence", "tab_set", "heading", "link", "toctree"
    )
    file: str  # Relative file path (e.g. "docs/index.md", "mkdocs.yml")
    span: Tuple[int, int]  # (start_line, end_line)
    occurrence: Optional[str] = None  # Representative snippet or identifier


class TargetStrategy(BaseModel):
    """Planned target representation and emission strategy in Sphinx/MyST."""

    strategy: str  # e.g., "myst_admonition", "direct_fence", "sphinx_design_tab", "root_toctree"
    emitted: Optional[str] = None  # Exact generated directive / snippet
    target_reference: Optional[str] = (
        None  # Directive name, anchor ID, or conf variable
    )


class ManualActionSpec(BaseModel):
    """Specification of human action requirements."""

    required: bool = False
    instruction: Optional[str] = None
    rationale: Optional[str] = None


class ConstructRecord(BaseModel):
    """An individual accountable construct tracked across the full migration lifecycle."""

    record_id: str
    source: SourceOccurrence
    disposition: ConstructDisposition
    target: TargetStrategy
    verification: ConstructVerification = ConstructVerification.ACCOUNTED
    manual_action: ManualActionSpec = Field(default_factory=ManualActionSpec)


class AccountabilityInventory(BaseModel):
    """Repository-wide construct accountability matrix."""

    records: List[ConstructRecord] = Field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.records)

    @property
    def accounted_count(self) -> int:
        return sum(
            1
            for r in self.records
            if r.verification
            in (ConstructVerification.ACCOUNTED, ConstructVerification.VERIFIED)
        )

    @property
    def verified_count(self) -> int:
        return sum(
            1 for r in self.records if r.verification == ConstructVerification.VERIFIED
        )

    @property
    def manual_count(self) -> int:
        return sum(1 for r in self.records if r.manual_action.required)

    def by_disposition(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self.records:
            counts[r.disposition.value] = counts.get(r.disposition.value, 0) + 1
        return counts

    def by_kind(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self.records:
            counts[r.source.kind] = counts.get(r.source.kind, 0) + 1
        return counts
