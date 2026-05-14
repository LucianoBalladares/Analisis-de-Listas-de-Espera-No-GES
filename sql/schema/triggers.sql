-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/schema/triggers.sql
-- Descripción: Triggers para actualización automática de updated_at
--              en todas las tablas principales del esquema.
--
-- Ejecución: psql -U <usuario> -d <base> -f sql/schema/triggers.sql
-- Debe ejecutarse DESPUÉS de create_tables.sql
-- =================================================================
-- -----------------------------------------------------------------
-- Función compartida reutilizada por todos los triggers.
-- Actualiza updated_at al instante exacto del UPDATE, incluyendo
-- actualizaciones directas a la BD fuera del pipeline Python.
-- -----------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW();
RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- -----------------------------------------------------------------
-- listas_espera_ss_trimestre
-- -----------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_listas_espera_updated_at ON listas_espera_ss_trimestre;
CREATE TRIGGER trg_listas_espera_updated_at BEFORE
UPDATE ON listas_espera_ss_trimestre FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();
-- -----------------------------------------------------------------
-- personas_nacional_trimestre
-- -----------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_personas_nacional_updated_at ON personas_nacional_trimestre;
CREATE TRIGGER trg_personas_nacional_updated_at BEFORE
UPDATE ON personas_nacional_trimestre FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();
-- -----------------------------------------------------------------
-- nivel_atencion_trimestre
-- -----------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_nivel_atencion_updated_at ON nivel_atencion_trimestre;
CREATE TRIGGER trg_nivel_atencion_updated_at BEFORE
UPDATE ON nivel_atencion_trimestre FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();