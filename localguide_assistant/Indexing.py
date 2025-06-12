#!/usr/bin/env python
# coding: utf-8
#get_ipython().system('pip install sentence-transformers pandas tqdm')
#get_ipython().system('python -m spacy download en_core_web_md')
#get_ipython().system('pip install "elasticsearch<9"')

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import pandas as pd
from tqdm import tqdm
import re

print(">>> ĐANG RUN INDEXING.PY <<<")

es = Elasticsearch(
    hosts=["http://localhost:9200"],   
)

index_name = "places_danang"

mapping = {
    "mappings": {
        "properties": {
            "type": {"type": "keyword"},
            "name": {"type": "text"},
            "description": {"type": "text"},
            "time": {"type": "keyword"},
            "price": {"type": "keyword"},
            "location": {"type": "text"},
            "area": {"type": "keyword"},
            "note": {"type": "text"},
            "id": {"type": "keyword"},
            "full_text": {"type": "text"},  
            "vector_search": {
                "type": "dense_vector",
                "dims": 384,  
                "index": True,           
                "similarity": "cosine"  
            }
        }
    }
}


if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body=mapping)
    print(f"Index `{index_name}` đã được tạo!")
else:
    print(f"Index `{index_name}` đã tồn tại. Không tạo lại.")



model = SentenceTransformer('all-MiniLM-L6-v2')
df = pd.read_csv("Data/data_danang_ok.csv")# Đường dẫn file của bạn


def embed(text):
    return model.encode(text).tolist()


tqdm.pandas()
df["vector_search"] = df["full_text"].progress_apply(embed)

#indexing data to elasticsearch
for i, row in tqdm(df.iterrows(), total=len(df)):
    doc = row.to_dict()
    # Nếu vector_search dạng numpy, cần chuyển sang list
    es.index(index=index_name, id=doc["id"], document=doc)
