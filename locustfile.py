import os
from locust import HttpUser, task, between

class TelcoPredictUser(HttpUser):
    wait_time=between(3, 4)
    @task
    def predict(self):
        self.client.post('/api/predict',json={'message':'No tengo internet en mi casa'},
                         headers={'X-API-Key':os.getenv('API_KEY','')},name='/api/predict')
