-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/transformations/normalize_services.sql
-- Descripción: Segunda pasada de normalización de ss_id por coincidencia
--              parcial (ILIKE). Actúa como red de seguridad para variantes
--              no previstas en el catálogo exacto de catalogos.py.
--
-- NOTA ARQUITECTURAL:
--   La normalización por coincidencia exacta (antes un CTE hardcodeado
--   en este archivo) fue migrada a execute_catalog_normalization() en
--   run_transformations.py. Esa función lee SS_ID_MAP directamente de
--   catalogos.py, garantizando una única fuente de verdad.
--   Este archivo solo ejecuta el paso 2 (ILIKE) como fallback para
--   variantes que no figuren en SS_ID_MAP.
--
-- Idempotente: filas ya normalizadas no cumplen el WHERE de exclusión.
-- Ejecución  : siempre después de execute_catalog_normalization().
-- =================================================================
UPDATE listas_espera_ss_trimestre
SET ss_id = CASE
        -- ── Metropolitana (orden importa: Sur Oriente antes que Sur y Oriente) ─
        WHEN ss_id ILIKE '%metropolitano sur oriente%' THEN 'SS Metropolitano Sur Oriente'
        WHEN ss_id ILIKE '%metropolitano norte%' THEN 'SS Metropolitano Norte'
        WHEN ss_id ILIKE '%metropolitano occidente%' THEN 'SS Metropolitano Occidente'
        WHEN ss_id ILIKE '%metropolitano central%' THEN 'SS Metropolitano Central'
        WHEN ss_id ILIKE '%metropolitano oriente%'
        AND ss_id NOT ILIKE '%sur%' THEN 'SS Metropolitano Oriente'
        WHEN ss_id ILIKE '%metropolitano sur%'
        AND ss_id NOT ILIKE '%oriente%' THEN 'SS Metropolitano Sur' -- ── Araucanía ─────────────────────────────────────────────────────────
        WHEN ss_id ILIKE '%araucan%norte%' THEN 'SS Araucanía Norte'
        WHEN ss_id ILIKE '%araucan%sur%' THEN 'SS Araucanía Sur' -- ── Otros con ambigüedad baja ─────────────────────────────────────────
        WHEN ss_id ILIKE '%reloncav%' THEN 'SS Del Reloncaví'
        WHEN ss_id ILIKE '%biob%' THEN 'SS Biobío'
        WHEN ss_id ILIKE '%higgins%' THEN 'SS O''Higgins'
        WHEN ss_id ILIKE '%parinacota%'
        OR ss_id ILIKE '%arica%' THEN 'SS Arica y Parinacota'
        WHEN ss_id ILIKE '%iquique%' THEN 'SS Tarapacá'
        WHEN ss_id ILIKE '%valdivia%'
        OR ss_id ILIKE '%los r%os%' THEN 'SS Los Ríos'
        WHEN ss_id ILIKE '%concepci%' THEN 'SS Concepción'
        ELSE ss_id
    END,
    observaciones = COALESCE(observaciones || ' | ', '') || 'ss_id normalizado por coincidencia parcial ILIKE (fallback)',
    updated_at = NOW()
WHERE ss_id NOT IN (
        'SS Arica y Parinacota',
        'SS Tarapacá',
        'SS Antofagasta',
        'SS Atacama',
        'SS Coquimbo',
        'SS Viña del Mar - Quillota',
        'SS Valparaíso - San Antonio',
        'SS Aconcagua',
        'SS Metropolitano Norte',
        'SS Metropolitano Occidente',
        'SS Metropolitano Central',
        'SS Metropolitano Oriente',
        'SS Metropolitano Sur',
        'SS Metropolitano Sur Oriente',
        'SS O''Higgins',
        'SS Maule',
        'SS Ñuble',
        'SS Concepción',
        'SS Arauco',
        'SS Talcahuano',
        'SS Biobío',
        'SS Araucanía Norte',
        'SS Araucanía Sur',
        'SS Los Ríos',
        'SS Osorno',
        'SS Del Reloncaví',
        'SS Chiloé',
        'SS Aysén',
        'SS Magallanes'
    );