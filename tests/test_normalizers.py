"""
Tests for normalizer functions:
  - normalize_tipo_prestacion()
  - normalize_nivel_atencion()
  - normalize_ss_id()
  - is_total_row()
  - parse_trimestre()

Each function has its own class. Edge cases and documented variants are
all covered so that OCR-introduced variations are caught by the test suite.
"""
import pytest
import pandas as pd
from pathlib import Path

from pipeline.ingest.excel_a_sql import (
    normalize_tipo_prestacion,
    normalize_nivel_atencion,
    normalize_ss_id,
    is_total_row,
    parse_trimestre,
)


# ── normalize_tipo_prestacion ──────────────────────────────────────────────────

class TestNormalizeTipoPrestacion:

    # --- CNE variants ---
    @pytest.mark.parametrize("val", [
        "CNE", "cne", "Cne",
        "Consulta Nueva de Especialidad",
        "consulta nueva de especialidad",
        "Consulta Nueva Especialidad",
        "Consulta Nueva",
    ])
    def test_cne_variants(self, val):
        assert normalize_tipo_prestacion(val) == "CNE"

    # --- IQ variants ---
    @pytest.mark.parametrize("val", [
        "IQ", "iq", "Iq",
        "Cirugía", "cirugia", "CIRUGIA",
        "Intervención Quirúrgica",
        "intervencion quirurgica",
        "Int. Quirurgica",
        "int. quirúrgica",
        "Quirurgica", "quirúrgica",
    ])
    def test_iq_variants(self, val):
        assert normalize_tipo_prestacion(val) == "IQ"

    # --- Unknown / null ---
    def test_unknown_returns_none(self):
        assert normalize_tipo_prestacion("LABORATORIO") is None

    def test_none_input(self):
        assert normalize_tipo_prestacion(None) is None

    def test_pandas_na(self):
        assert normalize_tipo_prestacion(pd.NA) is None

    def test_null_marker_nd(self):
        assert normalize_tipo_prestacion("N/D") is None

    def test_empty_string(self):
        assert normalize_tipo_prestacion("") is None

    def test_output_is_exactly_cne_or_iq(self):
        assert normalize_tipo_prestacion("cne") in ("CNE", "IQ", None)


# ── normalize_nivel_atencion ───────────────────────────────────────────────────

class TestNormalizeNivelAtencion:

    # --- Primario ---
    @pytest.mark.parametrize("val", [
        "Primario", "primario", "PRIMARIO",
        "Nivel Primario", "nivel primario",
        "1° nivel", "Primer Nivel",
    ])
    def test_primario_variants(self, val):
        assert normalize_nivel_atencion(val) == "Primario"

    # --- Secundario ---
    @pytest.mark.parametrize("val", [
        "Secundario", "secundario", "SECUNDARIO",
        "Nivel Secundario", "nivel secundario",
        "2° nivel", "Segundo Nivel",
    ])
    def test_secundario_variants(self, val):
        assert normalize_nivel_atencion(val) == "Secundario"

    # --- Terciario ---
    @pytest.mark.parametrize("val", [
        "Terciario", "terciario", "TERCIARIO",
        "Nivel Terciario", "nivel terciario",
        "3° nivel", "Tercer Nivel",
    ])
    def test_terciario_variants(self, val):
        assert normalize_nivel_atencion(val) == "Terciario"

    # --- Fallback: .title() ---
    def test_unknown_returns_title_case(self):
        result = normalize_nivel_atencion("cuaternario")
        assert result == "Cuaternario"

    def test_unknown_mixed_case_returns_title(self):
        result = normalize_nivel_atencion("NIVEL ESPECIAL")
        assert result == "Nivel Especial"

    # --- None ---
    def test_none_returns_none(self):
        assert normalize_nivel_atencion(None) is None

    def test_pandas_na_returns_none(self):
        assert normalize_nivel_atencion(pd.NA) is None

    # --- Output is always string or None ---
    def test_output_type(self):
        result = normalize_nivel_atencion("Primario")
        assert isinstance(result, str)


# ── normalize_ss_id ────────────────────────────────────────────────────────────

class TestNormalizeSsId:

    # --- Exact canonical names pass through unchanged ---
    @pytest.mark.parametrize("canonical", [
        "SS Metropolitano Norte",
        "SS Araucanía Sur",
        "SS Del Reloncaví",
        "SS O'Higgins",
        "SS Viña del Mar - Quillota",
        "SS Valparaíso - San Antonio",
    ])
    def test_canonical_names_normalise_correctly(self, canonical):
        result = normalize_ss_id(canonical)
        assert result == canonical

    # --- Historical names (renamed services) ---
    def test_arica_maps_to_arica_parinacota(self):
        assert normalize_ss_id("SS Arica") == "SS Arica y Parinacota"

    def test_iquique_maps_to_tarapaca(self):
        assert normalize_ss_id("Iquique") == "SS Tarapacá"

    def test_valdivia_maps_to_los_rios(self):
        assert normalize_ss_id("Valdivia") == "SS Los Ríos"

    def test_ss_valdivia_maps_to_los_rios(self):
        assert normalize_ss_id("SS Valdivia") == "SS Los Ríos"

    # --- Prefix variants ---
    def test_servicio_de_salud_prefix_stripped(self):
        assert normalize_ss_id("Servicio de Salud Antofagasta") == "SS Antofagasta"

    def test_ss_prefix_stripped(self):
        assert normalize_ss_id("SS Antofagasta") == "SS Antofagasta"

    def test_ss_dot_prefix_stripped(self):
        assert normalize_ss_id("S.S. Coquimbo") == "SS Coquimbo"

    # --- Accent / tilde variants ---
    def test_without_tilde_nuble(self):
        assert normalize_ss_id("SS Nuble") == "SS Ñuble"

    def test_without_tilde_araucania(self):
        assert normalize_ss_id("SS Araucania Sur") == "SS Araucanía Sur"

    def test_without_tilde_biobio(self):
        assert normalize_ss_id("Biobio") == "SS Biobío"

    # --- Hyphen variants ---
    def test_valparaiso_hyphen_no_spaces(self):
        assert normalize_ss_id("SS Valparaíso-San Antonio") == "SS Valparaíso - San Antonio"

    def test_metropolitano_sur_hyphen(self):
        assert normalize_ss_id("SS Metropolitano Sur-Oriente") == "SS Metropolitano Sur Oriente"

    # --- Reloncaví variants ---
    @pytest.mark.parametrize("val", [
        "Reloncavi", "SS Del Reloncavi", "Reloncaví"
    ])
    def test_reloncavi_variants(self, val):
        assert normalize_ss_id(val) == "SS Del Reloncaví"

    # --- Total rows are excluded ---
    def test_total_row_returns_none(self):
        assert normalize_ss_id("Total") is None

    def test_total_nacional_returns_none(self):
        assert normalize_ss_id("Total Nacional") is None

    def test_subtotal_returns_none(self):
        assert normalize_ss_id("Subtotal") is None

    # --- None input ---
    def test_none_returns_none(self):
        assert normalize_ss_id(None) is None

    def test_pandas_na_returns_none(self):
        assert normalize_ss_id(pd.NA) is None

    # --- Unrecognised value falls back to raw ---
    def test_unknown_ss_returns_original(self):
        result = normalize_ss_id("SS Inventado")
        assert result == "SS Inventado"


# ── is_total_row ───────────────────────────────────────────────────────────────

class TestIsTotalRow:

    # --- Should match (return True) ---
    @pytest.mark.parametrize("val", [
        "Total",
        "total",
        "TOTAL",
        "Total Nacional",
        "total nacional",
        "TOTAL NACIONAL",
        "Subtotal",
        "SUBTOTAL",
        "País",
        "pais",
        "PAIS",
        "Nacional",
        "NACIONAL",
        "Promedio Nacional",
        "promedio nacional",
        "Promedio País",
        "N/A",
        "n/a",
        "  Total  ",        # leading/trailing whitespace
    ])
    def test_total_row_returns_true(self, val):
        assert is_total_row(val) is True

    # --- Should NOT match (return False) ---
    @pytest.mark.parametrize("val", [
        "SS Metropolitano Norte",
        "Antofagasta",
        "SS O'Higgins",
        "CNE",
        "IQ",
        "Primario",
        "2024_T3",
        "365",
    ])
    def test_non_total_row_returns_false(self, val):
        assert is_total_row(val) is False

    # --- None / NaN ---
    def test_none_returns_false(self):
        assert is_total_row(None) is False

    def test_nan_returns_false(self):
        assert is_total_row(float("nan")) is False

    def test_pandas_na_returns_false(self):
        assert is_total_row(pd.NA) is False

    def test_empty_string_returns_false(self):
        # Empty string doesn't match any total pattern
        assert is_total_row("") is False


# ── parse_trimestre ────────────────────────────────────────────────────────────

class TestParseTrimestre:

    @pytest.mark.parametrize("filename,expected", [
        ("2024_T3.xlsx",              "2024_T3"),
        ("2024_T4.xlsx",              "2024_T4"),
        ("2021_T1.xlsx",              "2021_T1"),
        ("2025_T2.xlsx",              "2025_T2"),
        ("data/staging/2024_T3.xlsx", "2024_T3"),
        ("reporte_2023_T2_v2.xlsx",   "2023_T2"),
        # lowercase accepted and uppercased
        ("2024_t1.xlsx",              "2024_T1"),
    ])
    def test_valid_filenames(self, filename, expected):
        assert parse_trimestre(Path(filename)) == expected

    @pytest.mark.parametrize("filename", [
        "archivo_sin_trimestre.xlsx",
        "datos.xlsx",
        "2024_T5.xlsx",             # T5 is invalid
        "2024.xlsx",
        "T3_2024.xlsx",             # wrong order — won't match \d{4}_T[1-4]
    ])
    def test_invalid_filenames_raise(self, filename):
        with pytest.raises(ValueError):
            parse_trimestre(Path(filename))

    def test_result_is_always_uppercase(self):
        result = parse_trimestre(Path("2024_t3.xlsx"))
        assert result == result.upper()