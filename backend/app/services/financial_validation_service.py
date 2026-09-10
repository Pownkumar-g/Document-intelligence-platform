"""Financial validation service.

Implements the mandatory validation checks for all four document types:
  • Invoice – line-item totals, subtotal, tax, cash/change reconciliation
  • Balance Sheet – assets ≈ capital & liabilities, component sums
  • Profit & Loss – income/expenditure sums, net-profit derivation
  • Cash Flow Statement – activity sums, opening→closing reconciliation

Tolerance for rounding: 1.0 (absolute).  Fields not present in the
document cause the check to return NOT_APPLICABLE.
"""

import logging
from typing import Any, Optional

from app.utils.helpers import safe_float, get_field_value

logger = logging.getLogger("docextract")

TOLERANCE = 1.0  # Allow ±1.0 for rounding differences


def _check(
    name: str,
    formula: str,
    operands: dict[str, Any],
    calculated: Optional[float],
    reported: Optional[float],
) -> dict[str, Any]:
    """Build a single validation-check dict."""
    if calculated is None or reported is None:
        return {
            "name": name,
            "formula": formula,
            "operands": operands,
            "calculated_value": calculated,
            "reported_value": reported,
            "variance": None,
            "status": "NOT_APPLICABLE",
        }
    variance = round(abs(calculated - reported), 2)
    return {
        "name": name,
        "formula": formula,
        "operands": operands,
        "calculated_value": round(calculated, 2),
        "reported_value": round(reported, 2),
        "variance": variance,
        "status": "PASS" if variance <= TOLERANCE else "FAIL",
    }


class FinancialValidationService:
    """Runs financial-validation checks based on document type."""

    def validate(self, extracted_data: dict, document_type: str) -> dict[str, Any]:
        """Return a validation result dict with checks, overall_status, issues."""
        validators = {
            "invoice": self._validate_invoice,
            "balance_sheet": self._validate_balance_sheet,
            "profit_and_loss": self._validate_profit_and_loss,
            "cash_flow_statement": self._validate_cash_flow,
        }
        validator = validators.get(document_type)
        if not validator:
            return {"checks": [], "overall_status": "PASS", "issues": []}

        try:
            checks = validator(extracted_data)
        except Exception as exc:
            logger.error("Financial validation failed: %s", exc)
            return {
                "checks": [],
                "overall_status": "PASS",
                "issues": [f"Validation error: {exc}"],
            }

        issues = [c["name"] for c in checks if c["status"] == "FAIL"]
        overall = "FAIL" if issues else "PASS"
        return {"checks": checks, "overall_status": overall, "issues": issues}

    # ==================================================================
    # INVOICE
    # ==================================================================
    def _validate_invoice(self, data: dict) -> list[dict]:
        checks: list[dict] = []

        # --- 1. Line-item: qty × unit_price ≈ amount ---
        line_items = data.get("line_items") or []
        line_amounts: list[float] = []

        for idx, item in enumerate(line_items):
            qty = safe_float(item.get("quantity"))
            up = safe_float(item.get("unit_price"))
            amt = safe_float(item.get("amount"))
            if amt is not None:
                line_amounts.append(amt)
            if qty is not None and up is not None and amt is not None:
                calc = round(qty * up, 2)
                checks.append(
                    _check(
                        f"line_item_{idx + 1}_total",
                        "quantity × unit_price",
                        {"quantity": qty, "unit_price": up},
                        calc,
                        amt,
                    )
                )

        # --- 2. Sum of line totals ≈ subtotal ---
        subtotal = get_field_value(data, "subtotal")
        if line_amounts and subtotal is not None:
            calc_sub = round(sum(line_amounts), 2)
            checks.append(
                _check(
                    "line_items_subtotal_check",
                    "sum(line_item_amounts)",
                    {"line_item_amounts": line_amounts},
                    calc_sub,
                    subtotal,
                )
            )

        # --- 3. subtotal + tax − discount ≈ total ---
        tax_val = get_field_value(data, "tax_amount")
        discount_val = get_field_value(data, "discount") or 0.0
        total_val = get_field_value(data, "total_amount")
        rounding_adj = get_field_value(data, "rounding_adjustment") or 0.0

        if subtotal is not None and total_val is not None:
            tax_component = tax_val if tax_val is not None else 0.0
            calc_total = round(subtotal + tax_component - discount_val + rounding_adj, 2)
            checks.append(
                _check(
                    "invoice_total_check",
                    "subtotal + tax_amount - discount + rounding_adjustment",
                    {
                        "subtotal": subtotal,
                        "tax_amount": tax_component,
                        "discount": discount_val,
                        "rounding_adjustment": rounding_adj,
                    },
                    calc_total,
                    total_val,
                )
            )
        elif tax_val is not None and total_val is not None and subtotal is None:
            # Some receipts only show tax and total
            pass

        # --- 4. Cash − Total ≈ Change ---
        cash_val = get_field_value(data, "cash_paid")
        change_val = get_field_value(data, "change")
        if cash_val is not None and total_val is not None and change_val is not None:
            calc_change = round(cash_val - total_val, 2)
            checks.append(
                _check(
                    "cash_change_check",
                    "cash_paid - total_amount",
                    {"cash_paid": cash_val, "total_amount": total_val},
                    calc_change,
                    change_val,
                )
            )

        return checks

    # ==================================================================
    # BALANCE SHEET
    # ==================================================================
    def _validate_balance_sheet(self, data: dict) -> list[dict]:
        checks: list[dict] = []
        periods = data.get("periods") or []

        for period in periods:
            label = period.get("period_label", "unknown")
            cap_liab = period.get("capital_and_liabilities") or {}
            assets = period.get("assets") or {}

            total_cl = self._get_total(cap_liab)
            total_a = self._get_total(assets)

            # Check 1: Total Assets ≈ Total Capital & Liabilities
            checks.append(
                _check(
                    f"assets_eq_liabilities_{label}",
                    "Total Assets ≈ Total Capital & Liabilities",
                    {"total_assets": total_a, "total_capital_and_liabilities": total_cl},
                    total_a,
                    total_cl,
                )
            )

            # Check 2: Sum of asset components ≈ reported Total Assets
            asset_items = assets.get("items") or []
            if asset_items and total_a is not None:
                comp_sum = sum(safe_float(i.get("value")) or 0.0 for i in asset_items)
                checks.append(
                    _check(
                        f"asset_components_sum_{label}",
                        "sum(asset_items) ≈ Total Assets",
                        {"component_count": len(asset_items), "component_sum": round(comp_sum, 2)},
                        round(comp_sum, 2),
                        total_a,
                    )
                )

            # Check 3: Sum of C&L components ≈ reported Total C&L
            cl_items = cap_liab.get("items") or []
            if cl_items and total_cl is not None:
                comp_sum = sum(safe_float(i.get("value")) or 0.0 for i in cl_items)
                checks.append(
                    _check(
                        f"cl_components_sum_{label}",
                        "sum(capital_and_liabilities_items) ≈ Total Capital & Liabilities",
                        {"component_count": len(cl_items), "component_sum": round(comp_sum, 2)},
                        round(comp_sum, 2),
                        total_cl,
                    )
                )

        return checks

    # ==================================================================
    # PROFIT & LOSS
    # ==================================================================
    def _validate_profit_and_loss(self, data: dict) -> list[dict]:
        checks: list[dict] = []
        periods = data.get("periods") or []

        for period in periods:
            label = period.get("period_label", "unknown")
            income = period.get("income") or {}
            expenditure = period.get("expenditure") or {}
            profit_calc = period.get("profit_calculations") or {}

            total_income = self._get_total_pl(income, "total_income")
            total_exp = self._get_total_pl(expenditure, "total_expenditure")

            # Check 1: Sum of income items ≈ Total Income
            inc_items = income.get("items") or []
            if inc_items and total_income is not None:
                comp_sum = sum(safe_float(i.get("value")) or 0.0 for i in inc_items)
                checks.append(
                    _check(
                        f"income_components_sum_{label}",
                        "sum(income_items) ≈ Total Income",
                        {"component_count": len(inc_items), "component_sum": round(comp_sum, 2)},
                        round(comp_sum, 2),
                        total_income,
                    )
                )

            # Check 2: Sum of expenditure items ≈ Total Expenditure
            exp_items = expenditure.get("items") or []
            if exp_items and total_exp is not None:
                comp_sum = sum(safe_float(i.get("value")) or 0.0 for i in exp_items)
                checks.append(
                    _check(
                        f"expenditure_components_sum_{label}",
                        "sum(expenditure_items) ≈ Total Expenditure",
                        {"component_count": len(exp_items), "component_sum": round(comp_sum, 2)},
                        round(comp_sum, 2),
                        total_exp,
                    )
                )

            # Check 3: Total Income − Total Expenditure ≈ Net Profit before MI
            net_profit_bmi = self._pv(profit_calc, "consolidated_net_profit_before_mi") or self._pv(profit_calc, "net_profit_for_the_year")
            if total_income is not None and total_exp is not None and net_profit_bmi is not None:
                calc = round(total_income - total_exp, 2)
                checks.append(
                    _check(
                        f"income_minus_expenditure_{label}",
                        "Total Income - Total Expenditure ≈ Net Profit",
                        {"total_income": total_income, "total_expenditure": total_exp},
                        calc,
                        net_profit_bmi,
                    )
                )

            # Check 4: Net Profit before MI − Minority Interest ≈ Net Profit (Group)
            mi = self._pv(profit_calc, "minority_interest")
            net_group = self._pv(profit_calc, "consolidated_net_profit_group")
            if net_profit_bmi is not None and mi is not None and net_group is not None:
                calc = round(net_profit_bmi - mi, 2)
                checks.append(
                    _check(
                        f"net_profit_after_mi_{label}",
                        "Net Profit before MI - Minority Interest ≈ Net Profit (Group)",
                        {"net_profit_before_mi": net_profit_bmi, "minority_interest": mi},
                        calc,
                        net_group,
                    )
                )

            # Check 5: Current Profit + Brought Forward ≈ Total Available for Appropriation
            bf = self._pv(profit_calc, "brought_forward_profit")
            total_avail = self._pv(profit_calc, "total_available_for_appropriation")
            current_profit = net_group if net_group is not None else net_profit_bmi
            if current_profit is not None and bf is not None and total_avail is not None:
                calc = round(current_profit + bf, 2)
                checks.append(
                    _check(
                        f"appropriation_available_{label}",
                        "Current Profit + Brought Forward ≈ Total Available",
                        {"current_profit": current_profit, "brought_forward": bf},
                        calc,
                        total_avail,
                    )
                )

        return checks

    # ==================================================================
    # CASH FLOW STATEMENT
    # ==================================================================
    def _validate_cash_flow(self, data: dict) -> list[dict]:
        checks: list[dict] = []
        periods = data.get("periods") or []

        for period in periods:
            label = period.get("period_label", "unknown")
            op = period.get("operating_activities") or {}
            inv = period.get("investing_activities") or {}
            fin = period.get("financing_activities") or {}

            op_cf = self._get_cf(op)
            inv_cf = self._get_cf(inv)
            fin_cf = self._get_cf(fin)
            fx = safe_float(self._pv_raw(period, "fx_translation_adjustment")) or 0.0
            net_change = safe_float(self._pv_raw(period, "net_increase_in_cash"))
            opening = safe_float(self._pv_raw(period, "opening_cash"))
            closing = safe_float(self._pv_raw(period, "closing_cash"))
            amalg = safe_float(self._pv_raw(period, "cash_acquired_on_amalgamation")) or 0.0

            # Check 1: Op + Inv + Fin + FX ≈ Net Change in Cash
            if op_cf is not None and inv_cf is not None and fin_cf is not None and net_change is not None:
                calc = round(op_cf + inv_cf + fin_cf + fx, 2)
                checks.append(
                    _check(
                        f"cash_flow_sum_{label}",
                        "Operating + Investing + Financing + FX ≈ Net Change in Cash",
                        {
                            "operating": op_cf,
                            "investing": inv_cf,
                            "financing": fin_cf,
                            "fx_adjustment": fx,
                        },
                        calc,
                        net_change,
                    )
                )

            # Check 2: Opening + Net Change + Amalgamation ≈ Closing
            if opening is not None and net_change is not None and closing is not None:
                calc = round(opening + net_change + amalg, 2)
                checks.append(
                    _check(
                        f"cash_reconciliation_{label}",
                        "Opening Cash + Net Change + Amalgamation ≈ Closing Cash",
                        {
                            "opening_cash": opening,
                            "net_change": net_change,
                            "amalgamation": amalg,
                        },
                        calc,
                        closing,
                    )
                )

        return checks

    # ==================================================================
    # Helpers
    # ==================================================================
    @staticmethod
    def _get_total(section: dict) -> Optional[float]:
        total = section.get("total")
        if total is None:
            return None
        if isinstance(total, dict):
            return safe_float(total.get("value"))
        return safe_float(total)

    @staticmethod
    def _get_total_pl(section: dict, key: str) -> Optional[float]:
        val = section.get(key)
        if val is None:
            return None
        if isinstance(val, dict):
            return safe_float(val.get("value"))
        return safe_float(val)

    @staticmethod
    def _pv(calc_dict: dict, key: str) -> Optional[float]:
        """Get a profit-calc value that may be a dict or scalar."""
        val = calc_dict.get(key)
        if val is None:
            return None
        if isinstance(val, dict):
            return safe_float(val.get("value"))
        return safe_float(val)

    @staticmethod
    def _pv_raw(d: dict, key: str) -> Any:
        """Get raw value (supports nested dict or scalar)."""
        val = d.get(key)
        if val is None:
            return None
        if isinstance(val, dict):
            return val.get("value")
        return val

    @staticmethod
    def _get_cf(section: dict) -> Optional[float]:
        ncf = section.get("net_cash_flow")
        if ncf is None:
            return None
        if isinstance(ncf, dict):
            return safe_float(ncf.get("value"))
        return safe_float(ncf)
