"""
Document Ingestion and Validation Module.
Validates file format, size limits, corruption checks, and computes cryptographic hashes.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pymupdf as fitz


class IngestionError(Exception):
    """Raised when document ingestion or validation fails."""
    pass


class DocumentValidator:
    """
    Validates uploaded documents against size, format, and integrity constraints.
    """
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

    @classmethod
    def calculate_sha256(cls, file_bytes: bytes) -> str:
        """Computes deterministic SHA-256 hash for evidence lineage."""
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    def validate_file(
        cls,
        filename: str,
        file_bytes: bytes
    ) -> Tuple[bool, Optional[str], Dict[str, any]]:
        """
        Validates file attributes, structure, and integrity.
        Returns:
            (is_valid, error_message, metadata_dict)
        """
        # 1. Check empty file
        if not file_bytes or len(file_bytes) == 0:
            return False, "Uploaded file is empty (0 bytes).", {}

        # 2. Check size limits
        size_bytes = len(file_bytes)
        if size_bytes > cls.MAX_FILE_SIZE_BYTES:
            return False, f"File exceeds maximum allowed size of {cls.MAX_FILE_SIZE_BYTES / (1024 * 1024)}MB.", {}

        # 3. Check extension
        ext = Path(filename).suffix.lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file extension '{ext}'. Allowed: {sorted(cls.ALLOWED_EXTENSIONS)}", {}

        sha256_hash = cls.calculate_sha256(file_bytes)
        metadata = {
            "filename": filename,
            "extension": ext,
            "size_bytes": size_bytes,
            "sha256": sha256_hash,
            "is_pdf": ext == ".pdf",
        }

        # 4. Deep PDF validation if PDF
        if ext == ".pdf":
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc)
                if total_pages == 0:
                    doc.close()
                    return False, "PDF contains no pages.", metadata
                metadata["total_pages"] = total_pages
                doc.close()
            except Exception as e:
                return False, f"Corrupted or invalid PDF file: {str(e)}", metadata

        return True, None, metadata
