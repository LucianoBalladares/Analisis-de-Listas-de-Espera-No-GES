-- =================================================================
-- Fix: division entera en pct_mayor_24m y pct_mayor_36m
-- Archivo: fix_view_integer_division.sql
--
-- Problema:
--   BIGINT / BIGINT en PostgreSQL usa división entera (trunca decimales).
--   (reg_24a36m + reg_mayor_36m) / registros_espera * 100
--   = 1000 / 6000 * 100
--   = 0 * 100   ← truncamiento a 0 antes de multiplicar
--   = 0
--
-- Solución:
--   Castear el numerador a NUMERIC antes de la división.
--   Esto fuerza división de punto flotante en todo el cálculo.
--
-- Ejecución:
--   psql -U postgres -d listas_espera_ges -f fix_view_integer_division.sql
--
-- Verificación post-ejecución:
--   SELECT ss_id, trimestre, reg_24a36m, reg_mayor_36m,
--          registros_espera, pct_mayor_24m, pct_mayor_36m
--   FROM v_listas_espera_enriquecido
--   WHERE reg_24a36m IS NOT NULL
--     AND reg_mayor_36m IS NOT NULL
--   LIMIT 10;
-- =================================================================
CREATE OR REPLACE VIEW v_listas_espera_enriquecido AS
SELECT l.id,
    l.ss_id,
    l.trimestre,
    l.tipo_prestacion,
    -- Volumen
    l.personas_espera,
    l.registros_espera,
    -- Tiempos de espera
    l.mediana_dias,
    l.promedio_dias,
    l.asimetria,
    -- Antigüedad en registros
    l.reg_24a36m,
    l.reg_mayor_36m,
    -- Antigüedad en porcentaje
    -- FIX: ::NUMERIC evita división entera BIGINT/BIGINT que producía 0 en todos los casos
    CASE
        WHEN l.registros_espera > 0
        AND l.reg_24a36m IS NOT NULL
        AND l.reg_mayor_36m IS NOT NULL THEN ROUND(
            (l.reg_24a36m + l.reg_mayor_36m)::NUMERIC / l.registros_espera * 100,
            1
        )
    END AS pct_mayor_24m,
    CASE
        WHEN l.registros_espera > 0
        AND l.reg_mayor_36m IS NOT NULL THEN ROUND(
            l.reg_mayor_36m::NUMERIC / l.registros_espera * 100,
            1
        )
    END AS pct_mayor_36m,
    -- Dimensiones temporales (facilitan fórmulas DAX y slicers)
    SUBSTRING(l.trimestre, 1, 4)::INT AS anio,
    SUBSTRING(l.trimestre, 7, 1)::INT AS n_trimestre,
    SUBSTRING(l.trimestre, 1, 4)::INT * 4 + SUBSTRING(l.trimestre, 7, 1)::INT AS periodo_orden,
    -- Trazabilidad
    l.fuente,
    l.observaciones,
    l.ingested_at,
    l.updated_at
FROM listas_espera_ss_trimestre l;
-- -----------------------------------------------------------------
-- Verificación inmediata: debe mostrar valores > 0 donde hay datos
-- -----------------------------------------------------------------
SELECT COUNT(*) FILTER (
        WHERE reg_24a36m IS NOT NULL
            AND reg_mayor_36m IS NOT NULL
            AND pct_mayor_24m = 0
    ) AS casos_cero_24m_sospechosos,
    COUNT(*) FILTER (
        WHERE reg_24a36m IS NOT NULL
            AND reg_mayor_36m IS NOT NULL
            AND pct_mayor_24m > 0
    ) AS casos_correctos_24m,
    COUNT(*) FILTER (
        WHERE reg_24a36m IS NOT NULL
            AND reg_mayor_36m IS NOT NULL
            AND pct_mayor_24m IS NULL
    ) AS casos_null_24m
FROM v_listas_espera_enriquecido;