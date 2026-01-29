"""
Test PDF ingestion flow to debug why data isn't being saved
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import VectorStore, set_session_vector_store
from src.rag_engine import ingest_pdf_tool
from src.firestore_db import get_firestore_db
from google.cloud import firestore

load_dotenv()

async def test_pdf_ingestion():
    """Test the full PDF ingestion flow"""
    print("\n" + "="*60)
    print("🧪 Testing PDF Ingestion Flow")
    print("="*60)
    
    # Use one of the uploaded PDFs from GCS
    gcs_uri = "gs://my-pdf-files__spike688023/uploads/e7c6e754-9786-4e42-8078-7cc7c9d4c74c/Prototype to Production.pdf"
    session_id = "test_ingestion_session"
    
    try:
        # 1. Create session vector store
        print(f"\n1️⃣  Creating VectorStore for session: {session_id}")
        vector_store = VectorStore(session_id=session_id)
        set_session_vector_store(vector_store)  # Set it globally
        
        print(f"   ✅ VectorStore created")
        print(f"   Using Firestore: {vector_store.use_firestore}")
        print(f"   Using Vertex AI: {vector_store.use_vertex_ai}")
        
        # 2. Ingest PDF
        print(f"\n2️⃣  Ingesting PDF from GCS...")
        print(f"   URI: {gcs_uri}")
        
        result = await ingest_pdf_tool(gcs_uri, original_filename="Prototype to Production.pdf")
        
        print(f"\n   Result: {result}")
        
        # 3. Check Firestore
        print(f"\n3️⃣  Checking Firestore...")
        db = firestore.Client(
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            database=os.getenv("FIRESTORE_DATABASE", "(default)")
        )
        
        docs = list(db.collection('documents').stream())
        chunks = list(db.collection('chunks').stream())
        
        print(f"   Documents: {len(docs)}")
        print(f"   Chunks: {len(chunks)}")
        
        if docs:
            for doc in docs:
                data = doc.to_dict()
                print(f"\n   Document: {data.get('document_name')}")
                print(f"   Chunks: {data.get('chunk_count')}")
        
        # 4. Check Vertex AI
        print(f"\n4️⃣  Checking Vertex AI...")
        from src.vertex_search import VertexVectorStore
        import numpy as np
        
        vertex_store = VertexVectorStore(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            index_endpoint_name=os.getenv("VERTEX_INDEX_ENDPOINT_NAME"),
            deployed_index_id=os.getenv("VERTEX_DEPLOYED_INDEX_ID")
        )
        
        query_vector = np.random.rand(1024).astype('float32')
        results = vertex_store.search(query_vector, k=10)
        
        # Filter out test vectors
        real_vectors = [r for r in results if not r['id'].startswith('test_vector')]
        
        print(f"   Total vectors: {len(results)}")
        print(f"   Real document vectors: {len(real_vectors)}")
        
        if real_vectors:
            print(f"\n   Sample vector IDs:")
            for i, result in enumerate(real_vectors[:5], 1):
                print(f"   {i}. {result['id']}")
        
        # Summary
        print(f"\n" + "="*60)
        print("📋 Summary")
        print("="*60)
        
        if len(docs) > 0 and len(chunks) > 0 and len(real_vectors) > 0:
            print("✅ PDF ingestion successful!")
            print(f"   Documents: {len(docs)}")
            print(f"   Chunks: {len(chunks)}")
            print(f"   Vectors: {len(real_vectors)}")
        else:
            print("⚠️  PDF ingestion incomplete:")
            print(f"   Documents in Firestore: {len(docs)}")
            print(f"   Chunks in Firestore: {len(chunks)}")
            print(f"   Vectors in Vertex AI: {len(real_vectors)}")
        
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_pdf_ingestion())
