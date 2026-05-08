#!/usr/bin/env python3
"""
excel_a_sql.py
==============
Ingesta de datos desde Excel trimestral a PostgreSQL.

Uso:
    python pipeline/ingest/excel_a_sql.py <ruta/al/archivo.xlsx>
    python pipeline/ingest/excel_a_sql.py data/staging/cleaned_excels/2024_T3.xlsx

El archivo debe seguir la convención: YYYY_T#.xlsx (ej: 2024_T3.xlsx).
Puede contener hasta 3 hojas (ninguna es obligatoria):
    - listas_espera_ss_trimestre
    - personas_nacional_trimestre
    - nivel_atencion_trimestre

La carga es idempotente: re-correr el script con el mismo archivo
actualiza los registros existentes (UPSERT), nunca duplica.
"""

import os
import re
import sys
import logging
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
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
        logging.FileHandler("pipeline/logs/ingesta.log", encoding="utf-8"),
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

# Valores que representan datos no disponibles en los Excel (post-OCR)
NULL_VALUES = {
    "N/D", "ND", "NO DISPONIBLE", "S/I", "S/D", "SIN INFORMACION",
    "SIN INFORMACIÓN", "-", "—", "–", "", "NA", "N/A", ".", "..",
}

# ── Mapeo de columnas Excel → DB ───────────────────────────────────────────────
# Clave: nombre canónico en DB | Valor: variantes posibles en el Excel (lowercase)

COL_MAP_LISTAS = {
    "ss_id":             ["ss_id", "servicio de salud", "servicio", "ss"],
    "tipo_prestacion":   ["tipo_prestacion", "tipo prestacion", "tipo de prestacion", "tipo"],
    "personas_espera":   ["personas_espera", "personas espera", "personas en espera",
                          "n° personas", "nro personas", "personas"],
    "registros_espera":  ["registros_espera", "registros espera", "n° registros",
                          "nro registros", "registros"],
    "mediana_dias":      ["mediana_dias", "mediana dias", "mediana (días)",
                          "mediana (dias)", "mediana"],
    "promedio_dias":     ["promedio_dias", "promedio dias", "promedio (días)",
                          "promedio (dias)", "promedio"],
    "reg_24a36m":        ["reg_24a36m", "24 a 36m", "24-36 meses", "24 a 36 meses",
                          "registros 24-36", ">24m"],
    "reg_mayor_36m":     ["reg_mayor_36m", ">36m", "mayor 36m", ">36 meses",
                          "mayor a 36", "registros >36"],
    "fuente":            ["fuente"],
    "observaciones":     ["observaciones", "obs", "notas"],
}

COL_MAP_PERSONAS = {
    "tipo_prestacion":  ["tipo_prestacion", "tipo prestacion", "tipo de prestacion", "tipo"],
    "personas_total":   ["personas_total", "personas total", "total personas", "total"],
}

COL_MAP_NIVEL = {
    "nivel_atencion":        ["nivel_atencion", "nivel atencion", "nivel de atencion",
                              "nivel de atención", "nivel"],
    "tipo_prestacion":       ["tipo_prestacion", "tipo prestacion", "tipo de prestacion", "tipo"],
    "registros_total_nivel": ["registros_total_nivel", "registros total nivel",
                              "total registros", "registros"],
}

# ── Tablas de normalización ────────────────────────────────────────────────────

TIPO_PRESTACION_MAP = {
    "cne":                              "CNE",
    "consulta nueva de especialidad":   "CNE",
    "consulta nueva especialidad":      "CNE",
    "consulta nueva":                   "CNE",
    "iq":                               "IQ",
    "cirugia":                          "IQ",
    "cirugía":                          "IQ",
    "intervencion quirurgica":          "IQ",
    "intervención quirúrgica":          "IQ",
    "intervencion q.":                  "IQ",
    "int. quirurgica":                  "IQ",
    "int. quirúrgica":                  "IQ",
    "quirurgica":                       "IQ",
    "quirúrgica":                       "IQ",
}

# Servicios de Salud: clave en lowercase sin prefijo "ss" | valor: nombre estándar
SS_ID_MAP = {
    "arica":                        "SS Arica",
    "tarapaca":                     "SS Tarapacá",
    "tarapacá":                     "SS Tarapacá",
    "antofagasta":                  "SS Antofagasta",
    "atacama":                      "SS Atacama",
    "coquimbo":                     "SS Coquimbo",
    "viña del mar quillota":        "SS Viña del Mar - Quillota",
    "viña del mar - quillota":      "SS Viña del Mar - Quillota",
    "vina del mar quillota":        "SS Viña del Mar - Quillota",
    "valparaiso san antonio":       "SS Valparaíso - San Antonio",
    "valparaíso san antonio":       "SS Valparaíso - San Antonio",
    "valparaíso - san antonio":     "SS Valparaíso - San Antonio",
    "aconcagua":                    "SS Aconcagua",
    "metropolitano norte":          "SS Metropolitano Norte",
    "metropolitano occidente":      "SS Metropolitano Occidente",
    "metropolitano central":        "SS Metropolitano Central",
    "metropolitano oriente":        "SS Metropolitano Oriente",
    "metropolitano sur":            "SS Metropolitano Sur",
    "metropolitano sur oriente":    "SS Metropolitano Sur Oriente",
    "o'higgins":                    "SS O'Higgins",
    "ohiggins":                     "SS O'Higgins",
    "maule":                        "SS Maule",
    "ñuble":                        "SS Ñuble",
    "nuble":                        "SS Ñuble",
    "biobio":                       "SS Biobío",
    "biobío":                       "SS Biobío",
    "talcahuano":                   "SS Talcahuano",
    "araucania norte":              "SS Araucanía Norte",
    "araucanía norte":              "SS Araucanía Norte",
    "araucania sur":                "SS Araucanía Sur",
    "araucanía sur":                "SS Araucanía Sur",
    "valdivia":                     "SS Valdivia",
    "osorno":                       "SS Osorno",
    "del reloncavi":                "SS Del Reloncaví",
    "del reloncaví":                "SS Del Reloncaví",
    "reloncavi":                    "SS Del Reloncaví",
    "reloncaví":                    "SS Del Reloncaví",
    "chiloe":                       "SS Chiloé",
    "chiloé":                       "SS Chiloé",
    "aysen":                        "SS Aysén",
    "aysén":                        "SS Aysén",
    "magallanes":                   "SS Magallanes",
}

# ── Funciones auxiliares ───────────────────────────────────────────────────────

def parse_trimestre(filepath: Path) -> str:
    """
    Extrae el período del nombre del archivo.
    Acepta variantes como: 2024_T1.xlsx, datos_2024_T2_v2.xlsx
    """
    match = re.search(r'(\d{4}_T[1-4])', filepath.stem, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"No se pudo determinar el trimestre desde '{filepath.name}'. "
            "El nombre debe contener un patrón como '2024_T1'."
        )
    return match.group(1).upper()


def normalize_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """
    Renombra columnas del DataFrame usando el mapa de equivalencias.
    La comparación es case-insensitive y tolera espacios extra.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    rename = {}
    for db_col, candidates in col_map.items():
        for candidate in candidates:
            if candidate.lower() in df.columns:
                rename[candidate.lower()] = db_col
                break
    df = df.rename(columns=rename)
    # Mantener solo columnas que están en el col_map
    known_cols = list(col_map.keys())
    return df[[c for c in known_cols if c in df.columns]]


def clean_numeric(val) -> float | None:
    """
    Convierte un valor a float tolerando formatos numéricos chilenos/europeos.
    Ejemplos:
        "1.234"    → 1234.0   (punto como separador de miles)
        "1.234,5"  → 1234.5   (formato europeo)
        "1,234.5"  → 1234.5   (formato anglosajón)
        "N/D"      → None
    """
    if pd.isna(val):
        return None
    s = str(val).strip().upper()
    if s in NULL_VALUES:
        return None
    # Quitar prefijos/sufijos comunes
    s = re.sub(r'[%$]', '', s).strip()
    if not s:
        return None

    if ',' in s and '.' in s:
        # Ambos separadores → punto es miles, coma es decimal
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        parts = s.split(',')
        # Si hay ≤2 dígitos tras la coma → separador decimal
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')  # separador de miles
    # Eliminar caracteres no numéricos excepto punto y signo negativo
    s = re.sub(r'[^\d.\-]', '', s)
    if not s or s == '.':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize_tipo_prestacion(val) -> str | None:
    """Normaliza el tipo de prestación a 'CNE' o 'IQ'."""
    if pd.isna(val) or str(val).strip().upper() in NULL_VALUES:
        return None
    key = str(val).strip().lower()
    result = TIPO_PRESTACION_MAP.get(key)
    if result is None:
        log.warning(f"  tipo_prestacion no reconocido: '{val}'")
    return result


def normalize_ss_id(val) -> str | None:
    """
    Normaliza el nombre del Servicio de Salud al estándar del proyecto.
    Si no hay coincidencia exacta, intenta una búsqueda parcial.
    Si tampoco la hay, retorna el valor original (sin perder el dato).
    """
    if pd.isna(val):
        return None
    raw = str(val).strip()
    # Remover prefijo "ss " y variantes comunes del OCR
    key = re.sub(r'^s\.?\s*s\.?\s*', '', raw.lower()).strip()
    key = re.sub(r'\s+', ' ', key)  # normalizar espacios internos

    if key in SS_ID_MAP:
        return SS_ID_MAP[key]

    # Fallback: búsqueda parcial (tolerancia a OCR con caracteres extra)
    for k, v in SS_ID_MAP.items():
        if k in key or key in k:
            log.debug(f"  ss_id '{raw}' → '{v}' (coincidencia parcial)")
            return v

    log.warning(f"  ss_id no reconocido: '{raw}' — se usará el valor original")
    return raw


def read_sheet(xl: pd.ExcelFile, sheet_name: str) -> pd.DataFrame | None:
    """
    Lee una hoja del Excel con matching case-insensitive.
    Retorna None si no existe o está vacía.
    """
    sheet_map = {s.strip().lower(): s for s in xl.sheet_names}
    actual_name = sheet_map.get(sheet_name.lower())

    if actual_name is None:
        log.info(f"  Hoja '{sheet_name}' no encontrada en el archivo — se omite")
        return None

    df = xl.parse(actual_name, dtype=str)
    df = df.dropna(how="all").dropna(axis=1, how="all")

    if df.empty:
        log.warning(f"  Hoja '{sheet_name}' encontrada pero vacía — se omite")
        return None

    return df


# ── Funciones de procesamiento por tabla ──────────────────────────────────────

def process_listas_espera(df: pd.DataFrame, trimestre: str) -> pd.DataFrame:
    """Limpia y estandariza la hoja listas_espera_ss_trimestre."""
    df = normalize_columns(df, COL_MAP_LISTAS)

    for req in ("ss_id", "tipo_prestacion"):
        if req not in df.columns:
            raise ValueError(
                f"Columna requerida '{req}' no encontrada. "
                f"Columnas disponibles: {list(df.columns)}"
            )

    df["ss_id"] = df["ss_id"].apply(normalize_ss_id)
    df["tipo_prestacion"] = df["tipo_prestacion"].apply(normalize_tipo_prestacion)

    n_raw = len(df)
    df = df.dropna(subset=["ss_id", "tipo_prestacion"])
    n_dropped = n_raw - len(df)
    if n_dropped:
        log.warning(f"  {n_dropped} fila(s) eliminadas por ss_id o tipo_prestacion inválido")

    for col in ("personas_espera", "registros_espera", "mediana_dias",
                "promedio_dias", "reg_24a36m", "reg_mayor_36m"):
        df[col] = df[col].apply(clean_numeric) if col in df.columns else None

    # Asimetría: promedio - mediana (None si alguno falta)
    df["asimetria"] = df.apply(
        lambda r: round(r["promedio_dias"] - r["mediana_dias"], 1)
        if pd.notna(r.get("promedio_dias")) and pd.notna(r.get("mediana_dias"))
        else None,
        axis=1,
    )

    df["trimestre"] = trimestre
    if "fuente" not in df.columns:
        df["fuente"] = "Glosa 06"
    if "observaciones" not in df.columns:
        df["observaciones"] = None

    return df.reset_index(drop=True)


def process_personas_nacional(df: pd.DataFrame, trimestre: str) -> pd.DataFrame:
    """Limpia y estandariza la hoja personas_nacional_trimestre."""
    df = normalize_columns(df, COL_MAP_PERSONAS)

    if "tipo_prestacion" not in df.columns:
        raise ValueError(
            f"Columna requerida 'tipo_prestacion' no encontrada. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    df["tipo_prestacion"] = df["tipo_prestacion"].apply(normalize_tipo_prestacion)
    df = df.dropna(subset=["tipo_prestacion"])

    df["personas_total"] = (
        df["personas_total"].apply(clean_numeric) if "personas_total" in df.columns
        else None
    )
    df["trimestre"] = trimestre

    return df.reset_index(drop=True)


def process_nivel_atencion(df: pd.DataFrame, trimestre: str) -> pd.DataFrame:
    """Limpia y estandariza la hoja nivel_atencion_trimestre."""
    df = normalize_columns(df, COL_MAP_NIVEL)

    for req in ("nivel_atencion", "tipo_prestacion"):
        if req not in df.columns:
            raise ValueError(
                f"Columna requerida '{req}' no encontrada. "
                f"Columnas disponibles: {list(df.columns)}"
            )

    df["tipo_prestacion"] = df["tipo_prestacion"].apply(normalize_tipo_prestacion)
    df["nivel_atencion"] = df["nivel_atencion"].str.strip().str.title()
    df = df.dropna(subset=["nivel_atencion", "tipo_prestacion"])

    df["registros_total_nivel"] = (
        df["registros_total_nivel"].apply(clean_numeric)
        if "registros_total_nivel" in df.columns
        else None
    )
    df["trimestre"] = trimestre

    return df.reset_index(drop=True)


# ── UPSERT en PostgreSQL ───────────────────────────────────────────────────────

def _to_row(series, cols: list) -> tuple:
    """Convierte una fila del DataFrame a tupla para psycopg2, mapeando NaN → None."""
    return tuple(
        None if pd.isna(series.get(c)) else series.get(c)
        for c in cols
    )


def upsert_listas_espera(conn, df: pd.DataFrame) -> int:
    cols = [
        "ss_id", "trimestre", "tipo_prestacion", "personas_espera",
        "registros_espera", "mediana_dias", "promedio_dias", "asimetria",
        "reg_24a36m", "reg_mayor_36m", "fuente", "observaciones",
    ]
    rows = [_to_row(r, cols) for _, r in df.iterrows()]
    sql = """
        INSERT INTO listas_espera_ss_trimestre
            (ss_id, trimestre, tipo_prestacion, personas_espera, registros_espera,
             mediana_dias, promedio_dias, asimetria, reg_24a36m, reg_mayor_36m,
             fuente, observaciones)
        VALUES %s
        ON CONFLICT (ss_id, trimestre, tipo_prestacion) DO UPDATE SET
            personas_espera    = EXCLUDED.personas_espera,
            registros_espera   = EXCLUDED.registros_espera,
            mediana_dias       = EXCLUDED.mediana_dias,
            promedio_dias      = EXCLUDED.promedio_dias,
            asimetria          = EXCLUDED.asimetria,
            reg_24a36m         = EXCLUDED.reg_24a36m,
            reg_mayor_36m      = EXCLUDED.reg_mayor_36m,
            fuente             = EXCLUDED.fuente,
            observaciones      = EXCLUDED.observaciones,
            updated_at         = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    return len(rows)


def upsert_personas_nacional(conn, df: pd.DataFrame) -> int:
    cols = ["trimestre", "tipo_prestacion", "personas_total"]
    rows = [_to_row(r, cols) for _, r in df.iterrows()]
    sql = """
        INSERT INTO personas_nacional_trimestre (trimestre, tipo_prestacion, personas_total)
        VALUES %s
        ON CONFLICT (trimestre, tipo_prestacion) DO UPDATE SET
            personas_total = EXCLUDED.personas_total,
            updated_at     = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    return len(rows)


def upsert_nivel_atencion(conn, df: pd.DataFrame) -> int:
    cols = ["nivel_atencion", "trimestre", "tipo_prestacion", "registros_total_nivel"]
    rows = [_to_row(r, cols) for _, r in df.iterrows()]
    sql = """
        INSERT INTO nivel_atencion_trimestre
            (nivel_atencion, trimestre, tipo_prestacion, registros_total_nivel)
        VALUES %s
        ON CONFLICT (nivel_atencion, trimestre, tipo_prestacion) DO UPDATE SET
            registros_total_nivel = EXCLUDED.registros_total_nivel,
            updated_at            = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    return len(rows)


def log_pipeline_run(conn, archivo: str, trimestre: str, tabla: str,
                     procesadas: int, cargadas: int, omitidas: int,
                     estado: str, detalle: str = None):
    """Registra el resultado de cada carga en pipeline_runs."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_runs
                (archivo, trimestre, tabla_destino, filas_procesadas,
                 filas_insertadas, filas_actualizadas, filas_omitidas, estado, detalle)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (archivo, trimestre, tabla, procesadas, cargadas, 0, omitidas, estado, detalle))


# ── Orquestador ────────────────────────────────────────────────────────────────

PIPELINE = [
    ("listas_espera_ss_trimestre",  process_listas_espera,    upsert_listas_espera),
    ("personas_nacional_trimestre", process_personas_nacional, upsert_personas_nacional),
    ("nivel_atencion_trimestre",    process_nivel_atencion,    upsert_nivel_atencion),
]


def main(filepath: str):
    path = Path(filepath)
    if not path.exists():
        log.error(f"Archivo no encontrado: {path}")
        sys.exit(1)

    trimestre = parse_trimestre(path)

    log.info("=" * 62)
    log.info(f"  Archivo  : {path.name}")
    log.info(f"  Trimestre: {trimestre}")
    log.info("=" * 62)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        log.info(f"Hojas detectadas: {xl.sheet_names}\n")

        for sheet_name, process_fn, upsert_fn in PIPELINE:
            log.info(f"── {sheet_name}")
            df_raw = read_sheet(xl, sheet_name)

            if df_raw is None:
                log_pipeline_run(conn, path.name, trimestre, sheet_name,
                                 0, 0, 0, "warning", "Hoja no encontrada o vacía")
                log.info("")
                continue

            n_raw = len(df_raw)
            try:
                df_clean = process_fn(df_raw, trimestre)
                omitidas = n_raw - len(df_clean)
                cargadas = upsert_fn(conn, df_clean)

                estado = "warning" if omitidas > 0 else "ok"
                log_pipeline_run(conn, path.name, trimestre, sheet_name,
                                 n_raw, cargadas, omitidas, estado)

                log.info(f"  ✓ {cargadas} filas cargadas | {omitidas} omitidas\n")

            except ValueError as e:
                log.error(f"  ✗ Error de estructura: {e}\n")
                log_pipeline_run(conn, path.name, trimestre, sheet_name,
                                 n_raw, 0, n_raw, "error", str(e))

        conn.commit()
        log.info("=" * 62)
        log.info("  Carga completada y confirmada ✓")
        log.info("=" * 62)

    except Exception as e:
        conn.rollback()
        log.error(f"Error crítico — se ejecutó rollback: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])