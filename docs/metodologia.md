# Metodología

## 1. Diseño del estudio

Este estudio corresponde a un **análisis observacional, longitudinal y ecológico**, basado en datos administrativos agregados del sistema público de salud en Chile.

La unidad de análisis es el **Servicio de Salud**, evaluado en forma trimestral, lo que permite analizar la evolución temporal de indicadores de listas de espera NO GES.

El enfoque metodológico se centra en la **evaluación de la recuperación del sistema** entre el primer y último trimestre con mediana disponible, más que en una caracterización estática del nivel de espera.

---

## 2. Unidad de análisis

Cada observación del dataset corresponde a:

- Un **Servicio de Salud**
- Un **trimestre específico**
- Un **tipo de prestación**:
  - Consulta Nueva de Especialidad (CNE)
  - Intervención Quirúrgica

Esto define una estructura de datos de tipo:

> Servicio de Salud × Trimestre × Tipo de prestación

---

## 3. Fuentes de datos

### 3.1 Fuente principal

- **Glosa 06 – Ley de Presupuestos (MINSAL)**

Características:

- Datos oficiales de carácter público
- Periodicidad trimestral
- Nivel de agregación:
  - Nacional
  - Regional
  - Servicio de Salud

Contiene información sobre:

- Tiempos de espera (mediana, promedio)
- Volumen de casos (personas y registros)
- Distribución por nivel de atención
- Tramos de antigüedad

---

## 4. Construcción del dataset

### 4.1 Naturaleza de los datos

Las fuentes originales se encuentran mayoritariamente en formato:

- PDF
- Imágenes escaneadas

Por lo tanto, no constituyen bases de datos estructuradas directamente utilizables para análisis.

---

### 4.2 Proceso de reconstrucción

Se implementó un proceso de transformación en múltiples etapas:

1. **Extracción de información**
   - Aplicación de herramientas de OCR para convertir contenido en texto/tablas.
   - El OCR se configura explícitamente para no usar separadores de miles, garantizando que cualquier coma en los valores numéricos sea interpretada como separador decimal.

2. **Validación manual**
   - Verificación de 3 valores al azar por archivo contra el PDF original.
   - Corrección de errores derivados del OCR.

3. **Estructuración intermedia**
   - Organización de datos en archivos Excel por año y trimestre.
   - Homogeneización de nombres de variables y categorías.

4. **Consolidación**
   - Integración de archivos intermedios en una estructura única.
   - Estandarización de claves (Servicio de Salud, periodo, tipo de prestación).
   - El catálogo de los 29 Servicios de Salud vigentes y sus aliases de normalización están centralizados en `pipeline/config/catalogos.py`.

5. **Construcción del dataset maestro**
   - Generación de una tabla final con granularidad homogénea.
   - Manejo explícito de valores faltantes (NULL).

---

### 4.3 Principios aplicados

- **Trazabilidad:** cada dato puede vincularse a su fuente original.
- **Consistencia longitudinal:** priorización de variables comparables en el tiempo.
- **Transparencia:** documentación explícita de limitaciones y supuestos.

---

## 5. Definición de variables

### 5.1 Variables dependientes (outcomes)

#### Mediana de días de espera (`mediana_dias`)

- Indicador principal de tiempo de espera.
- Robusto frente a distribuciones asimétricas.

#### Delta de recuperación (análisis comparativo)

El análisis central del proyecto evalúa la magnitud del cambio en la mediana de espera entre el trimestre más antiguo y el más reciente con datos disponibles para cada Servicio de Salud.

Este cálculo se implementa en Power BI mediante una medida DAX que utiliza `FIRSTNONBLANK` y `LASTNONBLANK` sobre `mediana_dias`, identificando automáticamente los extremos del período con datos para cada combinación de Servicio de Salud y tipo de prestación.

Este enfoque es más adecuado que una vista SQL con LAG porque:

- Maneja correctamente los trimestres sin datos (los ignora en lugar de compararlos con el anterior disponible).
- No requiere definir períodos de referencia fijos, adaptándose a la disponibilidad variable de medianas documentada en `docs/limitaciones.md`.

#### Antigüedad extrema

- `% >24 meses` — calculada en `v_listas_espera_enriquecido`
- `% >36 meses` — calculada en `v_listas_espera_enriquecido`

Interpretadas como proxy de riesgo sanitario y presencia de cola larga.

---

### 5.2 Variables independientes

#### Concentración en nivel terciario (`pct_nivel_terciario`)

- Proporción de la demanda en establecimientos de alta complejidad.
- Calculada sobre el total nacional de registros por período y tipo de prestación.
- Utilizada como proxy de **fragmentación funcional de la red asistencial**.
- Disponible en la vista `v_pct_nivel_terciario`.
- Requiere que los valores de `nivel_atencion` sean exactamente `'Primario'`, `'Secundario'` o `'Terciario'`. El check `check_niveles_atencion` en `validacion.py` verifica esto tras cada carga.

#### Volumen de demanda

- `personas_espera`
- `registros_espera`

Utilizadas como variables de control.

#### Asimetría (`asimetria`)

- Definida como:

  asimetria = promedio_dias – mediana_dias

- Proxy de dispersión y presencia de valores extremos.

---

## 6. Estrategia analítica

El análisis se estructura en tres niveles:

### 6.1 Análisis descriptivo

- Comparación de indicadores entre Servicios de Salud.
- Evaluación de tendencias entre el trimestre de referencia y el trimestre final con datos disponibles.
- Identificación de heterogeneidad en niveles de espera.

---

### 6.2 Análisis de recuperación

- Evaluación del delta de mediana entre el primer y último trimestre con mediana disponible.
- Comparación entre Servicios de Salud.
- Identificación de patrones persistentes de rezago.

---

### 6.3 Análisis estructural

- Relación entre:
  - Concentración en nivel terciario
  - Tiempos de espera
  - Antigüedad extrema

- Evaluación de hipótesis de:
  - Fragmentación funcional
  - Ineficiencia en resolución en niveles secundarios

---

## 7. Manejo de datos faltantes

Dada la variabilidad en la disponibilidad de información:

- Los valores no disponibles se codifican como **NULL**
- No se realizan imputaciones
- El análisis se restringe a subconjuntos comparables cuando es necesario
- La vista `v_disponibilidad_indicadores` permite identificar qué indicadores tienen datos en cada período antes de construir cualquier análisis

Las limitaciones específicas por periodo se documentan en:

`docs/limitaciones.md`

---

## 8. Limitaciones metodológicas

### 8.1 Nivel de agregación

- Datos a nivel de Servicio de Salud
- No permiten inferencias a nivel individual

---

### 8.2 Calidad de datos

- Dependencia de registros administrativos
- Posibles errores residuales derivados de OCR

---

### 8.3 Disponibilidad de variables

- Variación entre años y tipos de prestación
- Uso de proxies en ausencia de medición directa
- La distribución por nivel hospitalario está disponible principalmente a nivel nacional

---

### 8.4 Interpretación

- El estudio no establece causalidad
- Los resultados deben interpretarse como asociaciones observacionales

---

## 9. Reproducibilidad

El proyecto busca maximizar reproducibilidad mediante:

- Publicación de dataset maestro
- Disponibilidad de fuentes originales (Glosa 06)
- Documentación completa del proceso metodológico
- Definición explícita de variables y supuestos
- Centralización del catálogo de Servicios de Salud en `pipeline/config/catalogos.py`
- Scripts de ingesta y transformación idempotentes

---

## 10. Consideraciones éticas

- Uso exclusivo de datos públicos agregados
- No se utilizan datos personales ni identificables
- Cumplimiento de principios de transparencia y uso responsable de información pública
