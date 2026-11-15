# EP3 · Equipo 1 · Chatbot Telco · Informe técnico (borrador para completar con evidencia AWS)

**Asignatura:** ITY1102 Arquitectura de Sistemas de Inteligencia Artificial  
**Caso:** 2 · Chatbot inteligente para Andesnet Telecomunicaciones S.A.  
**Integrantes:** [APELLIDOS Y NOMBRES DE AMBOS]  
**Fecha:** [FECHA DE ENTREGA]

> **Estado actualizado al 15 de noviembre de 2026:** se verificó el despliegue en EC2, el acceso HTTPS, SageMaker Serverless, una respuesta generada mediante NVIDIA y registros de CloudWatch. Las evidencias se documentan al final del informe. Permanecen pendientes las mediciones y validaciones expresamente identificadas.

## 1. Modelo y endpoint (IE1)

Se implementó un clasificador supervisado de intención basado en TF-IDF de unigramas/bigramas y regresión logística con balanceo de clases (`class_weight=balanced`, `max_iter=1500`, `C=3.0`). Se combinaron tickets y conversaciones del caso 2. Las etiquetas se normalizaron a siete intenciones: `consulta_saldo`, `falla_conexion`, `cambio_plan`, `estado_visita`, `anulacion`, `portabilidad` y `consulta_general`. Los alias de las fuentes originales se homologaron en `training/prepare.py`.

El conjunto final contiene 4.680 mensajes únicos: 3.744 para entrenamiento (80%) y 936 para prueba (20%), separados de forma estratificada con `random_state=42`. Los datos de texto libre se anonimizan antes de generar los CSV procesados. La FAQ se limita a artículos vigentes con respuesta no vacía y se asocia a una intención normalizada: 354 artículos.

**Resultados medidos localmente:**

| Métrica | Resultado |
|---|---:|
| Accuracy | 0,8323 |
| Precision macro | 0,8259 |
| Recall macro | 0,8050 |
| F1 macro | 0,8131 |
| Train / test | 3.744 / 936 |

El detalle por clase y matriz de confusión está en `data/processed/metrics.json`. Estas cifras corresponden a la ejecución local del clasificador; SageMaker volverá a entrenar el modelo con Script Mode usando los mismos archivos anonimizados. No deben presentarse como métricas de un endpoint cloud hasta completar esa ejecución.

**Configuración SageMaker desplegada:** región `us-east-1`; endpoint Serverless `chatbot-telco-ep3` en estado `InService`, memoria 2.048 MB y concurrencia máxima 1; versión del modelo `telco-equipo1-v1`. La API utiliza las credenciales AWS disponibles en EC2 para invocar el endpoint. Se selecciona Serverless por su cobro ligado al uso y para evitar mantener una instancia de inferencia encendida en Learner Lab. Si el laboratorio lo rechaza, la alternativa documentada es endpoint realtime `ml.m5.large`, encendido solo durante la sesión y eliminado al terminar.

**Evidencia AWS verificada (15-11-2026):** el endpoint SageMaker Serverless `chatbot-telco-ep3` se encuentra en estado `InService`, con 2.048 MB de memoria y concurrencia máxima 1. Se verificaron invocaciones desde FastAPI y respuestas que incluyen `model_version=telco-equipo1-v1`.

La evidencia de inferencia se conserva en `docs/evidencias_aws/ep3_sagemaker_nvidia.json`.

**Entrenamiento AWS verificado:** el trabajo de entrenamiento de SageMaker `chatbot-telco-ep3`, creado el 13-11-2026 a las 17:16 UTC, figura con estado `Completed` en la región `us-east-1`.

La consulta se realizó mediante `boto3.list_training_jobs` y `boto3.describe_training_job`.

**Trazabilidad del modelo verificada:** el entrenamiento utilizó la imagen SageMaker Scikit-learn `1.2-1-cpu-py3` y finalizó el 13-11-2026 a las 17:19 UTC. El artefacto generado fue:

`s3://chatbot-telco/telco-ep3/output/chatbot-telco-ep3/output/model.tar.gz`

Mediante `describe_endpoint`, `describe_endpoint_config` y `describe_model` se confirmó que el endpoint `chatbot-telco-ep3`, en estado `InService`, utiliza exactamente ese artefacto S3.

Esto verifica la asociación entre el entrenamiento y el modelo desplegado. Las métricas de evaluación deben documentarse por separado.

## 2. Consumo e interpretabilidad (IE2)

El microservicio FastAPI no carga el modelo en su imagen en producción. Envía el mensaje a SageMaker Runtime con `boto3.invoke_endpoint` usando el rol de instancia EC2. La respuesta contiene la intención, probabilidad por clase y versión del modelo. El API entrega la intención y su probabilidad para que el sistema/ejecutivo entienda la clasificación. Si la confianza queda bajo el umbral configurable `CONFIDENCE_THRESHOLD` (inicialmente 0,45), se presenta como `desconocida` y se solicita reformulación.

Las reglas de negocio están fuera del modelo: intención `anulacion`, molestia detectada, solicitud explícita de hablar con una persona o tres intentos consecutivos fallidos provocan derivación. El sistema conserva historial anonimizado por `conversation_id`, consultable por `/api/derivaciones/{conversation_id}`. La cancelación nunca se ejecuta automáticamente.

`/api/predict` entrega solo la predicción sin encolar el LLM. `/api/conversacion` realiza la predicción y encola la redacción asíncrona con artículos FAQ relevantes. El resultado del LLM se consulta después en `/api/predicciones/{id}`. Si NVIDIA falla, la predicción no se pierde y `llm_status` pasa a `degraded`.

**Evidencia AWS verificada (15-11-2026):** se realizó una conversación con el mensaje "No tengo internet en casa". SageMaker clasificó la intención como `falla_conexion`, con confianza `0.798521` y versión `telco-equipo1-v1`. El procesamiento asíncrono mediante NVIDIA finalizó con `llm_status=completed` y generó una recomendación para solucionar el problema de conexión.

La respuesta se conserva en `docs/evidencias_aws/ep3_sagemaker_nvidia.json`. Esta evidencia demuestra una respuesta completada; no constituye una prueba de modo degradado ni una medición de latencia extremo a extremo.

## 3. Plataforma, infraestructura y costos (IE4, IE5)

**Infraestructura desplegada (15-11-2026):** Amazon EC2 `t3.medium` con Ubuntu 24.04 en `us-east-1`. Docker Compose ejecuta siete servicios: FastAPI, Caddy, PostgreSQL, RabbitMQ, worker, Prometheus y Grafana.

Caddy proporciona acceso HTTPS mediante `https://18-215-177-17.sslip.io/`. Se verificó el funcionamiento de `/api/health` y la comunicación con SageMaker Serverless.

La instancia utiliza actualmente una dirección IPv4 pública dinámica. **No se ha configurado una Elastic IP**, por lo que la dirección y el dominio `sslip.io` podrían cambiar si se detiene y vuelve a iniciar EC2.

El despliegue utiliza credenciales AWS asociadas a la instancia. La configuración de seguridad y los artefactos de S3 deben verificarse por separado antes de declarar su cumplimiento completo.

**Diagrama de despliegue:** ver `docs/arquitectura.md` y su diagrama Mermaid.

**Cold start:** ejecutar `scripts/measure_endpoint.py` para medir una primera invocación y otra después de 600 segundos sin uso. Registrar ambos valores, fecha, endpoint, región y memoria.  
`[PENDIENTE AWS: latencia invocación 1 = ___ ms; latencia invocación 2 tras 10 min = ___ ms]`.

**CloudWatch:** `scripts/cloudwatch_metrics.py` consulta `Invocations` y `ModelLatency` de `AWS/SageMaker`. Adjuntar capturas y logs del microservicio.  
**Evidencia parcial de CloudWatch (15-11-2026):** se consultaron 161 eventos del grupo `/aws/sagemaker/Endpoints/chatbot-telco-ep3` durante la prueba de carga. Se observaron múltiples invocaciones HTTP 200 y alertas de permisos durante la inicialización. No se identificó una causa confirmada del error HTTP 503 registrado por FastAPI.

Los registros relevantes se guardaron en `docs/evidencias_aws/ep3_cloudwatch_sagemaker.txt`.

**Métricas CloudWatch obtenidas (15-11-2026):** se consultó el espacio de nombres `AWS/SageMaker` para el endpoint `chatbot-telco-ep3`, con períodos de 60 segundos.

| Hora UTC | Invocations | ModelLatency promedio |
|---|---:|---:|
| 17:45 | 2 | 239,57 ms |
| 17:46 | 5 | 107,21 ms |
| 17:47 | 6 | 3,11 ms |
| 17:48 | 4 | 2,92 ms |
| **Total** | **17** | — |

Los valores de `ModelLatency` se convirtieron de microsegundos a milisegundos. Estas métricas representan el procesamiento en SageMaker y no incluyen toda la latencia de FastAPI ni la generación de respuestas NVIDIA.

**Evidencia:** `docs/evidencias_aws/ep3_cloudwatch_metricas.txt`.

**Pendiente:** medición de latencia extremo a extremo con NVIDIA y prueba de cold start después de 10 minutos sin invocaciones.

**Costos mensuales:** completar con AWS Pricing Calculator para el volumen de 340.000 contactos/mes y escenario piloto del 10%. La cotización debe indicar fecha, región, horas EC2, invocaciones, memoria/duración Serverless, GB y solicitudes S3. El costo NVIDIA debe calcularse con la tarifa pagada del modelo exacto publicado por el docente, no con la cuota gratuita.

| Componente | Supuesto/uso | Costo mensual USD |
|---|---|---:|
| EC2 t3.medium | Horas encendida según operación | [PENDIENTE CALCULADORA] |
| SageMaker Serverless | Memoria × duración × invocaciones | [PENDIENTE CALCULADORA] |
| S3 | Datos procesados + requests | [PENDIENTE CALCULADORA] |
| NVIDIA LLM | Volumen tokens con tarifa pagada del modelo del curso | [PENDIENTE TARIFA/MODELO] |
| **Total** |  | **[PENDIENTE]** |

La selección Serverless reduce el costo ocioso del endpoint frente a realtime, a cambio de variabilidad y cold start. Se debe comparar el tiempo medido con el endpoint realtime y con alternativas como un modelo embebido en EC2 o Amazon Bedrock, manteniendo la misma carga de prueba.

## 4. Integración y seguridad (IE7)

| Método | Ruta | Acceso | Propósito |
|---|---|---|---|
| GET | `/api/health` | Público | Estado de base, SageMaker, RabbitMQ y configuración NVIDIA |
| POST | `/api/predict` | X-API-Key | Clasificación síncrona sin LLM; objetivo de carga |
| POST | `/api/conversacion` | X-API-Key | Clasifica y encola generación de respuesta |
| GET | `/api/predicciones/{id}` | X-API-Key | Resultado, versión y respuesta LLM si está lista |
| GET | `/api/derivaciones/{conversation_id}` | X-API-Key | Historial anonimizado para derivación humana |
| GET | `/api/dashboard` | X-API-Key | Métricas de negocio |
| POST | `/api/feedback` | X-API-Key | Registro de valoración CSAT (prototipo) |
| GET | `/docs` | Público | Swagger/OpenAPI |
| GET | `/dashboard` | Público | Dashboard visual; requiere clave para consultar métricas |

La API exige `X-API-Key`, valida entrada con Pydantic (422), limita frecuencia (429) y devuelve 401 si falta la clave. Caddy publica HTTPS. Las claves se guardan en `.env` del servidor y no en el repositorio ni en la imagen. EC2 obtiene credenciales AWS desde `LabInstanceProfile`; no hay access keys estáticas.

Antes de guardar o encolar, `app/privacy.py` enmascara RUT, nombre indicado por expresiones, correo, teléfono, dirección indicada por expresiones y tarjeta. El worker recibe el mensaje anonimizado y los artículos FAQ relevantes, nunca la base completa. El LLM no se invoca desde navegador. La llamada se protege con timeout, reintentos exponenciales para 429/errores transitorios, intervalo de ritmo para respetar el límite de solicitudes y modo degradado.

**Secuencia:** cliente → HTTPS/Caddy → FastAPI → SageMaker → reglas de derivación → PostgreSQL; si aplica, FastAPI → anonimización → RabbitMQ → worker → NVIDIA → PostgreSQL → consulta posterior por ID.

## 5. Pruebas y calidad (IE10)

Se implementaron 16 pruebas automatizadas en `tests/`, que cubren petición válida, validación 422, autenticación 401, rate limit 429, anonimización de identificadores, fallo simulado del LLM y modo degradado, derivación por anulación, solicitud explícita de humano, tres intentos fallidos, persistencia, endpoint de salud, ruta conversacional, separación del endpoint de carga y validación de artefactos FAQ/dataset.

**Resultado local:** `pytest -q` → **16 passed**.  
**Pruebas de carga AWS realizadas el 15-11-2026:** se ejecutaron dos pruebas con Locust 2.47.0, de 180 segundos cada una.

| Métrica | Infraestructura | Inferencia SageMaker |
|---|---|---|
| Rutas | `GET /`, `GET /api/health` | `POST /api/predict` |
| Usuarios virtuales | 2 | 1 |
| Solicitudes | 116 | 17 |
| Exitosas | 116 | 16 |
| Errores | 0 (0 %) | 1 (5,88 %) |
| p50 | 140 ms | 84 ms |
| p95 | 190 ms | Aproximadamente 7.400 ms |
| p99 | 290 ms | Aproximadamente 7.400 ms |
| RPS | 0,65 | Aproximadamente 0,10 |

La prueba de inferencia registró un HTTP 503 a las 17:46:32 UTC. CloudWatch mostró invocaciones exitosas antes y después, pero no se confirmó la causa del error.

Las métricas de infraestructura no representan tiempos de inferencia. La prueba de `/api/predict` no incluye generación NVIDIA y, por su bajo número de solicitudes, sus percentiles son aproximados.

Evidencias: `docs/evidencias_aws/ep3_carga_aws.html`, `docs/evidencias_aws/ep3_predict_autenticado_aws.html` y sus archivos CSV asociados.

El RNF1 del caso solicita p95 inferior a 3 segundos desde que termina de escribir hasta que la respuesta LLM está lista. Medir por separado el camino asíncrono `/api/conversacion` con pocas peticiones, dado el límite gratuito de NVIDIA. Si no se cumple, ajustar timeout, tamaño del contexto FAQ, memoria/concurrencia Serverless, worker y/o estrategia de caché, e informar la medición real.

**Oportunidades de optimización:**

1. Cachear artículos FAQ por intención y reducir tokens enviados al LLM; costo incremental aproximado: bajo, sujeto a memoria Redis si se incorpora.
2. Ajustar memoria/concurrencia Serverless con mediciones de `ModelLatency` y cold start; costo: recalcular consumo por memoria y duración en AWS Pricing Calculator.
3. Aplicar rate limit distribuido y escalado horizontal del worker con cola RabbitMQ; costo: recursos adicionales de worker/EC2 y posible almacenamiento Redis administrado; cuantificar con la calculadora.

## Anexo A · Referencias (APA 7)

- Amazon Web Services. (s. f.). *Amazon SageMaker Developer Guide*. https://docs.aws.amazon.com/sagemaker/latest/dg/whatis.html
- Amazon Web Services. (s. f.). *Serverless Inference*. https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html
- NVIDIA. (s. f.). *NVIDIA API Catalog*. https://build.nvidia.com/
- scikit-learn developers. (s. f.). *Working with text data*. https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html

## Anexo B · Declaración de uso de IA generativa

Declaramos que se utilizó ChatGPT como apoyo para estructurar código, documentación, pruebas y revisión técnica. Los integrantes revisaron y deben validar los resultados, ejecutar el despliegue, comprobar las métricas y asumir responsabilidad por el contenido final. No se ingresaron claves secretas en el asistente ni se deben publicar datos personales.  
**Integrante 1:** ____________________ **Firma:** ____________________  
**Integrante 2:** ____________________ **Firma:** ____________________

## Anexo C · Repositorios y sistema (completar tras despliegue)

| Elemento | Valor |
|---|---|
| Front HTTPS | `https://18-215-177-17.sslip.io/` (verificado) |
| Swagger `/docs` | `https://18-215-177-17.sslip.io/docs` (verificado desde navegador, OpenAPI 3.1) |
| Health `/api/health` | `https://18-215-177-17.sslip.io/api/health` (verificado: HTTP 200) |
| API key de prueba del docente | `[GENERAR Y ENTREGAR POR CANAL SEGURO]` |
| Endpoint SageMaker | `chatbot-telco-ep3` (verificado InService) |
| Repositorio y tag | `https://github.com/haloblack/chatbot-telco-ep3` · `ep3` |
| Último workflow verde | `[URL_GITHUB_ACTIONS]` |
| Usuario GitHub integrante 1 | `haloblack` |
| Usuario GitHub integrante 2 | `[PENDIENTE]` |

## Actualización de evidencias AWS — 15 de noviembre de 2026

### Despliegue verificado

El sistema fue desplegado en una instancia Amazon EC2 t3.medium con Ubuntu 24.04, utilizando Docker Compose.

Se verificaron siete servicios activos: FastAPI, Caddy, PostgreSQL, RabbitMQ, worker, Prometheus y Grafana.

URL pública HTTPS:
https://18-215-177-17.sslip.io/

Endpoint de salud:
https://18-215-177-17.sslip.io/api/health

El endpoint de salud confirmó conectividad con PostgreSQL, RabbitMQ y SageMaker en estado InService.

### Inferencia y generación de respuestas

Se verificó una conversación con el mensaje:
"No tengo internet en casa".

Resultados:
- Intención: falla_conexion.
- Confianza: 0.798521.
- Versión del modelo: telco-equipo1-v1.
- Estado de generación NVIDIA: completed.
- Respuesta: "Reinicia el router, revisa las luces y verifica que no haya corte en tu zona. Si no te sirve, te recomiendo un ejecutivo."

### Pruebas de carga

Prueba de infraestructura:
- Duración: 180 segundos.
- Solicitudes: 116.
- Errores: 0%.
- p50: 140 ms.
- p95: 190 ms.
- p99: 290 ms.
- RPS: 0.65.

Prueba de inferencia SageMaker:
- Duración: 180 segundos.
- Solicitudes: 17.
- Exitosas: 16.
- Errores: 1 (HTTP 503).
- Tasa de errores: 5.88%.
- p50: 84 ms.
- p95: aproximadamente 7400 ms.
- p99: aproximadamente 7400 ms.
- RPS: aproximadamente 0.10.

Los resultados de infraestructura no representan latencia de inferencia ni generación LLM.

### Investigación del error HTTP 503

FastAPI registró un error HTTP 503 el 15 de noviembre de 2026 a las 17:46:32 UTC.

CloudWatch registró invocaciones exitosas de SageMaker antes y después del error. No se confirmó su causa.

### Evidencias disponibles

Los archivos se encuentran en:
docs/evidencias_aws/

Incluyen informes HTML y CSV de Locust, estado de contenedores, conversación completada, registros de CloudWatch y resumen de pruebas.

### Mediciones pendientes

- Latencia completa de conversación incluyendo NVIDIA.
- Pruebas de arranque en frío de SageMaker.
- Métricas CloudWatch Invocations y ModelLatency.
- Evaluación manual de 20 respuestas LLM.
- Estimación de costos mediante AWS Pricing Calculator.

Estas mediciones no deben presentarse como completadas hasta disponer de evidencia.
