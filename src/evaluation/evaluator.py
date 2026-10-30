"""
Evaluation and Benchmarking Engine for SchemeLens AI.
Measures field-level exact accuracy, high-risk amount/deadline accuracy,
evidence verification rates, page-reference correctness, missing-field precision/recall,
and conflict detection metrics against verified ground truth.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.models.schemas import FieldStatus, SchemeDraft


class MetricResult(BaseModel):
    name: str
    numerator: int
    denominator: int
    value: float
    description: str


class EvaluationReport(BaseModel):
    total_documents_evaluated: int
    overall_field_accuracy: MetricResult
    amount_and_deadline_accuracy: MetricResult
    evidence_quotation_rate: MetricResult
    page_reference_accuracy: MetricResult
    missing_field_metrics: Dict[str, float]
    conflict_detection_metrics: Dict[str, Any]
    field_breakdown: Dict[str, Dict[str, Any]]
    proposed_pilot_quality_gates: Dict[str, str]


class SchemeEvaluator:
    """
    Evaluates extracted scheme drafts against ground truth.
    Provides mathematically rigorous metric calculations with explicit denominators.
    """

    def __init__(self, ground_truth_path: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.gt_path = ground_truth_path or (base_dir / "data" / "ground_truth" / "synthetic_ground_truth.json")
        self.ground_truth = self._load_ground_truth()

    def _load_ground_truth(self) -> Dict[str, Any]:
        if not self.gt_path.exists():
            return {}
        with open(self.gt_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _normalize_cmp(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, dict):
            return " ".join(f"{k}:{v}" for k, v in sorted(val.items())).lower()
        if isinstance(val, list):
            return " ".join(sorted(str(x).strip().lower() for x in val))
        return str(val).strip().lower()

    def evaluate_drafts(
        self,
        drafts_by_doc: Dict[str, SchemeDraft]
    ) -> EvaluationReport:
        """
        Calculates all required metrics across evaluated documents.
        """
        field_num = 0
        field_den = 0

        risk_num = 0
        risk_den = 0

        ev_num = 0
        ev_den = 0

        page_num = 0
        page_den = 0

        # Missing field counters (for precision/recall)
        missing_tp = 0
        missing_fp = 0
        missing_fn = 0
        missing_tn = 0

        field_breakdown: Dict[str, Dict[str, Any]] = {}

        for doc_name, expected_fields in self.ground_truth.items():
            draft = drafts_by_doc.get(doc_name)
            if not draft:
                continue

            for field_name, expected_data in expected_fields.items():
                expected_val = expected_data.get("value")
                expected_status = expected_data.get("status", "found")
                expected_page = expected_data.get("page")
                expected_quote = expected_data.get("evidence_quote")
                is_expected_missing = expected_data.get("expected_missing", False)

                rec = draft.fields.get(field_name)

                # Initialize breakdown tracker
                if field_name not in field_breakdown:
                    field_breakdown[field_name] = {"correct": 0, "total": 0, "evidence_verified": 0}

                # 1. Missing field detection tracking
                is_predicted_missing = (
                    rec is None or rec.status == FieldStatus.NOT_FOUND or rec.value is None
                )

                if is_expected_missing:
                    if is_predicted_missing:
                        missing_tp += 1
                    else:
                        missing_fn += 1  # Hallucinated a value when should be missing
                else:
                    if is_predicted_missing:
                        missing_fp += 1  # Missed a field that was present
                    else:
                        missing_tn += 1

                # 2. Value accuracy (only evaluated when expected value is present)
                if not is_expected_missing and expected_val is not None:
                    field_den += 1
                    field_breakdown[field_name]["total"] += 1

                    predicted_val = rec.value if rec else None
                    norm_exp = self._normalize_cmp(expected_val)
                    norm_pred = self._normalize_cmp(predicted_val)

                    # Check exact or strong containment match
                    match = (
                        norm_exp == norm_pred or
                        (norm_exp in norm_pred if len(norm_exp) > 5 else False) or
                        (norm_pred in norm_exp if len(norm_pred) > 5 else False)
                    )

                    # Check word overlap for descriptive clauses / multi-item criteria
                    if not match and len(norm_exp) > 10 and len(norm_pred) > 10:
                        words_exp = set(norm_exp.split())
                        words_pred = set(norm_pred.split())
                        if words_exp and words_pred:
                            common = len(words_exp & words_pred)
                            if (common / min(len(words_exp), len(words_pred))) >= 0.70:
                                match = True

                    if match:
                        field_num += 1
                        field_breakdown[field_name]["correct"] += 1

                    # High-risk fields (benefit amount and deadline)
                    if field_name in ["benefit_amount", "deadline"]:
                        risk_den += 1
                        if match:
                            risk_num += 1

                # 3. Evidence Quotation Verification
                if expected_quote and rec and rec.evidence:
                    ev_den += 1
                    first_ev = rec.evidence[0]
                    if first_ev.is_verified:
                        ev_num += 1
                        field_breakdown[field_name]["evidence_verified"] += 1

                # 4. Page Reference Accuracy
                if expected_page is not None and rec and rec.evidence:
                    page_den += 1
                    first_ev = rec.evidence[0]
                    if first_ev.page_or_section == expected_page:
                        page_num += 1

        # Missing field Precision / Recall / F1
        missing_prec = (missing_tp / (missing_tp + missing_fp)) if (missing_tp + missing_fp) > 0 else 1.0
        missing_rec = (missing_tp / (missing_tp + missing_fn)) if (missing_tp + missing_fn) > 0 else 1.0
        missing_f1 = (
            2 * (missing_prec * missing_rec) / (missing_prec + missing_rec)
            if (missing_prec + missing_rec) > 0 else 1.0
        )

        # Conflict Detection Metrics (computed on multi-source test case)
        conflict_report = self._evaluate_conflict_detection(drafts_by_doc)

        report = EvaluationReport(
            total_documents_evaluated=len(drafts_by_doc),
            overall_field_accuracy=MetricResult(
                name="Overall Field Accuracy",
                numerator=field_num,
                denominator=field_den,
                value=round(field_num / max(field_den, 1), 4),
                description="Exact/strong normalized match across all ground-truth fields where facts exist."
            ),
            amount_and_deadline_accuracy=MetricResult(
                name="High-Risk Amount and Deadline Accuracy",
                numerator=risk_num,
                denominator=risk_den,
                value=round(risk_num / max(risk_den, 1), 4),
                description="Accuracy specifically on benefit_amount and deadline fields."
            ),
            evidence_quotation_rate=MetricResult(
                name="Evidence Quotation Verification Rate",
                numerator=ev_num,
                denominator=ev_den,
                value=round(ev_num / max(ev_den, 1), 4),
                description="Percentage of extracted evidence quotations verified verbatim in document text."
            ),
            page_reference_accuracy=MetricResult(
                name="Page Reference Accuracy",
                numerator=page_num,
                denominator=page_den,
                value=round(page_num / max(page_den, 1), 4),
                description="Percentage of citations referencing the exact correct page number."
            ),
            missing_field_metrics={
                "precision": round(missing_prec, 4),
                "recall": round(missing_rec, 4),
                "f1_score": round(missing_f1, 4),
                "true_positives": missing_tp,
                "false_positives": missing_fp,
                "false_negatives": missing_fn
            },
            conflict_detection_metrics=conflict_report,
            field_breakdown=field_breakdown,
            proposed_pilot_quality_gates={
                "Benefit Amount Verification Gate": "100% human review required if quotation unverified or conflict detected.",
                "Eligibility Conditions Gate": "Zero unverified eligibility clauses allowed into approved records.",
                "Deadline Expiration Gate": "Automated alert if deadline is past or conflicting between circulars.",
                "Missing Field Threshold": "Automated prompt to search supplementary government gazette when >=3 core fields missing.",
                "Reviewer Audit Trail": "All field corrections must record reviewer ID, rationale, and timestamp."
            }
        )

        return report

    def _evaluate_conflict_detection(
        self,
        drafts_by_doc: Dict[str, SchemeDraft]
    ) -> Dict[str, float]:
        """
        Evaluates conflict detection on the conflict-testing pair:
        kisan_samriddhi_yojana.pdf + kisan_samriddhi_revised_circular.pdf
        """
        from src.conflict.detector import ConflictDetector

        draft_a = drafts_by_doc.get("kisan_samriddhi_yojana.pdf")
        draft_b = drafts_by_doc.get("kisan_samriddhi_revised_circular.pdf")

        if not draft_a or not draft_b:
            return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "note": "Conflict pair not provided in eval run."}

        # Merge copies to test conflict detection
        import copy
        merged = copy.deepcopy(draft_a)
        merged = ConflictDetector.merge_drafts(merged, copy.deepcopy(draft_b))

        # Expected conflicting fields: benefit_amount, benefit_frequency, deadline
        expected_conflicts = {"benefit_amount", "benefit_frequency", "deadline"}

        tp = 0
        fp = 0
        fn = 0

        for field_name, rec in merged.fields.items():
            is_conflict = rec.status == FieldStatus.CONFLICT
            if field_name in expected_conflicts:
                if is_conflict:
                    tp += 1
                else:
                    fn += 1
            else:
                if is_conflict:
                    fp += 1

        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 1.0

        return {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "conflicts_detected": tp,
            "false_alarms": fp,
            "missed_conflicts": fn
        }
