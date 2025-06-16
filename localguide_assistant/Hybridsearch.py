
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import pandas as pd
from tqdm import tqdm
import re
import spacy
import os
import csv
import time
from datetime import datetime
#pip install google-generativeai

#Connect back to the es db 
es = Elasticsearch(
    hosts=["http://localhost:9200"],   
)

index_name = "places_danang"
model = SentenceTransformer('all-MiniLM-L6-v2')

def check_index_exists(es, index_name):
    return es.indices.exists(index=index_name)

if not check_index_exists(es, index_name):
    import subprocess
    subprocess.run(["python", "Indexing.py"])


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
You are a helpful local travel assistant for Da Nang. Answer the QUESTION using only the facts from the CONTEXT below. 
If multiple relevant places are mentioned, list them with detailed descriptions (price, time, location, and unique notes). 
Format your response in full sentences to help the traveler make an informed decision. If you do not know the answer, just say you do not know.



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

#from openai import OpenAI

'''
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
'''


import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=api_key)
modelgpt = genai.GenerativeModel('gemma-3-12b-it')

def llm(prompt):
    response = modelgpt.generate_content(prompt)
    return response.text
    
def log_to_csv(question, answer, latency, status="ok"):
    with open("chat_log.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # timestamp
            question,
            answer,
            latency,
            status
        ])

def rag(query, type_filter=None, top_k=3):
    search_results = hybrid_search(query, top_k=top_k, type_filter=type_filter)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt)
    #start_time = time.time()
    #answer = llm(prompt)
    #latency = round(time.time() - start_time, 3)
    #log_to_csv(user_question, answer, latency)

    return answer

# Test end-to-end
#print(rag("Suggest a noodle soup for breakfast in the center", model="llama3.1", type_filter="eat"))








