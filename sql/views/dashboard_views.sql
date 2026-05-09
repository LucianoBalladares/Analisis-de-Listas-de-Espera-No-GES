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
--   v_velocidad_recuperacion     → delta trimestral de mediana (LAG)
--   v_nivel_atencion_distribucion→ % de demanda por nivel de atención
--   v_disponibilidad_indicadores → mapa de disponibilidad de datos por período
-- =================================================================
-- -----------------------------------------------------------------
-- 1. Dimensión temporal
-- Tabla de apoyo para slicers y orden correcto en Power BI.
-- Power BI no ordena texto alfanumérico correctamente por defecto;
-- periodo_orden es la columna que se usa para Sort By Column.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_dim_trimestre AS
SELECT DISTINCT trimestre,
    SUBSTRING(trimestre, 1, 4)::INT AS anio,
    SUBSTRING(trimestre, 7, 1)::INT AS n_trimestre,
    'T' || SUBSTRING(trimestre, 7, 1) || ' ' || SUBSTRING(trimestre, 1, 4) AS etiqueta,
    -- Entero secuencial para ordenamiento correcto (2021_T1 = 1, 2021_T2 = 2, …)
    (SUBSTRING(trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(trimestre, 7, 1)::INT AS periodo_orden,
    -- Primer día del trimestre (útil para eje de fechas en Power BI)
    MAKE_DATE(
        SUBSTRING(trimestre, 1, 4)::INT,
        (SUBSTRING(trimestre, 7, 1)::INT - 1) * 3 + 1,
        1
    ) AS fecha_inicio
FROM listas_espera_ss_trimestre
ORDER BY trimestre;
-- -----------------------------------------------------------------
-- 2. Tabla de hechos principal (enriquecida)
-- Incluye todas las columnas originales más métricas derivadas.
-- Es la vista central del dashboard.
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
    -- Antigüedad en porcentaje (para gráficos proporcionales)
    -- pct_mayor_24m incluye tanto 24-36 como >36 meses
    CASE
        WHEN l.registros_espera > 0
        AND (
            l.reg_24a36m IS NOT NULL
            OR l.reg_mayor_36m IS NOT NULL
        ) THEN ROUND(
            (
                COALESCE(l.reg_24a36m, 0) + COALESCE(l.reg_mayor_36m, 0)
            ) / l.registros_espera * 100,
            1
        )
    END AS pct_mayor_24m,
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
-- Calcula el delta de mediana entre trimestres consecutivos
-- para cada Servicio de Salud y tipo de prestación.
-- Valores negativos = reducción de espera (mejora del sistema).
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
            ) AS trimestre_anterior
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
-- pct_nivel se usa como proxy de concentración en nivel terciario.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_nivel_atencion_distribucion AS
SELECT n.nivel_atencion,
    n.trimestre,
    n.tipo_prestacion,
    n.registros_total_nivel,
    -- Total del período para calcular porcentaje
    SUM(n.registros_total_nivel) OVER (
        PARTITION BY n.trimestre,
        n.tipo_prestacion
    ) AS total_registros_periodo,
    -- Porcentaje por nivel
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
    -- Dimensión temporal
    (SUBSTRING(n.trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(n.trimestre, 7, 1)::INT AS periodo_orden
FROM nivel_atencion_trimestre n;
-- -----------------------------------------------------------------
-- 5. Mapa de disponibilidad de indicadores
-- Muestra qué indicadores tienen datos en cada período.
-- Útil en Power BI para marcar visualmente los datos faltantes
-- y evitar interpretaciones erróneas de valores nulos.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_disponibilidad_indicadores AS
SELECT l.trimestre,
    l.tipo_prestacion,
    -- Cobertura de SS (¿están los 27+ esperados?)
    COUNT(*) AS n_ss_cargados,
    -- Disponibilidad de indicadores principales
    -- TRUE = al menos 1 SS tiene el dato en este período
    BOOL_OR(l.mediana_dias IS NOT NULL) AS mediana_disponible,
    BOOL_OR(l.personas_espera IS NOT NULL) AS personas_ss_disponible,
    BOOL_OR(
        l.reg_24a36m IS NOT NULL
        OR l.reg_mayor_36m IS NOT NULL
    ) AS antiguedad_disponible,
    BOOL_OR(l.reg_24a36m IS NOT NULL) AS tramo_24_36m_disponible,
    BOOL_OR(l.reg_mayor_36m IS NOT NULL) AS tramo_mayor_36m_disponible,
    -- Disponibilidad en tablas relacionadas
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
    -- Orden temporal
    (SUBSTRING(l.trimestre, 1, 4)::INT - 2021) * 4 + SUBSTRING(l.trimestre, 7, 1)::INT AS periodo_orden
FROM listas_espera_ss_trimestre l
GROUP BY l.trimestre,
    l.tipo_prestacion
ORDER BY l.trimestre,
    l.tipo_prestacion;