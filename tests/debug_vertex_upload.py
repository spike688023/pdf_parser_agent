"""
Debug script to test Vertex AI vector upload
"""
import os
import sys
import numpy as np
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vertex_search import VertexVectorStore

load_dotenv()

def test_upload_vectors():
    """Test uploading vectors to Vertex AI"""
    print("\n" + "="*60)
    print("🧪 Testing Vertex AI Vector Upload")
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
        print(f"   Endpoint: {vertex_store.index_endpoint_name}")
        print(f"   Deployed Index: {vertex_store.deployed_index_id}")
        
        # Create test vectors
        print(f"\n📝 Creating test vectors...")
        test_ids = ["test_vector_1", "test_vector_2", "test_vector_3"]
        test_embeddings = np.random.rand(3, 1024).astype('float32')
        
        print(f"   IDs: {test_ids}")
        print(f"   Embeddings shape: {test_embeddings.shape}")
        
        # Upload to Vertex AI
        print(f"\n⬆️  Uploading vectors to Vertex AI...")
        vertex_store.add_items(test_ids, test_embeddings)
        
        print(f"\n✅ Upload completed!")
        print(f"\n⏳ Waiting for indexing (this may take a few seconds)...")
        import time
        time.sleep(5)
        
        # Test search
        print(f"\n🔍 Testing search with first test vector...")
        results = vertex_store.search(test_embeddings[0], k=5)
        
        print(f"\n📊 Search Results:")
        print(f"   Found: {len(results)} vectors")
        
        if results:
            print(f"\n   Matches:")
            for i, result in enumerate(results, 1):
                print(f"   {i}. ID: {result['id']}")
                print(f"      Distance: {result['distance']:.4f}")
                if result['id'] in test_ids:
                    print(f"      ✅ Test vector found!")
                print()
        else:
            print(f"\n   ⚠️  No results found")
            print(f"   Indexing might still be in progress...")
            
        return len(results) > 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_upload_vectors()
    
    print("\n" + "="*60)
    if success:
        print("🎉 Vector upload test PASSED!")
    else:
        print("⚠️  Vector upload test FAILED or indexing in progress")
    print("="*60)
