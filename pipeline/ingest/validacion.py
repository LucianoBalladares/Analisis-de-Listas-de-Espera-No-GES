"""
Validación de integridad y calidad de datos post-carga.

Genera un reporte con conteos, alertas y problemas detectados.
Retorna exit code 1 si se encuentran errores críticos.

Uso:
    python pipeline/ingest/validacion.py              # valida todos los trimestres
    python pipeline/ingest/validacion.py 2024_T3      # valida un trimestre específico
"""

import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path

# ── Ruta raíz derivada de la ubicación del script (no del CWD) ───────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from tabulate import tabulate

from pipeline.config.catalogos import SS_CANONICOS, SS_ESPECIALES, NIVELES_ATENCION

# ── Configuración ──────────────────────────────────────────────────────────────

load_dotenv()

LOG_DIR = _ROOT / "pipeline" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "validacion.log", encoding="utf-8"),
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

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def query(conn, sql: str, params=None) -> list:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def header(title: str, index: int, total: int):
    log.info("")
    log.info(f"[{index}/{total}] {title}")
    log.info("─" * 62)


def ok(msg):    log.info(f"  ✓ {msg}")
def warn(msg):  log.warning(f"  ⚠  {msg}")
def error(msg): log.error(f"  ✗ {msg}")


def fmt_table(rows: list, floatfmt=".1f") -> str:
    if not rows:
        return "  (sin resultados)"
    if not hasattr(rows[0], "keys"):
        return "  (formato de fila inesperado)"
    headers = list(rows[0].keys())
    data = [[r[h] for h in headers] for r in rows]
    return tabulate(data, headers=headers, tablefmt="simple", floatfmt=floatfmt)


def trimestre_filter(trimestre):
    if trimestre:
        return "WHERE trimestre = %s", [trimestre]
    return "", []


# ── Checks ─────────────────────────────────────────────────────────────────────

def check_cobertura_tablas(conn, trimestre) -> int:
    wh, params = trimestre_filter(trimestre)

    for tabla in ("listas_espera_ss_trimestre",
                  "personas_nacional_trimestre",
                  "nivel_atencion_trimestre"):
        rows = query(conn, f"""
            SELECT trimestre, tipo_prestacion, COUNT(*) AS filas
            FROM {tabla} {wh}
            GROUP BY trimestre, tipo_prestacion
            ORDER BY trimestre, tipo_prestacion
        """, params)
        log.info(f"\n  {tabla}:")
        log.info(fmt_table(rows))

    return 0


def check_servicios_por_trimestre(conn, trimestre) -> int:
    wh, params = trimestre_filter(trimestre)
    rows = query(conn, f"""
        SELECT trimestre, tipo_prestacion,
               COUNT(DISTINCT ss_id) FILTER (
                   WHERE ss_id NOT IN ('No definido', 'NO DEFINIDO', 'Sin asignar')
               ) AS n_ss_standard,
               COUNT(DISTINCT ss_id) FILTER (
                   WHERE ss_id IN ('No definido', 'NO DEFINIDO', 'Sin asignar')
               ) AS n_ss_especiales
        FROM listas_espera_ss_trimestre {wh}
        GROUP BY trimestre, tipo_prestacion
        ORDER BY trimestre, tipo_prestacion
    """, params)

    errors = 0
    for r in rows:
        n = r["n_ss_standard"]
        esp = r["n_ss_especiales"]
        t = f"{r['trimestre']} / {r['tipo_prestacion']}"
        sufijo = f" + {esp} entrada(s) especial(es) ('No definido')" if esp else ""
        if n == len(SS_CANONICOS):
            ok(f"{t}: {n} servicios ✓{sufijo}")
        else:
            warn(f"{t}: {n} de {len(SS_CANONICOS)} servicios esperados{sufijo}")
    return errors


def check_ss_no_estandarizados(conn, trimestre) -> int:
    wh, params = trimestre_filter(trimestre)
    rows = query(conn, f"""
        SELECT DISTINCT ss_id
        FROM listas_espera_ss_trimestre {wh}
        ORDER BY ss_id
    """, params)

    ss_encontrados = {r["ss_id"] for r in rows}
    fuera_catalogo = ss_encontrados - SS_CANONICOS - SS_ESPECIALES

    if not fuera_catalogo:
        ok(f"Todos los ss_id están en el catálogo ({len(ss_encontrados - SS_ESPECIALES)} estándar)")
        return 0

    for ss in sorted(fuera_catalogo):
        warn(f"ss_id fuera de catálogo: '{ss}' — revisar normalización")
    return len(fuera_catalogo)


def check_niveles_atencion(conn, trimestre) -> int:
    """
    Valida que los valores de nivel_atencion sean exactamente los esperados
    ('Primario', 'Secundario', 'Terciario').

    Si el OCR extrae variantes no estándar (ej: 'Alta Complejidad', 'Nivel 3'),
    el registro se carga pero NO contribuye a v_pct_nivel_terciario.
    Este check cuantifica el impacto real sobre esa vista antes de que
    afecte los análisis.
    """
    wh, params = trimestre_filter(trimestre)
    wh_and = "AND trimestre = %s" if trimestre else ""

    rows = query(conn, f"""
        SELECT DISTINCT nivel_atencion
        FROM nivel_atencion_trimestre {wh}
        ORDER BY nivel_atencion
    """, params)

    niveles_encontrados = {r["nivel_atencion"] for r in rows}
    fuera_catalogo = niveles_encontrados - NIVELES_ATENCION

    if not fuera_catalogo:
        ok(f"Todos los niveles de atención están en el catálogo: {sorted(niveles_encontrados)}")
        return 0

    # Cuantificar impacto: filas y registros de pacientes afectados
    placeholders = ", ".join(["%s"] * len(fuera_catalogo))
    params_fuera = list(fuera_catalogo)
    count_rows = query(conn, f"""
        SELECT COUNT(*)                        AS n_filas,
               COALESCE(SUM(registros_total_nivel), 0) AS registros_afectados
        FROM nivel_atencion_trimestre
        WHERE nivel_atencion IN ({placeholders})
        {wh_and}
    """, params_fuera + (params if trimestre else []))

    n_filas      = count_rows[0]["n_filas"]      if count_rows else 0
    n_registros  = count_rows[0]["registros_afectados"] if count_rows else 0

    for nivel in sorted(fuera_catalogo):
        warn(
            f"nivel_atencion fuera de catálogo: '{nivel}' — "
            "NO contribuirá a v_pct_nivel_terciario. Revisar OCR."
        )

    warn(
        f"Impacto: {n_filas} fila(s) con nivel no reconocido "
        f"({n_registros:,} registros de pacientes excluidos de v_pct_nivel_terciario). "
        "El porcentaje de nivel terciario puede estar subestimado."
    )

    return 0  # Warning, no bloquea el pipeline, pero el impacto queda registrado


def check_coherencia_antiguedad(conn, trimestre) -> int:
    """
    Valida que la suma de los tramos de antigüedad no supere los registros totales.

    reg_24a36m y reg_mayor_36m son tramos MUTUAMENTE EXCLUYENTES:
      - reg_24a36m    → registros con entre 24 y 36 meses de espera
      - reg_mayor_36m → registros con más de 36 meses de espera
    La única restricción válida es que su suma no supere registros_espera.
    """
    wh_and = "AND trimestre = %s" if trimestre else ""
    params = [trimestre] if trimestre else []

    rows = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion,
               registros_espera,
               reg_24a36m,
               reg_mayor_36m,
               (reg_24a36m + reg_mayor_36m) AS suma_tramos
        FROM listas_espera_ss_trimestre
        WHERE reg_24a36m      IS NOT NULL
          AND reg_mayor_36m   IS NOT NULL
          AND registros_espera IS NOT NULL
          AND (reg_24a36m + reg_mayor_36m) > registros_espera
          {wh_and}
        ORDER BY trimestre, ss_id
    """, params)

    if not rows:
        ok("Suma de tramos de antigüedad no supera registros_espera en ningún registro")
        return 0

    error(f"{len(rows)} fila(s) donde reg_24a36m + reg_mayor_36m > registros_espera:")
    log.error(fmt_table(rows))
    return len(rows)


def check_asimetria(conn, trimestre) -> int:
    wh_and = "AND trimestre = %s" if trimestre else ""
    params = [trimestre] if trimestre else []

    rows = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion,
               promedio_dias, mediana_dias,
               asimetria AS asimetria_guardada,
               ROUND(promedio_dias - mediana_dias, 1) AS asimetria_esperada
        FROM listas_espera_ss_trimestre
        WHERE promedio_dias IS NOT NULL
          AND mediana_dias IS NOT NULL
          AND asimetria IS NOT NULL
          AND ABS(asimetria - ROUND(promedio_dias - mediana_dias, 1)) > 0.5
          {wh_and}
        ORDER BY trimestre, ss_id
    """, params)

    if not rows:
        ok("Columna asimetria consistente con promedio - mediana")
        return 0

    warn(f"{len(rows)} fila(s) con asimetría inconsistente (diferencia > 0.5 días):")
    log.warning(fmt_table(rows))
    return 0


def check_outliers(conn, trimestre) -> int:
    wh_and = "AND trimestre = %s" if trimestre else ""
    params = [trimestre] if trimestre else []

    rows_mediana = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion, mediana_dias
        FROM listas_espera_ss_trimestre
        WHERE (mediana_dias < 0 OR mediana_dias > 3650)
          {wh_and}
        ORDER BY mediana_dias DESC
    """, params)

    rows_neg = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion,
               personas_espera, registros_espera
        FROM listas_espera_ss_trimestre
        WHERE (personas_espera < 0 OR registros_espera < 0)
          {wh_and}
    """, params)

    errors = 0
    if rows_mediana:
        warn(f"{len(rows_mediana)} fila(s) con mediana fuera de rango (< 0 o > 3650 días):")
        log.warning(fmt_table(rows_mediana))
        errors += len(rows_mediana)
    else:
        ok("Medianas dentro de rango razonable (0–3650 días)")

    if rows_neg:
        error(f"{len(rows_neg)} fila(s) con conteos negativos:")
        log.error(fmt_table(rows_neg))
        errors += len(rows_neg)
    else:
        ok("Sin conteos negativos")

    return errors


def check_nulos_criticos(conn, trimestre) -> int:
    wh, params = trimestre_filter(trimestre)

    rows = query(conn, f"""
        SELECT trimestre, tipo_prestacion,
               COUNT(*) FILTER (WHERE mediana_dias IS NULL)     AS sin_mediana,
               COUNT(*) FILTER (WHERE personas_espera IS NULL)  AS sin_personas,
               COUNT(*) FILTER (WHERE registros_espera IS NULL) AS sin_registros,
               COUNT(*) AS total_filas
        FROM listas_espera_ss_trimestre {wh}
        GROUP BY trimestre, tipo_prestacion
        ORDER BY trimestre, tipo_prestacion
    """, params)

    log.info(fmt_table(rows))
    ok("Nulos esperados documentados en docs/limitaciones.md")
    return 0


def check_pipeline_runs(conn, trimestre) -> int:
    wh, params = trimestre_filter(trimestre)
    rows = query(conn, f"""
        SELECT run_at::date AS fecha,
               archivo,
               tabla_destino,
               filas_insertadas,
               filas_omitidas,
               estado
        FROM pipeline_runs
        {wh}
        ORDER BY run_at DESC
        LIMIT 20
    """, params)

    if not rows:
        warn("Sin registros en pipeline_runs")
        return 0

    log.info(fmt_table(rows))
    errores = sum(1 for r in rows if r["estado"] == "error")
    if errores:
        warn(f"{errores} ejecución(es) con estado 'error' en el historial reciente")
    else:
        ok("Sin errores en el historial reciente")
    return 0


# ── Orquestador ────────────────────────────────────────────────────────────────

CHECKS = [
    ("Cobertura de tablas por trimestre y tipo",        check_cobertura_tablas,        "info"),
    ("Servicios de Salud por trimestre",                check_servicios_por_trimestre,  "warning"),
    ("ss_id fuera del catálogo estándar",               check_ss_no_estandarizados,     "warning"),
    ("Niveles de atención fuera del catálogo",          check_niveles_atencion,         "warning"),
    ("Coherencia de tramos de antigüedad",              check_coherencia_antiguedad,    "error"),
    ("Consistencia de columna asimetria",               check_asimetria,                "warning"),
    ("Outliers en valores numéricos",                   check_outliers,                 "warning"),
    ("Nulos por trimestre (completitud esperada)",      check_nulos_criticos,           "info"),
    ("Historial de ejecuciones del pipeline",           check_pipeline_runs,            "info"),
]


def main(trimestre=None):
    if trimestre and not re.match(r'^\d{4}_T[1-4]$', trimestre):
        log.error(f"Formato de trimestre inválido: '{trimestre}'. Ejemplo válido: 2024_T3")
        sys.exit(1)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scope = trimestre if trimestre else "TODOS LOS TRIMESTRES"

    log.info("═" * 62)
    log.info("  REPORTE DE VALIDACIÓN — Listas de Espera NO GES")
    log.info(f"  Ejecutado : {now}")
    log.info(f"  Alcance   : {scope}")
    log.info("═" * 62)

    conn = get_conn()
    total_errors = 0

    try:
        for i, (title, fn, severity) in enumerate(CHECKS, 1):
            header(title, i, len(CHECKS))
            try:
                n_issues = fn(conn, trimestre)
                if n_issues and severity == "error":
                    total_errors += n_issues
            except Exception as e:
                error(f"Error ejecutando el check: {e}")
                total_errors += 1
    finally:
        conn.close()

    log.info("")
    log.info("═" * 62)
    if total_errors == 0:
        log.info("  RESULTADO: OK — sin errores críticos detectados ✓")
    else:
        log.error(f"  RESULTADO: {total_errors} error(es) crítico(s) detectado(s) ✗")
        log.error("  Revisar los registros marcados antes de continuar con el análisis.")
    log.info("═" * 62)

    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    trimestre_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(trimestre_arg)