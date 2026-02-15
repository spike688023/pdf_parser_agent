import requests
import os
import sys

EMBEDDING_SERVICE_URL = "http://nim-embedding:8000/v1/embeddings"
MODEL_NAME = "nvidia/llama-3.2-nv-embedqa-1b-v2"

print(f"Testing Embedding Model: {MODEL_NAME}")
print(f"URL: {EMBEDDING_SERVICE_URL}")

payload = {
    "input": ["Hello world"],
    "model": MODEL_NAME,
    "input_type": "query",
    "encoding_format": "float"
}

try:
    response = requests.post(EMBEDDING_SERVICE_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    embedding = data["data"][0]["embedding"]
    dim = len(embedding)
    
    print(f"✅ Success! Embedding Dimension: {dim}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    if hasattr(e, 'response') and e.response:
        print(f"Response: {e.response.text}")
