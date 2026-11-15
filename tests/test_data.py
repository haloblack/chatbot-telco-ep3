from pathlib import Path
import json

def test_processed_dataset_exists_and_has_split():
    root=Path(__file__).resolve().parents[1]/'data'/'processed'
    assert (root/'train.csv').exists() and (root/'test.csv').exists()

def test_faq_only_current_articles():
    path=Path(__file__).resolve().parents[1]/'data'/'processed'/'faq.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    assert len(data)>0 and all(x.get('respuesta') for x in data)
