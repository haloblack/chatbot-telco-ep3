import argparse,datetime,boto3,json
p=argparse.ArgumentParser();p.add_argument('--endpoint',required=True);p.add_argument('--region',default='us-east-1');a=p.parse_args()
c=boto3.client('cloudwatch',region_name=a.region);end=datetime.datetime.now(datetime.timezone.utc);start=end-datetime.timedelta(hours=3)
for metric in ['Invocations','ModelLatency']:
    r=c.get_metric_statistics(Namespace='AWS/SageMaker',MetricName=metric,Dimensions=[{'Name':'EndpointName','Value':a.endpoint},{'Name':'VariantName','Value':'AllTraffic'}],StartTime=start,EndTime=end,Period=60,Statistics=['Sum','Average','Maximum'])
    print(metric,json.dumps(r.get('Datapoints',[]),default=str))
