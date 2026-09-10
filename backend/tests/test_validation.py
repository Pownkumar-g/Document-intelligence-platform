"""Tests for document validation and financial validation services."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.document_validation_service import DocumentValidationService
from app.services.financial_validation_service import FinancialValidationService


class TestDocumentValidation:
    def setup_method(self):
        self.svc = DocumentValidationService(max_pages=3)

    def test_empty_file_rejected(self):
        result = self.svc.validate(b"", "test.pdf", "application/pdf")
        assert result["status"] == "FAIL"
        assert result["is_supported"] == False

    def test_unsupported_extension(self):
        result = self.svc.validate(b"data", "test.docx", "application/docx")
        assert result["status"] == "FAIL"
        assert result["is_supported"] == False

    def test_valid_png_image(self):
        # Create a real valid 1x1 PNG using Pillow
        from PIL import Image
        import io
        img = Image.new("RGB", (1, 1), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        result = self.svc.validate(png_bytes, "test.png", "image/png")
        assert result["status"] == "PASS"
        assert result["is_supported"] == True
        assert result["is_readable"] == True
        assert result["page_count"] == 1

    def test_corrupted_pdf(self):
        result = self.svc.validate(b"not a pdf", "bad.pdf", "application/pdf")
        assert result["status"] == "FAIL"
        assert result["is_readable"] == False

    def test_jpg_extension_accepted(self):
        # We can't make a trivially valid JPEG here, but we verify extension logic
        result = self.svc.validate(b"\xff\xd8\xff", "photo.jpg", "image/jpeg")
        # It will fail on readability since it's not a complete JPEG
        assert result["is_supported"] == True


class TestFinancialValidation:
    def setup_method(self):
        self.svc = FinancialValidationService()

    def test_invoice_total_pass(self):
        data = {
            "subtotal": {"value": 100.00},
            "tax_amount": {"value": 10.00},
            "discount": {"value": 0.00},
            "total_amount": {"value": 110.00},
        }
        result = self.svc.validate(data, "invoice")
        total_check = [c for c in result["checks"] if c["name"] == "invoice_total_check"]
        assert len(total_check) == 1
        assert total_check[0]["status"] == "PASS"
        assert total_check[0]["variance"] == 0.0

    def test_invoice_total_fail(self):
        data = {
            "subtotal": {"value": 100.00},
            "tax_amount": {"value": 10.00},
            "discount": {"value": 0.00},
            "total_amount": {"value": 999.00},
        }
        result = self.svc.validate(data, "invoice")
        total_check = [c for c in result["checks"] if c["name"] == "invoice_total_check"]
        assert len(total_check) == 1
        assert total_check[0]["status"] == "FAIL"

    def test_invoice_line_item_validation(self):
        data = {
            "line_items": [
                {"description": "Item A", "quantity": 5, "unit_price": 10.0, "amount": 50.0},
                {"description": "Item B", "quantity": 3, "unit_price": 20.0, "amount": 60.0},
            ],
            "subtotal": {"value": 110.0},
            "total_amount": {"value": 110.0},
        }
        result = self.svc.validate(data, "invoice")
        line_checks = [c for c in result["checks"] if c["name"].startswith("line_item_") and c["name"].endswith("_total")]
        assert len(line_checks) == 2
        assert all(c["status"] == "PASS" for c in line_checks)

    def test_invoice_cash_change(self):
        data = {
            "total_amount": {"value": 60.30},
            "cash_paid": {"value": 70.30},
            "change": {"value": 10.00},
        }
        result = self.svc.validate(data, "invoice")
        cash_check = [c for c in result["checks"] if c["name"] == "cash_change_check"]
        assert len(cash_check) == 1
        assert cash_check[0]["status"] == "PASS"

    def test_balance_sheet_assets_eq_liabilities(self):
        data = {
            "periods": [{
                "period_label": "2024",
                "capital_and_liabilities": {
                    "items": [
                        {"name": "Capital", "value": 100},
                        {"name": "Reserves", "value": 400},
                    ],
                    "total": {"value": 500},
                },
                "assets": {
                    "items": [
                        {"name": "Cash", "value": 200},
                        {"name": "Investments", "value": 300},
                    ],
                    "total": {"value": 500},
                },
            }],
        }
        result = self.svc.validate(data, "balance_sheet")
        eq_check = [c for c in result["checks"] if "assets_eq" in c["name"]]
        assert len(eq_check) == 1
        assert eq_check[0]["status"] == "PASS"

    def test_cash_flow_sum(self):
        data = {
            "periods": [{
                "period_label": "2024",
                "operating_activities": {"items": [], "net_cash_flow": {"value": 100}},
                "investing_activities": {"items": [], "net_cash_flow": {"value": -50}},
                "financing_activities": {"items": [], "net_cash_flow": {"value": -30}},
                "net_increase_in_cash": {"value": 20},
                "opening_cash": {"value": 80},
                "closing_cash": {"value": 100},
            }],
        }
        result = self.svc.validate(data, "cash_flow_statement")
        sum_check = [c for c in result["checks"] if "cash_flow_sum" in c["name"]]
        assert len(sum_check) == 1
        assert sum_check[0]["status"] == "PASS"

    def test_missing_fields_not_applicable(self):
        data = {
            "subtotal": {"value": 100.00},
            # tax_amount and total_amount missing
        }
        result = self.svc.validate(data, "invoice")
        # Should have no checks since total_amount is missing
        total_checks = [c for c in result["checks"] if c["name"] == "invoice_total_check"]
        assert len(total_checks) == 0

    def test_profit_and_loss_validation(self):
        data = {
            "periods": [{
                "period_label": "2024",
                "income": {
                    "items": [
                        {"name": "Interest Earned", "value": 300},
                        {"name": "Other Income", "value": 50},
                    ],
                    "total_income": {"value": 350},
                },
                "expenditure": {
                    "items": [
                        {"name": "Interest Expended", "value": 150},
                        {"name": "Operating Expenses", "value": 50},
                    ],
                    "total_expenditure": {"value": 200},
                },
                "profit_calculations": {
                    "net_profit_for_the_year": {"value": 150},
                },
            }],
        }
        result = self.svc.validate(data, "profit_and_loss")
        inc_check = [c for c in result["checks"] if "income_components" in c["name"]]
        assert len(inc_check) == 1
        assert inc_check[0]["status"] == "PASS"
