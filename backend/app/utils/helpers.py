"""Utility helpers shared across services."""

from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    """Try to convert a value to float, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(" ", "").strip()
        # Handle parentheses as negative
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


def get_field_value(data: dict, key: str) -> Optional[float]:
    """Extract a numeric value from a field that may be a dict or a scalar.

    Handles both ``{"value": 123.45}`` and plain ``123.45``.
    """
    val = data.get(key)
    if val is None:
        return None
    if isinstance(val, dict):
        return safe_float(val.get("value"))
    return safe_float(val)


def get_nested_value(data: dict, *keys: str) -> Any:
    """Walk a nested dict by successive keys, returning None on miss."""
    current = data
    for k in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(k)
    return current
