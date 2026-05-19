"""
catalogos.py
============
Única fuente de verdad para el catálogo de Servicios de Salud.

Antes de esta centralización, el catálogo estaba duplicado en:
    - pipeline/ingest/validacion.py        (SS_ESPERADOS)
    - pipeline/transform/run_transformations.py (SS_CANONICOS)
    - pipeline/ingest/excel_a_sql.py       (SS_ID_MAP)
    - sql/transformations/normalize_services.sql (lista comentada)

Cualquier cambio en el catálogo (nuevos SS, renombres) se hace
SOLO aquí. Los demás módulos importan desde este archivo.
"""

# =================================================================
# Catálogo vigente — 29 Servicios de Salud (última Glosa 06)
# =================================================================

SS_CANONICOS: set[str] = {
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
    "SS Magallanes",
}

# Valores especiales que pueden aparecer como ss_id pero NO son SS estándar
SS_ESPECIALES: set[str] = {"No definido", "NO DEFINIDO", "Sin asignar"}

# Niveles de atención esperados (para validación en validacion.py)
NIVELES_ATENCION: set[str] = {"Primario", "Secundario", "Terciario"}

# =================================================================
# Mapa de normalización: alias → nombre canónico
# Cubre nombres históricos, variantes de OCR, prefijos largos.
# =================================================================

SS_ID_MAP: dict[str, str] = {
    # ── Extremo Norte ──────────────────────────────────────────────
    "arica":                            "SS Arica y Parinacota",
    "arica y parinacota":               "SS Arica y Parinacota",
    "ss arica":                         "SS Arica y Parinacota",   # nombre anterior
    "iquique":                          "SS Tarapacá",             # nombre anterior
    "tarapaca":                         "SS Tarapacá",
    "tarapacá":                         "SS Tarapacá",
    # ── Norte ──────────────────────────────────────────────────────
    "antofagasta":                      "SS Antofagasta",
    "atacama":                          "SS Atacama",
    "coquimbo":                         "SS Coquimbo",
    # ── Centro-Norte ───────────────────────────────────────────────
    "viña del mar quillota":            "SS Viña del Mar - Quillota",
    "viña del mar - quillota":          "SS Viña del Mar - Quillota",
    "vina del mar quillota":            "SS Viña del Mar - Quillota",
    "valparaiso san antonio":           "SS Valparaíso - San Antonio",
    "valparaíso san antonio":           "SS Valparaíso - San Antonio",
    "valparaíso - san antonio":         "SS Valparaíso - San Antonio",
    "aconcagua":                        "SS Aconcagua",
    # ── Metropolitana ──────────────────────────────────────────────
    "metropolitano norte":              "SS Metropolitano Norte",
    "metropolitano occidente":          "SS Metropolitano Occidente",
    "metropolitano central":            "SS Metropolitano Central",
    "metropolitano oriente":            "SS Metropolitano Oriente",
    "metropolitano sur":                "SS Metropolitano Sur",
    "metropolitano sur oriente":        "SS Metropolitano Sur Oriente",
    # ── Centro-Sur ─────────────────────────────────────────────────
    "o'higgins":                        "SS O'Higgins",
    "ohiggins":                         "SS O'Higgins",
    "maule":                            "SS Maule",
    "ñuble":                            "SS Ñuble",
    "nuble":                            "SS Ñuble",
    # ── Biobío ─────────────────────────────────────────────────────
    "concepcion":                       "SS Concepción",
    "concepción":                       "SS Concepción",
    "arauco":                           "SS Arauco",
    "talcahuano":                       "SS Talcahuano",
    "biobio":                           "SS Biobío",
    "biobío":                           "SS Biobío",
    # ── Araucanía ──────────────────────────────────────────────────
    "araucania norte":                  "SS Araucanía Norte",
    "araucanía norte":                  "SS Araucanía Norte",
    "araucania sur":                    "SS Araucanía Sur",
    "araucanía sur":                    "SS Araucanía Sur",
    # ── Sur ────────────────────────────────────────────────────────
    "valdivia":                         "SS Los Ríos",             # nombre anterior
    "los rios":                         "SS Los Ríos",
    "los ríos":                         "SS Los Ríos",
    "osorno":                           "SS Osorno",
    "del reloncavi":                    "SS Del Reloncaví",
    "del reloncaví":                    "SS Del Reloncaví",
    "reloncavi":                        "SS Del Reloncaví",
    "reloncaví":                        "SS Del Reloncaví",
    "chiloe":                           "SS Chiloé",
    "chiloé":                           "SS Chiloé",
    # ── Austral ────────────────────────────────────────────────────
    "aysen":                            "SS Aysén",
    "aysén":                            "SS Aysén",
    "magallanes":                       "SS Magallanes",

    # Variantes con guión sin espacios (OCR de algunos períodos)──────
    "valparaíso-san antonio":           "SS Valparaíso - San Antonio",
    "valparaiso-san antonio":           "SS Valparaíso - San Antonio",
    "viña del mar-quillota":            "SS Viña del Mar - Quillota",
    "vina del mar-quillota":            "SS Viña del Mar - Quillota",
    "metropolitano sur-oriente":        "SS Metropolitano Sur Oriente",
    "del maule":                        "SS Maule",
}