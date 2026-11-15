"""Mide invocación inicial y segunda invocación tras inactividad de 10 minutos."""
import argparse,time,json,boto3
p=argparse.ArgumentParser();p.add_argument('--endpoint',required=True);p.add_argument('--region',default='us-east-1');p.add_argument('--idle-seconds',type=int,default=600);a=p.parse_args()
r=boto3.client('sagemaker-runtime',region_name=a.region)
def invoke(label):
    start=time.perf_counter(); response=r.invoke_endpoint(EndpointName=a.endpoint,ContentType='application/json',Accept='application/json',Body=json.dumps({'text':'No tengo internet en mi casa'})); body=response['Body'].read().decode(); elapsed=(time.perf_counter()-start)*1000
    print(json.dumps({'label':label,'latency_ms':round(elapsed,2),'prediction':json.loads(body)},ensure_ascii=False))
invoke('invocacion_1');print(f'Esperando {a.idle_seconds} segundos sin invocar...');time.sleep(a.idle_seconds);invoke('invocacion_2_despues_de_inactividad')
