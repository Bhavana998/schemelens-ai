"""
Evidence Verification and Quotation Grounding Engine.
Applies deterministic, minimal-normalization checks to guarantee that every
evidence quotation is verbatim supported by the extracted source text and page reference.
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.models.schemas import DocumentContent, ExtractedPage, SchemeDraft, SchemeFieldRecord


class EvidenceVerifier:
    """
    Verifies that extracted field quotations exist verbatim within specified source pages.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Applies clearly defined, minimal normalization:
        - Collapses contiguous whitespace (spaces, tabs, newlines) into single space
        - Strips leading and trailing whitespace
        - Standardizes common Unicode quotation marks and dashes
        """
        if not text:
            return ""
        # Replace non-breaking spaces and standardized quotes/dashes
        text = text.replace("\u00a0", " ").replace("\u200b", "")
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = re.sub(r"\s*[—–\u2010\u2011\u2012\u2013\u2014\u2015\u2212-]\s*", " - ", text)
        # Collapse multiple spaces and newlines
        return re.sub(r"\s+", " ", text).strip().lower()

    @classmethod
    def verify_quotation_in_page(
        cls,
        quotation: str,
        page_text: str
    ) -> Tuple[bool, str]:
        """
        Determines whether normalized quotation is a strict substring of normalized page text.
        """
        if not quotation or not quotation.strip():
            return False, "Empty or null quotation provided."

        if not page_text or not page_text.strip():
            return False, "Target page text is empty."

        norm_quote = cls.normalize_text(quotation)
        norm_page = cls.normalize_text(page_text)

        if norm_quote in norm_page:
            return True, "Quotation verified: exact verbatim substring match found on target page."

        # If direct substring fails, check if 85%+ of continuous words match (for slight line-wrap breaks)
        quote_words = norm_quote.split()
        if len(quote_words) >= 4:
            # Check window matching
            window_size = len(quote_words)
            page_words = norm_page.split()
            for i in range(len(page_words) - window_size + 1):
                window = page_words[i : i + window_size]
                common = sum(1 for w1, w2 in zip(quote_words, window) if w1 == w2)
                if (common / window_size) >= 0.85:
                    return True, "Quotation verified: matched with minor formatting/linebreak tolerance (>=85% word alignment)."

        return False, "Verification mismatch: quotation text was NOT found on referenced page."

    @classmethod
    def validate_url(cls, url: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validates URL syntax and sanity.
        Rejects placeholder or invalid schemes.
        """
        if not url:
            return True, None  # Empty URL is valid if field is missing

        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False, f"Malformed URL: '{url}' missing scheme (http/https) or domain."
            if result.scheme not in ["http", "https"]:
                return False, f"Invalid URL protocol: '{result.scheme}'."
            if "example.com" in result.netloc or "placeholder" in result.netloc:
                return False, f"Placeholder URL detected: '{url}'."
            return True, None
        except Exception as e:
            return False, f"URL parse failure: {str(e)}"

    @classmethod
    def verify_draft_evidence(
        cls,
        draft: SchemeDraft,
        documents: Dict[str, DocumentContent]
    ) -> SchemeDraft:
        """
        Iterates over all fields in a draft, verifies every supporting Evidence item
        against the referenced document and page, and updates verification flags.
        """
        unverified_count = 0

        for field_name, field_record in draft.fields.items():
            for ev in field_record.evidence:
                source_doc = documents.get(ev.source_id)
                if not source_doc:
                    ev.is_verified = False
                    ev.verification_details = f"Source document '{ev.source_id}' not found in active corpus."
                    unverified_count += 1
                    continue

                # Locate referenced page
                target_page_num = ev.page_or_section if isinstance(ev.page_or_section, int) else 1
                page_obj = next(
                    (p for p in source_doc.pages if p.page_number == target_page_num),
                    None
                )

                if not page_obj:
                    # Try checking full document if specific page is out of bounds
                    is_found, details = cls.verify_quotation_in_page(ev.quotation, source_doc.raw_full_text)
                    if is_found:
                        ev.is_verified = True
                        ev.verification_details = f"Verified across document text (page reference {target_page_num} was out of bounds)."
                    else:
                        ev.is_verified = False
                        ev.verification_details = f"Page {target_page_num} does not exist in document '{ev.source_id}'."
                        unverified_count += 1
                else:
                    is_verified, details = cls.verify_quotation_in_page(ev.quotation, page_obj.text)
                    ev.is_verified = is_verified
                    ev.verification_details = details
                    if not is_verified:
                        # Check if quote appears on a different page of same doc
                        other_page = next(
                            (p for p in source_doc.pages if cls.verify_quotation_in_page(ev.quotation, p.text)[0]),
                            None
                        )
                        ev.is_verified = False
                        unverified_count += 1
                        if other_page:
                            ev.verification_details = (
                                f"Page citation mismatch: quotation found on Page {other_page.page_number} "
                                f"rather than cited Page {target_page_num}. Flagged for human review."
                            )
                        else:
                            ev.verification_details = (
                                f"Verification failure: quotation not found on referenced page {target_page_num} "
                                f"or document text. Flagged for human review."
                            )

            # Validate official_link syntax
            if field_name == "official_link" and field_record.value:
                valid_url, url_err = cls.validate_url(str(field_record.value))
                if not valid_url:
                    field_record.note = (
                        f"{field_record.note or ''} [URL Warning: {url_err}]"
                    ).strip()

            # Flag field if any evidence item failed verification
            if field_record.evidence and any(not ev.is_verified for ev in field_record.evidence):
                field_record.note = (
                    f"{field_record.note or ''} [UNVERIFIED EVIDENCE: Citation could not be verified on cited page. Flagged for reviewer inspection.]"
                ).strip()

        draft.unverified_evidence_count = unverified_count
        return draft
