"""
Tests for Human Review Workflow, Approval Gates, Versioning, and Persistent Storage.
"""

import tempfile
from pathlib import Path
import pytest

from src.models.schemas import (
    Evidence,
    FieldStatus,
    ReviewStatus,
    SchemeDraft,
    SchemeFieldRecord,
)
from src.review.service import ReviewService, ReviewServiceError
from src.storage.db import DatabaseManager


@pytest.fixture
def temp_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_schemelens.db"
        db = DatabaseManager(str(db_path))
        yield ReviewService(db=db)


def test_field_editing_and_audit_trail(temp_service):
    draft = SchemeDraft(
        id="draft-edit-1",
        scheme_name="Test Scheme",
        source_document_ids=["doc1.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Test Scheme",
                field="benefit_amount",
                value="Rs. 5,000",
                status=FieldStatus.FOUND
            )
        }
    )
    temp_service.create_or_update_draft(draft, actor="system")

    # Perform field edit
    updated = temp_service.edit_field(
        draft_id="draft-edit-1",
        field_name="benefit_amount",
        new_value="Rs. 6,000",
        reviewer_id="reviewer_alice",
        reason="Corrected based on gazette amendment"
    )

    assert updated.fields["benefit_amount"].value == "Rs. 6,000"
    assert updated.fields["benefit_amount"].confidence == 1.0

    # Verify audit trail
    audit_trail = temp_service.get_audit_history("draft-edit-1")
    assert len(audit_trail) >= 2  # created + edited
    latest = audit_trail[0]
    assert latest.action == "field_edited"
    assert latest.actor == "reviewer_alice"
    assert latest.details["old_value"] == "Rs. 5,000"
    assert latest.details["new_value"] == "Rs. 6,000"
    assert latest.details["reason"] == "Corrected based on gazette amendment"


def test_cannot_approve_draft_with_unresolved_conflicts(temp_service):
    draft = SchemeDraft(
        id="draft-conflict-1",
        scheme_name="Conflicted Scheme",
        source_document_ids=["doc_a.pdf", "doc_b.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        has_conflicts=True,
        fields={
            "scheme_name": SchemeFieldRecord(
                scheme_ref="Conflicted Scheme",
                field="scheme_name",
                value="Conflicted Scheme",
                status=FieldStatus.FOUND
            ),
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Conflicted Scheme",
                field="benefit_amount",
                value={"doc_a.pdf": "Rs. 6,000", "doc_b.pdf": "Rs. 8,000"},
                status=FieldStatus.CONFLICT
            )
        }
    )
    temp_service.create_or_update_draft(draft)

    with pytest.raises(ReviewServiceError) as exc_info:
        temp_service.approve_draft("draft-conflict-1", reviewer_id="reviewer_alice")

    assert "Cannot approve draft with unresolved conflicts" in str(exc_info.value)


def test_approval_workflow_and_version_protection(temp_service):
    draft = SchemeDraft(
        id="draft-approve-1",
        scheme_name="Pradhan Mantri Awas Yojana (Synthetic)",
        source_document_ids=["doc_clean.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        has_conflicts=False,
        fields={
            "scheme_name": SchemeFieldRecord(
                scheme_ref="Pradhan Mantri Awas Yojana (Synthetic)",
                field="scheme_name",
                value="Pradhan Mantri Awas Yojana (Synthetic)",
                status=FieldStatus.FOUND
            ),
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Pradhan Mantri Awas Yojana (Synthetic)",
                field="benefit_amount",
                value="Rs. 1,20,000",
                status=FieldStatus.FOUND
            )
        }
    )
    temp_service.create_or_update_draft(draft)

    # 1. First Approval -> Version 1
    approved_v1 = temp_service.approve_draft(
        draft_id="draft-approve-1",
        reviewer_id="senior_evaluator_01",
        reviewer_notes="Verified against official release."
    )

    assert approved_v1.version == 1
    assert approved_v1.approved_by == "senior_evaluator_01"
    assert approved_v1.audit_hash is not None

    # Verify draft status updated to APPROVED
    draft_after = temp_service.get_draft("draft-approve-1")
    assert draft_after.review_status == ReviewStatus.APPROVED

    # 2. Modify draft and approve again -> Version 2 (preserves Version 1)
    temp_service.edit_field(
        draft_id="draft-approve-1",
        field_name="benefit_amount",
        new_value="Rs. 1,30,000",
        reviewer_id="senior_evaluator_01",
        reason="Annual inflation adjustment"
    )

    approved_v2 = temp_service.approve_draft(
        draft_id="draft-approve-1",
        reviewer_id="senior_evaluator_01",
        reviewer_notes="Approved amended financial outlay."
    )

    assert approved_v2.version == 2
    assert approved_v2.fields["benefit_amount"].value == "Rs. 1,30,000"

    # Verify approved catalog preserves latest
    approved_list = temp_service.list_approved_schemes()
    assert len(approved_list) == 1
    assert approved_list[0].version == 2


def test_rejection_workflow(temp_service):
    draft = SchemeDraft(
        id="draft-reject-1",
        scheme_name="Bogus Circular Scheme",
        source_document_ids=["fake.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "scheme_name": SchemeFieldRecord(
                scheme_ref="Bogus Circular Scheme",
                field="scheme_name",
                value="Bogus Circular Scheme",
                status=FieldStatus.FOUND
            )
        }
    )
    temp_service.create_or_update_draft(draft)

    rejected_draft = temp_service.reject_draft(
        draft_id="draft-reject-1",
        reviewer_id="reviewer_bob",
        rejection_reason="Unverified circular originating from unauthorized website."
    )

    assert rejected_draft.review_status == ReviewStatus.REJECTED

    # Verify in audit log
    audit_entries = temp_service.get_audit_history("draft-reject-1")
    assert audit_entries[0].action == "rejected"
    assert audit_entries[0].details["rejection_reason"] == "Unverified circular originating from unauthorized website."
