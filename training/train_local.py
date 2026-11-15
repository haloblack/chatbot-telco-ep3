from pathlib import Path
import json, joblib
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'/'processed'

def build_model():
    train=pd.read_csv(D/'train.csv'); test=pd.read_csv(D/'test.csv')
    model=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),strip_accents='unicode',min_df=2,sublinear_tf=True)),
                    ('clf',LogisticRegression(max_iter=1500,class_weight='balanced',C=3.0))])
    model.fit(train.text,train.label)
    pred=model.predict(test.text)
    p,r,f,_=precision_recall_fscore_support(test.label,pred,average='macro',zero_division=0)
    metrics={'accuracy':accuracy_score(test.label,pred),'precision_macro':p,'recall_macro':r,'f1_macro':f,
             'labels':list(model.classes_),'confusion_matrix':confusion_matrix(test.label,pred,labels=model.classes_).tolist(),
             'classification_report':classification_report(test.label,pred,zero_division=0,output_dict=True),
             'test_size':len(test),'train_size':len(train)}
    joblib.dump(model,D/'intent_model.joblib')
    (D/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in metrics.items() if k not in ('confusion_matrix','classification_report')},ensure_ascii=False,indent=2))
    return metrics
if __name__=='__main__': build_model()
