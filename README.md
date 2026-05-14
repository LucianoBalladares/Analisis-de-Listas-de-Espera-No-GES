# Análisis de recuperación de listas de espera NO GES en Chile

### Modelamiento de variabilidad entre Servicios de Salud

**Dashboard interactivo en Power BI:** [LINK](https://app.powerbi.com/view?r=eyJrIjoiNDFhZDFlMWYtYzhkMC00NjRjLWIzNzItMGY1MWEyNDUwZmE5IiwidCI6IjZmZDQ4ZjQxLWFmODEtNDVhNS05YzFlLWUzOTkwYmMyN2U3YyIsImMiOjR9)

---

## 1. Descripción del proyecto

Este proyecto analiza la **heterogeneidad en la recuperación de las listas de espera NO GES en Chile**, con foco en diferencias estructurales entre Servicios de Salud.

A diferencia de aproximaciones descriptivas tradicionales centradas en volumen de casos, este trabajo introduce un enfoque analítico basado en:

- Evolución de la mediana de espera entre el primer y último trimestre con datos disponibles
- Estructura de la red asistencial
- Distribución interna de la demanda

El objetivo es generar **evidencia útil para la gestión y gobernanza del sistema de salud**, utilizando datos administrativos oficiales.

---

## 2. Pregunta de investigación

**¿En qué medida la heterogeneidad en la recuperación de las listas de espera NO GES entre Servicios de Salud en Chile se asocia a diferencias en la estructura y funcionamiento de la red asistencial, más allá del volumen de demanda acumulada?**

---

## 3. Enfoque analítico

El análisis se estructura en torno a tres dimensiones principales:

### 1. Recuperación del sistema

- Mediana de días de espera por Servicio de Salud
- Delta de recuperación calculado en Power BI mediante una medida DAX que identifica automáticamente el trimestre más antiguo y el más reciente con mediana disponible para cada Servicio de Salud, manejando correctamente los períodos sin datos

### 2. Severidad de la espera

- Proporción de casos con antigüedad extrema (>24 y >36 meses)
- Asimetría de la distribución (cola larga)

### 3. Estructura de la red

- Concentración de la demanda en nivel terciario (`pct_nivel_terciario`)

---

## 4. Fuente de datos

### Fuente principal:

- **Glosa 06 – Ley de Presupuestos (MINSAL)**

Características:

- Datos oficiales
- Periodicidad trimestral
- Nivel de agregación: Servicio de Salud
- Incluye:
  - Medianas de espera
  - Volumen de casos
  - Distribución por nivel de atención
  - Tramos de antigüedad

---

## 5. Pipeline de datos

Dado que las fuentes originales se encuentran mayoritariamente en formato no estructurado (PDF/imágenes), se implementó un proceso de reconstrucción del dataset:

```
Glosa 06 (PDF / imágenes)
↓
Extracción mediante OCR
↓
Validación manual de datos
↓
Estructuración en Excel (por año / trimestre)
↓
Consolidación de bases intermedias
↓
Construcción de dataset maestro
↓
Modelamiento y visualización en Power BI
```

Este pipeline prioriza la **trazabilidad y consistencia longitudinal de los datos**, considerando las limitaciones de las fuentes administrativas.

El catálogo de los 29 Servicios de Salud vigentes (nombres canónicos y aliases de normalización) está centralizado en `pipeline/config/catalogos.py`, que actúa como única fuente de verdad para todos los scripts del pipeline.

---

## 6. Instrucciones de uso

### 1. Preparar el entorno (una sola vez)

```bash
python -m venv .venv && source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate                             # Windows
pip install -r requirements.txt
```

### 2. Configurar conexión a la base de datos

```bash
cp .env.example .env   # completar DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
```

### 3. Inicializar la base de datos (una sola vez)

Ejecutar los archivos SQL en este orden:

```bash
psql -U postgres -d listas_espera_ges -f sql/schema/create_tables.sql
psql -U postgres -d listas_espera_ges -f sql/schema/constraints.sql
psql -U postgres -d listas_espera_ges -f sql/schema/indexes.sql
psql -U postgres -d listas_espera_ges -f sql/schema/triggers.sql
psql -U postgres -d listas_espera_ges -f sql/views/dashboard_views.sql
```

### 4. Ciclo normal cuando llega un nuevo Excel

```bash
# Opción A: orquestador automático (recomendado)
python pipeline/orchestration/pipeline_runner.py data/staging/cleaned_excels/2024_T4.xlsx

# Opción B: pasos manuales
python pipeline/ingest/excel_a_sql.py data/staging/cleaned_excels/2024_T4.xlsx
python pipeline/ingest/validacion.py 2024_T4
python pipeline/transform/run_transformations.py --trimestre 2024_T4
```

> Todos los comandos deben ejecutarse desde la **raíz del repositorio**.

### 5. Conectar Power BI al dashboard local

El dashboard público está disponible sin configuración adicional:

🔗 [Ver dashboard en Power BI Service](https://app.powerbi.com/view?r=eyJrIjoiNDFhZDFlMWYtYzhkMC00NjRjLWIzNzItMGY1MWEyNDUwZmE5IiwidCI6IjZmZDQ4ZjQxLWFmODEtNDVhNS05YzFlLWUzOTkwYmMyN2U3YyIsImMiOjR9)

Para replicar localmente con tu propia base de datos:

1. Abre **Power BI Desktop**
2. **Inicio → Obtener datos → Base de datos → PostgreSQL**
3. Completa los campos:
   - **Servidor:** hostname o IP donde corre PostgreSQL (ej: `localhost`)
   - **Puerto:** `5432`
   - **Base de datos:** `listas_espera_ges`
4. Selecciona las vistas del esquema `public`:
   - `v_listas_espera_enriquecido` — tabla de hechos principal
   - `v_dim_trimestre` — dimensión temporal para slicers
   - `v_pct_nivel_terciario` — concentración en nivel terciario
   - `v_disponibilidad_indicadores` — mapa de disponibilidad de datos
5. Usa el modo **Importar** para análisis estáticos o **DirectQuery** para datos en vivo.

---

## 7. Dataset

### Unidad de análisis:

- Servicio de Salud × Trimestre × Tipo de prestación

### Tipos de prestación:

- Consulta Nueva de Especialidad (CNE)
- Intervención Quirúrgica (IQ)

### Variables principales:

- `mediana_dias` → Mediana de días de espera
- `personas_espera` → Número de personas en lista activa
- `registros_espera` → Número de registros totales
- `pct_mayor_24m` / `pct_mayor_36m` → Antigüedad extrema (calculadas en `v_listas_espera_enriquecido`)
- `pct_nivel_terciario` → Concentración en nivel terciario (disponible en `v_pct_nivel_terciario`)
- `asimetria` → Diferencia entre promedio y mediana

📄 Ver detalle completo en:
`docs/diccionario_variables.md`

---

## 8. Dashboard (Power BI)

El dashboard permite:

- Comparar Servicios de Salud
- Analizar la evolución de la mediana entre el primer y último trimestre con datos disponibles
- Identificar concentración de demanda en nivel terciario
- Detectar presencia de colas largas (casos extremos)

🔗 Acceso:
[LINK POWER BI](https://app.powerbi.com/view?r=eyJrIjoiNDFhZDFlMWYtYzhkMC00NjRjLWIzNzItMGY1MWEyNDUwZmE5IiwidCI6IjZmZDQ4ZjQxLWFmODEtNDVhNS05YzFlLWUzOTkwYmMyN2U3YyIsImMiOjR9)

---

## 9. Limitaciones

- Datos agregados (no permiten análisis a nivel individual)
- Dependencia de calidad de registros administrativos
- Proceso de OCR puede introducir errores residuales
- Uso de proxies (concentración en nivel terciario como medida de fragmentación)
- Disponibilidad variable de indicadores según tipo de prestación y período

Estas limitaciones son abordadas mediante:

- Validación manual
- Transparencia metodológica
- Definición explícita de supuestos analíticos

---

### Limitaciones específicas de disponibilidad de datos

La disponibilidad de indicadores varía significativamente entre periodos, lo que afecta la comparabilidad longitudinal:

- **2021–2022:** Ausencia de medianas de espera en varios trimestres.
- **2023–2024:** Falta de datos de personas en espera para CNE en algunos periodos.
- **2024–2025:** No disponibilidad de tramos de antigüedad (>24 y >36 meses).
- **Distribución por nivel hospitalario:** Disponible principalmente a nivel nacional, con limitada desagregación por Servicio de Salud.

El detalle completo por trimestre se encuentra en `docs/limitaciones.md`.

---

## 10. Contribución

Este proyecto aporta:

- Un dataset estructurado listo para análisis longitudinal
- Un enfoque analítico centrado en la evolución del sistema entre períodos comparables
- Evidencia sobre desigualdad estructural entre Servicios de Salud
- Una herramienta visual para apoyo en toma de decisiones

---

## 11. Autor

**Luciano Balladares**
Tecnólogo Médico | Especialización en Informática en Salud

- LinkedIn: [LINK](https://www.linkedin.com/in/luciano-balladares/)
- Email: [LINK](l.garridoballadares@uandresbello.edu)

---

## 12. Licencia

Este repositorio utiliza datos públicos provenientes de fuentes oficiales del Estado de Chile (MINSAL).
El uso del dataset reconstruido debe citar la fuente original.
