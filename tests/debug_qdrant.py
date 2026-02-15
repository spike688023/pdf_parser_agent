
import sys
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid

# Connect to Qdrant inside cluster
client = QdrantClient(host="qdrant", port=6333)

def test_upsert(dim, batch_size):
    print(f"Testing upsert with dim={dim}, batch_size={batch_size}")
    points = []
    for i in range(batch_size):
        points.append(models.PointStruct(
            id=str(uuid.uuid4()),
            vector=np.random.rand(dim).tolist(),
            payload={"text": "test payload " * 100}
        ))
    
    try:
        client.upsert(
            collection_name="pdf_rag",
            points=points
        )
        print("✅ Upsert success!")
    except Exception as e:
        print(f"❌ Upsert failed: {e}")

# Test 1: 1024 dimension (current setting)
test_upsert(1024, 50)

# Test 2: 768 dimension (common alternative)
test_upsert(768, 50)

