import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('API_KEY', 'local-test-key')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
SAGEMAKER_ENDPOINT_NAME = os.getenv('SAGEMAKER_ENDPOINT_NAME', '')
MODEL_VERSION = os.getenv('MODEL_VERSION', 'telco-intent-v1')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.45'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:////tmp/telco_ep3_test.db')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/%2F')
FAQ_PATH = os.getenv('FAQ_PATH', 'data/processed/faq.json')
LOCAL_MODEL_PATH = os.getenv('LOCAL_MODEL_PATH', 'data/processed/intent_model.joblib')
ALLOW_LOCAL_MODEL = os.getenv('ALLOW_LOCAL_MODEL', 'false').lower() == 'true'
RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '60'))
