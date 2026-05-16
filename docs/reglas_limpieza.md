# Reglas de limpieza de datos

## Introducción

Los datos de este proyecto provienen de documentos PDF oficiales publicados trimestralmente por el Ministerio de Salud (Glosa 06). Estos documentos no están diseñados para ser procesados por computadores: son reportes formateados para lectura humana, con tablas que cambian de estructura entre trimestres.

Para convertirlos en un dataset analítico consistente se aplican **cuatro fases de limpieza** en orden secuencial. Este documento describe cada fase, las decisiones tomadas y el motivo detrás de cada una.

---

## Fase 1 — Extracción mediante OCR

El punto de partida es convertir el PDF a texto y tablas legibles por máquina mediante un software de reconocimiento óptico de caracteres (OCR).

### 1.1 Instrucción de formato numérico

**Regla:** el OCR se configura explícitamente para **no producir ningún separador de miles** (ni punto ni coma). Los números deben llegar como enteros limpios (`1234`) o con punto decimal (`1234.5`).

**Motivo:** en Chile se usa el punto como separador de miles (ej: `1.234.567`), pero este mismo carácter es el separador decimal en inglés. Al instruir al OCR para que omita cualquier separador de miles, el número llega como `1234`, eliminando la ambigüedad completamente. El manejo de comas y puntos combinados que se describe en la Fase 3 es exclusivamente una **red de seguridad para doble falla** (OCR que produce separadores y revisión humana que no los detecta), no el camino normal de los datos.

### 1.2 Verificación manual de calidad

**Regla:** tras cada extracción se verifican **3 valores al azar** comparando el resultado del OCR con el PDF original.

**Motivo:** los PDFs de Glosa 06 contienen tablas escaneadas en las que la calidad de imagen varía. La verificación aleatoria detecta errores sistemáticos (ej: el OCR confunde `8` con `B`, o interpreta mal columnas fusionadas) antes de que los datos lleguen a la base de datos.

---

## Fase 2 — Estructuración manual del Excel

Una vez extraído el texto, se construye manualmente un archivo Excel por trimestre (`YYYY_T#.xlsx`) siguiendo una estructura estandarizada.

### 2.1 Eliminación de columnas no estándar

**Regla:** se eliminan columnas que aparecen solo en algunos trimestres y que no forman parte del conjunto de variables definido en el dataset maestro.

**Motivo:** la Glosa 06 agrega o quita columnas entre años según cambios administrativos. Incluir columnas presentes solo en un subconjunto de trimestres rompería la consistencia longitudinal del dataset. Las variables del dataset maestro están definidas en `docs/diccionario_variables.md`.

### 2.2 Estructura de hojas

Cada archivo Excel debe contener hasta tres hojas con nombres exactos (no sensibles a mayúsculas):

| Hoja                          | Contenido                            |
| ----------------------------- | ------------------------------------ |
| `listas_espera_ss_trimestre`  | Datos por Servicio de Salud          |
| `personas_nacional_trimestre` | Total nacional de personas en espera |
| `nivel_atencion_trimestre`    | Distribución por nivel de atención   |

Las hojas son opcionales: si un trimestre no tiene datos para una hoja, se omite. El pipeline registra la ausencia en el log sin interrumpir la carga.

### 2.3 Valores no disponibles

**Regla:** cuando un dato no está disponible en la fuente (la celda aparece en blanco, con guión o con texto como "S/I"), se deja la celda vacía o se escribe uno de los siguientes marcadores reconocidos:

`N/D` · `ND` · `NO DISPONIBLE` · `S/I` · `S/D` · `-` · `N/A`

**Motivo:** el pipeline reconoce estos marcadores y los convierte a `NULL` en la base de datos. No se realizan imputaciones: los valores faltantes se codifican explícitamente y se documentan en `docs/limitaciones.md`.

---

## Fase 3 — Limpieza automatizada en Python (pipeline de ingesta)

Al ejecutar `pipeline/ingest/excel_a_sql.py`, el archivo Excel pasa por un proceso de limpieza automática antes de cargarse en PostgreSQL.

### 3.1 Eliminación de filas de totales

**Regla:** se eliminan automáticamente las filas cuya columna identificadora contiene valores como `Total`, `Total Nacional`, `Subtotal`, `País`, `Promedio Nacional` u otros patrones similares.

**Motivo:** los archivos de Glosa 06 frecuentemente incluyen filas de subtotales al final de cada bloque de datos. Si no se eliminan, se cargarían en la base de datos como si fueran registros de un Servicio de Salud, corrompiendo los totales y los porcentajes calculados en las vistas.

**Aplica a:** las tres hojas del Excel. En la hoja `personas_nacional_trimestre`, el filtro se aplica siempre sobre la columna `tipo_prestacion`, que es la columna identificadora de esa hoja.

### 3.2 Normalización de nombres de Servicios de Salud (`ss_id`)

**Regla:** los nombres de Servicios de Salud se estandarizan al catálogo vigente de **29 SS**, independientemente de cómo los haya extraído el OCR.

El catálogo canónico y todos sus aliases de normalización están centralizados en `pipeline/config/catalogos.py`. Este archivo es la **única fuente de verdad** del catálogo: cualquier cambio en nombres o incorporación de nuevos servicios se hace exclusivamente ahí, y el resto del pipeline lo importa automáticamente.

Se manejan tres tipos de variantes:

| Tipo              | Ejemplo entrada                 | Resultado                     |
| ----------------- | ------------------------------- | ----------------------------- |
| Nombre histórico  | `SS Arica`, `Arica`             | `SS Arica y Parinacota`       |
| Nombre histórico  | `SS Iquique`, `Iquique`         | `SS Tarapacá`                 |
| Nombre histórico  | `SS Valdivia`, `Valdivia`       | `SS Los Ríos`                 |
| Prefijo largo OCR | `Servicio de Salud Antofagasta` | `SS Antofagasta`              |
| Abreviatura OCR   | `SS Metro Norte`                | `SS Metropolitano Norte`      |
| Guión omitido     | `SS Valparaíso San Antonio`     | `SS Valparaíso - San Antonio` |
| Sin tilde         | `SS Araucania Sur`              | `SS Araucanía Sur`            |

El matching por coincidencia exacta tiene prioridad. Si ninguna clave exacta coincide, se aplica un matching parcial ordenado de mayor a menor especificidad (longitud de clave), para evitar que una clave corta como `"metropolitano sur"` sea subcadena de `"metropolitano sur oriente"` y produzca una asignación incorrecta. Cualquier coincidencia parcial se registra como `WARNING` en el log para revisión manual.

Si un nombre no coincide con ninguna variante conocida, se carga con el valor original y se registra un `WARNING`. La segunda capa de normalización (Fase 4) puede corregirlo.

### 3.3 Normalización del tipo de prestación

**Regla:** todos los valores de tipo de prestación se convierten a uno de dos códigos estándar:

| Variantes reconocidas                                         | Código estándar |
| ------------------------------------------------------------- | --------------- |
| `CNE`, `Consulta Nueva de Especialidad`, `Consulta Nueva`     | `CNE`           |
| `IQ`, `Cirugía`, `Intervención Quirúrgica`, `Int. Quirúrgica` | `IQ`            |

### 3.4 Normalización del nivel de atención

**Regla:** todos los valores de nivel de atención se normalizan a uno de tres valores estándar mediante un mapa explícito:

| Variantes reconocidas                          | Valor estándar |
| ---------------------------------------------- | -------------- |
| `Primario`, `Nivel Primario`, `Primer Nivel`   | `Primario`     |
| `Secundario`, `Nivel Secundario`, `2° Nivel`   | `Secundario`   |
| `Terciario`, `Nivel Terciario`, `Tercer Nivel` | `Terciario`    |

Si el valor no coincide con ninguna variante reconocida, se aplica `.title()` como fallback y se registra un `WARNING`. El check `check_niveles_atencion` en `validacion.py` cuantifica el impacto sobre `v_pct_nivel_terciario`.

### 3.5 Conversión de valores numéricos

**Caso normal (OCR configurado correctamente):** los números llegan como enteros limpios o con punto decimal y se convierten directamente a `float`. Este es el único caso que debería ocurrir en operación normal.

**Red de seguridad (doble falla OCR + revisión humana):** si a pesar de la configuración del OCR y la revisión manual llegan valores con separadores, se aplica la siguiente lógica:

| Formato de entrada | Resultado | Condición                                                       |
| ------------------ | --------- | --------------------------------------------------------------- |
| `1234`             | `1234.0`  | Caso normal — entero limpio                                     |
| `1234.5`           | `1234.5`  | Caso normal — decimal con punto                                 |
| `1234,5`           | `1234.5`  | Falla OCR: coma interpretada como decimal                       |
| `0,365`            | `0.365`   | Falla OCR: coma interpretada como decimal (3 dígitos post-coma) |
| `1.234,5`          | `1234.5`  | Falla OCR: punto=miles, coma=decimal (formato europeo)          |
| `1,234.5`          | `1.234`   | Doble falla: código asume europeo, resultado incorrecto¹        |
| `N/D`, `-`, vacío  | `NULL`    | Marcador de no disponible                                       |
| Valores negativos  | `NULL`    | Aberrante en este dominio; se registra `WARNING` en el log      |

> ¹ Cuando ambos separadores están presentes, el código asume formato europeo
> (punto = miles, coma = decimal). Si el valor real era `1,234.5` en formato
> americano (1234.5), el resultado sería `1.234` (incorrecto). Este caso
> requiere doble falla simultánea: OCR que produce separadores a pesar de la
> configuración **y** revisión humana que no detecta el error. En condiciones
> normales de operación este formato no debería llegar al pipeline.

**Nota sobre negativos:** los valores negativos son aberrantes en este dominio (días de espera, conteos de personas). Si aparecen como resultado de un error de OCR, se descartan como `NULL` con una advertencia en el log, evitando que violen el `CHECK CONSTRAINT` de la base de datos.

### 3.6 Cálculo de asimetría

**Regla:** la columna `asimetria` se calcula automáticamente como:

```
asimetria = promedio_dias – mediana_dias
```

Si cualquiera de los dos componentes es `NULL`, `asimetria` también queda `NULL`. No se hacen estimaciones parciales.

**Interpretación:** valores altos indican que hay casos con esperas muy largas que elevan el promedio por encima de la mediana (cola larga). Valores cercanos a cero indican una distribución más homogénea. El valor puede ser negativo si la mediana supera al promedio, lo que es inusual pero posible en distribuciones con sesgo a la izquierda.

---

## Fase 4 — Correcciones SQL post-carga

Después de la ingesta, se ejecuta `pipeline/transform/run_transformations.py`, que aplica dos scripts SQL sobre la base de datos.

### 4.1 Segunda normalización de `ss_id` (`normalize_services.sql`)

**Regla:** se aplica una segunda pasada de normalización sobre los `ss_id` que no quedaron estandarizados en la Fase 3. Usa dos mecanismos:

1. **Normalización exacta desde catálogo:** un único `UPDATE` con `JOIN` contra una tabla temporal que contiene todas las variantes de `SS_ID_MAP` (clave directa más prefijos `ss`, `s.s.`, `servicio de salud`). Es eficiente: una sola sentencia SQL independiente del tamaño del catálogo.
2. **Coincidencia parcial:** para variantes no previstas, se usan condiciones `ILIKE` con patrones inequívocos (ej: cualquier valor que contenga `metropolitano sur oriente` → `SS Metropolitano Sur Oriente`).

Cada corrección queda registrada en la columna `observaciones` del registro, con el valor original y el valor corregido, garantizando trazabilidad completa.

### 4.2 Limpieza de métricas (`clean_waitlists.sql`)

Se aplican cuatro correcciones idempotentes (se pueden ejecutar múltiples veces sin efecto adicional):

**Corrección 1 — Recalcular asimetría faltante**
Si `promedio_dias` y `mediana_dias` existen pero `asimetria` es `NULL` (puede ocurrir si un dato se corrigió manualmente después de la carga), se recalcula automáticamente.

**Corrección 2 — Fuente por defecto**
Si la columna `fuente` quedó vacía, se asigna `'Glosa 06'` como valor por defecto.

**Corrección 3 — Normalización de seguridad del tipo de prestación**
Capa adicional que corrige cualquier valor de `tipo_prestacion` que haya eludido la validación en Python, garantizando que solo existan los valores `'CNE'` e `'IQ'` en la base de datos.

**Corrección 4 — Detección de incoherencia en tramos de antigüedad**
Si la suma de `reg_24a36m` + `reg_mayor_36m` supera `registros_espera`, se marca el registro con una alerta en `observaciones`. Estos dos campos son tramos mutuamente excluyentes (24–36 meses y más de 36 meses respectivamente), por lo que su suma nunca puede superar el total de registros.

---

## Nota sobre `observaciones` en re-cargas

La columna `observaciones` acumula anotaciones de tres fuentes:

1. **Fuente original** (Excel): notas manuales del proceso de estructuración, si las hay.
2. **Normalización** (Fases 3 y 4): registros de correcciones automáticas de `ss_id`.
3. **Alertas de calidad** (Fase 4): marcas como `ALERTA: suma de tramos de antigüedad supera registros_espera`.

Al re-cargar el mismo Excel (por corrección de datos), el `UPSERT` **preserva** el valor existente en la base de datos si ya contiene anotaciones, y solo usa el valor del Excel si la columna está vacía en la BD. Esto garantiza que las alertas y correcciones agregadas por las transformaciones no se pierdan. Las transformaciones son idempotentes y re-agregan las anotaciones si corresponde.

---

## Resumen del flujo de limpieza

```
PDF / imagen (Glosa 06)
        │
        ▼
[Fase 1] OCR sin separadores de miles
         + verificación manual de 3 valores al azar
        │
        ▼
[Fase 2] Estructuración manual en Excel
         - Eliminación de columnas no estándar
         - Marcado de valores no disponibles
         - Organización en 3 hojas estandarizadas
        │
        ▼
[Fase 3] excel_a_sql.py (Python)
         - Filtrado de filas de totales en las 3 hojas
         - Normalización de ss_id (desde pipeline/config/catalogos.py)
           · matching exacto primero
           · matching parcial por especificidad (mayor longitud = mayor prioridad)
         - Normalización de nivel_atencion (mapa explícito + fallback title())
         - Normalización de tipo_prestacion
         - Conversión numérica: caso normal = entero o punto decimal limpio
         - Negativos descartados como NULL
         - Cálculo de asimetría
         - UPSERT idempotente en PostgreSQL (preserva observaciones existentes)
        │
        ▼
[Fase 4] normalize_services.sql + clean_waitlists.sql (SQL)
         - Segunda normalización de ss_id (UPDATE único + ILIKE fallback)
         - Recálculo de asimetría faltante
         - Detección y marcado de incoherencias
        │
        ▼
Dataset limpio en PostgreSQL
(disponible vía vistas para Power BI)
```

---

## Principios generales

- **Sin imputación:** los valores no disponibles se codifican como `NULL`. No se estiman ni reemplazan por promedios u otros valores.
- **Trazabilidad:** cada corrección automática queda registrada en la columna `observaciones` del registro afectado.
- **Preservación de metadatos:** en re-cargas, `observaciones` no se sobreescribe si ya contiene anotaciones de transformaciones anteriores.
- **Idempotencia:** todos los scripts de limpieza pueden ejecutarse múltiples veces sobre los mismos datos sin producir resultados distintos.
- **Fuente única de verdad:** el catálogo de Servicios de Salud (nombres canónicos y aliases) está centralizado en `pipeline/config/catalogos.py`. No debe duplicarse en otros archivos.
- **Transparencia:** las limitaciones de disponibilidad de datos por período se documentan en `docs/limitaciones.md`.
