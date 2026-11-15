"""Prepara datos del caso 2. Solo exporta texto anonimizado y etiquetas; nunca cliente_id."""
from pathlib import Path
import re, unicodedata, json
import pandas as pd
from sklearn.model_selection import train_test_split
from app.privacy import anonymize

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data'/'raw'; OUT = ROOT/'data'/'processed'

def norm(s):
    s = str(s or '').strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    s = re.sub(r'[^a-z0-9 ]',' ',s)
    return re.sub(r'\s+',' ',s).strip()

ALIASES = {
 'facturacion':'consulta_saldo','fact':'consulta_saldo','facturacion ':'consulta_saldo','cobros':'consulta_saldo',
 'falla tecnica':'falla_conexion','soporte tecnico':'falla_conexion','soporte':'falla_conexion','tecnico':'falla_conexion','router':'falla_conexion',
 'cambio plan':'cambio_plan','upgrade':'cambio_plan','visita':'estado_visita','agenda tecnico':'estado_visita',
 'anulacion':'anulacion','baja':'anulacion','cancelacion':'anulacion','portabilidad':'portabilidad','porta':'portabilidad',
 'cobertura':'falla_conexion','senal':'falla_conexion','equipos':'falla_conexion','equipo':'falla_conexion',
 'roaming':'consulta_general','tv':'consulta_general','television':'consulta_general','internacional':'consulta_general',
 'consulta general':'consulta_general','otros':'consulta_general','general':'consulta_general','consulta saldo':'consulta_saldo',
 'saldo':'consulta_saldo','sin internet':'falla_conexion','falla':'falla_conexion','estado visita':'estado_visita','visita tecnica':'estado_visita',
 'cambio de plan':'cambio_plan','desconocida':'', 'unknown':'','-':''
}

def canonical(v):
    k=norm(v)
    return ALIASES.get(k, ALIASES.get(k.replace(' ','_'), ''))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    tickets=pd.read_csv(RAW/'tickets.csv')
    for _,r in tickets.iterrows():
        label=canonical(r.get('categoria'))
        msg=str(r.get('texto_consulta') or '').strip()
        if label and len(msg)>=5 and msg.lower()!='nan': rows.append((anonymize(msg),label,'ticket'))
    conv=pd.read_csv(RAW/'conversaciones.csv')
    for _,r in conv.iterrows():
        label=canonical(r.get('intencion_detectada'))
        transcript=str(r.get('transcripcion') or '')
        # Extract only customer utterances; avoid learning bot templates.
        customer=re.findall(r'cliente\s*:\s*(.*?)(?=\s*\|\|\s*bot\s*:|\s*\|\|\s*cliente\s*:|$)',transcript,flags=re.I)
        msg=' '.join(x.strip() for x in customer if x.strip())
        if label and len(msg)>=5: rows.append((anonymize(msg),label,'conversation'))
    df=pd.DataFrame(rows,columns=['text','label','source']).drop_duplicates(subset=['text','label'])
    # Remove empty/noisy records after anonymization.
    df=df[df.text.str.len()>=5]
    train,test=train_test_split(df[['text','label']],test_size=.20,random_state=42,stratify=df.label)
    train.to_csv(OUT/'train.csv',index=False); test.to_csv(OUT/'test.csv',index=False)
    faq=pd.read_csv(RAW/'faq.csv')
    faq=faq[(faq['vigente']==1) & faq['respuesta'].notna() & faq['respuesta'].astype(str).str.strip().ne('')].copy()
    faq['intent']=faq['categoria'].map(canonical)
    faq=faq[faq.intent!='']
    faq_records=faq[['articulo_id','pregunta','respuesta','intent']].fillna('').to_dict('records')
    (OUT/'faq.json').write_text(json.dumps(faq_records,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'total_examples':len(df),'train':len(train),'test':len(test),'classes':df.label.value_counts().to_dict(),
             'faq_articles_current_mapped':len(faq_records),'note':'Datos de texto anonimizados; no exportar IDs personales.'}
    (OUT/'data_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
