"""Script de entrenamiento ejecutado por SageMaker Script Mode."""
import argparse, os, json
import pandas as pd, joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--max-iter',type=int,default=1500); p.add_argument('--C',type=float,default=3.0)
    args,_=p.parse_known_args()
    train_path=os.path.join('/opt/ml/input/data/train','train.csv')
    test_path=os.path.join('/opt/ml/input/data/test','test.csv')
    train=pd.read_csv(train_path); test=pd.read_csv(test_path)
    model=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),strip_accents='unicode',min_df=2,sublinear_tf=True)),
                    ('clf',LogisticRegression(max_iter=args.max_iter,class_weight='balanced',C=args.C))])
    model.fit(train.text,train.label); pred=model.predict(test.text)
    precision,recall,f1,_=precision_recall_fscore_support(test.label,pred,average='macro',zero_division=0)
    metrics={'accuracy':accuracy_score(test.label,pred),'precision_macro':precision,'recall_macro':recall,'f1_macro':f1,
             'report':classification_report(test.label,pred,zero_division=0,output_dict=True)}
    os.makedirs('/opt/ml/model',exist_ok=True); joblib.dump(model,'/opt/ml/model/model.joblib')
    with open('/opt/ml/model/metrics.json','w') as f: json.dump(metrics,f)
