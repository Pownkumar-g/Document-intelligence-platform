"""OCR / text extraction service.

Uses PyMuPDF for native PDF text and page-image rendering.
For image files, images are loaded directly with Pillow.
Gemini's multimodal vision serves as the primary OCR engine.
"""

import io
import logging
from dataclasses import dataclass, field

from PIL import Image
import fitz  # PyMuPDF

logger = logging.getLogger("docextract")


@dataclass
class OCRResult:
    """Container for extracted text and page images."""
    text_by_page: dict[int, str] = field(default_factory=dict)
    images: list[Image.Image] = field(default_factory=list)
    page_count: int = 0
    is_scanned: bool = False


class OCRService:
    """Extracts text and page images from uploaded documents."""

    def extract(self, file_bytes: bytes, filename: str) -> OCRResult:
        ext = self._extension(filename)
        if ext == ".pdf":
            return self._process_pdf(file_bytes, filename)
        if ext in {".jpg", ".jpeg", ".png"}:
            return self._process_image(file_bytes, filename)
        raise ValueError(f"Unsupported file type: {ext}")

    # ------------------------------------------------------------------
    # PDF processing
    # ------------------------------------------------------------------
    def _process_pdf(self, file_bytes: bytes, filename: str) -> OCRResult:
        result = OCRResult()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        result.page_count = len(doc)

        total_text_len = 0
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            result.text_by_page[page_num + 1] = text
            total_text_len += len(text.strip())

            # Render page as high-DPI image for Gemini
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            result.images.append(img)

        doc.close()

        # Heuristic: if very little text extracted, likely scanned
        result.is_scanned = total_text_len < 100
        logger.info(
            "PDF '%s': %d pages, %d chars extracted, scanned=%s",
            filename, result.page_count, total_text_len, result.is_scanned,
        )
        return result

    # ------------------------------------------------------------------
    # Image processing
    # ------------------------------------------------------------------
    def _process_image(self, file_bytes: bytes, filename: str) -> OCRResult:
        result = OCRResult()
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        result.images.append(img)
        result.page_count = 1
        result.is_scanned = True
        result.text_by_page[1] = ""
        logger.info("Image '%s': loaded (1 page, scanned)", filename)
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _extension(filename: str) -> str:
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()
        return ""
