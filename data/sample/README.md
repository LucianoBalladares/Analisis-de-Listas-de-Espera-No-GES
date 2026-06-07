# Datos de muestra

Este directorio contiene un archivo Excel de muestra del período 2023_T1
que puede usarse para probar el pipeline de ingesta sin acceso a la fuente original.

Los datos provienen de la **Glosa 06 – Ley de Presupuestos (MINSAL)**,
que es información pública oficial disponible en https://www.minsal.cl

## Uso

```bash
python pipeline/orchestration/pipeline_runner.py data/sample/2023_T1.xlsx
```

## Estructura

El archivo contiene las tres hojas requeridas por el pipeline:

- `listas_espera_ss_trimestre`
- `personas_nacional_trimestre`
- `nivel_atencion_trimestre`
