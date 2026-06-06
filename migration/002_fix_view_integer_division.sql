-- =================================================================
-- Migración : 002_fix_view_integer_division.sql
-- Fecha     : 2026-06-06
-- Descripción: Corrige división entera BIGINT/BIGINT en los cálculos
--              de pct_mayor_24m y pct_mayor_36m en la vista
--              v_listas_espera_enriquecido.
--
--              El bug causaba que la mayoría de los porcentajes
--              se calcularan como 0 por truncamiento antes de
--              multiplicar por 100.
--
--              Fix: ::NUMERIC en el numerador fuerza división
--              de punto flotante en toda la expresión.
--
--              Aplicado en producción el 2026-06-06.
--              La corrección está incorporada en
--              sql/views/dashboard_views.sql desde esa fecha.
-- =================================================================
-- (Solo se preserva como registro histórico de la corrección.)
-- La sentencia real ya está en sql/views/dashboard_views.sql.
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