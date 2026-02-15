import requests
import json

QDRANT_URL = "http://qdrant:6333/collections/pdf_rag"

try:
    response = requests.get(QDRANT_URL)
    if response.status_code == 200:
        data = response.json()
        config = data.get("result", {}).get("config", {}).get("params", {})
        vectors = config.get("vectors", {})
        
        print(f"✅ Collection 'pdf_rag' Found!")
        print(f"Full Config: {json.dumps(config, indent=2)}")
        
        if isinstance(vectors, dict):
             print(f"📏 Dimension: {vectors.get('size')}")
        else:
             # Legacy or single vector shorthand
             print(f"📏 Dimension: {vectors}")
             
    else:
        print(f"❌ Failed to get collection info. Status: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error: {e}")
