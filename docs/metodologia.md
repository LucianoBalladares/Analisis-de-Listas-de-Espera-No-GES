# Metodología

## 1. Diseño del estudio

Este estudio corresponde a un **análisis observacional, longitudinal y ecológico**, basado en datos administrativos agregados del sistema público de salud en Chile.

La unidad de análisis es el **Servicio de Salud**, evaluado en forma trimestral, lo que permite analizar la evolución temporal de indicadores de listas de espera NO GES.

El enfoque metodológico se centra en la **evaluación de la recuperación del sistema**, más que en una caracterización estática del nivel de espera.

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

2. **Validación manual**
   - Revisión de consistencia de valores extraídos.
   - Corrección de errores derivados del OCR.

3. **Estructuración intermedia**
   - Organización de datos en archivos Excel por año y trimestre.
   - Homogeneización de nombres de variables y categorías.

4. **Consolidación**
   - Integración de archivos intermedios en una estructura única.
   - Estandarización de claves (Servicio de Salud, periodo, tipo de prestación).

5. **Construcción del dataset maestro**
   - Generación de una tabla final con granularidad homogénea.
   - Manejo explícito de valores faltantes (NA).

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

#### Velocidad de recuperación (variable derivada)
- Definida como el cambio trimestral en la mediana:

Δ mediana = mediana(t) – mediana(t-1)

- Permite evaluar la dinámica de reducción de la lista.

#### Antigüedad extrema
- `% >24 meses`
- `% >36 meses`

Interpretadas como proxy de riesgo sanitario y presencia de cola larga.

---

### 5.2 Variables independientes

#### Concentración en nivel terciario (`pct_nivel_terciario`)
- Proporción de la demanda en establecimientos de alta complejidad.
- Utilizada como proxy de **fragmentación funcional de la red asistencial**.

#### Volumen de demanda
- `personas_espera`
- `registros_espera`

Utilizadas como variables de control.

#### Asimetría (`asimetria`)
- Definida como:

promedio_dias – mediana_dias

- Proxy de dispersión y presencia de valores extremos.

---

## 6. Estrategia analítica

El análisis se estructura en tres niveles:

### 6.1 Análisis descriptivo

- Comparación de indicadores entre Servicios de Salud.
- Evaluación de tendencias temporales.
- Identificación de heterogeneidad en niveles de espera.

---

### 6.2 Análisis de recuperación

- Evaluación de la **velocidad de reducción** de la mediana.
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

- Los valores no disponibles se codifican como **NO DISPONIBLE**
- No se realizan imputaciones
- El análisis se restringe a subconjuntos comparables cuando es necesario

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
- Posibles errores derivados de OCR

---

### 8.3 Disponibilidad de variables

- Variación entre años y tipos de prestación
- Uso de proxies en ausencia de medición directa

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

---

## 10. Consideraciones éticas

- Uso exclusivo de datos públicos agregados
- No se utilizan datos personales ni identificables
- Cumplimiento de principios de transparencia y uso responsable de información pública

---