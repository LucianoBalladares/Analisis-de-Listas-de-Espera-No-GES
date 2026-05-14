# Reglas de limpieza de datos

## Introducción

Los datos de este proyecto provienen de documentos PDF oficiales publicados trimestralmente por el Ministerio de Salud (Glosa 06). Estos documentos no están diseñados para ser procesados por computadores: son reportes formateados para lectura humana, con tablas que cambian de estructura entre trimestres.

Para convertirlos en un dataset analítico consistente se aplican **cuatro fases de limpieza** en orden secuencial. Este documento describe cada fase, las decisiones tomadas y el motivo detrás de cada una.

---

## Fase 1 — Extracción mediante OCR

El punto de partida es convertir el PDF a texto y tablas legibles por máquina mediante un software de reconocimiento óptico de caracteres (OCR).

### 1.1 Instrucción de formato numérico

**Regla:** el OCR se configura explícitamente para **no utilizar punto ni coma como separador de miles**.

**Motivo:** en Chile se usa el punto como separador de miles (ej: `1.234.567`), pero este mismo carácter es el separador decimal en inglés. Si el OCR produce `1.234`, es imposible saber automáticamente si significa `1,234` (mil doscientos treinta y cuatro) o `1.234` (un poco más que uno). Al instruir al OCR para que omita ese separador, el número llega como `1234`, eliminando la ambigüedad.

Esta instrucción también se aplica a la coma: el OCR no la usa como separador de miles. Por eso, en la limpieza automatizada (Fase 3), cualquier coma presente en un valor numérico se interpreta siempre como separador decimal, independientemente de cuántos dígitos haya tras ella.

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

Si un nombre no coincide con ninguna variante conocida, se carga con el valor original y se registra un `warning` en el log. La segunda capa de normalización (Fase 4) puede corregirlo.

### 3.3 Normalización del tipo de prestación

**Regla:** todos los valores de tipo de prestación se convierten a uno de dos códigos estándar:

| Variantes reconocidas                                         | Código estándar |
| ------------------------------------------------------------- | --------------- |
| `CNE`, `Consulta Nueva de Especialidad`, `Consulta Nueva`     | `CNE`           |
| `IQ`, `Cirugía`, `Intervención Quirúrgica`, `Int. Quirúrgica` | `IQ`            |

### 3.4 Conversión de valores numéricos

**Regla:** todos los campos numéricos se convierten a número decimal con la siguiente lógica, construida sobre la garantía de la Fase 1 (el OCR no usa separadores de miles):

| Formato de entrada | Interpretación                                        |
| ------------------ | ----------------------------------------------------- |
| `1234`             | 1.234 (entero)                                        |
| `1234,5`           | 1.234,5 (coma = decimal, por garantía OCR)            |
| `0,365`            | 0,365 (coma = decimal, aunque tenga 3 dígitos)        |
| `1234.5`           | 1.234,5 (punto = decimal)                             |
| `1.234,5`          | 1.234,5 (ambos presentes → punto=miles, coma=decimal) |
| `N/D`, `-`, vacío  | `NULL`                                                |
| Valores negativos  | `NULL` + advertencia en el log                        |

**Nota sobre la coma:** dado que el OCR está instruido para no usar coma como separador de miles, cualquier coma en el output del OCR es siempre un separador decimal. Por eso, `1,200` se convierte a `1.2` y no a `1200`. Esta regla elimina la ambigüedad sin necesidad de heurísticas adicionales.

**Nota sobre negativos:** los valores negativos son aberrantes en este dominio (días de espera, conteos de personas). Si aparecen como resultado de un error de OCR, se descartan como `NULL` con una advertencia en el log, evitando que violen el `CHECK CONSTRAINT` de la base de datos.

### 3.5 Cálculo de asimetría

**Regla:** la columna `asimetria` se calcula automáticamente como:

```
asimetria = promedio_dias – mediana_dias
```

Si cualquiera de los dos componentes es `NULL`, `asimetria` también queda `NULL`. No se hacen estimaciones parciales.

**Interpretación:** valores altos indican que hay casos con esperas muy largas que elevan el promedio por encima de la mediana (cola larga). Valores cercanos a cero indican una distribución más homogénea.

---

## Fase 4 — Correcciones SQL post-carga

Después de la ingesta, se ejecuta `pipeline/transform/run_transformations.py`, que aplica dos scripts SQL sobre la base de datos.

### 4.1 Segunda normalización de `ss_id` (`normalize_services.sql`)

**Regla:** se aplica una segunda pasada de normalización sobre los `ss_id` que no quedaron estandarizados en la Fase 3. Usa dos mecanismos:

1. **Tabla de correcciones exactas:** lista exhaustiva de variantes conocidas con su valor correcto.
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

## Resumen del flujo de limpieza

```
PDF / imagen (Glosa 06)
        │
        ▼
[Fase 1] OCR sin separadores de miles (ni punto ni coma)
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
         - Normalización de tipo_prestacion
         - Conversión numérica: coma = decimal (garantía OCR)
         - Negativos descartados como NULL
         - Cálculo de asimetría
         - UPSERT idempotente en PostgreSQL
        │
        ▼
[Fase 4] normalize_services.sql + clean_waitlists.sql (SQL)
         - Segunda normalización de ss_id
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
- **Idempotencia:** todos los scripts de limpieza pueden ejecutarse múltiples veces sobre los mismos datos sin producir resultados distintos.
- **Fuente única de verdad:** el catálogo de Servicios de Salud (nombres canónicos y aliases) está centralizado en `pipeline/config/catalogos.py`. No debe duplicarse en otros archivos.
- **Transparencia:** las limitaciones de disponibilidad de datos por período se documentan en `docs/limitaciones.md`.
