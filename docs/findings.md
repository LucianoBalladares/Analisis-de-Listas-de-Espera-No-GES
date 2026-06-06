# Hallazgos del Análisis

**Análisis Longitudinal de Listas de Espera NO GES en Chile (2021–2025)**
Luciano Balladares · Mayo 2026

> Este documento resume los hallazgos principales del análisis.
> El informe completo y el dashboard interactivo están disponibles
> en los recursos del proyecto.
>
> 🔗 **Dashboard Power BI:**
> [Ver en Power BI Service](https://app.powerbi.com/view?r=eyJrIjoiNDFhZDFlMWYtYzhkMC00NjRjLWIzNzItMGY1MWEyNDUwZmE5IiwidCI6IjZmZDQ4ZjQxLWFmODEtNDVhNS05YzFlLWUzOTkwYmMyN2U3YyIsImMiOjR9)

---

## Contexto

Las listas de espera NO GES en Chile son gestionadas por 29 Servicios de Salud
y reportadas trimestralmente a través de la Glosa 06 de la Ley de Presupuestos (MINSAL).
Este análisis construyó series longitudinales desde 2021 hasta 2025 para examinar
si la heterogeneidad en la recuperación post-pandemia se asocia a diferencias en la
estructura y funcionamiento de la red asistencial, más allá del volumen de demanda acumulada.

**Unidad de análisis:** Servicio de Salud × Trimestre × Tipo de prestación (CNE / IQ)
**Períodos con mediana disponible:** 13 trimestres (2022_T3 – 2025_T4)
**Fuente:** Glosa 06 – Ley de Presupuestos (MINSAL)

---

## Hallazgo 1 — La crisis homogénea de 2022 se fragmentó en perfiles heterogéneos de recuperación

En el período inicial de análisis, mediana de espera y carga histórica mostraban una
relación fuerte y coherente entre Servicios de Salud. Esa relación se debilitó
progresivamente durante la recuperación post-pandemia, evidenciando que los SS
recuperaron ambas dimensiones a ritmos distintos.

**Evidencia:**

- En **2022_T3**, el ajuste entre mediana de espera y proporción de registros >36 meses
  era alto: **R² = 0.75 en CNE** y **R² = 0.88 en IQ**. En ese momento, los SS más
  estresados lo eran simultáneamente en flujo reciente y en acumulación histórica.
- En **2025_T4**, la relación se debilitó significativamente: **R² = 0.52 en CNE** y
  **R² = 0.28 en IQ**, particularmente marcado en intervenciones quirúrgicas.
- La segmentación por cuadrantes evidenció la coexistencia simultánea de cuatro
  perfiles: alta mediana con baja cola histórica, baja mediana con alta acumulación,
  y perfiles mixtos de congestión.

> **Advertencia metodológica:** la comparación entre períodos debe hacerse con cautela.
> El número de SS con datos de tramos de antigüedad disponibles varía entre trimestres:
> en 2022_T3 la cobertura es mayor, mientras que en 2025_T4 los tramos figuran como
> "información incompleta" según `docs/limitaciones.md`. Esto podría influir en los
> valores de R² observados al final del período.

**Interpretación:** La caída del R² durante la recuperación refleja que los SS no
mejoraron ambas dimensiones de manera proporcional. Algunos redujeron su mediana sin
resolver el backlog acumulado. Otros priorizaron la reducción de casos históricos.
Esto produce directamente los cuatro perfiles operacionales del Hallazgo 3.

**Implicancia:** Monitorear solo la mediana o solo la cola histórica es insuficiente.
Precisamente porque ambos indicadores se desacoplaron durante la recuperación, un SS
puede mostrar mejoría en uno mientras deteriora en el otro.

---

## Hallazgo 2 — Heterogeneidad territorial persistente y estructural

Las listas de espera NO GES presentaron heterogeneidad territorial persistente
durante todo el período analizado. La brecha entre Servicios de Salud extremos fue
especialmente pronunciada en los períodos iniciales y se redujo parcialmente, aunque
sin convergencia territorial real.

**Brechas entre SS extremos por período:**

| Período | SS mayor CNE           | Días | SS menor CNE          | Días | Brecha CNE |
| ------- | ---------------------- | ---- | --------------------- | ---- | ---------- |
| 2022_T3 | SS Metropolitano Norte | 584  | SS Arica y Parinacota | 74   | 510 días   |
| 2025_T4 | SS Metropolitano Norte | 378  | SS Aconcagua          | 92   | 286 días   |

| Período | SS mayor IQ  | Días  | SS menor IQ           | Días | Brecha IQ |
| ------- | ------------ | ----- | --------------------- | ---- | --------- |
| 2022_T3 | SS Los Ríos  | 1.080 | SS Arica y Parinacota | 139  | 941 días  |
| 2025_T4 | SS Aconcagua | 329   | SS Araucanía Norte    | 128  | 201 días  |

**Top 5 CNE en 2025_T4 (medianas más altas):**

- SS Metropolitano Norte: 378 días
- SS Tarapacá: 357 días
- SS Araucanía Sur: 344 días
- SS Antofagasta: 328 días
- SS Metropolitano Central: 288 días

**Bottom 5 CNE en 2025_T4 (medianas más bajas):**

- SS Aconcagua: 92 días
- SS Osorno: 120 días
- SS Metropolitano Oriente: 127 días
- SS Arica y Parinacota: 144 días
- SS Aysén: 148 días

**Top 5 IQ en 2025_T4 (medianas más altas):**

- SS Aconcagua: 329 días
- SS O'Higgins: 317 días
- SS Biobío: 307 días
- SS Tarapacá: 303 días
- SS Metropolitano Sur Oriente: 302 días

**Bottom 5 IQ en 2025_T4 (medianas más bajas):**

- SS Araucanía Norte: 128 días
- SS Talcahuano: 153 días
- SS Aysén: 147 días
- SS Antofagasta: 182 días
- SS Arauco: 185 días

**Servicios con medianas consistentemente elevadas en CNE** (aparecen en el top 5 en
al menos 11 de los 13 trimestres con datos disponibles):

- SS Metropolitano Norte _(presente en todos los trimestres como el SS con mayor mediana)_
- SS Antofagasta
- SS Araucanía Sur
- SS Tarapacá

**Servicios con medianas consistentemente bajas en CNE:**

- SS Arica y Parinacota _(bottom en períodos tempranos)_
- SS Aconcagua _(bottom en períodos recientes)_

**Implicancia:** Políticas nacionales uniformes tienen efectividad limitada frente a
realidades operacionales heterogéneas. La reducción de brechas absolutas no implica
convergencia territorial: los SS que encabezaban las listas en 2022 siguen haciéndolo
en 2025, aunque a valores absolutos menores.

---

## Hallazgo 3 — Cuatro perfiles operacionales diferenciados

La segmentación basada en mediana relativa y proporción de registros >36 meses
permite identificar cuatro perfiles funcionales con necesidades de intervención
distintas.

**Clasificación en 2025_T4:**

| Perfil             | Característica                     | SS representativos                                |
| ------------------ | ---------------------------------- | ------------------------------------------------- |
| **Crítico**        | Alta mediana + alta cola larga     | Metro Norte, Araucanía Sur, Tarapacá, Antofagasta |
| **Ineficiente**    | Alta mediana + baja cola histórica | Metro Central, Coquimbo                           |
| **En riesgo**      | Baja mediana + alta cola larga     | Arauco                                            |
| **Buen desempeño** | Baja mediana + baja cola           | Aconcagua, Arica y Parinacota                     |

SS Metropolitano Norte y SS Araucanía Sur se mantienen en el cuadrante crítico de
manera consistente a lo largo de los períodos analizados, constituyendo los casos de
congestión estructural más persistente del sistema.

**Implicancia:** La utilización de indicadores agregados nacionales puede ocultar
diferencias críticas entre SS. La segmentación operacional permite priorización más
precisa y estrategias adaptadas al tipo de deterioro predominante.

---

## Hallazgo 4 — Divergencia operacional entre CNE e IQ

Los patrones territoriales de espera difieren significativamente entre Consultas de
Nueva Especialidad (CNE) e Intervenciones Quirúrgicas (IQ), sugiriendo que los
cuellos de botella operacionales no son homogéneos entre tipos de prestación.

**El caso más ilustrativo: SS Aconcagua en 2025_T4**

| Prestación | Mediana  | Posición nacional     |
| ---------- | -------- | --------------------- |
| CNE        | 92 días  | **Más baja** del país |
| IQ         | 329 días | **Más alta** del país |

Este SS es la expresión más contundente de que el desempeño en una dimensión no
garantiza desempeño equivalente en la otra.

**Homogeneidad en la distribución IQ vs CNE (2025_T4):**

En IQ, la diferencia entre el primer y séptimo lugar es de solo **42 días**
(Aconcagua 329 días → Del Reloncaví 300 días). En CNE, esa misma brecha alcanza
**96 días** (Metropolitano Norte 378 días → Del Reloncaví 274 días). La carga
quirúrgica está distribuida de manera más uniforme entre los SS más congestionados.

**Servicios con mayores medianas IQ** (composición distinta a CNE):

- SS Aconcagua, O'Higgins, Biobío, Tarapacá, Metropolitano Sur Oriente.

**Implicancia:** Las estrategias de reducción de listas de espera no deben diseñarse
como intervenciones uniformes para todas las prestaciones. CNE requiere abordar
restricciones de acceso ambulatorio especializado; IQ requiere intervención sobre
capacidad quirúrgica, pabellones y continuidad operatoria.

---

## Hallazgo 5 — Recuperación post-pandemia marcadamente desigual

La recuperación de medianas de espera entre 2022_T3 y 2025_T4 fue
heterogénea entre Servicios de Salud, evidenciando diferencias importantes en
resiliencia operacional.

**Top 5 con mayor reducción de mediana CNE:**

| Servicio de Salud        | 2022_T3 | 2025_T4 | Variación |
| ------------------------ | ------- | ------- | --------- |
| SS Metropolitano Norte   | 584     | 378     | −206 días |
| SS Metropolitano Oriente | 331     | 127     | −204 días |
| SS Ñuble                 | 354     | 198     | −156 días |
| SS Viña del Mar-Quillota | 400     | 258     | −142 días |
| SS Arauco                | 338     | 197     | −141 días |

**SS con mayor deterioro de mediana CNE:**

| Servicio de Salud        | 2022_T3 | 2025_T4 | Variación |
| ------------------------ | ------- | ------- | --------- |
| SS Tarapacá              | 210     | 357     | +147 días |
| SS Coquimbo              | 183     | 274     | +91 días  |
| SS Arica y Parinacota    | 74      | 144     | +70 días  |
| SS Magallanes            | 150     | 225     | +75 días  |
| SS Metropolitano Central | 242     | 288     | +46 días  |

**Top 5 con mayor reducción de mediana IQ:**

| Servicio de Salud         | 2022_T3 | 2025_T4 | Variación |
| ------------------------- | ------- | ------- | --------- |
| SS Los Ríos               | 1.080   | 189     | −891 días |
| SS Valparaíso-San Antonio | 821     | 229     | −592 días |
| SS Araucanía Sur          | 582     | 265     | −317 días |
| SS Del Maule              | 512     | 203     | −309 días |
| SS Viña del Mar-Quillota  | 591     | 238     | −353 días |

**Matices importantes:**

- **SS Metropolitano Norte** registra la mayor reducción absoluta en CNE (−206 días),
  pero continúa siendo el SS con la mediana más alta del país (378 días en 2025_T4).
  La escala inicial del deterioro era tan extrema que incluso la mayor mejora del sistema
  no fue suficiente para sacarlo del extremo superior de la distribución.

- **SS Tarapacá en CNE** representa un caso de deterioro activo, no de falla de
  recuperación: con 210 días en 2022_T3 (valor dentro del rango medio del sistema),
  alcanzó 357 días en 2025_T4, posicionándose como el segundo SS con mayor mediana CNE.

- **SS Los Ríos en IQ** muestra la trayectoria de recuperación más notable del dataset:
  la mediana aumentó hasta 1.124 días en 2023_T1 antes de iniciar una reducción sostenida
  hasta los 189 días en 2025_T4 — una reducción de 891 días en menos de dos años.

**Implicancia:** La recuperación asistencial depende no solo de disponibilidad de
recursos, sino también de capacidad organizacional y operacional local. La existencia
de casos exitosos sugiere potencial de transferencia de prácticas hacia SS rezagados.

---

## Hallazgo 6 — Concentración estructural en nivel terciario

Entre 2021 y 2025, la resolución de listas de espera NO GES se mantuvo
fuertemente concentrada en el nivel terciario de atención.

**Distribución por nivel de atención (total registros, sin separación CNE/IQ):**

| Período | Primario | Secundario | Terciario | No definido |
| ------- | -------- | ---------- | --------- | ----------- |
| 2021_T1 | 8,1%     | 1,2%       | 90,7%     | —           |
| 2025_T4 | 10,4%    | 3,0%       | 83,6%     | 3,1%        |

Se observa una leve disminución relativa de la concentración terciaria y un crecimiento
del nivel primario y secundario, sin modificar significativamente la estructura general.

> ⚠️ **Nota sobre discontinuidad:** Los datos del período 2023_T2 – 2024_T4 presentan
> una anomalía en la distribución de niveles causada por un cambio en criterios de
> clasificación del MINSAL. **No son comparables** con los períodos anteriores ni
> posteriores. Esta discontinuidad **no afecta** otras variables del dataset (medianas,
> registros de espera, tramos de antigüedad).

**Implicancia:** Incrementos de capacidad exclusivamente hospitalaria podrían tener
impacto limitado si no se acompañan de mecanismos de resolución ambulatoria,
triage especializado y coordinación entre niveles asistenciales.

---

## Hallazgo 7 — Reducción de medianas pese a aumento sostenido de registros

Las medianas de espera mostraron reducción sostenida durante el período analizado
pese al aumento simultáneo del volumen de registros acumulados.

**Variaciones entre 2022_T3 y 2025_T4:**

| Indicador                | CNE                  | IQ                    |
| ------------------------ | -------------------- | --------------------- |
| Mediana inicio (2022_T3) | 266,24 días          | 410,38 días           |
| Mediana fin (2025_T4)    | 216,79 días          | 239,55 días           |
| Variación mediana        | −49,45 días (−18,6%) | −170,83 días (−41,6%) |
| Registros inicio         | 2,15 millones        | 328.500               |
| Registros fin            | 2,46 millones        | 425.000               |
| Variación registros      | +314.000 (+14,6%)    | +96.500 (+29,4%)      |
| % >36 meses inicio       | 12,0%                | 19,7%                 |
| % >36 meses fin          | 3,0%                 | 5,7%                  |

La reducción de la cola larga fue especialmente pronunciada en IQ, donde casi uno de
cada cinco registros tenía más de 36 meses de antigüedad al inicio del periodo.

**Implicancia:** La mejora agregada nacional no se distribuyó homogéneamente. SS como
Metropolitano Norte, Tarapacá y Araucanía Sur continúan presentando niveles elevados
de espera en los períodos más recientes, evidenciando que los indicadores nacionales
pueden ocultar desigualdades territoriales relevantes.

---

## Discusión — Síntesis analítica

Los resultados en conjunto son consistentes con la existencia de múltiples tipos
de congestión operacional dentro del sistema, no de un único mecanismo de saturación.

Tres tensiones analíticas estructuran la discusión:

1. **La crisis fue inicialmente homogénea y se fragmentó durante la recuperación.**
   En 2022_T3, R² = 0,75 (CNE) y R² = 0,88 (IQ) indicaban que el sistema estaba
   uniformemente deteriorado. La caída a R² = 0,52 y 0,28 en 2025_T4 refleja que
   los SS recuperaron ambas dimensiones a ritmos distintos, generando los cuatro
   perfiles operacionales identificados.

2. **Existen múltiples mecanismos de congestión.** CNE y IQ presentan distribuciones
   territoriales distintas; el caso de Aconcagua (92 días CNE vs 329 días IQ) ilustra
   que el desempeño en una dimensión no garantiza el otro. Los indicadores únicos son
   insuficientes para caracterizar el estado real del sistema.

3. **La recuperación post-pandemia no redujo las brechas territoriales.**
   La mejora nacional agregada coexistió con deterioro activo en algunos SS (Tarapacá
   CNE: +147 días) y con recuperación excepcional en otros (Los Ríos IQ: −891 días).
   La brecha entre extremos en IQ pasó de 941 días (2022_T3) a 201 días (2025_T4),
   pero la posición relativa de los SS se mantuvo.

---

## Recomendaciones estratégicas

| Eje                                    | Intervención central                                        | Impacto | Factibilidad |
| -------------------------------------- | ----------------------------------------------------------- | ------- | ------------ |
| Gestión segmentada por clúster         | Clasificar SS y asignar estrategia según perfil operacional | Alto    | Alta         |
| Monitoreo multidimensional             | Panel con mediana + cola larga + trayectoria por SS         | Alto    | Alta         |
| Reducción focalizada de backlog        | Operativos dirigidos a casos >24 y >36 meses                | Alto    | Media        |
| Fortalecimiento resolución ambulatoria | Teleinterconsulta, triage especializado, coordinación APS   | Medio   | Media-Alta   |
| Benchmarking institucional             | Sistematizar prácticas de SS con recuperación exitosa       | Medio   | Alta         |

---

## Limitaciones

- **Diseño:** Estudio observacional ecológico. No establece causalidad.
- **Granularidad:** Datos agregados a nivel de Servicio de Salud; no análisis individual.
- **Disponibilidad variable:** Medianas ausentes en 2021–2022_T2; tramos de antigüedad
  ausentes en 2024_T1–2025_T1; discontinuidad administrativa en 2023_T2–2024_T4
  (solo afecta distribución por nivel, no otras variables).
- **Variables no incorporadas:** Capacidad instalada, dotación de especialistas,
  complejidad clínica, indicadores poblacionales ajustados.
- **Proceso de extracción:** OCR con validación manual; posible error residual en
  datos de períodos históricos.

El detalle completo de limitaciones y disponibilidad por período se encuentra en
[`docs/limitaciones.md`](limitaciones.md).

---

## Cita

Si utilizas este dataset o análisis en tu trabajo, por favor cita la fuente original:

```
Ministerio de Salud de Chile (MINSAL).
Glosa 06 – Ley de Presupuestos del Sector Público.
Reportes trimestrales de listas de espera NO GES, 2021–2025.
```

Y el repositorio:

```
Balladares, L. (2026). Análisis Longitudinal de Listas de Espera NO GES en Chile (2021–2025).
GitHub: https://github.com/LucianoBalladares/Analisis-de-Listas-de-Espera-No-GES
```

---

_Luciano Balladares · Tecnólogo Médico · Informática en Salud_
_[LinkedIn](https://www.linkedin.com/in/luciano-balladares/) · l.garridoballadares@uandresbello.edu_
