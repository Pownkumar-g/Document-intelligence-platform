"""Document orchestrator service.

Coordinates the full processing pipeline:
  1. File validation
  2. OCR / text extraction
  3. AI-based field & table extraction
  4. Financial validation
  5. Persist to database
  6. Return structured response
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.services.document_validation_service import DocumentValidationService
from app.services.ocr_service import OCRService
from app.services.extraction_service import ExtractionService
from app.services.financial_validation_service import FinancialValidationService

logger = logging.getLogger("docextract")

VALID_DOCUMENT_TYPES = {"invoice", "balance_sheet", "profit_and_loss", "cash_flow_statement"}


class DocumentService:
    """High-level service that orchestrates the complete document pipeline."""

    def __init__(self):
        self.validation_svc = DocumentValidationService()
        self.ocr_svc = OCRService()
        self.extraction_svc = ExtractionService()
        self.financial_svc = FinancialValidationService()

    def process(
        self, file_bytes: bytes, filename: str, document_type: str, content_type: str | None = None
    ) -> dict[str, Any]:
        """Process a document through the full pipeline and return the structured response."""
        start_time = time.time()
        logger.info("Processing document '%s' (type=%s)", filename, document_type)

        # --- Step 1: File validation ---
        file_validation = self.validation_svc.validate(file_bytes, filename, content_type)

        if file_validation["status"] != "PASS":
            elapsed = int((time.time() - start_time) * 1000)
            logger.warning("File validation failed for '%s'", filename)
            return self._build_response(
                document_name=filename,
                document_type=document_type,
                processing_status="FAILED",
                file_validation=file_validation,
                extracted_data={},
                validation={"checks": [], "overall_status": "FAIL", "issues": ["File validation failed"]},
                ocr_used=False,
                elapsed_ms=elapsed,
            )

        # --- Step 2: OCR / text + image extraction ---
        try:
            ocr_result = self.ocr_svc.extract(file_bytes, filename)
        except Exception as exc:
            elapsed = int((time.time() - start_time) * 1000)
            logger.error("OCR failed for '%s': %s", filename, exc)
            return self._build_response(
                document_name=filename,
                document_type=document_type,
                processing_status="FAILED",
                file_validation=file_validation,
                extracted_data={},
                validation={"checks": [], "overall_status": "FAIL", "issues": [f"OCR failed: {exc}"]},
                ocr_used=False,
                elapsed_ms=elapsed,
            )

        # --- Step 3: AI extraction ---
        try:
            extracted_data = self.extraction_svc.extract(ocr_result, document_type)
        except Exception as exc:
            elapsed = int((time.time() - start_time) * 1000)
            logger.error("Extraction failed for '%s': %s", filename, exc)
            return self._build_response(
                document_name=filename,
                document_type=document_type,
                processing_status="FAILED",
                file_validation=file_validation,
                extracted_data={},
                validation={"checks": [], "overall_status": "FAIL", "issues": [f"Extraction failed: {exc}"]},
                ocr_used=ocr_result.is_scanned,
                elapsed_ms=int((time.time() - start_time) * 1000),
            )

        # --- Step 4: Financial validation ---
        validation_result = self.financial_svc.validate(extracted_data, document_type)

        # --- Step 5: Compute overall confidence ---
        overall_confidence = self._compute_confidence(extracted_data)

        # --- Step 6: Determine processing status ---
        processing_status = "PASS"
        if validation_result.get("overall_status") == "FAIL":
            # Still PASS for processing, the validation section shows the failures
            processing_status = "PASS"

        elapsed = int((time.time() - start_time) * 1000)
        logger.info(
            "Document '%s' processed in %dms (status=%s)", filename, elapsed, processing_status
        )

        return self._build_response(
            document_name=filename,
            document_type=document_type,
            processing_status=processing_status,
            file_validation=file_validation,
            extracted_data=extracted_data,
            validation=validation_result,
            ocr_used=ocr_result.is_scanned,
            elapsed_ms=elapsed,
            overall_confidence=overall_confidence,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_response(
        document_name: str,
        document_type: str,
        processing_status: str,
        file_validation: dict,
        extracted_data: dict,
        validation: dict,
        ocr_used: bool,
        elapsed_ms: int,
        overall_confidence: float | None = None,
    ) -> dict[str, Any]:
        return {
            "document_name": document_name,
            "document_type": document_type,
            "processing_status": processing_status,
            "overall_confidence": overall_confidence,
            "file_validation": file_validation,
            "extracted_data": extracted_data,
            "validation": validation,
            "processing_metadata": {
                "ocr_used": ocr_used,
                "processed_at": datetime.now(timezone.utc).isoformat() + "Z",
                "processing_time_ms": elapsed_ms,
            },
        }

    @staticmethod
    def _compute_confidence(extracted_data: dict) -> float | None:
        """Average the confidence scores found in extracted_data."""
        scores: list[float] = []
        for key, val in extracted_data.items():
            if isinstance(val, dict) and "confidence" in val:
                c = val["confidence"]
                if isinstance(c, (int, float)) and 0 <= c <= 1:
                    scores.append(float(c))
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)
