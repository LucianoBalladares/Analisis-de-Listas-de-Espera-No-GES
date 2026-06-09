"""
Orquestador del pipeline completo para un archivo Excel trimestral.

Encadena los tres pasos en el orden correcto y detiene la ejecución
si cualquier paso falla con errores críticos:

    1. Ingesta    → excel_a_sql.py      (carga UPSERT en PostgreSQL)
    2. Validación → validacion.py       (10 checks de integridad)
    3. Transform  → run_transformations.py  (normalización + limpieza SQL)

Uso:
    python pipeline/orchestration/pipeline_runner.py <ruta/al/archivo.xlsx>
    python pipeline/orchestration/pipeline_runner.py data/staging/2024_T4.xlsx

    # Solo ingesta + validación (omitir transformaciones):
    python pipeline/orchestration/pipeline_runner.py 2024_T4.xlsx --skip-transform

    # Forzar continuar aunque la validación encuentre errores críticos:
    python pipeline/orchestration/pipeline_runner.py 2024_T4.xlsx --force

Salida:
    - Exit code 0 → pipeline completado sin errores críticos
    - Exit code 1 → al menos un paso terminó con errores

Logs individuales por módulo:
    pipeline/logs/ingesta.log
    pipeline/logs/validacion.log
    pipeline/logs/transformaciones.log

Log consolidado del orquestador:
    pipeline/logs/pipeline_runner.log
"""

import re
import sys
import logging
import subprocess
from argparse import ArgumentParser
from pathlib import Path

# ── Ruta raíz derivada de la ubicación del script (no del CWD) ───────────────
_ROOT = Path(__file__).resolve().parent.parent.parent

LOG_DIR = _ROOT / "pipeline" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "pipeline_runner.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# Rutas absolutas a los módulos del pipeline
INGEST_SCRIPT     = _ROOT / "pipeline" / "ingest"         / "excel_a_sql.py"
VALIDATE_SCRIPT   = _ROOT / "pipeline" / "ingest"         / "validacion.py"
TRANSFORM_SCRIPT  = _ROOT / "pipeline" / "transform"      / "run_transformations.py"

STEP_TIMEOUT_SECONDS = 3600  # 1 hora


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "excel",
        help="Ruta al archivo Excel trimestral (ej: data/staging/2024_T4.xlsx)",
    )
    parser.add_argument(
        "--skip-transform",
        action="store_true",
        default=False,
        help="Omitir el paso de transformaciones SQL (solo ingesta + validación)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Continuar con transformaciones aunque la validación reporte errores críticos",
    )
    return parser.parse_args()


def extract_trimestre(filepath: Path) -> str:
    """Extrae YYYY_T# del nombre del archivo."""
    match = re.search(r'(\d{4}_T[1-4])', filepath.stem, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"No se pudo determinar el trimestre desde '{filepath.name}'. "
            "El nombre debe contener un patrón como '2024_T1'."
        )
    return match.group(1).upper()


def run_step(label: str, cmd: list) -> int:
    """
    Ejecuta un subproceso y retorna su exit code.
    Muestra la salida en tiempo real usando el mismo stdout/stderr del proceso padre
    """
    log.info(f"  Ejecutando: {' '.join(str(c) for c in cmd)}")
    try:
        result = subprocess.run(
            [sys.executable] + [str(c) for c in cmd],
            timeout=STEP_TIMEOUT_SECONDS,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        log.error(
            f"  ✗ Timeout: el paso '{label}' superó {STEP_TIMEOUT_SECONDS}s y fue cancelado. "
            "Verificar conexión a la BD o integridad del archivo de entrada."
        )
        return 1


def separator(title: str = ""):
    line = "═" * 62
    if title:
        log.info(line)
        log.info(f"  {title}")
        log.info(line)
    else:
        log.info(line)


# ── Orquestador ────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    excel_path = Path(args.excel)

    # ── Validaciones previas ───────────────────────────────────────────────────
    if not excel_path.exists():
        log.error(f"Archivo no encontrado: {excel_path}")
        sys.exit(1)

    try:
        trimestre = extract_trimestre(excel_path)
    except ValueError as e:
        log.error(str(e))
        sys.exit(1)

    for script in (INGEST_SCRIPT, VALIDATE_SCRIPT, TRANSFORM_SCRIPT):
        if not script.exists():
            log.error(
                f"Script no encontrado: {script}\n"
                f"  Raíz del proyecto detectada: {_ROOT}\n"
                "  Verifica que la estructura del repositorio es la esperada."
            )
            sys.exit(1)

    # ── Cabecera ───────────────────────────────────────────────────────────────
    separator(f"Pipeline — Listas de Espera NO GES")
    log.info(f"  Archivo   : {excel_path.name}")
    log.info(f"  Trimestre : {trimestre}")
    log.info(f"  Transform : {'OMITIDO (--skip-transform)' if args.skip_transform else 'SÍ'}")
    separator()

    resultados = {}

    # ── Paso 1: Ingesta ────────────────────────────────────────────────────────
    separator("PASO 1 / 3 — Ingesta (excel_a_sql.py)")
    rc_ingesta = run_step("ingesta", [INGEST_SCRIPT, excel_path])
    resultados["ingesta"] = rc_ingesta

    if rc_ingesta != 0:
        log.error("  ✗ La ingesta falló con errores críticos.")
        log.error(f"  Pipeline detenido. Revisar {LOG_DIR / 'ingesta.log'}")
        _resumen(resultados, trimestre)
        sys.exit(1)

    log.info("  ✓ Ingesta completada")

    # ── Paso 2: Validación ─────────────────────────────────────────────────────
    separator("PASO 2 / 3 — Validación (validacion.py)")
    rc_validacion = run_step("validación", [VALIDATE_SCRIPT, trimestre])
    resultados["validacion"] = rc_validacion

    if rc_validacion != 0:
        if args.force:
            log.warning("  ⚠  La validación reportó errores críticos.")
            log.warning("  Continuando con --force (no recomendado en producción).")
        else:
            log.error("  ✗ La validación reportó errores críticos.")
            log.error("  Usa --force para continuar de todas formas.")
            log.error(f"  Revisar {LOG_DIR / 'validacion.log'}")
            _resumen(resultados, trimestre)
            sys.exit(1)
    else:
        log.info("  ✓ Validación completada sin errores críticos")

    # ── Paso 3: Transformaciones ───────────────────────────────────────────────
    if args.skip_transform:
        log.info("")
        log.info("  [omitido por --skip-transform]")
        resultados["transformaciones"] = None
    else:
        separator("PASO 3 / 3 — Transformaciones (run_transformations.py)")
        rc_transform = run_step(
            "transformaciones",
            [TRANSFORM_SCRIPT, "--trimestre", trimestre],
        )
        resultados["transformaciones"] = rc_transform

        if rc_transform != 0:
            log.error("  ✗ Las transformaciones finalizaron con errores.")
            log.error(f"  Revisar {LOG_DIR / 'transformaciones.log'}")
        else:
            log.info("  ✓ Transformaciones completadas correctamente")

    # ── Resumen final ──────────────────────────────────────────────────────────
    _resumen(resultados, trimestre)

    exit_code = 0 if all(v in (0, None) for v in resultados.values()) else 1
    sys.exit(exit_code)


def _resumen(resultados: dict, trimestre: str):
    separator(f"Resumen — {trimestre}")
    iconos  = {0: "✓", 1: "✗", None: "—"}
    estados = {0: "OK", 1: "ERROR", None: "OMITIDO"}
    for paso, rc in resultados.items():
        icono  = iconos.get(rc if rc in (0, None) else 1, "✗")
        estado = estados.get(rc if rc in (0, None) else 1, "ERROR")
        log.info(f"  {icono} {paso:<20} {estado}")
    separator()


if __name__ == "__main__":
    main()