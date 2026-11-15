import json, time, uuid, re
from collections import defaultdict, deque
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.config import API_KEY, CONFIDENCE_THRESHOLD, MODEL_VERSION, FAQ_PATH, RATE_LIMIT_PER_MINUTE
from app.inference import predict_intent
from app.privacy import anonymize
from app.queue import publish
from app import db

app=FastAPI(title='Andesnet Telco - EP3 Equipo 1',version='1.0.0',description='Clasificación de intención con SageMaker y respuesta LLM asíncrona por RabbitMQ/NVIDIA.')
REQUESTS=Counter('telco_requests_total','Solicitudes procesadas',['route','status'])
LATENCY=Histogram('telco_request_seconds','Latencia de solicitudes',['route'])
_rate=defaultdict(deque)

class PredictRequest(BaseModel):
    message: str = Field(min_length=2,max_length=2000)
    conversation_id: str|None = None

class ConversationRequest(PredictRequest):
    channel: str = Field(default='web',pattern='^(web|whatsapp|app)$')

class FeedbackRequest(BaseModel):
    prediction_id: str
    rating: int = Field(ge=1,le=5)
    comment: str|None = Field(default=None,max_length=500)

def require_key(x_api_key: str|None=Header(default=None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401,detail='API key inválida o ausente')

def rate_limit(request: Request):
    ip=request.client.host if request.client else 'unknown'; now=time.time(); q=_rate[ip]
    while q and now-q[0]>60: q.popleft()
    if len(q)>=RATE_LIMIT_PER_MINUTE: raise HTTPException(status_code=429,detail='Límite de solicitudes excedido')
    q.append(now)

def load_faq(intent: str, limit=4):
    p=Path(FAQ_PATH)
    if not p.exists(): return []
    try: data=json.loads(p.read_text(encoding='utf-8'))
    except Exception: return []
    selected=[x for x in data if x.get('intent')==intent]
    if not selected: selected=[x for x in data if x.get('intent')=='consulta_general']
    return [{'id':x.get('articulo_id'),'question':x.get('pregunta'),'answer':x.get('respuesta')} for x in selected[:limit]]

HANDOFF_PHRASES=['quiero hablar con una persona','hablar con un ejecutivo','necesito un humano','hablar con alguien','quiero un ejecutivo']
ANGER_WORDS=['estafa','ladrones','pésimo','pesimo','harto','indignado','furioso','enojado','molesto','reclamo urgente','voy a denunciar']
def handoff_rule(message,intent,failed_attempts):
    low=message.lower()
    if any(x in low for x in HANDOFF_PHRASES): return True,'solicitud_explicita_humano'
    if intent=='anulacion': return True,'intencion_anulacion'
    if any(x in low for x in ANGER_WORDS): return True,'molestia_detectada'
    if failed_attempts>=3: return True,'tres_intentos_fallidos'
    return False,None

def _predict(body: PredictRequest, channel='api', customer_token: str|None=None, enqueue_llm: bool=False):
    start=time.perf_counter()
    try: result=predict_intent(body.message)
    except Exception as e:
        REQUESTS.labels(channel,'503').inc()
        raise HTTPException(status_code=503,detail=f'No fue posible consultar SageMaker: {type(e).__name__}')
    intent=result.get('intent','desconocida'); confidence=float(result.get('confidence',0)); version=result.get('model_version',MODEL_VERSION)
    if confidence<CONFIDENCE_THRESHOLD: intent='desconocida'
    conversation_id=body.conversation_id or str(uuid.uuid4())
    sanitized=anonymize(body.message)
    attempts=db.record_attempt(conversation_id,intent=='desconocida')
    handoff,reason=handoff_rule(body.message,intent,attempts)
    # Account data is not returned without customer authentication.
    import os
    configured_customer_token=os.getenv('CUSTOMER_AUTH_TOKEN','')
    customer_authenticated=bool(configured_customer_token and customer_token and customer_token==configured_customer_token)
    needs_auth=intent=='consulta_saldo'
    if needs_auth and not customer_authenticated:
        response_text='Para consultar información de tu cuenta, primero debes autenticarte.'
    elif handoff:
        response_text='Voy a derivarte con un ejecutivo. No necesitas repetir lo que ya nos contaste.'
    elif intent=='desconocida':
        response_text='No estoy seguro de haber entendido. ¿Puedes reformular tu consulta?'
    else: response_text='Estoy preparando una respuesta con la base de conocimiento.'
    pid=str(uuid.uuid4()); articles=load_faq(intent)
    db.append_message(conversation_id,sanitized,intent)
    row={'id':pid,'conversation_id':conversation_id,'message':sanitized,'intent':intent,'confidence':confidence,
         'model_version':version,'handoff':int(handoff),'handoff_reason':reason,'llm_status':'pending' if enqueue_llm and not handoff and not needs_auth and intent!='desconocida' else 'not_requested','llm_response':None}
    db.save_prediction(row)
    queued=False
    if enqueue_llm and not handoff and not needs_auth and intent!='desconocida':
        queued=publish({'prediction_id':pid,'message':sanitized,'intent':intent,'faq':articles})
        if not queued:
            db.update_llm(pid,'degraded',None); row['llm_status']='degraded'
    elapsed=time.perf_counter()-start
    LATENCY.labels(channel).observe(elapsed); REQUESTS.labels(channel,'200').inc()
    return {'prediction_id':pid,'conversation_id':conversation_id,'failed_attempts':attempts,'intent':intent,'probability':round(confidence,6),'model_version':version,
            'handoff':handoff,'handoff_reason':reason,'authentication_required':needs_auth and not customer_authenticated,
            'llm_status':row['llm_status'],'message':response_text,'llm_poll_url':f'/api/predicciones/{pid}'}

@app.middleware('http')
async def timing_middleware(request,call_next):
    response=await call_next(request)
    return response

@app.get('/api/health')
def health():
    from app.config import SAGEMAKER_ENDPOINT_NAME, AWS_REGION
    checks={'database':'unknown','sagemaker':'not_configured','rabbitmq':'unknown',
            'llm':'configured' if __import__('os').getenv('NVIDIA_API_KEY') and not __import__('os').getenv('NVIDIA_MODEL','').startswith('REPLACE_') else 'not_configured'}
    if SAGEMAKER_ENDPOINT_NAME:
        try:
            import boto3
            status=boto3.client('sagemaker',region_name=AWS_REGION).describe_endpoint(EndpointName=SAGEMAKER_ENDPOINT_NAME)['EndpointStatus']
            checks['sagemaker']=status
        except Exception: checks['sagemaker']='error'
    try: db.engine().connect().close(); checks['database']='ok'
    except Exception: checks['database']='error'
    try:
        import pika
        from app.config import RABBITMQ_URL
        c=pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL)); c.close(); checks['rabbitmq']='ok'
    except Exception: checks['rabbitmq']='error'
    return {'status':'ok' if checks['database']=='ok' else 'degraded','components':checks}

@app.post('/api/predict',dependencies=[Depends(require_key),Depends(rate_limit)])
def predict(body: PredictRequest, x_customer_token: str|None=Header(default=None)): return _predict(body,customer_token=x_customer_token)

@app.post('/api/conversacion',dependencies=[Depends(require_key),Depends(rate_limit)])
def conversacion(body: ConversationRequest, x_customer_token: str|None=Header(default=None)): return _predict(body,'conversacion',x_customer_token,True)

@app.get('/api/predicciones/{prediction_id}',dependencies=[Depends(require_key)])
def get_prediction(prediction_id:str):
    row=db.get_prediction(prediction_id)
    if not row: raise HTTPException(status_code=404,detail='Predicción no encontrada')
    return row

@app.get('/api/dashboard',dependencies=[Depends(require_key)])
def dashboard(): return db.dashboard_data()

@app.get('/api/derivaciones/{conversation_id}',dependencies=[Depends(require_key)])
def handoff_history(conversation_id:str):
    history=db.get_history(conversation_id)
    if not history: raise HTTPException(status_code=404,detail='Conversación no encontrada')
    return {'conversation_id':conversation_id,'history':history}

@app.post('/api/feedback',dependencies=[Depends(require_key)])
def feedback(body:FeedbackRequest):
    row=db.get_prediction(body.prediction_id)
    if not row: raise HTTPException(status_code=404,detail='Predicción no encontrada')
    return {'status':'received','prediction_id':body.prediction_id,'rating':body.rating}

@app.get('/',response_class=HTMLResponse)
def frontend():
    return HTMLResponse("""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Andesnet Chatbot</title><style>body{font:16px system-ui;background:#eef2f7;color:#152238;margin:0}.box{max-width:760px;margin:40px auto;background:white;padding:26px;border-radius:16px;box-shadow:0 4px 24px #0001}input,textarea,button{font:inherit;padding:12px;border:1px solid #ccd4df;border-radius:8px}textarea{width:96%;min-height:90px}button{background:#123d69;color:white;cursor:pointer;margin:8px 0}.msg{padding:14px;background:#f3f6fa;border-radius:9px;margin-top:12px;white-space:pre-wrap}.small{color:#526174;font-size:13px}</style><div class="box"><h1>Andesnet · Atención digital</h1><p>Asistente de consultas de telecomunicaciones</p><label>Clave API de demostración<br><input id="key" type="password" placeholder="X-API-Key" style="width:95%"></label><p><textarea id="message" placeholder="Ej.: No tengo internet en casa"></textarea></p><button onclick="send()">Enviar consulta</button><div id="result"></div><p class="small">La clasificación se realiza con el modelo propio desplegado en Amazon SageMaker. La respuesta generativa llega de forma asíncrona.</p></div><script>let conversationId=null;async function send(){let out=document.getElementById('result');out.textContent='Procesando…';let r=await fetch('/api/conversacion',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':document.getElementById('key').value},body:JSON.stringify({message:document.getElementById('message').value,channel:'web',conversation_id:conversationId})});let d=await r.json();if(!r.ok){out.textContent=JSON.stringify(d);return}conversationId=d.conversation_id;out.innerHTML='<div class="msg"><b>Intención:</b> '+d.intent+'<br><b>Probabilidad:</b> '+(d.probability*100).toFixed(1)+'%<br><b>Derivación:</b> '+d.handoff+'<br><b>Estado LLM:</b> '+d.llm_status+'<br>'+d.message+'</div>';if(d.prediction_id){let n=0;let timer=setInterval(async()=>{n++;let q=await fetch(d.llm_poll_url,{headers:{'X-API-Key':document.getElementById('key').value}});let v=await q.json();if(v.llm_response||v.llm_status==='degraded'||n>=15){clearInterval(timer);let el=out.querySelector('.msg');el.innerHTML+=' <br><b>Respuesta:</b> '+(v.llm_response||'Respuesta generativa no disponible; se conserva la predicción del modelo.')}} ,1000)}} </script></html>""")

@app.get('/dashboard',response_class=HTMLResponse)
def dashboard_page():
    return HTMLResponse('''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Andesnet · Dashboard</title><style>body{font:16px system-ui;background:#f3f5f9;margin:0;color:#182230}.wrap{max-width:1000px;margin:35px auto;padding:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}.card{background:white;padding:22px;border-radius:12px;box-shadow:0 2px 10px #0001}.n{font-size:32px;font-weight:700}input{padding:10px;width:260px}button{padding:10px 15px}li{padding:5px}</style><div class="wrap"><h1>Andesnet · Chatbot Telco</h1><p>Dashboard operativo · Equipo 1</p><p><input id="key" placeholder="X-API-Key"><button onclick="load()">Actualizar</button></p><div class="grid" id="cards"></div><div class="card"><h2>Intenciones detectadas</h2><ul id="intents"></ul></div></div><script>async function load(){let k=document.getElementById('key').value;let r=await fetch('/api/dashboard',{headers:{'X-API-Key':k}});if(!r.ok){alert('No se pudo cargar: '+r.status);return}let d=await r.json();document.getElementById('cards').innerHTML=[['Conversaciones',d.conversaciones],['Derivaciones',d.derivaciones],['Tasa derivación',(d.tasa_derivacion*100).toFixed(1)+'%'],['Modo degradado',d.modo_degradado],['Tasa degradado',(d.tasa_degradado*100).toFixed(1)+'%']].map(x=>`<div class="card"><div>${x[0]}</div><div class="n">${x[1]}</div></div>`).join('');document.getElementById('intents').innerHTML=d.intenciones.map(x=>`<li>${x.intent}: ${x.n}</li>`).join('')} </script></html>''')

@app.get('/metrics')
def metrics(): return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
