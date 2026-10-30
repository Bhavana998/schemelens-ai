"""
Structured Scheme Extractor Service.
Coordinates document text parsing, model invocation, structured schema conversion,
and initial field packaging.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.extraction.llm_provider import BaseLLMProvider, get_llm_provider
from src.models.schemas import (
    DocumentContent,
    Evidence,
    FieldStatus,
    RawExtractionPayload,
    ReviewStatus,
    SchemeDraft,
    SchemeFieldRecord,
)

STANDARD_FIELDS = [
    "scheme_name",
    "department",
    "benefit_type",
    "benefit_amount",
    "benefit_frequency",
    "eligibility_conditions",
    "required_documents",
    "application_procedure",
    "deadline",
    "official_link",
]


class SchemeExtractor:
    """
    Transforms extracted document content into structured SchemeDraft with SchemeFieldRecords.
    """

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or get_llm_provider()

    def extract_scheme_draft(
        self,
        document: DocumentContent,
        scheme_id: Optional[str] = None
    ) -> Tuple[SchemeDraft, Dict[str, Any]]:
        """
        Processes DocumentContent and returns a populated SchemeDraft.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        draft_id = scheme_id or str(uuid.uuid4())

        # Invoke LLM provider
        payload, metrics = self.provider.extract_scheme_payload(
            document_text=document.raw_full_text,
            document_metadata={
                "filename": document.filename,
                "document_id": document.document_id,
                "total_pages": document.total_pages
            }
        )

        scheme_title = payload.scheme_name or "Untitled Welfare Scheme"
        fields: Dict[str, SchemeFieldRecord] = {}
        missing_count = 0

        for field_name in STANDARD_FIELDS:
            value = getattr(payload, field_name, None)
            evidence_quote = getattr(payload, f"{field_name}_evidence", None)
            page_num = getattr(payload, f"{field_name}_page", 1)

            if value is not None and value != "" and value != []:
                # Field Found
                evidence_list = []
                if evidence_quote:
                    evidence_list.append(
                        Evidence(
                            quotation=evidence_quote,
                            source_id=document.filename,
                            page_or_section=page_num or 1,
                            source_link=value if field_name == "official_link" else None,
                            capture_date=now_iso,
                            is_verified=False  # To be verified deterministically in next pipeline stage
                        )
                    )

                fields[field_name] = SchemeFieldRecord(
                    scheme_ref=scheme_title,
                    field=field_name,
                    value=value,
                    evidence=evidence_list,
                    confidence=0.92 if evidence_quote else 0.70,
                    status=FieldStatus.FOUND,
                    note=None
                )
            else:
                # Field Missing / Not Found
                missing_count += 1
                rationale = payload.missing_fields_rationale.get(
                    field_name,
                    f"No mention of '{field_name}' found in source document."
                )
                fields[field_name] = SchemeFieldRecord(
                    scheme_ref=scheme_title,
                    field=field_name,
                    value=None,
                    evidence=[],
                    confidence=0.0,
                    status=FieldStatus.NOT_FOUND,
                    note=rationale
                )

        ocr_dur = document.metadata.get("ocr_duration_sec", 0.0)
        proc_dur = document.metadata.get("processing_duration_sec", 0.0)
        llm_dur = metrics.get("duration_sec", 0.0)
        total_dur = round(proc_dur + llm_dur, 4)

        combined_metrics = {
            **metrics,
            "ocr_duration_sec": ocr_dur,
            "processing_duration_sec": proc_dur,
            "llm_duration_sec": llm_dur,
            "total_duration_sec": total_dur
        }

        draft = SchemeDraft(
            id=draft_id,
            scheme_name=scheme_title,
            source_document_ids=[document.filename],
            created_at=now_iso,
            updated_at=now_iso,
            version=1,
            review_status=ReviewStatus.DRAFT,
            fields=fields,
            has_conflicts=False,
            missing_fields_count=missing_count,
            unverified_evidence_count=0,
            processing_metadata={
                "document_id": document.document_id,
                "file_hash": document.file_hash,
                "ocr_applied": document.ocr_applied,
                "ocr_warning": document.ocr_warning,
                **combined_metrics
            }
        )

        return draft, combined_metrics
