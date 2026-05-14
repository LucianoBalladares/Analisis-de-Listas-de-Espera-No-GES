# Diccionario de Variables

## 1. Descripción general

Este documento describe las variables contenidas en el dataset maestro y sus derivadas.

La **tabla base** del proyecto es:

`listas_espera_ss_trimestre`

con unidad de análisis:

> **Servicio de Salud × Trimestre × Tipo de prestación**

Adicionalmente, la vista `v_listas_espera_enriquecido` extiende la tabla base con métricas calculadas (porcentajes de antigüedad, dimensiones temporales) listas para consumo en Power BI.

Todas las variables provienen de fuentes administrativas oficiales (Glosa 06 – MINSAL).

---

## 2. Variables identificatorias

### 2.1 `ss_id`

- **Definición:** Servicio de Salud responsable de la gestión de la lista de espera.
- **Tipo:** Categórica nominal
- **Ejemplo:** "SS Metropolitano Norte"
- **Fuente:** Glosa 06 (MINSAL)
- **Nivel:** Servicio de Salud
- **Notas:**
  - Se utiliza como clave principal para análisis comparativo.
  - Nombre estandarizado según catálogo vigente de 29 Servicios de Salud.
  - El catálogo canónico y sus alias de normalización están centralizados en `pipeline/config/catalogos.py`.

---

### 2.2 `trimestre`

- **Definición:** Periodo temporal de observación.
- **Tipo:** Categórica ordinal
- **Formato:** `YYYY_T#` (ej: 2024_T3)
- **Fuente:** Glosa 06
- **Notas:**
  - Permite análisis longitudinal.
  - Se recomienda tratar como variable ordenada en análisis temporal.

---

### 2.3 `tipo_prestacion`

- **Definición:** Tipo de prestación NO GES analizada.
- **Tipo:** Categórica nominal
- **Categorías:**
  - `CNE` (Consulta Nueva de Especialidad)
  - `IQ` (Intervención Quirúrgica)
- **Fuente:** Glosa 06
- **Notas:**
  - Las variables disponibles pueden diferir entre categorías.

---

## 3. Variables de resultado (outcomes)

### 3.1 `mediana_dias`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Mediana de días de espera de personas en lista activa.
- **Tipo:** Numérica continua
- **Unidad:** Días
- **Fuente:** Glosa 06 (tablas de tiempos de espera)
- **Interpretación:**
  - Indicador robusto del tiempo típico de espera.
  - Menos sensible a valores extremos que el promedio.
- **Limitaciones:**
  - No disponible en todos los periodos (ver `limitaciones.md`).

---

### 3.2 `promedio_dias`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Promedio de días de espera.
- **Tipo:** Numérica continua
- **Unidad:** Días
- **Fuente:** Glosa 06
- **Uso:**
  - Complementa la mediana.
  - Permite evaluar asimetría de la distribución.

---

### 3.3 `asimetria`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Diferencia entre promedio y mediana de días de espera.
- **Tipo:** Numérica continua
- **Cálculo:**

  asimetria = promedio_dias – mediana_dias

- **Interpretación:**
  - Valores altos → presencia de cola larga en la distribución de esperas.
  - Valores cercanos a 0 → distribución más simétrica.
- **Rol:**
  - Proxy de dispersión de tiempos de espera a nivel de Servicio de Salud.

---

### 3.4 `pct_mayor_24m`

- **Disponible en:** vista `v_listas_espera_enriquecido` (no en la tabla base)
- **Definición:** Porcentaje de registros con tiempo de espera superior a 24 meses.
- **Cálculo en vista:**

  `(reg_24a36m + reg_mayor_36m) / registros_espera × 100`

- **Nota importante:** `reg_24a36m` y `reg_mayor_36m` son **tramos mutuamente excluyentes**:
  - `reg_24a36m` → registros con entre 24 y 36 meses de espera
  - `reg_mayor_36m` → registros con más de 36 meses de espera
  - La suma de ambos representa el total de registros con más de 24 meses.
- **Retorna NULL** si cualquiera de los dos tramos o `registros_espera` es NULL.

---

### 3.5 `pct_mayor_36m`

- **Disponible en:** vista `v_listas_espera_enriquecido` (no en la tabla base)
- **Definición:** Porcentaje de registros con tiempo de espera superior a 36 meses.
- **Tipo:** Numérica continua
- **Unidad:** Porcentaje (0–100)
- **Cálculo en vista:**

  `reg_mayor_36m / registros_espera × 100`

- **Interpretación:**
  - Indicador de casos extremos (cola larga severa).
- **Limitaciones:**
  - Disponibilidad variable entre años (ver `limitaciones.md`).
  - Retorna NULL si `reg_mayor_36m` o `registros_espera` es NULL.

---

## 4. Variables independientes (estructurales)

### 4.1 `pct_nivel_terciario`

- **Disponible en:** vista `v_pct_nivel_terciario`
- **Definición:** Proporción de la demanda registrada en establecimientos de nivel terciario, sobre el total nacional de registros del período.
- **Tipo:** Numérica continua
- **Unidad:** Porcentaje (0–100)
- **Fuente:** Glosa 06 (distribución por nivel de atención), tabla `nivel_atencion_trimestre`
- **Interpretación:**
  - Proxy de **fragmentación funcional de la red asistencial**.
  - Valores altos sugieren sobrecarga del nivel de alta complejidad y menor resolución en niveles secundarios.
- **Limitaciones:**
  - Disponible principalmente a nivel nacional. No hay desagregación por Servicio de Salud en la mayoría de los periodos (ver `limitaciones.md`).
  - La vista asume que los valores de `nivel_atencion` corresponden exactamente a `'Primario'`, `'Secundario'` o `'Terciario'`. Si el OCR extrae variantes distintas, `validacion.py` lo reportará mediante `check_niveles_atencion`.

---

## 5. Variables de control

### 5.1 `personas_espera`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Número de personas únicas en lista de espera activa.
- **Tipo:** Numérica discreta (BIGINT)
- **Fuente:** Glosa 06
- **Uso:**
  - Control por tamaño de la demanda.
- **Limitaciones:**
  - No disponible para CNE en algunos periodos.

---

### 5.2 `registros_espera`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Número total de registros en lista de espera.
- **Tipo:** Numérica discreta (BIGINT)
- **Interpretación:**
  - Puede diferir de `personas_espera` por duplicidad de registros.
- **Uso:**
  - Análisis complementario del volumen y denominador para cálculos de antigüedad en `v_listas_espera_enriquecido`.
- **Notas:**
  - Si `registros_espera` es NULL para un período, `pct_mayor_24m` y `pct_mayor_36m` también serán NULL. Verificar disponibilidad en `v_disponibilidad_indicadores` (columna `registros_espera_disponible`).

---

## 6. Variables de antigüedad en registros

### 6.1 `reg_24a36m`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Registros con tiempo de espera entre 24 y 36 meses.
- **Tipo:** Numérica discreta (BIGINT)
- **Nota:** Tramo mutuamente excluyente con `reg_mayor_36m`.

### 6.2 `reg_mayor_36m`

- **Tabla:** `listas_espera_ss_trimestre`
- **Definición:** Registros con tiempo de espera superior a 36 meses.
- **Tipo:** Numérica discreta (BIGINT)
- **Nota:** Tramo mutuamente excluyente con `reg_24a36m`.

---

## 7. Variables adicionales

### 7.1 `fuente`

- **Definición:** Origen del dato.
- **Tipo:** Texto
- **Valores posibles:** `"Glosa 06"`
- **Uso:** Trazabilidad del dato.

---

### 7.2 `observaciones`

- **Definición:** Notas sobre calidad, disponibilidad o particularidades del dato.
- **Tipo:** Texto
- **Uso:**
  - Documentación de excepciones.
  - Registro de alertas generadas automáticamente por el pipeline (ej: `ALERTA: suma de tramos de antigüedad supera registros_espera`).
  - Registro de correcciones de normalización (ej: `ss_id normalizado: SS Arica → SS Arica y Parinacota`).

---

## 8. Consideraciones generales

- Los valores faltantes se codifican como **NULL** en la base de datos y como **NA** en los archivos CSV exportados.
- No se realizan imputaciones.
- La disponibilidad de variables varía por periodo y tipo de prestación.
- El dataset prioriza consistencia longitudinal sobre completitud total.
- Los campos de conteo (`personas_espera`, `registros_espera`, `reg_24a36m`, `reg_mayor_36m`, `personas_total`, `registros_total_nivel`) son de tipo `BIGINT` en PostgreSQL.

---

## 9. Relación con documentación adicional

Para comprender completamente el dataset, se recomienda revisar:

- `docs/metodologia.md` → diseño del estudio y estrategia analítica
- `docs/limitaciones.md` → disponibilidad de datos por periodo
- `docs/reglas_limpieza.md` → proceso de construcción del dataset
