#!/usr/bin/env python3
"""
validacion.py
=============
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

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from tabulate import tabulate

# ── Configuración ──────────────────────────────────────────────────────────────

load_dotenv()

Path("pipeline/logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline/logs/validacion.log", encoding="utf-8"),
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


SS_ESPERADOS = {
    "SS Arica y Parinacota", 
    "SS Tarapacá", 
    "SS Antofagasta", 
    "SS Atacama", 
    "SS Coquimbo",
    "SS Valparaíso - San Antonio", 
    "SS Viña del Mar - Quillota", 
    "SS Aconcagua",
    "SS Metropolitano Norte", 
    "SS Metropolitano Occidente", 
    "SS Metropolitano Central",
    "SS Metropolitano Oriente", 
    "SS Metropolitano Sur", 
    "SS Metropolitano Sur Oriente",
    "SS O'Higgins", 
    "SS Maule", 
    "SS Ñuble", 
    "SS Concepción",
    "SS Arauco",     
    "SS Talcahuano",
    "SS Biobío", 
    "SS Araucanía Norte", 
    "SS Araucanía Sur", 
    "SS Los Ríos",   
    "SS Osorno",
    "SS Del Reloncaví", 
    "SS Chiloé", 
    "SS Aysén", 
    "SS Magallanes"
}

SS_ESPECIALES = {"No definido", "NO DEFINIDO", "Sin asignar"}

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def query(conn, sql: str, params=None) -> list[dict]:
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


def fmt_table(rows: list[dict], floatfmt=".1f") -> str:
    if not rows:
        return "  (sin resultados)"
    headers = list(rows[0].keys())
    data = [[r[h] for h in headers] for r in rows]
    return tabulate(data, headers=headers, tablefmt="simple", floatfmt=floatfmt)


def trimestre_filter(trimestre: str | None) -> tuple[str, list]:
    """Retorna cláusula WHERE y parámetros según si hay filtro de trimestre."""
    if trimestre:
        return "WHERE trimestre = %s", [trimestre]
    return "", []


# ── Checks ─────────────────────────────────────────────────────────────────────

def check_cobertura_tablas(conn, trimestre) -> int:
    """Cuántas filas hay en cada tabla, por trimestre y tipo de prestación."""
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
        if n == len(SS_ESPERADOS):
            ok(f"{t}: {n} servicios ✓{sufijo}")
        else:
            warn(f"{t}: {n} de {len(SS_ESPERADOS)} servicios esperados{sufijo}")
    return errors


def check_ss_no_estandarizados(conn, trimestre) -> int:
    wh, params = trimestre_filter(trimestre)
    rows = query(conn, f"""
        SELECT DISTINCT ss_id
        FROM listas_espera_ss_trimestre {wh}
        ORDER BY ss_id
    """, params)

    ss_encontrados = {r["ss_id"] for r in rows}
    fuera_catalogo = ss_encontrados - SS_ESPERADOS - SS_ESPECIALES  # excluir especiales

    if not fuera_catalogo:
        ok(f"Todos los ss_id están en el catálogo ({len(ss_encontrados - SS_ESPECIALES)} estándar)")
        return 0

    for ss in sorted(fuera_catalogo):
        warn(f"ss_id fuera de catálogo: '{ss}' — revisar normalización")
    return len(fuera_catalogo)


def check_coherencia_antiguedad(conn, trimestre) -> int:
    """reg_mayor_36m no puede superar reg_24a36m (los >36m son subconjunto de >24m)."""
    wh, params = trimestre_filter(trimestre)

    rows = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion,
               reg_24a36m, reg_mayor_36m
        FROM listas_espera_ss_trimestre
        WHERE reg_mayor_36m IS NOT NULL
          AND reg_24a36m IS NOT NULL
          AND reg_mayor_36m > reg_24a36m
          {('AND trimestre = %s' if trimestre else '')}
        ORDER BY trimestre, ss_id
    """, params)

    if not rows:
        ok("Sin inconsistencias en tramos de antigüedad")
        return 0

    error(f"{len(rows)} fila(s) con reg_mayor_36m > reg_24a36m:")
    log.error(fmt_table(rows))
    return len(rows)


def check_asimetria(conn, trimestre) -> int:
    """La columna asimetria debe coincidir con promedio_dias - mediana_dias."""
    wh, params = trimestre_filter(trimestre)

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
          {('AND trimestre = %s' if trimestre else '')}
        ORDER BY trimestre, ss_id
    """, params)

    if not rows:
        ok("Columna asimetria consistente con promedio - mediana")
        return 0

    warn(f"{len(rows)} fila(s) con asimetría inconsistente (diferencia > 0.5 días):")
    log.warning(fmt_table(rows))
    return 0  # warning, no error crítico


def check_outliers(conn, trimestre) -> int:
    """Detecta valores extremos que pueden indicar errores de OCR."""
    wh, params = trimestre_filter(trimestre)

    # Medianas fuera de rango razonable
    rows_mediana = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion, mediana_dias
        FROM listas_espera_ss_trimestre
        WHERE (mediana_dias < 0 OR mediana_dias > 3650)
          {('AND trimestre = %s' if trimestre else '')}
        ORDER BY mediana_dias DESC
    """, params)

    # Conteos negativos
    rows_neg = query(conn, f"""
        SELECT ss_id, trimestre, tipo_prestacion,
               personas_espera, registros_espera
        FROM listas_espera_ss_trimestre
        WHERE (personas_espera < 0 OR registros_espera < 0)
          {('AND trimestre = %s' if trimestre else '')}
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
    """Detecta nulos en columnas que deberían tener valor según el período."""
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
    return 0  # Los nulos son esperados — se reportan pero no son errores


def check_pipeline_runs(conn, trimestre) -> int:
    """Muestra el historial reciente de cargas."""
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
    ("Coherencia de tramos de antigüedad",              check_coherencia_antiguedad,    "error"),
    ("Consistencia de columna asimetria",               check_asimetria,                "warning"),
    ("Outliers en valores numéricos",                   check_outliers,                 "warning"),
    ("Nulos por trimestre (completitud esperada)",      check_nulos_criticos,           "info"),
    ("Historial de ejecuciones del pipeline",           check_pipeline_runs,            "info"),
]


def main(trimestre: str | None = None):
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