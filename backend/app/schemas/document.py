"""Pydantic schemas for API request/response models."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# File Validation
# ---------------------------------------------------------------------------
class FileValidation(BaseModel):
    file_type: str
    is_supported: bool
    is_readable: bool
    page_count: int
    status: str  # PASS | FAIL


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class ValidationCheck(BaseModel):
    name: str
    formula: str
    operands: dict[str, Any]
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: str  # PASS | FAIL | NOT_APPLICABLE


class ValidationResult(BaseModel):
    checks: list[ValidationCheck] = Field(default_factory=list)
    overall_status: str = "PASS"
    issues: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Processing Metadata
# ---------------------------------------------------------------------------
class ProcessingMetadata(BaseModel):
    ocr_used: bool = False
    processed_at: str
    processing_time_ms: int


# ---------------------------------------------------------------------------
# Full Document Response
# ---------------------------------------------------------------------------
class DocumentResponse(BaseModel):
    document_name: str
    document_type: str
    processing_status: str  # PASS | FAILED
    overall_confidence: Optional[float] = None
    file_validation: FileValidation
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationResult = Field(default_factory=ValidationResult)
    processing_metadata: ProcessingMetadata

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# List Item (for dashboard)
# ---------------------------------------------------------------------------
class DocumentListItem(BaseModel):
    document_name: str
    document_type: str
    processing_status: str
    overall_confidence: Optional[float] = None
    processed_at: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
