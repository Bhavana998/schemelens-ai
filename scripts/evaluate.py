"""
SchemeLens AI Evaluation Script.
Runs reproducible, automated benchmark across synthetic fixtures, verifies
evidence quotations, detects conflicts, and outputs rigorous field-level metrics.
"""

import json
from pathlib import Path
import sys

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.ingestion.validator import DocumentValidator
from src.processing.extractor import DocumentProcessor
from src.extraction.extractor import SchemeExtractor
from src.extraction.llm_provider import MockLLMProvider
from src.validation.evidence_verifier import EvidenceVerifier
from src.evaluation.evaluator import SchemeEvaluator


def run_evaluation():
    print("=" * 75)
    print("       SCHEMELENS AI - SYSTEM EVALUATION & BENCHMARK REPORT")
    print("=" * 75)

    base_dir = Path(__file__).resolve().parent.parent
    docs_dir = base_dir / "data" / "sample_documents"

    if not docs_dir.exists():
        print(f"Error: Directory {docs_dir} does not exist. Run scripts/generate_synthetic_data.py first.")
        sys.exit(1)

    # Initialize components
    processor = DocumentProcessor()
    extractor = SchemeExtractor(provider=MockLLMProvider())
    evaluator = SchemeEvaluator()

    sample_files = [
        "kisan_samriddhi_yojana.pdf",
        "kisan_samriddhi_revised_circular.pdf",
        "mahila_swavalamban_yojana.pdf",
        "yuva_kaushal_scanned.pdf",
    ]

    drafts_by_doc = {}
    documents_by_id = {}

    print(f"\n[1/3] Ingesting and Processing {len(sample_files)} Synthetic Documents...")
    for filename in sample_files:
        file_path = docs_dir / filename
        if not file_path.exists():
            print(f"  [MISSING] {filename}")
            continue

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        is_valid, err, meta = DocumentValidator.validate_file(filename, file_bytes)
        if not is_valid:
            print(f"  [INVALID] {filename}: {err}")
            continue

        # Extract document pages
        preferred_lang = "hin" if "mahila" in filename else "eng"
        doc_content = processor.extract_document(
            document_id=filename,
            filename=filename,
            file_bytes=file_bytes,
            preferred_lang=preferred_lang
        )
        documents_by_id[filename] = doc_content

        # Extract structured scheme draft
        draft, metrics = extractor.extract_scheme_draft(doc_content)

        # Deterministically verify evidence quotations
        draft = EvidenceVerifier.verify_draft_evidence(draft, {filename: doc_content})
        drafts_by_doc[filename] = draft

        ocr_info = f" [OCR Used]" if doc_content.ocr_applied else " [Digital Text]"
        warning_info = f" (Warning: {doc_content.ocr_warning[:35]}...)" if doc_content.ocr_warning else ""
        print(f"  [OK] Processed: {filename:<38} | Pages: {doc_content.total_pages}{ocr_info}{warning_info}")

    print(f"\n[2/3] Computing Metrics Against Verified Ground Truth...")
    report = evaluator.evaluate_drafts(drafts_by_doc)

    print("\n" + "=" * 75)
    print("                    FIELD-LEVEL ACCURACY & CITATIONS")
    print("=" * 75)
    print(f"{'Metric':<38} | {'Score':<8} | {'Numerator/Denominator':<22}")
    print("-" * 75)

    m1 = report.overall_field_accuracy
    print(f"{m1.name:<38} | {m1.value * 100:>5.1f}%  | {f'{m1.numerator}/{m1.denominator} fields':<22}")

    m2 = report.amount_and_deadline_accuracy
    print(f"{m2.name:<38} | {m2.value * 100:>5.1f}%  | {f'{m2.numerator}/{m2.denominator} fields':<22}")

    m3 = report.evidence_quotation_rate
    print(f"{m3.name:<38} | {m3.value * 100:>5.1f}%  | {f'{m3.numerator}/{m3.denominator} quotes':<22}")

    m4 = report.page_reference_accuracy
    print(f"{m4.name:<38} | {m4.value * 100:>5.1f}%  | {f'{m4.numerator}/{m4.denominator} pages':<22}")

    print("\n" + "=" * 75)
    print("                 MISSING-FIELD & CONFLICT DETECTION")
    print("=" * 75)
    mf = report.missing_field_metrics
    print(f"Missing-Field Precision:    {mf['precision'] * 100:.1f}%")
    print(f"Missing-Field Recall:       {mf['recall'] * 100:.1f}%")
    print(f"Missing-Field F1 Score:     {mf['f1_score'] * 100:.1f}%")
    print(f"  (True Positives: {mf['true_positives']}, False Positives: {mf['false_positives']}, False Negatives: {mf['false_negatives']})")

    cd = report.conflict_detection_metrics
    print("-" * 75)
    print(f"Conflict Detection Precision: {cd['precision'] * 100:.1f}%")
    print(f"Conflict Detection Recall:    {cd['recall'] * 100:.1f}%")
    print(f"Conflict Detection F1 Score:  {cd['f1'] * 100:.1f}%")
    print(f"  (Conflicts Detected: {cd.get('conflicts_detected', 0)}, Missed: {cd.get('missed_conflicts', 0)})")

    print("\n" + "=" * 75)
    print("                  PROPOSED QUALITY GATES FOR PILOT")
    print("=" * 75)
    for gate_name, description in report.proposed_pilot_quality_gates.items():
        print(f"• {gate_name}:")
        print(f"    {description}")

    # Save JSON report artifact
    report_path = base_dir / "data" / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)
    print(f"\n[3/3] Detailed report saved to: {report_path}")
    print("=" * 75)


if __name__ == "__main__":
    run_evaluation()
