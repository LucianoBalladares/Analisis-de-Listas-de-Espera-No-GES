-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/views/dashboard_views.sql
-- Descripción: Vistas optimizadas para consumo en Power BI
--
-- Ejecución : psql -U <usuario> -d <base> -f sql/views/dashboard_views.sql
-- Orden     : Ejecutar después del esquema completo (tablas + constraints)
--
-- Vistas incluidas:
--   v_dim_trimestre                → dimensión temporal para slicers
--   v_listas_espera_enriquecido    → tabla de hechos principal con métricas derivadas
--   v_nivel_atencion_distribucion  → % de demanda por nivel de atención
--   v_pct_nivel_terciario          → proporción de demanda en nivel terciario por período
--   v_disponibilidad_indicadores   → mapa de disponibilidad de datos por período
-- =================================================================
-- -----------------------------------------------------------------
-- 1. Dimensión temporal
-- Cubre todos los trimestres presentes en cualquiera de las 3 tablas.
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
    SUBSTRING(trimestre, 1, 4)::INT * 4 + SUBSTRING(trimestre, 7, 1)::INT AS periodo_orden,
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
-- pct_mayor_24m: devuelve NULL si cualquiera de los dos tramos es NULL.
-- reg_24a36m y reg_mayor_36m son tramos mutuamente excluyentes:
--   reg_24a36m    → registros con entre 24 y 36 meses de espera
--   reg_mayor_36m → registros con más de 36 meses de espera
--   Su suma representa el total de registros con más de 24 meses.
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
-- 3. Distribución por nivel de atención
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
    SUBSTRING(n.trimestre, 1, 4)::INT * 4 + SUBSTRING(n.trimestre, 7, 1)::INT AS periodo_orden
FROM nivel_atencion_trimestre n;
-- -----------------------------------------------------------------
-- 4. Concentración en nivel terciario
-- Proporción de registros en nivel terciario sobre el total nacional
-- por trimestre y tipo de prestación. Usado como proxy de
-- fragmentación funcional de la red asistencial.
--
-- Valores posibles de nivel_atencion: 'Primario', 'Secundario', 'Terciario'.
-- Si validacion.py detecta valores fuera de este catálogo, reportar en
-- check_niveles_atencion antes de confiar en esta vista.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_pct_nivel_terciario AS
SELECT trimestre,
    tipo_prestacion,
    ROUND(
        SUM(registros_total_nivel) FILTER (
            WHERE nivel_atencion = 'Terciario'
        ) / NULLIF(SUM(registros_total_nivel), 0) * 100,
        1
    ) AS pct_nivel_terciario,
    SUM(registros_total_nivel) FILTER (
        WHERE nivel_atencion = 'Primario'
    ) AS registros_primario,
    SUM(registros_total_nivel) FILTER (
        WHERE nivel_atencion = 'Secundario'
    ) AS registros_secundario,
    SUM(registros_total_nivel) FILTER (
        WHERE nivel_atencion = 'Terciario'
    ) AS registros_terciario,
    SUM(registros_total_nivel) AS registros_total,
    SUBSTRING(trimestre, 1, 4)::INT * 4 + SUBSTRING(trimestre, 7, 1)::INT AS periodo_orden
FROM nivel_atencion_trimestre
GROUP BY trimestre,
    tipo_prestacion;
-- -----------------------------------------------------------------
-- 5. Mapa de disponibilidad de indicadores
-- Muestra qué indicadores tienen datos en cada período.
-- Útil para marcar visualmente datos faltantes en Power BI.
--
-- CAMBIO respecto a la versión anterior de esta vista:
--   Se añaden columnas n_ss_con_* / n_ss_sin_* para exponer la
--   disponibilidad a nivel de Servicio de Salud, no solo como
--   booleano agregado de período.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_disponibilidad_indicadores AS
SELECT l.trimestre,
    l.tipo_prestacion,
    COUNT(*) AS n_ss_cargados,
    -- ── Disponibilidad booleana por indicador ─────────────────────
    -- TRUE = al menos 1 SS tiene el dato en ese período
    BOOL_OR(l.mediana_dias IS NOT NULL) AS mediana_disponible,
    BOOL_OR(l.promedio_dias IS NOT NULL) AS promedio_disponible,
    BOOL_OR(l.asimetria IS NOT NULL) AS asimetria_disponible,
    BOOL_OR(l.personas_espera IS NOT NULL) AS personas_ss_disponible,
    BOOL_OR(l.registros_espera IS NOT NULL) AS registros_espera_disponible,
    BOOL_OR(l.reg_24a36m IS NOT NULL) AS tramo_24_36m_disponible,
    BOOL_OR(l.reg_mayor_36m IS NOT NULL) AS tramo_mayor_36m_disponible,
    BOOL_OR(
        l.reg_24a36m IS NOT NULL
        AND l.reg_mayor_36m IS NOT NULL
    ) AS antiguedad_completa_disponible,
    -- ── Conteos de SS con/sin dato (granularidad para filtros) ────
    COUNT(*) FILTER (
        WHERE l.mediana_dias IS NOT NULL
    ) AS n_ss_con_mediana,
    COUNT(*) FILTER (
        WHERE l.mediana_dias IS NULL
    ) AS n_ss_sin_mediana,
    COUNT(*) FILTER (
        WHERE l.personas_espera IS NOT NULL
    ) AS n_ss_con_personas,
    COUNT(*) FILTER (
        WHERE l.personas_espera IS NULL
    ) AS n_ss_sin_personas,
    COUNT(*) FILTER (
        WHERE l.registros_espera IS NOT NULL
    ) AS n_ss_con_registros,
    COUNT(*) FILTER (
        WHERE l.registros_espera IS NULL
    ) AS n_ss_sin_registros,
    COUNT(*) FILTER (
        WHERE l.reg_24a36m IS NOT NULL
            AND l.reg_mayor_36m IS NOT NULL
    ) AS n_ss_con_antiguedad,
    COUNT(*) FILTER (
        WHERE l.reg_24a36m IS NULL
            OR l.reg_mayor_36m IS NULL
    ) AS n_ss_sin_antiguedad,
    -- ── Tablas complementarias ────────────────────────────────────
    EXISTS (
        SELECT 1
        FROM personas_nacional_trimestre p
        WHERE p.trimestre = l.trimestre
            AND p.tipo_prestacion = l.tipo_prestacion
            AND p.personas_total IS NOT NULL -- valor efectivamente disponible
    ) AS personas_nacional_disponible,
    EXISTS (
        SELECT 1
        FROM nivel_atencion_trimestre na
        WHERE na.trimestre = l.trimestre
            AND na.tipo_prestacion = l.tipo_prestacion
            AND na.registros_total_nivel IS NOT NULL -- FIX M1: valor efectivamente disponible
    ) AS nivel_atencion_disponible,
    -- ── Orden temporal ────────────────────────────────────────────
    SUBSTRING(l.trimestre, 1, 4)::INT * 4 + SUBSTRING(l.trimestre, 7, 1)::INT AS periodo_orden
FROM listas_espera_ss_trimestre l
GROUP BY l.trimestre,
    l.tipo_prestacion
ORDER BY l.trimestre,
    l.tipo_prestacion;
-- -----------------------------------------------------------------
-- 6. Dimensión de tipos de prestación
-- Tabla de dimensión para el modelo de datos de Power BI.
-- Importar y conectar en relación 1→muchos con tipo_prestacion de:
--   v_listas_espera_enriquecido, v_disponibilidad_indicadores,
--   v_pct_nivel_terciario
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_dim_tipo_prestacion AS
SELECT tipo_prestacion,
    CASE
        tipo_prestacion
        WHEN 'CNE' THEN 'Consulta Nueva de Especialidad'
        WHEN 'IQ' THEN 'Intervención Quirúrgica'
    END AS descripcion,
    CASE
        tipo_prestacion
        WHEN 'CNE' THEN 1
        WHEN 'IQ' THEN 2
    END AS orden_display
FROM (
        VALUES ('CNE'),
            ('IQ')
    ) AS t(tipo_prestacion);