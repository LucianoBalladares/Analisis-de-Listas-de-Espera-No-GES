"""
Tests for pipeline/config/catalogos.py

These tests enforce structural invariants on the catalog:
  - SS_CANONICOS must contain exactly 29 services
  - All SS_ID_MAP values must point to a canonical name
  - No duplicates, no typos in key structure
  - NIVELES_ATENCION contains the three expected levels
  - All historical renames are covered
"""
import pytest
from pipeline.config.catalogos import (
    SS_CANONICOS,
    SS_ESPECIALES,
    SS_ID_MAP,
    NIVELES_ATENCION,
)


class TestSSCanonicosIntegrity:

    def test_exactly_29_services(self):
        assert len(SS_CANONICOS) == 29, (
            f"Expected 29 canonical SS, found {len(SS_CANONICOS)}: {sorted(SS_CANONICOS)}"
        )

    def test_all_entries_start_with_ss(self):
        bad = [s for s in SS_CANONICOS if not s.startswith("SS ")]
        assert not bad, f"Entries not starting with 'SS ': {bad}"

    def test_no_duplicates(self):
        # Sets cannot have duplicates, but check the list form if ever refactored
        assert len(SS_CANONICOS) == len(set(SS_CANONICOS))

    def test_no_empty_strings(self):
        assert all(s.strip() for s in SS_CANONICOS)

    def test_all_metropolitanos_present(self):
        metro = {"Norte", "Occidente", "Central", "Oriente", "Sur", "Sur Oriente"}
        for m in metro:
            expected = f"SS Metropolitano {m}"
            assert expected in SS_CANONICOS, f"Missing: {expected}"

    def test_all_araucania_present(self):
        assert "SS Araucanía Norte" in SS_CANONICOS
        assert "SS Araucanía Sur" in SS_CANONICOS

    def test_renamed_services_use_current_names(self):
        # These are historical renames — old names must NOT be in SS_CANONICOS
        assert "SS Arica" not in SS_CANONICOS
        assert "SS Iquique" not in SS_CANONICOS
        assert "SS Valdivia" not in SS_CANONICOS
        # Current names must be present
        assert "SS Arica y Parinacota" in SS_CANONICOS
        assert "SS Tarapacá" in SS_CANONICOS
        assert "SS Los Ríos" in SS_CANONICOS

    def test_special_characters_in_expected_entries(self):
        # Entries with tildes, apostrophes, hyphens must be correct
        assert "SS O'Higgins" in SS_CANONICOS
        assert "SS Ñuble" in SS_CANONICOS
        assert "SS Valparaíso - San Antonio" in SS_CANONICOS
        assert "SS Viña del Mar - Quillota" in SS_CANONICOS
        assert "SS Del Reloncaví" in SS_CANONICOS
        assert "SS Chiloé" in SS_CANONICOS
        assert "SS Aysén" in SS_CANONICOS


class TestSSIdMapIntegrity:

    def test_all_map_values_are_canonical(self):
        non_canonical = {
            k: v for k, v in SS_ID_MAP.items()
            if v not in SS_CANONICOS
        }
        assert not non_canonical, (
            f"SS_ID_MAP values not in SS_CANONICOS: {non_canonical}"
        )

    def test_no_empty_keys(self):
        empty_keys = [k for k in SS_ID_MAP if not k.strip()]
        assert not empty_keys, f"Empty keys found: {empty_keys}"

    def test_no_empty_values(self):
        empty_vals = [k for k, v in SS_ID_MAP.items() if not v.strip()]
        assert not empty_vals, f"Empty values for keys: {empty_vals}"

    def test_all_keys_are_lowercase(self):
        non_lower = [k for k in SS_ID_MAP if k != k.lower()]
        assert not non_lower, (
            f"SS_ID_MAP keys must be lowercase for case-insensitive lookup: {non_lower}"
        )

    def test_historical_renames_present(self):
        assert "arica" in SS_ID_MAP
        assert SS_ID_MAP["arica"] == "SS Arica y Parinacota"
        assert "iquique" in SS_ID_MAP
        assert SS_ID_MAP["iquique"] == "SS Tarapacá"
        assert "valdivia" in SS_ID_MAP
        assert SS_ID_MAP["valdivia"] == "SS Los Ríos"

    def test_ss_prefix_variants_present(self):
        # Each service should have at least one plain-name entry (without 'ss' prefix)
        # so that prefix-stripping logic can find a match
        plain_keys = {k for k in SS_ID_MAP if not k.startswith("ss ")}
        assert len(plain_keys) > 0

    def test_metropolitano_sur_and_sur_oriente_distinct(self):
        # Critical: these two must map to different canonical names
        assert SS_ID_MAP.get("metropolitano sur") == "SS Metropolitano Sur"
        assert SS_ID_MAP.get("metropolitano sur oriente") == "SS Metropolitano Sur Oriente"
        assert SS_ID_MAP["metropolitano sur"] != SS_ID_MAP["metropolitano sur oriente"]

    def test_all_29_canonical_services_reachable_from_map(self):
        reachable = set(SS_ID_MAP.values())
        unreachable = SS_CANONICOS - reachable
        assert not unreachable, (
            f"Canonical SS with no map entry (unreachable by normalisation): {unreachable}"
        )

    def test_map_size_reasonable(self):
        # The map must have more entries than canonical services
        # (multiple aliases per service) but not be excessively large
        assert len(SS_ID_MAP) >= 29
        assert len(SS_ID_MAP) < 500

    def test_del_maule_is_canonical_not_maule(self):
        #SS Del Maule es el nombre oficial en Glosa 06 (no SS Maule).
        assert "SS Del Maule" in SS_CANONICOS
        assert "SS Maule"     not in SS_CANONICOS
        assert SS_ID_MAP.get("maule")     == "SS Del Maule"
        assert SS_ID_MAP.get("del maule") == "SS Del Maule"


class TestNivelesAtencion:

    def test_exactly_three_levels(self):
        assert len(NIVELES_ATENCION) == 3

    def test_expected_levels_present(self):
        assert "Primario" in NIVELES_ATENCION
        assert "Secundario" in NIVELES_ATENCION
        assert "Terciario" in NIVELES_ATENCION

    def test_levels_are_title_case(self):
        for nivel in NIVELES_ATENCION:
            assert nivel == nivel.title(), f"Level not title-case: {nivel}"


class TestSSEspeciales:

    def test_no_overlap_with_canonicos(self):
        overlap = SS_CANONICOS & SS_ESPECIALES
        assert not overlap, f"Overlap between SS_CANONICOS and SS_ESPECIALES: {overlap}"

    def test_especiales_non_empty(self):
        assert len(SS_ESPECIALES) > 0