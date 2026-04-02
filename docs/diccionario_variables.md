# Diccionario de Variables

## 1. Descripción general

Este documento describe las variables contenidas en el dataset maestro:

`listas_espera_ss_trimestre.csv`

El dataset tiene como unidad de análisis:

> **Servicio de Salud × Trimestre × Tipo de prestación**

Incluye variables de resultado, variables estructurales y variables de control, derivadas de fuentes administrativas oficiales (Glosa 06 – MINSAL).

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
  - Debe estar estandarizado (sin variaciones de nombre).

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
  - `Cirugia` (Intervención Quirúrgica)
- **Fuente:** Glosa 06
- **Notas:**
  - Permite segmentar el análisis por tipo de atención.
  - Las variables disponibles pueden diferir entre categorías.

---

## 3. Variables de resultado (outcomes)

### 3.1 `mediana_dias`

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

- **Definición:** Promedio de días de espera.
- **Tipo:** Numérica continua
- **Unidad:** Días
- **Fuente:** Glosa 06
- **Uso:**
  - Complementa la mediana.
  - Permite evaluar asimetría de la distribución.

---

### 3.3 `velocidad_recuperacion` *(variable derivada)*

- **Definición:** Cambio en la mediana de días de espera entre trimestres consecutivos.
- **Tipo:** Numérica continua
- **Cálculo:**

  velocidad = mediana(t) – mediana(t-1)

- **Interpretación:**
  - Valores negativos → reducción de la espera (mejor desempeño)
  - Valores positivos → aumento de la espera
- **Notas:**
  - No forma parte del dataset crudo.
  - Se calcula en Power BI o herramientas analíticas.

---

### 3.4 `pct_mayor_24m`

- **Definición:** Porcentaje de registros con tiempo de espera superior a 24 meses.
- **Tipo:** Numérica continua
- **Unidad:** Porcentaje (0–100)
- **Fuente:** Glosa 06 (tramos de antigüedad)
- **Interpretación:**
  - Proxy de riesgo sanitario acumulado.
- **Limitaciones:**
  - No disponible en todos los periodos.

---

### 3.5 `pct_mayor_36m`

- **Definición:** Porcentaje de registros con tiempo de espera superior a 36 meses.
- **Tipo:** Numérica continua
- **Unidad:** Porcentaje (0–100)
- **Fuente:** Glosa 06
- **Interpretación:**
  - Indicador de casos extremos (cola larga severa).
- **Limitaciones:**
  - Disponibilidad variable entre años.

---

## 4. Variables independientes (estructurales)

### 4.1 `pct_nivel_terciario`

- **Definición:** Proporción de la demanda en lista de espera concentrada en establecimientos de nivel terciario.
- **Tipo:** Numérica continua
- **Unidad:** Porcentaje (0–100)
- **Fuente:** Glosa 06 (distribución por nivel de atención)
- **Interpretación:**
  - Proxy de **fragmentación funcional de la red asistencial**.
  - Valores altos sugieren sobrecarga del nivel de alta complejidad.
- **Limitaciones:**
  - En algunos periodos solo disponible a nivel nacional.

---

## 5. Variables de control

### 5.1 `personas_espera`

- **Definición:** Número de personas únicas en lista de espera activa.
- **Tipo:** Numérica discreta
- **Fuente:** Glosa 06
- **Uso:**
  - Control por tamaño de la demanda.
- **Limitaciones:**
  - No disponible para CNE en algunos periodos.

---

### 5.2 `registros_espera`

- **Definición:** Número total de registros en lista de espera.
- **Tipo:** Numérica discreta
- **Interpretación:**
  - Puede diferir de personas por duplicidad de registros.
- **Uso:**
  - Análisis complementario del volumen.

---

### 5.3 `asimetria`

- **Definición:** Diferencia entre promedio y mediana de días de espera.
- **Tipo:** Numérica continua
- **Cálculo:**

  asimetria = promedio_dias – mediana_dias

- **Interpretación:**
  - Valores altos → presencia de cola larga
  - Valores cercanos a 0 → distribución más simétrica
- **Rol:**
  - Proxy de dispersión de tiempos de espera.

---

## 6. Variables adicionales

### 6.1 `fuente`

- **Definición:** Origen del dato.
- **Tipo:** Texto
- **Valores posibles:**
  - "Glosa 06"
  - "SIGTE" (si aplica en futuras versiones)
- **Uso:**
  - Trazabilidad del dato.

---

### 6.2 `observaciones`

- **Definición:** Notas sobre calidad, disponibilidad o particularidades del dato.
- **Tipo:** Texto
- **Uso:**
  - Documentación de excepciones.
  - Registro de decisiones metodológicas específicas.

---

## 7. Consideraciones generales

- Los valores faltantes se codifican como **NA**.
- No se realizan imputaciones.
- La disponibilidad de variables varía por periodo y tipo de prestación.
- El dataset prioriza consistencia longitudinal sobre completitud total.

---

## 8. Relación con documentación adicional

Para comprender completamente el dataset, se recomienda revisar:

- `docs/metodologia.md` → diseño del estudio y estrategia analítica  
- `docs/limitaciones.md` → disponibilidad de datos por periodo  

---