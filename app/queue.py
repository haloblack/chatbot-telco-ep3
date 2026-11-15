import json, os
from app.config import RABBITMQ_URL
QUEUE = 'telco.llm.responses'

def publish(payload: dict) -> bool:
    try:
        import pika
        params = pika.URLParameters(RABBITMQ_URL)
        params.socket_timeout = 3
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE, durable=True)
        channel.basic_publish(exchange='', routing_key=QUEUE,
            body=json.dumps(payload, ensure_ascii=False).encode(),
            properties=pika.BasicProperties(delivery_mode=2, content_type='application/json'))
        connection.close()
        return True
    except Exception:
        return False
