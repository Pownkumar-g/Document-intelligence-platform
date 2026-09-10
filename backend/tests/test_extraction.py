"""Tests for extraction-related utilities and helpers."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.helpers import safe_float, get_field_value, get_nested_value


class TestSafeFloat:
    def test_int(self):
        assert safe_float(42) == 42.0

    def test_float(self):
        assert safe_float(3.14) == 3.14

    def test_string_number(self):
        assert safe_float("123.45") == 123.45

    def test_string_with_commas(self):
        assert safe_float("1,234,567.89") == 1234567.89

    def test_parenthesized_negative(self):
        assert safe_float("(500.00)") == -500.00

    def test_none(self):
        assert safe_float(None) is None

    def test_invalid_string(self):
        assert safe_float("not a number") is None

    def test_empty_string(self):
        assert safe_float("") is None


class TestGetFieldValue:
    def test_dict_with_value(self):
        assert get_field_value({"total": {"value": 123.45}}, "total") == 123.45

    def test_plain_number(self):
        assert get_field_value({"total": 99.9}, "total") == 99.9

    def test_missing_key(self):
        assert get_field_value({"other": 1}, "total") is None

    def test_none_value(self):
        assert get_field_value({"total": None}, "total") is None


class TestGetNestedValue:
    def test_nested(self):
        data = {"a": {"b": {"c": 42}}}
        assert get_nested_value(data, "a", "b", "c") == 42

    def test_missing(self):
        data = {"a": {"b": 1}}
        assert get_nested_value(data, "a", "x") is None

    def test_single_level(self):
        assert get_nested_value({"key": "val"}, "key") == "val"
