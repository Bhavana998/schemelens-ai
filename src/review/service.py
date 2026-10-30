"""
Human Review and Approval Service for SchemeLens AI.
Enforces the Human-in-the-Loop gatekeeper principle:
- AI-generated drafts cannot be published without explicit approval.
- Drafts with unresolved conflicts cannot be approved.
- Approved records are versioned and tamper-hashed.
- Every correction and state transition is captured in an immutable audit log.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid

from src.models.schemas import (
    ApprovedScheme,
    FieldStatus,
    ReviewAuditEntry,
    ReviewStatus,
    SchemeDraft,
    SchemeFieldRecord,
)
from src.storage.db import DatabaseManager


class ReviewServiceError(Exception):
    """Raised when a review workflow constraint is violated."""
    pass


class ReviewService:
    """
    Manages human review lifecycle, field-level manual corrections,
    approval gates, and audit trails.
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def create_or_update_draft(
        self,
        draft: SchemeDraft,
        actor: str = "system"
    ) -> SchemeDraft:
        """Saves a newly extracted or re-extracted draft and logs audit entry."""
        self.db.save_draft(draft)
        self.db.log_audit_entry(
            ReviewAuditEntry(
                id=str(uuid.uuid4()),
                scheme_id=draft.id,
                action="created_or_updated_draft",
                actor=actor,
                timestamp=draft.updated_at,
                details={
                    "scheme_name": draft.scheme_name,
                    "version": draft.version,
                    "has_conflicts": draft.has_conflicts,
                    "missing_fields": draft.missing_fields_count,
                    "sources": draft.source_document_ids
                }
            )
        )
        return draft

    def find_draft_by_source_or_name(
        self,
        source_id: Optional[str] = None,
        scheme_name: Optional[str] = None
    ) -> Optional[SchemeDraft]:
        """
        Locates an existing draft record by source document filename or scheme title.
        Prevents duplicate draft records when processing the same document repeatedly.
        """
        all_drafts = self.db.list_drafts()
        for d in all_drafts:
            if source_id and source_id in d.source_document_ids:
                return d
            if scheme_name and d.scheme_name.strip().lower() == scheme_name.strip().lower():
                return d
        return None

    def edit_field(
        self,
        draft_id: str,
        field_name: str,
        new_value: Any,
        reviewer_id: str,
        reason: str
    ) -> SchemeDraft:
        """
        Allows reviewer to correct or resolve a field value.
        Logs audit record with prior value, new value, and rationale.
        """
        draft = self.db.get_draft(draft_id)
        if not draft:
            raise ReviewServiceError(f"Draft with ID '{draft_id}' not found.")

        if field_name not in draft.fields:
            raise ReviewServiceError(f"Invalid field name '{field_name}'.")

        if not reviewer_id or not reviewer_id.strip():
            raise ReviewServiceError("Reviewer ID is required for editing a field.")

        if not reason or not reason.strip():
            raise ReviewServiceError("A correction reason must be provided for the audit trail.")

        rec = draft.fields[field_name]
        old_val = rec.value
        old_status = rec.status

        # Apply correction
        now_iso = datetime.now(timezone.utc).isoformat()
        rec.value = new_value
        rec.status = FieldStatus.FOUND if new_value is not None else FieldStatus.NOT_FOUND
        rec.note = f"Manually verified and updated by reviewer '{reviewer_id}': {reason}"
        rec.confidence = 1.0  # Human-verified value has absolute confidence

        # Re-evaluate draft conflict flag
        draft.has_conflicts = any(r.status == FieldStatus.CONFLICT for r in draft.fields.values())
        draft.missing_fields_count = sum(1 for r in draft.fields.values() if r.status == FieldStatus.NOT_FOUND)
        draft.updated_at = now_iso

        self.db.save_draft(draft)

        # Record audit entry
        self.db.log_audit_entry(
            ReviewAuditEntry(
                id=str(uuid.uuid4()),
                scheme_id=draft.id,
                action="field_edited",
                actor=reviewer_id,
                timestamp=now_iso,
                details={
                    "field": field_name,
                    "old_value": old_val,
                    "new_value": new_value,
                    "old_status": old_status.value if isinstance(old_status, FieldStatus) else old_status,
                    "new_status": rec.status.value,
                    "reason": reason
                }
            )
        )

        return draft

    def approve_draft(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_notes: Optional[str] = None
    ) -> ApprovedScheme:
        """
        Validates draft and promotes it to the immutable scheme_approved repository.
        Prevents approval if conflicts remain unresolved.
        """
        draft = self.db.get_draft(draft_id)
        if not draft:
            raise ReviewServiceError(f"Draft with ID '{draft_id}' not found.")

        if not reviewer_id or not reviewer_id.strip():
            raise ReviewServiceError("Reviewer ID is mandatory for approving a scheme.")

        # Safety Gate 1: Check unresolved conflicts
        if draft.has_conflicts:
            conflicting_fields = [
                f for f, r in draft.fields.items() if r.status == FieldStatus.CONFLICT
            ]
            raise ReviewServiceError(
                f"Cannot approve draft with unresolved conflicts in: {', '.join(conflicting_fields)}. "
                "Reviewer must adjudicate conflicting fields before publication."
            )

        # Safety Gate 2: Scheme title check
        name_rec = draft.fields.get("scheme_name")
        if not name_rec or not name_rec.value or name_rec.status == FieldStatus.NOT_FOUND:
            raise ReviewServiceError("Cannot approve a scheme record without a valid scheme name.")

        now_iso = datetime.now(timezone.utc).isoformat()
        current_max_v = self.db.get_latest_approved_version(draft.id)
        new_version = current_max_v + 1

        # Calculate cryptographic tamper audit hash
        fields_repr = json.dumps(
            {k: v.model_dump() for k, v in draft.fields.items()},
            sort_keys=True,
            ensure_ascii=False
        )
        audit_hash = hashlib.sha256(
            f"{draft.id}:{new_version}:{reviewer_id}:{now_iso}:{fields_repr}".encode("utf-8")
        ).hexdigest()

        approved_record = ApprovedScheme(
            id=draft.id,
            draft_id=draft.id,
            scheme_name=draft.scheme_name,
            version=new_version,
            approved_by=reviewer_id,
            approved_at=now_iso,
            fields=draft.fields,
            reviewer_notes=reviewer_notes,
            audit_hash=audit_hash
        )

        # Save to approved table
        self.db.save_approved_scheme(approved_record)

        # Update draft review status
        draft.review_status = ReviewStatus.APPROVED
        draft.version = new_version
        draft.updated_at = now_iso
        self.db.save_draft(draft)

        # Log audit entry
        self.db.log_audit_entry(
            ReviewAuditEntry(
                id=str(uuid.uuid4()),
                scheme_id=draft.id,
                action="approved",
                actor=reviewer_id,
                timestamp=now_iso,
                details={
                    "version": new_version,
                    "reviewer_notes": reviewer_notes,
                    "audit_hash": audit_hash
                }
            )
        )

        return approved_record

    def reject_draft(
        self,
        draft_id: str,
        reviewer_id: str,
        rejection_reason: str
    ) -> SchemeDraft:
        """Marks a draft as rejected with an explicit recorded rationale."""
        draft = self.db.get_draft(draft_id)
        if not draft:
            raise ReviewServiceError(f"Draft with ID '{draft_id}' not found.")

        if not reviewer_id or not reviewer_id.strip():
            raise ReviewServiceError("Reviewer ID is mandatory for rejection.")

        if not rejection_reason or not rejection_reason.strip():
            raise ReviewServiceError("A specific rejection reason must be provided.")

        now_iso = datetime.now(timezone.utc).isoformat()
        draft.review_status = ReviewStatus.REJECTED
        draft.updated_at = now_iso
        self.db.save_draft(draft)

        self.db.log_audit_entry(
            ReviewAuditEntry(
                id=str(uuid.uuid4()),
                scheme_id=draft.id,
                action="rejected",
                actor=reviewer_id,
                timestamp=now_iso,
                details={"rejection_reason": rejection_reason}
            )
        )

        return draft

    def get_audit_trail(self, scheme_id: str) -> List[ReviewAuditEntry]:
        return self.db.get_audit_trail(scheme_id)

    def get_audit_history(self, scheme_id: str) -> List[ReviewAuditEntry]:
        """Alias for get_audit_trail."""
        return self.get_audit_trail(scheme_id)

    def get_draft(self, draft_id: str) -> Optional[SchemeDraft]:
        return self.db.get_draft(draft_id)

    def list_drafts(self, review_status: Optional[str] = None) -> List[SchemeDraft]:
        return self.db.list_drafts(review_status)

    def list_approved_schemes(self) -> List[ApprovedScheme]:
        return self.db.list_approved_schemes()
