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
import spacy

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


try:
    es.indices.create(index=index_name, body=mapping)
except Exception as e:
    print("Mapping error details:", getattr(e, 'info', str(e)))



#Delete pervious index and create a new one: 
if es.indices.exists(index=index_name):
    es.indices.delete(index=index_name)
es.indices.create(index=index_name, body=mapping)
print(f"Index `{index_name}` đã được tạo!")



model = SentenceTransformer('all-MiniLM-L6-v2')


# In[11]:


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


# **Querry processing for better search**


#extract keywords for better keyword search
nlp = spacy.load("en_core_web_md")
def preprocess_bm25_query(query):
    doc = nlp(query)
    return " ".join([chunk.text.strip() for chunk in doc.noun_chunks if len(chunk.text.strip()) > 2])
#preprocess_bm25_query("suggest a noodle soup for breakfast near center")



#remove non-sense words 
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if",
    "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that",
    "the", "their", "then", "there", "these", "they", "this", "to", "was",
    "will", "with", "me", "my", "you", "your", "we", "our", "us", "he",
    "him", "his", "she", "her", "hers", "it", "its", "them", "so", "too"
}

def preprocess_query_for_vector(query):
    # Bỏ dấu câu (tuỳ chọn, để nguyên cũng được vì embedding model hiểu)
    query_no_punct = re.sub(r'[^\w\s]', '', query)
    # Bỏ stopword, giữ lại trật tự và ý nghĩa câu
    words = query_no_punct.split()
    filtered = [w for w in words if w.lower() not in STOP_WORDS]
    # Ghép lại thành câu ngắn gọn
    processed_query = " ".join(filtered) if filtered else query
    return processed_query

# Ví dụ:
#preprocess_query_for_vector( "Where to eat Bun Bo Hue in the evening?")
    #-> "Where eat Bun Bo Hue evening"


# **Search**




'''
def bm25_search(query, top_k=10):
    processed_query = preprocess_bm25_query(query)  # extract keyword
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": processed_query,
                "fields": ["name^3", "description^2", "note", "full_text"],
                "operator": "or",  
                "type": "most_fields"
            }
        }
    }
    res = es.search(index=index_name, body=body)
    return [
        {
            "id": hit["_source"]["id"],
            "score": hit["_score"],
            "full_text": hit["_source"]["full_text"]
        }
        for hit in res["hits"]["hits"]
    ]
'''
def bm25_search(query, top_k, type_filter=None):
    processed_query = preprocess_bm25_query(query)

    must_clauses = [
        {
            "multi_match": {
                "query": processed_query,
                "fields": ["name^3", "description^2", "note", "full_text"],
                "operator": "or",
                "type": "most_fields"
            }
        }
    ]

    # Nếu có filter, thêm điều kiện
    if type_filter:
        must_clauses.append({"term": {"type": type_filter}})

    body = {
        "size": top_k,
        "query": {
            "bool": {
                "must": must_clauses
            }
        }
    }

    res = es.search(index=index_name, body=body)
    return [
        {
            "id": hit["_source"]["id"],
            "score": hit["_score"],
            "name": hit["_source"]["name"],
            "description": hit["_source"]["description"],
            "time": hit["_source"]["time"],
            "price": hit["_source"]["price"],
            "location": hit["_source"]["location"],
            "area": hit["_source"]["area"],
            "note": hit["_source"]["note"],
            "type": hit["_source"]["type"]
        }
        for hit in res["hits"]["hits"]
    ]
#khi goi bm25_search(query, type_filter="eat") -> tim trong moi muc eat thoi 





'''
def vector_search(query, top_k=10):
    query_vec = model.encode(query).tolist()
    body = {
        "size": top_k,
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'vector_search') + 1.0",
                    "params": {"query_vector": query_vec}
                }
            }
        }
    }
    res = es.search(index=index_name, body=body)
    return [
        {
            "id": hit["_source"]["id"],
            "score": hit["_score"],
            "full_text": hit["_source"]["full_text"]
        }
        for hit in res["hits"]["hits"]
    ]
'''
def vector_search(query, top_k, type_filter=None):
    query = preprocess_query_for_vector(query)
    query_vec = model.encode(query).tolist()

    # Nếu có filter, dùng bool; nếu không, dùng match_all như cũ
    if type_filter:
        inner_query = {
            "bool": {
                "must": [
                    {"term": {"type": type_filter}}
                ]
            }
        }
    else:
        inner_query = {"match_all": {}}

    body = {
        "size": top_k,
        "query": {
            "script_score": {
                "query": inner_query,
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'vector_search') + 1.0",
                    "params": {"query_vector": query_vec}
                }
            }
        }
    }
    res = es.search(index=index_name, body=body)
    return [
        {
            "id": hit["_source"]["id"],
            "score": hit["_score"],
            "name": hit["_source"]["name"],
            "description": hit["_source"]["description"],
            "time": hit["_source"]["time"],
            "price": hit["_source"]["price"],
            "location": hit["_source"]["location"],
            "area": hit["_source"]["area"],
            "note": hit["_source"]["note"],
            "type": hit["_source"]["type"]
        }
        for hit in res["hits"]["hits"]
    ]
#vector_search(query, type_filter="eat")





def reciprocal_rank_fusion(lexical_hits, semantic_hits, k=60, top_k=5):
    rrf_scores = {}
    # Lexical hits
    for rank, hit in enumerate(lexical_hits, start=1):
        doc_id = hit["id"]
        score = 1 / (k + rank)
        if doc_id in rrf_scores:
            rrf_scores[doc_id]["rrf_score"] += score
            rrf_scores[doc_id]["lexical_score"] = hit["score"]
        else:
            rrf_scores[doc_id] = {**hit, "lexical_score": hit["score"], "semantic_score": 0, "rrf_score": score}
    # Semantic hits
    for rank, hit in enumerate(semantic_hits, start=1):
        doc_id = hit["id"]
        score = 1 / (k + rank)
        if doc_id in rrf_scores:
            rrf_scores[doc_id]["rrf_score"] += score
            rrf_scores[doc_id]["semantic_score"] = hit["score"]
        else:
            rrf_scores[doc_id] = {**hit, "lexical_score": 0, "semantic_score": hit["score"], "rrf_score": score}
    results = sorted(rrf_scores.values(), key=lambda x: x["rrf_score"], reverse=True)[:top_k]
    return results





'''
def hybrid_search(query, top_k=5, alpha=0.5):
    # BM25
    bm25_results = bm25_search(query, top_k=top_k*2)
    bm25_ids = {doc["id"]: doc for doc in bm25_results}

    # Vector
    vec_results = vector_search(query, top_k=top_k*2)
    vec_ids = {doc["id"]: doc for doc in vec_results}

    # Gộp tất cả id
    all_ids = set(bm25_ids.keys()) | set(vec_ids.keys())

    # Tính điểm hybrid
    hybrid_results = []
    for id_ in all_ids:
        bm25_score = bm25_ids.get(id_, {}).get("score", 0)
        vec_score = vec_ids.get(id_, {}).get("score", 0)
        score = (1 - alpha) * bm25_score + alpha * vec_score
        hybrid_results.append({
            "id": id_,
            "hybrid_score": score,
            "full_text": bm25_ids.get(id_, vec_ids.get(id_, {})).get("full_text", "")
        })

    # Sort theo điểm hybrid
    hybrid_results = sorted(hybrid_results, key=lambda x: x["hybrid_score"], reverse=True)[:top_k]
    return hybrid_results
'''
def hybrid_search(query, top_k, k_rrf=60, type_filter=None):
    bm25_results = bm25_search(query, top_k=top_k*2,type_filter=type_filter )   # Lấy nhiều hơn để RRF hiệu quả hơn
    vector_results = vector_search(query, top_k=top_k*2, type_filter=type_filter)
    results = reciprocal_rank_fusion(bm25_results, vector_results, k=k_rrf, top_k=top_k)
    return results


# **Testing search**

# In[71]:


#query = "Where to eat beef noodles"
#print("BM25:", bm25_search(query, type_filter = 'eat'))
#print("Vector:", vector_search(query, type_filter="see"))
#print("Hybrid:", hybrid_search(query, type_filter="eat"))


# **Build Prompt**


entry_template = """
Name: {name}
Type: {type}
Description: {description}
Time: {time}
Price: {price}
Location: {location}
Area: {area}
Note: {note}
""".strip()

prompt_template = """
You are a helpful local travel assistant for Da Nang. Answer the QUESTION based on the CONTEXT from our database of places to eat, see, and stay.
Only use the facts from the CONTEXT when answering the QUESTION. If you don't know, say you don't know.

QUESTION: {question}

CONTEXT:
{context}
""".strip()




def build_prompt(query, search_results):
    context = ""
    for doc in search_results:
        context += entry_template.format(**doc) + "\n\n"
    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt



'''
sample_query = "Where can I eat grilled fish in Da Nang?"
search_results = hybrid_search(sample_query, top_k=2, type_filter="eat")  # hoặc merged từ RRF
prompt = build_prompt(sample_query, search_results)
print(prompt)
'''



from openai import OpenAI

client = OpenAI(
    base_url='http://localhost:11434/v1/',
    api_key='ollama',  
)

def llm(prompt):
    response = client.chat.completions.create(
        model='llama3.2',
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def rag(query, type_filter=None, top_k=3):
    search_results = hybrid_search(query, top_k=top_k, type_filter=type_filter)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt)
    return answer

# Test end-to-end
#print(rag("Suggest a noodle soup for breakfast in the center", model="llama3.1", type_filter="eat"))







