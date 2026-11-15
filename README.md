# EP3 · Equipo 1 · Caso 2 Chatbot Telco (Andesnet)

Implementación de referencia para la Evaluación Parcial 3 de ITY1102. La solución clasifica intenciones con un modelo propio entrenado en los CSV del caso y desplegado en Amazon SageMaker; genera respuestas con la API NVIDIA mediante RabbitMQ y un worker asíncrono.

> **Estado honesto:** preparación de datos, entrenamiento local, API, worker, cola, dashboard, contenedores, CI y pruebas están implementados en el repositorio. Las pruebas unitarias locales pasan. La creación de recursos AWS, el endpoint SageMaker, el certificado HTTPS público, CloudWatch real y la prueba Locust contra AWS requieren ejecutar los pasos de `docs/aws_sagemaker_paso_a_paso.md` con el Learner Lab del equipo. No se incluyen credenciales ni se afirma que esos recursos ya estén desplegados.

## 1. Arquitectura

- EC2 `t3.medium` en `us-east-1`, IP elástica, perfil `LabInstanceProfile`.
- Caddy + sslip.io + Let's Encrypt como gateway HTTPS público.
- FastAPI: `/api/predict`, `/api/conversacion`, `/api/predicciones/{id}`, `/api/health`, `/api/dashboard`, `/api/derivaciones/{conversation_id}` y `/docs`.
- Microservicio de IA invoca SageMaker Runtime con `boto3`; no contiene el modelo en la imagen.
- Endpoint serverless SageMaker con clasificador propio TF-IDF + Logistic Regression.
- PostgreSQL para predicciones, estado de intentos e historial anonimizado.
- RabbitMQ + worker LLM; el navegador nunca llama a NVIDIA.
- Prometheus + Grafana y dashboard de negocio en `/dashboard`.

Ver `docs/arquitectura.md`.

## 2. Datos y entrenamiento local

Los CSV originales están en `data/raw/` en el paquete que recibió el equipo. No deben subirse a un repositorio público ni copiarse a la imagen Docker, ya que el texto libre contiene datos identificables de prueba.

En PowerShell, desde la raíz del proyecto:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m training.prepare
python -m training.train_local
pytest -q
```

El preprocesamiento crea un split estratificado 80/20 y FAQ vigentes anonimizadas en `data/processed/`. Se entrenó una línea base TF-IDF + LogisticRegression sobre 4.680 mensajes únicos: 3.744 train y 936 test. Métricas locales registradas en `data/processed/metrics.json`: accuracy 0,8323; precision macro 0,8259; recall macro 0,8050; F1 macro 0,8131. Son métricas del entrenamiento local reproducible, no resultados de SageMaker ni evidencia cloud.

## 3. Ejecución local con Docker

1. Copiar `.env.example` a `.env` y cambiar las contraseñas.
2. Ejecutar la preparación de datos y entrenamiento local como arriba.
3. En `.env`, poner `ALLOW_LOCAL_MODEL=true` y `LOCAL_MODEL_PATH=/srv/data/processed/intent_model.joblib` solo para desarrollo local. Para AWS dejarlo en `false`.
4. Ejecutar:

```powershell
docker compose -f docker-compose.yml -f compose.local.yaml up --build -d
```

Abrir `http://localhost:8080` (chat), `http://localhost:8080/docs`, `http://localhost:8080/dashboard` y `http://localhost:8080/api/health`.

Para probar manualmente:

```powershell
$headers = @{ 'X-API-Key' = 'cambia-esta-clave' }
$body = @{ message = 'No tengo internet en mi casa' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/predict -Headers $headers -ContentType 'application/json' -Body $body
```

`/api/predict` ejecuta solo clasificación, sin encolar LLM; es el objetivo de Locust. `/api/conversacion` ejecuta clasificación y encola la redacción LLM asíncrona.

## 4. SageMaker y AWS

Seguir **completo y en orden** `docs/aws_sagemaker_paso_a_paso.md`. El script reproducible es `scripts/sagemaker_train_deploy.py`; el rol debe ser `LabRole`, región `us-east-1`, endpoint Serverless con memoria 2048 MB y concurrencia máxima 5. Si Learner Lab rechaza Serverless, usar `--mode realtime` y eliminar el endpoint al terminar la sesión.

La EC2 usa su perfil de instancia `LabInstanceProfile`; no configurar `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY` en `.env`.

## 5. Variables obligatorias antes del despliegue

- `API_KEY`: clave fuerte para `/api/predict`, `/api/conversacion` y rutas protegidas.
- `NVIDIA_API_KEY`: clave propia creada en NVIDIA Build.
- `NVIDIA_MODEL`: nombre exacto publicado por el docente en el foro; no adivinarlo.
- `SAGEMAKER_ENDPOINT_NAME`: endpoint creado por el script.
- `IMAGE_NAME`: imagen GHCR publicada por el workflow, `ghcr.io/USUARIO/REPOSITORIO:ep3`.
- Contraseñas de PostgreSQL, RabbitMQ y Grafana.
- `SITE_ADDRESS`: hostname `IP-CON-GUIONES.sslip.io` de la IP elástica.

## 6. Pruebas y rendimiento

```powershell
pytest -q
$env:API_KEY='TU_CLAVE'
locust -f locustfile.py --headless -u 10 -r 2 -t 3m --host https://TU_HOST --csv=locust_ep3
```

La carga va contra `/api/predict`, que no llama al LLM. Registrar p50, p95, p99, RPS y errores. Para el LLM, usar pocas solicitudes manuales y registrar latencia y comportamiento degradado.

## 7. Flujo de equipo y entrega

Cada integrante debe realizar commits y pull requests propios desde el 12/11/2026. El pipeline ejecuta preparación ya versionada, entrenamiento, 16 pruebas y publica la imagen al crear el tag `ep3`. Ajustar el repositorio GitHub y la visibilidad GHCR con las cuentas reales del equipo.

El informe técnico está en `docs/informe_tecnico.md`; debe completarse con capturas reales de SageMaker, EC2, CloudWatch, HTTPS, Locust y URLs antes de exportar a PDF. La presentación de máximo 6 láminas queda fuera de este paquete porque la prepara el compañero.
