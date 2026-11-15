import argparse,boto3
p=argparse.ArgumentParser();p.add_argument('--endpoint',required=True);p.add_argument('--region',default='us-east-1');a=p.parse_args()
s=boto3.client('sagemaker',region_name=a.region)
try:
    d=s.describe_endpoint(EndpointName=a.endpoint)
    s.delete_endpoint(EndpointName=a.endpoint)
    print('Solicitud de eliminación enviada:',a.endpoint)
except s.exceptions.ClientError as e:
    if 'Could not find' in str(e): print('Endpoint ya no existe')
    else: raise
