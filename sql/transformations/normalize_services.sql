-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/transformations/normalize_services.sql
-- Descripción: Estandarización de nombres de Servicios de Salud
--
-- Contexto: el ingester normaliza ss_id durante la carga, pero
-- variantes de OCR no previstas pueden pasar sin ser reconocidas
-- (el ingester las guarda con el valor original como fallback).
-- Este script aplica una segunda capa de normalización.
--
-- Idempotente: después de la primera ejecución exitosa, no hay
-- filas que cumplan las condiciones WHERE, por lo que no hay efecto.
-- =================================================================
-- -----------------------------------------------------------------
-- 1. Tabla temporal de correcciones conocidas
--    Extender esta lista cuando aparezcan nuevas variantes de OCR.
--    Formato: (valor_en_db, valor_estandar)
-- -----------------------------------------------------------------
WITH correcciones (raw, estandar) AS (
    VALUES -- Variantes con prefijo diferente
        (
            'Servicio de Salud Arica',
            'SS Arica'
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
            'Servicio de Salud Talcahuano',
            'SS Talcahuano'
        ),
        (
            'Servicio de Salud Valdivia',
            'SS Valdivia'
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
        -- Variantes compuestas (OCR omite guión o guión largo)
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
        -- Variantes Metropolitano
        (
            'SS Metropolitano Norte',
            'SS Metropolitano Norte'
        ),
        -- ya correcto
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
        -- Variantes del Sur
        (
            'SS Araucanía Norte',
            'SS Araucanía Norte'
        ),
        -- ya correcto
        (
            'SS Araucania Norte',
            'SS Araucanía Norte'
        ),
        (
            'SS Araucanía Sur',
            'SS Araucanía Sur'
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
        -- Biobío / Ñuble / O'Higgins
        (
            'SS Biobio',
            'SS Biobío'
        ),
        (
            'SS Bio Bio',
            'SS Biobío'
        ),
        (
            'SS Nuble',
            'SS Ñuble'
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
            'Servicio de Salud O''Higgins',
            'SS O''Higgins'
        ),
        (
            'Servicio de Salud Biobío',
            'SS Biobío'
        ),
        (
            'Servicio de Salud Ñuble',
            'SS Ñuble'
        ),
        -- Reloncaví
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
-- evitar re-procesar los ya correctos
-- -----------------------------------------------------------------
-- 2. Normalización por coincidencia parcial (segunda pasada)
--    Para variantes que no están en la tabla de correcciones exactas
--    pero contienen palabras clave únicas.
--    Solo actualiza cuando la coincidencia es inequívoca.
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET ss_id = CASE
        WHEN ss_id ILIKE '%metropolitano norte%' THEN 'SS Metropolitano Norte'
        WHEN ss_id ILIKE '%metropolitano occidente%' THEN 'SS Metropolitano Occidente'
        WHEN ss_id ILIKE '%metropolitano central%' THEN 'SS Metropolitano Central'
        WHEN ss_id ILIKE '%metropolitano oriente%'
        AND ss_id NOT ILIKE '%sur%' THEN 'SS Metropolitano Oriente'
        WHEN ss_id ILIKE '%metropolitano sur oriente%' THEN 'SS Metropolitano Sur Oriente'
        WHEN ss_id ILIKE '%metropolitano sur%'
        AND ss_id NOT ILIKE '%oriente%' THEN 'SS Metropolitano Sur'
        WHEN ss_id ILIKE '%reloncav%' THEN 'SS Del Reloncaví'
        WHEN ss_id ILIKE '%araucan%norte%' THEN 'SS Araucanía Norte'
        WHEN ss_id ILIKE '%araucan%sur%' THEN 'SS Araucanía Sur'
        WHEN ss_id ILIKE '%biob%' THEN 'SS Biobío'
        WHEN ss_id ILIKE '%higgins%' THEN 'SS O''Higgins'
        ELSE ss_id
    END,
    observaciones = COALESCE(observaciones || ' | ', '') || 'ss_id normalizado por coincidencia parcial',
    updated_at = NOW()
WHERE ss_id NOT IN (
        'SS Arica',
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
        'SS Biobío',
        'SS Talcahuano',
        'SS Araucanía Norte',
        'SS Araucanía Sur',
        'SS Valdivia',
        'SS Osorno',
        'SS Del Reloncaví',
        'SS Chiloé',
        'SS Aysén',
        'SS Magallanes'
    );
-- -----------------------------------------------------------------
-- Reporte: ss_id que siguen sin reconocer tras ambas pasadas
-- Un resultado vacío indica normalización completa.
-- -----------------------------------------------------------------
SELECT ss_id AS ss_id_no_reconocido,
    COUNT(*) AS n_registros,
    STRING_AGG(
        DISTINCT trimestre,
        ', '
        ORDER BY trimestre
    ) AS trimestres
FROM listas_espera_ss_trimestre
WHERE ss_id NOT IN (
        'SS Arica',
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
        'SS Biobío',
        'SS Talcahuano',
        'SS Araucanía Norte',
        'SS Araucanía Sur',
        'SS Valdivia',
        'SS Osorno',
        'SS Del Reloncaví',
        'SS Chiloé',
        'SS Aysén',
        'SS Magallanes'
    )
GROUP BY ss_id
ORDER BY n_registros DESC;