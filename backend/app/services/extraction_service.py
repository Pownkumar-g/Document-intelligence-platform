"""AI-based field and table extraction using Google Gemini.

Sends document images (and any extracted text) to Gemini 2.0 Flash with
per-document-type prompts.  Returns structured JSON with field values,
confidence scores, page numbers and source-text evidence.
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from app.core.config import settings
from app.services.ocr_service import OCRResult

logger = logging.getLogger("docextract")


class ExtractionService:
    """Orchestrates AI extraction via the Gemini multimodal API."""

    def __init__(self):
        self._client = None
        if settings.GEMINI_API_KEY:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Gemini extraction client initialised")
        else:
            logger.warning("GEMINI_API_KEY not set – extraction will fail")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract(self, ocr_result: OCRResult, document_type: str) -> dict[str, Any]:
        """Extract structured data from a document.

        Returns a dict suitable for the ``extracted_data`` response field.
        """
        if self._client is None:
            raise RuntimeError("Gemini API key is not configured")

        prompt = self._build_prompt(document_type)

        # Assemble content parts: images + supplementary text + prompt
        parts: list[Any] = []
        for img in ocr_result.images:
            parts.append(img)

        # Append any natively-extracted text as supplementary context
        supplementary = self._supplementary_text(ocr_result)
        if supplementary:
            parts.append(supplementary)

        parts.append(prompt)

        try:
            response = self._client.models.generate_content(
                model="gemini-3.6-flash",
                contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw = response.text
            result = json.loads(raw)
            logger.info("Extraction succeeded for document_type=%s", document_type)
            return result
        except json.JSONDecodeError as exc:
            logger.error("Gemini returned invalid JSON: %s", exc)
            raise RuntimeError(f"AI extraction returned invalid JSON: {exc}") from exc
        except Exception as exc:
            logger.error("Extraction failed: %s", exc)
            raise RuntimeError(f"AI extraction failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------
    def _build_prompt(self, document_type: str) -> str:
        builders = {
            "invoice": self._invoice_prompt,
            "balance_sheet": self._balance_sheet_prompt,
            "profit_and_loss": self._profit_and_loss_prompt,
            "cash_flow_statement": self._cash_flow_prompt,
        }
        builder = builders.get(document_type, self._invoice_prompt)
        return builder()

    # ---- Invoice ----
    @staticmethod
    def _invoice_prompt() -> str:
        return """You are an expert document-extraction AI.  Analyze the provided invoice / receipt image(s) and extract ALL visible information.

Return a single JSON object with the following structure.  Use null for any field that is not present.  Do NOT invent or guess values.
Monetary values must be plain numbers (no currency symbols).  Confidence scores should reflect readability (1.0 = crystal clear).

{
  "invoice_number": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "invoice_date": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "vendor_name": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "vendor_address": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "vendor_tax_id": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "customer_name": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "customer_address": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "customer_tax_id": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "currency": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "subtotal": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "tax_rate": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "tax_amount": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "discount": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "total_amount": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "rounding_adjustment": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "cash_paid": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "change": {"value": 0.0, "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "payment_method": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "line_items": [
    {
      "description": "...",
      "quantity": 0.0,
      "unit": "...",
      "unit_price": 0.0,
      "amount": 0.0,
      "discount": 0.0,
      "vat_percent": 0.0,
      "gross_amount": 0.0,
      "page_number": 1
    }
  ],
  "additional_fields": {}
}

IMPORTANT RULES:
- Extract EVERY visible field, not just the ones listed above.  Put any extra fields in additional_fields.
- For receipts that show "Total Includes GST", the total_amount IS the GST-inclusive total.
- If tax is already included in the displayed total, set tax_amount to the separate tax value if shown, or null.
- Dates should be in the format shown in the document (do not reformat).
- source_text must be the exact text snippet from the document that contains the value.
"""

    # ---- Balance Sheet ----
    @staticmethod
    def _balance_sheet_prompt() -> str:
        return """You are an expert financial-document extraction AI.  Analyze the provided Balance Sheet image(s) and extract ALL visible information.

Return a single JSON object.  Use null for missing values.  Do NOT invent values.
Monetary values must be plain numbers.  Parenthesized values like (1,234.56) are NEGATIVE.

{
  "company_name": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "report_title": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "as_of_date": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "currency": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "unit": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "auditor_notes": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "periods": [
    {
      "period_label": "As at 31.03.2024",
      "capital_and_liabilities": {
        "items": [
          {"name": "Capital", "value": 0.0, "schedule_ref": "...", "page_number": 1}
        ],
        "total": {"value": 0.0, "page_number": 1}
      },
      "assets": {
        "items": [
          {"name": "Cash and Balances with Reserve Bank of India", "value": 0.0, "schedule_ref": "...", "page_number": 1}
        ],
        "total": {"value": 0.0, "page_number": 1}
      }
    }
  ]
}

IMPORTANT:
- Extract EVERY line item visible in the document, not just examples above.
- If the document shows two or more comparative periods/years, create a separate object in the periods array for each.
- Preserve the exact item names as shown in the document.
- Schedule references (e.g., "Schedule 1") should be captured if present.
- Parenthesized numbers are negative.
"""

    # ---- Profit & Loss ----
    @staticmethod
    def _profit_and_loss_prompt() -> str:
        return """You are an expert financial-document extraction AI.  Analyze the provided Profit & Loss / Income Statement image(s) and extract ALL visible information.

Return a single JSON object.  Use null for missing values.  Do NOT invent values.
Parenthesized values like (1,234.56) are NEGATIVE.

{
  "company_name": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "report_title": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "period": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "currency": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "unit": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "periods": [
    {
      "period_label": "Year ended 31.03.2024",
      "income": {
        "items": [
          {"name": "Interest Earned", "value": 0.0, "schedule_ref": "...", "page_number": 1}
        ],
        "total_income": {"value": 0.0, "page_number": 1}
      },
      "expenditure": {
        "items": [
          {"name": "Interest Expended", "value": 0.0, "schedule_ref": "...", "page_number": 1}
        ],
        "total_expenditure": {"value": 0.0, "page_number": 1}
      },
      "profit_calculations": {
        "net_profit_for_the_year": {"value": 0.0, "page_number": 1},
        "consolidated_net_profit_before_mi": {"value": 0.0, "page_number": 1},
        "minority_interest": {"value": 0.0, "page_number": 1},
        "consolidated_net_profit_group": {"value": 0.0, "page_number": 1},
        "brought_forward_profit": {"value": 0.0, "page_number": 1},
        "total_available_for_appropriation": {"value": 0.0, "page_number": 1}
      },
      "appropriations": {
        "items": [
          {"name": "Transfer to Statutory Reserve", "value": 0.0, "page_number": 1}
        ],
        "balance_carried_forward": {"value": 0.0, "page_number": 1}
      }
    }
  ]
}

IMPORTANT:
- Extract EVERY line item visible in the document.
- If the document shows two or more comparative periods/years, create a separate object in the periods array for each.
- Preserve the exact item names as shown in the document.
- Parenthesized numbers are negative.
- Capture ALL profit computation steps shown (gross profit, operating profit, PBT, PAT, etc.).
"""

    # ---- Cash Flow Statement ----
    @staticmethod
    def _cash_flow_prompt() -> str:
        return """You are an expert financial-document extraction AI.  Analyze the provided Cash Flow Statement image(s) and extract ALL visible information.

Return a single JSON object.  Use null for missing values.  Do NOT invent values.
Parenthesized / bracketed values like (1,234.56) are NEGATIVE.

{
  "company_name": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "report_title": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "period": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "currency": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "unit": {"value": "...", "confidence": 0.0, "page_number": 1, "source_text": "..."},
  "periods": [
    {
      "period_label": "Year ended 31.03.2024",
      "operating_activities": {
        "items": [
          {"name": "Net Profit before tax", "value": 0.0, "page_number": 1}
        ],
        "net_cash_flow": {"value": 0.0, "page_number": 1}
      },
      "investing_activities": {
        "items": [
          {"name": "Purchase of fixed assets", "value": 0.0, "page_number": 1}
        ],
        "net_cash_flow": {"value": 0.0, "page_number": 1}
      },
      "financing_activities": {
        "items": [
          {"name": "Dividends paid", "value": 0.0, "page_number": 1}
        ],
        "net_cash_flow": {"value": 0.0, "page_number": 1}
      },
      "fx_translation_adjustment": {"value": 0.0, "page_number": 1},
      "net_increase_in_cash": {"value": 0.0, "page_number": 1},
      "opening_cash": {"value": 0.0, "page_number": 1},
      "cash_acquired_on_amalgamation": {"value": 0.0, "page_number": 1},
      "closing_cash": {"value": 0.0, "page_number": 1}
    }
  ]
}

IMPORTANT:
- Extract EVERY line item visible in the document.
- If the document shows two or more comparative periods/years, create a separate object in the periods array for each.
- Preserve the exact item names as shown in the document.
- Parenthesized / bracketed numbers are NEGATIVE.  Convert them: (5,000) → -5000.
- Capture opening cash, closing cash, net increase/decrease and any reconciliation adjustments.
"""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _supplementary_text(ocr_result: OCRResult) -> str | None:
        parts: list[str] = []
        for page_num, text in ocr_result.text_by_page.items():
            stripped = text.strip()
            if stripped:
                parts.append(f"--- Page {page_num} Extracted Text ---\n{stripped}")
        if not parts:
            return None
        return "\nSupplementary text extracted from the document:\n" + "\n\n".join(parts)
