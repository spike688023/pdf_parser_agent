"""
Test script to verify Vertex AI Vector Search data
"""
import os
import sys
import numpy as np
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vertex_search import VertexVectorStore
from src.firestore_db import get_firestore_db

load_dotenv()

def test_vector_search():
    """Test vector search with random query"""
    print("\n" + "="*60)
    print("🔍 Testing Vertex AI Vector Search")
    print("="*60)
    
    try:
        # Initialize Vertex AI
        vertex_store = VertexVectorStore(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            index_endpoint_name=os.getenv("VERTEX_INDEX_ENDPOINT_NAME"),
            deployed_index_id=os.getenv("VERTEX_DEPLOYED_INDEX_ID")
        )
        
        print(f"\n✅ Connected to Vertex AI")
        print(f"   Project: {vertex_store.project_id}")
        print(f"   Location: {vertex_store.location}")
        print(f"   Endpoint: {vertex_store.index_endpoint_name}")
        print(f"   Deployed Index: {vertex_store.deployed_index_id}")
        
        # Generate random query vector (1024 dimensions for nvidia/llama-3.2-nv-embedqa-1b-v2)
        print(f"\n🎲 Generating random query vector (1024 dimensions)...")
        query_vector = np.random.rand(1024).astype('float32')
        
        # Search for similar vectors
        print(f"🔎 Searching for top 10 similar vectors...")
        results = vertex_store.search(query_vector, k=10)
        
        print(f"\n📊 Search Results:")
        print(f"   Found: {len(results)} vectors")
        
        if results:
            print(f"\n   Top matches:")
            for i, result in enumerate(results, 1):
                print(f"   {i}. ID: {result['id']}")
                print(f"      Distance: {result['distance']:.4f}")
                print()
        else:
            print(f"\n   ⚠️  No vectors found in index")
            print(f"   This means no documents have been indexed yet.")
            
        return len(results) > 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_firestore_chunks():
    """Check how many chunks are stored in Firestore"""
    print("\n" + "="*60)
    print("📦 Checking Firestore for Document Chunks")
    print("="*60)
    
    try:
        firestore_db = get_firestore_db(session_id="test")
        
        # Get all documents
        docs = firestore_db.get_all_documents()
        
        print(f"\n📄 Documents in Firestore: {len(docs)}")
        
        total_chunks = 0
        for doc in docs:
            doc_id = doc.get('document_id', 'unknown')
            doc_name = doc.get('document_name', 'unknown')
            chunk_count = doc.get('chunk_count', 0)
            total_chunks += chunk_count
            
            print(f"\n   Document: {doc_name}")
            print(f"   ID: {doc_id}")
            print(f"   Chunks: {chunk_count}")
            
        print(f"\n📊 Total chunks across all documents: {total_chunks}")
        print(f"   Expected vectors in Vertex AI: {total_chunks}")
        
        return total_chunks
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 0


def main():
    print("\n" + "="*60)
    print("🚀 Vertex AI Vector Data Verification")
    print("="*60)
    
    # Check Firestore chunks
    expected_chunks = check_firestore_chunks()
    
    # Test vector search
    has_vectors = test_vector_search()
    
    # Summary
    print("\n" + "="*60)
    print("📋 Summary")
    print("="*60)
    
    if expected_chunks > 0:
        print(f"✅ Firestore has {expected_chunks} chunks")
    else:
        print(f"⚠️  No chunks found in Firestore")
        
    if has_vectors:
        print(f"✅ Vertex AI has indexed vectors")
    else:
        print(f"⚠️  No vectors found in Vertex AI")
        
    if expected_chunks > 0 and has_vectors:
        print(f"\n🎉 Vector indexing is working correctly!")
    elif expected_chunks > 0 and not has_vectors:
        print(f"\n⚠️  Chunks exist but not indexed in Vertex AI")
        print(f"   This might mean indexing is still in progress.")
    else:
        print(f"\n💡 Upload a PDF document to test vector indexing")
    
    print("="*60)


if __name__ == "__main__":
    main()
