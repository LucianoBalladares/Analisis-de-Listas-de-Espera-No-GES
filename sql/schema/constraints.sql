-- =================================================================
-- Proyecto : Análisis de Listas de Espera NO GES - Chile
-- Archivo  : sql/schema/constraints.sql
-- Descripción: Primary keys, unique keys y check constraints
--
-- Ejecución: psql -U <usuario> -d <base> -f sql/schema/constraints.sql
-- Debe ejecutarse DESPUÉS de create_tables.sql
-- =================================================================
-- -----------------------------------------------------------------
-- PRIMARY KEYS
-- -----------------------------------------------------------------
ALTER TABLE listas_espera_ss_trimestre
ADD CONSTRAINT pk_listas_espera PRIMARY KEY (id);
ALTER TABLE personas_nacional_trimestre
ADD CONSTRAINT pk_personas_nacional PRIMARY KEY (id);
ALTER TABLE nivel_atencion_trimestre
ADD CONSTRAINT pk_nivel_atencion PRIMARY KEY (id);
-- -----------------------------------------------------------------
-- UNIQUE KEYS (clave natural de negocio)
-- Permite UPSERT idempotente desde el pipeline
-- -----------------------------------------------------------------
ALTER TABLE listas_espera_ss_trimestre
ADD CONSTRAINT uq_listas_espera_clave UNIQUE (ss_id, trimestre, tipo_prestacion);
ALTER TABLE personas_nacional_trimestre
ADD CONSTRAINT uq_personas_nacional_clave UNIQUE (trimestre, tipo_prestacion);
ALTER TABLE nivel_atencion_trimestre
ADD CONSTRAINT uq_nivel_atencion_clave UNIQUE (nivel_atencion, trimestre, tipo_prestacion);
-- -----------------------------------------------------------------
-- CHECK CONSTRAINTS
-- -----------------------------------------------------------------
-- Formato de trimestre: YYYY_T1 a YYYY_T4
ALTER TABLE listas_espera_ss_trimestre
ADD CONSTRAINT chk_listas_trimestre CHECK (trimestre ~ '^\d{4}_T[1-4]$');
ALTER TABLE personas_nacional_trimestre
ADD CONSTRAINT chk_personas_trimestre CHECK (trimestre ~ '^\d{4}_T[1-4]$');
ALTER TABLE nivel_atencion_trimestre
ADD CONSTRAINT chk_nivel_trimestre CHECK (trimestre ~ '^\d{4}_T[1-4]$');
-- Tipo de prestación válido
ALTER TABLE listas_espera_ss_trimestre
ADD CONSTRAINT chk_listas_tipo_prestacion CHECK (tipo_prestacion IN ('CNE', 'IQ'));
ALTER TABLE personas_nacional_trimestre
ADD CONSTRAINT chk_personas_tipo_prestacion CHECK (tipo_prestacion IN ('CNE', 'IQ'));
ALTER TABLE nivel_atencion_trimestre
ADD CONSTRAINT chk_nivel_tipo_prestacion CHECK (tipo_prestacion IN ('CNE', 'IQ'));
-- Valores numéricos no negativos
ALTER TABLE listas_espera_ss_trimestre
ADD CONSTRAINT chk_listas_valores_positivos CHECK (
        (
            personas_espera IS NULL
            OR personas_espera >= 0
        )
        AND (
            registros_espera IS NULL
            OR registros_espera >= 0
        )
        AND (
            mediana_dias IS NULL
            OR mediana_dias >= 0
        )
        AND (
            promedio_dias IS NULL
            OR promedio_dias >= 0
        )
        AND (
            reg_24a36m IS NULL
            OR reg_24a36m >= 0
        )
        AND (
            reg_mayor_36m IS NULL
            OR reg_mayor_36m >= 0
        )
    );
ALTER TABLE personas_nacional_trimestre
ADD CONSTRAINT chk_personas_positivo CHECK (
        personas_total IS NULL
        OR personas_total >= 0
    );
ALTER TABLE nivel_atencion_trimestre
ADD CONSTRAINT chk_nivel_positivo CHECK (
        registros_total_nivel IS NULL
        OR registros_total_nivel >= 0
    );
-- Estado del pipeline válido
ALTER TABLE pipeline_runs
ADD CONSTRAINT chk_pipeline_estado CHECK (estado IN ('ok', 'warning', 'error'));