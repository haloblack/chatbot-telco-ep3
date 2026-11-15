import os, json, time, logging
from app.config import RABBITMQ_URL
from app.db import update_llm

logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
log=logging.getLogger('telco-worker')
QUEUE='telco.llm.responses'
_last_nvidia_call=0.0

def generate_response(payload, client=None):
    api_key=os.getenv('NVIDIA_API_KEY',''); model=os.getenv('NVIDIA_MODEL','')
    if not api_key or not model or model.startswith('REPLACE_'):
        raise RuntimeError('NVIDIA_API_KEY o NVIDIA_MODEL no configurados')
    from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
    client=client or OpenAI(base_url=os.getenv('NVIDIA_BASE_URL','https://integrate.api.nvidia.com/v1'),api_key=api_key,
                           timeout=float(os.getenv('NVIDIA_TIMEOUT_SECONDS','12')))
    articles='\n'.join(f"- {x.get('question','')}: {x.get('answer','')}" for x in payload.get('faq',[]))
    system=('Eres el asistente de Andesnet Telecomunicaciones. Responde en español chileno claro y breve. '
            'Usa solo los artículos FAQ proporcionados. Si no hay información suficiente, dilo y recomienda un ejecutivo. '
            'No inventes saldos, fechas, estados de cuenta ni promesas comerciales.')
    user=f"Intención: {payload.get('intent')}\nMensaje anonimizado: {payload.get('message')}\nArtículos FAQ:\n{articles}"
    max_retries=int(os.getenv('NVIDIA_MAX_RETRIES','3'))
    global _last_nvidia_call
    for attempt in range(max_retries+1):
        try:
            interval=float(os.getenv('NVIDIA_MIN_INTERVAL_SECONDS','1.6'))
            wait=max(0.0,interval-(time.monotonic()-_last_nvidia_call))
            if wait: time.sleep(wait)
            _last_nvidia_call=time.monotonic()
            result=client.chat.completions.create(model=model,messages=[{'role':'system','content':system},{'role':'user','content':user}],temperature=0.2,max_tokens=220)
            return result.choices[0].message.content.strip()
        except RateLimitError:
            if attempt>=max_retries: raise
            time.sleep(min(2**attempt,8))
        except (APIConnectionError,APITimeoutError):
            if attempt>=max_retries: raise
            time.sleep(min(2**attempt,8))
    raise RuntimeError('LLM no disponible')

def handle_payload(payload):
    pid=payload['prediction_id']
    try:
        response=generate_response(payload)
        update_llm(pid,'completed',response)
    except Exception as exc:
        log.exception('LLM degradado para %s: %s',pid,type(exc).__name__)
        update_llm(pid,'degraded',None)

def main():
    import pika
    while True:
        try:
            connection=pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL)); channel=connection.channel()
            channel.queue_declare(queue=QUEUE,durable=True); channel.basic_qos(prefetch_count=1)
            def callback(ch,method,properties,body):
                try: handle_payload(json.loads(body.decode())); ch.basic_ack(method.delivery_tag)
                except Exception: log.exception('Error procesando mensaje'); ch.basic_nack(method.delivery_tag,requeue=False)
            channel.basic_consume(queue=QUEUE,on_message_callback=callback); log.info('Worker LLM escuchando %s',QUEUE); channel.start_consuming()
        except Exception: log.exception('RabbitMQ no disponible; reintento en 5s'); time.sleep(5)

if __name__=='__main__': main()
