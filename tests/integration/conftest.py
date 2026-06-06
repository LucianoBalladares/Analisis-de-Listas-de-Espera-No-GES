"""
conftest.py — Fixtures para tests de integración.

Requiere una base de datos PostgreSQL de prueba separada de producción.

Configuración (crear un archivo .env.test en la raíz del proyecto):
    TEST_DB_HOST=localhost
    TEST_DB_PORT=5432
    TEST_DB_NAME=listas_espera_test
    TEST_DB_USER=postgres
    TEST_DB_PASSWORD=tu_password

Inicialización manual (primera vez):
    psql -U postgres -c "CREATE DATABASE listas_espera_test;"

Los tests crean y destruyen el esquema automáticamente en cada sesión.
"""

import os
from pathlib import Path

import pandas as pd
import psycopg2
import pytest
from dotenv import load_dotenv

# Carga .env.test primero (prioridad) y luego .env como fallback
_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env.test", override=True)
load_dotenv(_ROOT / ".env", override=False)

# ── Configuración del test DB ─────────────────────────────────────────────────

TEST_DB_CONFIG = {
    "host":     os.getenv("TEST_DB_HOST",     os.getenv("DB_HOST", "localhost")),
    "port":     int(os.getenv("TEST_DB_PORT", os.getenv("DB_PORT", 5432))),
    "dbname":   os.getenv("TEST_DB_NAME",     "listas_espera_test"),
    "user":     os.getenv("TEST_DB_USER",     os.getenv("DB_USER", "postgres")),
    "password": os.getenv("TEST_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
}

# Archivos SQL del esquema, en orden de ejecución
_SQL_SCHEMA = [
    _ROOT / "sql" / "schema" / "create_tables.sql",
    _ROOT / "sql" / "schema" / "constraints.sql",
    _ROOT / "sql" / "schema" / "indexes.sql",
    _ROOT / "sql" / "schema" / "triggers.sql",
    _ROOT / "sql" / "views"  / "dashboard_views.sql",
]

_TABLES_TO_TRUNCATE = [
    "pipeline_runs",
    "listas_espera_ss_trimestre",
    "personas_nacional_trimestre",
    "nivel_atencion_trimestre",
]

_OBJECTS_TO_DROP = """
    DROP TABLE IF EXISTS pipeline_runs CASCADE;
    DROP TABLE IF EXISTS listas_espera_ss_trimestre CASCADE;
    DROP TABLE IF EXISTS personas_nacional_trimestre CASCADE;
    DROP TABLE IF EXISTS nivel_atencion_trimestre CASCADE;
    DROP VIEW  IF EXISTS v_listas_espera_enriquecido CASCADE;
    DROP VIEW  IF EXISTS v_dim_trimestre CASCADE;
    DROP VIEW  IF EXISTS v_nivel_atencion_distribucion CASCADE;
    DROP VIEW  IF EXISTS v_pct_nivel_terciario CASCADE;
    DROP VIEW  IF EXISTS v_disponibilidad_indicadores CASCADE;
    DROP FUNCTION IF EXISTS trg_set_updated_at CASCADE;
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_test_db_available() -> bool:
    try:
        conn = psycopg2.connect(**TEST_DB_CONFIG, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


def _exec_sql_file(conn, path: Path) -> None:
    """Ejecuta un archivo SQL completo (autocommit requerido)."""
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)


# ── Marker de skip automático ────────────────────────────────────────────────

requires_test_db = pytest.mark.skipif(
    not _is_test_db_available(),
    reason=(
        "Base de datos de test no disponible. "
        "Configura TEST_DB_* en .env.test y crea la base: "
        "psql -U postgres -c 'CREATE DATABASE listas_espera_test;'"
    ),
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_db_session():
    """
    Conexión de sesión al test DB con esquema inicializado.
    El esquema se crea al inicio y se destruye al final de la sesión.
    """
    if not _is_test_db_available():
        pytest.skip("Test DB no disponible")

    conn = psycopg2.connect(**TEST_DB_CONFIG)
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute(_OBJECTS_TO_DROP)
        for sql_file in _SQL_SCHEMA:
            _exec_sql_file(conn, sql_file)

    conn.autocommit = False
    yield conn

    # Teardown: limpiar al finalizar la sesión
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_OBJECTS_TO_DROP)
    conn.close()


@pytest.fixture()
def db(test_db_session):
    """
    Conexión limpia por test: hace TRUNCATE de todas las tablas
    antes de cada test y rollback de cualquier transacción sucia.
    Alias corto para usar en los tests.
    """
    test_db_session.rollback()
    with test_db_session.cursor() as cur:
        tables = ", ".join(_TABLES_TO_TRUNCATE)
        cur.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
    test_db_session.commit()
    yield test_db_session
    test_db_session.rollback()


# ── Fábrica de Excel de prueba ────────────────────────────────────────────────

def make_test_excel(
    trimestre: str,
    tmp_path: Path,
    listas_rows: list[dict] | None = None,
    personas_rows: list[dict] | None = None,
    nivel_rows: list[dict] | None = None,
) -> Path:
    """
    Genera un archivo Excel mínimo con la estructura esperada por el pipeline.

    Parámetros
    ----------
    trimestre    : Código de período, ej. "2023_T1"
    tmp_path     : Directorio temporal donde se crea el archivo
    listas_rows  : Filas para la hoja listas_espera_ss_trimestre (usa default si None)
    personas_rows: Filas para la hoja personas_nacional_trimestre (usa default si None)
    nivel_rows   : Filas para la hoja nivel_atencion_trimestre (usa default si None)

    Retorna
    -------
    Path al archivo .xlsx creado.
    """
    if listas_rows is None:
        listas_rows = [
            {
                "ss_id": "SS Metropolitano Norte",
                "tipo_prestacion": "CNE",
                "personas_espera": 5000,
                "registros_espera": 10000,
                "mediana_dias": 300,
                "promedio_dias": 350,
                "reg_24a36m": 1200,
                "reg_mayor_36m": 800,
                "fuente": "Glosa 06",
                "observaciones": None,
            },
            {
                "ss_id": "SS Antofagasta",
                "tipo_prestacion": "CNE",
                "personas_espera": 2000,
                "registros_espera": 3000,
                "mediana_dias": 250,
                "promedio_dias": 280,
                "reg_24a36m": 300,
                "reg_mayor_36m": 150,
                "fuente": "Glosa 06",
                "observaciones": None,
            },
        ]

    if personas_rows is None:
        personas_rows = [
            {"tipo_prestacion": "CNE", "personas_total": 120000},
            {"tipo_prestacion": "IQ",  "personas_total": 45000},
        ]

    if nivel_rows is None:
        nivel_rows = [
            {"nivel_atencion": "Primario",   "tipo_prestacion": "CNE", "registros_total_nivel": 10000},
            {"nivel_atencion": "Secundario", "tipo_prestacion": "CNE", "registros_total_nivel": 5000},
            {"nivel_atencion": "Terciario",  "tipo_prestacion": "CNE", "registros_total_nivel": 85000},
        ]

    output_path = tmp_path / f"{trimestre}.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(listas_rows).to_excel(
            writer, sheet_name="listas_espera_ss_trimestre", index=False
        )
        pd.DataFrame(personas_rows).to_excel(
            writer, sheet_name="personas_nacional_trimestre", index=False
        )
        pd.DataFrame(nivel_rows).to_excel(
            writer, sheet_name="nivel_atencion_trimestre", index=False
        )

    return output_path