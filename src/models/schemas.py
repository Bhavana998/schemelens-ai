"""
Pydantic data models for SchemeLens AI.
Defines schemas for fields, evidence, drafts, approvals, audit logs, and extraction payloads.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class FieldStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"

    @classmethod
    def _missing_(cls, value: object) -> Optional["FieldStatus"]:
        if isinstance(value, str):
            clean = value.split(".")[-1].lower()
            for member in cls:
                if member.value == clean or member.name.lower() == clean:
                    return member
        return None


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def _missing_(cls, value: object) -> Optional["ReviewStatus"]:
        if isinstance(value, str):
            clean = value.split(".")[-1].lower()
            for member in cls:
                if member.value == clean or member.name.lower() == clean:
                    return member
        return None


class BenefitType(str, Enum):
    CASH_TRANSFER = "Cash Transfer"
    SUBSIDY = "Subsidy"
    IN_KIND = "In-Kind"
    LOAN = "Loan"
    INSURANCE = "Insurance"
    TRAINING = "Skill / Training"
    OTHER = "Other"
    NOT_SPECIFIED = "Not Specified"


class Evidence(BaseModel):
    """
    Evidence backing an extracted field value.
    Must link to exact supporting quotation, source identifier, page/section,
    source URL if available, and capture timestamp.
    """
    quotation: Optional[str] = Field(
        default=None,
        description="Exact supporting quotation directly extracted from source text without fabrication."
    )
    source_id: str = Field(
        description="Source identifier (e.g. document filename or UUID)."
    )
    page_or_section: Optional[Union[int, str]] = Field(
        default=None,
        description="1-indexed page number or named section heading."
    )
    source_link: Optional[str] = Field(
        default=None,
        description="Source URL if genuinely cited in the source text."
    )
    capture_date: str = Field(
        description="ISO 8601 timestamp of when evidence was extracted."
    )
    is_verified: bool = Field(
        default=False,
        description="Deterministic verification: quotation was found verbatim in the specified page text."
    )
    verification_details: Optional[str] = Field(
        default=None,
        description="Detailed verification outcome or mismatch explanation."
    )


class SchemeFieldRecord(BaseModel):
    """
    Represents an individual scheme field with its value, status, confidence,
    supporting evidence, and notes.
    """
    scheme_ref: str = Field(description="Scheme identifier or reference name.")
    field: str = Field(description="Name of the field being captured.")
    value: Optional[Any] = Field(
        default=None,
        description="Extracted value (string, list, or None if unsupported)."
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="List of supporting evidence items. Multiple allowed for conflicts."
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0."
    )
    status: FieldStatus = Field(
        default=FieldStatus.NOT_FOUND,
        description="Field status: found, not_found, or conflict."
    )
    note: Optional[str] = Field(
        default=None,
        description="Explanation when field is missing or rationale for conflict."
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, round(val, 4)))
        except (ValueError, TypeError):
            return 0.0


class ExtractedPage(BaseModel):
    """Text extracted from a single document page."""
    page_number: int = Field(ge=1, description="1-indexed page number.")
    text: str = Field(default="", description="Extracted text content.")
    extraction_method: str = Field(
        default="pdf_text",
        description="Method used: 'pdf_text', 'ocr', or 'empty'."
    )
    is_scanned: bool = Field(
        default=False,
        description="Flag indicating if the page required OCR."
    )
    char_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        self.char_count = len(self.text.strip())


class DocumentContent(BaseModel):
    """Complete document text and structural metadata."""
    document_id: str
    filename: str
    file_hash: str
    total_pages: int
    pages: List[ExtractedPage]
    raw_full_text: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ocr_applied: bool = False
    ocr_warning: Optional[str] = None


class RawExtractionPayload(BaseModel):
    """
    Direct model output schema for structured LLM completion.
    Strictly constrained to the supplied source document.
    """
    scheme_name: Optional[str] = None
    scheme_name_evidence: Optional[str] = None
    scheme_name_page: Optional[int] = None

    department: Optional[str] = None
    department_evidence: Optional[str] = None
    department_page: Optional[int] = None

    benefit_type: Optional[str] = None
    benefit_type_evidence: Optional[str] = None
    benefit_type_page: Optional[int] = None

    benefit_amount: Optional[str] = None
    benefit_amount_evidence: Optional[str] = None
    benefit_amount_page: Optional[int] = None

    benefit_frequency: Optional[str] = None
    benefit_frequency_evidence: Optional[str] = None
    benefit_frequency_page: Optional[int] = None

    eligibility_conditions: Optional[Union[List[str], str]] = None
    eligibility_conditions_evidence: Optional[str] = None
    eligibility_conditions_page: Optional[int] = None

    required_documents: Optional[Union[List[str], str]] = None
    required_documents_evidence: Optional[str] = None
    required_documents_page: Optional[int] = None

    application_procedure: Optional[str] = None
    application_procedure_evidence: Optional[str] = None
    application_procedure_page: Optional[int] = None

    deadline: Optional[str] = None
    deadline_evidence: Optional[str] = None
    deadline_page: Optional[int] = None

    official_link: Optional[str] = None
    official_link_evidence: Optional[str] = None
    official_link_page: Optional[int] = None

    missing_fields_rationale: Dict[str, str] = Field(
        default_factory=dict,
        description="Explanations for why specific fields were not found in source text."
    )


class SchemeDraft(BaseModel):
    """
    Complete scheme draft record with all required fields, conflict flags,
    and metadata.
    """
    id: str
    scheme_name: str
    source_document_ids: List[str]
    created_at: str
    updated_at: str
    version: int = 1
    review_status: ReviewStatus = ReviewStatus.DRAFT
    fields: Dict[str, SchemeFieldRecord]
    has_conflicts: bool = False
    missing_fields_count: int = 0
    unverified_evidence_count: int = 0
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovedScheme(BaseModel):
    """
    Immutable approved scheme record locked behind human review.
    """
    id: str
    draft_id: str
    scheme_name: str
    version: int
    approved_by: str
    approved_at: str
    fields: Dict[str, SchemeFieldRecord]
    reviewer_notes: Optional[str] = None
    audit_hash: str


class ReviewAuditEntry(BaseModel):
    """Audit log entry capturing any review action, edit, or approval."""
    id: str
    scheme_id: str
    action: str  # e.g., 'created_draft', 'field_edited', 'approved', 'rejected'
    actor: str
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)
