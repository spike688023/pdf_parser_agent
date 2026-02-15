import requests
import os

# Hardcode host and port to avoid K8s env var conflict
QDRANT_HOST = "qdrant"
QDRANT_PORT = "6333"
URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/pdf_rag"

print(f"📡 Checking Qdrant at: {URL}")

try:
    response = requests.get(URL, timeout=5)
    if response.status_code == 200:
        data = response.json().get("result", {})
        points_count = data.get("points_count", "N/A")
        vectors_count = data.get("vectors_count", "N/A")
        
        print(f"✅ Success! Collection 'pdf_rag' exists.")
        print(f"📊 Points Count: {points_count}")
        print(f"🧩 Vectors Count: {vectors_count}")
        
        if points_count == 0:
            print("⚠️  Warning: Collection exists but is empty (0 points).")
    else:
        print(f"❌ Failed. Status: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Connection Error: {e}")
