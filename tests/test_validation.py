"""
Tests for Data Models, Ingestion Validation, and URL Validation.
"""

import pytest
from pydantic import ValidationError

from src.ingestion.validator import DocumentValidator
from src.models.schemas import (
    Evidence,
    FieldStatus,
    RawExtractionPayload,
    SchemeFieldRecord,
)
from src.validation.evidence_verifier import EvidenceVerifier


def test_scheme_field_record_valid():
    rec = SchemeFieldRecord(
        scheme_ref="Test Scheme",
        field="benefit_amount",
        value="Rs. 5,000",
        evidence=[
            Evidence(
                quotation="Rs. 5,000 financial support",
                source_id="test.pdf",
                page_or_section=1,
                capture_date="2026-10-30T12:00:00Z"
            )
        ],
        confidence=0.95,
        status=FieldStatus.FOUND
    )
    assert rec.status == FieldStatus.FOUND
    assert rec.value == "Rs. 5,000"
    assert rec.confidence == 0.95
    assert len(rec.evidence) == 1


def test_confidence_clamping():
    rec = SchemeFieldRecord(
        scheme_ref="Test",
        field="test",
        value="abc",
        confidence=1.5  # Out of normal 0-1 range
    )
    assert rec.confidence == 1.0

    rec2 = SchemeFieldRecord(
        scheme_ref="Test",
        field="test",
        value="abc",
        confidence=-0.5
    )
    assert rec2.confidence == 0.0


def test_empty_document_rejection():
    is_valid, msg, meta = DocumentValidator.validate_file("empty.pdf", b"")
    assert not is_valid
    assert "empty (0 bytes)" in msg


def test_unsupported_file_extension():
    is_valid, msg, meta = DocumentValidator.validate_file("document.docx", b"some content")
    assert not is_valid
    assert "Unsupported file extension" in msg


def test_corrupt_pdf_rejection():
    corrupt_bytes = b"%PDF-1.4\nCorrupted content completely invalid binary string"
    is_valid, msg, meta = DocumentValidator.validate_file("corrupt.pdf", corrupt_bytes)
    assert not is_valid
    assert "Corrupted or invalid PDF" in msg


def test_valid_url_validation():
    valid, err = EvidenceVerifier.validate_url("https://synthetic-portal.gov.in/schemes/kisan")
    assert valid
    assert err is None


def test_invalid_url_schemes():
    valid, err = EvidenceVerifier.validate_url("ftp://unsupported.com")
    assert not valid
    assert "Invalid URL protocol" in err

    valid2, err2 = EvidenceVerifier.validate_url("not-a-valid-url")
    assert not valid2
    assert "missing scheme" in err2


def test_placeholder_url_rejection():
    valid, err = EvidenceVerifier.validate_url("https://example.com/scheme")
    assert not valid
    assert "Placeholder URL detected" in err
