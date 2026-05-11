-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Autor    : Luciano Balladares
-- Archivo  : sql/schema/create_tables.sql
-- Descripción: Creación del esquema principal de la base de datos
--
-- Requisitos: PostgreSQL >= 12
-- Ejecución : psql -U <usuario> -d <base> -f sql/schema/create_tables.sql
-- =================================================================
-- -----------------------------------------------------------------
-- Tabla 1: listas_espera_ss_trimestre
-- Unidad de análisis: Servicio de Salud × Trimestre × Tipo prestación
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS listas_espera_ss_trimestre (
    id SERIAL,
    ss_id TEXT NOT NULL,
    trimestre TEXT NOT NULL,
    tipo_prestacion TEXT NOT NULL,
    -- Volumen
    personas_espera NUMERIC(10, 0),
    -- Personas únicas en lista activa
    registros_espera NUMERIC(10, 0),
    -- Registros totales (puede superar personas)
    -- Tiempos de espera
    mediana_dias NUMERIC(8, 1),
    promedio_dias NUMERIC(8, 1),
    asimetria NUMERIC(8, 1),
    -- Calculada en ingesta: promedio - mediana
    -- Antigüedad extrema (tramos independientes, calculados en registros)
    reg_24a36m NUMERIC(10, 0),
    -- Registros con 24–36 meses de espera
    reg_mayor_36m NUMERIC(10, 0),
    -- Registros con >36 meses de espera
    -- Trazabilidad
    fuente TEXT,
    observaciones TEXT,
    -- Auditoría
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- -----------------------------------------------------------------
-- Tabla 2: personas_nacional_trimestre
-- Unidad de análisis: Trimestre × Tipo prestación (nivel nacional)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personas_nacional_trimestre (
    id SERIAL,
    trimestre TEXT NOT NULL,
    tipo_prestacion TEXT NOT NULL,
    personas_total NUMERIC(10, 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- -----------------------------------------------------------------
-- Tabla 3: nivel_atencion_trimestre
-- Unidad de análisis: Nivel atención × Trimestre × Tipo prestación
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nivel_atencion_trimestre (
    id SERIAL,
    nivel_atencion TEXT NOT NULL,
    trimestre TEXT NOT NULL,
    tipo_prestacion TEXT NOT NULL,
    registros_total_nivel NUMERIC(10, 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- -----------------------------------------------------------------
-- Tabla 4: pipeline_runs
-- Registra cada ejecución del script de ingesta para auditoría
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archivo TEXT NOT NULL,
    -- Nombre del Excel procesado
    trimestre TEXT NOT NULL,
    -- Período cargado (ej: 2024_T3)
    tabla_destino TEXT NOT NULL,
    -- Tabla donde se insertó
    filas_procesadas INT NOT NULL DEFAULT 0,
    filas_insertadas INT NOT NULL DEFAULT 0,
    filas_actualizadas INT NOT NULL DEFAULT 0,
    filas_omitidas INT NOT NULL DEFAULT 0,
    -- Filas con error o vacías
    estado TEXT NOT NULL,
    -- 'ok' | 'warning' | 'error'
    detalle TEXT -- Mensaje de error o advertencia
);