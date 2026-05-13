-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/transformations/normalize_services.sql
-- Descripción: Estandarización de nombres de Servicios de Salud
--
-- Catálogo vigente: 29 Servicios de Salud según última Glosa 06.
-- Nombres históricos cubiertos (datos desde 2021):
--   SS Arica / Arica            → SS Arica y Parinacota
--   SS Iquique / Iquique        → SS Tarapacá
--   SS Valdivia / Valdivia      → SS Los Ríos
--
-- Idempotente: después de la primera ejecución exitosa no hay
-- filas que cumplan las condiciones WHERE, por lo que no hay efecto.
-- =================================================================
-- -----------------------------------------------------------------
-- Lista canónica de los 29 SS vigentes.
-- Usada como referencia en los WHERE de exclusión.
-- -----------------------------------------------------------------
-- 'SS Arica y Parinacota', 'SS Tarapacá', 'SS Antofagasta',
-- 'SS Atacama', 'SS Coquimbo',
-- 'SS Viña del Mar - Quillota', 'SS Valparaíso - San Antonio', 'SS Aconcagua',
-- 'SS Metropolitano Norte', 'SS Metropolitano Occidente',
-- 'SS Metropolitano Central', 'SS Metropolitano Oriente',
-- 'SS Metropolitano Sur', 'SS Metropolitano Sur Oriente',
-- 'SS O''Higgins', 'SS Maule', 'SS Ñuble',
-- 'SS Concepción', 'SS Arauco', 'SS Talcahuano', 'SS Biobío',
-- 'SS Araucanía Norte', 'SS Araucanía Sur',
-- 'SS Los Ríos', 'SS Osorno', 'SS Del Reloncaví', 'SS Chiloé',
-- 'SS Aysén', 'SS Magallanes'
-- -----------------------------------------------------------------
-- 1. Correcciones exactas conocidas
--    Cubre prefijos largos de OCR, nombres históricos y variantes
--    de ortografía/abreviatura frecuentes.
-- -----------------------------------------------------------------
WITH correcciones (raw, estandar) AS (
    VALUES -- ── Nombres históricos (renombres desde 2021) ─────────────
        (
            'SS Arica',
            'SS Arica y Parinacota'
        ),
        (
            'Arica',
            'SS Arica y Parinacota'
        ),
        (
            'SS Iquique',
            'SS Tarapacá'
        ),
        (
            'Iquique',
            'SS Tarapacá'
        ),
        (
            'SS Valdivia',
            'SS Los Ríos'
        ),
        (
            'Valdivia',
            'SS Los Ríos'
        ),
        -- ── Prefijo largo por OCR ─────────────────────────────────
        (
            'Servicio de Salud Arica y Parinacota',
            'SS Arica y Parinacota'
        ),
        (
            'Servicio de Salud Tarapacá',
            'SS Tarapacá'
        ),
        (
            'Servicio de Salud Antofagasta',
            'SS Antofagasta'
        ),
        (
            'Servicio de Salud Atacama',
            'SS Atacama'
        ),
        (
            'Servicio de Salud Coquimbo',
            'SS Coquimbo'
        ),
        (
            'Servicio de Salud Aconcagua',
            'SS Aconcagua'
        ),
        (
            'Servicio de Salud Maule',
            'SS Maule'
        ),
        (
            'Servicio de Salud Ñuble',
            'SS Ñuble'
        ),
        (
            'Servicio de Salud Concepción',
            'SS Concepción'
        ),
        (
            'Servicio de Salud Arauco',
            'SS Arauco'
        ),
        (
            'Servicio de Salud Talcahuano',
            'SS Talcahuano'
        ),
        (
            'Servicio de Salud Biobío',
            'SS Biobío'
        ),
        (
            'Servicio de Salud Los Ríos',
            'SS Los Ríos'
        ),
        (
            'Servicio de Salud Osorno',
            'SS Osorno'
        ),
        (
            'Servicio de Salud Chiloé',
            'SS Chiloé'
        ),
        (
            'Servicio de Salud Aysén',
            'SS Aysén'
        ),
        (
            'Servicio de Salud Magallanes',
            'SS Magallanes'
        ),
        -- ── Compuestos con guión omitido por OCR ─────────────────
        (
            'SS Viña del Mar Quillota',
            'SS Viña del Mar - Quillota'
        ),
        (
            'SS Viña del MarQuillota',
            'SS Viña del Mar - Quillota'
        ),
        (
            'SS Valparaíso San Antonio',
            'SS Valparaíso - San Antonio'
        ),
        (
            'SS Valparaíso-San Antonio',
            'SS Valparaíso - San Antonio'
        ),
        (
            'SS Valparaiso San Antonio',
            'SS Valparaíso - San Antonio'
        ),
        (
            'Servicio de Salud Viña del Mar - Quillota',
            'SS Viña del Mar - Quillota'
        ),
        (
            'Servicio de Salud Valparaíso - San Antonio',
            'SS Valparaíso - San Antonio'
        ),
        -- ── Metropolitano (abreviaturas de OCR) ───────────────────
        (
            'SSMO Norte',
            'SS Metropolitano Norte'
        ),
        (
            'SS Metro Norte',
            'SS Metropolitano Norte'
        ),
        (
            'SS Metro Occidente',
            'SS Metropolitano Occidente'
        ),
        (
            'SS Metro Central',
            'SS Metropolitano Central'
        ),
        (
            'SS Metro Oriente',
            'SS Metropolitano Oriente'
        ),
        (
            'SS Metro Sur',
            'SS Metropolitano Sur'
        ),
        (
            'SS Metro Sur Oriente',
            'SS Metropolitano Sur Oriente'
        ),
        (
            'Servicio de Salud Metropolitano Norte',
            'SS Metropolitano Norte'
        ),
        (
            'Servicio de Salud Metropolitano Occidente',
            'SS Metropolitano Occidente'
        ),
        (
            'Servicio de Salud Metropolitano Central',
            'SS Metropolitano Central'
        ),
        (
            'Servicio de Salud Metropolitano Oriente',
            'SS Metropolitano Oriente'
        ),
        (
            'Servicio de Salud Metropolitano Sur',
            'SS Metropolitano Sur'
        ),
        (
            'Servicio de Salud Metropolitano Sur Oriente',
            'SS Metropolitano Sur Oriente'
        ),
        -- ── Araucanía ─────────────────────────────────────────────
        (
            'SS Araucania Norte',
            'SS Araucanía Norte'
        ),
        (
            'SS Araucania Sur',
            'SS Araucanía Sur'
        ),
        (
            'Servicio de Salud Araucanía Norte',
            'SS Araucanía Norte'
        ),
        (
            'Servicio de Salud Araucanía Sur',
            'SS Araucanía Sur'
        ),
        -- ── Biobío y variantes de ortografía ──────────────────────
        (
            'SS Biobio',
            'SS Biobío'
        ),
        (
            'SS Bio Bio',
            'SS Biobío'
        ),
        (
            'Servicio de Salud O''Higgins',
            'SS O''Higgins'
        ),
        (
            'SS O Higgins',
            'SS O''Higgins'
        ),
        (
            'SS OHiggins',
            'SS O''Higgins'
        ),
        (
            'SS Nuble',
            'SS Ñuble'
        ),
        -- ── Reloncaví ─────────────────────────────────────────────
        (
            'SS Reloncaví',
            'SS Del Reloncaví'
        ),
        (
            'SS Del Reloncavi',
            'SS Del Reloncaví'
        ),
        (
            'Servicio de Salud Del Reloncaví',
            'SS Del Reloncaví'
        )
)
UPDATE listas_espera_ss_trimestre AS l
SET ss_id = c.estandar,
    observaciones = COALESCE(l.observaciones || ' | ', '') || 'ss_id normalizado: ' || l.ss_id || ' → ' || c.estandar,
    updated_at = NOW()
FROM correcciones c
WHERE l.ss_id = c.raw
    AND l.ss_id <> c.estandar;
-- -----------------------------------------------------------------
-- 2. Normalización por coincidencia parcial (segunda pasada)
--    Para variantes no cubiertas por la tabla exacta.
--    Solo actúa cuando la coincidencia es inequívoca.
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET ss_id = CASE
        WHEN ss_id ILIKE '%metropolitano norte%' THEN 'SS Metropolitano Norte'
        WHEN ss_id ILIKE '%metropolitano occidente%' THEN 'SS Metropolitano Occidente'
        WHEN ss_id ILIKE '%metropolitano central%' THEN 'SS Metropolitano Central'
        WHEN ss_id ILIKE '%metropolitano sur oriente%' THEN 'SS Metropolitano Sur Oriente'
        WHEN ss_id ILIKE '%metropolitano oriente%'
        AND ss_id NOT ILIKE '%sur%' THEN 'SS Metropolitano Oriente'
        WHEN ss_id ILIKE '%metropolitano sur%'
        AND ss_id NOT ILIKE '%oriente%' THEN 'SS Metropolitano Sur'
        WHEN ss_id ILIKE '%reloncav%' THEN 'SS Del Reloncaví'
        WHEN ss_id ILIKE '%araucan%norte%' THEN 'SS Araucanía Norte'
        WHEN ss_id ILIKE '%araucan%sur%' THEN 'SS Araucanía Sur'
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
    observaciones = COALESCE(observaciones || ' | ', '') || 'ss_id normalizado por coincidencia parcial',
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
-- -----------------------------------------------------------------
