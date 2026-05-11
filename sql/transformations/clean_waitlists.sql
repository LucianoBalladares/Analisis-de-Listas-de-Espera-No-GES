-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/transformations/clean_waitlists.sql
-- Descripción: Correcciones y completitud sobre listas_espera_ss_trimestre
--
-- Todas las operaciones son idempotentes: re-ejecutar no produce
-- cambios adicionales si los datos ya están corregidos.
--
-- Orden de ejecución: después de excel_a_sql.py, antes de las vistas.
-- =================================================================
-- -----------------------------------------------------------------
-- 1. Recalcular asimetria donde es NULL pero los componentes existen
--    Ocurre cuando promedio o mediana se agregaron en una corrección
--    posterior a la carga original.
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET asimetria = ROUND(promedio_dias - mediana_dias, 1),
    updated_at = NOW()
WHERE asimetria IS NULL
    AND promedio_dias IS NOT NULL
    AND mediana_dias IS NOT NULL;
-- -----------------------------------------------------------------
-- 2. Asignar fuente por defecto donde quedó NULL en la ingesta
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET fuente = 'Glosa 06',
    updated_at = NOW()
WHERE fuente IS NULL;
-- -----------------------------------------------------------------
-- 3. Normalizar tipo_prestacion como capa de seguridad
--    En condiciones normales el ingester ya lo hace; este paso
--    corrige cualquier valor que haya eludido la validación.
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET tipo_prestacion = CASE
        WHEN UPPER(TRIM(tipo_prestacion)) = 'CNE' THEN 'CNE'
        WHEN UPPER(TRIM(tipo_prestacion)) IN (
            'IQ',
            'CIRUGIA',
            'CIRUGÍA',
            'INTERVENCION QUIRURGICA',
            'INTERVENCIÓN QUIRÚRGICA'
        ) THEN 'IQ'
        ELSE tipo_prestacion
    END,
    updated_at = NOW()
WHERE tipo_prestacion NOT IN ('CNE', 'IQ');
-- -----------------------------------------------------------------
-- 4. Corregir asimetría inconsistente
--    Si asimetria difiere en más de 1 día del valor calculado,
--    se recalcula. Diferencias pequeñas pueden ser redondeo del OCR.
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET asimetria = ROUND(promedio_dias - mediana_dias, 1),
    observaciones = COALESCE(observaciones || ' | ', '') || 'asimetria recalculada por transformacion',
    updated_at = NOW()
WHERE promedio_dias IS NOT NULL
    AND mediana_dias IS NOT NULL
    AND asimetria IS NOT NULL
    AND ABS(
        asimetria - ROUND(promedio_dias - mediana_dias, 1)
    ) > 1.0;
-- -----------------------------------------------------------------
-- 5. Detectar y marcar registros donde la suma de tramos de
--    antigüedad supera los registros totales (incoherencia real).
--    reg_24a36m y reg_mayor_36m son tramos independientes (exclusivos):
--    24–36m y >36m respectivamente. No hay relación de orden entre ellos.
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET observaciones = COALESCE(observaciones || ' | ', '') || 'ALERTA: suma de tramos de antigüedad supera registros_espera',
    updated_at = NOW()
WHERE reg_24a36m IS NOT NULL
    AND reg_mayor_36m IS NOT NULL
    AND registros_espera IS NOT NULL
    AND (reg_24a36m + reg_mayor_36m) > registros_espera
    AND (
        observaciones IS NULL
        OR observaciones NOT LIKE '%suma de tramos%'
    );
-- -----------------------------------------------------------------
-- Reporte de estado post-transformación
-- -----------------------------------------------------------------
SELECT 'listas_espera_ss_trimestre' AS tabla,
    COUNT(*) AS total_registros,
    COUNT(mediana_dias) AS con_mediana,
    COUNT(asimetria) AS con_asimetria,
    COUNT(personas_espera) AS con_personas,
    COUNT(*) FILTER (
        WHERE observaciones LIKE '%ALERTA%'
    ) AS con_alertas
FROM listas_espera_ss_trimestre;