"""REST API routes for document processing, retrieval, and health check."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService, VALID_DOCUMENT_TYPES

logger = logging.getLogger("docextract")

router = APIRouter()
document_service = DocumentService()
repo = DocumentRepository()

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


# ======================================================================
# Health
# ======================================================================
@router.get("/health", tags=["Health"])
async def health_check():
    """Health-check endpoint."""
    return {"status": "healthy", "service": "Document Intelligence Platform"}


# ======================================================================
# POST – process document
# ======================================================================
@router.post("/documents/process", tags=["Documents"])
async def process_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload and process a PDF / JPG / PNG document.

    - **file**: The document file (PDF, JPG, or PNG).
    - **document_type**: One of ``invoice``, ``balance_sheet``, ``profit_and_loss``, ``cash_flow_statement``.
    """
    # --- validate document_type ---
    if document_type not in VALID_DOCUMENT_TYPES:
        logger.warning("Invalid document_type: %s", document_type)
        return _error_response(
            422,
            "INVALID_DOCUMENT_TYPE",
            f"document_type must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}",
        )

    # --- validate file extension ---
    filename = file.filename or "unknown"
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        logger.warning("Unsupported file type: %s", filename)
        return _error_response(
            400,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF / JPG / PNG documents are supported.",
        )

    # --- read file bytes ---
    try:
        file_bytes = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file: %s", exc)
        return _error_response(400, "FILE_READ_ERROR", "Could not read the uploaded file.")

    if not file_bytes:
        return _error_response(400, "EMPTY_FILE", "The uploaded file is empty.")

    # --- process ---
    try:
        result = document_service.process(
            file_bytes=file_bytes,
            filename=filename,
            document_type=document_type,
            content_type=file.content_type,
        )
    except Exception as exc:
        logger.error("Unexpected processing error: %s", exc)
        return _error_response(500, "PROCESSING_ERROR", "An unexpected error occurred during processing.")

    # --- persist ---
    try:
        repo.save_result(db, result)
    except Exception as exc:
        logger.error("Database save failed: %s", exc)
        # Still return the result even if persistence fails
        result["_warning"] = "Result could not be saved to database"

    return result


# ======================================================================
# GET – retrieve by document name
# ======================================================================
@router.get("/documents/{document_name}", tags=["Documents"])
async def get_document(document_name: str, db: Session = Depends(get_db)):
    """Retrieve the latest structured result for a document by file name."""
    result = repo.get_by_name(db, document_name)
    if result is None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "DOCUMENT_NOT_FOUND", "message": f"No processed result found for '{document_name}'."}
        })
    return result


# ======================================================================
# GET – list all processed documents
# ======================================================================
@router.get("/documents", tags=["Documents"])
async def list_documents(db: Session = Depends(get_db)):
    """List all processed documents for the dashboard."""
    return repo.list_all(db)


# ======================================================================
# Helpers
# ======================================================================
def _error_response(status_code: int, code: str, message: str):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _extension(filename: str) -> str:
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""
