"""
Ejecuta las transformaciones SQL sobre la base de datos en el orden correcto.

Uso:
    python pipeline/transform/run_transformations.py
    python pipeline/transform/run_transformations.py --trimestre 2024_T3

Orden de ejecución:
    0. catalog_normalization   → normalización exacta desde SS_ID_MAP (catalogos.py)
    1. normalize_services.sql  → normalización parcial ILIKE (fallback)
    2. clean_waitlists.sql     → corrige métricas y marca alertas

Cada paso se ejecuta en su propia transacción. Si el paso 0 falla,
los siguientes no se ejecutan y se registra el error en pipeline_runs.
"""

import os
import re
import sys
import logging
from pathlib import Path
from argparse import ArgumentParser

# ── Ruta raíz derivada de la ubicación del script (no del CWD) ───────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from pipeline.config.catalogos import SS_CANONICOS, SS_ID_MAP

# ── Configuración ──────────────────────────────────────────────────────────────

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

        # ── Comentario de bloque /* ... */ ────────────────────────────────────
        if ch == '/' and i + 1 < n and sql[i + 1] == '*':
            buf.append(ch)
            buf.append(sql[i + 1])
            i += 2
            while i < n:
                if sql[i] == '*' and i + 1 < n and sql[i + 1] == '/':
                    buf.append(sql[i])
                    buf.append(sql[i + 1])
                    i += 2
                    break
                buf.append(sql[i])
                i += 1
            continue

        # ── Comentario de línea -- ────────────────────────────────────────────
        if ch == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                buf.append(sql[i])
                i += 1
            continue

        # ── Dollar-quoting $tag$...$tag$ ──────────────────────────────────────
        if ch == '$':
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            if j < n and sql[j] == '$':
                tag = sql[i:j + 1]      # ej: '$$' o '$body$'
                buf.append(tag)
                i = j + 1
                while i < n:            # buscar cierre del mismo tag
                    if sql[i:i + len(tag)] == tag:
                        buf.append(tag)
                        i += len(tag)
                        break
                    buf.append(sql[i])
                    i += 1
                continue
            # No era dollar-quoting: tratar '$' como carácter normal
            buf.append(ch)
            i += 1
            continue

        # ── Literal de texto ' o " ────────────────────────────────────────────
        if ch in ("'", '"'):
            q = ch
            buf.append(ch)
            i += 1
            while i < n:
                c2 = sql[i]
                buf.append(c2)
                i += 1
                if c2 == q:
                    if i < n and sql[i] == q:   # comilla duplicada = escape
                        buf.append(sql[i])
                        i += 1
                    else:
                        break
            continue

        # ── Separador de sentencia ────────────────────────────────────────────
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

    # Última sentencia sin ';' final
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


# ── Normalización desde catálogo (única fuente de verdad) ─────────────────

def execute_catalog_normalization(conn) -> dict:
    """
    Normaliza ss_id usando SS_ID_MAP de catalogos.py como única fuente
    de verdad, reemplazando la tabla de correcciones exactas (CTE) que
    antes estaba hardcodeada en normalize_services.sql.

    Para cada (raw_key → canonical) de SS_ID_MAP, reconstruye las
    variantes con prefijo que podrían haber llegado a la BD si Python
    no las normalizó, y ejecuta un UPDATE case-insensitive.

    Mirrors la lógica de normalize_ss_id() en excel_a_sql.py:
      1. raw_key tal cual        (ej: "antofagasta")
      2. con prefijo "ss "       (ej: "ss antofagasta")
      3. con prefijo "s.s. "     (variante con puntos)
      4. con prefijo largo OCR   (ej: "servicio de salud antofagasta")
    """

    def build_variants(raw_key: str) -> list[str]:
        return [
            raw_key,
            f"ss {raw_key}",
            f"s.s. {raw_key}",
            f"servicio de salud {raw_key}",
        ]

    total_affected = 0
    executed = 0

    with conn.cursor() as cur:
        for raw_key, canonical in SS_ID_MAP.items():
            for variant in build_variants(raw_key):
                cur.execute("""
                    UPDATE listas_espera_ss_trimestre
                    SET ss_id = %s,
                        observaciones = COALESCE(observaciones || ' | ', '') ||
                                        'ss_id normalizado (catálogo): ' || ss_id || ' → ' || %s,
                        updated_at    = NOW()
                    WHERE LOWER(TRIM(ss_id)) = %s
                      AND ss_id <> %s
                """, (canonical, canonical, variant, canonical))

                total_affected += cur.rowcount
                executed += 1

    return {
        "archivo":         "catalog_normalization (catalogos.py → SS_ID_MAP)",
        "sentencias":      executed,
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
    Ejecuta un paso (función o archivo SQL), hace commit en éxito y
    registra en pipeline_runs. Devuelve True si tuvo éxito.
    """
    log.info(f"\n── {label}")
    try:
        result = fn(conn)
        conn.commit()
        log.info(f"  ✓ {result['sentencias']} sentencias | {result['filas_afectadas']} filas afectadas")
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
            archivo = label if isinstance(label, str) else str(label)
            log_pipeline_run(conn, archivo, trimestre, "error", detalle=str(e)[:500])
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
        ok = _run_step(
            "catalog_normalization (SS_ID_MAP de catalogos.py)",
            execute_catalog_normalization,
            conn, trimestre,
        )
        if not ok:
            log.error("  Deteniendo pipeline: la normalización de catálogo es prerequisito.")
            has_errors = True

        # ── Pasos SQL (solo si paso 0 fue exitoso) ────────────────────────────
        if not has_errors:
            for sql_file in TRANSFORMATIONS:
                ok = _run_step(
                    sql_file.name,
                    lambda c, f=sql_file: execute_sql_file(c, f),
                    conn, trimestre,
                )
                if not ok:
                    has_errors = True
                    if "normalize_services" in sql_file.name:
                        log.error("  Deteniendo: normalize_services.sql es prerequisito de clean_waitlists.sql.")
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