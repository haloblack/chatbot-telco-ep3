import json, os, joblib

def model_fn(model_dir):
    return joblib.load(os.path.join(model_dir,'model.joblib'))

def input_fn(request_body, request_content_type):
    if request_content_type != 'application/json': raise ValueError('Content-Type debe ser application/json')
    data=json.loads(request_body)
    text=data.get('text')
    if not isinstance(text,str) or not text.strip(): raise ValueError("Se requiere campo 'text' no vacío")
    return text

def predict_fn(text, model):
    probabilities=model.predict_proba([text])[0]
    index=int(probabilities.argmax())
    return {'intent':str(model.classes_[index]),'confidence':float(probabilities[index]),
            'probabilities':{str(c):float(p) for c,p in zip(model.classes_,probabilities)}}

def output_fn(prediction, accept):
    return json.dumps({**prediction,'model_version':os.getenv('MODEL_VERSION','telco-intent-v1')},ensure_ascii=False), 'application/json'
