"""
Tests for clean_numeric() — the numeric parser used during Excel ingestion.

The function handles:
  - Clean integers and decimals (normal OCR output)
  - Comma-as-decimal (OCR failure mode)
  - European format with both separators (double-failure safety net)
  - Null / missing value markers
  - Symbols ($, %)
  - Negative values (aberrant in this domain → None)
  - Pandas NA / float NaN / None inputs
"""
import math
import pytest
import pandas as pd

from pipeline.ingest.excel_a_sql import clean_numeric


# ── Normal OCR output (no separators) ─────────────────────────────────────────

class TestNormalIntegers:
    def test_plain_integer(self):
        assert clean_numeric("1234") == 1234.0

    def test_zero(self):
        assert clean_numeric("0") == 0.0

    def test_single_digit(self):
        assert clean_numeric("7") == 7.0

    def test_large_integer(self):
        assert clean_numeric("999999") == 999999.0

    def test_integer_as_float_type(self):
        assert clean_numeric(1234) == 1234.0

    def test_float_input_type(self):
        assert clean_numeric(1234.5) == 1234.5


class TestNormalDecimals:
    def test_decimal_with_dot(self):
        assert clean_numeric("1234.5") == 1234.5

    def test_decimal_less_than_one(self):
        assert clean_numeric("0.5") == 0.5

    def test_two_decimal_places(self):
        assert clean_numeric("365.25") == 365.25

    def test_three_decimal_places(self):
        assert clean_numeric("1.365") == 1.365

    def test_integer_string_returns_float(self):
        result = clean_numeric("100")
        assert isinstance(result, float)


# ── OCR failure modes (comma as decimal) ──────────────────────────────────────

class TestCommaDecimal:
    def test_comma_as_decimal_simple(self):
        assert clean_numeric("1234,5") == 1234.5

    def test_comma_as_decimal_less_than_one(self):
        # 0,365 → 0.365  (3 digits after comma still treated as decimal)
        assert clean_numeric("0,365") == 0.365

    def test_comma_as_decimal_two_digits(self):
        assert clean_numeric("45,75") == 45.75

    def test_comma_as_decimal_zero_prefix(self):
        assert clean_numeric("0,5") == 0.5


# ── European format: both separators (double-failure safety net) ───────────────

class TestBothSeparators:
    def test_european_format_dot_thousands_comma_decimal(self):
        # 1.234,5 → 1234.5  (dot=thousands, comma=decimal)
        assert clean_numeric("1.234,5") == 1234.5

    def test_european_format_larger_number(self):
        # 12.345,67 → 12345.67
        assert clean_numeric("12.345,67") == 12345.67

    def test_american_format_ambiguity(self):
        # 1,234.5 → treated as European → 1.234 (documented incorrect behaviour)
        # This documents the known limitation, NOT the desired outcome.
        result = clean_numeric("1,234.5")
        assert result == pytest.approx(1.234, rel=1e-3)


# ── Null / missing value markers ──────────────────────────────────────────────

class TestNullMarkers:
    @pytest.mark.parametrize("val", [
        "N/D", "ND", "NO DISPONIBLE", "S/I", "S/D",
        "SIN INFORMACION", "SIN INFORMACIÓN",
        "-", "—", "–",
        "", "NA", "N/A", ".", "..",
    ])
    def test_null_markers_return_none(self, val):
        assert clean_numeric(val) is None

    def test_null_marker_case_insensitive(self):
        assert clean_numeric("n/d") is None

    def test_null_marker_with_spaces(self):
        # Strip happens before NULL check
        assert clean_numeric("  -  ") is None


# ── Python / pandas None / NaN ────────────────────────────────────────────────

class TestNoneAndNaN:
    def test_python_none(self):
        assert clean_numeric(None) is None

    def test_pandas_na(self):
        assert clean_numeric(pd.NA) is None

    def test_float_nan(self):
        assert clean_numeric(float("nan")) is None

    def test_pandas_nan(self):
        assert clean_numeric(pd.NaT) is None


# ── Symbol stripping ──────────────────────────────────────────────────────────

class TestSymbolStripping:
    def test_percentage_suffix(self):
        assert clean_numeric("15%") == 15.0

    def test_dollar_prefix(self):
        assert clean_numeric("$100") == 100.0

    def test_dollar_and_percentage(self):
        assert clean_numeric("$15%") == 15.0

    def test_percentage_decimal(self):
        assert clean_numeric("3.5%") == pytest.approx(3.5)


# ── Negative values ───────────────────────────────────────────────────────────

class TestNegatives:
    def test_negative_integer_returns_none(self):
        assert clean_numeric("-5") is None

    def test_negative_decimal_returns_none(self):
        assert clean_numeric("-1.5") is None

    def test_negative_float_type_returns_none(self):
        assert clean_numeric(-100.0) is None

    def test_negative_zero_is_zero(self):
        # -0 after float() is 0.0 which is not < 0
        assert clean_numeric("-0") == 0.0


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_whitespace_only(self):
        assert clean_numeric("   ") is None

    def test_only_dot(self):
        assert clean_numeric(".") is None

    def test_letters_only(self):
        assert clean_numeric("abc") is None

    def test_mixed_letters_numbers(self):
        # Non-numeric chars stripped; "abc123" → "123"
        result = clean_numeric("abc123")
        assert result == 123.0

    def test_very_large_number(self):
        result = clean_numeric("9999999")
        assert result == 9999999.0

    def test_return_type_is_float_or_none(self):
        result = clean_numeric("42")
        assert result is None or isinstance(result, float)