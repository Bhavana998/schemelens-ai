"""
PDF and Scanned Document Processing Engine.
Extracts page-by-page text with PyMuPDF, detects scanned/image pages,
and falls back to Tesseract OCR with explicit language capability checks.
"""

import io
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
import pymupdf as fitz
import pytesseract

from src.models.schemas import DocumentContent, ExtractedPage


class DocumentProcessor:
    """
    Handles PDF text extraction and OCR fallback with language validation.
    """

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        tessdata_prefix: Optional[str] = None,
        min_char_threshold: int = 30
    ):
        self.min_char_threshold = min_char_threshold

        # Configure Tesseract binary path
        configured_cmd = tesseract_cmd or os.getenv("TESSERACT_CMD")
        if configured_cmd and os.path.exists(configured_cmd):
            pytesseract.pytesseract.tesseract_cmd = configured_cmd
        elif os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        # Configure TESSDATA_PREFIX if provided
        configured_prefix = tessdata_prefix or os.getenv("TESSDATA_PREFIX")
        if configured_prefix and os.path.exists(configured_prefix):
            os.environ["TESSDATA_PREFIX"] = configured_prefix

    def is_tesseract_available(self) -> bool:
        """Checks if Tesseract executable is installed and runnable."""
        cmd = pytesseract.pytesseract.tesseract_cmd
        if cmd and os.path.exists(cmd):
            return True
        return shutil.which("tesseract") is not None

    def get_installed_ocr_languages(self) -> List[str]:
        """Returns list of installed Tesseract language codes."""
        if not self.is_tesseract_available():
            return []
        try:
            return pytesseract.get_languages()
        except Exception:
            return ["eng"]

    def extract_document(
        self,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        preferred_lang: str = "eng"
    ) -> DocumentContent:
        """
        Extracts page-by-page text from PDF or raw image.
        Uses OCR when text is absent or below threshold.
        """
        ext = Path(filename).suffix.lower()
        pages: List[ExtractedPage] = []
        ocr_applied = False
        ocr_warning: Optional[str] = None
        import time
        t_start = time.time()

        if ext == ".pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)

            for page_idx in range(total_pages):
                page_num = page_idx + 1
                page = doc[page_idx]

                # 1. First attempt: Direct digital text extraction
                page_text = page.get_text("text").strip()

                if len(page_text) >= self.min_char_threshold:
                    pages.append(
                        ExtractedPage(
                            page_number=page_num,
                            text=page_text,
                            extraction_method="pdf_text",
                            is_scanned=False
                        )
                    )
                else:
                    # 2. Text absent or minimal: Scanned page fallback
                    scanned_text, method, warning = self._ocr_page(page, preferred_lang)
                    ocr_applied = True
                    if warning and not ocr_warning:
                        ocr_warning = warning

                    pages.append(
                        ExtractedPage(
                            page_number=page_num,
                            text=scanned_text,
                            extraction_method=method,
                            is_scanned=True
                        )
                    )

            doc.close()

        elif ext in {".png", ".jpg", ".jpeg"}:
            total_pages = 1
            image = Image.open(io.BytesIO(file_bytes))
            scanned_text, method, warning = self._ocr_image(image, preferred_lang)
            ocr_applied = True
            ocr_warning = warning
            pages.append(
                ExtractedPage(
                    page_number=1,
                    text=scanned_text,
                    extraction_method=method,
                    is_scanned=True
                )
            )
        else:
            raise ValueError(f"Unsupported format for extraction: {ext}")

        full_text = "\n\n--- Page Break ---\n\n".join(
            f"[Page {p.page_number}]\n{p.text}" for p in pages
        )

        proc_duration = round(time.time() - t_start, 4)

        import hashlib
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        return DocumentContent(
            document_id=document_id,
            filename=filename,
            file_hash=file_hash,
            total_pages=total_pages,
            pages=pages,
            raw_full_text=full_text,
            ocr_applied=ocr_applied,
            ocr_warning=ocr_warning,
            metadata={
                "preferred_lang": preferred_lang,
                "installed_ocr_langs": self.get_installed_ocr_languages(),
                "processing_duration_sec": proc_duration,
                "ocr_duration_sec": proc_duration if ocr_applied else 0.0
            }
        )

    def _ocr_page(
        self,
        page: fitz.Page,
        preferred_lang: str
    ) -> Tuple[str, str, Optional[str]]:
        """Renders a PDF page to high-res image and runs OCR."""
        # Render page at 200 DPI for reliable OCR
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return self._ocr_image(img, preferred_lang)

    def _ocr_image(
        self,
        img: Image.Image,
        preferred_lang: str
    ) -> Tuple[str, str, Optional[str]]:
        """Runs Tesseract OCR on a PIL image with language validation."""
        if not self.is_tesseract_available():
            msg = (
                "Tesseract OCR is not installed or not found on PATH. "
                "Scanned content cannot be processed."
            )
            return "", "ocr_unavailable", msg

        installed_langs = self.get_installed_ocr_languages()

        # Check requested language availability
        ocr_lang = "eng"
        warning = None

        if preferred_lang in ["hin", "hindi"]:
            if "hin" in installed_langs:
                ocr_lang = "hin+eng"
            else:
                warning = (
                    "Hindi language data ('hin.traineddata') is not installed in Tesseract. "
                    "Setup instruction: Download 'hin.traineddata' from "
                    "https://github.com/tesseract-ocr/tessdata and place it in your Tesseract "
                    "tessdata directory (e.g., C:\\Program Files\\Tesseract-OCR\\tessdata). "
                    "Falling back to English OCR."
                )
                ocr_lang = "eng"
        elif preferred_lang in installed_langs:
            ocr_lang = preferred_lang

        try:
            text = pytesseract.image_to_string(img, lang=ocr_lang).strip()
            return text, "ocr", warning
        except Exception as e:
            err_msg = f"OCR processing failed: {str(e)}"
            return "", "ocr_error", err_msg
