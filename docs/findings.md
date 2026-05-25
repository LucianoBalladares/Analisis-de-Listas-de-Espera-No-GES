# Hallazgos del Análisis

**Análisis Longitudinal de Listas de Espera NO GES en Chile (2021–2025)**
Luciano Balladares · Mayo 2025

> Este documento resume los hallazgos principales del análisis.
> El informe completo (24 páginas) y el dashboard interactivo están disponibles
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
**Períodos analizados:** ~17 trimestres (2022_T3 – 2025_T4 con medianas disponibles)
**Fuente:** Glosa 06 – Ley de Presupuestos (MINSAL)

---

## Hallazgo 1 — La relación entre mediana y backlog histórico fue inestable

La relación entre la mediana de espera y la proporción de casos de larga
espera (>36 meses) fue débil e inestable durante gran parte del período
analizado, con señales recientes de convergencia.

**Evidencia:**

- R² < 50% en la mayoría de los trimestres entre 2022 y 2024, tanto en CNE como en IQ.
- En 2025_T3 y 2025_T4 el ajuste aumentó significativamente, alcanzando R² > 75% en ambos
  tipos de prestación.
- La segmentación por cuadrantes evidenció coexistencia simultánea de cuatro perfiles:
  alta mediana con baja cola histórica, baja mediana con alta acumulación, y perfiles mixtos.

**Implicancia:** La utilización aislada de la mediana como indicador de desempeño puede
ocultar diferencias relevantes en la carga histórica. Dos Servicios de Salud con
medianas similares pueden presentar niveles muy distintos de backlog crónico y necesidades
operacionales completamente diferentes.

---

## Hallazgo 2 — Heterogeneidad territorial persistente y estructural

Las listas de espera NO GES presentaron heterogeneidad territorial persistente
durante todo el período analizado. La brecha entre Servicios de Salud extremos
alcanzó aproximadamente **200 días en CNE** y **150 días en IQ**.

**Servicios con medianas consistentemente elevadas en CNE:**

- SS Metropolitano Norte
- SS Antofagasta
- SS Araucanía Sur
- SS Tarapacá

**Servicios con medianas consistentemente bajas en CNE:**

- SS Aconcagua
- SS Arica y Parinacota
- SS Aysén

**Evidencia adicional:**

- La estabilidad relativa de estas posiciones a lo largo de ~17 trimestres sugiere
  restricciones estructurales persistentes, no fluctuaciones transitorias de demanda.
- Los patrones territoriales en IQ difieren de los identificados en CNE, tanto en
  magnitud como en la composición de Servicios de Salud afectados.

**Implicancia:** Políticas nacionales uniformes tienen efectividad limitada frente a
realidades operacionales heterogéneas. La persistencia de Servicios de Salud
sistemáticamente rezagados indica riesgo de cronificación territorial y ampliación
de brechas de acceso.

---

## Hallazgo 3 — Cuatro perfiles operacionales diferenciados

La segmentación basada en mediana relativa y proporción de registros >36 meses
permite identificar cuatro perfiles funcionales con necesidades de intervención
distintas.

| Perfil                  | Característica                     | Estrategia sugerida                                 |
| ----------------------- | ---------------------------------- | --------------------------------------------------- |
| **Crítico estructural** | Alta mediana + alta cola larga     | Intervención intensiva y apoyo central diferenciado |
| **Congestión reciente** | Alta mediana + baja cola histórica | Optimización de flujo y capacidad ambulatoria       |
| **Backlog persistente** | Baja mediana + alta cola larga     | Resolución focalizada de casos históricos           |
| **Buen desempeño**      | Baja mediana + baja cola           | Benchmarking y transferencia de prácticas           |

**Implicancia:** La utilización de indicadores agregados nacionales puede ocultar
diferencias críticas entre Servicios de Salud. La segmentación operacional permite
priorización más precisa y estrategias adaptadas al tipo de deterioro predominante.

---

## Hallazgo 4 — Divergencia operacional entre CNE e IQ

Los patrones territoriales de espera difieren significativamente entre Consultas de
Nueva Especialidad (CNE) e Intervenciones Quirúrgicas (IQ), sugiriendo que los
cuellos de botella operacionales no son homogéneos entre tipos de prestación.

**Servicios con medianas más altas en IQ** (composición distinta a CNE):

- SS Aconcagua
- SS O'Higgins
- SS Biobío
- SS Tarapacá

**Evidencia:**

- Las medianas CNE mostraron mayor dispersión entre los Servicios de Salud extremos.
- En IQ, las diferencias tendieron a concentrarse en un rango más homogéneo.
- Un Servicio de Salud puede presentar buen desempeño en CNE y simultáneamente
  estar rezagado en IQ, y viceversa.

**Implicancia:** Las estrategias de reducción de listas de espera no deben diseñarse
como intervenciones uniformes para todas las prestaciones. CNE requiere abordar
restricciones de acceso ambulatorio especializado; IQ requiere intervención sobre
capacidad quirúrgica, pabellones y continuidad operatoria.

---

## Hallazgo 5 — Recuperación post-pandemia marcadamente desigual

La recuperación de medianas de espera entre 2022_T3 y 2025_T4 fue
heterogénea entre Servicios de Salud, evidenciando diferencias importantes en
resiliencia operacional.

**Casos de recuperación destacada:**

| Servicio de Salud        | Prestación | Mediana inicial | Mediana final | Variación  |
| ------------------------ | ---------- | --------------- | ------------- | ---------- |
| SS Metropolitano Oriente | CNE        | ~331 días       | ~127 días     | −204 días  |
| SS Los Ríos              | IQ         | >1.000 días     | ~189 días     | >−800 días |

**Servicios persistentemente rezagados** (mejoras absolutas insuficientes):

- SS Metropolitano Norte (CNE): continúa en el extremo superior nacional
- SS Tarapacá: tendencia persistentemente elevada en ambas prestaciones
- SS Araucanía Norte (CNE): aumento de mediana en el período

**Implicancia:** La recuperación asistencial depende no solo de disponibilidad de
recursos, sino también de capacidad organizacional y operacional local.
La existencia de casos de recuperación exitosa sugiere potencial de transferencia
de prácticas hacia Servicios de Salud persistentemente rezagados.

---

## Hallazgo 6 — Concentración estructural en nivel terciario

Entre 2021 y 2025, la resolución de listas de espera NO GES se mantuvo
fuertemente concentrada en el nivel terciario de atención durante todo el período.

| Nivel de atención | Participación |
| ----------------- | ------------- |
| Terciario         | 83 – 90%      |
| Primario          | 8 – 10%       |
| Secundario        | 1 – 3%        |

**Evidencia adicional:**

- Se observa una leve disminución relativa de la concentración terciaria hacia los
  períodos más recientes, sin modificar significativamente la estructura general.
- Entre 2023_T2 y 2024_T4 se identificó una discontinuidad en la serie asociada a
  cambios administrativos en criterios de clasificación reportados por el MINSAL.
  **Este período no es directamente comparable con el resto de la serie.**

**Implicancia:** Incrementos de capacidad exclusivamente hospitalaria podrían tener
impacto limitado si no se acompañan de mecanismos de resolución ambulatoria,
triage especializado y coordinación entre niveles asistenciales.

---

## Hallazgo 7 — Reducción de medianas pese a aumento sostenido de registros

Las medianas de espera mostraron reducción sostenida durante el período analizado
pese al aumento simultáneo del volumen de registros acumulados.

**Variaciones entre 2022_T3 y 2025_T4:**

| Indicador              | CNE               | IQ        |
| ---------------------- | ----------------- | --------- |
| Variación de mediana   | −49 días (−16,3%) | −171 días |
| Variación de registros | +14,6%            | +29,4%    |
| % registros >36 meses  | ~12% → ~3%        | —         |

**Implicancia:** La mejora agregada nacional no se distribuyó homogéneamente.
Servicios de Salud como Metropolitano Norte, Tarapacá y Araucanía Sur
continuaron presentando niveles elevados de espera incluso en los períodos
más recientes, evidenciando que indicadores nacionales pueden ocultar
desigualdades operacionales relevantes entre territorios.

---

## Discusión — Síntesis analítica

Los resultados en conjunto son consistentes con la existencia de múltiples tipos
de congestión operacional dentro del sistema, no de un único mecanismo de saturación.

Tres tensiones analíticas estructuran la discusión:

1. **La crisis es heterogénea.** La estabilidad relativa de las posiciones
   territoriales a lo largo de ~17 trimestres sugiere que las diferencias observadas
   responden a restricciones estructurales y no a fluctuaciones transitorias de demanda.

2. **Existen múltiples mecanismos de congestión.** CNE y IQ presentan distribuciones
   territoriales distintas; el flujo reciente y el backlog histórico no evolucionan
   de manera conjunta. Esto hace que indicadores únicos agregados sean insuficientes
   para caracterizar el estado del sistema.

3. **La recuperación post-pandemia amplificó las diferencias.** Mientras algunos
   Servicios de Salud mostraron recuperaciones significativas, otros permanecieron
   críticamente rezagados. La mejora nacional agregada no implicó reducción de brechas
   territoriales.

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
- **Disponibilidad variable:** Medianas ausentes en 2021–2022; tramos de antigüedad
  ausentes en 2024–2025; discontinuidad administrativa en 2023_T2–2024_T4.
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
Balladares, L. (2025). Análisis Longitudinal de Listas de Espera NO GES en Chile (2021–2025).
GitHub: https://github.com/LucianoBalladares/Analisis-de-Listas-de-Espera-No-GES
```

---

_Luciano Balladares · Tecnólogo Médico · Informática en Salud_
_[LinkedIn](https://www.linkedin.com/in/luciano-balladares/) · l.garridoballadares@uandresbello.edu_
