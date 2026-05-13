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

# ── Ruta raíz del proyecto en sys.path (necesario para importar catalogos) ──
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from pipeline.config.catalogos import SS_CANONICOS  # M1: import centralizado

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

SQL_DIR = Path("sql/transformations")
TRANSFORMATIONS = [
    SQL_DIR / "normalize_services.sql",
    SQL_DIR / "clean_waitlists.sql",
]

# M1: SS_CANONICOS importado desde pipeline.config.catalogos

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


def split_statements(sql: str) -> list[str]:
    """
    M4: Divide SQL en sentencias individuales respetando literales de texto.

    La versión anterior usaba sql.split(';') a ciegas, lo que rompería
    ante cualquier literal de string que contuviera un punto y coma
    (ej: mensajes de error, URLs, etc.).

    Esta implementación recorre el SQL caracter a caracter y respeta:
      - Literales de comilla simple ('...')  con escape por duplicación ('')
      - Literales de comilla doble ("...")  con escape por duplicación ("")
      - Comentarios de línea (--)

    No soporta dollar-quoting ($$ ... $$) ya que no se usa en este proyecto.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]

        # Comentario de línea: avanzar hasta fin de línea (sin agregar al buffer)
        if ch == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                buf.append(sql[i])
                i += 1
            continue

        # Literal de texto (comilla simple o doble)
        if ch in ("'", '"'):
            q = ch
            buf.append(ch)
            i += 1
            while i < n:
                c2 = sql[i]
                buf.append(c2)
                i += 1
                if c2 == q:
                    # Comilla duplicada = escape dentro del literal
                    if i < n and sql[i] == q:
                        buf.append(sql[i])
                        i += 1
                    else:
                        break  # fin del literal
            continue

        # Separador de sentencia
        if ch == ';':
            stmt = ''.join(buf).strip()
            meaningful = '\n'.join(
                ln for ln in stmt.splitlines()
                if ln.strip() and not ln.strip().startswith('--')
            ).strip()
            if meaningful:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    # Última sentencia (puede no tener ';' final)
    stmt = ''.join(buf).strip()
    meaningful = '\n'.join(
        ln for ln in stmt.splitlines()
        if ln.strip() and not ln.strip().startswith('--')
    ).strip()
    if meaningful:
        statements.append(stmt)

    return statements


def execute_sql_file(conn, filepath: Path) -> dict:
    """
    Ejecuta todas las sentencias DML de un archivo SQL dentro de una
    transacción. Retorna estadísticas de ejecución.
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
    log.info("")
    log.info("── Resumen post-transformación")

    wh      = "WHERE trimestre = %s" if trimestre else ""
    wh_and  = "AND trimestre = %s"   if trimestre else ""
    params  = [trimestre] if trimestre else []

    placeholders = ", ".join(["%s"] * len(SS_CANONICOS))
    ss_list = list(SS_CANONICOS)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"""
            SELECT COUNT(DISTINCT ss_id) AS ss_no_reconocidos
            FROM listas_espera_ss_trimestre
            WHERE ss_id NOT IN ({placeholders})
            {wh_and}
        """, ss_list + params)
        ss_issues = cur.fetchone()["ss_no_reconocidos"]

        cur.execute(f"""
            SELECT COUNT(*) AS alertas
            FROM listas_espera_ss_trimestre
            WHERE observaciones LIKE '%ALERTA%'
            {wh_and}
        """, params)
        alertas = cur.fetchone()["alertas"]

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