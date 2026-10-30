"""
Tests for Conflict Detection and Multi-Source Merging.
"""

from src.conflict.detector import ConflictDetector
from src.models.schemas import Evidence, FieldStatus, SchemeDraft, SchemeFieldRecord


def test_conflict_detection_benefit_amount():
    draft_a = SchemeDraft(
        id="draft-a",
        scheme_name="Kisan Samriddhi",
        source_document_ids=["source_a.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Kisan Samriddhi",
                field="benefit_amount",
                value="Rs. 6,000 per year",
                evidence=[
                    Evidence(
                        quotation="assistance of Rs. 6,000 per year",
                        source_id="source_a.pdf",
                        page_or_section=1,
                        capture_date="2026-10-30T12:00:00Z"
                    )
                ],
                confidence=0.95,
                status=FieldStatus.FOUND
            )
        }
    )

    draft_b = SchemeDraft(
        id="draft-b",
        scheme_name="Kisan Samriddhi",
        source_document_ids=["source_b.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Kisan Samriddhi",
                field="benefit_amount",
                value="Rs. 8,000 per year",
                evidence=[
                    Evidence(
                        quotation="revised to Rs. 8,000 per year",
                        source_id="source_b.pdf",
                        page_or_section=1,
                        capture_date="2026-10-30T12:00:00Z"
                    )
                ],
                confidence=0.92,
                status=FieldStatus.FOUND
            )
        }
    )

    merged = ConflictDetector.merge_drafts(draft_a, draft_b)

    assert merged.has_conflicts
    amount_rec = merged.fields["benefit_amount"]
    assert amount_rec.status == FieldStatus.CONFLICT
    assert isinstance(amount_rec.value, dict)
    assert amount_rec.value["source_a.pdf"] == "Rs. 6,000 per year"
    assert amount_rec.value["source_b.pdf"] == "Rs. 8,000 per year"
    # Verify BOTH evidence records are preserved
    assert len(amount_rec.evidence) == 2
    assert amount_rec.evidence[0].source_id == "source_a.pdf"
    assert amount_rec.evidence[1].source_id == "source_b.pdf"


def test_merge_missing_field_with_found_field():
    draft_base = SchemeDraft(
        id="draft-base",
        scheme_name="Welfare Scheme",
        source_document_ids=["notice.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "deadline": SchemeFieldRecord(
                scheme_ref="Welfare Scheme",
                field="deadline",
                value=None,
                evidence=[],
                status=FieldStatus.NOT_FOUND,
                note="No deadline specified in initial notice."
            )
        }
    )

    draft_supp = SchemeDraft(
        id="draft-supp",
        scheme_name="Welfare Scheme",
        source_document_ids=["circular_addendum.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "deadline": SchemeFieldRecord(
                scheme_ref="Welfare Scheme",
                field="deadline",
                value="31 December 2025",
                evidence=[
                    Evidence(
                        quotation="Last date for submission is 31 December 2025",
                        source_id="circular_addendum.pdf",
                        page_or_section=1,
                        capture_date="2026-10-30T12:00:00Z"
                    )
                ],
                status=FieldStatus.FOUND
            )
        }
    )

    merged = ConflictDetector.merge_drafts(draft_base, draft_supp)
    deadline_rec = merged.fields["deadline"]
    assert deadline_rec.status == FieldStatus.FOUND
    assert deadline_rec.value == "31 December 2025"
    assert len(deadline_rec.evidence) == 1
    assert not merged.has_conflicts
