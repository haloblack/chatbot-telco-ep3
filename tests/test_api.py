import os, sys
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DATABASE_URL','sqlite:////tmp/telco_ep3_pytest.db')
os.environ.setdefault('API_KEY','test-secret')
os.environ.setdefault('FAQ_PATH',os.path.join(os.path.dirname(os.path.dirname(__file__)),'data','processed','faq.json'))
from fastapi.testclient import TestClient
from app import main

client=TestClient(main.app)
HEAD={'X-API-Key':'test-secret'}

def fake_prediction(message):
    return {'intent':'falla_conexion','confidence':0.91,'model_version':'test-model-v1'}

def setup_function():
    main._rate.clear()
    main.predict_intent=fake_prediction
    main.publish=lambda payload: True

# 1 valid request returns model output and version
def test_valid_prediction_200():
    r=client.post('/api/predict',headers=HEAD,json={'message':'No tengo internet'}); assert r.status_code==200
    assert r.json()['intent']=='falla_conexion' and r.json()['model_version']=='test-model-v1'
# 2 missing required field -> 422
def test_missing_field_422():
    assert client.post('/api/predict',headers=HEAD,json={}).status_code==422
# 3 unauthenticated -> 401
def test_missing_api_key_401():
    assert client.post('/api/predict',json={'message':'Hola'}).status_code==401
# 4 rate limiter -> 429
def test_rate_limit_429(monkeypatch):
    monkeypatch.setattr(main,'RATE_LIMIT_PER_MINUTE',1)
    client.post('/api/predict',headers=HEAD,json={'message':'No tengo internet'})
    assert client.post('/api/predict',headers=HEAD,json={'message':'Tengo problemas de red'}).status_code==429
# 5 PII removal: RUT, email, phone and card
def test_anonymization_removes_pii():
    from app.privacy import anonymize
    source='Mi nombre es Ana Pérez, RUT 12.345.678-5 correo ana@example.cl teléfono +56987654321 tarjeta 4111 1111 1111 1111, mi dirección es Av Siempre Viva 123'
    result=anonymize(source)
    assert '12.345.678-5' not in result and 'ana@example.cl' not in result
    assert '987654321' not in result and '4111 1111 1111 1111' not in result
    assert 'Ana Pérez' not in result and 'Av Siempre Viva 123' not in result
# 6 queue failure -> degraded but prediction succeeds
def test_llm_queue_failure_degraded(monkeypatch):
    monkeypatch.setattr(main,'publish',lambda payload:False)
    r=client.post('/api/conversacion',headers=HEAD,json={'message':'No tengo internet','channel':'web'})
    assert r.status_code==200 and r.json()['llm_status']=='degraded'
# 7 explicit human request
def test_explicit_human_handoff():
    r=client.post('/api/predict',headers=HEAD,json={'message':'Quiero hablar con una persona'})
    assert r.status_code==200 and r.json()['handoff'] is True
# 8 cancellation intent always handoff
def test_cancel_intent_handoff(monkeypatch):
    monkeypatch.setattr(main,'predict_intent',lambda m:{'intent':'anulacion','confidence':.98,'model_version':'v1'})
    r=client.post('/api/predict',headers=HEAD,json={'message':'Quiero cancelar mi servicio'})
    assert r.json()['handoff'] is True and r.json()['handoff_reason']=='intencion_anulacion'
# 9 three failed attempts
def test_three_failed_attempts_handoff(monkeypatch):
    monkeypatch.setattr(main,'predict_intent',lambda m:{'intent':'consulta_general','confidence':.10,'model_version':'v1'})
    results=[client.post('/api/predict',headers=HEAD,json={'message':'no entiendo','conversation_id':'three-failures'}) for _ in range(3)]
    assert results[-1].json()['handoff'] is True and results[-1].json()['handoff_reason']=='tres_intentos_fallidos'
# 10 saved prediction can be retrieved
def test_prediction_saved_and_retrieved():
    r=client.post('/api/predict',headers=HEAD,json={'message':'No tengo internet'})
    pid=r.json()['prediction_id']; got=client.get('/api/predicciones/'+pid,headers=HEAD)
    assert got.status_code==200 and got.json()['model_version']=='test-model-v1'
# 11 public health endpoint
def test_health_public():
    assert client.get('/api/health').status_code==200
# 12 conversation endpoint
def test_conversation_route():
    r=client.post('/api/conversacion',headers=HEAD,json={'message':'No tengo internet','channel':'web'})
    assert r.status_code==200 and 'llm_poll_url' in r.json()

# 13 LLM worker failure leaves the model prediction intact and records degraded mode
def test_worker_llm_failure_degraded(monkeypatch):
    from worker import main as worker
    states=[]
    monkeypatch.setattr(worker,'generate_response',lambda payload: (_ for _ in ()).throw(RuntimeError('simulated NVIDIA 429/outage')))
    monkeypatch.setattr(worker,'update_llm',lambda pid,status,response: states.append((pid,status,response)))
    worker.handle_payload({'prediction_id':'test-worker-failure','message':'consulta anonimizada','intent':'consulta_general','faq':[]})
    assert states==[('test-worker-failure','degraded',None)]

# 14 Predict endpoint is synchronous-only and does not enqueue the LLM (Locust target)
def test_predict_does_not_enqueue_llm(monkeypatch):
    called=[]
    monkeypatch.setattr(main,'publish',lambda payload: called.append(payload) or True)
    r=client.post('/api/predict',headers=HEAD,json={'message':'No tengo internet'})
    assert r.status_code==200 and r.json()['llm_status']=='not_requested' and called==[]
