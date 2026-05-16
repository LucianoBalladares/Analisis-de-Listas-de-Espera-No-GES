"""
Ejecuta las transformaciones SQL sobre la base de datos en el orden correcto.

Uso:
    python pipeline/transform/run_transformations.py
    python pipeline/transform/run_transformations.py --trimestre 2024_T3

Orden de ejecución:
    0.  catalog_normalization        → normalización exacta desde SS_ID_MAP (catalogos.py)
    0b. _ss_canonicos (temp table)   → tabla temporal con SS_CANONICOS para normalize_services.sql
    1.  normalize_services.sql       → normalización parcial ILIKE (fallback)
    2.  clean_waitlists.sql          → corrige métricas y marca alertas

Cada paso se ejecuta en su propia transacción. Si un paso crítico falla,
los siguientes no se ejecutan y se registra el error en pipeline_runs.

"""

import os
import re
import sys
import logging
from pathlib import Path
from argparse import ArgumentParser

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from pipeline.config.catalogos import SS_CANONICOS, SS_ID_MAP

load_dotenv()

LOG_DIR = _ROOT / "pipeline" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "transformaciones.log", encoding="utf-8"),
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

SQL_DIR = _ROOT / "sql" / "transformations"
TRANSFORMATIONS = [
    SQL_DIR / "normalize_services.sql",
    SQL_DIR / "clean_waitlists.sql",
]


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
    Divide un string SQL en sentencias individuales, manejando correctamente:
      - Comentarios de línea (--)
      - Comentarios de bloque (/* ... */)
      - Literales de texto (' y " con escape por duplicación)
      - Dollar-quoting de PostgreSQL ($$...$$ o $tag$...$tag$)
      - Punto y coma como separador de sentencias
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]

        if ch == '/' and i + 1 < n and sql[i + 1] == '*':
            buf.append(ch); buf.append(sql[i + 1]); i += 2
            while i < n:
                if sql[i] == '*' and i + 1 < n and sql[i + 1] == '/':
                    buf.append(sql[i]); buf.append(sql[i + 1]); i += 2; break
                buf.append(sql[i]); i += 1
            continue

        if ch == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                buf.append(sql[i]); i += 1
            continue

        if ch == '$':
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            if j < n and sql[j] == '$':
                tag = sql[i:j + 1]
                buf.append(tag); i = j + 1
                while i < n:
                    if sql[i:i + len(tag)] == tag:
                        buf.append(tag); i += len(tag); break
                    buf.append(sql[i]); i += 1
                continue
            buf.append(ch); i += 1; continue

        if ch in ("'", '"'):
            q = ch; buf.append(ch); i += 1
            while i < n:
                c2 = sql[i]; buf.append(c2); i += 1
                if c2 == q:
                    if i < n and sql[i] == q:
                        buf.append(sql[i]); i += 1
                    else:
                        break
            continue

        if ch == ';':
            stmt = ''.join(buf).strip()
            meaningful = '\n'.join(
                ln for ln in stmt.splitlines()
                if ln.strip() and not ln.strip().startswith('--')
            ).strip()
            if meaningful:
                statements.append(stmt)
            buf = []; i += 1; continue

        buf.append(ch); i += 1

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
    Ejecuta todas las sentencias de un archivo SQL dentro de una transacción.
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

                if cur.description is not None:
                    rows = cur.fetchall()
                    if rows:
                        col_names = [d[0] for d in cur.description]
                        log.info(f"    ── Reporte SQL [{filepath.name}]:")
                        for row in rows:
                            log.info(
                                "    " + "  ".join(
                                    f"{col}={val}" for col, val in zip(col_names, row)
                                )
                            )
                elif cur.rowcount is not None and cur.rowcount > 0:
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


# ── Paso 0b: Tabla temporal _ss_canonicos ─────────────────────────────────────

def create_canonical_temp_table(conn) -> dict:
    """
    Crea la tabla temporal de sesión _ss_canonicos con los nombres canónicos
    de SS_CANONICOS en catalogos.py.

    PostgreSQL mantiene las tablas temporales durante toda la sesión, no
    solo durante la transacción activa. La tabla persiste tras el COMMIT
    de este paso y está disponible cuando normalize_services.sql se ejecuta
    en su propia transacción a continuación.
    CREATE TEMP TABLE IF NOT EXISTS garantiza idempotencia dentro de la sesión.
    """
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS _ss_canonicos (
                ss_id TEXT PRIMARY KEY
            )
        """)
        cur.execute("TRUNCATE _ss_canonicos")
        execute_values(
            cur,
            "INSERT INTO _ss_canonicos (ss_id) VALUES %s",
            [(ss,) for ss in SS_CANONICOS],
        )

    return {
        "archivo":         "create_canonical_temp_table (SS_CANONICOS de catalogos.py)",
        "sentencias":      3,
        "filas_afectadas": len(SS_CANONICOS),
    }


# ── Paso 0: Normalización exacta desde catálogo ────────────────────────────────

def execute_catalog_normalization(conn) -> dict:
    """
    Normaliza ss_id usando SS_ID_MAP de catalogos.py como única fuente
    de verdad, ejecutando un único UPDATE con JOIN contra una tabla temporal
    de mapeo en lugar de N×4 sentencias individuales.

    Variantes de prefijo generadas por cada clave de SS_ID_MAP:
        raw_key                        (ej: 'arica')
        'ss ' + raw_key                (ej: 'ss arica')
        's.s. ' + raw_key              (ej: 's.s. arica')
        'servicio de salud ' + raw_key (ej: 'servicio de salud arica')

    ON CONFLICT DO NOTHING en el INSERT maneja colisiones cuando una clave
    ya existe con prefijo explícito en SS_ID_MAP (ej: 'ss arica' es clave
    directa y también se genera como 'ss ' + 'arica').
    """
    # Construir todas las variantes (raw → canonical)
    all_variants: list[tuple[str, str]] = []
    for raw_key, canonical in SS_ID_MAP.items():
        for prefix in ("", "ss ", "s.s. ", "servicio de salud "):
            all_variants.append((f"{prefix}{raw_key}", canonical))

    with conn.cursor() as cur:
        # Tabla temporal de mapeo (persiste durante la sesión)
        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS _ss_norm_map (
                raw       TEXT PRIMARY KEY,
                canonical TEXT NOT NULL
            )
        """)
        cur.execute("TRUNCATE _ss_norm_map")
        execute_values(
            cur,
            "INSERT INTO _ss_norm_map (raw, canonical) VALUES %s ON CONFLICT DO NOTHING",
            all_variants,
        )

        # UPDATE único con JOIN: solo toca filas que necesitan normalización
        cur.execute("""
            UPDATE listas_espera_ss_trimestre l
            SET ss_id = m.canonical,
                observaciones = COALESCE(l.observaciones || ' | ', '') ||
                                'ss_id normalizado (catálogo): ' || l.ss_id || ' → ' || m.canonical,
                updated_at    = NOW()
            FROM _ss_norm_map m
            WHERE LOWER(TRIM(l.ss_id)) = m.raw
              AND l.ss_id <> m.canonical
        """)
        total_affected = cur.rowcount

    return {
        "archivo":         "catalog_normalization (catalogos.py → SS_ID_MAP)",
        "sentencias":      3,
        "filas_afectadas": total_affected,
    }


# ── Pipeline logging ───────────────────────────────────────────────────────────

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

    wh     = "WHERE trimestre = %s" if trimestre else ""
    wh_and = "AND trimestre = %s"   if trimestre else ""
    params = [trimestre] if trimestre else []

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
                                   AND mediana_dias  IS NOT NULL
                                   AND asimetria     IS NULL) AS asimetria_faltante,
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
             f"{'✓' if row['asimetria_faltante'] == 0 else '(mediana o promedio sin dato)'}")


# ── Orquestador ────────────────────────────────────────────────────────────────

def _run_step(label: str, fn, conn, trimestre) -> bool:
    """
    Ejecuta un paso (función Python), hace commit en éxito y
    registra en pipeline_runs. Devuelve True si tuvo éxito.
    """
    log.info(f"\n── {label}")
    try:
        result = fn(conn)
        conn.commit()
        log.info(
            f"  ✓ {result['sentencias']} sentencias | "
            f"{result['filas_afectadas']} filas afectadas"
        )
        try:
            log_pipeline_run(conn, result["archivo"], trimestre, "ok",
                             filas=result["filas_afectadas"])
            conn.commit()
        except Exception as log_err:
            log.warning(f"  No se pudo registrar en pipeline_runs: {log_err}")
            conn.rollback()
        return True

    except (FileNotFoundError, RuntimeError, Exception) as e:
        conn.rollback()
        log.error(f"  ✗ {e}")
        try:
            log_pipeline_run(conn, str(label), trimestre, "error", detalle=str(e)[:500])
            conn.commit()
        except Exception:
            conn.rollback()
        return False


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
        # ── Paso 0: Normalización exacta desde SS_ID_MAP (catalogos.py) ───────
        step_ok = _run_step(
            "0 — catalog_normalization (SS_ID_MAP de catalogos.py)",
            execute_catalog_normalization,
            conn, trimestre,
        )
        if not step_ok:
            log.error("  Deteniendo pipeline: la normalización de catálogo es prerequisito.")
            has_errors = True

        # ── Paso 0b: Tabla temporal _ss_canonicos ─────────────────────────────
        if not has_errors:
            step_ok = _run_step(
                "0b — temp table _ss_canonicos (SS_CANONICOS de catalogos.py)",
                create_canonical_temp_table,
                conn, trimestre,
            )
            if not step_ok:
                log.error(
                    "  Deteniendo: _ss_canonicos es prerequisito de normalize_services.sql."
                )
                has_errors = True

        # ── Pasos SQL (solo si pasos 0 y 0b fueron exitosos) ─────────────────
        if not has_errors:
            for sql_file in TRANSFORMATIONS:
                step_ok = _run_step(
                    sql_file.name,
                    lambda c, f=sql_file: execute_sql_file(c, f),
                    conn, trimestre,
                )
                if not step_ok:
                    has_errors = True
                    if "normalize_services" in sql_file.name:
                        log.error(
                            "  Deteniendo: normalize_services.sql es prerequisito "
                            "de clean_waitlists.sql."
                        )
                        break

        # ── Reporte final ─────────────────────────────────────────────────────
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
        log.error(f"  Revisar {LOG_DIR / 'transformaciones.log'}")
    else:
        log.info("  Transformaciones completadas correctamente ✓")
    log.info("=" * 62)

    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()