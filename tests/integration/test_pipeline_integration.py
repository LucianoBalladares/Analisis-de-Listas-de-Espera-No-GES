"""
test_pipeline_integration.py — Tests de integración del pipeline completo.

Cubren:
  1. Ciclo completo de ingesta (Excel → PostgreSQL)
  2. Idempotencia del UPSERT (re-carga del mismo Excel)
  3. Preservación de observaciones en re-carga
  4. Normalización de ss_id mediante el catálogo
  5. Nombre canónico SS Del Maule (no SS Maule)
  6. Corrección del bug de división entera en pct_mayor_24m / pct_mayor_36m
  7. pct_mayor_24m = NULL cuando tramos no están disponibles
  8. clean_waitlists.sql — recalculo de asimetría faltante
  9. clean_waitlists.sql — detección de incoherencia en tramos de antigüedad
 10. Ingestas de personas_nacional y nivel_atencion
 11. Vista v_disponibilidad_indicadores — cobertura correcta

Ejecución:
    pytest tests/integration/ -m integration -v

Requiere:
    Base de datos PostgreSQL configurada en TEST_DB_* (ver conftest.py).
"""

import pytest
import pandas as pd
from pathlib import Path

from pipeline.ingest.excel_a_sql import (
    process_listas_espera,
    process_nivel_atencion,
    process_personas_nacional,
    upsert_listas_espera,
    upsert_nivel_atencion,
    upsert_personas_nacional,
)
from pipeline.transform.run_transformations import (
    create_canonical_temp_table,
    execute_catalog_normalization,
    execute_sql_file,
)

from tests.integration.conftest import make_test_excel, requires_test_db

_ROOT = Path(__file__).resolve().parent.parent.parent
_SQL_CLEAN     = _ROOT / "sql" / "transformations" / "clean_waitlists.sql"
_SQL_NORMALIZE = _ROOT / "sql" / "transformations" / "normalize_services.sql"


def _load_excel(db, trimestre: str, path: Path):
    """Helper: carga las 3 hojas de un Excel de test en la BD."""
    xl = pd.ExcelFile(path, engine="openpyxl")

    raw = xl.parse("listas_espera_ss_trimestre", dtype=str)
    df = process_listas_espera(raw, trimestre)
    upsert_listas_espera(db, df)

    raw = xl.parse("personas_nacional_trimestre", dtype=str)
    df = process_personas_nacional(raw, trimestre)
    upsert_personas_nacional(db, df)

    raw = xl.parse("nivel_atencion_trimestre", dtype=str)
    df = process_nivel_atencion(raw, trimestre)
    upsert_nivel_atencion(db, df)

    db.commit()


def _query(db, sql: str, params=None) -> list:
    with db.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()


# ── 1. Ciclo de ingesta ───────────────────────────────────────────────────────

@requires_test_db
@pytest.mark.integration
class TestIngestCycle:

    def test_listas_rows_inserted(self, db, tmp_path):
        """El pipeline carga el número correcto de filas en listas_espera_ss_trimestre."""
        excel = make_test_excel("2023_T1", tmp_path)
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, "SELECT COUNT(*) FROM listas_espera_ss_trimestre WHERE trimestre = '2023_T1'")
        assert rows[0][0] == 2

    def test_personas_rows_inserted(self, db, tmp_path):
        """El pipeline carga las filas de personas_nacional_trimestre."""
        excel = make_test_excel("2023_T1", tmp_path)
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, "SELECT COUNT(*) FROM personas_nacional_trimestre WHERE trimestre = '2023_T1'")
        assert rows[0][0] == 2

    def test_nivel_rows_inserted(self, db, tmp_path):
        """El pipeline carga las filas de nivel_atencion_trimestre."""
        excel = make_test_excel("2023_T1", tmp_path)
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, "SELECT COUNT(*) FROM nivel_atencion_trimestre WHERE trimestre = '2023_T1'")
        assert rows[0][0] == 3

    def test_asimetria_computed_on_ingest(self, db, tmp_path):
        """La asimetría se calcula automáticamente como promedio - mediana durante la ingesta."""
        excel = make_test_excel("2023_T1", tmp_path)
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, """
            SELECT promedio_dias, mediana_dias, asimetria
            FROM listas_espera_ss_trimestre
            WHERE trimestre = '2023_T1' AND ss_id = 'SS Metropolitano Norte'
        """)

        assert rows, "No se encontró el registro esperado"
        promedio, mediana, asimetria = float(rows[0][0]), float(rows[0][1]), float(rows[0][2])
        assert abs(asimetria - (promedio - mediana)) <= 0.1, (
            f"asimetria esperada: {promedio - mediana:.1f}, obtenida: {asimetria}"
        )

    def test_null_markers_stored_as_null(self, db, tmp_path):
        """Marcadores N/D y similares se almacenan como NULL, no como string."""
        listas_rows = [{
            "ss_id": "SS Antofagasta",
            "tipo_prestacion": "CNE",
            "personas_espera": "N/D",   # marcador de no disponible
            "registros_espera": 3000,
            "mediana_dias": "S/I",       # otro marcador
            "promedio_dias": None,
            "reg_24a36m": "-",
            "reg_mayor_36m": None,
            "fuente": "Glosa 06",
            "observaciones": None,
        }]
        excel = make_test_excel("2022_T3", tmp_path, listas_rows=listas_rows)
        _load_excel(db, "2022_T3", excel)

        rows = _query(db, """
            SELECT personas_espera, mediana_dias, reg_24a36m
            FROM listas_espera_ss_trimestre
            WHERE trimestre = '2022_T3' AND ss_id = 'SS Antofagasta'
        """)

        assert rows[0][0] is None, "N/D debe almacenarse como NULL"
        assert rows[0][1] is None, "S/I debe almacenarse como NULL"
        assert rows[0][2] is None, "'-' debe almacenarse como NULL"

    def test_total_rows_filtered_out(self, db, tmp_path):
        """Filas de totales (Total, Total Nacional, etc.) se descartan durante la ingesta."""
        listas_rows = [
            {
                "ss_id": "SS Metropolitano Norte", "tipo_prestacion": "CNE",
                "personas_espera": 5000, "registros_espera": 6000,
                "mediana_dias": 300, "promedio_dias": 350,
                "reg_24a36m": None, "reg_mayor_36m": None,
                "fuente": "Glosa 06", "observaciones": None,
            },
            {
                "ss_id": "Total Nacional", "tipo_prestacion": "CNE",
                "personas_espera": 100000, "registros_espera": 120000,
                "mediana_dias": 280, "promedio_dias": 300,
                "reg_24a36m": None, "reg_mayor_36m": None,
                "fuente": "Glosa 06", "observaciones": None,
            },
        ]
        excel = make_test_excel("2022_T4", tmp_path, listas_rows=listas_rows)
        _load_excel(db, "2022_T4", excel)

        rows = _query(db, """
            SELECT ss_id FROM listas_espera_ss_trimestre
            WHERE trimestre = '2022_T4'
            ORDER BY ss_id
        """)

        ss_ids = [r[0] for r in rows]
        assert "Total Nacional" not in ss_ids, "La fila de totales no debe cargarse"
        assert len(ss_ids) == 1


# ── 2. Idempotencia UPSERT ────────────────────────────────────────────────────

@requires_test_db
@pytest.mark.integration
class TestUpsertIdempotency:

    def test_double_load_no_duplicates(self, db, tmp_path):
        """Cargar el mismo Excel dos veces no duplica registros."""
        excel = make_test_excel("2023_T2", tmp_path)
        for _ in range(2):
            _load_excel(db, "2023_T2", excel)

        rows = _query(db, "SELECT COUNT(*) FROM listas_espera_ss_trimestre WHERE trimestre = '2023_T2'")
        assert rows[0][0] == 2, "UPSERT idempotente: exactamente 2 filas tras doble carga"

    def test_second_load_counts_as_updates(self, db, tmp_path):
        """En la segunda carga, los conteos reportan actualizaciones, no inserciones."""
        excel = make_test_excel("2023_T3", tmp_path)
        xl = pd.ExcelFile(excel, engine="openpyxl")

        # Primera carga
        raw = xl.parse("listas_espera_ss_trimestre", dtype=str)
        df = process_listas_espera(raw, "2023_T3")
        n_ins_1, n_upd_1 = upsert_listas_espera(db, df)
        db.commit()

        # Segunda carga (mismo contenido)
        raw = xl.parse("listas_espera_ss_trimestre", dtype=str)
        df = process_listas_espera(raw, "2023_T3")
        n_ins_2, n_upd_2 = upsert_listas_espera(db, df)
        db.commit()

        assert n_ins_1 == 2, "Primera carga: 2 inserciones"
        assert n_upd_1 == 0, "Primera carga: 0 actualizaciones"
        assert n_ins_2 == 0, "Segunda carga: 0 inserciones"
        assert n_upd_2 == 2, "Segunda carga: 2 actualizaciones"

    def test_observaciones_preserved_on_reload(self, db, tmp_path):
        """El UPSERT preserva observaciones existentes; no las sobreescribe con NULL."""
        excel = make_test_excel("2023_T4", tmp_path)
        _load_excel(db, "2023_T4", excel)

        # Simular anotación agregada por transformación
        with db.cursor() as cur:
            cur.execute("""
                UPDATE listas_espera_ss_trimestre
                SET observaciones = 'ALERTA: dato anómalo registrado manualmente'
                WHERE trimestre = '2023_T4'
                  AND ss_id = 'SS Metropolitano Norte'
            """)
        db.commit()

        # Re-cargar con observaciones = None en el Excel
        _load_excel(db, "2023_T4", excel)

        rows = _query(db, """
            SELECT observaciones FROM listas_espera_ss_trimestre
            WHERE trimestre = '2023_T4' AND ss_id = 'SS Metropolitano Norte'
        """)

        assert "ALERTA: dato anómalo" in (rows[0][0] or ""), (
            "El UPSERT no debe sobreescribir observaciones existentes con NULL del Excel"
        )


# ── 3. Normalización de ss_id ─────────────────────────────────────────────────

@requires_test_db
@pytest.mark.integration
class TestSSNormalization:

    def test_prefix_servicio_de_salud_stripped(self, db, tmp_path):
        """'Servicio de Salud Antofagasta' se normaliza a 'SS Antofagasta'."""
        rows = [{
            "ss_id": "Servicio de Salud Antofagasta",
            "tipo_prestacion": "CNE",
            "personas_espera": 1000, "registros_espera": 1200,
            "mediana_dias": 250, "promedio_dias": 270,
            "reg_24a36m": None, "reg_mayor_36m": None,
            "fuente": "Glosa 06", "observaciones": None,
        }]
        excel = make_test_excel("2022_T3", tmp_path, listas_rows=rows)
        _load_excel(db, "2022_T3", excel)
        execute_catalog_normalization(db)
        db.commit()

        result = _query(db, "SELECT ss_id FROM listas_espera_ss_trimestre WHERE trimestre = '2022_T3'")
        assert result[0][0] == "SS Antofagasta"

    def test_ss_del_maule_is_canonical(self, db, tmp_path):
        """'del maule' y 'maule' normalizan a 'SS Del Maule', nunca a 'SS Maule'."""
        for alias in ("del maule", "maule", "SS Del Maule"):
            listas_rows = [{
                "ss_id": alias, "tipo_prestacion": "IQ",
                "personas_espera": 800, "registros_espera": 900,
                "mediana_dias": 200, "promedio_dias": 220,
                "reg_24a36m": None, "reg_mayor_36m": None,
                "fuente": "Glosa 06", "observaciones": None,
            }]
            # Usar trimestres distintos para evitar conflicto UNIQUE
            trimestre = f"2022_T{'1' if alias=='del maule' else '2' if alias=='maule' else '3'}"
            excel = make_test_excel(trimestre, tmp_path, listas_rows=listas_rows)
            _load_excel(db, trimestre, excel)

        execute_catalog_normalization(db)
        db.commit()

        result = _query(db, """
            SELECT DISTINCT ss_id FROM listas_espera_ss_trimestre
            WHERE tipo_prestacion = 'IQ'
        """)
        ss_ids = {r[0] for r in result}

        assert "SS Del Maule" in ss_ids, "El nombre canónico correcto es 'SS Del Maule'"
        assert "SS Maule" not in ss_ids, "'SS Maule' no debe existir tras la normalización"

    def test_unrecognized_ss_kept_with_original_value(self, db, tmp_path):
        """Un ss_id no reconocido se carga con su valor original (no se descarta)."""
        rows = [{
            "ss_id": "SS Inventado Para Test",
            "tipo_prestacion": "CNE",
            "personas_espera": 100, "registros_espera": 120,
            "mediana_dias": 180, "promedio_dias": 200,
            "reg_24a36m": None, "reg_mayor_36m": None,
            "fuente": "Glosa 06", "observaciones": None,
        }]
        excel = make_test_excel("2022_T4", tmp_path, listas_rows=rows)
        _load_excel(db, "2022_T4", excel)

        result = _query(db, """
            SELECT ss_id FROM listas_espera_ss_trimestre WHERE trimestre = '2022_T4'
        """)
        assert result[0][0] == "SS Inventado Para Test", (
            "ss_id no reconocido debe cargarse con el valor original, no descartarse"
        )


# ── 4. Bug de división entera en porcentajes ──────────────────────────────────

@requires_test_db
@pytest.mark.integration
class TestViewPercentages:

    def test_pct_mayor_24m_correct_value(self, db, tmp_path):
        """
        pct_mayor_24m debe ser (reg_24a36m + reg_mayor_36m) / registros_espera * 100
        usando división de punto flotante (no entera).

        Caso concreto: 1200 + 800 = 2000 sobre 10000 → 20.0 %
        Si la división fuera entera: 2000 / 10000 = 0, luego 0 * 100 = 0 → BUG.
        """
        excel = make_test_excel("2023_T1", tmp_path)  # default: 1200+800 / 10000
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, """
            SELECT pct_mayor_24m
            FROM v_listas_espera_enriquecido
            WHERE trimestre = '2023_T1' AND ss_id = 'SS Metropolitano Norte'
        """)

        assert rows, "No se encontró el registro en la vista"
        pct = rows[0][0]
        assert pct is not None, "pct_mayor_24m es NULL cuando debería tener valor"
        assert abs(float(pct) - 20.0) < 0.2, (
            f"pct_mayor_24m esperado ≈ 20.0, obtenido: {pct}. "
            "Si es 0, el bug de división entera no está corregido en la vista."
        )

    def test_pct_mayor_36m_correct_value(self, db, tmp_path):
        """pct_mayor_36m debe ser reg_mayor_36m / registros_espera * 100 (float)."""
        excel = make_test_excel("2023_T1", tmp_path)  # default: 800 / 10000 = 8%
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, """
            SELECT pct_mayor_36m
            FROM v_listas_espera_enriquecido
            WHERE trimestre = '2023_T1' AND ss_id = 'SS Metropolitano Norte'
        """)

        pct = rows[0][0]
        assert abs(float(pct) - 8.0) < 0.2, (
            f"pct_mayor_36m esperado ≈ 8.0, obtenido: {pct}"
        )

    def test_pct_null_when_tramos_not_available(self, db, tmp_path):
        """pct_mayor_24m y pct_mayor_36m son NULL cuando los tramos no están disponibles."""
        rows = [{
            "ss_id": "SS Antofagasta", "tipo_prestacion": "CNE",
            "personas_espera": 2000, "registros_espera": 3000,
            "mediana_dias": 280, "promedio_dias": 300,
            "reg_24a36m": None,   # No disponible (ej: 2024_T1)
            "reg_mayor_36m": None,
            "fuente": "Glosa 06", "observaciones": None,
        }]
        excel = make_test_excel("2024_T1", tmp_path, listas_rows=rows)
        _load_excel(db, "2024_T1", excel)

        result = _query(db, """
            SELECT pct_mayor_24m, pct_mayor_36m
            FROM v_listas_espera_enriquecido
            WHERE trimestre = '2024_T1' AND ss_id = 'SS Antofagasta'
        """)

        assert result[0][0] is None, "pct_mayor_24m debe ser NULL cuando reg_24a36m es NULL"
        assert result[0][1] is None, "pct_mayor_36m debe ser NULL cuando reg_mayor_36m es NULL"

    def test_pct_handles_edge_case_full_list_is_old(self, db, tmp_path):
        """pct_mayor_24m = 100 cuando todos los registros tienen más de 24 meses."""
        rows = [{
            "ss_id": "SS Coquimbo", "tipo_prestacion": "IQ",
            "personas_espera": 1000, "registros_espera": 1000,
            "mediana_dias": 900, "promedio_dias": 1000,
            "reg_24a36m": 400,    # 40%
            "reg_mayor_36m": 600, # 60%  → suma = 100% de 1000
            "fuente": "Glosa 06", "observaciones": None,
        }]
        excel = make_test_excel("2022_T3", tmp_path, listas_rows=rows)
        _load_excel(db, "2022_T3", excel)

        result = _query(db, """
            SELECT pct_mayor_24m FROM v_listas_espera_enriquecido
            WHERE trimestre = '2022_T3' AND ss_id = 'SS Coquimbo'
        """)
        assert abs(float(result[0][0]) - 100.0) < 0.2


# ── 5. Transformaciones SQL ───────────────────────────────────────────────────

@requires_test_db
@pytest.mark.integration
class TestTransformations:

    def test_clean_waitlists_recalculates_missing_asimetria(self, db):
        """clean_waitlists.sql recalcula asimetria cuando es NULL pero existen promedio y mediana."""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO listas_espera_ss_trimestre
                    (ss_id, trimestre, tipo_prestacion,
                     mediana_dias, promedio_dias, asimetria, fuente)
                VALUES ('SS Antofagasta', '2022_T4', 'CNE', 200.0, 250.0, NULL, 'Glosa 06')
            """)
        db.commit()

        execute_sql_file(db, _SQL_CLEAN)
        db.commit()

        rows = _query(db, """
            SELECT asimetria FROM listas_espera_ss_trimestre
            WHERE trimestre = '2022_T4' AND ss_id = 'SS Antofagasta'
        """)
        assert abs(float(rows[0][0]) - 50.0) < 0.1, (
            "clean_waitlists.sql debe recalcular asimetria = promedio - mediana"
        )

    def test_clean_waitlists_flags_antiguedad_incoherencia(self, db):
        """clean_waitlists.sql marca en observaciones cuando tramos > registros_espera."""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO listas_espera_ss_trimestre
                    (ss_id, trimestre, tipo_prestacion,
                     registros_espera, reg_24a36m, reg_mayor_36m, fuente)
                VALUES ('SS Maule', '2023_T1', 'IQ', 1000, 700, 600, 'Glosa 06')
            """)
        db.commit()

        execute_sql_file(db, _SQL_CLEAN)
        db.commit()

        rows = _query(db, """
            SELECT observaciones FROM listas_espera_ss_trimestre
            WHERE trimestre = '2023_T1' AND tipo_prestacion = 'IQ'
        """)

        obs = rows[0][0] or ""
        assert "ALERTA" in obs, (
            "clean_waitlists.sql debe marcar incoherencia de tramos en observaciones"
        )

    def test_clean_waitlists_assigns_default_fuente(self, db):
        """clean_waitlists.sql asigna 'Glosa 06' como fuente cuando es NULL."""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO listas_espera_ss_trimestre
                    (ss_id, trimestre, tipo_prestacion,
                     registros_espera, mediana_dias, fuente)
                VALUES ('SS Atacama', '2022_T3', 'CNE', 500, 180.0, NULL)
            """)
        db.commit()

        execute_sql_file(db, _SQL_CLEAN)
        db.commit()

        rows = _query(db, """
            SELECT fuente FROM listas_espera_ss_trimestre
            WHERE trimestre = '2022_T3' AND ss_id = 'SS Atacama'
        """)
        assert rows[0][0] == "Glosa 06"

    def test_transformations_are_idempotent(self, db, tmp_path):
        """Ejecutar clean_waitlists.sql dos veces produce el mismo resultado."""
        excel = make_test_excel("2023_T2", tmp_path)
        _load_excel(db, "2023_T2", excel)

        execute_sql_file(db, _SQL_CLEAN)
        db.commit()

        rows_after_first = _query(db, """
            SELECT ss_id, asimetria, fuente, observaciones
            FROM listas_espera_ss_trimestre
            WHERE trimestre = '2023_T2'
            ORDER BY ss_id
        """)

        execute_sql_file(db, _SQL_CLEAN)
        db.commit()

        rows_after_second = _query(db, """
            SELECT ss_id, asimetria, fuente, observaciones
            FROM listas_espera_ss_trimestre
            WHERE trimestre = '2023_T2'
            ORDER BY ss_id
        """)

        assert rows_after_first == rows_after_second, (
            "clean_waitlists.sql debe ser idempotente: dos ejecuciones dan el mismo resultado"
        )


# ── 6. Vista v_disponibilidad_indicadores ─────────────────────────────────────

@requires_test_db
@pytest.mark.integration
class TestAvailabilityView:

    def test_periodo_correctly_reported_as_available(self, db, tmp_path):
        """v_disponibilidad_indicadores reporta correctamente los indicadores disponibles."""
        excel = make_test_excel("2023_T1", tmp_path)
        _load_excel(db, "2023_T1", excel)

        rows = _query(db, """
            SELECT mediana_disponible, tramo_24_36m_disponible,
                   tramo_mayor_36m_disponible, antiguedad_completa_disponible
            FROM v_disponibilidad_indicadores
            WHERE trimestre = '2023_T1' AND tipo_prestacion = 'CNE'
        """)

        assert rows, "No se encontró el período en v_disponibilidad_indicadores"
        mediana, t2436, t36, completa = rows[0]
        assert mediana  is True, "mediana_disponible debería ser True"
        assert t2436    is True, "tramo_24_36m_disponible debería ser True"
        assert t36      is True, "tramo_mayor_36m_disponible debería ser True"
        assert completa is True, "antiguedad_completa_disponible debería ser True"

    def test_missing_tramos_reported_as_unavailable(self, db, tmp_path):
        """Un período sin tramos se reporta correctamente como no disponible."""
        rows = [{
            "ss_id": "SS Antofagasta", "tipo_prestacion": "CNE",
            "personas_espera": 2000, "registros_espera": 3000,
            "mediana_dias": 280, "promedio_dias": 300,
            "reg_24a36m": None, "reg_mayor_36m": None,
            "fuente": "Glosa 06", "observaciones": None,
        }]
        excel = make_test_excel("2024_T2", tmp_path, listas_rows=rows)
        _load_excel(db, "2024_T2", excel)

        result = _query(db, """
            SELECT antiguedad_completa_disponible
            FROM v_disponibilidad_indicadores
            WHERE trimestre = '2024_T2' AND tipo_prestacion = 'CNE'
        """)

        assert result[0][0] is False, (
            "antiguedad_completa_disponible debe ser False cuando los tramos son NULL"
        )
        