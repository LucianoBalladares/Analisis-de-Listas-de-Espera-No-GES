-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/views/dashboard_views.sql
-- Descripción: Vistas optimizadas para consumo en Power BI
--
-- Ejecución : psql -U <usuario> -d <base> -f sql/views/dashboard_views.sql
-- Orden     : Ejecutar después del esquema completo (tablas + constraints)
--
-- Vistas incluidas:
--   v_dim_trimestre              → dimensión temporal para slicers
--   v_listas_espera_enriquecido  → tabla de hechos principal con métricas derivadas
--   v_velocidad_recuperacion     → delta trimestral de mediana con flag de gap
--   v_nivel_atencion_distribucion→ % de demanda por nivel de atención
--   v_disponibilidad_indicadores → mapa de disponibilidad de datos por período
--
-- CORRECCIONES:
--   - v_dim_trimestre: usa UNION de las 3 tablas (antes solo listas_espera).
--   - v_velocidad_recuperacion: agrega columnas periodos_gap y es_consecutivo
--     para identificar deltas calculados entre trimestres no consecutivos.
--   - v_listas_espera_enriquecido: pct_mayor_24m devuelve NULL cuando
--     ambos rangos son NULL, en lugar de sumar COALESCEs parciales.
-- =================================================================
-- -----------------------------------------------------------------
-- 1. Dimensión temporal
-- Cubre todos los trimestres presentes en cualquiera de las 3 tablas.
-- Antes solo incluía los de listas_espera_ss_trimestre, lo que podía
-- dejar fuera trimestres con datos solo en las otras tablas.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_dim_trimestre AS WITH todos_trimestres AS (
        SELECT trimestre
        FROM listas_espera_ss_trimestre
        UNION
        SELECT trimestre
        FROM personas_nacional_trimestre
        UNION
        SELECT trimestre
        FROM nivel_atencion_trimestre
    )
SELECT DISTINCT trimestre,
    SUBSTRING(trimestre, 1, 4)::INT AS anio,
    SUBSTRING(trimestre, 7, 1)::INT AS n_trimestre,
    'T' || SUBSTRING(trimestre, 7, 1) || ' ' || SUBSTRING(trimestre, 1, 4) AS etiqueta,
    -- Entero secuencial para ordenamiento correcto en Power BI
    (SUBSTRING(trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(trimestre, 7, 1)::INT AS periodo_orden,
    -- Primer día del trimestre (útil para eje de fechas)
    MAKE_DATE(
        SUBSTRING(trimestre, 1, 4)::INT,
        (SUBSTRING(trimestre, 7, 1)::INT - 1) * 3 + 1,
        1
    ) AS fecha_inicio
FROM todos_trimestres
ORDER BY trimestre;
-- -----------------------------------------------------------------
-- 2. Tabla de hechos principal (enriquecida)
-- Incluye todas las columnas originales más métricas derivadas.
--
-- CORRECCIÓN pct_mayor_24m: devuelve NULL si ambos rangos son NULL.
-- Si solo uno tiene valor, COALESCE a 0 subestimaría silenciosamente.
-- pct_mayor_24m representa el % de registros con >24m de espera,
-- calculado como (reg_24a36m + reg_mayor_36m) / registros_espera,
-- dado que ambos son rangos disjuntos (24-36m y >36m respectivamente).
-- -----------------------------------------------------------------
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
    -- pct_mayor_24m = % registros con >24m = (24-36m + >36m) / total
    -- Solo se calcula si ambos rangos tienen dato; NULL si alguno falta.
    CASE
        WHEN l.registros_espera > 0
        AND l.reg_24a36m IS NOT NULL
        AND l.reg_mayor_36m IS NOT NULL THEN ROUND(
            (l.reg_24a36m + l.reg_mayor_36m) / l.registros_espera * 100,
            1
        )
    END AS pct_mayor_24m,
    -- pct_mayor_36m = % registros con >36m
    CASE
        WHEN l.registros_espera > 0
        AND l.reg_mayor_36m IS NOT NULL THEN ROUND(l.reg_mayor_36m / l.registros_espera * 100, 1)
    END AS pct_mayor_36m,
    -- Dimensiones temporales (facilitan fórmulas DAX y slicers)
    SUBSTRING(l.trimestre, 1, 4)::INT AS anio,
    SUBSTRING(l.trimestre, 7, 1)::INT AS n_trimestre,
    (SUBSTRING(l.trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(l.trimestre, 7, 1)::INT AS periodo_orden,
    -- Trazabilidad
    l.fuente,
    l.observaciones,
    l.ingested_at,
    l.updated_at
FROM listas_espera_ss_trimestre l;
-- -----------------------------------------------------------------
-- 3. Velocidad de recuperación
-- Delta de mediana entre trimestres consecutivos por SS y tipo.
-- Valores negativos = reducción de espera (mejora del sistema).
--
-- CORRECCIÓN: agregadas columnas periodos_gap y es_consecutivo.
-- Cuando hay trimestres sin datos intermedios, LAG salta al anterior
-- disponible. delta_mediana en ese caso abarca múltiples períodos.
-- Power BI puede filtrar por es_consecutivo = TRUE para análisis puros.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_velocidad_recuperacion AS WITH base AS (
        SELECT ss_id,
            trimestre,
            tipo_prestacion,
            mediana_dias,
            (SUBSTRING(trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(trimestre, 7, 1)::INT AS periodo_orden,
            LAG(mediana_dias) OVER (
                PARTITION BY ss_id,
                tipo_prestacion
                ORDER BY trimestre
            ) AS mediana_anterior,
            LAG(trimestre) OVER (
                PARTITION BY ss_id,
                tipo_prestacion
                ORDER BY trimestre
            ) AS trimestre_anterior,
            -- periodo_orden del trimestre anterior con dato disponible
            LAG(
                (SUBSTRING(trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(trimestre, 7, 1)::INT
            ) OVER (
                PARTITION BY ss_id,
                tipo_prestacion
                ORDER BY trimestre
            ) AS periodo_orden_anterior
        FROM listas_espera_ss_trimestre
        WHERE mediana_dias IS NOT NULL
    )
SELECT ss_id,
    trimestre,
    trimestre_anterior,
    tipo_prestacion,
    periodo_orden,
    mediana_dias,
    mediana_anterior,
    ROUND(mediana_dias - mediana_anterior, 1) AS delta_mediana,
    -- Número de trimestres que separan este dato del anterior con dato
    -- 1 = consecutivo, 2+ = hubo gap(s) de datos intermedios
    (periodo_orden - periodo_orden_anterior) AS periodos_gap,
    -- TRUE solo cuando el delta es entre trimestres estrictamente consecutivos
    (periodo_orden - periodo_orden_anterior) = 1 AS es_consecutivo,
    CASE
        WHEN mediana_dias - mediana_anterior < 0 THEN 'Mejora'
        WHEN mediana_dias - mediana_anterior > 0 THEN 'Deterioro'
        WHEN mediana_dias - mediana_anterior = 0 THEN 'Sin cambio'
        ELSE NULL
    END AS tendencia
FROM base;
-- -----------------------------------------------------------------
-- 4. Distribución por nivel de atención
-- Calcula el porcentaje de registros por nivel dentro de cada
-- trimestre y tipo de prestación.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_nivel_atencion_distribucion AS
SELECT n.nivel_atencion,
    n.trimestre,
    n.tipo_prestacion,
    n.registros_total_nivel,
    SUM(n.registros_total_nivel) OVER (
        PARTITION BY n.trimestre,
        n.tipo_prestacion
    ) AS total_registros_periodo,
    ROUND(
        n.registros_total_nivel / NULLIF(
            SUM(n.registros_total_nivel) OVER (
                PARTITION BY n.trimestre,
                n.tipo_prestacion
            ),
            0
        ) * 100,
        1
    ) AS pct_nivel,
    (SUBSTRING(n.trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(n.trimestre, 7, 1)::INT AS periodo_orden
FROM nivel_atencion_trimestre n;
-- -----------------------------------------------------------------
-- 5. Mapa de disponibilidad de indicadores
-- Muestra qué indicadores tienen datos en cada período.
-- Útil para marcar visualmente datos faltantes en Power BI.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_disponibilidad_indicadores AS
SELECT l.trimestre,
    l.tipo_prestacion,
    COUNT(*) AS n_ss_cargados,
    -- Disponibilidad por indicador (TRUE = al menos 1 SS tiene el dato)
    BOOL_OR(l.mediana_dias IS NOT NULL) AS mediana_disponible,
    BOOL_OR(l.personas_espera IS NOT NULL) AS personas_ss_disponible,
    BOOL_OR(l.reg_24a36m IS NOT NULL) AS tramo_24_36m_disponible,
    BOOL_OR(l.reg_mayor_36m IS NOT NULL) AS tramo_mayor_36m_disponible,
    BOOL_OR(
        l.reg_24a36m IS NOT NULL
        AND l.reg_mayor_36m IS NOT NULL
    ) AS antiguedad_completa_disponible,
    EXISTS (
        SELECT 1
        FROM personas_nacional_trimestre p
        WHERE p.trimestre = l.trimestre
            AND p.tipo_prestacion = l.tipo_prestacion
            AND p.personas_total IS NOT NULL
    ) AS personas_nacional_disponible,
    EXISTS (
        SELECT 1
        FROM nivel_atencion_trimestre na
        WHERE na.trimestre = l.trimestre
            AND na.tipo_prestacion = l.tipo_prestacion
    ) AS nivel_atencion_disponible,
    (SUBSTRING(l.trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(l.trimestre, 7, 1)::INT AS periodo_orden
FROM listas_espera_ss_trimestre l
GROUP BY l.trimestre,
    l.tipo_prestacion
ORDER BY l.trimestre,
    l.tipo_prestacion;