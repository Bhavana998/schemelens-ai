"""
Automated Evaluation and Integration Tests for SchemeLens AI Synthetic Fixture.

Validates:
1. Field-level extraction accuracy against synthetic test document kisan_samriddhi_yojana.pdf.
2. Benefit amount and deadline accuracy.
3. Evidence quotation and page correctness (Page 1 citations, verbatim text occurrence).
4. Missing-field handling (deliberate omissions remain FieldStatus.NOT_FOUND).
5. Conflicting-source detection (multi-source merge preserves both sides with quotes).
6. Human edits and approval workflow (audit logging, version snapshot).
7. Invalid model output and unreadable PDF handling.
8. Complete operation without an API key (MOCK mode).
9. Duplicate draft prevention when re-processing the same document.
10. Dynamic heuristic fallback for arbitrary documents (no hardcoded answers for non-fixtures).
"""

from pathlib import Path
import pytest
import tempfile

from src.processing.extractor import DocumentProcessor
from src.ingestion.validator import DocumentValidator
from src.extraction.extractor import SchemeExtractor
from src.extraction.llm_provider import MockLLMProvider, LLMProviderError
from src.validation.evidence_verifier import EvidenceVerifier
from src.conflict.detector import ConflictDetector
from src.models.schemas import FieldStatus, DocumentContent, ExtractedPage, RawExtractionPayload
from src.review.service import ReviewService
from src.storage.db import DatabaseManager


def load_doc(path: Path) -> DocumentContent:
    processor = DocumentProcessor()
    with open(path, "rb") as f:
        pdf_bytes = f.read()
    return processor.extract_document(
        document_id=path.name,
        filename=path.name,
        file_bytes=pdf_bytes
    )


@pytest.fixture
def test_pdf_path():
    path = Path("data/sample_documents/kisan_samriddhi_yojana.pdf")
    assert path.exists(), f"Synthetic test document fixture not found at {path}"
    return path


@pytest.fixture
def temp_review_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_schemelens.db"
        db = DatabaseManager(str(db_path))
        yield ReviewService(db=db)


def test_synthetic_fixture_field_level_extraction_accuracy(test_pdf_path):
    """
    1. Field-level extraction accuracy against synthetic test document kisan_samriddhi_yojana.pdf.
    Expected values:
    - Scheme name: Kisan Samriddhi Support Yojana (Synthetic)
    - Department: Department of Agriculture & Farmers Welfare (Synthetic)
    - Benefit type: Direct Cash Transfer
    - Benefit amount: Rs. 6,000 per year
    - Benefit frequency: Annual, paid in three equal installments of Rs. 2,000 every four months
    - Eligibility: Small and marginal farmers owning cultivable agricultural land up to 2 hectares...
    - Required documents: Aadhaar Card, Land Ownership Record (Khatauni or Khasra certificate), and active bank account passbook with IFSC code
    - Application procedure: Official web portal or local Common Service Centre (CSC)...
    - Deadline: 31 March 2025
    - Source URL: https://synthetic-portal.gov.in/schemes/kisan-samriddhi
    """
    doc_content = load_doc(test_pdf_path)
    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft, metrics = extractor.extract_scheme_draft(doc_content)
    verified_draft = EvidenceVerifier.verify_draft_evidence(draft, {doc_content.document_id: doc_content})

    fields = verified_draft.fields

    # 1. Scheme Name
    assert fields["scheme_name"].value == "Kisan Samriddhi Support Yojana (Synthetic)"
    assert fields["scheme_name"].status == FieldStatus.FOUND

    # 2. Department
    assert fields["department"].value == "Department of Agriculture & Farmers Welfare (Synthetic)"
    assert fields["department"].status == FieldStatus.FOUND

    # 3. Benefit Type
    assert fields["benefit_type"].value == "Direct Cash Transfer"

    # 4. Benefit Amount (High-risk)
    assert fields["benefit_amount"].value == "Rs. 6,000 per year"

    # 5. Benefit Frequency
    assert "three equal installments of Rs. 2,000 every four months" in fields["benefit_frequency"].value

    # 6. Eligibility
    assert "Small and marginal farmers" in fields["eligibility_conditions"].value
    assert "2 hectares" in fields["eligibility_conditions"].value

    # 7. Required Documents
    assert "Aadhaar Card" in fields["required_documents"].value
    assert "Khatauni" in fields["required_documents"].value

    # 8. Application Procedure
    assert "Common Service Centre" in fields["application_procedure"].value
    assert "21 working days" in fields["application_procedure"].value

    # 9. Deadline (High-risk)
    assert fields["deadline"].value == "31 March 2025"

    # 10. Source URL
    assert fields["official_link"].value == "https://synthetic-portal.gov.in/schemes/kisan-samriddhi"


def test_high_risk_amount_and_deadline_accuracy(test_pdf_path):
    """2. Benefit amount and deadline accuracy."""
    doc_content = load_doc(test_pdf_path)
    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft, _ = extractor.extract_scheme_draft(doc_content)

    assert draft.fields["benefit_amount"].value == "Rs. 6,000 per year"
    assert draft.fields["deadline"].value == "31 March 2025"


def test_evidence_quotations_and_page_correctness(test_pdf_path):
    """
    3. Evidence quotation and page correctness.
    - All quotations must occur verbatim in the source text.
    - For this 1-page PDF, all page citations must reference page 1.
    - Unverified or mismatched citations must not be marked verified.
    """
    doc_content = load_doc(test_pdf_path)
    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft, _ = extractor.extract_scheme_draft(doc_content)
    verified_draft = EvidenceVerifier.verify_draft_evidence(draft, {doc_content.document_id: doc_content})

    for field_name, field_rec in verified_draft.fields.items():
        if field_rec.status == FieldStatus.FOUND:
            assert len(field_rec.evidence) > 0, f"Field {field_name} marked FOUND without evidence!"
            for ev in field_rec.evidence:
                assert ev.page_or_section == 1, f"Field {field_name} cited page {ev.page_or_section}, expected page 1"
                assert ev.is_verified, f"Field {field_name} quotation failed verification: '{ev.quotation}'"
                # Check that quotation physically appears in page 1 text
                page_text = doc_content.pages[0].text
                match, _ = EvidenceVerifier.verify_quotation_in_page(ev.quotation, page_text)
                assert match, f"Quotation '{ev.quotation}' not found in page 1 text"


def test_missing_field_handling():
    """
    4. Missing-field handling.
    Missing fields must remain empty or explicitly use FieldStatus.NOT_FOUND with an explanatory note.
    """
    extractor = SchemeExtractor(provider=MockLLMProvider())
    doc = DocumentContent(
        document_id="mahila_swavalamban_yojana.pdf",
        filename="mahila_swavalamban_yojana.pdf",
        file_hash="hash_mahila",
        total_pages=1,
        pages=[ExtractedPage(page_number=1, text="महिला स्वावलंबन स्वरोजगार योजना")],
        raw_full_text="महिला स्वावलंबन स्वरोजगार योजना"
    )
    draft, _ = extractor.extract_scheme_draft(doc)

    deadline_field = draft.fields["deadline"]
    assert deadline_field.value is None
    assert deadline_field.status == FieldStatus.NOT_FOUND
    assert deadline_field.note is not None
    assert len(deadline_field.evidence) == 0

    link_field = draft.fields["official_link"]
    assert link_field.value is None
    assert link_field.status == FieldStatus.NOT_FOUND


def test_conflicting_source_detection(test_pdf_path):
    """
    5. Conflicting-source detection.
    When two documents have different values (e.g. revised circular has Rs. 8,000 and 31 Dec 2025),
    both values, source names, and quotations must be preserved and flagged for reviewer resolution.
    No silent overwrite, no artificial conflicts when values agree.
    """
    revised_pdf_path = Path("data/sample_documents/kisan_samriddhi_revised_circular.pdf")
    assert revised_pdf_path.exists()

    doc_base = load_doc(test_pdf_path)
    doc_rev = load_doc(revised_pdf_path)

    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft_base, _ = extractor.extract_scheme_draft(doc_base)
    draft_rev, _ = extractor.extract_scheme_draft(doc_rev)

    verified_base = EvidenceVerifier.verify_draft_evidence(draft_base, {doc_base.document_id: doc_base})
    verified_rev = EvidenceVerifier.verify_draft_evidence(draft_rev, {doc_rev.document_id: doc_rev})

    merged = ConflictDetector.merge_drafts(verified_base, verified_rev)

    assert merged.has_conflicts is True

    # Benefit amount conflict
    amount_rec = merged.fields["benefit_amount"]
    assert amount_rec.status == FieldStatus.CONFLICT
    assert isinstance(amount_rec.value, dict)
    assert amount_rec.value["kisan_samriddhi_yojana.pdf"] == "Rs. 6,000 per year"
    assert amount_rec.value["kisan_samriddhi_revised_circular.pdf"] == "Rs. 8,000 per year"
    assert len(amount_rec.evidence) == 2

    # Deadline conflict
    deadline_rec = merged.fields["deadline"]
    assert deadline_rec.status == FieldStatus.CONFLICT
    assert isinstance(deadline_rec.value, dict)
    assert deadline_rec.value["kisan_samriddhi_yojana.pdf"] == "31 March 2025"
    assert deadline_rec.value["kisan_samriddhi_revised_circular.pdf"] == "30 June 2025"

    # Scheme name must NOT conflict (sources agree)
    name_rec = merged.fields["scheme_name"]
    assert name_rec.status == FieldStatus.FOUND
    assert name_rec.value == "Kisan Samriddhi Support Yojana (Synthetic)"


def test_human_edits_and_approval_workflow(temp_review_service, test_pdf_path):
    """
    6. Human edits and approval workflow.
    - Edits must update the field, set confidence to 1.0, and record an audit log entry.
    - Approval must create a separate versioned approved record and lock the draft.
    """
    doc_content = load_doc(test_pdf_path)
    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft, _ = extractor.extract_scheme_draft(doc_content)
    verified_draft = EvidenceVerifier.verify_draft_evidence(draft, {doc_content.document_id: doc_content})

    temp_review_service.create_or_update_draft(verified_draft, actor="test_user")

    # 1. Edit a field
    updated = temp_review_service.edit_field(
        draft_id=verified_draft.id,
        field_name="benefit_amount",
        new_value="Rs. 7,000 per year (Amended)",
        reviewer_id="lead_reviewer_bob",
        reason="Updated following Gazette notification"
    )
    assert updated.fields["benefit_amount"].value == "Rs. 7,000 per year (Amended)"
    assert updated.fields["benefit_amount"].confidence == 1.0

    # 2. Check audit trail
    audit_history = temp_review_service.get_audit_history(verified_draft.id)
    assert any(log.action == "field_edited" and log.actor == "lead_reviewer_bob" for log in audit_history)

    # 3. Approve draft
    approved_record = temp_review_service.approve_draft(verified_draft.id, reviewer_id="lead_reviewer_bob")
    assert approved_record.version == 1
    assert approved_record.fields["benefit_amount"].value == "Rs. 7,000 per year (Amended)"

    # 4. Drafts and approved records remain separate
    drafts = temp_review_service.list_drafts()
    approved = temp_review_service.list_approved_schemes()
    assert len(approved) == 1
    assert approved[0].draft_id == verified_draft.id


def test_invalid_model_output_and_unreadable_pdf_handling():
    """
    7. Invalid model output and unreadable PDF handling.
    - Corrupt and empty files must be cleanly rejected by DocumentValidator.
    - Ingestion must fail gracefully without crash or fabrication.
    """
    # Empty file
    valid, err, _ = DocumentValidator.validate_file("empty.pdf", b"")
    assert not valid
    assert "empty" in err.lower()

    # Corrupt PDF
    valid, err, _ = DocumentValidator.validate_file("corrupt.pdf", b"%PDF-1.4\nGarbage data corrupt content")
    assert not valid
    assert "corrupted" in err.lower() or "invalid" in err.lower()

    # Invalid LLM response: simulate failure
    failing_provider = MockLLMProvider(simulate_failure=True, failure_message="Model Output Malformed JSON")
    extractor = SchemeExtractor(provider=failing_provider)
    doc = DocumentContent(
        document_id="sample.pdf",
        filename="sample.pdf",
        file_hash="hash",
        total_pages=1,
        pages=[ExtractedPage(page_number=1, text="Sample text")],
        raw_full_text="Sample text"
    )
    with pytest.raises(LLMProviderError) as exc_info:
        extractor.extract_scheme_draft(doc)
    assert "Model Output Malformed JSON" in str(exc_info.value)


def test_operation_without_api_key(test_pdf_path):
    """
    8. Operation without an API key.
    MOCK mode runs completely offline with no network calls or API keys required.
    """
    extractor = SchemeExtractor(provider=MockLLMProvider())
    doc_content = load_doc(test_pdf_path)
    draft, metrics = extractor.extract_scheme_draft(doc_content)

    assert metrics["estimated_cost_usd"] == 0.0
    assert metrics["model_name"] == "mock-schemelens-engine-v1"
    assert draft.scheme_name is not None


def test_duplicate_draft_prevention(temp_review_service, test_pdf_path):
    """
    9. Check for duplicate draft creation when processing the same file repeatedly.
    Re-extracting or re-saving the same document reuses the existing draft record.
    """
    doc_content = load_doc(test_pdf_path)
    extractor = SchemeExtractor(provider=MockLLMProvider())

    # First run
    draft1, _ = extractor.extract_scheme_draft(doc_content)
    temp_review_service.create_or_update_draft(draft1, actor="user")

    # Second run for same source
    existing = temp_review_service.find_draft_by_source_or_name(
        source_id=doc_content.document_id,
        scheme_name="Kisan Samriddhi Support Yojana (Synthetic)"
    )
    assert existing is not None
    assert existing.id == draft1.id

    # Re-extracting with existing scheme_id updates the existing draft
    draft2, _ = extractor.extract_scheme_draft(doc_content, scheme_id=existing.id)
    temp_review_service.create_or_update_draft(draft2, actor="user")

    drafts = temp_review_service.list_drafts()
    matching_drafts = [d for d in drafts if d.id == draft1.id]
    assert len(matching_drafts) == 1, "Duplicate draft created for the same source document!"


def test_arbitrary_document_extraction_no_hardcoding():
    """
    10. Verify that arbitrary uploaded documents do NOT return hardcoded Kisan Samriddhi answers.
    Mock provider must dynamically extract patterns via heuristic fallback.
    """
    arbitrary_text = (
        "GOVERNMENT OF MEGHALAYA\n"
        "SCHEME NOTIFICATION: Solar Pump Irrigation Scheme 2026\n"
        "Department of Renewable Energy Development\n\n"
        "Financial grant: Subsidy of Rs. 45,000 per pump set for solar installation.\n"
        "Eligibility: Farmers with verified water source and minimum 1 acre land.\n"
        "Application: Submit through the official portal before 15 November 2026.\n"
        "Official link: https://synthetic-meghalaya.gov.in/solar-pump\n"
    )
    doc = DocumentContent(
        document_id="arbitrary_solar.pdf",
        filename="arbitrary_solar.pdf",
        file_hash="hash_solar_123",
        total_pages=1,
        pages=[ExtractedPage(page_number=1, text=arbitrary_text)],
        raw_full_text=arbitrary_text
    )

    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft, _ = extractor.extract_scheme_draft(doc)

    # Must NOT be Kisan Samriddhi
    assert draft.scheme_name != "Kisan Samriddhi Support Yojana (Synthetic)"
    assert "Solar Pump Irrigation Scheme 2026" in draft.scheme_name
    assert draft.fields["benefit_amount"].value == "Rs. 45,000"
    assert draft.fields["deadline"].value == "15 November 2026"
    assert draft.fields["official_link"].value == "https://synthetic-meghalaya.gov.in/solar-pump"
