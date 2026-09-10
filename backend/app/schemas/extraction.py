"""Extraction-related schema helpers.

The extracted_data payload is intentionally a flexible dict because different
document types return different field sets.  These helpers provide lightweight
structures used inside the extraction and validation services.
"""

from typing import Any, Optional
from pydantic import BaseModel


class ExtractedField(BaseModel):
    """A single extracted field with optional confidence and evidence."""
    value: Any
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None


class LineItem(BaseModel):
    """A single line item from an invoice."""
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    vat_percent: Optional[float] = None
    gross_amount: Optional[float] = None


class FinancialLineItem(BaseModel):
    """A line item from a financial statement."""
    name: str
    value: Optional[float] = None
    page_number: Optional[int] = None
