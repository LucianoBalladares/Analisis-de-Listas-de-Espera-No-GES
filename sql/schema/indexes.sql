-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/schema/indexes.sql
-- Descripción: Índices para optimizar consultas analíticas y de Power BI
--
-- Ejecución: psql -U <usuario> -d <base> -f sql/schema/indexes.sql
-- Debe ejecutarse DESPUÉS de constraints.sql
-- =================================================================
-- -----------------------------------------------------------------
-- listas_espera_ss_trimestre
-- Patrones de consulta: filtrar por SS, por período, por tipo prestación
-- -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_listas_ss_id ON listas_espera_ss_trimestre (ss_id);
CREATE INDEX IF NOT EXISTS idx_listas_trimestre ON listas_espera_ss_trimestre (trimestre);
CREATE INDEX IF NOT EXISTS idx_listas_tipo_prestacion ON listas_espera_ss_trimestre (tipo_prestacion);
-- Índice compuesto para análisis longitudinal (más común en Power BI)
CREATE INDEX IF NOT EXISTS idx_listas_ss_trimestre_tipo ON listas_espera_ss_trimestre (ss_id, trimestre, tipo_prestacion);
-- -----------------------------------------------------------------
-- personas_nacional_trimestre
-- -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_personas_trimestre ON personas_nacional_trimestre (trimestre);
CREATE INDEX IF NOT EXISTS idx_personas_tipo ON personas_nacional_trimestre (tipo_prestacion);
-- -----------------------------------------------------------------
-- nivel_atencion_trimestre
-- -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_nivel_trimestre ON nivel_atencion_trimestre (trimestre);
CREATE INDEX IF NOT EXISTS idx_nivel_tipo ON nivel_atencion_trimestre (tipo_prestacion);
CREATE INDEX IF NOT EXISTS idx_nivel_atencion ON nivel_atencion_trimestre (nivel_atencion);
-- -----------------------------------------------------------------
-- pipeline_runs
-- Para consultar historial de carga rápidamente
-- -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pipeline_trimestre ON pipeline_runs (trimestre);
CREATE INDEX IF NOT EXISTS idx_pipeline_estado ON pipeline_runs (estado);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_at ON pipeline_runs (run_at DESC);