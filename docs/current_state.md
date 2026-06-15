# Estado actual de la Fase 1

## 1. Objetivo
Consolidar una lectura canónica de lo que el FRD espera de los datos y de lo que los extractos actuales realmente permiten procesar, sin validar todavía con el operador comercial.

## 2. Fuentes disponibles
Hay dos extractos observados: `Previa mayo - Pipe.xlsx` y `Previo mayo - Ganadas.xlsx`. El FRD documental sigue esperando capas consolidadas como `Resumen`, `2026 Actual`, `Pipe Total`, `Resumen x Comercial Latam_2026`, `Detalle de visitas` y `Paretto por pais`.

## 3. Hallazgos confirmados
`Pipe` tiene granularidad itemizada, con `TVT` repetido, duplicados exactos y campos monetarios que no deben agregarse sin validación funcional. `Ganadas` es más compacto y sirve como corte provisional de ventas cerradas, pero no se ha validado como reemplazo de `2026 Actual`.

## 4. Hipótesis pendientes
Siguen abiertas la equivalencia de `TVT`, la unidad real de una fila de `Pipe`, el campo monetario oficial de pipeline, la relación entre `Pipe` y `Ganadas`, y la equivalencia `BU` vs `LOB`. También sigue pendiente confirmar si `ACV Item em Reais` es el monto oficial para pipeline.

## 5. Cobertura actual del FRD
Solo `pipeline_positions` y `won_deals` están en estado `conditional`. `summary_snapshot`, `sales_rep_scorecard`, `sales_activity` y `client_concentration` siguen `blocked` por falta de fuente oficial o por semántica no validada. El resto de los casos FRD dependen de esas decisiones compartidas.

## 6. Riesgos principales
Doble conteo en `Pipe`, mezcla de granularidades, uso indebido de `Status da Negociação`, inferencias de budget o coverage sin fuente maestra, y uniones entre libros sin llave validada. El riesgo funcional principal sigue siendo responder como oficial algo que hoy solo es provisional.

## 7. Próximo trabajo
Esperar la validación del operador comercial y, con esa respuesta, convertir los casos provisionales en reglas definitivas o mantener bloqueos explícitos. Mientras tanto, el sistema debe seguir procesando, perfilando y explicando límites, no inventando verdad comercial.
