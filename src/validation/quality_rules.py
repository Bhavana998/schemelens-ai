"""
Data Quality Rules Engine for SchemeLens AI.
Evaluates high-risk fields, logical coherence, and generates structured reviewer flags.
"""

from typing import Any, Dict, List
from pydantic import BaseModel
from src.models.schemas import FieldStatus, SchemeDraft


class QualityFlag(BaseModel):
    level: str  # "critical", "warning", "info"
    field: str
    message: str


class QualityRulesEngine:
    """
    Applies deterministic business and data validation checks on draft scheme records.
    """

    HIGH_RISK_FIELDS = {"benefit_amount", "deadline", "eligibility_conditions"}

    @classmethod
    def evaluate_draft(cls, draft: SchemeDraft) -> List[QualityFlag]:
        flags: List[QualityFlag] = []

        # 1. Scheme name check
        name_record = draft.fields.get("scheme_name")
        if not name_record or not name_record.value or name_record.status == FieldStatus.NOT_FOUND:
            flags.append(
                QualityFlag(
                    level="critical",
                    field="scheme_name",
                    message="Scheme name is missing or unidentified. Reviewer must supply a scheme title before approval."
                )
            )

        # 2. Benefit Amount and Type Coherence
        amount_record = draft.fields.get("benefit_amount")
        type_record = draft.fields.get("benefit_type")
        if amount_record and amount_record.value and (not type_record or not type_record.value):
            flags.append(
                QualityFlag(
                    level="warning",
                    field="benefit_type",
                    message="Benefit amount is specified, but benefit type (e.g. Cash Transfer, Subsidy) is undefined."
                )
            )

        # 3. Evidence Verification Checks across all fields
        for field_name, record in draft.fields.items():
            if record and record.status == FieldStatus.FOUND:
                if field_name in cls.HIGH_RISK_FIELDS and not record.evidence:
                    flags.append(
                        QualityFlag(
                            level="critical",
                            field=field_name,
                            message=f"High-risk field '{field_name}' has value '{record.value}' without any supporting evidence quotation."
                        )
                    )
                elif record.evidence:
                    unverified = [ev for ev in record.evidence if not ev.is_verified]
                    if unverified:
                        is_critical = field_name in cls.HIGH_RISK_FIELDS
                        flags.append(
                            QualityFlag(
                                level="critical" if is_critical else "warning",
                                field=field_name,
                                message=f"Evidence for {'high-risk ' if is_critical else ''}field '{field_name}' could not be verified verbatim on cited page. Flagged for human review."
                            )
                        )

        # 4. Conflict Flags
        for field_name, record in draft.fields.items():
            if record.status == FieldStatus.CONFLICT:
                flags.append(
                    QualityFlag(
                        level="critical",
                        field=field_name,
                        message=f"Conflicting values detected across sources for '{field_name}'. Human reviewer must resolve."
                    )
                )

        # 5. Missing Field Summaries
        missing_fields = [f for f, r in draft.fields.items() if r.status == FieldStatus.NOT_FOUND]
        if missing_fields:
            flags.append(
                QualityFlag(
                    level="info",
                    field="all",
                    message=f"{len(missing_fields)} standard fields are missing in source documentation: {', '.join(missing_fields)}."
                )
            )

        return flags
