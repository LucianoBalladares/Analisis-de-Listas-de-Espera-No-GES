-- =================================================================
-- Migración : 001_fix_ss_del_maule.sql  (v2 — fix sintaxis RAISE)
-- Descripción: Corrige el nombre canónico SS Maule → SS Del Maule.
--
-- Ejecución:
--   psql -U postgres -d listas_espera_ges -f migration/001_fix_ss_del_maule.sql
-- =================================================================
BEGIN;
-- -----------------------------------------------------------------
-- Paso 0: Verificación de conflictos UNIQUE antes de migrar
-- -----------------------------------------------------------------
DO $$
DECLARE conflictos INT;
BEGIN
SELECT COUNT(*) INTO conflictos
FROM listas_espera_ss_trimestre a
WHERE a.ss_id = 'SS Maule'
    AND EXISTS (
        SELECT 1
        FROM listas_espera_ss_trimestre b
        WHERE b.ss_id = 'SS Del Maule'
            AND b.trimestre = a.trimestre
            AND b.tipo_prestacion = a.tipo_prestacion
    );
IF conflictos > 0 THEN RAISE EXCEPTION 'Conflicto UNIQUE: % fila(s) ya existen como SS Del Maule en el mismo periodo. Revisar manualmente.',
conflictos;
END IF;
RAISE NOTICE 'Verificacion OK: sin conflictos. Procediendo con la migracion.';
END;
$$;
-- -----------------------------------------------------------------
-- Paso 1: Corregir ss_id en listas_espera_ss_trimestre
-- -----------------------------------------------------------------
UPDATE listas_espera_ss_trimestre
SET ss_id = 'SS Del Maule',
    observaciones = COALESCE(observaciones || ' | ', '') || 'ss_id corregido por migracion 001: SS Maule -> SS Del Maule (nombre oficial Glosa 06)',
    updated_at = NOW()
WHERE ss_id = 'SS Maule';
-- -----------------------------------------------------------------
-- Paso 2: Reporte final
-- -----------------------------------------------------------------
DO $$
DECLARE n_corregidos INT;
n_residuales INT;
BEGIN
SELECT COUNT(*) INTO n_corregidos
FROM listas_espera_ss_trimestre
WHERE ss_id = 'SS Del Maule'
    AND observaciones LIKE '%migracion 001%';
SELECT COUNT(*) INTO n_residuales
FROM listas_espera_ss_trimestre
WHERE ss_id = 'SS Maule';
RAISE NOTICE 'Resultado: % registros corregidos a SS Del Maule, % con nombre anterior sin corregir.',
n_corregidos,
n_residuales;
END;
$$;
SELECT ss_id,
    COUNT(*) AS total_registros,
    COUNT(DISTINCT trimestre) AS trimestres,
    COUNT(DISTINCT tipo_prestacion) AS tipos_prestacion
FROM listas_espera_ss_trimestre
WHERE ss_id IN ('SS Maule', 'SS Del Maule')
GROUP BY ss_id
ORDER BY ss_id;
COMMIT;