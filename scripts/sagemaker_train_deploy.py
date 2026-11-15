"""Entrena en SageMaker y despliega endpoint Serverless usando LabRole.
Ejecutar desde SageMaker Studio/Notebook o entorno con rol autorizado en Learner Lab.
"""
import os, argparse, boto3, sagemaker
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.sklearn.model import SKLearnModel
from sagemaker.serverless import ServerlessInferenceConfig
from sagemaker.session import Session

p=argparse.ArgumentParser()
p.add_argument('--bucket',required=True); p.add_argument('--prefix',default='telco-ep3')
p.add_argument('--endpoint',default='telco-equipo1-intent-ep3')
p.add_argument('--role',default='LabRole'); p.add_argument('--region',default='us-east-1')
p.add_argument('--memory-mb',type=int,default=2048); p.add_argument('--max-concurrency',type=int,default=5)
p.add_argument('--mode',choices=['serverless','realtime'],default='serverless')
a=p.parse_args()
boto_session = boto3.Session(region_name=a.region)
sm_session = Session(boto_session=boto_session)
role = a.role  # Learner Lab provides this role; do not create IAM users/keys.
train_uri=f's3://{a.bucket}/{a.prefix}/train/'
test_uri=f's3://{a.bucket}/{a.prefix}/test/'
data_dir=os.path.join(os.path.dirname(__file__),'..','data','processed')
boto_session.client('s3').upload_file(os.path.join(data_dir,'train.csv'),a.bucket,f'{a.prefix}/train/train.csv')
boto_session.client('s3').upload_file(os.path.join(data_dir,'test.csv'),a.bucket,f'{a.prefix}/test/test.csv')
boto_session.client('s3').upload_file(os.path.join(data_dir,'faq.json'),a.bucket,f'{a.prefix}/knowledge/faq.json')
estimator=SKLearn(entry_point='train.py',source_dir=os.path.join(os.path.dirname(__file__),'..','sagemaker'),
    role=role,instance_type='ml.m5.large',instance_count=1,framework_version='1.2-1',py_version='py3',
    sagemaker_session=sm_session, hyperparameters={'max-iter':1500,'C':3.0})
estimator.fit({'train':train_uri,'test':test_uri})
model=SKLearnModel(model_data=estimator.model_data,role=role,entry_point='inference.py',
    source_dir=os.path.join(os.path.dirname(__file__),'..','sagemaker'),framework_version='1.2-1',py_version='py3',
    sagemaker_session=sm_session,env={'MODEL_VERSION':'telco-equipo1-v1'})
if a.mode=='serverless':
    config=ServerlessInferenceConfig(memory_size_in_mb=a.memory_mb,max_concurrency=a.max_concurrency)
    predictor=model.deploy(serverless_inference_config=config,endpoint_name=a.endpoint,wait=True)
else:
    predictor=model.deploy(initial_instance_count=1,instance_type='ml.m5.large',endpoint_name=a.endpoint,wait=True)
print(f'Endpoint listo: {a.endpoint}')
print(predictor.predict({'text':'No tengo internet en mi casa'}))
