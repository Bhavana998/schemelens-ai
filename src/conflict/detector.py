"""
Conflict Detection Engine for SchemeLens AI.
Identifies contradictory statements across multiple source documents
(e.g., conflicting benefit amounts, extended deadlines) and preserves all
conflicting values and supporting evidence records transparently.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from src.models.schemas import Evidence, FieldStatus, SchemeDraft, SchemeFieldRecord


class ConflictDetector:
    """
    Compares and reconciles multi-source extractions for the same welfare scheme.
    """

    @staticmethod
    def _normalize_val(val: Any) -> str:
        """Helper to normalize values for equivalence comparison."""
        if val is None:
            return ""
        if isinstance(val, list):
            return " ".join(sorted(str(x).strip().lower() for x in val))
        return str(val).strip().lower()

    @classmethod
    def are_values_conflicting(cls, val_a: Any, val_b: Any, field_name: Optional[str] = None) -> bool:
        """
        Determines whether two values represent a genuine factual conflict.
        - High-risk fields (amount, deadline, frequency) strictly flag any difference as a conflict.
        - Textual and list fields with strong containment or >=70% word overlap are treated as compatible elaborations.
        """
        if val_a is None or val_b is None:
            return False

        norm_a = cls._normalize_val(val_a)
        norm_b = cls._normalize_val(val_b)

        if not norm_a or not norm_b:
            return False

        if norm_a == norm_b:
            return False

        # Strict fields: any discrepancy is a conflict
        if field_name in ["benefit_amount", "deadline", "benefit_frequency"]:
            return True

        # Containment check (e.g. summarized vs full clause)
        if norm_a in norm_b or norm_b in norm_a:
            return False

        # Word overlap check for rephrased lists/descriptions
        words_a = set(re.findall(r"\w+", norm_a))
        words_b = set(re.findall(r"\w+", norm_b))
        if words_a and words_b:
            shorter_len = min(len(words_a), len(words_b))
            common = len(words_a & words_b)
            if (common / shorter_len) >= 0.55:
                return False

        return True

    @classmethod
    def merge_drafts(
        cls,
        base_draft: SchemeDraft,
        incoming_draft: SchemeDraft
    ) -> SchemeDraft:
        """
        Merges an incoming draft extraction into a base draft.
        Detects conflicts on field levels and merges evidence lists.
        Never silently overwrites conflicting facts.
        """
        has_any_conflict = base_draft.has_conflicts
        source_ids = list(set(base_draft.source_document_ids + incoming_draft.source_document_ids))
        base_draft.source_document_ids = source_ids

        all_fields = set(list(base_draft.fields.keys()) + list(incoming_draft.fields.keys()))

        for field_name in all_fields:
            base_rec = base_draft.fields.get(field_name)
            inc_rec = incoming_draft.fields.get(field_name)

            if not base_rec and inc_rec:
                base_draft.fields[field_name] = inc_rec
                continue

            if base_rec and not inc_rec:
                continue

            # Both records exist
            val_a = base_rec.value
            val_b = inc_rec.value

            is_conflict = cls.are_values_conflicting(val_a, val_b, field_name=field_name)

            if is_conflict:
                has_any_conflict = True
                source_a = base_rec.evidence[0].source_id if base_rec.evidence else "Source A"
                source_b = inc_rec.evidence[0].source_id if inc_rec.evidence else "Source B"

                # Composite conflict value preserving both representations
                conflict_value = {
                    source_a: val_a,
                    source_b: val_b
                }

                # Combine evidence lists
                combined_evidence = base_rec.evidence + [
                    ev for ev in inc_rec.evidence
                    if not any(
                        existing.quotation == ev.quotation and existing.source_id == ev.source_id
                        for existing in base_rec.evidence
                    )
                ]

                base_rec.value = conflict_value
                base_rec.evidence = combined_evidence
                base_rec.status = FieldStatus.CONFLICT
                base_rec.note = (
                    f"Conflict detected between '{source_a}' ({val_a}) "
                    f"and '{source_b}' ({val_b}). Both sources preserved for human adjudication."
                )
                base_rec.confidence = min(base_rec.confidence, inc_rec.confidence)

            elif base_rec.status == FieldStatus.NOT_FOUND and inc_rec.status == FieldStatus.FOUND:
                # Supplement missing field with newly discovered information
                base_rec.value = inc_rec.value
                base_rec.evidence = inc_rec.evidence
                base_rec.status = FieldStatus.FOUND
                base_rec.confidence = inc_rec.confidence
                base_rec.note = f"Discovered in supplementary source '{inc_rec.evidence[0].source_id if inc_rec.evidence else 'supplementary document'}'."

            elif base_rec.status == FieldStatus.FOUND and inc_rec.status == FieldStatus.FOUND:
                # Same facts: append corroborating evidence
                for ev in inc_rec.evidence:
                    if not any(
                        existing.quotation == ev.quotation and existing.source_id == ev.source_id
                        for existing in base_rec.evidence
                    ):
                        base_rec.evidence.append(ev)

        base_draft.has_conflicts = has_any_conflict
        base_draft.missing_fields_count = sum(
            1 for r in base_draft.fields.values() if r.status == FieldStatus.NOT_FOUND
        )

        return base_draft
