# Validaciones Pendientes

## Fuentes oficiales

- ¿Cuál es la fuente oficial para `Resumen` o su sustituto? Bloquea `1.1`, `1.2`, `2.1` y `5.1`.
- ¿`Ganadas` representa ventas reales del periodo y reemplaza `2026 Actual`? Bloquea `1.3` y `3.1`.
- ¿`Resumen x Comercial Latam_2026` existe y cuál es su equivalente real? Bloquea `4.1`.
- ¿`Detalle de visitas` existe y cuál es su fuente oficial? Bloquea `4.3`.
- ¿`Paretto por pais` existe y cómo se define `Participacion`? Bloquea `6.1`.

## Pipeline

- ¿Cuál es el campo monetario oficial de pipeline? Bloquea `3.2`, `5.2` y `5.3`.
- ¿`ACV Item em Reais` es el monto oficial de pipeline o solo un candidato? Bloquea `3.2`, `5.2` y `5.3`.
- ¿`Status da Negociação` es una dimensión reportable o un metadato operativo? Bloquea `3.2`.
- ¿Qué representa `TVT` exactamente y cuál es la unidad real de una fila en `Pipe`? Bloquea la consolidación segura de `pipeline_positions` y `won_deals`.
- ¿Las 55 filas duplicadas exactas en `Pipe` son esperadas o deben limpiarse? Bloquea la preparación de `pipeline_positions`.

## Dimensiones y tiempo

- ¿`BU` puede usarse como `LOB` para reporting? Bloquea `3.1`.
- ¿Qué campo temporal gobierna cada métrica: cierre real, cierre estimado o creación? Bloquea `1.3`, `3.1`, `3.2`, `5.2` y `5.3`.
- ¿Cómo se relacionan `Pipe` y `Ganadas` si comparten cortes distintos y no comparten `TVT`? Bloquea cruces operativos entre ambos extractos.
