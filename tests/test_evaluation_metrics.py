"""
Tests for Evaluation Metrics, Denominator Accounting, and Metric Calculation.
"""

from src.evaluation.evaluator import SchemeEvaluator
from src.models.schemas import Evidence, FieldStatus, SchemeDraft, SchemeFieldRecord


def test_evaluator_metrics_denominators():
    evaluator = SchemeEvaluator()

    # Create synthetic test drafts matching ground truth
    draft_kisan = SchemeDraft(
        id="kisan",
        scheme_name="Kisan Samriddhi Support Yojana (Synthetic)",
        source_document_ids=["kisan_samriddhi_yojana.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "scheme_name": SchemeFieldRecord(
                scheme_ref="Kisan Samriddhi",
                field="scheme_name",
                value="Kisan Samriddhi Support Yojana (Synthetic)",
                evidence=[Evidence(quotation="Kisan Samriddhi Support Yojana (Synthetic)", source_id="kisan_samriddhi_yojana.pdf", page_or_section=1, capture_date="2026-10-30T12:00:00Z", is_verified=True)],
                status=FieldStatus.FOUND
            ),
            "benefit_amount": SchemeFieldRecord(
                scheme_ref="Kisan Samriddhi",
                field="benefit_amount",
                value="Rs. 6,000 per year",
                evidence=[Evidence(quotation="guaranteed financial assistance of Rs. 6,000 per year", source_id="kisan_samriddhi_yojana.pdf", page_or_section=1, capture_date="2026-10-30T12:00:00Z", is_verified=True)],
                status=FieldStatus.FOUND
            ),
            "deadline": SchemeFieldRecord(
                scheme_ref="Kisan Samriddhi",
                field="deadline",
                value="31 March 2025",
                evidence=[Evidence(quotation="final deadline for enrolling under the current fiscal cycle is 31 March 2025", source_id="kisan_samriddhi_yojana.pdf", page_or_section=1, capture_date="2026-10-30T12:00:00Z", is_verified=True)],
                status=FieldStatus.FOUND
            )
        }
    )

    draft_hindi = SchemeDraft(
        id="hindi",
        scheme_name="महिला स्वावलंबन स्वरोजगार योजना (सिंथेटिक)",
        source_document_ids=["mahila_swavalamban_yojana.pdf"],
        created_at="2026-10-30T12:00:00Z",
        updated_at="2026-10-30T12:00:00Z",
        fields={
            "deadline": SchemeFieldRecord(
                scheme_ref="Mahila",
                field="deadline",
                value=None,
                status=FieldStatus.NOT_FOUND,
                note="Not mentioned in document"
            ),
            "official_link": SchemeFieldRecord(
                scheme_ref="Mahila",
                field="official_link",
                value=None,
                status=FieldStatus.NOT_FOUND,
                note="Not cited in notification"
            )
        }
    )

    drafts = {
        "kisan_samriddhi_yojana.pdf": draft_kisan,
        "mahila_swavalamban_yojana.pdf": draft_hindi
    }

    report = evaluator.evaluate_drafts(drafts)

    # Check that denominators are explicit and positive
    assert report.overall_field_accuracy.denominator > 0
    assert report.overall_field_accuracy.numerator <= report.overall_field_accuracy.denominator

    # Check high-risk metric
    assert report.amount_and_deadline_accuracy.denominator >= 2
    assert report.amount_and_deadline_accuracy.numerator >= 2

    # Check missing-field handling
    assert report.missing_field_metrics["precision"] >= 0.0
    assert report.missing_field_metrics["recall"] >= 0.0
    assert report.missing_field_metrics["true_positives"] >= 2  # deadline and official_link in hindi
