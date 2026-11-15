import json, os
import boto3
import joblib
from app.config import AWS_REGION, SAGEMAKER_ENDPOINT_NAME, MODEL_VERSION, ALLOW_LOCAL_MODEL, LOCAL_MODEL_PATH

_client = None
_local = None

def predict_intent(message: str):
    if SAGEMAKER_ENDPOINT_NAME:
        global _client
        if _client is None:
            _client = boto3.client('sagemaker-runtime', region_name=AWS_REGION)
        response = _client.invoke_endpoint(EndpointName=SAGEMAKER_ENDPOINT_NAME, ContentType='application/json',
            Accept='application/json', Body=json.dumps({'text': message}, ensure_ascii=False))
        result = json.loads(response['Body'].read().decode())
        result['model_version'] = result.get('model_version', MODEL_VERSION)
        return result
    if ALLOW_LOCAL_MODEL:
        global _local
        if _local is None:
            _local = joblib.load(LOCAL_MODEL_PATH)
        probs = _local.predict_proba([message])[0]
        idx = int(probs.argmax())
        return {'intent':str(_local.classes_[idx]), 'confidence':float(probs[idx]), 'model_version':MODEL_VERSION}
    raise RuntimeError('SageMaker endpoint no configurado; no se permite fallback local en este entorno.')
