"""Document validation service – file type, integrity, page-count checks."""

import io
import logging
from typing import Any

from PIL import Image
import fitz  # PyMuPDF

from app.core.config import settings

logger = logging.getLogger("docextract")

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

EXTENSION_TO_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class DocumentValidationService:
    """Validates uploaded files before OCR / extraction."""

    def __init__(self, max_pages: int | None = None):
        self.max_pages = max_pages or settings.MAX_PAGES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def validate(self, file_bytes: bytes, filename: str, content_type: str | None = None) -> dict[str, Any]:
        """Return a file-validation dict conforming to the spec."""
        result: dict[str, Any] = {
            "file_type": content_type or "unknown",
            "is_supported": False,
            "is_readable": False,
            "page_count": 0,
            "status": "FAIL",
        }

        # --- empty file ---
        if not file_bytes or len(file_bytes) == 0:
            logger.warning("Validation failed: empty file '%s'", filename)
            return result

        # --- extension check ---
        ext = self._extension(filename)
        if ext not in SUPPORTED_EXTENSIONS:
            logger.warning("Validation failed: unsupported extension '%s' for '%s'", ext, filename)
            return result

        result["file_type"] = EXTENSION_TO_MIME.get(ext, content_type or "unknown")
        result["is_supported"] = True

        # --- type-specific validation ---
        if ext == ".pdf":
            return self._validate_pdf(file_bytes, filename, result)
        return self._validate_image(file_bytes, filename, result)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extension(filename: str) -> str:
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()
        return ""

    def _validate_pdf(self, file_bytes: bytes, filename: str, result: dict) -> dict:
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            logger.error("Cannot open PDF '%s': %s", filename, exc)
            result["is_readable"] = False
            return result

        page_count = len(doc)
        result["page_count"] = page_count
        result["is_readable"] = True

        if page_count == 0:
            logger.warning("PDF '%s' has 0 pages", filename)
            result["is_readable"] = False
            doc.close()
            return result

        if page_count > self.max_pages:
            logger.warning(
                "PDF '%s' exceeds page limit (%d > %d)", filename, page_count, self.max_pages
            )
            result["status"] = "FAIL"
            doc.close()
            return result

        doc.close()
        result["status"] = "PASS"
        logger.info("PDF '%s' passed validation (%d pages)", filename, page_count)
        return result

    def _validate_image(self, file_bytes: bytes, filename: str, result: dict) -> dict:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # raises on corrupt data
        except Exception as exc:
            logger.error("Cannot read image '%s': %s", filename, exc)
            result["is_readable"] = False
            return result

        result["is_readable"] = True
        result["page_count"] = 1
        result["status"] = "PASS"
        logger.info("Image '%s' passed validation", filename)
        return result
