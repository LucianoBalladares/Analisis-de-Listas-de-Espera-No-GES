"""
Ingesta de datos desde Excel trimestral a PostgreSQL.

Uso:
    python pipeline/ingest/excel_a_sql.py <ruta/al/archivo.xlsx>
    python pipeline/ingest/excel_a_sql.py data/staging/2024_T3.xlsx

El archivo debe seguir la convención: YYYY_T#.xlsx (ej: 2024_T3.xlsx).
Puede contener hasta 3 hojas (ninguna es obligatoria):
    - listas_espera_ss_trimestre
    - personas_nacional_trimestre
    - nivel_atencion_trimestre

La carga es idempotente: re-correr el script con el mismo archivo
actualiza los registros existentes (UPSERT), nunca duplica.

Cada hoja se carga en su propia transacción: si una falla, las hojas
ya confirmadas no se revierten.

Requisitos: Python >= 3.10 (usa sintaxis X | Y para type hints)
"""

import os
import re
import sys
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import psycopg2
from psycopg2 import sql                    
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from pipeline.config.catalogos import SS_ID_MAP

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
        logging.FileHandler(LOG_DIR / "ingesta.log", encoding="utf-8"),
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

NULL_VALUES = {
    "N/D", "ND", "NO DISPONIBLE", "S/I", "S/D", "SIN INFORMACION",
    "SIN INFORMACIÓN", "-", "—", "–", "", "NA", "N/A", ".", "..",
}

TOTAL_ROW_PATTERNS = re.compile(
    r'^\s*(total|subtotal|país|pais|nacional|promedio\s+nacional|promedio\s+país'
    r'|n\.?\s*a\.?|n/a)\s*$',
    flags=re.IGNORECASE | re.UNICODE,
)

# ── Mapeo de columnas Excel → DB ───────────────────────────────────────────────

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

NIVEL_ATENCION_MAP: dict[str, str] = {
    "primario":           "Primario",
    "nivel primario":     "Primario",
    "1° nivel":           "Primario",
    "primer nivel":       "Primario",
    "secundario":         "Secundario",
    "nivel secundario":   "Secundario",
    "2° nivel":           "Secundario",
    "segundo nivel":      "Secundario",
    "terciario":          "Terciario",
    "nivel terciario":    "Terciario",
    "3° nivel":           "Terciario",
    "tercer nivel":       "Terciario",
}

# ── Funciones auxiliares ───────────────────────────────────────────────────────

def parse_trimestre(filepath: Path) -> str:
    match = re.search(r'(\d{4}_T[1-4])', filepath.stem, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"No se pudo determinar el trimestre desde '{filepath.name}'. "
            "El nombre debe contener un patrón como '2024_T1'."
        )
    return match.group(1).upper()


def normalize_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    rename = {}
    for db_col, candidates in col_map.items():
        for candidate in candidates:
            if candidate.lower() in df.columns:
                rename[candidate.lower()] = db_col
                break
    df = df.rename(columns=rename)
    known_cols = list(col_map.keys())
    return df[[c for c in known_cols if c in df.columns]]


def clean_numeric(val) -> float | None:
    """
    Convierte un valor a float tolerando formatos numéricos post-OCR.

    En condiciones normales el OCR está configurado para no usar separadores
    de miles (ni punto ni coma), por lo que los números llegan como enteros
    limpios ('1234') o con punto decimal ('1234.5'). El manejo de comas y
    puntos combinados es una red de seguridad para doble falla (OCR + revisión
    humana), no el camino normal de datos.

    Formatos manejados:
        '1234'     → 1234.0  (caso normal — entero limpio del OCR)
        '1234.5'   → 1234.5  (caso normal — decimal con punto)
        '1234,5'   → 1234.5  (coma decimal — falla OCR documentada)
        '0,365'    → 0.365   (coma decimal, aunque tenga 3 dígitos post-coma)
        '1.234,5'  → 1234.5  (ambos separadores: se asume punto=miles, coma=decimal)
        '1,234.5'  → 1.234   (ambos separadores: se asume punto=miles, coma=decimal;
                               si el valor real era 1234.5 en formato americano,
                               el resultado es incorrecto — requiere doble falla)
        'N/D', '-' → None
        Negativos  → None (aberrantes en este dominio; se loguean)
    """
    if pd.isna(val):
        return None
    s = str(val).strip().upper()
    if s in NULL_VALUES:
        return None
    s = re.sub(r'[%$]', '', s).strip()
    if not s:
        return None

    if ',' in s and '.' in s:
        # Ambos separadores presentes: se asume formato europeo
        # (punto = miles, coma = decimal).
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')

    s = re.sub(r'[^\d.\-]', '', s)
    if not s or s == '.':
        return None

    try:
        result = float(s)
    except ValueError:
        return None

    if result < 0:
        log.warning(f"  Valor negativo descartado como NULL: '{val}'")
        return None

    return result


def is_total_row(val) -> bool:
    if pd.isna(val):
        return False
    return bool(TOTAL_ROW_PATTERNS.match(str(val).strip()))


def normalize_tipo_prestacion(val) -> str | None:
    if pd.isna(val) or str(val).strip().upper() in NULL_VALUES:
        return None
    key = str(val).strip().lower()
    result = TIPO_PRESTACION_MAP.get(key)
    if result is None:
        log.warning(f"  tipo_prestacion no reconocido: '{val}'")
    return result



def normalize_nivel_atencion(val) -> str | None:
    if pd.isna(val):
        return None
    cleaned = str(val).strip()
    key = cleaned.lower()
    result = NIVEL_ATENCION_MAP.get(key)
    if result is not None:
        return result
    fallback = cleaned.title()
    log.warning(
        f"  nivel_atencion no reconocido: '{cleaned}' → usando '{fallback}' "
        "(revisar con validacion.py → check_niveles_atencion)"
    )
    return fallback


def normalize_ss_id(val) -> str | None:
    if pd.isna(val):
        return None
    raw = str(val).strip()

    if is_total_row(raw):
        return None

    key = re.sub(r'^servicio\s+de\s+salud\s+', '', raw.lower()).strip()
    key = re.sub(r'^s\.?\s*s\.?\s*', '', key).strip()
    key = re.sub(r'\s+', ' ', key)

    if key in SS_ID_MAP:
        return SS_ID_MAP[key]

    for k, v in sorted(SS_ID_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if k in key or key in k:
            log.warning(
                f"  ss_id '{raw}' → '{v}' (coincidencia parcial, verificar manualmente)"
            )
            return v

    log.warning(f"  ss_id no reconocido: '{raw}' — se usará el valor original")
    return raw


def read_sheet(xl: pd.ExcelFile, sheet_name: str) -> pd.DataFrame | None:
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


# ── Procesamiento por tabla ────────────────────────────────────────────────────

def _filter_total_rows(df: pd.DataFrame, col: str, tabla: str) -> pd.DataFrame:
    n_pre = len(df)
    df = df[~df[col].apply(is_total_row)]
    n_dropped = n_pre - len(df)
    if n_dropped:
        log.info(f"  [{tabla}] {n_dropped} fila(s) de totales/encabezados descartadas")
    return df


def process_listas_espera(df: pd.DataFrame, trimestre: str) -> pd.DataFrame:
    df = normalize_columns(df, COL_MAP_LISTAS)

    for req in ("ss_id", "tipo_prestacion"):
        if req not in df.columns:
            raise ValueError(
                f"Columna requerida '{req}' no encontrada. "
                f"Columnas disponibles: {list(df.columns)}"
            )

    df = _filter_total_rows(df, "ss_id", "listas_espera")
    df["ss_id"] = df["ss_id"].apply(normalize_ss_id)
    df["tipo_prestacion"] = df["tipo_prestacion"].apply(normalize_tipo_prestacion)

    n_raw = len(df)
    df = df.dropna(subset=["ss_id", "tipo_prestacion"])
    n_dropped = n_raw - len(df)
    if n_dropped:
        log.warning(f"  {n_dropped} fila(s) eliminadas por ss_id o tipo_prestacion inválido")

    for col in ("personas_espera", "registros_espera", "mediana_dias",
                "promedio_dias", "reg_24a36m", "reg_mayor_36m"):
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

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
    df = normalize_columns(df, COL_MAP_PERSONAS)

    if "tipo_prestacion" not in df.columns:
        raise ValueError(
            f"Columna requerida 'tipo_prestacion' no encontrada. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    df = _filter_total_rows(df, "tipo_prestacion", "personas_nacional")
    df["tipo_prestacion"] = df["tipo_prestacion"].apply(normalize_tipo_prestacion)
    df = df.dropna(subset=["tipo_prestacion"])

    if "personas_total" in df.columns:
        df["personas_total"] = df["personas_total"].apply(clean_numeric)
    else:
        df["personas_total"] = pd.NA

    df["trimestre"] = trimestre
    return df.reset_index(drop=True)


def process_nivel_atencion(df: pd.DataFrame, trimestre: str) -> pd.DataFrame:
    df = normalize_columns(df, COL_MAP_NIVEL)

    for req in ("nivel_atencion", "tipo_prestacion"):
        if req not in df.columns:
            raise ValueError(
                f"Columna requerida '{req}' no encontrada. "
                f"Columnas disponibles: {list(df.columns)}"
            )

    df = _filter_total_rows(df, "nivel_atencion", "nivel_atencion")
    df["tipo_prestacion"] = df["tipo_prestacion"].apply(normalize_tipo_prestacion)
    df["nivel_atencion"] = df["nivel_atencion"].apply(normalize_nivel_atencion)

    df = df.dropna(subset=["nivel_atencion", "tipo_prestacion"])

    df["registros_total_nivel"] = (
        df["registros_total_nivel"].apply(clean_numeric)
        if "registros_total_nivel" in df.columns
        else pd.NA
    )
    df["trimestre"] = trimestre
    return df.reset_index(drop=True)


# ── Helpers de UPSERT ─────────────────────────────────────────────────────────

def _to_row(series, cols: list) -> tuple:
    return tuple(
        None if pd.isna(series.get(c)) else series.get(c)
        for c in cols
    )


def _count_existing(conn, tabla: str, trimestre: str) -> int:
    """
    Cuenta las filas que ya existen en la tabla para el trimestre dado.
    Usado antes del UPSERT para estimar cuántas serán inserciones nuevas
    vs actualizaciones de registros existentes.
    """
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {} WHERE trimestre = %s").format(
                sql.Identifier(tabla)
            ),
            (trimestre,),
        )
        return cur.fetchone()[0]


def _compute_insert_update(n_upserted: int, pre_count: int) -> tuple[int, int]:
    """
    Estima inserciones vs actualizaciones a partir del UPSERT.

    Lógica:
        - n_updated = min(pre_count, n_upserted)
          (no puede haber más actualizaciones que filas preexistentes)
        - n_inserted = n_upserted - n_updated

    Esta estimación es exacta en el flujo habitual (primera carga de un
    trimestre: pre_count=0 → todo son inserts; re-carga del mismo Excel:
    pre_count≈n_upserted → todo son updates). En re-cargas parciales la
    estimación puede diferir ligeramente del valor real.
    """
    n_updated  = min(pre_count, n_upserted)
    n_inserted = n_upserted - n_updated
    return n_inserted, n_updated


# ── UPSERT en PostgreSQL ───────────────────────────────────────────────────────

def upsert_listas_espera(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Inserta o actualiza filas en listas_espera_ss_trimestre.

    Returns:
        (n_inserted, n_updated): estimación de inserciones y actualizaciones.
    """
    trimestre = df["trimestre"].iloc[0] if not df.empty else ""
    pre_count = _count_existing(conn, "listas_espera_ss_trimestre", trimestre)

    cols = [
        "ss_id", "trimestre", "tipo_prestacion", "personas_espera",
        "registros_espera", "mediana_dias", "promedio_dias", "asimetria",
        "reg_24a36m", "reg_mayor_36m", "fuente", "observaciones",
    ]
    rows = [_to_row(r, cols) for _, r in df.iterrows()]
    sql_stmt = """
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
            observaciones      = COALESCE(
                                     listas_espera_ss_trimestre.observaciones,
                                     EXCLUDED.observaciones
                                 ),
            updated_at         = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql_stmt, rows)

    return _compute_insert_update(len(rows), pre_count)


def upsert_personas_nacional(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Inserta o actualiza filas en personas_nacional_trimestre.

    Returns:
        (n_inserted, n_updated): estimación de inserciones y actualizaciones.
    """
    trimestre = df["trimestre"].iloc[0] if not df.empty else ""
    pre_count = _count_existing(conn, "personas_nacional_trimestre", trimestre)

    cols = ["trimestre", "tipo_prestacion", "personas_total"]
    rows = [_to_row(r, cols) for _, r in df.iterrows()]
    sql_stmt = """
        INSERT INTO personas_nacional_trimestre (trimestre, tipo_prestacion, personas_total)
        VALUES %s
        ON CONFLICT (trimestre, tipo_prestacion) DO UPDATE SET
            personas_total = EXCLUDED.personas_total,
            updated_at     = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql_stmt, rows)

    return _compute_insert_update(len(rows), pre_count)


def upsert_nivel_atencion(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Inserta o actualiza filas en nivel_atencion_trimestre.

    Returns:
        (n_inserted, n_updated): estimación de inserciones y actualizaciones.
    """
    trimestre = df["trimestre"].iloc[0] if not df.empty else ""
    pre_count = _count_existing(conn, "nivel_atencion_trimestre", trimestre)

    cols = ["nivel_atencion", "trimestre", "tipo_prestacion", "registros_total_nivel"]
    rows = [_to_row(r, cols) for _, r in df.iterrows()]
    sql_stmt = """
        INSERT INTO nivel_atencion_trimestre
            (nivel_atencion, trimestre, tipo_prestacion, registros_total_nivel)
        VALUES %s
        ON CONFLICT (nivel_atencion, trimestre, tipo_prestacion) DO UPDATE SET
            registros_total_nivel = EXCLUDED.registros_total_nivel,
            updated_at            = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql_stmt, rows)

    return _compute_insert_update(len(rows), pre_count)


# ── Registro de ejecución ─────────────────────────────────────────────────────

def log_pipeline_run(
    conn,
    archivo:     str,
    trimestre:   str,
    tabla:       str,
    procesadas:  int,
    insertadas:  int,
    actualizadas: int,
    omitidas:    int,
    estado:      str,
    detalle:     str = None,
):
    """
    Registra una ejecución en pipeline_runs.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_runs
                (archivo, trimestre, tabla_destino, filas_procesadas,
                 filas_insertadas, filas_actualizadas, filas_omitidas, estado, detalle)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            archivo, trimestre, tabla,
            procesadas, insertadas, actualizadas, omitidas,
            estado, detalle,
        ))


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
                try:
                    log_pipeline_run(
                        conn, path.name, trimestre, sheet_name,
                        0, 0, 0, 0, "warning", "Hoja no encontrada o vacía",
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                log.info("")
                continue

            n_raw = len(df_raw)
            try:
                df_clean  = process_fn(df_raw, trimestre)
                omitidas  = n_raw - len(df_clean)

                n_inserted, n_updated = upsert_fn(conn, df_clean)

                estado = "warning" if omitidas > 0 else "ok"
                log_pipeline_run(
                    conn, path.name, trimestre, sheet_name,
                    n_raw, n_inserted, n_updated, omitidas, estado,
                )
                conn.commit()
                log.info(
                    f"  ✓ {n_inserted} insertadas | "
                    f"{n_updated} actualizadas | "
                    f"{omitidas} omitidas\n"
                )

            except ValueError as e:
                conn.rollback()
                log.error(f"  ✗ Error de estructura: {e}\n")
                try:
                    log_pipeline_run(
                        conn, path.name, trimestre, sheet_name,
                        n_raw, 0, 0, n_raw, "error", str(e)[:500],
                    )
                    conn.commit()
                except Exception as log_err:
                    log.warning(f"  No se pudo registrar error en pipeline_runs: {log_err}")
                    conn.rollback()

            except psycopg2.Error as e:
                conn.rollback()
                log.error(f"  ✗ Error de base de datos en '{sheet_name}': {e}\n")
                try:
                    log_pipeline_run(
                        conn, path.name, trimestre, sheet_name,
                        n_raw, 0, 0, n_raw, "error", str(e)[:500],
                    )
                    conn.commit()
                except Exception as log_err:
                    log.warning(f"  No se pudo registrar error en pipeline_runs: {log_err}")
                    conn.rollback()

        log.info("=" * 62)
        log.info("  Carga completada ✓")
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