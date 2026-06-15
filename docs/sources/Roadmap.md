### FASE 1: MVP de Consulta

**Objetivo:** Demostrar valor rápido creando un Agente capaz de leer el Excel maestro actual y responder con precisión matemática a preguntas de negocio en lenguaje natural. No modificaremos el Excel todavía.

**Pasos de Desarrollo:**

1. **Definición de la Capa Semántica (Semanas 1):**

   * Seleccionar 5 pestañas core (ej. `2026 Actual`, `Pipe Total`, `TAXA\_Budget`, `DE\_PARA BU`, `Metas por comercial`).
   * Crear el "Diccionario de Datos": Un documento técnico que le explique a la IA qué significa cada columna (ej. *"La columna 'ACV Real BSC' está en Reales y ya tiene el multiplicador aplicado"*).
2. **Preparación del Entorno (Semana 2):**

   * Configurar el entorno de Python usando librerías como `Pandas` (para manipular los datos).
   * Transformar las pestañas seleccionadas a un formato ultraligero (CSV o DataFrames en memoria) para que la IA los lea instantáneamente.
3. **Desarrollo del Agente (Semana 3):**

   * Implementar un framework de IA como **LangChain** o **LlamaIndex**.
   * Integrar un LLM avanzado (como GPT-4o, Claude 3.5 Sonnet o Gemini 1.5 Pro).
   * **Ingeniería de Prompts:** Configurar el *System Prompt* central: *"Eres el Analista de Ventas de TIVIT Latam. Tu objetivo es calcular ACV, cobertura y cumplimiento de presupuesto..."*
4. **Pruebas de Precisión - QA (Semana 4):**

   * Realizar una batería de 50 preguntas predefinidas (ej. *"¿Cuánto pipeline tiene Colombia para el Q3?"*).
   * **Validación cruzada:** Un analista humano compara la respuesta del Agente con la tabla dinámica del Excel original. La tolerancia de error debe ser del 0%.

**Entregable Fase 1:** Un bot conversacional (puede ser en un entorno web interno o integrado a Microsoft Teams/Slack) que responde preguntas sobre el desempeño de ventas.

### FASE 2: Flujo de Actualización

**Objetivo:** Automatizar la ingesta de datos. Que el Agente tome el archivo crudo semanal/mensual que sale del CRM (Salesforce) y actualice el Excel Maestro automáticamente.

**Pasos de Desarrollo:**

1. **Mapeo de Reglas de Transformación (Semanas 1-2):**

   * Programar la lógica de homologación: Enseñar al agente a cruzar el Excel nuevo con la pestaña `DE\_PARA BU` para asignar correctamente el "LOB" y la "Línea de Servicio".
   * Programar la lógica de monedas: El agente debe identificar el país de la oportunidad y cruzarlo con la pestaña de `TAXA` del año correspondiente para hacer la conversión matemática a Reales (R$).
2. **Desarrollo del Script de Inyección (Semanas 3-4):**

   * Usar librerías de Python (como `openpyxl` o `xlwings`) diseñadas para editar archivos Excel sin corromper fórmulas nativas, macros o gráficos.
   * Lógica de Inserción: El agente busca la última fila vacía en pestañas como `2026 Actual` o `Pipe Total` y "pega" los datos procesados.
3. **Implementación de Alertas Proactivas (Semana 5):**

   * Programar un trigger: Al terminar de actualizar el Excel, el Agente escanea los resultados y si detecta que la Cobertura bajó de 3.0x, envía una alerta al equipo comercial.
4. **Despliegue en Producción (Semana 6):**

   * Montar el script en un servidor seguro en la nube (AWS, Azure o GCP) para que se ejecute automáticamente cada vez que alguien suba el archivo del CRM a una carpeta específica.

**Entregable Fase 2:** Un pipeline de automatización completo. Cero trabajo manual en la actualización del "Seguimiento ACV Latam".

### FASE 3: Modernización de Arquitectura

**Objetivo:** Eliminar la dependencia y fragilidad de un archivo Excel de 70+ pestañas. Migrar la base de datos a un entorno relacional, manteniendo al Agente IA como interfaz principal.

**Pasos de Desarrollo:**

1. **Modelado de Base de Datos (Semanas 1-3):**

   * Diseñar un modelo de estrella (Star Schema) en una base de datos SQL (ej. PostgreSQL, SQL Server).
   * Crear Tablas de Hechos (Ventas, Pipeline) y Tablas de Dimensiones (Clientes, Ejecutivos, Geografía, Monedas/Taxas).
2. **Desarrollo ETL (Semanas 4-6):**

   * Conectar directamente el CRM (Salesforce) a la Base de Datos SQL mediante APIs. Ya no habrá necesidad de descargar Excels intermedios.
3. **Evolución del Agente IA (Semanas 7-9):**

   * Cambiar el modelo del Agente de un "Lector de Pandas/CSV" a un **Text-to-SQL Agent**.
   * Ahora el Agente convertirá la pregunta del usuario en una consulta SQL ultra rápida y segura directamente a la base de datos empresarial.
4. **Integración BI (Semanas 10-12):**

   * Conectar esta nueva base limpia y automatizada a PowerBI / Tableau para tener dashboards en tiempo real, complementados por el chat de la IA.

**Entregable Fase 3:** Una arquitectura de datos nivel Enterprise. 100% escalable, segura y gobernable.

