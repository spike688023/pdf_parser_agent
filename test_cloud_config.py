"""
Cloud Native Configuration Test Script
Tests GCS, Vertex AI, and Firestore integration
"""
import os
from dotenv import load_dotenv

load_dotenv()

def test_environment_variables():
    """Test that all required environment variables are set"""
    print("=" * 50)
    print("1️⃣  Testing Environment Variables")
    print("=" * 50)
    
    required_vars = [
        "GOOGLE_API_KEY",
        "GCS_BUCKET_NAME",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "USE_VERTEX_AI",
        "USE_FIRESTORE",
        "VERTEX_INDEX_ENDPOINT_NAME",
        "VERTEX_DEPLOYED_INDEX_ID"
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        print(f"{status} {var}: {value if value else 'NOT SET'}")
        if not value:
            all_set = False
    
    return all_set

def test_gcs_connection():
    """Test GCS connection and bucket access"""
    print("\n" + "=" * 50)
    print("2️⃣  Testing GCS Connection")
    print("=" * 50)
    
    try:
        from src.gcs_storage import get_gcs_storage
        gcs = get_gcs_storage()
        
        # List files
        files = gcs.list_files()
        print(f"✅ GCS Connection successful")
        print(f"   Bucket: {gcs.bucket_name}")
        print(f"   Files found: {len(files)}")
        for f in files[:3]:
            print(f"   - {f}")
        return True
    except Exception as e:
        print(f"❌ GCS Connection failed: {e}")
        return False

def test_vertex_ai_connection():
    """Test Vertex AI Vector Search connection"""
    print("\n" + "=" * 50)
    print("3️⃣  Testing Vertex AI Connection")
    print("=" * 50)
    
    try:
        from src.vertex_search import VertexVectorStore
        import numpy as np
        
        vertex_store = VertexVectorStore(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            index_endpoint_name=os.getenv("VERTEX_INDEX_ENDPOINT_NAME"),
            deployed_index_id=os.getenv("VERTEX_DEPLOYED_INDEX_ID")
        )
        
        # Test search with dummy embedding
        dummy_embedding = np.random.rand(384).astype('float32')
        results = vertex_store.search(dummy_embedding, k=1)
        
        print(f"✅ Vertex AI Connection successful")
        print(f"   Endpoint: {vertex_store.index_endpoint_name}")
        print(f"   Deployed Index ID: {vertex_store.deployed_index_id}")
        print(f"   Search results: {len(results)} items")
        return True
    except Exception as e:
        print(f"❌ Vertex AI Connection failed: {e}")
        return False

def test_firestore_connection():
    """Test Firestore connection"""
    print("\n" + "=" * 50)
    print("4️⃣  Testing Firestore Connection")
    print("=" * 50)
    
    try:
        from src.firestore_db import get_firestore_db
        
        firestore_db = get_firestore_db(session_id="test_session")
        
        # Test write
        firestore_db.save_document_metadata(
            document_id="test_doc",
            document_name="Test Document",
            file_path="gs://test/test.pdf",
            tags="test",
            chunk_count=1
        )
        
        # Test read
        doc = firestore_db.get_document_metadata("test_doc")
        
        # Cleanup
        firestore_db.delete_document("test_doc")
        
        print(f"✅ Firestore Connection successful")
        print(f"   Project: {firestore_db.project_id}")
        print(f"   Database: {firestore_db.database}")
        print(f"   Test document created and deleted successfully")
        return True
    except Exception as e:
        print(f"❌ Firestore Connection failed: {e}")
        return False

def test_database_integration():
    """Test VectorStore with cloud services"""
    print("\n" + "=" * 50)
    print("5️⃣  Testing Database Integration")
    print("=" * 50)
    
    try:
        from src.database import VectorStore
        
        vector_store = VectorStore(session_id="test_integration")
        
        print(f"✅ VectorStore initialized")
        print(f"   Using Firestore: {vector_store.use_firestore}")
        print(f"   Using Vertex AI: {vector_store.use_vertex_ai}")
        
        return True
    except Exception as e:
        print(f"❌ Database Integration failed: {e}")
        return False

def main():
    print("\n🚀 Cloud Native Configuration Test")
    print("=" * 50)
    
    results = {
        "Environment Variables": test_environment_variables(),
        "GCS Connection": test_gcs_connection(),
        "Vertex AI Connection": test_vertex_ai_connection(),
        "Firestore Connection": test_firestore_connection(),
        "Database Integration": test_database_integration()
    }
    
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Cloud Native configuration is ready.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    print("=" * 50)
    
    return all_passed

if __name__ == "__main__":
    main()
