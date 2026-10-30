"""
Tests for PDF Text Extraction, Page References, and OCR Fallback.
"""

from pathlib import Path
import pytest

from src.processing.extractor import DocumentProcessor

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = BASE_DIR / "data" / "sample_documents"


def test_digital_pdf_text_extraction():
    processor = DocumentProcessor()
    pdf_path = SAMPLE_DIR / "kisan_samriddhi_yojana.pdf"
    assert pdf_path.exists()

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    doc_content = processor.extract_document(
        document_id="kisan_samriddhi_yojana.pdf",
        filename="kisan_samriddhi_yojana.pdf",
        file_bytes=pdf_bytes
    )

    assert doc_content.total_pages == 1
    assert len(doc_content.pages) == 1
    assert doc_content.pages[0].page_number == 1
    assert doc_content.pages[0].extraction_method == "pdf_text"
    assert not doc_content.pages[0].is_scanned
    assert "KISAN SAMRIDDHI SUPPORT YOJANA" in doc_content.pages[0].text
    assert "Rs. 6,000 per year" in doc_content.raw_full_text


def test_scanned_pdf_ocr_fallback():
    processor = DocumentProcessor()
    if not processor.is_tesseract_available():
        pytest.skip("Tesseract OCR binary not installed on test host.")

    scanned_path = SAMPLE_DIR / "yuva_kaushal_scanned.pdf"
    assert scanned_path.exists()

    with open(scanned_path, "rb") as f:
        scanned_bytes = f.read()

    doc_content = processor.extract_document(
        document_id="yuva_kaushal_scanned.pdf",
        filename="yuva_kaushal_scanned.pdf",
        file_bytes=scanned_bytes
    )

    assert doc_content.ocr_applied
    assert doc_content.pages[0].is_scanned
    assert doc_content.pages[0].extraction_method == "ocr"
    assert len(doc_content.pages[0].text) > 50
    assert "Yuva Kaushal" in doc_content.pages[0].text or "Kaushal" in doc_content.pages[0].text


def test_ocr_missing_hindi_pack_detection():
    processor = DocumentProcessor()
    # Test preferred_lang="hin" when hin is missing
    installed = processor.get_installed_ocr_languages()
    if "hin" not in installed:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        text, method, warning = processor._ocr_image(img, preferred_lang="hin")
        assert warning is not None
        assert "hin.traineddata" in warning
        assert "Setup instruction" in warning


def test_ocr_unavailable_failure_path():
    # Pass a non-existent tesseract binary path to test failure path
    processor = DocumentProcessor(tesseract_cmd=r"C:\NonExistent\tesseract_fake.exe")
    processor.is_tesseract_available = lambda: False

    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    text, method, warning = processor._ocr_image(img, preferred_lang="eng")

    assert method == "ocr_unavailable"
    assert "Tesseract OCR is not installed" in warning
    assert text == ""


def test_scanned_pdf_timing_and_evidence_verification():
    """
    Tests the Yuva Kaushal scanned PDF extraction workflow:
    1. Validates that Tesseract OCR executes on the raster image and reports correct page count (1).
    2. Validates that OCR text is substantial (> 500 characters) and contains expected content.
    3. Verifies every evidence quote against the OCR output on Page 1.
    4. Validates that OCR duration and LLM extraction duration are recorded separately and are positive.
    5. Verifies that missing fields (e.g. official_link) remain FieldStatus.NOT_FOUND with explicit note.
    """
    processor = DocumentProcessor()
    if not processor.is_tesseract_available():
        pytest.skip("Tesseract OCR binary not installed on test host.")

    scanned_path = SAMPLE_DIR / "yuva_kaushal_scanned.pdf"
    assert scanned_path.exists()

    with open(scanned_path, "rb") as f:
        scanned_bytes = f.read()

    # 1. OCR execution and timing
    doc_content = processor.extract_document(
        document_id="yuva_kaushal_scanned.pdf",
        filename="yuva_kaushal_scanned.pdf",
        file_bytes=scanned_bytes
    )

    assert doc_content.total_pages == 1
    assert doc_content.ocr_applied is True
    assert doc_content.metadata["ocr_duration_sec"] > 0
    assert doc_content.metadata["processing_duration_sec"] > 0
    assert len(doc_content.pages[0].text) > 500
    assert "Yuva Kaushal" in doc_content.pages[0].text
    assert "3,500" in doc_content.pages[0].text

    # 2. Scheme extraction and timing breakdown
    from src.extraction.extractor import SchemeExtractor
    from src.extraction.llm_provider import MockLLMProvider
    from src.models.schemas import FieldStatus
    from src.validation.evidence_verifier import EvidenceVerifier

    extractor = SchemeExtractor(provider=MockLLMProvider())
    draft, metrics = extractor.extract_scheme_draft(doc_content)

    assert metrics["ocr_duration_sec"] > 0
    assert metrics["total_duration_sec"] >= metrics["ocr_duration_sec"]
    assert draft.scheme_name == "Yuva Kaushal Stipend Program (Synthetic)"
    assert draft.fields["benefit_amount"].value == "Rs. 3,500 monthly stipend"

    # 3. Deterministic evidence verification against OCR output
    verified_draft = EvidenceVerifier.verify_draft_evidence(draft, {doc_content.document_id: doc_content})
    assert verified_draft.unverified_evidence_count == 0

    for field_name, f_rec in verified_draft.fields.items():
        if f_rec.status == FieldStatus.FOUND and f_rec.evidence:
            for ev in f_rec.evidence:
                assert ev.is_verified is True, f"Quote for {field_name} not verified in OCR text: {ev.quotation}"
                assert ev.page_or_section == 1

    # 4. Missing field preservation (official_link omitted in physical bulletin)
    link_field = verified_draft.fields["official_link"]
    assert link_field.status == FieldStatus.NOT_FOUND
    assert link_field.value is None
    assert len(link_field.evidence) == 0
    assert "bulletin" in link_field.note.lower()

