"""
Check uploaded PDF data in Firestore and Vertex AI
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.firestore_db import get_firestore_db
from src.vertex_search import VertexVectorStore
from google.cloud import firestore

load_dotenv()

def check_firestore_data(session_id):
    """Check Firestore for uploaded documents"""
    print("\n" + "="*60)
    print(f"📦 Checking Firestore for session: {session_id}")
    print("="*60)
    
    try:
        # Get Firestore client
        db = firestore.Client(
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            database=os.getenv("FIRESTORE_DATABASE", "(default)")
        )
        
        # Check documents collection
        docs_ref = db.collection('documents')
        docs = list(docs_ref.stream())
        
        print(f"\n📄 Total documents in Firestore: {len(docs)}")
        
        for doc in docs:
            data = doc.to_dict()
            print(f"\n   Document ID: {doc.id}")
            print(f"   Name: {data.get('document_name', 'N/A')}")
            print(f"   File Path: {data.get('file_path', 'N/A')}")
            print(f"   Chunks: {data.get('chunk_count', 0)}")
            print(f"   Tags: {data.get('tags', 'N/A')}")
            print(f"   Created: {data.get('created_at', 'N/A')}")
        
        # Check chunks collection
        chunks_ref = db.collection('chunks')
        chunks = list(chunks_ref.stream())
        
        print(f"\n📝 Total chunks in Firestore: {len(chunks)}")
        
        if chunks:
            print(f"\n   Sample chunks:")
            for i, chunk in enumerate(chunks[:3], 1):
                data = chunk.to_dict()
                print(f"\n   Chunk {i}:")
                print(f"   ID: {chunk.id}")
                print(f"   Document ID: {data.get('document_id', 'N/A')}")
                print(f"   Page: {data.get('page_number', 'N/A')}")
                print(f"   Text preview: {data.get('text', '')[:100]}...")
        
        return len(docs), len(chunks)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0


def check_vertex_vectors():
    """Check Vertex AI for vectors"""
    print("\n" + "="*60)
    print("🔍 Checking Vertex AI Vector Search")
    print("="*60)
    
    try:
        vertex_store = VertexVectorStore(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            index_endpoint_name=os.getenv("VERTEX_INDEX_ENDPOINT_NAME"),
            deployed_index_id=os.getenv("VERTEX_DEPLOYED_INDEX_ID")
        )
        
        import numpy as np
        query_vector = np.random.rand(384).astype('float32')
        results = vertex_store.search(query_vector, k=10)
        
        print(f"\n📊 Vectors found: {len(results)}")
        
        if results:
            print(f"\n   Sample vector IDs:")
            for i, result in enumerate(results[:5], 1):
                print(f"   {i}. {result['id']} (distance: {result['distance']:.2f})")
        
        return len(results)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 0


if __name__ == "__main__":
    session_id = "e7c6e754-9786-4e42-8078-7cc7c9d4c74c"
    
    doc_count, chunk_count = check_firestore_data(session_id)
    vector_count = check_vertex_vectors()
    
    print("\n" + "="*60)
    print("📋 Summary")
    print("="*60)
    print(f"Documents in Firestore: {doc_count}")
    print(f"Chunks in Firestore: {chunk_count}")
    print(f"Vectors in Vertex AI: {vector_count}")
    
    if chunk_count > 0 and vector_count > 0:
        print(f"\n✅ Data successfully uploaded to cloud!")
    elif chunk_count > 0 and vector_count == 0:
        print(f"\n⚠️  Chunks exist but vectors not indexed")
    else:
        print(f"\n⚠️  No data found")
    print("="*60)
