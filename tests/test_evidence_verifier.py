"""
Tests for Deterministic Evidence Quotation Verification.
"""

from src.models.schemas import (
    DocumentContent,
    Evidence,
    ExtractedPage,
    FieldStatus,
    SchemeDraft,
    SchemeFieldRecord,
)
from src.validation.evidence_verifier import EvidenceVerifier


def test_verbatim_quotation_match():
    page_text = "The department provides a financial assistance of Rs. 6,000 per year directly to eligible farmers."
    quote = "financial assistance of Rs. 6,000 per year"

    is_verified, msg = EvidenceVerifier.verify_quotation_in_page(quote, page_text)
    assert is_verified
    assert "Quotation verified" in msg


def test_quotation_mismatch():
    page_text = "The financial grant is Rs. 4,000 for small landholders."
    quote = "guaranteed stipend of Rs. 10,000 per month"

    is_verified, msg = EvidenceVerifier.verify_quotation_in_page(quote, page_text)
    assert not is_verified
    assert "Verification mismatch" in msg


def test_normalization_whitespace_and_unicode_quotes():
    page_text = 'The scheme is called “Kisan Samriddhi”—designed for farmers.\n\nAssistance:   Rs. 6,000.'
    quote = '"Kisan Samriddhi" - designed for farmers. Assistance: Rs. 6,000.'

    is_verified, msg = EvidenceVerifier.verify_quotation_in_page(quote, page_text)
    assert is_verified


def test_verify_draft_evidence_end_to_end():
    doc = DocumentContent(
        document_id="doc1.pdf",
        filename="doc1.pdf",
        file_hash="abc",
        total_pages=1,
        pages=[
            ExtractedPage(
                page_number=1,
                text="The deadline for enrollment is 31 March 2025. Annual assistance: Rs. 6,000."
            )
        ],
        raw_full_text="The deadline for enrollment is 31 March 2025. Annual assistance: Rs. 6,000."
    )

    draft = SchemeDraft(
        id="draft-1",
        scheme_name="Test Scheme",
        source_document_ids=["doc1.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "deadline": SchemeFieldRecord(
                scheme_ref="Test Scheme",
                field="deadline",
                value="31 March 2025",
                evidence=[
                    Evidence(
                        quotation="deadline for enrollment is 31 March 2025",
                        source_id="doc1.pdf",
                        page_or_section=1,
                        capture_date="2026-10-30T12:00:00Z"
                    )
                ],
                confidence=0.9,
                status=FieldStatus.FOUND
            ),
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Test Scheme",
                field="benefit_amount",
                value="Rs. 99,000",
                evidence=[
                    Evidence(
                        quotation="hallucinated quote not in text",
                        source_id="doc1.pdf",
                        page_or_section=1,
                        capture_date="2026-10-30T12:00:00Z"
                    )
                ],
                confidence=0.9,
                status=FieldStatus.FOUND
            )
        }
    )

    verified_draft = EvidenceVerifier.verify_draft_evidence(draft, {"doc1.pdf": doc})

    assert verified_draft.fields["deadline"].evidence[0].is_verified
    assert not verified_draft.fields["benefit_amount"].evidence[0].is_verified
    assert verified_draft.unverified_evidence_count == 1
