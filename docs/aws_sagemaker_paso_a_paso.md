# Guía de despliegue AWS + SageMaker · Equipo 1

Esta guía está escrita para Windows + AWS Academy Learner Lab. Seguir el orden. No pegar claves AWS en archivos, GitHub, Docker ni el repositorio. El laboratorio puede suspender los recursos al cerrar sesión.

## A. Preparación local (Windows)

1. Extraer `chatbot_telco_ep3.zip` en una carpeta simple, por ejemplo `C:\EP3\chatbot_telco_ep3`.
2. Instalar/abrir Docker Desktop y esperar que indique Engine running.
3. Abrir PowerShell en esa carpeta.
4. Crear entorno e instalar dependencias:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

5. Preparar y entrenar:

```powershell
python -m training.prepare
python -m training.train_local
pytest -q
```

6. Copiar `.env.example` a `.env`. Cambiar `API_KEY`, `POSTGRES_PASSWORD`, `RABBITMQ_PASSWORD`, `GRAFANA_PASSWORD`. Para la prueba local, establecer `ALLOW_LOCAL_MODEL=true`, `SITE_ADDRESS=:80`, `SAGEMAKER_ENDPOINT_NAME=` y dejar las variables NVIDIA vacías si solo se prueba la clasificación. No usar estas credenciales de ejemplo en AWS.
7. Ejecutar localmente:

```powershell
docker compose -f docker-compose.yml -f compose.local.yaml up --build -d
docker compose -f docker-compose.yml -f compose.local.yaml ps
```

8. Probar `http://localhost:8080`, `/docs`, `/api/health` y `/dashboard`. Si el puerto 8080 no abre, probar `http://localhost` según el mapeo de puertos mostrado por Docker.
9. Detener al terminar: `docker compose -f docker-compose.yml -f compose.local.yaml down`.

## B. GitHub y publicación de imagen :ep3

1. Crear un repositorio privado del equipo (o el que ya use EP2). No subir `.env`, claves AWS/NVIDIA ni `data/raw/*.csv`.
2. `data/processed/` contiene el conjunto de entrenamiento/prueba anonimizado y FAQ vigentes; se versiona para reproducir el entrenamiento. El ZIP de trabajo conserva los CSV originales para preparar de nuevo localmente.
3. Cada integrante configura su propio usuario Git, crea una rama `feature/...`, realiza commits y abre su pull request. El enunciado exige actividad propia de ambos desde el 12/11/2026.
4. Subir el código y fusionar a la rama base.
5. Antes de publicar, confirmar que CI está verde y que hay 16 pruebas aprobadas.
6. Crear y subir el tag exacto:

```powershell
git tag ep3
git push origin ep3
```

7. En GitHub > Actions, esperar que finalice el workflow `EP3 CI and publish`. En GitHub > Packages, verificar `ghcr.io/USUARIO/REPOSITORIO:ep3`. Si GHCR queda privado, hacerlo público o autenticar Docker en EC2 con un token de solo lectura; nunca guardar ese token en el repositorio.

## C. Crear bucket S3

1. Entrar a AWS Academy Learner Lab y pulsar **Start Lab**. Esperar que el indicador esté verde y abrir AWS Console.
2. Confirmar región **US East (N. Virginia) us-east-1** en la barra superior.
3. Abrir S3 > Create bucket. Nombre globalmente único, por ejemplo `telco-ep3-equipo1-<identificador-no-personal>`. Región us-east-1. Mantener Block all public access activado y cifrado por defecto.
4. No subir `data/raw/` ni CSV originales con identificadores. Solo `data/processed/train.csv`, `test.csv` y `faq.json`.
5. Guardar el nombre del bucket; se usará en SageMaker.

## D. Entrenar y crear endpoint en SageMaker

El script incluido crea el training job y endpoint. Se ejecuta en un entorno AWS con credenciales temporales del Learner Lab y el rol permitido. La opción preferida es un notebook/entorno SageMaker que tenga asignado el rol `LabRole`. No crear usuarios IAM ni access keys.

1. En AWS Console > SageMaker, abrir el entorno de notebook/Studio que permita el Learner Lab. Si el laboratorio no permite crearlo, documentar el error y consultar al docente cómo ejecutar L11; no crear roles alternativos.
2. Subir el ZIP del proyecto al notebook y extraerlo. Asegurar que `data/raw/` contiene los CSV del caso.
3. Abrir Terminal del notebook, entrar a la raíz del proyecto e instalar:

```bash
pip install -r requirements-sagemaker.txt
python -m training.prepare
```

4. Comprobar `data/processed/data_summary.json`: debe indicar mensajes, train/test y FAQ. Revisar que los textos se encuentren anonimizados.
5. Ejecutar entrenamiento y endpoint serverless (cambiar el nombre de bucket):

```bash
python scripts/sagemaker_train_deploy.py --bucket NOMBRE_BUCKET --prefix equipo1/chatbot-telco --endpoint telco-equipo1-intent-ep3 --role LabRole --region us-east-1 --mode serverless --memory-mb 2048 --max-concurrency 5
```

6. El script carga train/test/FAQ anonimizados a S3, entrena con SageMaker Script Mode, empaqueta el pipeline TF-IDF + LogisticRegression, despliega Serverless y hace una invocación de prueba.
7. SageMaker > Inference > Endpoints. Esperar estado **InService**. Guardar captura del nombre, estado, memoria/concurrencia si la consola los muestra, y training job.
8. Si Learner Lab rechaza Serverless, guardar captura del error y volver a ejecutar con `--mode realtime`. Ese camino usa `ml.m5.large`, cobra por hora encendido y se debe borrar al terminar la sesión:

```bash
python scripts/sagemaker_train_deploy.py --bucket NOMBRE_BUCKET --prefix equipo1/chatbot-telco --endpoint telco-equipo1-intent-ep3 --role LabRole --region us-east-1 --mode realtime
python scripts/delete_endpoint.py --endpoint telco-equipo1-intent-ep3 --region us-east-1
```

9. Probar el endpoint desde el notebook:

```python
import boto3, json
rt=boto3.client('sagemaker-runtime',region_name='us-east-1')
r=rt.invoke_endpoint(EndpointName='telco-equipo1-intent-ep3',ContentType='application/json',Body=json.dumps({'text':'No tengo internet en mi casa'}))
print(r['Body'].read().decode())
```

10. Guardar salida/captura como evidencia. Registrar la versión `telco-equipo1-v1`.

## E. Crear EC2

1. EC2 > Launch instance. Nombre `telco-ep3-equipo1`. Ubuntu Server 22.04 LTS x86_64. Tipo **t3.medium**. Región us-east-1.
2. En IAM instance profile/advanced details, seleccionar exactamente **LabInstanceProfile**.
3. Crear Security Group con inbound:
   - SSH TCP 22: **My IP** solamente.
   - HTTP TCP 80: `0.0.0.0/0` y `::/0` si se usa IPv6.
   - HTTPS TCP 443: `0.0.0.0/0` y `::/0` si se usa IPv6.
   - No abrir 8000, 3000, 5432, 5672, 9090 ni 15672.
4. Lanzar la instancia. EC2 > Elastic IPs > Allocate Elastic IP > Associate con la instancia.
5. Copiar la IP elástica. Convertir puntos en guiones. Ejemplo IP `3.85.10.20` => `3-85-10-20.sslip.io`. Ese será el host HTTPS.
6. Conectarse por SSH desde Windows. Restringir SSH a la IP del equipo.

## F. Instalar Docker en EC2

En la terminal SSH de Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

7. Verificar que el rol EC2 está asociado (sin claves):

```bash
aws sts get-caller-identity
```

Si `aws` no está instalado, instalar AWS CLI v2 desde la documentación oficial. No ejecutar `aws configure` con claves personales. El perfil de instancia debe proveer credenciales temporales.

## G. Desplegar servicios en EC2

1. Clonar el repositorio GitHub en `/opt/telco-ep3`:

```bash
sudo mkdir -p /opt/telco-ep3 && sudo chown $USER:$USER /opt/telco-ep3
cd /opt/telco-ep3
git clone URL_DEL_REPOSITORIO .
```

2. Crear `.env` en EC2, nunca subirlo a GitHub:

```bash
cp .env.example .env
nano .env
```

3. Completar los valores:
   - `API_KEY`: generar con `openssl rand -hex 32`.
   - `CUSTOMER_AUTH_TOKEN`: token de demostración distinto.
   - `POSTGRES_PASSWORD`, `RABBITMQ_PASSWORD`, `GRAFANA_PASSWORD`: valores largos y diferentes; reflejarlos también en `DATABASE_URL` y `RABBITMQ_URL`.
   - `IMAGE_NAME=ghcr.io/USUARIO/REPOSITORIO:ep3`.
   - `SAGEMAKER_ENDPOINT_NAME=telco-equipo1-intent-ep3`.
   - `AWS_REGION=us-east-1`.
   - `NVIDIA_API_KEY`: clave de NVIDIA Build creada por el equipo.
   - `NVIDIA_MODEL`: nombre exacto que publicó el docente en el foro; no reemplazar por un modelo supuesto.
   - `SITE_ADDRESS=IP-CON-GUIONES.sslip.io`.
   - `ALLOW_LOCAL_MODEL=false`.
4. Asociar el perfil de instancia `LabInstanceProfile` a EC2 y comprobar `aws sts get-caller-identity`. No agregar AWS_ACCESS_KEY_ID ni AWS_SECRET_ACCESS_KEY al `.env`.
5. Si GHCR es público, `docker pull` no requiere autenticación. Si es privado, ejecutar `docker login ghcr.io` con un PAT de solo lectura, sin dejarlo en comandos compartidos ni en el repo.
6. Levantar:

```bash
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail=100 api worker caddy
```

7. Caddy solicitará automáticamente certificado Let's Encrypt para `sslip.io`. Esperar unos minutos y verificar:

```bash
curl -I https://IP-CON-GUIONES.sslip.io
curl https://IP-CON-GUIONES.sslip.io/api/health
```

8. Si HTTPS no funciona, revisar: IP elástica asociada, Security Group 80/443, DNS sslip.io, `SITE_ADDRESS`, logs `docker compose logs caddy`. No exponer puertos internos.

## H. Configurar API y comprobar demo

Desde PowerShell del equipo:

```powershell
$base = 'https://IP-CON-GUIONES.sslip.io'
$headers = @{ 'X-API-Key' = 'API_KEY_CONFIGURADA' }
$body = @{ message = 'No tengo internet en mi casa' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/api/predict" -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod -Method Post -Uri "$base/api/conversacion" -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod -Method Get -Uri "$base/api/health"
```

9. Consultar el `prediction_id` en `GET /api/predicciones/{id}` con la clave hasta que `llm_status` sea `completed` o `degraded`.
10. Probar sin clave: debe devolver 401. Probar JSON sin `message`: 422. Probar muchas peticiones: 429.
11. Abrir `https://IP-CON-GUIONES.sslip.io/` para el chat; `/dashboard` para el tablero; `/docs` para Swagger.
12. Para consulta de saldo, el prototipo solicita autenticación y acepta el encabezado `X-Customer-Token` solo si coincide con `CUSTOMER_AUTH_TOKEN`. No usarlo como autenticación productiva real.

## I. Métricas de SageMaker y prueba de carga

1. Medir cold start y segunda llamada tras 10 minutos sin uso:

```bash
python scripts/measure_endpoint.py --endpoint telco-equipo1-intent-ep3 --region us-east-1 --idle-seconds 600
```

2. Obtener las métricas de CloudWatch:

```bash
python scripts/cloudwatch_metrics.py --endpoint telco-equipo1-intent-ep3 --region us-east-1
```

3. En consola CloudWatch > Metrics > AWS/SageMaker, seleccionar `Invocations` y `ModelLatency` para el endpoint y guardar capturas. Registrar hora, región, nombre del endpoint y rango.
4. Locust (3 minutos, solo `/api/predict`, no LLM): desde el equipo local o una estación con red:

```powershell
$env:API_KEY='REEMPLAZAR_CON_TU_CLAVE'
locust -f locustfile.py --headless -u 10 -r 2 -t 3m --host https://IP-CON-GUIONES.sslip.io --csv=locust_ep3
```

5. Registrar p50, p95, p99, requests/s y porcentaje de fallos. El requisito del caso es p95 inferior a 3 s para la respuesta LLM. Medir por separado `/api/conversacion` con pocas llamadas, sin usar Locust masivo contra NVIDIA.
6. Guardar evidencias de estado de EC2, IP elástica, perfil de instancia, endpoint InService, S3 privado, HTTPS, API, dashboard, logs, CloudWatch y Locust.

## J. Costos, parada y limpieza

1. Completar costo mensual en AWS Pricing Calculator con región us-east-1 y horas reales de EC2. Para SageMaker Serverless considerar memoria, duración y solicitudes; S3 por GB/requests; NVIDIA con precio de proveedor pagado para el modelo que publicó el docente. No inventar precios: guardar fecha y captura de la calculadora.
2. EC2 t3.medium factura mientras está encendida; Learner Lab puede suspenderla al terminar la sesión. SageMaker Serverless factura por uso, pero no es costo cero.
3. Si se usa endpoint realtime, borrarlo después de cada sesión: `python scripts/delete_endpoint.py --endpoint telco-equipo1-intent-ep3 --region us-east-1`.
4. Para apagar la app: `docker compose down` (no usar `-v` salvo que quieran borrar datos). Para terminar EC2, liberar Elastic IP solo cuando el equipo haya terminado y ya no necesite URL.
5. Antes de presentación, iniciar Learner Lab al menos 30 minutos antes, comprobar EC2 y endpoint, probar URLs desde una red externa y tener las capturas disponibles.
