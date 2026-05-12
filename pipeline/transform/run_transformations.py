#!/usr/bin/env python3
"""
run_transformations.py
======================
Ejecuta las transformaciones SQL sobre la base de datos en el orden correcto.

Uso:
    python pipeline/transform/run_transformations.py
    python pipeline/transform/run_transformations.py --trimestre 2024_T3

Orden de ejecución:
    1. normalize_services.sql  → estandariza ss_id
    2. clean_waitlists.sql     → corrige métricas y marca alertas

Cada archivo se ejecuta en su propia transacción. Si uno falla,
los siguientes no se ejecutan y se registra el error en pipeline_runs.
"""

import os
import re
import sys
import logging
from pathlib import Path
from argparse import ArgumentParser

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ── Configuración ──────────────────────────────────────────────────────────────

load_dotenv()

Path("pipeline/logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline/logs/transformaciones.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "listas_espera_ges"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# Transformaciones en orden de ejecución
SQL_DIR = Path("sql/transformations")
TRANSFORMATIONS = [
    SQL_DIR / "normalize_services.sql",
    SQL_DIR / "clean_waitlists.sql",
]

# Catálogo vigente de 29 SS — debe mantenerse sincronizado con
# normalize_services.sql, excel_a_sql.py y validacion.py.
SS_CANONICOS = {
    'SS Arica y Parinacota', 'SS Tarapacá', 'SS Antofagasta',
    'SS Atacama', 'SS Coquimbo',
    'SS Viña del Mar - Quillota', 'SS Valparaíso - San Antonio', 'SS Aconcagua',
    'SS Metropolitano Norte', 'SS Metropolitano Occidente',
    'SS Metropolitano Central', 'SS Metropolitano Oriente',
    'SS Metropolitano Sur', 'SS Metropolitano Sur Oriente',
    "SS O'Higgins", 'SS Maule', 'SS Ñuble',
    'SS Concepción', 'SS Arauco', 'SS Talcahuano', 'SS Biobío',
    'SS Araucanía Norte', 'SS Araucanía Sur',
    'SS Los Ríos', 'SS Osorno', 'SS Del Reloncaví', 'SS Chiloé',
    'SS Aysén', 'SS Magallanes',
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trimestre", "-t",
        help="Limitar el reporte al trimestre especificado (ej: 2024_T3). "
             "Las transformaciones siempre aplican a toda la tabla.",
        default=None,
    )
    return parser.parse_args()


def split_statements(sql: str) -> list:
    """
    Divide el contenido de un archivo SQL en sentencias individuales.
    Ignora líneas de solo comentarios y sentencias vacías.
    """
    raw_statements = sql.split(";")
    statements = []
    for stmt in raw_statements:
        clean = stmt.strip()
        non_comment = "\n".join(
            line for line in clean.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ).strip()
        if non_comment:
            statements.append(clean)
    return statements


def execute_sql_file(conn, filepath: Path) -> dict:
    """
    Ejecuta todas las sentencias DML de un archivo SQL dentro de una
    transacción. Retorna estadísticas de ejecución.
    Los SELECT de diagnóstico (sin rowcount > 0) se ejecutan pero
    sus resultados se descartan — están pensados como referencia, no como log.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Archivo SQL no encontrado: {filepath}")

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    statements = split_statements(content)
    total_affected = 0
    executed = 0

    with conn.cursor() as cur:
        for stmt in statements:
            try:
                cur.execute(stmt)
                if cur.rowcount and cur.rowcount > 0:
                    total_affected += cur.rowcount
                executed += 1
            except psycopg2.Error as e:
                raise RuntimeError(
                    f"Error en sentencia #{executed + 1} de {filepath.name}:\n"
                    f"{stmt[:200]}...\n"
                    f"Error PostgreSQL: {e}"
                ) from e

    return {
        "archivo":         filepath.name,
        "sentencias":      executed,
        "filas_afectadas": total_affected,
    }


def log_pipeline_run(conn, archivo: str, trimestre: str, estado: str,
                     filas: int = 0, detalle: str = None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_runs
                (archivo, trimestre, tabla_destino, filas_procesadas,
                 filas_insertadas, filas_actualizadas, filas_omitidas,
                 estado, detalle)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            archivo,
            trimestre or "ALL",
            "transformation",
            filas, 0, filas, 0,
            estado,
            detalle,
        ))


def print_post_transform_report(conn, trimestre):
    """
    Muestra un resumen del estado de los datos tras las transformaciones.
    """
    log.info("")
    log.info("── Resumen post-transformación")

    wh      = "WHERE trimestre = %s" if trimestre else ""
    wh_and  = "AND trimestre = %s"   if trimestre else ""
    params  = [trimestre] if trimestre else []

    # Construir cláusula IN con el catálogo canónico
    placeholders = ", ".join(["%s"] * len(SS_CANONICOS))
    ss_list = list(SS_CANONICOS)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # ss_id sin reconocer
        cur.execute(f"""
            SELECT COUNT(DISTINCT ss_id) AS ss_no_reconocidos
            FROM listas_espera_ss_trimestre
            WHERE ss_id NOT IN ({placeholders})
            {wh_and}
        """, ss_list + params)
        ss_issues = cur.fetchone()["ss_no_reconocidos"]

        # Alertas activas
        cur.execute(f"""
            SELECT COUNT(*) AS alertas
            FROM listas_espera_ss_trimestre
            WHERE observaciones LIKE '%ALERTA%'
            {wh_and}
        """, params)
        alertas = cur.fetchone()["alertas"]

        # Completitud de asimetria
        cur.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE promedio_dias IS NOT NULL
                                   AND mediana_dias IS NOT NULL
                                   AND asimetria IS NULL) AS asimetria_faltante,
                COUNT(*) AS total
            FROM listas_espera_ss_trimestre
            {wh}
        """, params)
        row = cur.fetchone()

    scope = f"trimestre {trimestre}" if trimestre else "toda la base"
    log.info(f"  Alcance              : {scope}")
    log.info(f"  ss_id sin normalizar : {ss_issues}  "
             f"{'✓' if ss_issues == 0 else '⚠  (ver normalize_services.sql)'}")
    log.info(f"  Alertas activas      : {alertas}  "
             f"{'✓' if alertas == 0 else '⚠  (revisar columna observaciones)'}")
    log.info(f"  Asimetría faltante   : {row['asimetria_faltante']} de {row['total']} filas  "
             f"{'✓' if row['asimetria_faltante'] == 0 else '(mediana o promedio sin dato en esos registros)'}")


# ── Orquestador ────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    trimestre = args.trimestre

    if trimestre and not re.match(r'^\d{4}_T[1-4]$', trimestre):
        log.error(f"Formato inválido: '{trimestre}'. Ejemplo: 2024_T3")
        sys.exit(1)

    log.info("=" * 62)
    log.info("  Transformaciones — Listas de Espera NO GES")
    log.info(f"  Alcance: {'TODOS LOS TRIMESTRES' if not trimestre else trimestre}")
    log.info("=" * 62)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    has_errors = False

    try:
        for sql_file in TRANSFORMATIONS:
            log.info(f"\n── {sql_file.name}")

            try:
                result = execute_sql_file(conn, sql_file)
                conn.commit()

                log.info(f"  ✓ {result['sentencias']} sentencias ejecutadas "
                         f"| {result['filas_afectadas']} filas afectadas")

                log_pipeline_run(conn, sql_file.name, trimestre, "ok",
                                 filas=result["filas_afectadas"])
                conn.commit()

            except (FileNotFoundError, RuntimeError) as e:
                conn.rollback()
                log.error(f"  ✗ {e}")
                log_pipeline_run(conn, sql_file.name, trimestre,
                                 "error", detalle=str(e))
                conn.commit()
                has_errors = True
                if "normalize_services" in sql_file.name:
                    log.error("  Deteniendo pipeline: normalize_services es prerequisito.")
                    break

        if not has_errors:
            print_post_transform_report(conn, trimestre)
            conn.commit()

    except Exception as e:
        conn.rollback()
        log.error(f"Error crítico no manejado: {e}")
        raise
    finally:
        conn.close()

    log.info("")
    log.info("=" * 62)
    if has_errors:
        log.error("  Transformaciones completadas CON ERRORES ✗")
        log.error("  Revisar pipeline/logs/transformaciones.log")
    else:
        log.info("  Transformaciones completadas correctamente ✓")
    log.info("=" * 62)

    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()